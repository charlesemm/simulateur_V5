"""Connexion d'un compte neuf — vérifié le 2026-08-26.

Le mot de passe temporaire doit ouvrir la session sous les **deux** formes
d'identifiant, et un compte désactivé doit être refusé sans jamais dire
pourquoi au visiteur.
"""


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
