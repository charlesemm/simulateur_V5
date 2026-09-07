"""M1 — Les campagnes de test du module Qualité des données.

Ce que ces tests protègent : une campagne porte toujours une graine et une
référence lisible, et l'accueil apprend du serveur ce qui est ouvert plutôt
que de le décider lui-même.
"""

from __future__ import annotations

import pytest

from campagnes import creer, lire, lister, previsualiser_reference
from campagnes.models import STATUT_CREEE
from campagnes.paliers import COURANT, ECHANTILLON, PALIERS
from campagnes.service import normaliser_graine, normaliser_volume
from simulation.profils import PARCOURS_CAMPAGNE, PARCOURS_MOTEUR, PROFILS

pytestmark = pytest.mark.asyncio


async def test_creer_une_campagne_tire_une_graine(base_vierge):
    """Sans graine demandée, la campagne en reçoit une, jamais nulle.

    Une graine nulle ou absente rendrait la campagne irrejouable : c'est la
    seule chose qui permette de reproduire le jeu de données à l'identique.
    """

    campagne = await creer(code_palier=ECHANTILLON)

    assert campagne.campagne_graine >= 1
    assert campagne.campagne_statut == STATUT_CREEE
    assert campagne.campagne_volume_cible == PALIERS[ECHANTILLON].volume_propose


async def test_la_graine_demandee_est_conservee(base_vierge):
    """Une graine saisie est celle qui sera rejouée, telle quelle."""

    campagne = await creer(graine=4242)

    relue = await lire(campagne.campagne_id)
    assert relue.campagne_graine == 4242


async def test_les_references_se_suivent(base_vierge):
    """Deux campagnes de la même année portent deux numéros distincts."""

    premiere = await creer()
    seconde = await creer()

    assert premiere.campagne_reference != seconde.campagne_reference
    assert premiere.campagne_reference.startswith("C-")
    assert premiere.campagne_reference.endswith("001")
    assert seconde.campagne_reference.endswith("002")
    assert premiere.campagne_libelle == f"Campagne {premiere.campagne_reference}"
    assert seconde.campagne_libelle == f"Campagne {seconde.campagne_reference}"


async def test_la_reference_previsionnelle_annonce_la_prochaine(base_vierge):
    """Ce que l'écran affiche avant même de créer doit être ce qui suit."""

    annoncee = await previsualiser_reference()
    campagne = await creer()

    assert campagne.campagne_reference == annoncee


async def test_api_expose_la_reference_previsionnelle(client_api, base_vierge):
    """Vue de l'écran : l'endpoint répond avant toute création."""

    reponse = await client_api.get("/campagnes/prochaine-reference")
    assert reponse.status_code == 200, reponse.text
    annoncee = reponse.json()["reference"]

    creation = await client_api.post("/campagnes", json={})
    assert creation.json()["campagne_reference"] == annoncee


async def test_un_palier_inconnu_retombe_sur_l_echantillon(base_vierge):
    """Se tromper de palier ne doit jamais lancer un million de lignes."""

    campagne = await creer(code_palier="N_IMPORTE_QUOI")

    assert campagne.campagne_palier == ECHANTILLON
    assert campagne.campagne_volume_cible == PALIERS[ECHANTILLON].volume_propose


async def test_le_volume_est_borne(base_vierge):
    """Un volume aberrant est ramené dans les bornes, pas refusé."""

    minuscule = await creer(volume_cible=1)
    enorme = await creer(volume_cible=99_000_000)

    assert minuscule.campagne_volume_cible == 100
    assert enorme.campagne_volume_cible == 5_000_000


async def test_lister_rend_la_plus_recente_en_premier(base_vierge):
    """L'historique se lit du plus récent au plus ancien."""

    await creer()
    recente = await creer()

    liste = await lister()
    assert liste[0].campagne_id == recente.campagne_id


async def test_normalisations_hors_base():
    """Les bornes tiennent sans toucher à la base."""

    assert normaliser_graine(None) >= 1
    assert normaliser_graine(0) == 1
    assert normaliser_volume(None, COURANT) == PALIERS[COURANT].volume_propose


async def test_le_serveur_declare_ce_qui_est_ouvert():
    """L'accueil ne décide plus lui-même ce qu'il grise.

    Deux types sont ouverts : LIBRE, qui lance le moteur, et QUALITE, qui
    ouvre une campagne de test sans jamais le traverser.
    """

    ouverts = {code: profil for code, profil in PROFILS.items() if profil.disponible}

    assert set(ouverts) == {"LIBRE", "QUALITE"}
    assert PROFILS["LIBRE"].parcours == PARCOURS_MOTEUR
    assert PROFILS["QUALITE"].parcours == PARCOURS_CAMPAGNE
    assert all(
        profil.parcours is None
        for code, profil in PROFILS.items()
        if not profil.disponible
    )


async def test_api_cree_et_relit_une_campagne(client_api, base_vierge):
    """Le parcours complet vu de l'API, tel que l'écran l'emprunte."""

    creation = await client_api.post(
        "/campagnes",
        json={"palier": COURANT, "graine": 77},
    )
    assert creation.status_code == 201, creation.text
    corps = creation.json()
    assert corps["campagne_graine"] == 77
    assert corps["campagne_volume_cible"] == PALIERS[COURANT].volume_propose

    liste = await client_api.get("/campagnes")
    assert liste.status_code == 200
    assert any(
        ligne["campagne_id"] == corps["campagne_id"] for ligne in liste.json()
    )

    fiche = await client_api.get(f"/campagnes/{corps['campagne_id']}")
    assert fiche.status_code == 200
    assert fiche.json()["campagne_reference"] == corps["campagne_reference"]


async def test_api_campagne_inconnue(client_api, base_vierge):
    """Une campagne absente se solde par un 404, pas par une page vide."""

    reponse = await client_api.get(
        "/campagnes/00000000-0000-4000-8000-000000000000"
    )
    assert reponse.status_code == 404


async def test_api_paliers(client_api, base_vierge):
    """Les quatre paliers du cahier des charges sont servis à l'écran."""

    reponse = await client_api.get("/campagnes/paliers")
    assert reponse.status_code == 200
    codes = [palier["code"] for palier in reponse.json()]
    assert codes == list(PALIERS)


# ── M2 — le choix des anomalies ─────────────────────────────────────────


async def test_les_anomalies_choisies_sont_rangees_avec_la_campagne(base_vierge):
    """Ce que l'écran a coché se retrouve dans les paramètres de la campagne."""

    campagne = await creer(
        anomalies={"MONTANT_ABERRANT": {"taux": 0.15}, "DATE_ANTIDATEE": {"taux": 0.1}},
    )

    reglages = campagne.campagne_parametres["anomalies"]
    assert reglages == {
        "MONTANT_ABERRANT": {"taux": 0.15},
        "DATE_ANTIDATEE": {"taux": 0.1},
    }


async def test_un_code_inconnu_est_ecarte_sans_tout_faire_echouer(base_vierge):
    """Un écran en retard sur le catalogue ne doit pas perdre le reste."""

    campagne = await creer(
        anomalies={"PAS_UN_TYPE": {"taux": 0.5}, "MONTANT_ABERRANT": {"taux": 0.2}},
    )

    assert set(campagne.campagne_parametres["anomalies"]) == {"MONTANT_ABERRANT"}


async def test_un_taux_nul_n_est_pas_retenu(base_vierge):
    """Un type à 0 % n'injecterait rien : le garder promettrait une ligne vide."""

    campagne = await creer(anomalies={"MONTANT_ABERRANT": {"taux": 0}})

    assert campagne.campagne_parametres["anomalies"] == {}


async def test_les_dimensions_couvertes_se_deduisent_du_reglage():
    """Le périmètre du futur score se lit dans ce qui a été coché."""

    from campagnes import dimensions_couvertes

    couvertes = dimensions_couvertes(
        {"MONTANT_ABERRANT": {"taux": 0.1}, "PRESTATION_ORPHELINE": {"taux": 0.1}}
    )
    assert couvertes == ["EXACTITUDE", "REFERENTIELLE"]


async def test_chaque_type_du_catalogue_porte_une_dimension():
    """Aucun type ne doit rester sans dimension : le score l'oublierait."""

    from anomalies.catalogue import CODES, DIMENSIONS, DIMENSION_PAR_CODE

    assert set(DIMENSION_PAR_CODE) == set(CODES)
    assert set(DIMENSION_PAR_CODE.values()) <= set(DIMENSIONS)


async def test_api_les_huit_dimensions_ont_un_injecteur(client_api, base_vierge):
    """Depuis M5, plus aucune dimension n'est vide.

    Avant le chapitre 5, Unicité, Complétude et Conformité technique étaient
    décrites sans que rien ne sache les éprouver. Le compte servi avec chaque
    dimension existe précisément pour que ce trou se voie ; il doit désormais
    être clos partout.
    """

    reponse = await client_api.get("/campagnes/dimensions")
    assert reponse.status_code == 200

    par_code = {ligne["code"]: ligne for ligne in reponse.json()}
    assert len(par_code) == 8
    vides = [code for code, ligne in par_code.items()
             if ligne["types_disponibles"] == 0]
    assert vides == [], f"dimensions sans injecteur : {vides}"
    assert par_code["UNICITE"]["types_disponibles"] == 2
    assert par_code["COMPLETUDE"]["types_disponibles"] == 1
    assert par_code["TECHNIQUE"]["types_disponibles"] == 2


async def test_api_types_anomalies_portent_leur_dimension(client_api, base_vierge):
    """L'écran groupe par dimension : elle doit venir du serveur."""

    from anomalies.catalogue import CODES

    reponse = await client_api.get("/campagnes/anomalies")
    assert reponse.status_code == 200

    types = reponse.json()
    assert len(types) == len(CODES) == 19
    assert all(ligne["dimension"] and ligne["dimension_libelle"] for ligne in types)


async def test_api_cree_une_campagne_avec_ses_anomalies(client_api, base_vierge):
    """Le parcours complet de l'assistant, vu de l'API."""

    reponse = await client_api.post(
        "/campagnes",
        json={
            "palier": "ECHANTILLON",
            "graine": 4242,
            "anomalies": {
                "MONTANT_ABERRANT": {"taux": 0.05},
                "PRESTATION_ORPHELINE": {"taux": 0.01},
            },
        },
    )
    assert reponse.status_code == 201, reponse.text
    assert reponse.json()["campagne_parametres"]["anomalies"] == {
        "MONTANT_ABERRANT": {"taux": 0.05},
        "PRESTATION_ORPHELINE": {"taux": 0.01},
    }


async def test_api_refuse_un_taux_hors_bornes(client_api, base_vierge):
    """Un taux au-delà de 100 % est une erreur de saisie, pas un réglage."""

    reponse = await client_api.post(
        "/campagnes", json={"anomalies": {"MONTANT_ABERRANT": {"taux": 3}}}
    )
    assert reponse.status_code == 422


# ── M3 — le générateur et le corrigé ────────────────────────────────────


async def test_meme_graine_meme_fichier(tmp_path):
    """L'exigence du chapitre 3 : rejouable à l'octet près.

    C'est le test le plus important du module. S'il tombe, plus aucune
    comparaison entre deux campagnes n'a de sens.

    Depuis M4, deux campagnes de même graine portent des **références
    différentes** dans leur marquage : leurs fichiers ne sont donc plus
    identiques octet pour octet, et c'est voulu. Ce qui doit rester identique,
    c'est l'empreinte — calculée sur les seules données — et le corrigé.
    """

    from campagnes.generateur import produire

    reglages = {"MONTANT_ABERRANT": {"taux": 0.2}, "DATE_ANTIDATEE": {"taux": 0.1}}
    premiere, constats_a, _ = produire(4242, 300, reglages, tmp_path / "a.csv", "C-TEST-001")
    seconde, constats_b, _ = produire(4242, 300, reglages, tmp_path / "b.csv", "C-TEST-002")

    assert premiere == seconde
    assert [ (c.ligne, c.champ, c.anomalie_code) for c in constats_a ] == [
        (c.ligne, c.champ, c.anomalie_code) for c in constats_b
    ]

    # Les fichiers ne se distinguent que par la référence portée en 2e colonne.
    lignes_a = (tmp_path / "a.csv").read_text(encoding="utf-8").splitlines()
    lignes_b = (tmp_path / "b.csv").read_text(encoding="utf-8").splitlines()
    sans_marque_a = [";".join(ligne.split(";")[2:]) for ligne in lignes_a]
    sans_marque_b = [";".join(ligne.split(";")[2:]) for ligne in lignes_b]
    assert sans_marque_a == sans_marque_b


async def test_meme_graine_et_meme_reference_donnent_le_meme_fichier(tmp_path):
    """La rejouabilité à l'octet près, marquage compris.

    C'est la relecture stricte du chapitre 3 : rejouer *la même* campagne, et
    non une campagne jumelle, doit redonner exactement le même fichier.
    """

    from campagnes.generateur import produire

    reglages = {"MONTANT_ABERRANT": {"taux": 0.2}}
    produire(99, 200, reglages, tmp_path / "a.csv", "C-TEST-007")
    produire(99, 200, reglages, tmp_path / "b.csv", "C-TEST-007")

    assert (tmp_path / "a.csv").read_bytes() == (tmp_path / "b.csv").read_bytes()


async def test_une_autre_graine_donne_un_autre_jeu(tmp_path):
    """Sans quoi la graine ne servirait à rien."""

    from campagnes.generateur import produire

    reglages = {"MONTANT_ABERRANT": {"taux": 0.2}}
    premiere, _, _ = produire(1, 300, reglages, tmp_path / "a.csv", "C-TEST-001")
    seconde, _, _ = produire(2, 300, reglages, tmp_path / "b.csv", "C-TEST-001")

    assert premiere != seconde


async def test_l_ordre_de_saisie_ne_change_pas_le_fichier(tmp_path):
    """Deux opérateurs qui cochent les mêmes cases obtiennent le même jeu.

    Les types sont tirés dans l'ordre du catalogue, jamais dans celui du
    dictionnaire venu de l'écran.
    """

    from campagnes.generateur import produire

    premier = {"MONTANT_ABERRANT": {"taux": 0.2}, "DATE_ANTIDATEE": {"taux": 0.1}}
    second = {"DATE_ANTIDATEE": {"taux": 0.1}, "MONTANT_ABERRANT": {"taux": 0.2}}

    empreinte_a, _, _ = produire(7, 200, premier, tmp_path / "a.csv", "C-TEST-001")
    empreinte_b, _, _ = produire(7, 200, second, tmp_path / "b.csv", "C-TEST-001")

    assert empreinte_a == empreinte_b


async def test_le_fichier_ne_depend_pas_du_jour(tmp_path):
    """Aucune donnée produite ne vient de l'horloge.

    Une date « du jour » ferait changer le fichier d'un jour à l'autre à
    graine constante, et personne ne s'en apercevrait avant la comparaison.
    """

    from campagnes.generateur import DATE_REFERENCE, produire

    _, constats, _ = produire(11, 200, {"DATE_ANTIDATEE": {"taux": 1.0}},
                              tmp_path / "a.csv", "C-TEST-001")
    contenu = (tmp_path / "a.csv").read_text(encoding="utf-8")

    assert str(DATE_REFERENCE.year) in contenu
    assert constats, "un taux de 100 % doit poser une anomalie par ligne"


async def test_le_taux_demande_est_a_peu_pres_tenu(tmp_path):
    """Un taux de 20 % doit poser environ 20 % d'anomalies.

    La marge est large à dessein : c'est un tirage, pas un quota. Le test
    protège contre une erreur de facteur, pas contre le hasard.
    """

    from campagnes.generateur import produire

    _, constats, _ = produire(3, 2_000, {"MONTANT_ABERRANT": {"taux": 0.2}},
                              tmp_path / "a.csv", "C-TEST-001")
    assert 300 <= len(constats) <= 500


async def test_chaque_type_actif_sait_frapper(tmp_path):
    """Les treize types doivent tous produire un constat à 100 %.

    Un type qu'on peut cocher mais qui n'injecte rien afficherait « demandé
    5 %, posé 0 » sans que rien n'explique pourquoi.
    """

    from anomalies.catalogue import CODES
    from campagnes.generateur import produire

    reglages = {code: {"taux": 1.0} for code in CODES}
    _, constats, _ = produire(5, 50, reglages, tmp_path / "a.csv", "C-TEST-001")

    poses = {constat.anomalie_code for constat in constats}
    assert poses == set(CODES), set(CODES) - poses


async def test_generer_une_campagne_de_bout_en_bout(client_api, base_vierge):
    """Le parcours de l'écran : créer, générer, lire le corrigé."""

    import asyncio

    creation = await client_api.post(
        "/campagnes",
        json={
            "palier": "ECHANTILLON",
            "volume_cible": 200,
            "graine": 4242,
            "anomalies": {"MONTANT_ABERRANT": {"taux": 0.2}},
        },
    )
    campagne_id = creation.json()["campagne_id"]

    lancement = await client_api.post(f"/campagnes/{campagne_id}/generer")
    assert lancement.status_code == 202, lancement.text

    for _ in range(100):
        suivi = (await client_api.get(f"/campagnes/{campagne_id}/progression")).json()
        if suivi["terminee"]:
            break
        await asyncio.sleep(0.05)
    assert suivi["terminee"], suivi
    assert suivi["erreur"] is None

    fiche = (await client_api.get(f"/campagnes/{campagne_id}")).json()
    assert fiche["campagne_statut"] == "generee"
    assert fiche["campagne_lignes_generees"] == 200
    assert len(fiche["campagne_empreinte"]) == 64
    assert fiche["campagne_anomalies_posees"] > 0

    corrige = (await client_api.get(f"/campagnes/{campagne_id}/corrige")).json()
    assert corrige["total"] == fiche["campagne_anomalies_posees"]
    assert set(corrige["par_anomalie"]) == {"MONTANT_ABERRANT"}
    premiere = corrige["lignes"][0]
    assert premiere["corrige_champ"] == "PRESTATION_MONTANT_DEPENSE"
    assert premiere["corrige_valeur_origine"] != premiere["corrige_valeur_injectee"]


async def test_regenerer_ne_duplique_pas_le_corrige(client_api, base_vierge):
    """Régénérer reproduit le même corrigé, il ne l'empile pas."""

    import asyncio

    creation = await client_api.post(
        "/campagnes",
        json={"volume_cible": 150, "graine": 8, 
              "anomalies": {"DATE_ANTIDATEE": {"taux": 0.3}}},
    )
    campagne_id = creation.json()["campagne_id"]

    empreintes = []
    for _ in range(2):
        await client_api.post(f"/campagnes/{campagne_id}/generer")
        for _ in range(100):
            suivi = (
                await client_api.get(f"/campagnes/{campagne_id}/progression")
            ).json()
            if suivi["terminee"]:
                break
            await asyncio.sleep(0.05)
        fiche = (await client_api.get(f"/campagnes/{campagne_id}")).json()
        empreintes.append(fiche["campagne_empreinte"])

    assert empreintes[0] == empreintes[1]
    corrige = (await client_api.get(f"/campagnes/{campagne_id}/corrige")).json()
    assert corrige["total"] == fiche["campagne_anomalies_posees"]


async def test_generer_une_campagne_inconnue(client_api, base_vierge):
    """Une campagne absente ne se génère pas en silence."""

    reponse = await client_api.post(
        "/campagnes/00000000-0000-4000-8000-000000000000/generer"
    )
    assert reponse.status_code == 404


# ── M4 — l'export marqué ────────────────────────────────────────────────


async def test_chaque_ligne_porte_son_marquage(tmp_path):
    """Le chapitre 4 : aucun enregistrement ne sort sans être marqué.

    Le marquage est en tête, et sur toutes les lignes sans exception. Une
    seule ligne nue suffirait à ce qu'un extrait du jeu soit un jour pris
    pour des données réelles.
    """

    from campagnes.export import verifier_marquage
    from campagnes.generateur import (
        COLONNE_CAMPAGNE, COLONNE_MARQUE, COLONNES_FICHIER, MARQUE, produire,
    )

    fichier = tmp_path / "a.csv"
    produire(21, 120, {"MONTANT_ABERRANT": {"taux": 0.3}}, fichier, "C-TEST-042")

    lignes = fichier.read_text(encoding="utf-8").splitlines()
    assert lignes[0].split(";")[:2] == [COLONNE_MARQUE, COLONNE_CAMPAGNE]
    assert len(lignes) == 121
    assert all(ligne.startswith(f"{MARQUE};C-TEST-042;") for ligne in lignes[1:])
    assert len(COLONNES_FICHIER) == len(lignes[0].split(";"))
    assert verifier_marquage(fichier)


async def test_les_quatre_formats_sont_reproductibles(tmp_path):
    """Deux téléchargements du même format donnent deux fichiers identiques.

    C'est l'exigence à laquelle le classeur Excel a failli échouer : une
    archive porte par défaut l'heure de sa fabrication, et openpyxl y ajoutait
    un ordre que rien ne permettait de fixer. D'où le format écrit à la main.
    """

    from campagnes.export import FORMATS, exporter
    from campagnes.generateur import produire

    fichier = tmp_path / "a.csv"
    produire(33, 80, {"DATE_ANTIDATEE": {"taux": 0.2}}, fichier, "C-TEST-050")

    for code in FORMATS:
        un = exporter(fichier, code, "C-TEST-050")
        deux = exporter(fichier, code, "C-TEST-050")
        assert un.contenu == deux.contenu, f"{code} n'est pas reproductible"
        assert un.nom_fichier == f"C-TEST-050_jeu.{FORMATS[code].extension}"
        assert un.contenu, f"{code} a produit un fichier vide"


async def test_le_marquage_survit_aux_conversions(tmp_path):
    """Le marquage n'est pas propre au CSV : il suit dans les trois autres."""

    from campagnes.export import exporter
    from campagnes.generateur import COLONNE_MARQUE, MARQUE, produire

    fichier = tmp_path / "a.csv"
    produire(44, 40, {}, fichier, "C-TEST-051")

    en_json = exporter(fichier, "json", "C-TEST-051").contenu.decode("utf-8")
    assert f'"{COLONNE_MARQUE}": "{MARQUE}"' in en_json
    assert '"CAMPAGNE_REFERENCE": "C-TEST-051"' in en_json

    en_sql = exporter(fichier, "sql", "C-TEST-051").contenu.decode("utf-8")
    assert COLONNE_MARQUE in en_sql
    assert "DONNEES FICTIVES" in en_sql, "le script doit avertir en clair"
    assert f"'{MARQUE}'" in en_sql


async def test_le_classeur_est_relisible(tmp_path):
    """Le XLSX écrit à la main doit s'ouvrir comme n'importe quel autre.

    Écrire le format soi-même permet de le rendre reproductible, mais ne
    dispense pas d'être lisible : openpyxl sert ici de lecteur témoin.
    """

    from openpyxl import load_workbook

    from campagnes.export import exporter
    from campagnes.generateur import COLONNES_FICHIER, MARQUE, produire

    fichier = tmp_path / "a.csv"
    produire(55, 30, {}, fichier, "C-TEST-052")
    classeur_octets = exporter(fichier, "xlsx", "C-TEST-052").contenu

    cible = tmp_path / "jeu.xlsx"
    cible.write_bytes(classeur_octets)
    classeur = load_workbook(cible, read_only=True)
    feuille = classeur[classeur.sheetnames[0]]
    lignes = list(feuille.iter_rows(values_only=True))
    classeur.close()

    assert lignes[0] == COLONNES_FICHIER
    assert len(lignes) == 31
    assert lignes[1][0] == MARQUE
    assert lignes[1][1] == "C-TEST-052"


async def test_le_script_sql_echappe_les_apostrophes(tmp_path):
    """Une apostrophe dans un nom couperait le script en deux."""

    from campagnes.export import _echapper_sql

    assert _echapper_sql("N'Guessan") == "'N''Guessan'"
    assert _echapper_sql("Kouame") == "'Kouame'"


async def test_un_format_inconnu_est_refuse(tmp_path):
    """Un format qu'on ne sait pas produire se dit, il ne se devine pas."""

    from campagnes.export import exporter
    from campagnes.generateur import produire

    fichier = tmp_path / "a.csv"
    produire(66, 20, {}, fichier, "C-TEST-053")

    with pytest.raises(ValueError, match="Format inconnu"):
        exporter(fichier, "pdf", "C-TEST-053")


async def test_un_jeu_absent_ne_s_exporte_pas(tmp_path):
    """Le fichier a pu être effacé du disque : le dire, ne pas rendre du vide."""

    from campagnes.export import exporter

    with pytest.raises(FileNotFoundError):
        exporter(tmp_path / "jamais_produit.csv", "csv", "C-TEST-054")


async def test_api_exporte_une_campagne_generee(client_api, base_vierge):
    """De bout en bout : générer, puis télécharger dans les quatre formats."""

    import asyncio

    from campagnes.export import FORMATS

    creation = await client_api.post(
        "/campagnes",
        json={"palier": "echantillon",
              "volume_cible": 120, "graine": 12,
              "anomalies": {"MONTANT_ABERRANT": {"taux": 0.2}}},
    )
    campagne_id = creation.json()["campagne_id"]

    await client_api.post(f"/campagnes/{campagne_id}/generer")
    for _ in range(100):
        suivi = (await client_api.get(f"/campagnes/{campagne_id}/progression")).json()
        if suivi["terminee"]:
            break
        await asyncio.sleep(0.05)

    for code in FORMATS:
        reponse = await client_api.get(
            f"/campagnes/{campagne_id}/export?format={code}"
        )
        assert reponse.status_code == 200, f"{code} : {reponse.text[:200]}"
        assert "attachment" in reponse.headers["content-disposition"]
        assert f".{FORMATS[code].extension}" in reponse.headers["content-disposition"]
        assert reponse.content


async def test_api_refuse_d_exporter_une_campagne_non_generee(client_api, base_vierge):
    """409 et non 404 : la campagne existe, c'est son jeu qui manque.

    Les deux cas appellent des gestes différents ; leur donner le même code
    les rendrait indiscernables pour qui lit l'API.
    """

    creation = await client_api.post(
        "/campagnes",
        json={"palier": "echantillon", "volume_cible": 100,
              "graine": 13, "anomalies": {}},
    )
    campagne_id = creation.json()["campagne_id"]

    reponse = await client_api.get(f"/campagnes/{campagne_id}/export?format=csv")
    assert reponse.status_code == 409
    assert "générée" in reponse.json()["detail"]


async def test_api_liste_les_formats(client_api, base_vierge):
    """Les formats sont déclarés par le serveur, pas recopiés dans l'écran."""

    reponse = await client_api.get("/campagnes/formats")
    assert reponse.status_code == 200
    codes = {format_export["code"] for format_export in reponse.json()}
    assert codes == {"csv", "xlsx", "json", "sql"}


# ── M5 — les familles qui manquaient au catalogue ───────────────────────


async def test_les_huit_dimensions_sont_couvertes():
    """Aucune dimension du cahier ne reste sans injecteur."""

    from anomalies.catalogue import DIMENSIONS, DIMENSION_PAR_CODE
    from campagnes.generateur import INJECTEURS, INJECTEURS_AVEC_HISTORIQUE

    sachant_frapper = set(INJECTEURS) | set(INJECTEURS_AVEC_HISTORIQUE)
    couvertes = {
        dimension for code, dimension in DIMENSION_PAR_CODE.items()
        if code in sachant_frapper
    }
    assert couvertes == set(DIMENSIONS)


async def test_la_console_n_affiche_que_ce_qu_elle_sait_poser(client_api, base_vierge):
    """Un interrupteur sans effet est pire qu'un interrupteur absent.

    Le moteur temps réel traite un passage à la fois, sans mémoire de ce qui
    précède : il ne peut pas poser de doublon. La console ne doit donc pas les
    proposer, alors que l'écran des campagnes, lui, les affiche.
    """

    from anomalies.catalogue import CODES, CODES_MOTEUR

    console = await client_api.get("/anomalies/catalogue")
    assert console.status_code == 200
    affiches = {ligne["anomalie_code"] for ligne in console.json()}
    assert affiches == set(CODES_MOTEUR)
    assert "DOUBLON_EXACT" not in affiches

    campagne = await client_api.get("/campagnes/anomalies")
    proposes = {ligne["code"] for ligne in campagne.json()}
    assert proposes == set(CODES)
    assert "DOUBLON_EXACT" in proposes


def _relire_csv(fichier):
    """Rend l'en-tête et les lignes du jeu, indexées par numéro de ligne."""

    import csv

    with fichier.open(encoding="utf-8", newline="") as ouvert:
        lignes = list(csv.reader(ouvert, delimiter=";"))
    entete = lignes[0]
    rang_id = entete.index("LIGNE_ID")
    return entete, {int(ligne[rang_id]): ligne for ligne in lignes[1:]}


async def test_un_doublon_exact_recopie_une_identite_deja_ecrite(tmp_path):
    """Le doublon doit exister *ailleurs* dans le fichier, sinon il n'en est pas un."""

    from campagnes.generateur import produire

    fichier = tmp_path / "a.csv"
    _, constats, _ = produire(
        101, 200, {"DOUBLON_EXACT": {"taux": 0.15}}, fichier, "C-TEST-060"
    )
    assert constats, "aucun doublon posé"

    entete, par_numero = _relire_csv(fichier)
    champs = (
        "NUMERO_IMMATRICULATION", "ASSURE_NOM", "ASSURE_PRENOMS",
        "ASSURE_DATE_NAISSANCE",
    )
    rangs = [entete.index(nom) for nom in champs]

    def identite(ligne):
        return tuple(ligne[rang] for rang in rangs)

    for constat in constats:
        moi = identite(par_numero[constat.ligne])
        jumelles = [
            numero for numero, ligne in par_numero.items()
            if numero != constat.ligne and identite(ligne) == moi
        ]
        assert jumelles, f"ligne {constat.ligne} : doublon sans jumelle"


async def test_les_immatriculations_commencent_par_394_et_sont_uniques(tmp_path):
    """Chaque numéro fait treize caractères, commence par 394, et le fichier
    n'en répète jamais deux — le trou que le générateur laissait avant."""

    from campagnes.generateur import produire

    fichier = tmp_path / "b.csv"
    produire(202, 3_000, {}, fichier, "C-TEST-061")

    entete, par_numero = _relire_csv(fichier)
    rang = entete.index("NUMERO_IMMATRICULATION")
    numeros = [ligne[rang] for ligne in par_numero.values()]

    assert len(numeros) == len(set(numeros)), "des numéros se répètent"
    for numero in numeros:
        assert numero.startswith("394"), numero
        assert len(numero) == 13, numero
        assert numero.isdigit(), numero


async def test_agent_email_vient_de_la_liste_des_agents_accueil(tmp_path):
    """L'e-mail n'est plus dérivé de l'assuré : c'est un agent d'accueil,
    tiré d'une petite liste fixe, pas la personne qui vient se faire soigner."""

    from campagnes.generateur import AGENTS_ACCUEIL, produire

    fichier = tmp_path / "d.csv"
    produire(404, 200, {}, fichier, "C-TEST-064")

    entete, par_numero = _relire_csv(fichier)
    rang_email = entete.index("AGENT_EMAIL")
    emails_connus = {agent["email"] for agent in AGENTS_ACCUEIL}

    # Le domaine à lui seul suffit à prouver le découplage : l'ancienne
    # version bâtissait l'e-mail sur « @cnam.ci », depuis le nom et le
    # prénom de l'assuré de la ligne elle-même.
    for ligne in par_numero.values():
        assert ligne[rang_email] in emails_connus
        assert ligne[rang_email].endswith("@cmu.demo.ci")


async def test_facture_numero_et_centre_sont_des_entiers_sans_prefixe(tmp_path):
    """Fini le « F- » et le « CI-CMU- » : ce sont des entiers à l'écran."""

    from campagnes.generateur import FACTURE_NUMERO_BASE, produire

    fichier = tmp_path / "e.csv"
    produire(505, 50, {}, fichier, "C-TEST-065")

    entete, par_numero = _relire_csv(fichier)
    rang_facture = entete.index("FACTURE_NUMERO")
    rang_centre = entete.index("CENTRE_SANTE_CODE")

    numeros_facture = [int(ligne[rang_facture]) for ligne in par_numero.values()]
    assert numeros_facture == list(range(FACTURE_NUMERO_BASE, FACTURE_NUMERO_BASE + 50))
    assert len(str(FACTURE_NUMERO_BASE)) == 6

    for ligne in par_numero.values():
        assert ligne[rang_facture].isdigit()
        assert ligne[rang_centre].isdigit()
        assert 1 <= int(ligne[rang_centre]) <= 250


async def test_les_immatriculations_sont_stables_a_graine_egale(tmp_path):
    """Rejouer une campagne à graine identique doit produire les mêmes
    numéros — sinon deux campagnes de même graine n'ont plus la même
    empreinte, ce que le chapitre 3 du cahier exige."""

    from campagnes.generateur import produire

    premier = tmp_path / "c1.csv"
    second = tmp_path / "c2.csv"
    produire(303, 100, {}, premier, "C-TEST-062")
    produire(303, 100, {}, second, "C-TEST-063")

    _, par_numero_1 = _relire_csv(premier)
    _, par_numero_2 = _relire_csv(second)
    rang = _relire_csv(premier)[0].index("NUMERO_IMMATRICULATION")

    for numero in par_numero_1:
        assert par_numero_1[numero][rang] == par_numero_2[numero][rang]


async def test_un_doublon_approchant_garde_un_numero_distinct(tmp_path):
    """C'est tout le cas difficile : deux numéros pour une seule personne.

    Copier aussi l'immatriculation rendrait la détection triviale, et le test
    sans valeur pour l'outil examiné.
    """

    from campagnes.generateur import produire

    _, constats, _ = produire(
        102, 300, {"DOUBLON_APPROCHANT": {"taux": 0.15}},
        tmp_path / "a.csv", "C-TEST-061",
    )
    assert constats

    for constat in constats:
        avant = constat.valeur_origine.split(" | ")
        apres = constat.valeur_injectee.split(" | ")
        assert avant[0] == apres[0], "l'immatriculation ne doit pas être copiée"
        assert constat.valeur_origine != constat.valeur_injectee


async def test_un_doublon_ne_se_duplique_pas_lui_meme(tmp_path):
    """La première ligne n'a rien à copier : elle ne doit pas être signalée."""

    from campagnes.generateur import produire

    _, constats, _ = produire(
        103, 50, {"DOUBLON_EXACT": {"taux": 1.0}}, tmp_path / "a.csv", "C-TEST-062"
    )
    lignes = {constat.ligne for constat in constats}
    assert 1 not in lignes, "la ligne 1 ne peut pas être un doublon"
    assert len(constats) == 49


async def test_un_champ_obligatoire_vide_l_est_vraiment(tmp_path):
    """Vidé dans le fichier, et pas seulement annoncé dans le corrigé."""

    from campagnes.generateur import produire

    fichier = tmp_path / "a.csv"
    _, constats, _ = produire(
        104, 150, {"CHAMP_OBLIGATOIRE_VIDE": {"taux": 0.2}}, fichier, "C-TEST-063"
    )
    assert constats

    entete, par_numero = _relire_csv(fichier)
    for constat in constats:
        assert constat.valeur_injectee == ""
        assert par_numero[constat.ligne][entete.index(constat.champ)] == ""


async def test_l_encodage_casse_produit_un_texte_different(tmp_path):
    """Mojibake ou point d'interrogation, mais jamais le texte d'origine."""

    from campagnes.generateur import produire

    _, constats, _ = produire(
        105, 200, {"ENCODAGE_CASSE": {"taux": 0.3}}, tmp_path / "a.csv", "C-TEST-064"
    )
    assert constats
    for constat in constats:
        assert constat.valeur_origine != constat.valeur_injectee
        assert constat.champ in ("ASSURE_NOM", "ASSURE_PRENOMS")


async def test_une_date_mal_ecrite_reste_une_date_juste(tmp_path):
    """Le format change, le jour non : c'est une anomalie de forme.

    Une date faussée serait une anomalie d'exactitude, déjà couverte
    ailleurs. Ici, l'outil testé doit repérer un habillage, pas une erreur.
    """

    from datetime import date, datetime

    from campagnes.generateur import FORMATS_DATE_CONCURRENTS, produire

    _, constats, _ = produire(
        106, 200, {"FORMAT_DATE_INCOHERENT": {"taux": 0.3}},
        tmp_path / "a.csv", "C-TEST-065",
    )
    assert constats

    for constat in constats:
        origine = date.fromisoformat(constat.valeur_origine)
        relue = None
        for motif in FORMATS_DATE_CONCURRENTS:
            try:
                relue = datetime.strptime(constat.valeur_injectee, motif).date()
                break
            except ValueError:
                continue
        assert relue is not None, f"illisible : {constat.valeur_injectee}"
        # Le siècle se perd avec « %d.%m.%y » : le jour et le mois suffisent
        # à établir que la date n'a pas été altérée.
        assert (relue.month, relue.day) == (origine.month, origine.day)


async def test_une_charge_hostile_ne_casse_ni_le_csv_ni_le_sql(tmp_path):
    """Le jeu doit rester lisible même quand il transporte une attaque.

    La charge contient des points-virgules et des apostrophes, c'est-à-dire
    exactement les caractères qui découpent le CSV et le script SQL. Si notre
    propre export s'y cassait, l'outil testé ne recevrait jamais l'anomalie.
    """

    import json as json_module

    from campagnes.export import exporter
    from campagnes.generateur import COLONNES_FICHIER, produire

    fichier = tmp_path / "a.csv"
    _, constats, _ = produire(
        107, 200, {"TENTATIVE_INJECTION": {"taux": 0.3}}, fichier, "C-TEST-066"
    )
    assert constats

    entete, par_numero = _relire_csv(fichier)
    assert len(entete) == len(COLONNES_FICHIER)
    assert all(len(ligne) == len(COLONNES_FICHIER) for ligne in par_numero.values())

    en_sql = exporter(fichier, "sql", "C-TEST-066").contenu.decode("utf-8")
    for instruction in en_sql.splitlines():
        if instruction.startswith("INSERT"):
            # Une apostrophe non doublée couperait l'instruction en deux.
            assert instruction.rstrip().endswith(");")

    json_module.loads(exporter(fichier, "json", "C-TEST-066").contenu.decode("utf-8"))


async def test_les_nouveaux_types_restent_reproductibles(tmp_path):
    """Les doublons lisent le passé : la reproductibilité devait être revérifiée."""

    from campagnes.generateur import produire

    reglages = {
        "DOUBLON_EXACT": {"taux": 0.1},
        "DOUBLON_APPROCHANT": {"taux": 0.1},
        "CHAMP_OBLIGATOIRE_VIDE": {"taux": 0.1},
        "ENCODAGE_CASSE": {"taux": 0.1},
        "FORMAT_DATE_INCOHERENT": {"taux": 0.1},
        "TENTATIVE_INJECTION": {"taux": 0.1},
    }
    premiere, constats_a, _ = produire(
        108, 300, reglages, tmp_path / "a.csv", "C-TEST-067"
    )
    seconde, constats_b, _ = produire(
        108, 300, reglages, tmp_path / "b.csv", "C-TEST-067"
    )

    assert premiere == seconde
    assert (tmp_path / "a.csv").read_bytes() == (tmp_path / "b.csv").read_bytes()
    assert len(constats_a) == len(constats_b)


async def test_la_migration_inscrit_les_six_types_au_catalogue(base_vierge):
    """Le catalogue en base doit porter les dix-neuf types, pas seulement le code.

    Sans la migration 0021, la console et le corrigé continueraient de tourner
    sur treize types : le code proposerait des anomalies que la base ignore, et
    le journal d'injection les refuserait par clé étrangère.
    """

    from anomalies.catalogue import CODES
    from anomalies.repository import lire_catalogue

    en_base = {type_anomalie.anomalie_code for type_anomalie in await lire_catalogue()}
    assert set(CODES) <= en_base, f"absents de la base : {set(CODES) - en_base}"
