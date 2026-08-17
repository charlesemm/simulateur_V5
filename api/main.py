"""Assemble FastAPI, Socket.IO, CORS et le cycle de vie du simulateur."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio
from api.routers import centres, factures, kpi, simulation
from api.schema import HealthResponse
from api.services.simulation_manager import simulation_manager
from realtime import shutdown_event_pipeline, sio, startup_event_pipeline


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Démarre le consommateur KPI puis arrête toutes les tâches à l'extinction."""

    del application
    await startup_event_pipeline()
    try:
        yield
    finally:
        await simulation_manager.stop()
        await shutdown_event_pipeline()


fastapi_app = FastAPI(
    title="API du simulateur CMU",
    version="1.0.0",
    description="Pilotage, inspection et KPI du parcours assuré CMU.",
    lifespan=lifespan,
)

# Les deux origines Vite usuelles sont ouvertes uniquement pour le développement.
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fastapi_app.include_router(simulation.router)
fastapi_app.include_router(kpi.router)
fastapi_app.include_router(factures.router)
fastapi_app.include_router(centres.router)


@fastapi_app.get("/health", tags=["Technique"], response_model=HealthResponse)
async def health() -> HealthResponse:
    """Confirme que le processus ASGI répond."""

    return HealthResponse(statut="ok")


# Socket.IO traite /socket.io ; toutes les autres routes vont vers FastAPI.
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app, socketio_path="socket.io")