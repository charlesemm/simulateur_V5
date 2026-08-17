"""Expose le point d'entrée du module de peuplement référentiel."""

from seed.runner import main, seed_database

__all__ = ["main", "seed_database"]
