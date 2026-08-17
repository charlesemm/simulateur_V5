"""Expose les composants temps réel destinés à l'application FastAPI."""

from realtime.socket_server import (
    shutdown_event_pipeline, sio, socket_app, startup_event_pipeline,
)

__all__ = ["shutdown_event_pipeline", "sio", "socket_app", "startup_event_pipeline"]