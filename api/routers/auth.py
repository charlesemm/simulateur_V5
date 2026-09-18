"""Connexion, émission du jeton JWT et changement de mot de passe."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_database_session
from auth import limitation
from auth.dependencies import get_current_user
from auth.models import User
from auth.schemas import ChangePasswordRequest, LoginRequest, TokenResponse
from auth.security import create_access_token, hash_password, verify_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentification"])


def _identifiant_journalisable(identifiant: str) -> str:
    """Rend de quoi reconnaître un identifiant sans l'écrire en entier.

    Le motif du refus est ce qui rend une connexion ratée diagnosticable ;
    l'adresse complète n'y ajoute qu'une donnée personnelle de plus dans un
    journal sans durée de conservation. « adm…@cnam.ci » suffit à
    rapprocher deux lignes du même compte.
    """

    local, arobase, domaine = identifiant.partition("@")
    return f"{local[:3]}…{arobase}{domaine}"


def _jeton_de(user: User) -> TokenResponse:
    """La réponse de connexion : un jeton neuf et ce que l'écran doit savoir."""

    return TokenResponse(
        access_token=create_access_token(
            email=user.email, role=user.role, mot_de_passe_hash=user.mot_de_passe_hash,
        ),
        role=user.role,
        nom_complet=user.nom_complet,
        nom_utilisateur=user.nom_utilisateur,
        doit_changer_mot_de_passe=user.doit_changer_mot_de_passe,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, request: Request,
    session: AsyncSession = Depends(get_database_session),
) -> TokenResponse:
    """Vérifie l'identifiant et le mot de passe, renvoie un jeton JWT si valides.

    L'identifiant est accepté sous les deux formes : adresse e-mail ou nom
    d'utilisateur. La comparaison ignore la casse, personne ne retient si son
    compte a été créé en majuscules.
    """

    identifiant = payload.identifiant.strip().lower()
    source = request.client.host if request.client else None

    # Vérifié avant toute requête et tout calcul bcrypt : un essai freiné ne
    # doit rien coûter au serveur.
    attente = limitation.secondes_avant_nouvel_essai(identifiant, source)
    if attente:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives de connexion. Réessayez dans quelques minutes.",
            headers={"Retry-After": str(attente)},
        )

    result = await session.execute(
        select(User).where(or_(
            func.lower(User.email) == identifiant,
            func.lower(User.nom_utilisateur) == identifiant,
        ))
    )
    user = result.scalar_one_or_none()

    if user is None or not user.statut_actif or not verify_password(
        payload.mot_de_passe, user.mot_de_passe_hash
    ):
        # La réponse reste volontairement identique dans les trois cas :
        # distinguer « compte inconnu » de « mot de passe faux » révélerait
        # quels comptes existent. Le journal du serveur, lui, le dit — il
        # n'est lisible que par qui administre la machine, et sans cette
        # trace un refus de connexion est indiagnosticable.
        if user is None:
            motif = "aucun compte ne porte cet identifiant"
        elif not user.statut_actif:
            motif = "le compte est désactivé"
        else:
            motif = "le mot de passe ne correspond pas"
        logger.warning(
            "Connexion refusée pour « %s » : %s.",
            _identifiant_journalisable(identifiant), motif,
        )
        limitation.enregistrer_echec(identifiant, source)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiant ou mot de passe incorrect.",
        )

    limitation.oublier(identifiant)
    user.derniere_connexion = datetime.now(timezone.utc)
    await session.commit()

    return _jeton_de(user)


@router.post("/change-password", response_model=TokenResponse)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_database_session),
) -> TokenResponse:
    """Remplace le mot de passe de l'utilisateur connecté et lève l'obligation.

    Cette route dépend de `get_current_user` et non de `require_role` : c'est
    la seule que doit pouvoir appeler un compte encore sous mot de passe
    temporaire, précisément pour en sortir.

    Changer le mot de passe révoque tous les jetons émis avant, y compris
    celui de cette requête : la réponse en porte donc un nouveau, que le
    client doit adopter à la place de l'ancien.
    """

    if not verify_password(payload.mot_de_passe_actuel, current_user.mot_de_passe_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Le mot de passe actuel est incorrect.",
        )
    if payload.nouveau_mot_de_passe == payload.mot_de_passe_actuel:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Le nouveau mot de passe doit être différent de l'ancien.",
        )

    utilisateur = await session.get(User, current_user.utilisateur_uuid)
    utilisateur.mot_de_passe_hash = hash_password(payload.nouveau_mot_de_passe)
    utilisateur.doit_changer_mot_de_passe = False
    await session.commit()

    return _jeton_de(utilisateur)
