"""Endpoint de connexion : vérifie les identifiants et émet un jeton JWT."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_database_session
from auth.models import User
from auth.schemas import LoginRequest, TokenResponse
from auth.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["authentification"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, session: AsyncSession = Depends(get_database_session)
) -> TokenResponse:
    """Vérifie l'email et le mot de passe, renvoie un jeton JWT si valides."""

    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None or not user.statut_actif or not verify_password(
        payload.mot_de_passe, user.mot_de_passe_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou mot de passe incorrect."
        )

    user.derniere_connexion = datetime.now(timezone.utc)
    await session.commit()

    token = create_access_token(email=user.email, role=user.role)
    return TokenResponse(access_token=token, role=user.role, nom_complet=user.nom_complet)