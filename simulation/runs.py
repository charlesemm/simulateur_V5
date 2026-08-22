"""Ouvre et clôture les exécutions du moteur en base."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.database import async_session_factory
from simulation.models import STATUT_EN_COURS, SimulationRun


async def ouvrir_execution(parametres: dict[str, Any],
                           utilisateur_uuid: uuid.UUID | None = None,
                           type_simulation: str | None = None) -> uuid.UUID:
    """Enregistre une exécution en cours et retourne son identifiant."""

    debut = datetime.now(timezone.utc)
    execution = SimulationRun(
        simulation_id=uuid.uuid4(),
        simulation_libelle=f"Exécution du {debut:%d/%m/%Y à %H:%M:%S}",
        simulation_type=type_simulation,
        simulation_statut=STATUT_EN_COURS,
        simulation_parametres=parametres,
        simulation_date_debut=debut,
        utilisateur_uuid=utilisateur_uuid,
        utilisateur_id_creation="simulation",
    )
    async with async_session_factory() as session:
        session.add(execution)
        await session.commit()
    return execution.simulation_id


async def cloturer_execution(simulation_id: uuid.UUID, statut: str,
                             reussis: int, echoues: int) -> None:
    """Fige le statut, l'heure de fin et les compteurs d'une exécution.

    Les compteurs sont écrits ici parce que metrics/registry.py vit en mémoire
    et repart de zéro au redémarrage : sans cette écriture, le bilan d'une
    exécution disparaîtrait avec le processus.
    """

    async with async_session_factory() as session:
        execution = await session.get(SimulationRun, simulation_id)
        if execution is None:
            return
        execution.simulation_statut = statut
        execution.simulation_date_fin = datetime.now(timezone.utc)
        execution.passages_reussis = reussis
        execution.passages_echoues = echoues
        await session.commit()
