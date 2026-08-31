"""M1 — Les campagnes de test du module Qualité des données.

Ce que ces tests protègent : une campagne porte toujours une graine et une
référence lisible, et l'accueil apprend du serveur ce qui est ouvert plutôt
que de le décider lui-même.
"""

from __future__ import annotations

import pytest

from campagnes import creer, lire, lister
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

    campagne = await creer(libelle="Recette", code_palier=ECHANTILLON)

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

    premiere = await creer(libelle="Première")
    seconde = await creer(libelle="Seconde")

    assert premiere.campagne_reference != seconde.campagne_reference
    assert premiere.campagne_reference.startswith("C-")
    assert premiere.campagne_reference.endswith("001")
    assert seconde.campagne_reference.endswith("002")


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

    await creer(libelle="Ancienne")
    recente = await creer(libelle="Récente")

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
        json={"libelle": "Campagne d'essai", "palier": COURANT, "graine": 77},
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
        libelle="Avec anomalies",
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


async def test_api_dimensions_annonce_celles_sans_injecteur(client_api, base_vierge):
    """Les trois dimensions encore vides doivent se voir, pas se cacher."""

    reponse = await client_api.get("/campagnes/dimensions")
    assert reponse.status_code == 200

    par_code = {ligne["code"]: ligne for ligne in reponse.json()}
    assert len(par_code) == 8
    assert par_code["UNICITE"]["types_disponibles"] == 0
    assert par_code["COMPLETUDE"]["types_disponibles"] == 0
    assert par_code["TECHNIQUE"]["types_disponibles"] == 0
    assert par_code["EXACTITUDE"]["types_disponibles"] > 0


async def test_api_types_anomalies_portent_leur_dimension(client_api, base_vierge):
    """L'écran groupe par dimension : elle doit venir du serveur."""

    reponse = await client_api.get("/campagnes/anomalies")
    assert reponse.status_code == 200

    types = reponse.json()
    assert len(types) == 13
    assert all(ligne["dimension"] and ligne["dimension_libelle"] for ligne in types)


async def test_api_cree_une_campagne_avec_ses_anomalies(client_api, base_vierge):
    """Le parcours complet de l'assistant, vu de l'API."""

    reponse = await client_api.post(
        "/campagnes",
        json={
            "libelle": "Recette outil qualité",
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
    """

    from campagnes.generateur import produire

    reglages = {"MONTANT_ABERRANT": {"taux": 0.2}, "DATE_ANTIDATEE": {"taux": 0.1}}
    premiere, constats_a, _ = produire(4242, 300, reglages, tmp_path / "a.csv")
    seconde, constats_b, _ = produire(4242, 300, reglages, tmp_path / "b.csv")

    assert premiere == seconde
    assert (tmp_path / "a.csv").read_bytes() == (tmp_path / "b.csv").read_bytes()
    assert [ (c.ligne, c.champ, c.anomalie_code) for c in constats_a ] == [
        (c.ligne, c.champ, c.anomalie_code) for c in constats_b
    ]


async def test_une_autre_graine_donne_un_autre_jeu(tmp_path):
    """Sans quoi la graine ne servirait à rien."""

    from campagnes.generateur import produire

    reglages = {"MONTANT_ABERRANT": {"taux": 0.2}}
    premiere, _, _ = produire(1, 300, reglages, tmp_path / "a.csv")
    seconde, _, _ = produire(2, 300, reglages, tmp_path / "b.csv")

    assert premiere != seconde


async def test_l_ordre_de_saisie_ne_change_pas_le_fichier(tmp_path):
    """Deux opérateurs qui cochent les mêmes cases obtiennent le même jeu.

    Les types sont tirés dans l'ordre du catalogue, jamais dans celui du
    dictionnaire venu de l'écran.
    """

    from campagnes.generateur import produire

    premier = {"MONTANT_ABERRANT": {"taux": 0.2}, "DATE_ANTIDATEE": {"taux": 0.1}}
    second = {"DATE_ANTIDATEE": {"taux": 0.1}, "MONTANT_ABERRANT": {"taux": 0.2}}

    empreinte_a, _, _ = produire(7, 200, premier, tmp_path / "a.csv")
    empreinte_b, _, _ = produire(7, 200, second, tmp_path / "b.csv")

    assert empreinte_a == empreinte_b


async def test_le_fichier_ne_depend_pas_du_jour(tmp_path):
    """Aucune donnée produite ne vient de l'horloge.

    Une date « du jour » ferait changer le fichier d'un jour à l'autre à
    graine constante, et personne ne s'en apercevrait avant la comparaison.
    """

    from campagnes.generateur import DATE_REFERENCE, produire

    _, constats, _ = produire(11, 200, {"DATE_ANTIDATEE": {"taux": 1.0}},
                              tmp_path / "a.csv")
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
                              tmp_path / "a.csv")
    assert 300 <= len(constats) <= 500


async def test_chaque_type_actif_sait_frapper(tmp_path):
    """Les treize types doivent tous produire un constat à 100 %.

    Un type qu'on peut cocher mais qui n'injecte rien afficherait « demandé
    5 %, posé 0 » sans que rien n'explique pourquoi.
    """

    from anomalies.catalogue import CODES
    from campagnes.generateur import produire

    reglages = {code: {"taux": 1.0} for code in CODES}
    _, constats, _ = produire(5, 50, reglages, tmp_path / "a.csv")

    poses = {constat.anomalie_code for constat in constats}
    assert poses == set(CODES), set(CODES) - poses


async def test_generer_une_campagne_de_bout_en_bout(client_api, base_vierge):
    """Le parcours de l'écran : créer, générer, lire le corrigé."""

    import asyncio

    creation = await client_api.post(
        "/campagnes",
        json={
            "libelle": "Génération",
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
