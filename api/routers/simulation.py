"""Expose les commandes de pilotage du moteur de simulation."""

from fastapi import APIRouter, HTTPException, status, Depends
from api.schema import MessageResponse, SimulationSpeedRequest, SimulationStartRequest, SimulationStatusResponse
from api.services.simulation_manager import simulation_manager
from auth.dependencies import require_role

router = APIRouter(prefix="/simulation", tags=["Simulation"])

@router.post("/start", response_model=SimulationStatusResponse, status_code=status.HTTP_202_ACCEPTED,
             dependencies=[Depends(require_role("operateur"))])
async def start_simulation(request: SimulationStartRequest) -> SimulationStatusResponse:
    """Démarre le moteur en arrière-plan."""

    try:
        await simulation_manager.start(request.vitesse, request.nombre_passages_simultanes_max)
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return SimulationStatusResponse.model_validate(simulation_manager.status())

@router.post("/stop", response_model=MessageResponse,
             dependencies=[Depends(require_role("operateur"))])
async def stop_simulation() -> MessageResponse:
    """Arrête proprement toutes les tâches du moteur."""

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

@router.get("/status", response_model=SimulationStatusResponse)
async def get_status() -> SimulationStatusResponse:
    """Retourne l'état courant du moteur."""

    return SimulationStatusResponse.model_validate(simulation_manager.status())