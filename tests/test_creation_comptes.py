"""Création de comptes — les deux pièges rencontrés le 2026-08-25."""

import uuid


async def test_un_email_invalide_est_refuse_proprement(client_api):
    """Le navigateur accepte `admin@cnam` ; Pydantic non.

    La réponse est alors un 422 dont le `detail` est une **liste**, et non
    une chaîne comme pour nos refus métier. L'écran doit savoir lire les deux
    formes : rendre la liste telle quelle vidait la page d'administration.
    """

    reponse = await client_api.post("/users", json={
        "email": "admin@cnam", "nom_utilisateur": "sondeur",
        "nom_complet": "Sonde", "role": "operateur",
    })

    assert reponse.status_code == 422
    detail = reponse.json()["detail"]
    assert isinstance(detail, list)
    assert detail[0]["loc"] == ["body", "email"]
    assert isinstance(detail[0]["msg"], str)


async def test_un_doublon_croise_est_un_conflit_pas_une_panne(client_api):
    """L'e-mail pris par un compte, le nom d'utilisateur par un autre.

    La requête de contrôle remonte alors **deux** lignes.
    `scalar_one_or_none()` levait MultipleResultsFound, soit une 500 : une
    panne serveur là où il ne s'agit que d'un conflit ordinaire.
    """

    premier = await client_api.post("/users", json={
        "email": "a@cnam.ci", "nom_utilisateur": "alpha",
        "nom_complet": "A", "role": "operateur",
    })
    second = await client_api.post("/users", json={
        "email": "b@cnam.ci", "nom_utilisateur": "beta",
        "nom_complet": "B", "role": "operateur",
    })
    assert (premier.status_code, second.status_code) == (201, 201)

    croise = await client_api.post("/users", json={
        "email": "a@cnam.ci", "nom_utilisateur": "beta",
        "nom_complet": "Croisé", "role": "operateur",
    })

    assert croise.status_code == 409
    assert isinstance(croise.json()["detail"], str)


async def test_le_doublon_croise_vaut_aussi_a_la_modification(client_api):
    """Même piège sur PATCH, où le contrôle exclut le compte modifié."""

    await client_api.post("/users", json={
        "email": "c@cnam.ci", "nom_utilisateur": "gamma",
        "nom_complet": "C", "role": "operateur",
    })
    cible = await client_api.post("/users", json={
        "email": "d@cnam.ci", "nom_utilisateur": "delta",
        "nom_complet": "D", "role": "operateur",
    })
    uuid_cible = cible.json()["utilisateur"]["utilisateur_uuid"]

    conflit = await client_api.patch(f"/users/{uuid_cible}", json={
        "nom_utilisateur": "gamma",
    })
    assert conflit.status_code == 409


async def test_le_dernier_administrateur_actif_ne_peut_pas_etre_eteint(
    client_api, administrateur
):
    """Le clic qui a verrouillé l'administration le 2026-08-26.

    Un seul administrateur actif restait ; le désactiver a fermé la porte à
    tout le monde, et il a fallu la ligne de commande pour rouvrir.
    """

    uuid_admin = str(administrateur.utilisateur_uuid)

    extinction = await client_api.patch(
        f"/users/{uuid_admin}", json={"statut_actif": False})
    assert extinction.status_code == 409

    # Le rôle non plus : le rétrograder revient au même.
    retrogradation = await client_api.patch(
        f"/users/{uuid_admin}", json={"role": "observateur"})
    assert retrogradation.status_code == 409

    # Et rien ne doit avoir bougé au passage.
    liste = await client_api.get("/users")
    moi = next(u for u in liste.json() if u["utilisateur_uuid"] == uuid_admin)
    assert moi["statut_actif"] is True
    assert moi["role"] == "administrateur"


async def test_un_administrateur_s_efface_si_un_autre_prend_le_relais(
    client_api, administrateur
):
    """Le garde-fou protège la fonction, pas la personne."""

    releve = await client_api.post("/users", json={
        "email": "releve@cnam.ci", "nom_utilisateur": "releve",
        "nom_complet": "Relève", "role": "administrateur",
    })
    assert releve.status_code == 201

    extinction = await client_api.patch(
        f"/users/{administrateur.utilisateur_uuid}", json={"statut_actif": False})
    assert extinction.status_code == 200


async def test_supprimer_un_compte_le_retire_de_la_liste(client_api):
    """La suppression, contrairement à la désactivation, efface la ligne."""

    cree = await client_api.post("/users", json={
        "email": "e@cnam.ci", "nom_utilisateur": "epsilon",
        "nom_complet": "E", "role": "operateur",
    })
    uuid_cible = cree.json()["utilisateur"]["utilisateur_uuid"]

    suppression = await client_api.delete(f"/users/{uuid_cible}")
    assert suppression.status_code == 204

    liste = await client_api.get("/users")
    assert all(u["utilisateur_uuid"] != uuid_cible for u in liste.json())


async def test_supprimer_un_compte_inconnu_est_un_404(client_api):
    reponse = await client_api.delete(f"/users/{uuid.uuid4()}")
    assert reponse.status_code == 404


async def test_un_administrateur_ne_peut_pas_se_supprimer_lui_meme(
    client_api, administrateur
):
    """Se couper l'accès en plein milieu de l'action serait irréversible."""

    reponse = await client_api.delete(f"/users/{administrateur.utilisateur_uuid}")
    assert reponse.status_code == 409

    liste = await client_api.get("/users")
    assert any(
        u["utilisateur_uuid"] == str(administrateur.utilisateur_uuid)
        for u in liste.json()
    )


async def test_supprimer_un_autre_administrateur_reste_possible_si_on_en_reste_un(
    client_api, administrateur
):
    """Le garde-fou du dernier admin protège la fonction, pas un compte précis.

    `client_api` reste actif tout du long : supprimer un *autre* administrateur
    ne ferme donc jamais la porte, contrairement à se supprimer soi-même
    (couvert par test_un_administrateur_ne_peut_pas_se_supprimer_lui_meme).
    """

    releve = await client_api.post("/users", json={
        "email": "g@cnam.ci", "nom_utilisateur": "golf",
        "nom_complet": "Relève", "role": "administrateur",
    })
    uuid_releve = releve.json()["utilisateur"]["utilisateur_uuid"]

    suppression = await client_api.delete(f"/users/{uuid_releve}")
    assert suppression.status_code == 204

    # Il ne reste plus que `administrateur` : impossible de le supprimer
    # depuis un autre compte administrateur (ici, simulé via le rôle du
    # compte de relève déjà supprimé) -- le garde-fou est déjà couvert par
    # test_un_administrateur_ne_peut_pas_se_supprimer_lui_meme pour le cas
    # où c'est *soi-même* le dernier admin restant.
