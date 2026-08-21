"""Schémas Pydantic de l'authentification et de la gestion des utilisateurs."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

VALID_ROLES = ("administrateur", "operateur", "observateur")

# Longueur minimale exigée partout où un mot de passe est saisi ou produit.
LONGUEUR_MOT_DE_PASSE_MINIMALE = 8


class LoginRequest(BaseModel):
    """Un identifiant accepte indifféremment l'e-mail ou le nom d'utilisateur."""

    identifiant: str = Field(min_length=1, description="E-mail ou nom d'utilisateur.")
    mot_de_passe: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    nom_complet: str
    nom_utilisateur: str | None = None
    # Le client doit rediriger vers le changement de mot de passe tant que ce
    # drapeau est vrai : les autres routes lui répondront 403.
    doit_changer_mot_de_passe: bool = False


class ChangePasswordRequest(BaseModel):
    """Remplace le mot de passe courant par un nouveau, choisi par l'utilisateur."""

    mot_de_passe_actuel: str
    nouveau_mot_de_passe: str = Field(min_length=LONGUEUR_MOT_DE_PASSE_MINIMALE)


class UserCreateRequest(BaseModel):
    """L'administrateur ne choisit pas le mot de passe : il est généré."""

    email: EmailStr
    nom_utilisateur: str = Field(min_length=3, max_length=80)
    nom_complet: str
    role: str


class UserUpdateRequest(BaseModel):
    nom_complet: str | None = None
    nom_utilisateur: str | None = Field(default=None, min_length=3, max_length=80)
    role: str | None = None
    statut_actif: bool | None = None


class UserOut(BaseModel):
    # Le modèle porte un uuid natif : le déclarer en str faisait échouer la
    # validation Pydantic et renvoyait une 500 sur toutes les routes /users.
    utilisateur_uuid: UUID
    email: EmailStr
    nom_utilisateur: str | None
    nom_complet: str
    role: str
    statut_actif: bool
    doit_changer_mot_de_passe: bool

    model_config = {"from_attributes": True}


class UserCreatedResponse(BaseModel):
    """Le mot de passe temporaire n'est lisible qu'ici, une seule fois."""

    utilisateur: UserOut
    mot_de_passe_temporaire: str


class PasswordResetResponse(BaseModel):
    """Confirme la réinitialisation et remet le nouveau mot de passe temporaire."""

    utilisateur_uuid: UUID
    mot_de_passe_temporaire: str
