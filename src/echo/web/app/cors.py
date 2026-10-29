"""Les origines acceptées, définies une seule fois pour REST et temps réel.

Cette configuration vivait en double : une copie dans `api/main.py` pour le
middleware CORS de FastAPI, une copie identique dans `realtime/socket_server.py`
pour la poignée de main Socket.IO. Deux copies d'une règle de sécurité, c'est
une règle qu'on referme d'un côté en oubliant l'autre — et le temps réel reste
ouvert pendant que le REST est fermé, sans que rien ne le signale.

Ce module n'importe ni l'API ni le temps réel : les deux peuvent le lire sans
risque de dépendance circulaire.
"""

from __future__ import annotations

import os
import re

# Les deux origines Vite usuelles en développement.
_brut = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

ORIGINES = [origine.strip() for origine in _brut.split(",") if origine.strip()]
"""Liste explicite des origines autorisées."""

# Vite change de port dès qu'un autre serveur occupe le sien : un second
# « npm run dev » écoute sur 5174, et l'origine n'est plus dans la liste. Le
# préflight repart alors en 400, le navigateur bloque la requête, et l'écran de
# connexion ne peut pas distinguer ce refus d'une API éteinte — on cherche la
# panne dans son mot de passe pendant des heures.
#
# Toute origine locale est donc acceptée, quel que soit le port. Le « http:// »
# écrit ici ne décrit pas une destination qu'ÉCHO appelle : c'est le motif des
# origines locales de développement, du trafic qui ne quitte jamais la machine.
MOTIF_ORIGINE = os.getenv("CORS_ORIGIN_REGEX", r"http://(localhost|127\.0\.0\.1)(:\d+)?")
"""Expression régulière des origines tolérées. Vide = tolérance refermée.

En production, elle désigne le seul domaine du service (voir
deploiement/.env.exemple). Elle vaut pour **les deux** portes : le REST la
passe au middleware de Starlette, le temps réel la lit par `origine_autorisee`,
qui applique la même règle.
"""


def origine_autorisee(origine: str | None) -> bool:
    """La règle unique : dans la liste, ou reconnue en entier par le motif.

    C'est exactement ce que fait le middleware CORS de Starlette (liste, puis
    `fullmatch` du motif). Socket.IO ne sait pas lire une expression
    régulière, mais accepte une fonction : il reçoit celle-ci. Il recevait
    jusqu'ici « * » dès que le motif était posé — donc en production, où il
    est obligatoire, alors que le REST y était refermé.
    """

    if not origine:
        return False
    if origine in ORIGINES:
        return True
    return bool(MOTIF_ORIGINE) and re.fullmatch(MOTIF_ORIGINE, origine) is not None
