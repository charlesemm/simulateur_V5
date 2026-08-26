"""Gestion des comptes utilisateurs -- réservé au rôle administrateur."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_database_session
from auth.dependencies import require_role
from auth.models import User
from auth.schemas import (
    VALID_ROLES, PasswordResetResponse, UserCreatedResponse, UserCreateRequest,
    UserOut, UserUpdateRequest,
)
from auth.security import generer_mot_de_passe_temporaire, hash_password

router = APIRouter(
    prefix="/users",
    tags=["utilisateurs"],
    dependencies=[Depends(require_role("administrateur"))],
)


async def _refuser_doublon(
    session: AsyncSession, email: str | None, nom_utilisateur: str | None,
    sauf: uuid.UUID | None = None,
) -> None:
    """Vérifie qu'aucun autre compte ne porte déjà cet e-mail ou ce nom."""

    criteres = []
    if email:
        criteres.append(func.lower(User.email) == email.lower())
    if nom_utilisateur:
        criteres.append(func.lower(User.nom_utilisateur) == nom_utilisateur.lower())
    if not criteres:
        return

    requete = select(User).where(or_(*criteres))
    if sauf is not None:
        requete = requete.where(User.utilisateur_uuid != sauf)

    # `.first()` et non `scalar_one_or_none()` : l'e-mail et le nom demandés
    # peuvent être pris par DEUX comptes différents, auquel cas la requête
    # remonte deux lignes. `scalar_one_or_none()` levait alors
    # MultipleResultsFound — une 500 au lieu du 409 attendu.
    if (await session.execute(requete.limit(1))).scalars().first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte utilise déjà cet e-mail ou ce nom d'utilisateur.",
        )


async def _refuser_de_perdre_le_dernier_admin(
    session: AsyncSession, user: User, *,
    desactive: bool, nouveau_role: str | None,
) -> None:
    """Interdit de retirer le dernier administrateur actif.

    Sans ce garde-fou, un seul clic fermait l'administration à tout le monde :
    plus personne pour rouvrir un compte, et la seule issue restante était
    « python -m auth.bootstrap --reinitialiser » sur la machine elle-même.
    """

    if user.role != "administrateur" or not user.statut_actif:
        return

    perd_le_role = nouveau_role is not None and nouveau_role != "administrateur"
    if not desactive and not perd_le_role:
        return

    restants = await session.scalar(
        select(func.count()).select_from(User).where(
            User.role == "administrateur",
            User.statut_actif.is_(True),
            User.utilisateur_uuid != user.utilisateur_uuid,
        )
    )
    if restants:
        return

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "C'est le dernier administrateur actif : le désactiver ou changer "
            "son rôle fermerait l'administration à tout le monde. Donnez "
            "d'abord ce rôle à un autre compte actif."
        ),
    )


def _valider_role(role: str) -> None:
    """Rejette tout rôle hors de la liste connue."""

    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Rôle invalide. Attendu parmi {VALID_ROLES}.",
        )


@router.get("", response_model=list[UserOut])
async def list_users(session: AsyncSession = Depends(get_database_session)) -> list[UserOut]:
    result = await session.execute(select(User).order_by(User.nom_complet))
    return [UserOut.model_validate(u) for u in result.scalars().all()]


@router.post("", response_model=UserCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest, session: AsyncSession = Depends(get_database_session)
) -> UserCreatedResponse:
    """Crée un compte avec un mot de passe temporaire à usage unique.

    L'administrateur ne choisit pas le mot de passe : il est tiré au hasard,
    renvoyé une seule fois dans cette réponse, et son remplacement est exigé
    à la première connexion.
    """

    _valider_role(payload.role)
    await _refuser_doublon(session, payload.email, payload.nom_utilisateur)

    mot_de_passe = generer_mot_de_passe_temporaire()
    user = User(
        utilisateur_uuid=uuid.uuid4(),
        email=payload.email,
        nom_utilisateur=payload.nom_utilisateur,
        mot_de_passe_hash=hash_password(mot_de_passe),
        nom_complet=payload.nom_complet,
        role=payload.role,
        statut_actif=True,
        doit_changer_mot_de_passe=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserCreatedResponse(
        utilisateur=UserOut.model_validate(user),
        mot_de_passe_temporaire=mot_de_passe,
    )


@router.patch("/{utilisateur_uuid}", response_model=UserOut)
async def update_user(
    utilisateur_uuid: uuid.UUID,
    payload: UserUpdateRequest,
    session: AsyncSession = Depends(get_database_session),
) -> UserOut:
    """Modifie l'identité, le rôle ou l'activation d'un compte.

    Le mot de passe ne se change plus ici : l'utilisateur le choisit lui-même
    via /auth/change-password, ou l'administrateur le réinitialise.
    """

    user = await session.get(User, utilisateur_uuid)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    if payload.role is not None:
        _valider_role(payload.role)

    # Contrôlé avant toute écriture : un refus ne doit rien laisser à moitié
    # modifié derrière lui.
    await _refuser_de_perdre_le_dernier_admin(
        session, user,
        desactive=payload.statut_actif is False,
        nouveau_role=payload.role,
    )

    if payload.role is not None:
        user.role = payload.role
    if payload.nom_utilisateur is not None:
        await _refuser_doublon(session, None, payload.nom_utilisateur, sauf=utilisateur_uuid)
        user.nom_utilisateur = payload.nom_utilisateur
    if payload.nom_complet is not None:
        user.nom_complet = payload.nom_complet
    if payload.statut_actif is not None:
        user.statut_actif = payload.statut_actif

    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.post("/{utilisateur_uuid}/reinitialiser-mot-de-passe",
             response_model=PasswordResetResponse)
async def reset_password(
    utilisateur_uuid: uuid.UUID,
    session: AsyncSession = Depends(get_database_session),
) -> PasswordResetResponse:
    """Remet un mot de passe temporaire et réimpose son changement.

    Le compte retombe dans l'état d'un compte neuf : le jeton qu'il obtiendra
    ne lui ouvrira que le changement de mot de passe.
    """

    user = await session.get(User, utilisateur_uuid)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    mot_de_passe = generer_mot_de_passe_temporaire()
    user.mot_de_passe_hash = hash_password(mot_de_passe)
    user.doit_changer_mot_de_passe = True
    await session.commit()
    return PasswordResetResponse(
        utilisateur_uuid=utilisateur_uuid,
        mot_de_passe_temporaire=mot_de_passe,
    )
