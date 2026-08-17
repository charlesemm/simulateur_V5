"""Lance le moteur CMU en standalone depuis la ligne de commande."""

import argparse
import asyncio
import logging
from simulation import SimulationEngine, SimulationEvent

async def log_event(event: SimulationEvent) -> None:
    """Affiche chaque événement en attendant Socket.IO à l'étape 4."""

    logging.getLogger("evenements").info("%s | %s", event.event_type, event.to_dict())

def parse_arguments() -> argparse.Namespace:
    """Valide les paramètres de lancement standalone."""

    parser = argparse.ArgumentParser(description="Simulateur standalone du parcours assuré CMU.")
    parser.add_argument("--nombre-passages", type=int, default=10)
    parser.add_argument("--vitesse", type=float, default=60.0)
    arguments = parser.parse_args()
    if arguments.nombre_passages <= 0 or arguments.vitesse <= 0:
        parser.error("Les deux paramètres doivent être strictement positifs.")
    return arguments

async def run() -> None:
    """Configure et attend la fin du moteur."""

    arguments = parse_arguments()
    engine = SimulationEngine(event_callback=log_event)
    engine.set_speed(arguments.vitesse)
    try:
        await engine.start(arguments.nombre_passages)
    except KeyboardInterrupt:
        await engine.stop()

async def run() -> None:
    """Configure et attend la fin du moteur."""
    arguments = parse_arguments()
    engine = SimulationEngine(event_callback=log_event)
    engine.set_speed(arguments.vitesse)
    try:
        await engine.start(arguments.nombre_passages)
    except KeyboardInterrupt:
        await engine.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    asyncio.run(run())