"""Crée le premier compte administrateur, de façon interactive.

Usage : python -m auth.bootstrap
"""
from __future__ import annotations

import asyncio
import getpass
import uuid

from sqlalchemy import or_, select

from app.database import get_database_session
from auth.models import User
from auth.security import hash_password


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


def main() -> None:
    email = input("Email de l'administrateur : ").strip()
    nom_utilisateur = input("Nom d'utilisateur : ").strip()
    nom_complet = input("Nom complet : ").strip()
    mot_de_passe = getpass.getpass("Mot de passe (8 caractères minimum) : ")
    if len(nom_utilisateur) < 3:
        print("Nom d'utilisateur trop court, opération annulée.")
        return
    if len(mot_de_passe) < 8:
        print("Mot de passe trop court, opération annulée.")
        return
    asyncio.run(_create_admin(email, nom_utilisateur, mot_de_passe, nom_complet))


if __name__ == "__main__":
    main()