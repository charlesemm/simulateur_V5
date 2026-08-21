"""Lance le moteur CMU en standalone depuis la ligne de commande."""

import argparse
import asyncio
import logging
from events import publish_simulation_event
from simulation import SimulationEngine, SimulationEvent

async def log_event(event: SimulationEvent) -> None:
    """Affiche l'événement puis le journalise, comme le fait l'API.

    Sans la publication, un passage lancé en ligne de commande produisait une
    facture sans aucune trace dans TB_EVENEMENTS_METIER : son parcours était
    donc introuvable, alors que la même facture créée via l'API l'exposait.
    """

    logging.getLogger("evenements").info("%s | %s", event.event_type, event.to_dict())
    await publish_simulation_event(event)

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

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    asyncio.run(run())