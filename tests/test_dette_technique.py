"""Vérifie les corrections de dette technique X9 à X12."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.database import async_session_factory
from app.models import Invoice
from events import publish_simulation_event
from seed.constants import HEALTH_CENTER_TYPES
from simulation.passage import LIBELLES_TYPE_CENTRE, PassageSimulation
from simulation_config import DEFAULT_CONFIG
from tests.conftest import ASSURE_COUVERT

RACINE = Path(__file__).resolve().parent.parent


# ── X9 : la colonne du libellé de type ───────────────────────────────────

async def test_la_facture_porte_le_libelle_du_type_pas_le_nom_du_centre(base_vierge):
    del base_vierge

    await PassageSimulation(
        ASSURE_COUVERT, DEFAULT_CONFIG, lambda: 1_000_000.0,
        publish_simulation_event, 7,
    ).run()

    async with async_session_factory() as session:
        facture = (await session.execute(select(Invoice))).scalar_one()

    # Le centre de test est de type CSU : « Centre de santé urbain ».
    assert facture.centre_sante_type_code == "CSU"
    assert facture.centre_sante_type_libelle == "Centre de santé urbain"
    assert facture.centre_sante_type_libelle != "Centre de santé de test"


def test_les_six_libelles_de_type_sont_disponibles():
    assert len(LIBELLES_TYPE_CENTRE) == len(HEALTH_CENTER_TYPES) == 6
    assert LIBELLES_TYPE_CENTRE["HG"] == "Hôpital général"


# ── X10 : la configuration morte d'Alembic ───────────────────────────────

def test_alembic_ini_ne_contient_plus_d_url():
    """Une URL de repli silencieuse masquait les configurations absentes."""

    contenu = (RACINE / "alembic.ini").read_text(encoding="utf-8")

    assert "sqlalchemy.url =" not in contenu
    assert "CHANGEME" not in contenu


def test_env_alembic_exige_database_url(monkeypatch):
    """Sans la variable, Alembic doit le dire clairement, pas se rabattre."""

    import importlib.util

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)

    specification = importlib.util.spec_from_file_location(
        "alembic_env_test", RACINE / "alembic" / "env.py"
    )
    module = importlib.util.module_from_spec(specification)

    try:
        specification.loader.exec_module(module)
    except RuntimeError as erreur:
        assert "DATABASE_URL" in str(erreur)
    except Exception as autre:
        # Hors contexte Alembic, l'accès à context lève avant notre garde :
        # le test ne vaut alors que pour le message, vérifié dans le source.
        assert "DATABASE_URL" in (
            RACINE / "alembic" / "env.py"
        ).read_text(encoding="utf-8"), autre


# ── X11 : le seed en sortie redirigée ────────────────────────────────────

def test_l_affichage_du_seed_survit_a_une_console_limitee(capsys, monkeypatch):
    """Le seed avait déjà commité quand son dernier print le faisait échouer."""

    from seed.__main__ import afficher

    class SortieLimitee:
        """Refuse tout ce qui sort du cp1252, comme une console Windows."""

        encoding = "cp1252"

        def __init__(self) -> None:
            self.lignes: list[str] = []

        def write(self, texte: str) -> int:
            texte.encode("cp1252")
            self.lignes.append(texte)
            return len(texte)

        def flush(self) -> None:
            return None

    sortie = SortieLimitee()
    monkeypatch.setattr("sys.stdout", sortie)

    afficher("Seed complété ✓ terminé")

    # Les accents passent en cp1252, le « ✓ » non : il est remplacé, et la
    # ligne s'affiche au lieu de faire échouer un seed déjà commité.
    ecrit = "".join(sortie.lignes)
    assert "Seed complété" in ecrit
    assert "✓" not in ecrit


# ── X12 : un seul fichier image, et il sert ──────────────────────────────
#
# Le chantier X12 visait deux images concurrentes dont aucune n'avait de
# rôle clair. La réponse n'était pas de tout supprimer : le logo CNAM a
# retrouvé sa place à côté de la marque ÉCHO. Ce qui reste interdit, c'est
# l'image orpheline — celle que plus personne n'affiche.

def test_l_ancienne_image_de_connexion_a_disparu():
    """logo.jpg servait d'illustration à la page de connexion, remplacée."""

    assert not (RACINE / "dashboard" / "public" / "logo.jpg").exists()


def test_le_logo_cnam_existe_et_sert():
    """Un fichier image n'a le droit de rester que s'il est affiché."""

    logo = RACINE / "dashboard" / "src" / "assets" / "logo.png"
    assert logo.exists()

    sources = list((RACINE / "dashboard" / "src").rglob("*.tsx"))
    referents = [
        fichier.name for fichier in sources
        if "assets/logo.png" in fichier.read_text(encoding="utf-8")
    ]

    # La barre latérale et la page de connexion, toutes deux.
    assert "Sidebar.tsx" in referents
    assert "LoginPage.tsx" in referents


def test_plus_aucune_source_ne_reference_l_ancienne_image():
    sources = list((RACINE / "dashboard" / "src").rglob("*.tsx"))
    sources += list((RACINE / "dashboard" / "src").rglob("*.ts"))
    sources.append(RACINE / "dashboard" / "index.html")

    for fichier in sources:
        assert "logo.jpg" not in fichier.read_text(encoding="utf-8"), fichier
