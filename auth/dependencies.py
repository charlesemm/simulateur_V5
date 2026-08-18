"""Dépendances FastAPI pour authentifier un utilisateur et vérifier son rôle."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import jwt

from app.database import get_database_session
from auth.models import User
from auth.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Hiérarchie utilisée par require_role : un rôle donne accès à son niveau et
# à tout ce qui est en dessous (administrateur > operateur > observateur).
ROLE_HIERARCHY = {"observateur": 0, "operateur": 1, "administrateur": 2}


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_database_session),
) -> User:
    """Résout l'utilisateur courant à partir du jeton JWT envoyé par le client."""

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton invalide ou expiré, veuillez vous reconnecter.",
        ) from exc

    email = payload.get("sub")
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not user.statut_actif:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable ou compte désactivé.",
        )
    return user


def require_role(minimum_role: str):
    """Fabrique une dépendance qui exige au moins le rôle indiqué."""

    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if ROLE_HIERARCHY[current_user.role] < ROLE_HIERARCHY[minimum_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Votre rôle ne permet pas cette action.",
            )
        return current_user

    return checker