"""Vérifie le hachage, les jetons et les mots de passe temporaires."""
from __future__ import annotations

import jwt
import pytest

from auth.security import (
    ALPHABET_TEMPORAIRE, LONGUEUR_MOT_DE_PASSE_TEMPORAIRE, MotDePasseTropLong,
    create_access_token, decode_access_token, generer_mot_de_passe_temporaire,
    hash_password, jeton_toujours_lie, verify_password,
)

# Caractères que l'on confond en lisant ou en dictant un mot de passe.
AMBIGUS = set("Il1O0")

# Un hachage quelconque : les jetons de ces tests n'ouvrent aucun compte.
HACHAGE = "$2b$12$abcdefghijklmnopqrstuuH4Qb0e6Xz0O7hQ4b1eZr2k8x9m3yQnO"


def test_le_mot_de_passe_est_verifiable():
    empreinte = hash_password("MotDePasseSolide1")
    assert verify_password("MotDePasseSolide1", empreinte)
    assert not verify_password("MotDePasseSolide2", empreinte)


def test_deux_hachages_du_meme_mot_de_passe_different():
    """Le sel doit être unique, sinon deux comptes identiques se repèrent."""

    premiere_empreinte = hash_password("identique")
    seconde_empreinte = hash_password("identique")
    assert premiere_empreinte != seconde_empreinte


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
    jeton = create_access_token(email="agent@cnam.ci", role="operateur",
                                mot_de_passe_hash=HACHAGE)
    charge = decode_access_token(jeton)
    assert charge["sub"] == "agent@cnam.ci"
    assert charge["role"] == "operateur"
    assert "exp" in charge


def test_un_jeton_falsifie_est_rejete():
    jeton = create_access_token(email="agent@cnam.ci", role="observateur",
                                mot_de_passe_hash=HACHAGE)
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


# ── La limite de 72 octets de bcrypt (AUDIT A05) ─────────────────────────
#
# bcrypt 5 lève une ValueError au-delà de 72 octets. Sur /auth/login, cette
# erreur ne se produisait que pour un compte existant : une 500 contre un 401,
# et l'existence du compte se lisait dans le code de réponse.

def test_un_mot_de_passe_trop_long_se_refuse_sans_lever():
    empreinte = hash_password("MotDePasseSolide1")

    assert verify_password("x" * 100, empreinte) is False


def test_la_limite_se_compte_en_octets_et_non_en_caracteres():
    # 37 caractères, mais 74 octets : sous un max_length, au-delà de bcrypt.
    accentue = "é" * 37

    with pytest.raises(MotDePasseTropLong):
        hash_password(accentue)
    assert verify_password(accentue, hash_password("MotDePasseSolide1")) is False


def test_soixante_douze_octets_passent_encore():
    empreinte = hash_password("a" * 72)

    assert verify_password("a" * 72, empreinte)


# ── Le jeton lié au mot de passe (AUDIT A06) ─────────────────────────────

def test_le_jeton_est_lie_au_mot_de_passe_qui_l_a_emis():
    ancien, nouveau = hash_password("AncienMotDePasse1"), hash_password("NouveauMotDePasse1")
    charge = decode_access_token(
        create_access_token(email="agent@cnam.ci", role="operateur", mot_de_passe_hash=ancien)
    )

    assert jeton_toujours_lie(charge, ancien)
    assert not jeton_toujours_lie(charge, nouveau)


def test_un_jeton_sans_empreinte_n_est_lie_a_rien():
    """Les jetons émis avant ce correctif n'ont pas d'empreinte : refusés."""

    assert not jeton_toujours_lie({"sub": "agent@cnam.ci"}, HACHAGE)


def test_l_empreinte_ne_revele_pas_le_hachage():
    charge = decode_access_token(
        create_access_token(email="agent@cnam.ci", role="operateur", mot_de_passe_hash=HACHAGE)
    )

    assert HACHAGE not in str(charge)
