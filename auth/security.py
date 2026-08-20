"""Hachage de mot de passe et émission/lecture des jetons JWT."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from dotenv import load_dotenv

load_dotenv()

# En production, définir JWT_SECRET_KEY comme variable d'environnement --
# ne jamais garder la valeur par défaut ci-dessous hors développement local.
SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "La variable d'environnement JWT_SECRET_KEY est obligatoire. "
        "Génère-la avec : python -c \"import secrets; print(secrets.token_hex(32))\""
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8


def hash_password(mot_de_passe: str) -> str:
    """Hache un mot de passe en clair avec un sel bcrypt unique."""

    return bcrypt.hashpw(mot_de_passe.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(mot_de_passe: str, mot_de_passe_hash: str) -> bool:
    """Vérifie un mot de passe en clair contre son hachage stocké."""

    return bcrypt.checkpw(mot_de_passe.encode("utf-8"), mot_de_passe_hash.encode("utf-8"))


def create_access_token(email: str, role: str) -> str:
    """Émet un jeton JWT signé, valable ACCESS_TOKEN_EXPIRE_HOURS heures."""

    expiration = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": email, "role": role, "exp": expiration}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Décode et vérifie un jeton JWT. Lève jwt.PyJWTError si invalide/expiré."""

    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])