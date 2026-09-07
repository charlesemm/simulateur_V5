"""M6 — Le témoin : ce qu'il sait repérer dans un jeu de campagne.

Ces tests ne touchent à aucune base : le témoin lit du texte, comme le
ferait un vrai outil recevant le fichier exporté par M4.
"""

from __future__ import annotations

from temoin.regles import Constat, analyser
from temoin.service import analyser_fichier

# Une ligne saine, telle qu'un DictReader la rendrait : tout est du texte.
# Construite à la main plutôt qu'avec `ligne_saine` de campagnes/generateur —
# le témoin ne doit dépendre que du format du fichier, jamais du générateur
# qui l'a produit.
LIGNE_SAINE: dict[str, str] = {
    "LIGNE_ID": "1",
    "NUMERO_IMMATRICULATION": "3940000000001",
    "ASSURE_NOM": "Kouassi",
    "ASSURE_PRENOMS": "Awa",
    "ASSURE_DATE_NAISSANCE": "1990-05-12",
    "AGENT_EMAIL": "awa.kouassi.1@cmu.demo.ci",
    "REGIME_CODE": "RAM",
    "DROITS_DATE_DEBUT": "2025-01-01",
    "DROITS_DATE_FIN": "2027-01-01",
    "FACTURE_NUMERO": "100000",
    "FACTURE_DATE_EMISSION": "2026-01-05",
    "FACTURE_DATE_SOINS": "2026-01-03",
    "CENTRE_SANTE_CODE": "12",
    "CENTRE_SANTE_TYPE_CODE": "CHR",
    "PRESTATION_CODE": "CONS-001",
    "PRESTATION_QUANTITE_PRESCRITE": "2",
    "PRESTATION_QUANTITE_SERVIE": "2",
    "PRESTATION_MONTANT_DEPENSE": "5000.00",
    "PRESTATION_TAUX_REMBOURSEMENT": "1.00",
    "PRESTATION_MONTANT_CMU": "5000.00",
    "PRESTATION_MONTANT_ASSURE": "0.00",
    "DONNEE_FICTIVE": "FICTIF-ECHO",
    "CAMPAGNE_REFERENCE": "C-2026-001",
}


def _ligne(**ecarts: str) -> dict[str, str]:
    """Une ligne saine, avec quelques champs modifiés."""

    return {**LIGNE_SAINE, **ecarts}


def test_une_ligne_saine_ne_declenche_rien():
    assert analyser([_ligne()]) == []


def test_un_montant_negatif_est_detecte():
    constats = analyser([_ligne(PRESTATION_MONTANT_DEPENSE="-5000.00")])

    assert constats == [Constat(1, "PRESTATION_MONTANT_DEPENSE", "Montant hors norme")]


def test_un_taux_etranger_au_regime_est_detecte():
    constats = analyser([_ligne(PRESTATION_TAUX_REMBOURSEMENT="0.42")])

    assert len(constats) == 1
    assert constats[0].champ == "PRESTATION_TAUX_REMBOURSEMENT"


def test_une_date_de_naissance_future_est_detectee():
    constats = analyser([_ligne(ASSURE_DATE_NAISSANCE="2099-01-01")])

    assert constats == [Constat(1, "ASSURE_DATE_NAISSANCE", "Date de naissance impossible")]


def test_des_soins_hors_periode_de_droits_sont_detectes():
    constats = analyser([_ligne(FACTURE_DATE_SOINS="2030-01-01")])

    assert constats == [
        Constat(1, "FACTURE_DATE_SOINS", "Date de soins hors de la période de droits")
    ]


def test_une_date_dans_un_format_concurrent_est_detectee():
    constats = analyser([_ligne(FACTURE_DATE_SOINS="03/01/2026")])

    assert constats == [
        Constat(1, "FACTURE_DATE_SOINS", "Date écrite dans un format inattendu")
    ]


def test_une_quantite_servie_excessive_est_detectee():
    constats = analyser([_ligne(PRESTATION_QUANTITE_SERVIE="9")])

    assert constats[0].champ == "PRESTATION_QUANTITE_SERVIE"
    assert "supérieure" in constats[0].type


def test_une_quantite_servie_nulle_est_detectee():
    constats = analyser([_ligne(PRESTATION_QUANTITE_SERVIE="0")])

    assert constats[0].type == "Quantité servie nulle malgré une prescription"


def test_une_immatriculation_mal_formee_est_detectee():
    constats = analyser([_ligne(NUMERO_IMMATRICULATION="12345")])

    assert constats == [
        Constat(1, "NUMERO_IMMATRICULATION", "Numéro d'immatriculation mal formé")
    ]


def test_une_adresse_electronique_mal_formee_est_detectee():
    constats = analyser([_ligne(AGENT_EMAIL="awa.kouassi.1cmu.demo.ci")])

    assert constats == [Constat(1, "AGENT_EMAIL", "Adresse électronique mal formée")]


def test_un_type_de_centre_hors_referentiel_est_detecte():
    constats = analyser([_ligne(CENTRE_SANTE_TYPE_CODE="ZZZ")])

    assert constats == [
        Constat(1, "CENTRE_SANTE_TYPE_CODE", "Type d'établissement hors référentiel")
    ]


def test_une_prestation_hors_referentiel_est_detectee():
    constats = analyser([_ligne(PRESTATION_CODE="XXX-999")])

    assert constats == [
        Constat(1, "PRESTATION_CODE", "Code de prestation hors référentiel")
    ]


def test_un_champ_obligatoire_vide_est_detecte():
    constats = analyser([_ligne(ASSURE_NOM="")])

    assert Constat(1, "ASSURE_NOM", "Champ obligatoire vide") in constats


def test_des_caracteres_casses_sont_detectes():
    constats = analyser([_ligne(ASSURE_NOM="N?Guessan")])

    assert Constat(1, "ASSURE_NOM", "Caractères cassés à la lecture") in constats


def test_une_tentative_d_injection_est_detectee():
    constats = analyser([_ligne(ASSURE_NOM="<script>alert(1)</script>")])

    assert Constat(1, "ASSURE_NOM", "Tentative d'injection détectée") in constats


def test_un_doublon_strict_est_detecte_a_la_deuxieme_occurrence():
    lignes = [_ligne(LIGNE_ID="1"), _ligne(LIGNE_ID="2")]

    constats = analyser(lignes)

    assert constats == [
        Constat(2, "NUMERO_IMMATRICULATION", "Doublon strict d'une fiche déjà vue")
    ]


def test_un_doublon_approchant_est_detecte():
    lignes = [
        _ligne(LIGNE_ID="1"),
        _ligne(LIGNE_ID="2", NUMERO_IMMATRICULATION="3940000000099",
               ASSURE_NOM="KOUASSI"),
    ]

    constats = analyser(lignes)

    assert constats == [
        Constat(2, "ASSURE_NOM", "Doublon approchant d'une fiche déjà vue")
    ]


def test_analyser_fichier_lit_le_separateur_point_virgule():
    entete = ";".join(LIGNE_SAINE.keys())
    ligne = ";".join(LIGNE_SAINE.values())
    contenu = f"{entete}\n{ligne}\n".encode("utf-8")

    outil, constats = analyser_fichier(contenu)

    assert outil
    assert constats == []
