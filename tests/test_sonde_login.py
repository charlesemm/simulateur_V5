"""Connexion d'un compte neuf — vérifié le 2026-08-26.

Le mot de passe temporaire doit ouvrir la session sous les **deux** formes
d'identifiant, et un compte désactivé doit être refusé sans jamais dire
pourquoi au visiteur.
"""

from auth.limitation import TENTATIVES_MAXIMALES, TENTATIVES_MAXIMALES_PAR_SOURCE


async def test_le_mot_de_passe_genere_ouvre_par_email_comme_par_nom(client_api):
    creation = await client_api.post("/users", json={
        "email": "jean.charles@cnam.ci", "nom_utilisateur": "j.charles",
        "nom_complet": "Jean Charles", "role": "operateur",
    })
    assert creation.status_code == 201
    temporaire = creation.json()["mot_de_passe_temporaire"]

    par_email = await client_api.post("/auth/login", json={
        "identifiant": "jean.charles@cnam.ci", "mot_de_passe": temporaire})
    assert par_email.status_code == 200

    par_nom = await client_api.post("/auth/login", json={
        "identifiant": "j.charles", "mot_de_passe": temporaire})
    assert par_nom.status_code == 200

    # La casse ne doit pas compter : personne ne retient comment son compte
    # a été saisi.
    en_majuscules = await client_api.post("/auth/login", json={
        "identifiant": "Jean.Charles@CNAM.CI", "mot_de_passe": temporaire})
    assert en_majuscules.status_code == 200


async def test_un_compte_desactive_est_refuse_sans_se_trahir(client_api):
    """C'est le piège rencontré : mot de passe juste, compte éteint.

    Le refus doit porter exactement le même message qu'un mot de passe faux —
    dire « ce compte est désactivé » à un visiteur anonyme révélerait quels
    comptes existent. C'est le journal du serveur qui porte le motif réel.
    """

    creation = await client_api.post("/users", json={
        "email": "eteint@cnam.ci", "nom_utilisateur": "eteint",
        "nom_complet": "Compte éteint", "role": "operateur",
    })
    temporaire = creation.json()["mot_de_passe_temporaire"]
    uuid_compte = creation.json()["utilisateur"]["utilisateur_uuid"]

    ouvert = await client_api.post("/auth/login", json={
        "identifiant": "eteint", "mot_de_passe": temporaire})
    assert ouvert.status_code == 200

    extinction = await client_api.patch(
        f"/users/{uuid_compte}", json={"statut_actif": False})
    assert extinction.status_code == 200

    refus = await client_api.post("/auth/login", json={
        "identifiant": "eteint", "mot_de_passe": temporaire})
    assert refus.status_code == 401

    faux = await client_api.post("/auth/login", json={
        "identifiant": "eteint", "mot_de_passe": "PasLeBon1234"})
    assert refus.json()["detail"] == faux.json()["detail"]


# ── Le frein des tentatives (AUDIT A03) ──────────────────────────────────

async def _rater(client_api, identifiant: str, fois: int) -> None:
    for _ in range(fois):
        reponse = await client_api.post("/auth/login", json={
            "identifiant": identifiant, "mot_de_passe": "PasLeBon1234"})
        assert reponse.status_code == 401


async def test_les_essais_repetes_sont_freines(client_api):
    await _rater(client_api, "admin", TENTATIVES_MAXIMALES)

    # Même le bon mot de passe attend : sinon le frein ne freinerait rien.
    freine = await client_api.post("/auth/login", json={
        "identifiant": "admin", "mot_de_passe": "MotDePasseAdmin1"})
    assert freine.status_code == 429
    assert int(freine.headers["Retry-After"]) > 0


async def test_un_compte_inconnu_est_freine_comme_un_compte_reel(client_api):
    """Un 429 réservé aux comptes réels dirait lesquels existent."""

    await _rater(client_api, "personne", TENTATIVES_MAXIMALES)

    freine = await client_api.post("/auth/login", json={
        "identifiant": "personne", "mot_de_passe": "PasLeBon1234"})
    assert freine.status_code == 429


async def test_le_frein_vise_l_identifiant_pas_la_casse(client_api):
    await _rater(client_api, "ADMIN", TENTATIVES_MAXIMALES)

    freine = await client_api.post("/auth/login", json={
        "identifiant": "admin", "mot_de_passe": "MotDePasseAdmin1"})
    assert freine.status_code == 429


async def test_une_connexion_reussie_efface_les_echecs(client_api):
    await _rater(client_api, "admin", TENTATIVES_MAXIMALES - 1)
    reussie = await client_api.post("/auth/login", json={
        "identifiant": "admin", "mot_de_passe": "MotDePasseAdmin1"})
    assert reussie.status_code == 200

    await _rater(client_api, "admin", TENTATIVES_MAXIMALES - 1)
    encore = await client_api.post("/auth/login", json={
        "identifiant": "admin", "mot_de_passe": "MotDePasseAdmin1"})
    assert encore.status_code == 200


async def test_une_source_qui_balaie_les_comptes_est_freinee(client_api):
    """Un essai par compte passe sous le frein par identifiant : pas sous
    celui de l'adresse source."""

    for rang in range(TENTATIVES_MAXIMALES_PAR_SOURCE):
        await _rater(client_api, f"compte-{rang}", 1)

    freine = await client_api.post("/auth/login", json={
        "identifiant": "encore-un-autre", "mot_de_passe": "PasLeBon1234"})
    assert freine.status_code == 429


async def test_reussir_sur_son_compte_n_efface_pas_les_essais_de_la_source(client_api):
    for rang in range(TENTATIVES_MAXIMALES_PAR_SOURCE - 1):
        await _rater(client_api, f"compte-{rang}", 1)
    reussie = await client_api.post("/auth/login", json={
        "identifiant": "admin", "mot_de_passe": "MotDePasseAdmin1"})
    assert reussie.status_code == 200

    await _rater(client_api, "dernier-compte", 1)
    freine = await client_api.post("/auth/login", json={
        "identifiant": "admin", "mot_de_passe": "MotDePasseAdmin1"})
    assert freine.status_code == 429


# ── Les mots de passe au-delà de 72 octets (AUDIT A05) ───────────────────

async def test_un_mot_de_passe_trop_long_ne_trahit_pas_le_compte(client_api):
    """Avant : 500 pour un compte existant, 401 pour un inconnu."""

    existant = await client_api.post("/auth/login", json={
        "identifiant": "admin", "mot_de_passe": "x" * 100})
    inconnu = await client_api.post("/auth/login", json={
        "identifiant": "personne", "mot_de_passe": "x" * 100})

    assert existant.status_code == inconnu.status_code == 401
    assert existant.json() == inconnu.json()


async def test_un_nouveau_mot_de_passe_trop_long_est_un_refus_lisible(client_api):
    reponse = await client_api.post("/auth/change-password", json={
        "mot_de_passe_actuel": "MotDePasseAdmin1",
        # 37 caractères, 74 octets : la limite se compte en octets.
        "nouveau_mot_de_passe": "é" * 37,
    })

    assert reponse.status_code == 422
    assert "72 octets" in reponse.text


# ── La révocation des jetons (AUDIT A06) ─────────────────────────────────

async def test_la_reinitialisation_coupe_les_jetons_en_cours(client_api):
    """C'est le geste qu'on fait quand on soupçonne un vol de session."""

    creation = await client_api.post("/users", json={
        "email": "vole@cnam.ci", "nom_utilisateur": "vole",
        "nom_complet": "Session volée", "role": "operateur",
    })
    uuid_compte = creation.json()["utilisateur"]["utilisateur_uuid"]
    temporaire = creation.json()["mot_de_passe_temporaire"]
    connexion = await client_api.post("/auth/login", json={
        "identifiant": "vole", "mot_de_passe": temporaire})
    ancien = {"Authorization": f"Bearer {connexion.json()['access_token']}"}
    change = await client_api.post("/auth/change-password", headers=ancien, json={
        "mot_de_passe_actuel": temporaire, "nouveau_mot_de_passe": "MotDePasseChoisi1"})
    jeton_vole = {"Authorization": f"Bearer {change.json()['access_token']}"}
    assert (await client_api.get("/factures", headers=jeton_vole)).status_code == 200

    reinitialisation = await client_api.post(
        f"/users/{uuid_compte}/reinitialiser-mot-de-passe")
    assert reinitialisation.status_code == 200

    assert (await client_api.get("/factures", headers=jeton_vole)).status_code == 401


# ── Le journal des refus (AUDIT A12) ─────────────────────────────────────

async def test_le_journal_ne_garde_pas_l_adresse_entiere(client_api, caplog):
    with caplog.at_level("WARNING", logger="api.routers.auth"):
        await client_api.post("/auth/login", json={
            "identifiant": "jean.charles@cnam.ci", "mot_de_passe": "PasLeBon1234"})

    messages = " | ".join(enregistrement.getMessage() for enregistrement in caplog.records)
    assert "jean.charles@cnam.ci" not in messages
    assert "jea…@cnam.ci" in messages
    assert "aucun compte ne porte cet identifiant" in messages
