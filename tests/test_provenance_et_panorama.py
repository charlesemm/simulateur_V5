"""Vérifie le registre de provenance (X6, X7) et le panorama des tables (X8)."""
from __future__ import annotations

from gouvernance.panorama import panorama, panorama_markdown
from seed.provenance import (
    HYPOTHESES, INVENTE, PROFESSIONS, REFERENTIELS, resume,
)


# ── X6 et X7 : ce qui est inventé, et ce qui en découle ──────────────────

def test_chaque_referentiel_declare_sa_provenance():
    assert REFERENTIELS
    for referentiel in REFERENTIELS:
        assert referentiel.nature in resume()
        assert referentiel.entrees > 0
        assert referentiel.note


def test_les_referentiels_les_plus_sensibles_sont_signales_inventes():
    """Professions et types d'identifiants décident du régime et de l'identité."""

    natures = {referentiel.cle: referentiel.nature for referentiel in REFERENTIELS}

    assert natures["PROFESSIONS"] == INVENTE
    assert natures["TYPES_IDENTIFIANTS"] == INVENTE


def test_la_repartition_des_regimes_suit_vraiment_les_professions():
    """L'hypothèse doit rester juste si quelqu'un modifie la liste."""

    hypothese = next(ligne for ligne in HYPOTHESES if ligne.cle == "REPARTITION_REGIMES")
    part_ram = round(
        100 * sum(1 for entree in PROFESSIONS if entree[2] == "RAM") / len(PROFESSIONS), 1
    )

    assert f"{part_ram} % RAM" in hypothese.valeur


def test_le_taux_de_couverture_se_regle_par_l_environnement(monkeypatch):
    """Le jour où les vrais volumes seront connus, sans toucher au code."""

    from seed import runner

    monkeypatch.setenv("TAUX_COUVERTURE", "0.05")
    assert runner._taux_couverture() == 0.05

    # Une valeur absurde est ramenée dans l'intervalle plutôt que de casser.
    monkeypatch.setenv("TAUX_COUVERTURE", "12")
    assert runner._taux_couverture() == 1.0

    monkeypatch.setenv("TAUX_COUVERTURE", "pas un nombre")
    assert runner._taux_couverture() == 0.60


# ── X8 : panorama des tables ─────────────────────────────────────────────

async def test_le_panorama_decrit_toutes_les_tables(base_vierge):
    del base_vierge
    tables = await panorama()

    noms = {table["table"] for table in tables}
    assert "TB_FACTURES" in noms
    assert "TB_SIMULATIONS" in noms
    assert "TB_REFUS_ACCUEIL" in noms
    # Les tables techniques d'Alembic n'ont rien à faire dans un inventaire.
    assert all(nom.startswith("TB_") for nom in noms)


async def test_le_panorama_donne_les_colonnes_et_la_cle_primaire(base_vierge):
    del base_vierge
    tables = await panorama()

    factures = next(table for table in tables if table["table"] == "TB_FACTURES")

    assert factures["nombre_colonnes"] > 10
    assert factures["cle_primaire"] == ["FACTURE_NUMERO"]
    assert any(colonne["nom"] == "SIMULATION_ID" for colonne in factures["colonnes"])
    assert factures["au_catalogue"] is True
    assert factures["proprietaire"]


async def test_le_panorama_signale_les_tables_sans_proprietaire(base_vierge):
    """C'est le signalement qu'attend la gouvernance : une donnée orpheline."""

    del base_vierge
    tables = await panorama()

    orphelines = [table for table in tables if not table["au_catalogue"]]

    assert orphelines
    assert all(table["proprietaire"] is None for table in orphelines)


async def test_le_panorama_markdown_est_engendre_depuis_la_base(base_vierge):
    del base_vierge
    document = await panorama_markdown()

    assert document.startswith("# Panorama des tables")
    assert "`TB_FACTURES`" in document
    assert "| Colonne | Type | Obligatoire |" in document


async def test_l_api_expose_provenance_et_panorama(client_api):
    provenance = await client_api.get("/gouvernance/provenance")
    assert provenance.status_code == 200
    corps = provenance.json()
    assert corps["referentiels"]
    assert corps["hypotheses"]
    assert corps["resume"]["invente"] >= 2

    vue = await client_api.get("/gouvernance/panorama")
    assert vue.status_code == 200
    assert len(vue.json()) > 10

    document = await client_api.get("/gouvernance/panorama.md")
    assert document.status_code == 200
    assert document.text.startswith("# Panorama des tables")
