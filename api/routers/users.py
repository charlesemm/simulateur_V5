"""Gestion des comptes utilisateurs -- réservé au rôle administrateur."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_database_session
from auth.dependencies import require_role
from auth.models import User
from auth.schemas import VALID_ROLES, UserCreateRequest, UserOut, UserUpdateRequest
from auth.security import hash_password

router = APIRouter(
    prefix="/users",
    tags=["utilisateurs"],
    dependencies=[Depends(require_role("administrateur"))],
)


@router.get("", response_model=list[UserOut])
async def list_users(session: AsyncSession = Depends(get_database_session)) -> list[UserOut]:
    result = await session.execute(select(User).order_by(User.nom_complet))
    return [UserOut.model_validate(u) for u in result.scalars().all()]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest, session: AsyncSession = Depends(get_database_session)
) -> UserOut:
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"Rôle invalide. Attendu parmi {VALID_ROLES}.")

    existing = await session.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Un compte existe déjà avec cet email.")

    user = User(
        utilisateur_uuid=uuid.uuid4(),
        email=payload.email,
        mot_de_passe_hash=hash_password(payload.mot_de_passe),
        nom_complet=payload.nom_complet,
        role=payload.role,
        statut_actif=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.patch("/{utilisateur_uuid}", response_model=UserOut)
async def update_user(
    utilisateur_uuid: uuid.UUID,
    payload: UserUpdateRequest,
    session: AsyncSession = Depends(get_database_session),
) -> UserOut:
    result = await session.execute(select(User).where(User.utilisateur_uuid == utilisateur_uuid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    if payload.role is not None:
        if payload.role not in VALID_ROLES:
            raise HTTPException(status_code=422, detail=f"Rôle invalide. Attendu parmi {VALID_ROLES}.")
        user.role = payload.role
    if payload.nom_complet is not None:
        user.nom_complet = payload.nom_complet
    if payload.statut_actif is not None:
        user.statut_actif = payload.statut_actif
    if payload.nouveau_mot_de_passe is not None:
        user.mot_de_passe_hash = hash_password(payload.nouveau_mot_de_passe)

    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)