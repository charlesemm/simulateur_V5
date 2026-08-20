"""Crée le premier compte administrateur, de façon interactive.

Usage : python -m auth.bootstrap
"""
from __future__ import annotations

import asyncio
import getpass
import uuid

from sqlalchemy import select

from app.database import get_database_session
from auth.models import User
from auth.security import hash_password


async def _create_admin(email: str, mot_de_passe: str, nom_complet: str) -> None:
    async for session in get_database_session():
        existing = await session.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none() is not None:
            print(f"Un compte existe déjà pour {email}.")
            return

        user = User(
            utilisateur_uuid=uuid.uuid4(),
            email=email,
            mot_de_passe_hash=hash_password(mot_de_passe),
            nom_complet=nom_complet,
            role="administrateur",
            statut_actif=True,
        )
        session.add(user)
        await session.commit()
        print(f"Compte administrateur créé pour {email}.")


def main() -> None:
    email = input("Email de l'administrateur : ").strip()
    nom_complet = input("Nom complet : ").strip()
    mot_de_passe = getpass.getpass("Mot de passe (8 caractères minimum) : ")
    if len(mot_de_passe) < 8:
        print("Mot de passe trop court, opération annulée.")
        return
    asyncio.run(_create_admin(email, mot_de_passe, nom_complet))


if __name__ == "__main__":
    main()