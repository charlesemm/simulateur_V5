"""Permet d'exécuter le seed avec la commande python -m seed."""

import os
import sys

from anomalies import anomalies_config
from seed.runner import main


def afficher(message: str) -> None:
    """Écrit une ligne sans jamais faire échouer le seed sur l'encodage.

    La console Windows redirigée est en cp1252 : un simple « ✓ » y levait une
    UnicodeEncodeError, après que le seed avait pourtant tout commité. Le
    peuplement paraissait alors échoué alors qu'il avait réussi.
    """

    try:
        print(message)
    except UnicodeEncodeError:
        encodage = sys.stdout.encoding or "ascii"
        print(message.encode(encodage, "replace").decode(encodage))


if __name__ == "__main__":
    # Charger la configuration des anomalies depuis les variables d'env
    anomalies_config.enabled = os.getenv("ANOMALIES_ENABLED", "false").lower() == "true"
    try:
        anomalies_config.rate = float(os.getenv("ANOMALIES_RATE", "0.0"))
    except ValueError:
        anomalies_config.rate = 0.0

    main()

    # Afficher un résumé après le seed
    if anomalies_config.injected_count > 0:
        afficher(f"\nSeed complété. Anomalies injectées : {anomalies_config.injected_count}")
    else:
        afficher("\nSeed complété. Aucune anomalie.")
