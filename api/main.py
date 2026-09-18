"""Assemble FastAPI, Socket.IO, CORS et le cycle de vie du simulateur."""

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import (
    get_redoc_html, get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html,
)
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import socketio

# Le dashboard compilé, s'il a été construit. En conteneur il est copié ici
# par l'étage 1 du Containerfile ; en développement local il n'existe pas et
# c'est Vite qui sert l'interface, sur son propre port.
DASHBOARD_DIST = Path(__file__).resolve().parent.parent / "dashboard" / "dist"

import app
from app import cors
from anomalies.repository import (
    charger_catalogue, charger_configuration, sauvegarder_configuration,
)
from api.routers import centres, factures, kpi, parcours, simulation
from api.schema import HealthResponse
from api.routers import anomalies as anomalies_router
from api.routers import campagnes as campagnes_router
from api.routers import metrics as metrics_router
from api.routers import assures as assures_router
from api.routers import moteurs as moteurs_router
from api.routers import qualite as qualite_router
from api.routers import temoin as temoin_router
from api.services.simulation_manager import simulation_manager
from realtime import shutdown_event_pipeline, sio, startup_event_pipeline
from api.routers import auth as auth_router
from api.routers import users as users_router
from app.database import async_session_factory
from auth.dependencies import get_current_user, oauth2_scheme, require_role
import time
from reports.scheduler import start_scheduler, stop_scheduler
from metrics.registry import registry as metrics_registry
from api.routers import reports as reports_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Démarre le consommateur KPI puis arrête toutes les tâches à l'extinction."""

    del application
    await charger_configuration()
    await charger_catalogue()
    await startup_event_pipeline()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()
        await simulation_manager.stop()
        await shutdown_event_pipeline()
        # Le compteur d'injections monte en mémoire : on le fige avant de quitter.
        # Une base indisponible ne doit pas faire échouer l'arrêt du processus.
        try:
            await sauvegarder_configuration()
        except Exception:
            logging.getLogger(__name__).warning(
                "Sauvegarde de la configuration d'anomalies impossible à l'arrêt.",
                exc_info=True,
            )

fastapi_app = FastAPI(
    title="API du simulateur CMU",
    version="1.0.0",
    description="Pilotage, inspection et KPI du parcours assuré CMU.",
    lifespan=lifespan,
    # Déclarées plus bas, à la main : le schéma doit pouvoir exiger un jeton,
    # ce que les routes intégrées de FastAPI ne savent pas faire.
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

@fastapi_app.middleware("http")
async def mesurer_temps_reponse(request, call_next):
    """Chronomètre chaque requête REST pour le rapport technique quotidien."""

    if request.url.path.startswith("/socket.io"):
        return await call_next(request)
    debut = time.perf_counter()
    reponse = await call_next(request)
    metrics_registry.enregistrer_requete_api(time.perf_counter() - debut)
    return reponse

# Les origines sont définies dans app/cors.py, lu aussi par le temps réel :
# une seule variable d'environnement referme les deux portes à la fois.
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=cors.ORIGINES,
    allow_origin_regex=cors.MOTIF_ORIGINE or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
fastapi_app.include_router(simulation.router)
fastapi_app.include_router(kpi.router)
fastapi_app.include_router(factures.router)
fastapi_app.include_router(parcours.router)
fastapi_app.include_router(centres.router)
fastapi_app.include_router(auth_router.router)
fastapi_app.include_router(users_router.router)
fastapi_app.include_router(reports_router.router)
fastapi_app.include_router(anomalies_router.router)
fastapi_app.include_router(qualite_router.router)
fastapi_app.include_router(campagnes_router.router)
fastapi_app.include_router(temoin_router.router)
fastapi_app.include_router(moteurs_router.router)
fastapi_app.include_router(assures_router.router)
fastapi_app.include_router(metrics_router.router)

@fastapi_app.get("/", tags=["Technique"], response_model=None)
async def racine():
    """Sert le tableau de bord s'il est compilé, sinon dit où le trouver.

    En conteneur, l'image embarque `dashboard/dist` : c'est la même adresse
    qui rend l'interface et l'API, et il n'y a pas de second serveur à tenir.
    En développement, ce dossier n'existe pas — Vite sert l'interface sur son
    propre port — et cette route explique alors qu'on est sur l'API.

    Sans elle, taper l'adresse dans un navigateur renvoyait un « Not Found »
    nu : rien n'indiquait qu'on était au bon endroit mais sur le mauvais port.
    """

    if DASHBOARD_DIST.is_dir():
        return FileResponse(DASHBOARD_DIST / "index.html")

    return {
        "service": "ÉCHO — API du simulateur de données CMU",
        "organisation": "CNAM Côte d'Ivoire",
        "message": (
            "Vous êtes sur l'API, pas sur le tableau de bord. "
            "Celui-ci s'ouvre depuis le serveur du dashboard."
        ),
        "documentation": "/docs",
        "sante": "/health",
        "temps_reel": "/socket.io",
    }


@fastapi_app.get("/health", tags=["Technique"], response_model=HealthResponse)
async def health() -> HealthResponse:
    """Confirme que le processus ASGI répond."""

    return HealthResponse(statut="ok")

# ── Documentation de l'API ─────────────────────────────────────────────
#
# Le schéma OpenAPI décrit toute la surface de l'API, rôles compris. Ce n'est
# pas une donnée, mais c'est la carte : en production, il ne se lit plus sans
# jeton, et les pages /docs et /redoc — qui le chargent sans en présenter —
# disparaissent. L'explorateur d'API du tableau de bord, lui, joint son jeton
# et continue de fonctionner. En développement, rien ne change.
VARIABLE_DOCS_PUBLIQUES = "ECHO_DOCS_PUBLIQUES"


def _docs_publiques() -> bool:
    """Lu à chaque requête : la valeur suit l'environnement, tests compris."""

    return os.getenv(VARIABLE_DOCS_PUBLIQUES, "true").strip().lower() == "true"


async def _acces_au_schema(request: Request) -> None:
    """Laisse passer tout le monde si les docs sont publiques, sinon un compte."""

    if _docs_publiques():
        return
    jeton = await oauth2_scheme(request)
    async with async_session_factory() as session:
        utilisateur = await get_current_user(jeton, session)
    await require_role("observateur")(utilisateur)


@fastapi_app.get("/openapi.json", include_in_schema=False,
                 dependencies=[Depends(_acces_au_schema)])
async def schema_openapi() -> JSONResponse:
    return JSONResponse(fastapi_app.openapi())


@fastapi_app.get("/docs", include_in_schema=False)
async def documentation_swagger() -> HTMLResponse:
    if not _docs_publiques():
        raise HTTPException(status_code=404)
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{fastapi_app.title} - Swagger UI",
        oauth2_redirect_url="/docs/oauth2-redirect",
    )


@fastapi_app.get("/docs/oauth2-redirect", include_in_schema=False)
async def documentation_swagger_redirection() -> HTMLResponse:
    if not _docs_publiques():
        raise HTTPException(status_code=404)
    return get_swagger_ui_oauth2_redirect_html()


@fastapi_app.get("/redoc", include_in_schema=False)
async def documentation_redoc() -> HTMLResponse:
    if not _docs_publiques():
        raise HTTPException(status_code=404)
    return get_redoc_html(openapi_url="/openapi.json", title=f"{fastapi_app.title} - ReDoc")

# ── Tableau de bord compilé ─────────────────────────────────────────────
#
# Déclaré en dernier, après tous les routeurs : FastAPI teste les routes dans
# l'ordre d'enregistrement, donc /simulation, /docs et les autres gardent la
# main. Seul ce qui ne correspond à aucune route de l'API descend jusqu'ici.
if DASHBOARD_DIST.is_dir():
    fastapi_app.mount(
        "/assets",
        StaticFiles(directory=DASHBOARD_DIST / "assets"),
        name="assets",
    )

    @fastapi_app.get("/{chemin:path}", include_in_schema=False)
    async def servir_dashboard(chemin: str) -> FileResponse:
        """Rend le fichier demandé, ou l'index pour toute route de l'interface.

        Le tableau de bord est une application d'une seule page : ses adresses
        internes n'existent pas côté serveur et doivent toutes retomber sur
        `index.html`, faute de quoi un rafraîchissement du navigateur donnerait
        un 404 sur un écran qui existe pourtant.
        """

        demande = (DASHBOARD_DIST / chemin).resolve()

        # Un chemin remontant (« ../../etc/passwd ») sortirait du dossier
        # servi : on vérifie l'appartenance après résolution, jamais avant.
        if not demande.is_relative_to(DASHBOARD_DIST):
            raise HTTPException(status_code=404)

        if chemin and demande.is_file():
            return FileResponse(demande)
        return FileResponse(DASHBOARD_DIST / "index.html")


# Socket.IO traite /socket.io ; toutes les autres routes vont vers FastAPI.
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app, socketio_path="socket.io")