"""Vérifie l'API à travers le vrai transport ASGI : auth, factures, parcours."""
from __future__ import annotations

from app.database import async_session_factory
from simulation.events import SimulationEvent
from simulation.passage import PassageSimulation
from simulation_config import DEFAULT_CONFIG
from tests.conftest import ASSURE_COUVERT


async def _produire_une_facture() -> str:
    """Joue un passage complet et retourne le numéro de facture obtenu."""

    from events import publish_simulation_event

    async def journaliser(evenement: SimulationEvent) -> None:
        await publish_simulation_event(evenement)

    await PassageSimulation(
        ASSURE_COUVERT, DEFAULT_CONFIG, lambda: 1_000_000.0, journaliser, 3
    ).run()

    from sqlalchemy import select

    from app.models import Invoice
    async with async_session_factory() as session:
        return (await session.execute(select(Invoice.facture_numero))).scalar_one()


# ── Authentification ────────────────────────────────────────────────────

async def test_la_racine_oriente_au_lieu_de_renvoyer_un_mur(client_api):
    """Taper l'adresse dans un navigateur ne doit jamais donner un 404 nu.

    Deux cas légitimes, selon que le tableau de bord a été compilé ou non :
    en conteneur l'image embarque `dashboard/dist` et la racine sert
    l'interface elle-même ; en développement ce dossier n'existe pas, Vite
    sert l'interface sur son propre port, et la racine explique alors où
    aller. Ce qui est interdit dans les deux cas, c'est le mur.
    """

    from api.main import DASHBOARD_DIST

    reponse = await client_api.get("/")
    assert reponse.status_code == 200

    if DASHBOARD_DIST.is_dir():
        assert reponse.headers["content-type"].startswith("text/html")
        assert "<!doctype html>" in reponse.text.lower()
        return

    corps = reponse.json()
    assert "ÉCHO" in corps["service"]
    assert corps["documentation"] == "/docs"
    assert corps["sante"] == "/health"


async def test_les_routes_de_l_api_gardent_la_main_sur_le_dashboard(client_api):
    """Le rattrapage qui sert l'interface ne doit rien avaler de l'API.

    Il est déclaré en dernier pour cette raison : FastAPI teste les routes
    dans l'ordre d'enregistrement. Une inversion rendrait `index.html` sur
    `/health`, et la panne serait invisible jusqu'au déploiement.
    """

    sante = await client_api.get("/health")
    assert sante.status_code == 200
    assert sante.json() == {"statut": "ok"}

    schema = await client_api.get("/openapi.json")
    assert schema.status_code == 200
    assert schema.json()["openapi"].startswith("3.")


async def test_les_factures_exigent_un_jeton(client_api):
    reponse = await client_api.get("/factures", headers={"Authorization": ""})
    assert reponse.status_code == 401


async def test_connexion_par_email(client_api, administrateur):
    reponse = await client_api.post("/auth/login", json={
        "identifiant": administrateur.email, "mot_de_passe": "MotDePasseAdmin1",
    })
    assert reponse.status_code == 200
    assert reponse.json()["role"] == "administrateur"
    assert reponse.json()["doit_changer_mot_de_passe"] is False


async def test_connexion_par_nom_d_utilisateur(client_api):
    reponse = await client_api.post("/auth/login", json={
        "identifiant": "admin", "mot_de_passe": "MotDePasseAdmin1",
    })
    assert reponse.status_code == 200


async def test_connexion_insensible_a_la_casse(client_api):
    reponse = await client_api.post("/auth/login", json={
        "identifiant": "ADMIN", "mot_de_passe": "MotDePasseAdmin1",
    })
    assert reponse.status_code == 200


async def test_mot_de_passe_faux_et_compte_inconnu_donnent_le_meme_message(client_api):
    """Distinguer les deux cas révélerait quels comptes existent."""

    faux = await client_api.post("/auth/login", json={
        "identifiant": "admin", "mot_de_passe": "incorrect"})
    inconnu = await client_api.post("/auth/login", json={
        "identifiant": "personne", "mot_de_passe": "incorrect"})

    assert faux.status_code == inconnu.status_code == 401
    assert faux.json()["detail"] == inconnu.json()["detail"]


async def test_un_compte_neuf_recoit_un_mot_de_passe_temporaire(client_api):
    reponse = await client_api.post("/users", json={
        "email": "operateur@cnam.ci", "nom_utilisateur": "operateur",
        "nom_complet": "Opérateur de test", "role": "operateur",
    })
    assert reponse.status_code == 201
    corps = reponse.json()
    assert len(corps["mot_de_passe_temporaire"]) == 12
    assert corps["utilisateur"]["doit_changer_mot_de_passe"] is True


async def test_le_mot_de_passe_temporaire_ferme_les_autres_routes(client_api):
    creation = await client_api.post("/users", json={
        "email": "bloque@cnam.ci", "nom_utilisateur": "bloque",
        "nom_complet": "Compte bloqué", "role": "operateur",
    })
    temporaire = creation.json()["mot_de_passe_temporaire"]

    connexion = await client_api.post("/auth/login", json={
        "identifiant": "bloque", "mot_de_passe": temporaire})
    jeton = connexion.json()["access_token"]
    assert connexion.json()["doit_changer_mot_de_passe"] is True

    entetes = {"Authorization": f"Bearer {jeton}"}
    refus = await client_api.get("/factures", headers=entetes)
    assert refus.status_code == 403

    # Seul le changement de mot de passe reste ouvert.
    changement = await client_api.post("/auth/change-password", headers=entetes, json={
        "mot_de_passe_actuel": temporaire, "nouveau_mot_de_passe": "NouveauMotDePasse1",
    })
    assert changement.status_code == 204

    ouvert = await client_api.get("/factures", headers=entetes)
    assert ouvert.status_code == 200


async def test_un_email_deja_pris_est_refuse(client_api, administrateur):
    reponse = await client_api.post("/users", json={
        "email": administrateur.email, "nom_utilisateur": "autre",
        "nom_complet": "Doublon", "role": "operateur",
    })
    assert reponse.status_code == 409


# ── Factures et parcours ────────────────────────────────────────────────

async def test_la_liste_est_vide_au_depart(client_api):
    reponse = await client_api.get("/factures")
    assert reponse.status_code == 200
    assert reponse.json() == {"total": 0, "limite": 50, "decalage": 0, "factures": []}


async def test_la_liste_montre_la_facture_produite(client_api):
    numero = await _produire_une_facture()

    reponse = await client_api.get("/factures")
    corps = reponse.json()
    assert corps["total"] == 1

    ligne = corps["factures"][0]
    assert ligne["facture_numero"] == numero
    assert ligne["regime_code"] == "RGB"
    assert ligne["assure_nom_complet"] == "Kouassi Marie"
    assert float(ligne["montant_rembourse"]) > 0


async def test_le_filtre_par_regime_discrimine(client_api):
    await _produire_une_facture()

    rgb = await client_api.get("/factures", params={"regime_code": "RGB"})
    ram = await client_api.get("/factures", params={"regime_code": "RAM"})
    assert rgb.json()["total"] == 1
    assert ram.json()["total"] == 0


async def test_le_detail_porte_l_assure_le_centre_et_les_totaux(client_api):
    numero = await _produire_une_facture()

    reponse = await client_api.get(f"/factures/{numero}")
    assert reponse.status_code == 200
    detail = reponse.json()

    assert detail["assure"]["numero_secu"] == "3840000000001"
    assert detail["assure"]["regime_taux"] == "70.00"
    assert detail["assure"]["droits_ouverts"] is True
    assert detail["assure"]["profession_code"] == "SALPR"
    assert detail["centre"]["centre_sante_code"] == "CS001"
    assert float(detail["totaux"]["montant_rembourse"]) > 0
    assert detail["prestations"]


async def test_une_facture_inconnue_repond_404(client_api):
    reponse = await client_api.get("/factures/FAC-INEXISTANTE")
    assert reponse.status_code == 404


async def test_le_parcours_restitue_les_etapes_dans_l_ordre(client_api):
    numero = await _produire_une_facture()

    reponse = await client_api.get(f"/factures/{numero}/parcours")
    assert reponse.status_code == 200
    parcours = reponse.json()

    assert parcours["nombre_etapes"] >= 4
    ordres = [etape["ordre"] for etape in parcours["etapes"]]
    assert ordres == sorted(ordres)

    horodatages = [etape["simulated_at"] for etape in parcours["etapes"]]
    assert horodatages == sorted(horodatages)

    assert parcours["etapes"][0]["type_evenement"] == "facture.creee"
    assert parcours["etapes"][0]["libelle"] == "Ouverture de la facture"


async def test_un_passage_inconnu_repond_404(client_api):
    reponse = await client_api.get("/parcours/passage-inexistant")
    assert reponse.status_code == 404
