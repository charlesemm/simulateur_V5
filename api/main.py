"""Assemble FastAPI, Socket.IO, CORS et le cycle de vie du simulateur."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio
import os

import app
from api.routers import centres, factures, kpi, simulation
from api.schema import HealthResponse
from api.routers import anomalies as anomalies_router
from api.routers import metrics as metrics_router
from api.services.simulation_manager import simulation_manager
from realtime import shutdown_event_pipeline, sio, startup_event_pipeline
from api.routers import auth as auth_router
from api.routers import users as users_router
import time
from reports.scheduler import start_scheduler, stop_scheduler
from metrics.registry import registry as metrics_registry
from api.routers import reports as reports_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Démarre le consommateur KPI puis arrête toutes les tâches à l'extinction."""

    del application
    await startup_event_pipeline()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()
        await simulation_manager.stop()
        await shutdown_event_pipeline()

fastapi_app = FastAPI(
    title="API du simulateur CMU",
    version="1.0.0",
    description="Pilotage, inspection et KPI du parcours assuré CMU.",
    lifespan=lifespan,
)

_cors_raw = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173"
)
_cors_origins = [origin.strip() for origin in _cors_raw.split(",") if origin.strip()]

@fastapi_app.middleware("http")
async def mesurer_temps_reponse(request, call_next):
    """Chronomètre chaque requête REST pour le rapport technique quotidien."""

    if request.url.path.startswith("/socket.io"):
        return await call_next(request)
    debut = time.perf_counter()
    reponse = await call_next(request)
    metrics_registry.enregistrer_requete_api(time.perf_counter() - debut)
    return reponse

# Les deux origines Vite usuelles sont ouvertes uniquement pour le développement.
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
fastapi_app.include_router(simulation.router)
fastapi_app.include_router(kpi.router)
fastapi_app.include_router(factures.router)
fastapi_app.include_router(centres.router)
fastapi_app.include_router(auth_router.router)
fastapi_app.include_router(users_router.router)
fastapi_app.include_router(reports_router.router)
fastapi_app.include_router(anomalies_router.router)
fastapi_app.include_router(metrics_router.router)

@fastapi_app.get("/health", tags=["Technique"], response_model=HealthResponse)
async def health() -> HealthResponse:
    """Confirme que le processus ASGI répond."""

    return HealthResponse(statut="ok")

# Socket.IO traite /socket.io ; toutes les autres routes vont vers FastAPI.
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app, socketio_path="socket.io")