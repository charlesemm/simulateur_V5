"""Gère les comptes administrateurs hors de l'API, depuis la ligne de commande.

    python -m auth.bootstrap                  crée le premier administrateur
    python -m auth.bootstrap --lister         liste les comptes existants
    python -m auth.bootstrap --reinitialiser  redonne un mot de passe à un compte

Le mot de passe n'est jamais passé en argument : il se saisit à l'invite, sans
écho, pour qu'il ne reste ni dans l'historique du terminal ni dans la liste des
processus.
"""
from __future__ import annotations

import asyncio
import getpass
import sys
import uuid

from sqlalchemy import func, or_, select

from app.database import get_database_session
from auth.models import User
from auth.security import hash_password

LONGUEUR_MINIMALE = 8


async def _create_admin(email: str, nom_utilisateur: str, mot_de_passe: str,
                        nom_complet: str) -> None:
    async for session in get_database_session():
        existing = await session.execute(select(User).where(or_(
            User.email == email, User.nom_utilisateur == nom_utilisateur
        )))
        if existing.scalar_one_or_none() is not None:
            print(f"Un compte existe déjà pour {email} ou {nom_utilisateur}.")
            return

        # Ce compte-ci choisit son mot de passe à la saisie : aucun changement
        # ne lui est imposé, contrairement aux comptes créés depuis l'API.
        user = User(
            utilisateur_uuid=uuid.uuid4(),
            email=email,
            nom_utilisateur=nom_utilisateur,
            mot_de_passe_hash=hash_password(mot_de_passe),
            nom_complet=nom_complet,
            role="administrateur",
            statut_actif=True,
            doit_changer_mot_de_passe=False,
        )
        session.add(user)
        await session.commit()
        print(f"Compte administrateur créé pour {email}.")


async def _lister() -> None:
    """Affiche les comptes et leurs deux identifiants de connexion.

    Aucune empreinte n'est montrée : ce qu'on cherche ici, c'est de savoir
    quoi taper dans le champ « identifiant », rien de plus.
    """

    async for session in get_database_session():
        comptes = list((await session.execute(
            select(User).order_by(User.email)
        )).scalars())

        if not comptes:
            print("Aucun compte. Lancez « python -m auth.bootstrap » pour en créer un.")
            return

        print(f"{len(comptes)} compte(s) — la connexion accepte l'e-mail ou le nom :\n")
        for compte in comptes:
            etat = "actif" if compte.statut_actif else "DÉSACTIVÉ"
            a_changer = " · mot de passe à changer" if compte.doit_changer_mot_de_passe else ""
            print(f"  e-mail : {compte.email}")
            print(f"  nom    : {compte.nom_utilisateur}")
            print(f"  rôle   : {compte.role} · {etat}{a_changer}\n")


async def _reinitialiser(identifiant: str, mot_de_passe: str) -> None:
    """Remplace le mot de passe d'un compte et le réactive au besoin."""

    async for session in get_database_session():
        recherche = identifiant.strip().lower()
        # Même règle qu'à la connexion : e-mail ou nom d'utilisateur, sans
        # égard à la casse. Un décalage entre les deux rendrait cette commande
        # incapable de retrouver un compte qui, lui, sait se connecter.
        compte = (await session.execute(select(User).where(or_(
            func.lower(User.email) == recherche,
            func.lower(User.nom_utilisateur) == recherche,
        )))).scalar_one_or_none()

        if compte is None:
            print(f"Aucun compte ne correspond à « {identifiant} ».")
            print("Lancez « python -m auth.bootstrap --lister » pour voir les identifiants.")
            return

        compte.mot_de_passe_hash = hash_password(mot_de_passe)
        # Le mot de passe vient d'être choisi par la personne elle-même :
        # rien ne justifie de lui en imposer un autre à la connexion.
        compte.doit_changer_mot_de_passe = False
        compte.statut_actif = True
        await session.commit()

        print(f"Mot de passe remplacé pour {compte.email} ({compte.role}).")
        print(f"Connectez-vous avec « {compte.email} » ou « {compte.nom_utilisateur} ».")


def _demander_mot_de_passe() -> str | None:
    """Fait saisir le mot de passe deux fois, sans écho, et le valide."""

    mot_de_passe = getpass.getpass(f"Nouveau mot de passe ({LONGUEUR_MINIMALE} caractères minimum) : ")
    if len(mot_de_passe) < LONGUEUR_MINIMALE:
        print("Mot de passe trop court, opération annulée.")
        return None
    if mot_de_passe != getpass.getpass("Confirmez le mot de passe : "):
        # Sans cette confirmation, une faute de frappe verrouillerait le compte
        # aussi sûrement qu'un mot de passe oublié.
        print("Les deux saisies diffèrent, opération annulée.")
        return None
    return mot_de_passe


def main() -> None:
    option = sys.argv[1] if len(sys.argv) > 1 else ""

    if option == "--lister":
        asyncio.run(_lister())
        return

    if option == "--reinitialiser":
        identifiant = input("E-mail ou nom d'utilisateur du compte : ").strip()
        if not identifiant:
            print("Identifiant vide, opération annulée.")
            return
        mot_de_passe = _demander_mot_de_passe()
        if mot_de_passe:
            asyncio.run(_reinitialiser(identifiant, mot_de_passe))
        return

    email = input("Email de l'administrateur : ").strip()
    nom_utilisateur = input("Nom d'utilisateur : ").strip()
    nom_complet = input("Nom complet : ").strip()
    mot_de_passe = getpass.getpass(f"Mot de passe ({LONGUEUR_MINIMALE} caractères minimum) : ")
    if len(nom_utilisateur) < 3:
        print("Nom d'utilisateur trop court, opération annulée.")
        return
    if len(mot_de_passe) < LONGUEUR_MINIMALE:
        print("Mot de passe trop court, opération annulée.")
        return
    asyncio.run(_create_admin(email, nom_utilisateur, mot_de_passe, nom_complet))


if __name__ == "__main__":
    main()