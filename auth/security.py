"""Hachage de mot de passe et émission/lecture des jetons JWT."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
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

# Alphabet sans caractères ambigus : ni I/l/1, ni O/0. Un mot de passe
# temporaire se lit à voix haute ou se recopie d'un écran à l'autre.
ALPHABET_TEMPORAIRE = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
LONGUEUR_MOT_DE_PASSE_TEMPORAIRE = 12

# bcrypt ne lit que les 72 premiers octets d'un mot de passe ; depuis sa
# version 5, il lève une ValueError au-delà au lieu de tronquer en silence.
# Tronquer ici serait pire que refuser : deux mots de passe partageant leurs
# 72 premiers octets ouvriraient le même compte.
LONGUEUR_MOT_DE_PASSE_MAXIMALE_OCTETS = 72


class MotDePasseTropLong(ValueError):
    """Le mot de passe dépasse ce que bcrypt sait lire."""


def depasse_la_limite_bcrypt(mot_de_passe: str) -> bool:
    """Dit si un mot de passe dépasse les 72 octets que lit bcrypt.

    La limite se compte en octets UTF-8, pas en caractères : une lettre
    accentuée en vaut deux.
    """

    return len(mot_de_passe.encode("utf-8")) > LONGUEUR_MOT_DE_PASSE_MAXIMALE_OCTETS


def generer_mot_de_passe_temporaire() -> str:
    """Tire un mot de passe temporaire lisible, de force cryptographique.

    Douze caractères pris dans un alphabet de 55 signes valent environ
    69 bits d'entropie : hors de portée d'une attaque par recherche, tout en
    restant dictable au téléphone.
    """

    return "".join(
        secrets.choice(ALPHABET_TEMPORAIRE)
        for _ in range(LONGUEUR_MOT_DE_PASSE_TEMPORAIRE)
    )


def hash_password(mot_de_passe: str) -> str:
    """Hache un mot de passe en clair avec un sel bcrypt unique.

    Lève MotDePasseTropLong au-delà de 72 octets : les appelants valident la
    longueur en amont, ceci est le dernier rempart.
    """

    if depasse_la_limite_bcrypt(mot_de_passe):
        raise MotDePasseTropLong(
            f"Le mot de passe dépasse {LONGUEUR_MOT_DE_PASSE_MAXIMALE_OCTETS} octets."
        )
    return bcrypt.hashpw(mot_de_passe.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(mot_de_passe: str, mot_de_passe_hash: str) -> bool:
    """Vérifie un mot de passe en clair contre son hachage stocké.

    Un mot de passe trop long rend False au lieu de lever : aucun hachage
    stocké ne peut en provenir, et la ValueError de bcrypt devenait une 500
    sur /auth/login — pour les seuls comptes existants, ce qui révélait
    lesquels existent.
    """

    if depasse_la_limite_bcrypt(mot_de_passe):
        return False
    return bcrypt.checkpw(mot_de_passe.encode("utf-8"), mot_de_passe_hash.encode("utf-8"))


def empreinte_de_session(mot_de_passe_hash: str) -> str:
    """Condensé du hachage courant, porté par le jeton sous la clé « mdp ».

    Changer ou réinitialiser le mot de passe change le hachage, donc cette
    empreinte : tous les jetons émis avant cessent d'être acceptés. C'est le
    mécanisme de Django (`get_session_auth_hash`). Le HMAC, signé avec la clé
    des jetons, empêche de tirer du jeton quoi que ce soit sur le hachage.
    """

    return hmac.new(
        SECRET_KEY.encode("utf-8"), mot_de_passe_hash.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def create_access_token(email: str, role: str, mot_de_passe_hash: str) -> str:
    """Émet un jeton JWT signé, valable ACCESS_TOKEN_EXPIRE_HOURS heures.

    Le jeton est lié au mot de passe en vigueur à son émission : voir
    `empreinte_de_session`.
    """

    expiration = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": email,
        "role": role,
        "mdp": empreinte_de_session(mot_de_passe_hash),
        "exp": expiration,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def jeton_toujours_lie(payload: dict, mot_de_passe_hash: str) -> bool:
    """Dit si le jeton a été émis sous le mot de passe actuel du compte."""

    porte = payload.get("mdp")
    if not isinstance(porte, str):
        return False
    return hmac.compare_digest(porte, empreinte_de_session(mot_de_passe_hash))


def decode_access_token(token: str) -> dict:
    """Décode et vérifie un jeton JWT. Lève jwt.PyJWTError si invalide/expiré."""

    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])