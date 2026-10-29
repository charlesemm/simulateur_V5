"""Le moteur doit survivre à une vitesse qui dépasse son débit de passages.

À ×86400, une arrivée tombe toutes les ~7 ms : sans contre-pression, les
tâches s'empilaient devant le sémaphore avec chacune un assuré réservé, le
vivier se vidait et le moteur mourait en silence, toujours affiché « en cours ».
"""
from __future__ import annotations

import asyncio

from echo.web.api.services.simulation_manager import simulation_manager


async def test_le_moteur_survit_a_la_vitesse_maximale(client_api):
    demarrage = await client_api.post(
        "/simulation/start",
        json={"type_simulation": "LIBRE", "vitesse": 86400,
              "nombre_passages_simultanes_max": 20},
    )
    assert demarrage.status_code == 202
    try:
        await asyncio.sleep(3)
        moteur = simulation_manager._engine
        assert not simulation_manager._task.done()
        assert moteur._running
        assert len(moteur._tasks) <= 20
        assert moteur.passages_reussis >= 1
    finally:
        await client_api.post("/simulation/stop")
