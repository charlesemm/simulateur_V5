"""Expose les commandes de pilotage du moteur de simulation."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import func, select

from anomalies.models import AnomalyInjection
from api.schema import (
    CommandeRequest, ExecutionDetailResponse, MessageResponse, ProfilResponse,
    SimulationRunResponse, SimulationSpeedRequest, SimulationStartRequest,
    SimulationStatusResponse,
)
from app.models import Invoice, InvoiceProvision, PriorAuthorization
from events.models import EventJournal
from api.services.simulation_manager import simulation_manager
from app.database import async_session_factory
from auth.dependencies import require_role
from auth.models import User
from simulation.aleas import ALEAS, LIBELLES
from simulation.commandes import DECLENCHER_ALEA, ORDRES, Commande
from simulation.models import RefusAccueil, SimulationRun
from simulation.profils import PROFILS
from simulation.purge import compter as compter_purge
from simulation.purge import purger

router = APIRouter(prefix="/simulation", tags=["Simulation"])

@router.post("/start", response_model=SimulationStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_simulation(request: SimulationStartRequest,
                           utilisateur: User = Depends(require_role("operateur"))) -> SimulationStatusResponse:
    """Ouvre une exécution et démarre le moteur en arrière-plan."""

    try:
        await simulation_manager.start(
            request.vitesse, request.nombre_passages_simultanes_max,
            utilisateur.utilisateur_uuid, request.type_simulation,
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

@router.get("/profils", response_model=list[ProfilResponse],
            dependencies=[Depends(require_role("observateur"))])
async def list_profils() -> list[ProfilResponse]:
    """Retourne les quatre types de simulation et leur réglage par défaut."""

    return [ProfilResponse.model_validate(profil) for profil in PROFILS.values()]


@router.get("/aleas", dependencies=[Depends(require_role("observateur"))])
async def list_aleas() -> list[dict]:
    """Retourne les scénarios d'aléa que le moteur sait jouer."""

    return [{"code": code, "libelle": LIBELLES[code]} for code in ALEAS]


@router.post("/commandes", response_model=MessageResponse,
             dependencies=[Depends(require_role("operateur"))])
async def commander(request: CommandeRequest) -> MessageResponse:
    """Adresse un ordre au moteur en cours : armer une anomalie, lancer un aléa.

    L'ordre est déposé, pas exécuté sur-le-champ : le moteur le lira entre deux
    passages. C'est ce qui permet d'entrer en scène pendant une exécution sans
    toucher à son état depuis le fil de la requête.
    """

    if request.ordre not in ORDRES:
        raise HTTPException(
            status_code=422,
            detail=f"Ordre inconnu : {request.ordre}. Attendus : {', '.join(ORDRES)}.",
        )
    if request.ordre == DECLENCHER_ALEA and request.cible not in ALEAS:
        raise HTTPException(status_code=422, detail=f"Aléa inconnu : {request.cible}.")

    try:
        simulation_manager.commander(Commande(request.ordre, request.cible))
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return MessageResponse(message=f"Ordre {request.ordre} déposé pour {request.cible}.")


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


@router.get("/executions/{simulation_id}/refus",
            dependencies=[Depends(require_role("observateur"))])
async def list_refus(simulation_id: UUID, limite: int = 100) -> list[dict]:
    """Retourne les présentations refusées à l'accueil pendant une exécution."""

    async with async_session_factory() as session:
        refus = list((await session.execute(
            select(RefusAccueil)
            .where(RefusAccueil.simulation_id == simulation_id)
            .order_by(RefusAccueil.date_creation.desc())
            .limit(limite)
        )).scalars())

    return [
        {
            "refus_id": str(ligne.refus_id),
            "passage_id": ligne.passage_id,
            "personne_uuid": str(ligne.personne_uuid),
            "refus_date": ligne.refus_date.isoformat(),
            "refus_motif": ligne.refus_motif,
            "regime_code": ligne.regime_code,
        }
        for ligne in refus
    ]


@router.get("/executions/{simulation_id}/purge",
            dependencies=[Depends(require_role("administrateur"))])
async def previsualiser_purge(simulation_id: UUID) -> dict:
    """Compte ce qu'une purge supprimerait, sans rien toucher."""

    return await compter_purge(simulation_id)


@router.delete("/executions/{simulation_id}/donnees",
               dependencies=[Depends(require_role("administrateur"))])
async def purger_execution(simulation_id: UUID) -> dict:
    """Supprime les données d'une exécution ; l'exécution elle-même reste.

    Réservé à l'administrateur, et irréversible : c'est la seule sortie d'un
    simulateur qui conserve par principe toutes les lignes qu'il produit.
    """

    if (simulation_manager.status()["simulation_id"] or None) == simulation_id:
        raise HTTPException(
            status_code=409,
            detail="Cette exécution est en cours : arrêtez-la avant de purger.",
        )
    try:
        return await purger(simulation_id)
    except LookupError as absente:
        raise HTTPException(status_code=404, detail=str(absente)) from absente


@router.get("/executions/{simulation_id}", response_model=ExecutionDetailResponse,
            dependencies=[Depends(require_role("observateur"))])
async def get_execution(simulation_id: UUID) -> dict:
    """Retourne une exécution et le compte de ce qu'elle a produit.

    Les lignes antérieures à l'introduction des exécutions portent un
    SIMULATION_ID nul : elles ne sont comptées dans aucune fiche.
    """

    async with async_session_factory() as session:
        execution = await session.get(SimulationRun, simulation_id)
        if execution is None:
            raise HTTPException(status_code=404, detail="Exécution introuvable.")

        async def compter(modele) -> int:
            return (await session.execute(
                select(func.count()).select_from(modele)
                .where(modele.simulation_id == simulation_id)
            )).scalar_one()

        volumetrie = {
            "factures": await compter(Invoice),
            "prestations": await compter(InvoiceProvision),
            "ententes": await compter(PriorAuthorization),
            "evenements": await compter(EventJournal),
            "anomalies": await compter(AnomalyInjection),
            # Les refus ne produisent aucune facture : sans cette ligne, une
            # exécution qui refuse tout paraîtrait n'avoir rien fait.
            "refus_accueil": await compter(RefusAccueil),
        }

        par_anomalie = {
            code: nombre
            for code, nombre in (await session.execute(
                select(AnomalyInjection.anomalie_code, func.count())
                .where(AnomalyInjection.simulation_id == simulation_id)
                .group_by(AnomalyInjection.anomalie_code)
            )).all()
        }

    return {
        "execution": execution,
        "volumetrie": volumetrie,
        "anomalies_par_type": par_anomalie,
    }
