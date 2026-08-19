"""Permet d'exécuter le seed avec la commande python -m seed."""

import os
from seed.anomalies import anomalies_config
from seed.runner import main


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
        print(f"\n✓ Seed complété. Anomalies injectées : {anomalies_config.injected_count}")
    else:
        print("\n✓ Seed complété. Aucune anomalie.")