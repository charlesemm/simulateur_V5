"""Expose les commandes de pilotage du moteur de simulation."""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select

from api.schema import (
    MessageResponse, SimulationRunResponse, SimulationSpeedRequest,
    SimulationStartRequest, SimulationStatusResponse,
)
from api.services.simulation_manager import simulation_manager
from app.database import async_session_factory
from auth.dependencies import require_role
from auth.models import User
from simulation.models import SimulationRun

router = APIRouter(prefix="/simulation", tags=["Simulation"])

@router.post("/start", response_model=SimulationStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_simulation(request: SimulationStartRequest,
                           utilisateur: User = Depends(require_role("operateur"))) -> SimulationStatusResponse:
    """Ouvre une exécution et démarre le moteur en arrière-plan."""

    try:
        await simulation_manager.start(
            request.vitesse, request.nombre_passages_simultanes_max,
            utilisateur.utilisateur_uuid,
        )
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return SimulationStatusResponse.model_validate(simulation_manager.status())

@router.post("/stop", response_model=MessageResponse,
             dependencies=[Depends(require_role("operateur"))])
async def stop_simulation() -> MessageResponse:
    """Arrête proprement toutes les tâches du moteur et clôt l'exécution."""

    await simulation_manager.stop()
    return MessageResponse(message="Le simulateur est arrêté.")

@router.post("/speed", response_model=SimulationStatusResponse,
             dependencies=[Depends(require_role("operateur"))])
async def change_speed(request: SimulationSpeedRequest) -> SimulationStatusResponse:
    """Modifie la vitesse sans redémarrage."""

    try:
        simulation_manager.set_speed(request.vitesse)
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return SimulationStatusResponse.model_validate(simulation_manager.status())

@router.get("/status", response_model=SimulationStatusResponse,
            dependencies=[Depends(require_role("observateur"))])
async def get_status() -> SimulationStatusResponse:
    """Retourne l'état courant du moteur."""

    return SimulationStatusResponse.model_validate(simulation_manager.status())

@router.get("/executions", response_model=list[SimulationRunResponse],
            dependencies=[Depends(require_role("observateur"))])
async def list_executions(limite: int = 50) -> list[SimulationRun]:
    """Retourne les exécutions les plus récentes, la dernière en tête."""

    async with async_session_factory() as session:
        return list((await session.execute(
            select(SimulationRun)
            .order_by(SimulationRun.simulation_date_debut.desc())
            .limit(limite)
        )).scalars())
