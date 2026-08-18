"""Schémas Pydantic de l'authentification et de la gestion des utilisateurs."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

VALID_ROLES = ("administrateur", "operateur", "observateur")


class LoginRequest(BaseModel):
    email: EmailStr
    mot_de_passe: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    nom_complet: str


class UserCreateRequest(BaseModel):
    email: EmailStr
    mot_de_passe: str = Field(min_length=8, description="8 caractères minimum.")
    nom_complet: str
    role: str


class UserUpdateRequest(BaseModel):
    nom_complet: str | None = None
    role: str | None = None
    statut_actif: bool | None = None
    nouveau_mot_de_passe: str | None = Field(default=None, min_length=8)


class UserOut(BaseModel):
    utilisateur_uuid: str
    email: EmailStr
    nom_complet: str
    role: str
    statut_actif: bool

    model_config = {"from_attributes": True}
