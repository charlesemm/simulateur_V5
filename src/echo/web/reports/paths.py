"""Emplacement partagé des rapports générés sur le disque."""
from pathlib import Path

OUTPUT_DIR = Path("reports/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)