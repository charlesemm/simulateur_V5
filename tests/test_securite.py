"""Vérifie le hachage, les jetons et les mots de passe temporaires."""
from __future__ import annotations

import jwt
import pytest

from auth.security import (
    ALPHABET_TEMPORAIRE, LONGUEUR_MOT_DE_PASSE_TEMPORAIRE,
    create_access_token, decode_access_token, generer_mot_de_passe_temporaire,
    hash_password, verify_password,
)

# Caractères que l'on confond en lisant ou en dictant un mot de passe.
AMBIGUS = set("Il1O0")


def test_le_mot_de_passe_est_verifiable():
    empreinte = hash_password("MotDePasseSolide1")
    assert verify_password("MotDePasseSolide1", empreinte)
    assert not verify_password("MotDePasseSolide2", empreinte)


def test_deux_hachages_du_meme_mot_de_passe_different():
    """Le sel doit être unique, sinon deux comptes identiques se repèrent."""

    assert hash_password("identique") != hash_password("identique")


def test_le_mot_de_passe_temporaire_a_la_bonne_longueur():
    assert len(generer_mot_de_passe_temporaire()) == LONGUEUR_MOT_DE_PASSE_TEMPORAIRE


def test_le_mot_de_passe_temporaire_evite_les_caracteres_ambigus():
    assert not (set(ALPHABET_TEMPORAIRE) & AMBIGUS)
    tirage = "".join(generer_mot_de_passe_temporaire() for _ in range(200))
    assert not (set(tirage) & AMBIGUS)


def test_deux_mots_de_passe_temporaires_different():
    tirages = {generer_mot_de_passe_temporaire() for _ in range(500)}
    assert len(tirages) == 500


def test_le_jeton_transporte_l_identite_et_le_role():
    jeton = create_access_token(email="agent@cnam.ci", role="operateur")
    charge = decode_access_token(jeton)
    assert charge["sub"] == "agent@cnam.ci"
    assert charge["role"] == "operateur"
    assert "exp" in charge


def test_un_jeton_falsifie_est_rejete():
    jeton = create_access_token(email="agent@cnam.ci", role="observateur")
    # On remplace le rôle dans la charge utile sans re-signer.
    falsifie = jeton[:-4] + ("aaaa" if not jeton.endswith("aaaa") else "bbbb")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(falsifie)


def test_un_jeton_signe_par_une_autre_cle_est_rejete():
    # La clé doit faire au moins 32 octets : PyJWT avertit en deçà, et seule sa
    # différence avec la vraie clé compte pour ce test.
    etranger = jwt.encode({"sub": "intrus@ailleurs.ci", "role": "administrateur"},
                          "une-autre-cle-de-signature-suffisamment-longue", algorithm="HS256")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(etranger)
