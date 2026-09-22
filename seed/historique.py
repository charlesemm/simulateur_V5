"""Remplit les tables d'opérations avec un historique antidaté, sans attente.

    python -m seed.historique --debut 2026-06-01 --fin 2026-09-20 --par-jour 7000
    python -m seed.historique --purger        supprime tout ce que l'outil a écrit

Le moteur temps réel ne peut pas produire un tel volume : son horloge part de
« maintenant » et il attend réellement entre les étapes. Ici on tire les dates
soi-même et on écrit par lots (COPY), un jour à la fois, chaque jour dans sa
propre transaction.

Les règles sont celles du passage (simulation/passage.py) : type de facture
tiré à parts égales, prestation sur un acte de la famille, montant autour du
tarif (plafonné pour l'hospitalisation), taux du régime, entente préalable pour
BIO et HOS toujours et pour les autres types une fois sur trois environ, et
droits ouverts au mois des soins. Aucune anomalie n'est injectée.

Tout ce qui est écrit porte le `simulation_id` d'une ligne de TB_SIMULATIONS
de type « historique » : c'est ce qui permet de tout retirer d'un coup.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import asyncpg

from seed.identifiants import numero
from simulation.passage import (
    ACTES_PAR_TYPE_FACTURE, LIBELLES_TYPE_CENTRE, PROBABILITE_ENTENTE_AUTRES,
    TARIFS_ACTES, TYPES_FACTURE, montant_autour,
)
from simulation_config import DEFAULT_CONFIG

TYPE_SIMULATION = "historique"
UTILISATEUR = "historique"
SEQ_FACTURE = '"SEQ_FACTURE_NUMERO"'
SEQ_ENTENTE = '"TB_ENTENTES_PREALABLES_ENTENTE_PREALABLE_ID_seq"'
# Poids de chaque jour de la semaine (lundi = 0) : le week-end est plus calme.
POIDS_JOUR = (1.10, 1.10, 1.10, 1.10, 1.10, 0.55, 0.20)

COLONNES = {
    "TB_FACTURES": [
        "FACTURE_NUMERO", "PRODUIT_CODE", "REGIME_CODE", "REGIME_TAUX", "ORGANISME_CODE",
        "ASSURANCE_CODE", "PERSONNE_UUID", "TYPE_FACTURE_CODE", "FACTURE_DATE_SOINS",
        "DOSSIER_NUMERO", "CENTRE_SANTE_CODE", "CENTRE_SANTE_TYPE_CODE",
        "CENTRE_SANTE_TYPE_LIBELLE", "SIMULATION_ID", "DATE_CREATION",
        "UTILISATEUR_ID_CREATION"],
    "TB_FACTURES_STATUTS": [
        "FACTURE_NUMERO", "STATUT_CODE", "STATUT_DATE_DEBUT", "STATUT_OBSERVATIONS",
        "SIMULATION_ID", "DATE_CREATION", "UTILISATEUR_ID_CREATION"],
    "TB_FACTURES_PATHOLOGIES": [
        "FACTURE_NUMERO", "PATHOLOGIE_CODE", "PATHOLOGIE_DATE_DEBUT",
        "PATHOLOGIE_OBSERVATIONS", "SIMULATION_ID", "DATE_CREATION",
        "UTILISATEUR_ID_CREATION"],
    "TB_FACTURES_PRESCRIPTIONS": [
        "FACTURE_NUMERO", "PRESCRIPTION_CODE", "DATE_DEBUT", "PRESCRIPTION_QUANTITE",
        "PRESCRIPTION_POSOLOGIE", "PRESCRIPTION_DUREE", "SIMULATION_ID",
        "DATE_CREATION", "UTILISATEUR_ID_CREATION"],
    "TB_FACTURES_PRESTATIONS": [
        "FACTURE_NUMERO", "PRESTATION_CODE", "PROFESSIONNEL_SANTE_CODE",
        "STATUT_REMBOURSEMENT", "PRESTATION_BASE_REMBOURSEMENT",
        "PRESTATION_TAUX_REMBOURSEMENT", "PRESTATION_QUANTITE_PRESCRITE",
        "PRESTATION_QUANTITE_SERVIE", "PRESTATION_PRIX_UNITAIRE",
        "PRESTATION_MONTANT_DEPENSE", "PRESTATION_MONTANT_RQ",
        "PRESTATION_MONTANT_ASSURE", "STATUT_CODE", "SIMULATION_ID",
        "DATE_CREATION", "UTILISATEUR_ID_CREATION"],
    "TB_ENTENTES_PREALABLES": [
        "ENTENTE_PREALABLE_ID", "ENTENTE_PREALABLE_NUMERO", "CENTRE_SANTE_CODE",
        "PERSONNE_UUID", "DOSSIER_NUMERO", "ENTENTE_PREALABLE_DATE_DEBUT",
        "ENTENTE_PREALABLE_DATE_FIN", "ORGANISME_CODE", "FACTURE_NUMERO",
        "TYPE_DEMANDE_CODE", "TYPE_HOSPITALISATION_CODE", "SIMULATION_ID",
        "DATE_CREATION", "UTILISATEUR_ID_CREATION"],
    "TB_ENTENTES_PREALABLES_ACTES_MEDICAUX": [
        "ENTENTE_PREALABLE_ID", "ACTE_MEDICAL_CODE", "PROFESSIONNEL_SANTE_CODE",
        "ACTE_MEDICAL_MOTIF", "ACTE_MEDICAL_BASE_REMBOURSEMENT",
        "ACTE_MEDICAL_TAUX_REMBOURSEMENT", "ACTE_MEDICAL_MONTANT_CMU",
        "ACTE_MEDICAL_MONTANT_ASSURE", "ACTE_MEDICAL_STATUT",
        "ACTE_MEDICAL_MOTIF_REJET", "SIMULATION_ID", "DATE_CREATION",
        "UTILISATEUR_ID_CREATION"],
    "TB_ENTENTES_PREALABLES_STATUTS": [
        "ENTENTE_PREALABLE_ID", "STATUT_CODE", "STATUT_DATE_DEBUT", "AGENT_CODE",
        "SIMULATION_ID", "DATE_CREATION", "UTILISATEUR_ID_CREATION"],
}
# Ordre d'écriture (et, à l'envers, de suppression) : les factures d'abord,
# puis les ententes qui les référencent, puis les lignes filles.
ORDRE = list(COLONNES)


def _dsn() -> str:
    """Base cible : HISTORIQUE_DATABASE_URL, à défaut celle du compose.

    DATABASE_URL n'est volontairement pas lue : importer le moteur charge le
    `.env`, qui vise ici le PostgreSQL natif du poste et non celui du conteneur.
    """

    url = os.environ.get("HISTORIQUE_DATABASE_URL",
                         "postgresql://echo:echo_dev_2026@localhost:5433/echo_db")
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _heure_de_soins(jour: date, tirage: random.Random) -> datetime:
    """Heure d'arrivée : pic en fin de matinée, rien la nuit."""

    heures = tirage.triangular(7.0, 19.0, 10.5)
    debut = datetime.combine(jour, time(0), tzinfo=timezone.utc)
    return debut + timedelta(seconds=int(heures * 3600))


def _quantifier(valeur: Decimal) -> Decimal:
    return valeur.quantize(Decimal("0.01"))


def plan_des_jours(debut: date, fin: date, par_jour: int) -> list[tuple[date, int]]:
    """Nombre de factures de chaque jour : moyenne `par_jour`, week-end plus calme."""

    jours = [debut + timedelta(days=i) for i in range((fin - debut).days + 1)]
    moyenne = sum(POIDS_JOUR[j.weekday()] for j in jours) / len(jours)
    return [(j, round(par_jour * POIDS_JOUR[j.weekday()] / moyenne)) for j in jours]


class Referentiels:
    """Ce dont le tirage a besoin, lu une fois."""

    async def charger(self, cx: asyncpg.Connection, debut: date, fin: date) -> None:
        self.taux = {r["REGIME_CODE"]: Decimal(r["REGIME_TAUX"]) for r in await cx.fetch(
            'SELECT DISTINCT ON ("REGIME_CODE") "REGIME_CODE","REGIME_TAUX" FROM "TB_TV_REGIMES" '
            'WHERE "REGIME_DATE_FIN" IS NULL ORDER BY "REGIME_CODE","REGIME_DATE_DEBUT" DESC')}
        self.centres = [(r["CENTRE_SANTE_CODE"], r["TYPE_ETABLISSEMENT_SANITAIRE_CODE"])
                        for r in await cx.fetch(
            'SELECT "CENTRE_SANTE_CODE","TYPE_ETABLISSEMENT_SANITAIRE_CODE" FROM "TB_REF_CENTRES_SANTE"')]
        par_centre: dict[str, list[str]] = {}
        for r in await cx.fetch('SELECT "CENTRE_SANTE_CODE","PROFESSIONNEL_SANTE_CODE" '
                                'FROM "TB_PROFESSIONNELS_SANTE_CENTRES_SANTE" WHERE "DATE_FIN" IS NULL'):
            par_centre.setdefault(r["CENTRE_SANTE_CODE"], []).append(r["PROFESSIONNEL_SANTE_CODE"])
        self.professionnels = par_centre
        self.centres = [c for c in self.centres if c[0] in par_centre]
        self.pathologies = [(r[0], r[1]) for r in await cx.fetch(
            'SELECT "PATHOLOGIE_CODE","PATHOLOGIE_DATE_DEBUT" FROM "TB_REF_PATHOLOGIES"')]
        self.medicaments = [r[0] for r in await cx.fetch(
            'SELECT "MEDICAMENT_CODE" FROM "TB_REF_MEDICAMENTS"')]
        # Le tarif vient de seed/constants : la colonne ACTE_MEDICAL_TARIF
        # n'existe que sur une base migrée en 0026, ce que le moteur contourne
        # de la même façon (repli sur TARIFS_ACTES).
        self.actes = dict(TARIFS_ACTES)
        self.conseillers = [r[0] for r in await cx.fetch(
            'SELECT "AGENT_CODE" FROM "TB_REF_AGENTS" WHERE "AGENT_TYPE_CODE"=\'medecin_conseil\'')]
        # Assurés aux droits ouverts, mois par mois : c'est le contrôle de
        # l'accueil du moteur (statut 1 = ouvert, absence de ligne = fermé).
        self.assures: dict[tuple[int, int], list[tuple[uuid.UUID, str]]] = {}
        mois = {(debut.year, debut.month)}
        jour = debut
        while jour <= fin:
            mois.add((jour.year, jour.month))
            jour += timedelta(days=28)
        mois.add((fin.year, fin.month))
        for annee, m in sorted(mois):
            rows = await cx.fetch(
                'SELECT d."PERSONNE_UUID", a."REGIME_CODE" FROM "TB_ASSURES_DROITS" d '
                'JOIN "TB_REF_ASSURES" a USING ("PERSONNE_UUID") '
                'WHERE d."DROITS_ANNEE"=$1 AND d."DROITS_MOIS"=$2 AND d."DROITS_STATUT"=1',
                annee, m)
            self.assures[(annee, m)] = [(r[0], r[1]) for r in rows if r[1] in self.taux]
        vides = [k for k, v in self.assures.items() if not v]
        if vides or not self.centres or not self.pathologies or not self.conseillers:
            raise SystemExit(f"Référentiels incomplets (mois sans droits ouverts : {vides}).")


class Lots:
    """Lignes d'une journée, par table."""

    def __init__(self) -> None:
        self.lignes: dict[str, list[tuple]] = {t: [] for t in COLONNES}
        # (numéro de facture, index de l'entente dans lignes["TB_ENTENTES_PREALABLES"])
        self.liens: list[tuple[str, int]] = []


def facture_du_jour(ref: Referentiels, tirage: random.Random, lots: Lots, sim: uuid.UUID,
                    jour: date, aujourdhui: date, numero_facture: str,
                    numeros_utilises: set[str], config=DEFAULT_CONFIG) -> None:
    """Un passage complet, écrit d'un coup dans `lots`."""

    quand = _heure_de_soins(jour, tirage)
    personne, regime = tirage.choice(ref.assures[(jour.year, jour.month)])
    taux = ref.taux[regime]
    centre, type_centre = tirage.choice(ref.centres)
    professionnel = tirage.choice(ref.professionnels[centre])
    type_facture = tirage.choice(TYPES_FACTURE)
    hospitalisation = type_facture == "HOS"
    dossier = f"{tirage.getrandbits(32):08X}"

    lots.lignes["TB_FACTURES"].append((
        numero_facture, "CMU", regime, taux, "CNAM-CI", "CMU", personne, type_facture, jour,
        dossier, centre, type_centre, LIBELLES_TYPE_CENTRE.get(type_centre), sim, quand,
        UTILISATEUR))
    cloture = min(jour + timedelta(days=tirage.choice((0, 0, 0, 1, 1, 2, 3))), aujourdhui)
    for code, date_statut in (("ouverte", jour), ("cloturee", cloture)):
        lots.lignes["TB_FACTURES_STATUTS"].append((
            numero_facture, code, date_statut, "Statut produit par l'historique.", sim, quand,
            UTILISATEUR))

    for pathologie, debut_pathologie in tirage.sample(ref.pathologies, tirage.randint(1, 3)):
        lots.lignes["TB_FACTURES_PATHOLOGIES"].append((
            numero_facture, pathologie, debut_pathologie,
            "Diagnostic synthétique du simulateur.", sim, quand, UTILISATEUR))

    acte = tirage.choice(ACTES_PAR_TYPE_FACTURE[type_facture])
    base = montant_autour(ref.actes[acte], tirage, hospitalisation=hospitalisation)
    reste_a_charge = _quantifier(base * taux / Decimal("100"))
    lots.lignes["TB_FACTURES_PRESTATIONS"].append((
        numero_facture, acte, professionnel, "couvert", base, taux, Decimal(1), Decimal(1),
        base, base, reste_a_charge, base - reste_a_charge, "servie", sim, quand, UTILISATEUR))

    if type_facture == "PHA" or tirage.random() < config.medication_probability:
        lots.lignes["TB_FACTURES_PRESCRIPTIONS"].append((
            numero_facture, tirage.choice(ref.medicaments), jour, Decimal(1),
            "Selon prescription médicale synthétique.", 5, sim, quand, UTILISATEUR))

    if type_facture in ("BIO", "HOS") or tirage.random() < PROBABILITE_ENTENTE_AUTRES:
        _entente(ref, tirage, lots, sim, quand, numero_facture, dossier, personne, centre,
                 professionnel, type_facture, taux, numeros_utilises, config)


def _entente(ref, tirage, lots, sim, quand, numero_facture, dossier, personne, centre,
             professionnel, type_facture, taux, numeros_utilises, config) -> None:
    hospitalisation = type_facture == "HOS"
    if hospitalisation:
        candidats = [c for c in ref.actes if c.startswith("HOS-")]
    elif type_facture == "BIO":
        candidats = [c for c in ref.actes if c.startswith(("BIO-", "IMG-"))]
    else:
        candidats = ACTES_PAR_TYPE_FACTURE[type_facture]
    acte = tirage.choice(candidats)

    numero_entente = f"{tirage.getrandbits(32):08X}"
    while numero_entente in numeros_utilises:
        numero_entente = f"{tirage.getrandbits(32):08X}"
    numeros_utilises.add(numero_entente)

    delai = tirage.expovariate(1 / config.advice_mean_delay_seconds)
    automatique = delai >= config.automatic_approval_limit_seconds
    acceptee = automatique or tirage.random() < config.prior_authorization_acceptance_probability
    statut = "validee_office" if automatique else ("acceptee" if acceptee else "refusee")
    decision = quand + timedelta(seconds=round(delai))
    montant = montant_autour(ref.actes[acte], tirage, hospitalisation=hospitalisation)
    part_cmu = _quantifier(montant * taux / Decimal("100")) if acceptee else Decimal("0")

    index = len(lots.lignes["TB_ENTENTES_PREALABLES"])
    # L'identifiant est posé au moment d'écrire (None ici) : il vient de la séquence.
    lots.lignes["TB_ENTENTES_PREALABLES"].append([
        None, numero_entente, centre, personne, dossier, quand, decision, "CNAM-CI",
        numero_facture, "hospitalisation" if hospitalisation else "acte",
        "standard" if hospitalisation else None, sim, quand, UTILISATEUR])
    lots.liens.append((numero_facture, index))
    lots.lignes["TB_ENTENTES_PREALABLES_ACTES_MEDICAUX"].append([
        index, acte, professionnel, "Prescription issue du parcours simulé.", montant,
        taux if acceptee else Decimal("0"), part_cmu, montant - part_cmu, statut,
        None if acceptee else "Refus simulé du médecin conseil.", sim, quand, UTILISATEUR])
    lots.lignes["TB_ENTENTES_PREALABLES_STATUTS"].append([
        index, statut, decision, None if automatique else tirage.choice(ref.conseillers),
        sim, quand, UTILISATEUR])


async def ecrire(cx: asyncpg.Connection, lots: Lots) -> None:
    """Écrit la journée : factures, ententes (identifiants de la séquence), filles."""

    await cx.copy_records_to_table(
        "TB_FACTURES", records=lots.lignes["TB_FACTURES"], columns=COLONNES["TB_FACTURES"])
    ententes = lots.lignes["TB_ENTENTES_PREALABLES"]
    if ententes:
        premier = await cx.fetchval(f"SELECT nextval('{SEQ_ENTENTE}')")
        await cx.fetchval(f"SELECT setval('{SEQ_ENTENTE}', $1)", premier + len(ententes) - 1)
        identifiants = list(range(premier, premier + len(ententes)))
        for index, ligne in enumerate(ententes):
            ligne[0] = identifiants[index]
        await cx.copy_records_to_table(
            "TB_ENTENTES_PREALABLES", records=[tuple(l) for l in ententes],
            columns=COLONNES["TB_ENTENTES_PREALABLES"])
        # Une facture et son entente se référencent : la facture est écrite la
        # première, sans entente, puis reçoit son identifiant.
        await cx.execute(
            'UPDATE "TB_FACTURES" f SET "ENTENTE_PREALABLE_ID"=v.id '
            'FROM unnest($1::text[], $2::int[]) v(n, id) WHERE f."FACTURE_NUMERO"=v.n',
            [n for n, _ in lots.liens], [identifiants[i] for _, i in lots.liens])
        for table in ("TB_ENTENTES_PREALABLES_ACTES_MEDICAUX", "TB_ENTENTES_PREALABLES_STATUTS"):
            lignes = []
            for ligne in lots.lignes[table]:
                ligne[0] = identifiants[ligne[0]]
                lignes.append(tuple(ligne))
            await cx.copy_records_to_table(table, records=lignes, columns=COLONNES[table])
    for table in ORDRE[1:5]:
        if lots.lignes[table]:
            await cx.copy_records_to_table(
                table, records=lots.lignes[table], columns=COLONNES[table])


async def generer(debut: date, fin: date, par_jour: int, graine: int) -> None:
    cx = await asyncpg.connect(_dsn())
    try:
        ref = Referentiels()
        await ref.charger(cx, debut, fin)
        plan = plan_des_jours(debut, fin, par_jour)
        total = sum(n for _, n in plan)
        sim = uuid.uuid4()
        maintenant = datetime.now(timezone.utc)
        await cx.execute(
            'INSERT INTO "TB_SIMULATIONS" ("SIMULATION_ID","SIMULATION_LIBELLE","SIMULATION_STATUT",'
            '"SIMULATION_PARAMETRES","SIMULATION_DATE_DEBUT","SIMULATION_TYPE",'
            '"UTILISATEUR_ID_CREATION") VALUES ($1,$2,$3,$4,$5,$6,$7)',
            sim, f"Historique {debut} au {fin}", "en_cours",
            json.dumps({"origine": "seed.historique", "debut": str(debut), "fin": str(fin),
                        "par_jour": par_jour, "graine": graine, "factures": total}),
            maintenant, TYPE_SIMULATION, UTILISATEUR)

        # Les numéros de facture sont réservés d'un bloc : la séquence reste la
        # source d'unicité, et un passage du moteur lancé ensuite ne les réutilise pas.
        premier = await cx.fetchval(f"SELECT nextval('{SEQ_FACTURE}')")
        await cx.fetchval(f"SELECT setval('{SEQ_FACTURE}', $1)", premier + total - 1)
        suivant = premier
        tirage = random.Random(graine)
        numeros_utilises = {r[0] for r in await cx.fetch(
            'SELECT "ENTENTE_PREALABLE_NUMERO" FROM "TB_ENTENTES_PREALABLES"')}
        ecrites = 0
        for jour, nombre in plan:
            lots = Lots()
            for _ in range(nombre):
                facture_du_jour(ref, tirage, lots, sim, jour, maintenant.date(),
                                numero("facture", suivant - 1), numeros_utilises)
                suivant += 1
            async with cx.transaction():
                await ecrire(cx, lots)
            ecrites += nombre
            print(f"{jour}  {nombre:>6} factures  ({ecrites}/{total})", flush=True)
        await cx.execute(
            'UPDATE "TB_SIMULATIONS" SET "SIMULATION_STATUT"=$2,"SIMULATION_DATE_FIN"=now(),'
            '"PASSAGES_REUSSIS"=$3 WHERE "SIMULATION_ID"=$1', sim, "terminee", total)
        print(f"Terminé : {total} factures, simulation {sim}.")
    finally:
        await cx.close()


async def purger() -> None:
    cx = await asyncpg.connect(_dsn())
    try:
        ids = [r[0] for r in await cx.fetch(
            'SELECT "SIMULATION_ID" FROM "TB_SIMULATIONS" WHERE "SIMULATION_TYPE"=$1', TYPE_SIMULATION)]
        if not ids:
            print("Rien à purger.")
            return
        async with cx.transaction():
            await cx.execute('UPDATE "TB_FACTURES" SET "ENTENTE_PREALABLE_ID"=NULL '
                             'WHERE "SIMULATION_ID"=ANY($1)', ids)
            for table in ("TB_ENTENTES_PREALABLES_ACTES_MEDICAUX", "TB_ENTENTES_PREALABLES_STATUTS",
                          "TB_ENTENTES_PREALABLES", "TB_FACTURES_PRESCRIPTIONS",
                          "TB_FACTURES_PRESTATIONS", "TB_FACTURES_PATHOLOGIES",
                          "TB_FACTURES_STATUTS", "TB_FACTURES"):
                resultat = await cx.execute(f'DELETE FROM "{table}" WHERE "SIMULATION_ID"=ANY($1)', ids)
                print(f"{table}: {resultat}")
            await cx.execute('DELETE FROM "TB_SIMULATIONS" WHERE "SIMULATION_ID"=ANY($1)', ids)
    finally:
        await cx.close()


def main() -> None:
    parseur = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parseur.add_argument("--debut", type=date.fromisoformat, default=date(2026, 6, 1))
    parseur.add_argument("--fin", type=date.fromisoformat, default=date(2026, 9, 20))
    parseur.add_argument("--par-jour", type=int, default=7000)
    parseur.add_argument("--graine", type=int, default=2026)
    parseur.add_argument("--purger", action="store_true")
    args = parseur.parse_args()
    if args.purger:
        asyncio.run(purger())
    else:
        asyncio.run(generer(args.debut, args.fin, args.par_jour, args.graine))


if __name__ == "__main__":
    main()
