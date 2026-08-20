# GUIDE 4 — Sécuriser les endpoints

> **Chantier 4 sur 8** du plan de remise en ordre du projet `simulateur_V5`.
> Prérequis : [GUIDE_3_DOCKER_ET_TEMPS_REEL.md](./GUIDE_3_DOCKER_ET_TEMPS_REEL.md) terminé (commit `dedd982` poussé).

---

## En deux mots

Le projet a une authentification JWT complète, avec trois rôles hiérarchiques. **Elle n'est appliquée que sur la moitié des routes.**

Aujourd'hui, sans aucun mot de passe, n'importe qui atteignant l'API peut :

- **lire le dossier médical complet d'un assuré** — pathologies, prescriptions, montants
- consulter tous les indicateurs métier et techniques
- **remettre les compteurs de métriques à zéro** (une requête `POST`, sans authentification)

Ce chantier applique l'authentification partout où elle manque — backend **et** frontend, car les deux doivent évoluer ensemble.

> ⚠️ **Ce chantier casse le dashboard s'il est fait à moitié.** Le frontend appelle aujourd'hui six endpoints sans jeton. Si tu protèges le backend sans adapter le frontend, tout le cockpit renvoie `401`. **Fais les parties A à E d'une traite.**

---

## Table des matières

- [Inventaire : qui est protégé, qui ne l'est pas](#inventaire--qui-est-protégé-qui-ne-lest-pas)
- [Les trois rôles](#les-trois-rôles)
- [Partie A — Backend : la route la plus sensible](#partie-a--backend--la-route-la-plus-sensible)
- [Partie B — Backend : l'écriture non authentifiée](#partie-b--backend--lécriture-non-authentifiée)
- [Partie C — Backend : les routes de consultation](#partie-c--backend--les-routes-de-consultation)
- [Partie D — Frontend : transmettre le jeton](#partie-d--frontend--transmettre-le-jeton)
- [Partie E — Le temps réel aussi](#partie-e--le-temps-réel-aussi)
- [Partie F — Bonus : supprimer les composants orphelins](#partie-f--bonus--supprimer-les-composants-orphelins)
- [Partie G — Vérifier et commiter](#partie-g--vérifier-et-commiter)
- [Récapitulatif](#récapitulatif)

---

## Inventaire : qui est protégé, qui ne l'est pas

### ✅ Déjà protégé

| Route | Rôle exigé | Fichier |
|---|---|---|
| `POST /simulation/start` `/stop` `/speed` | `operateur` | `api/routers/simulation.py` |
| `GET` `POST` `/reports/*` | `operateur` | `api/routers/reports.py` |
| `GET` `POST` `PATCH` `/users/*` | `administrateur` | `api/routers/users.py` |
| `GET` `PATCH` `POST` `/anomalies/*` | `administrateur` | `api/routers/anomalies.py` |

### ❌ Ouvert à tous

| Route | Ce qu'elle expose | Gravité |
|---|---|---|
| `GET /factures/{numero}` | Dossier médical : pathologies, prescriptions, montants, `personne_uuid` | 🔴 **Critique** |
| `POST /metrics/technical/reset` | **Écriture** — remet les compteurs à zéro | 🔴 **Critique** |
| `GET /kpi/snapshot` | Tous les indicateurs métier | 🟠 Élevée |
| `GET /kpi/{nom}/history` | Séries historiques | 🟠 Élevée |
| `GET /metrics/technical` | Métriques système, mémoire, uptime | 🟠 Élevée |
| `GET /centres-sante` | Référentiel des centres | 🟡 Moyenne |
| `GET /simulation/status` | État du moteur | 🟡 Moyenne |
| Socket.IO `/kpi` | **Diffusion continue** de tous les KPI | 🔴 **Critique** |

### ✅ Publiques à dessein — on n'y touche pas

| Route | Pourquoi elle doit rester ouverte |
|---|---|
| `POST /auth/login` | C'est la porte d'entrée : l'exiger authentifiée serait absurde |
| `GET /health` | Utilisée par le healthcheck Docker et le smoke test de la CI (`ci.yml:56`). La protéger casserait le déploiement |

---

## Les trois rôles

`auth/dependencies.py:20` définit une hiérarchie : **un rôle donne accès à son niveau et à tout ce qui est en dessous.**

```python
ROLE_HIERARCHY = {"observateur": 0, "operateur": 1, "administrateur": 2}
```

| Rôle | Peut faire |
|---|---|
| `observateur` | Consulter — c'est le niveau minimum d'un compte authentifié |
| `operateur` | Consulter + piloter le moteur + générer des rapports |
| `administrateur` | Tout + gérer les utilisateurs et les anomalies |

👉 **`require_role("observateur")` signifie donc « n'importe quel compte valide et actif ».** C'est ce qu'on va appliquer aux routes de consultation.

---

## Partie A — Backend : la route la plus sensible

**Fichier :** `api/routers/factures.py`

### Pourquoi celle-ci d'abord

`GET /factures/{facture_numero}` renvoie le détail complet d'une facture : `personne_uuid`, la liste des **pathologies** diagnostiquées, les **prescriptions** médicamenteuses, les montants. Ce sont des **données de santé**.

Aujourd'hui, une simple requête suffit — sans compte, sans mot de passe.

### La correction

**Remplace les lignes 1 à 11** de `api/routers/factures.py` :

```python
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import async_session_factory
from app.models import Invoice
from api.schema import (
    InvoiceDetailResponse, InvoicePathologySchema, InvoicePrescriptionSchema,
    InvoiceProvisionSchema, InvoiceStatusSchema,
)

router = APIRouter(prefix="/factures", tags=["Factures"])
```

**Par :**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import async_session_factory
from app.models import Invoice
from api.schema import (
    InvoiceDetailResponse, InvoicePathologySchema, InvoicePrescriptionSchema,
    InvoiceProvisionSchema, InvoiceStatusSchema,
)
from auth.dependencies import require_role

# Les factures portent des données de santé : aucun accès anonyme.
router = APIRouter(
    prefix="/factures",
    tags=["Factures"],
    dependencies=[Depends(require_role("observateur"))],
)
```

**Deux changements :** `Depends` ajouté à l'import `fastapi`, et le paramètre `dependencies` sur le routeur.

> **Pourquoi `dependencies=[...]` sur le routeur plutôt que sur chaque route ?** La protection s'applique automatiquement à toute route ajoutée plus tard dans ce fichier. On ne peut pas oublier.

---

## Partie B — Backend : l'écriture non authentifiée

**Fichier :** `api/routers/metrics.py`

### Le problème

`POST /metrics/technical/reset` remet à zéro huit compteurs. C'est une **écriture**, exposée sans aucune authentification.

Deux niveaux différents s'imposent ici :

- **Lire** les métriques → `observateur`
- **Les remettre à zéro** → `operateur`, comme les autres commandes de pilotage

On ne peut donc pas protéger tout le routeur d'un bloc : il faut deux niveaux.

### La correction

**Remplace les lignes 1 à 8 :**

```python
"""Expose les métriques d'observabilité et de performance système du simulateur."""
from __future__ import annotations

from fastapi import APIRouter
from metrics.registry import registry as metrics_registry
from api.services.simulation_manager import simulation_manager

router = APIRouter(prefix="/metrics", tags=["Métriques Techniques"])
```

**Par :**

```python
"""Expose les métriques d'observabilité et de performance système du simulateur."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from metrics.registry import registry as metrics_registry
from api.services.simulation_manager import simulation_manager
from auth.dependencies import require_role

# Lecture : tout compte authentifié. La remise à zéro exige « operateur ».
router = APIRouter(
    prefix="/metrics",
    tags=["Métriques Techniques"],
    dependencies=[Depends(require_role("observateur"))],
)
```

**Puis, sur la route de remise à zéro**, remplace :

```python
@router.post("/technical/reset")
async def reset_technical_metrics() -> dict[str, str]:
```

**Par :**

```python
@router.post("/technical/reset", dependencies=[Depends(require_role("operateur"))])
async def reset_technical_metrics() -> dict[str, str]:
```

> **Les deux dépendances se cumulent** : FastAPI exécute celle du routeur puis celle de la route. Un `observateur` passera la première et sera refusé par la seconde, avec un `403`.

---

## Partie C — Backend : les routes de consultation

Trois fichiers, tous sur le même modèle : ajouter `Depends` à l'import et `dependencies` au routeur.

### C.1 — `api/routers/kpi.py`

**Remplace les lignes 1 à 9 :**

```python
"""Expose le snapshot et les séries historiques de KPI."""

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Query
from api.schema import Granularity, KpiHistoryResponse, KpiName, KpiSnapshotResponse
from api.services.history import calculate_history
from kpi import KpiService

router = APIRouter(prefix="/kpi", tags=["KPI"])
```

**Par :**

```python
"""Expose le snapshot et les séries historiques de KPI."""

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from api.schema import Granularity, KpiHistoryResponse, KpiName, KpiSnapshotResponse
from api.services.history import calculate_history
from auth.dependencies import require_role
from kpi import KpiService

router = APIRouter(
    prefix="/kpi",
    tags=["KPI"],
    dependencies=[Depends(require_role("observateur"))],
)
```

### C.2 — `api/routers/centres.py`

**Remplace les lignes 1 à 7 :**

```python
from fastapi import APIRouter
from sqlalchemy import select
from app.database import async_session_factory
from app.models import HealthCenter
from api.schema import HealthCenterListResponse, HealthCenterSchema

router = APIRouter(tags=["Centres de santé"])
```

**Par :**

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from app.database import async_session_factory
from app.models import HealthCenter
from api.schema import HealthCenterListResponse, HealthCenterSchema
from auth.dependencies import require_role

router = APIRouter(
    tags=["Centres de santé"],
    dependencies=[Depends(require_role("observateur"))],
)
```

### C.3 — `api/routers/simulation.py`

Ce fichier protège déjà `start`, `stop` et `speed`. Il ne manque que `status`.

**Remplace :**

```python
@router.get("/status", response_model=SimulationStatusResponse)
async def get_status() -> SimulationStatusResponse:
```

**Par :**

```python
@router.get("/status", response_model=SimulationStatusResponse,
            dependencies=[Depends(require_role("observateur"))])
async def get_status() -> SimulationStatusResponse:
```

---

## Partie D — Frontend : transmettre le jeton

Le backend exige maintenant un jeton sur six endpoints. **Le dashboard ne l'envoie pas encore.** Sans cette partie, tout le cockpit affiche `401`.

### D.1 — `dashboard/src/services/api.ts`

Cinq fonctions doivent accepter un jeton. **Remplace les cinq blocs suivants.**

**`getSnapshot` — remplace :**

```typescript
  async getSnapshot(signal?: AbortSignal): Promise<KpiSnapshot> {
    const response = await fetch(`${API_URL}/kpi/snapshot`, { signal });
    return parseOrThrow<KpiSnapshot>(response);
  },
```

**par :**

```typescript
  async getSnapshot(token: string | null, signal?: AbortSignal): Promise<KpiSnapshot> {
    const response = await fetch(`${API_URL}/kpi/snapshot`, {
      headers: authHeaders(token),
      signal,
    });
    return parseOrThrow<KpiSnapshot>(response);
  },
```

**`getPassageHistory` — remplace :**

```typescript
  async getPassageHistory(signal?: AbortSignal): Promise<KpiHistory> {
    const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    const response = await fetch(
      `${API_URL}/kpi/passages/history?since=${encodeURIComponent(since)}&granularite=heure`,
      { signal }
    );
    return parseOrThrow<KpiHistory>(response);
  },
```

**par :**

```typescript
  async getPassageHistory(token: string | null, signal?: AbortSignal): Promise<KpiHistory> {
    const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    const response = await fetch(
      `${API_URL}/kpi/passages/history?since=${encodeURIComponent(since)}&granularite=heure`,
      { headers: authHeaders(token), signal }
    );
    return parseOrThrow<KpiHistory>(response);
  },
```

**`getCenters` — remplace :**

```typescript
  async getCenters(signal?: AbortSignal): Promise<HealthCenterList> {
    const response = await fetch(`${API_URL}/centres-sante`, { signal });
    return parseOrThrow<HealthCenterList>(response);
  },
```

**par :**

```typescript
  async getCenters(token: string | null, signal?: AbortSignal): Promise<HealthCenterList> {
    const response = await fetch(`${API_URL}/centres-sante`, {
      headers: authHeaders(token),
      signal,
    });
    return parseOrThrow<HealthCenterList>(response);
  },
```

**`getSimulationStatus` — remplace :**

```typescript
  async getSimulationStatus(): Promise<SimulationStatus> {
    const response = await fetch(`${API_URL}/simulation/status`);
    return parseOrThrow<SimulationStatus>(response);
  },
```

**par :**

```typescript
  async getSimulationStatus(token: string | null = null): Promise<SimulationStatus> {
    const response = await fetch(`${API_URL}/simulation/status`, {
      headers: authHeaders(token),
    });
    return parseOrThrow<SimulationStatus>(response);
  },
```

**`getTechnicalMetrics` et `resetTechnicalMetrics` — remplace :**

```typescript
  async getTechnicalMetrics(signal?: AbortSignal): Promise<import("../types").TechnicalMetricsSnapshot> {
    const response = await fetch(`${API_URL}/metrics/technical`, { signal });
    return parseOrThrow<import("../types").TechnicalMetricsSnapshot>(response);
  },

  async resetTechnicalMetrics(): Promise<{ message: string }> {
    const response = await fetch(`${API_URL}/metrics/technical/reset`, { method: "POST" });
    return parseOrThrow<{ message: string }>(response);
  },
```

**par :**

```typescript
  async getTechnicalMetrics(
    token: string | null,
    signal?: AbortSignal
  ): Promise<import("../types").TechnicalMetricsSnapshot> {
    const response = await fetch(`${API_URL}/metrics/technical`, {
      headers: authHeaders(token),
      signal,
    });
    return parseOrThrow<import("../types").TechnicalMetricsSnapshot>(response);
  },

  async resetTechnicalMetrics(token: string | null = null): Promise<{ message: string }> {
    const response = await fetch(`${API_URL}/metrics/technical/reset`, {
      method: "POST",
      headers: authHeaders(token),
    });
    return parseOrThrow<{ message: string }>(response);
  },
```

> La fonction `authHeaders(token)` existe déjà en haut du fichier (ligne 7). On ne fait que l'employer là où elle manquait.

### D.2 — `dashboard/src/App.tsx`

Le composant `DashboardShell` utilise déjà `useAuth()`. Il suffit d'en extraire le jeton.

**Remplace :**

```typescript
  const { isAuthenticated } = useAuth();
```

**par :**

```typescript
  const { isAuthenticated, token } = useAuth();
```

**Puis remplace :**

```typescript
        const data = await api.getTechnicalMetrics();
```

**par :**

```typescript
        const data = await api.getTechnicalMetrics(token);
```

**Et remplace la ligne de dépendances de l'effet :**

```typescript
  }, [isAuthenticated]);
```

**par :**

```typescript
  }, [isAuthenticated, token]);
```

> **Pourquoi ajouter `token` aux dépendances :** sans lui, React garderait l'ancien jeton en mémoire après une reconnexion, et les appels échoueraient en `401`.

### D.3 — `dashboard/src/components/Header.tsx`

Le fichier importe déjà `useAuth` et dispose de `token`. Il y a **deux appels** à corriger.

**Ligne 33 environ — remplace :**

```typescript
        const value = await api.getSimulationStatus();
```

**par :**

```typescript
        const value = await api.getSimulationStatus(token);
```

**Ligne 74 environ (dans `handleArreter`) — remplace :**

```typescript
      setStatus(await api.getSimulationStatus());
```

**par :**

```typescript
      setStatus(await api.getSimulationStatus(token));
```

**Puis, la ligne de dépendances de l'effet — remplace :**

```typescript
  }, []);
```

**par :**

```typescript
  }, [token]);
```

> ⚠️ Attention : `}, []);` peut apparaître plusieurs fois dans le fichier. **Celle à modifier est celle qui suit immédiatement `void refreshStatus();` et `clearInterval(interval);`** — vers la ligne 71.

### D.4 — `dashboard/src/hooks/useKpiSocket.tsx`

C'est le seul fichier qui n'a pas encore accès au jeton.

**Remplace les imports :**

```typescript
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { io, type Socket } from "socket.io-client";
import { API_URL, api } from "../services/api";
import type { ConnectionStatus, HistoryPoint, KpiSnapshot, KpiUpdate } from "../types";
```

**par :**

```typescript
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { io, type Socket } from "socket.io-client";
import { useAuth } from "../auth/AuthContext";
import { API_URL, api } from "../services/api";
import type { ConnectionStatus, HistoryPoint, KpiSnapshot, KpiUpdate } from "../types";
```

**Puis, dans `KpiSocketProvider`, remplace :**

```typescript
export function KpiSocketProvider({ children }: { children: ReactNode }) {
  const [snapshot, setSnapshot] = useState<KpiSnapshot | null>(null);
```

**par :**

```typescript
export function KpiSocketProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  const [snapshot, setSnapshot] = useState<KpiSnapshot | null>(null);
```

**Puis remplace les deux appels REST :**

```typescript
    Promise.all([
      api.getSnapshot(controller.signal),
      api.getPassageHistory(controller.signal),
    ]).then(([initialSnapshot, initialHistory]) => {
```

**par :**

```typescript
    Promise.all([
      api.getSnapshot(token, controller.signal),
      api.getPassageHistory(token, controller.signal),
    ]).then(([initialSnapshot, initialHistory]) => {
```

**Enfin, la ligne de dépendances tout en bas de l'effet — remplace :**

```typescript
  }, []);
```

**par :**

```typescript
  }, [token]);
```

---

## Partie E — Le temps réel aussi

**Fichiers :** `realtime/socket_server.py` et `dashboard/src/hooks/useKpiSocket.tsx`

### Le problème

Le chantier 3 a réparé le CORS, mais le CORS **n'est pas de l'authentification** : il indique au navigateur quelles origines peuvent parler au serveur. Il n'empêche rien en dehors d'un navigateur.

Aujourd'hui, `realtime/socket_server.py:11` accepte **toute** connexion au namespace `/kpi`, puis lui envoie immédiatement un snapshot complet — et toutes les mises à jour ensuite. Un simple client Socket.IO suffit à recevoir le flux, sans compte.

### E.1 — Backend

**Remplace la fonction `connect` de `realtime/socket_server.py` :**

```python
@sio.event(namespace="/kpi")
async def connect(sid, environ, auth) -> None:
    """Accepte le client et lui envoie immédiatement un état complet."""
    metrics_registry.enregistrer_connexion_socketio()
    del environ, auth
    snapshot = await KpiService().calculate_snapshot()
    await sio.emit("kpi:snapshot", snapshot, to=sid, namespace="/kpi")
```

**Par :**

```python
@sio.event(namespace="/kpi")
async def connect(sid, environ, auth) -> None:
    """Vérifie le jeton JWT du client avant de lui ouvrir le flux KPI."""

    del environ
    jeton = (auth or {}).get("token")
    if not jeton:
        raise socketio.exceptions.ConnectionRefusedError(
            "Jeton d'authentification absent."
        )
    try:
        decode_access_token(jeton)
    except jwt.PyJWTError as exc:
        raise socketio.exceptions.ConnectionRefusedError(
            "Jeton invalide ou expiré."
        ) from exc

    metrics_registry.enregistrer_connexion_socketio()
    snapshot = await KpiService().calculate_snapshot()
    await sio.emit("kpi:snapshot", snapshot, to=sid, namespace="/kpi")
```

**Et ajoute deux imports** en haut du même fichier, après `import socketio` :

```python
import jwt

from auth.security import decode_access_token
```

> **`ConnectionRefusedError`** est l'exception prévue par `python-socketio` : elle refuse la poignée de main et transmet le motif au client. Le paramètre `auth` était déjà présent dans la signature — il était simplement jeté par le `del`.

### E.2 — Frontend

**Dans `dashboard/src/hooks/useKpiSocket.tsx`, remplace :**

```typescript
    socket = io(`${API_URL}/kpi`, {
      path: "/socket.io",
      transports: ["websocket", "polling"],
```

**par :**

```typescript
    socket = io(`${API_URL}/kpi`, {
      path: "/socket.io",
      auth: { token },
      transports: ["websocket", "polling"],
```

> L'option `auth` de Socket.IO transmet cet objet au serveur pendant la poignée de main. C'est exactement le paramètre `auth` que reçoit la fonction `connect` côté Python.

---

## Partie F — Bonus : supprimer les composants orphelins

Quatre composants React ne sont **importés nulle part**. Ils datent d'une version antérieure du dashboard, avant le passage au cockpit technique.

| Fichier | Statut |
|---|---|
| `dashboard/src/components/ActsDonut.tsx` | orphelin |
| `dashboard/src/components/CenterLoadTable.tsx` | orphelin |
| `dashboard/src/components/MetricCards.tsx` | orphelin |
| `dashboard/src/components/PathologiesBar.tsx` | orphelin |

```powershell
git rm dashboard/src/components/ActsDonut.tsx dashboard/src/components/CenterLoadTable.tsx dashboard/src/components/MetricCards.tsx dashboard/src/components/PathologiesBar.tsx
```

> **Sans risque.** Aucun `import` ne les référence — le build TypeScript le confirmera en partie G. Et git conserve leur historique si tu veux les retrouver.
>
> ℹ️ `CenterLoadTable` était le seul consommateur de `getCenters`. En le supprimant, plus rien n'appelle `/centres-sante` — la route reste protégée et disponible pour l'API.

---

## Partie G — Vérifier et commiter

### G.1 — Le backend compile

```powershell
python -m compileall app api auth events kpi metrics realtime reports seed simulation run_simulation.py
```

### G.2 — Les routes exigent bien un jeton

Démarre l'API :

```powershell
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Dans un **second terminal** :

```powershell
curl.exe -s -o NUL -w "%{http_code}`n" http://127.0.0.1:8000/kpi/snapshot
```

Attendu : **`401`**

```powershell
curl.exe -s -o NUL -w "%{http_code}`n" http://127.0.0.1:8000/health
```

Attendu : **`200`** — la route de santé doit rester publique.

```powershell
curl.exe -s -o NUL -w "%{http_code}`n" -X POST http://127.0.0.1:8000/metrics/technical/reset
```

Attendu : **`401`**

### G.3 — Le frontend compile

```powershell
cd dashboard
```

```powershell
npm run build
```

> Cette commande lance `tsc --noEmit` avant le build. **C'est le filet de sécurité de la partie D** : si tu as oublié de passer `token` à un appel, TypeScript refusera de compiler et te donnera le fichier et la ligne.

### G.4 — Le dashboard fonctionne de bout en bout

```powershell
npm run dev
```

Ouvre <http://localhost:5173> et connecte-toi. Vérifie **dans l'ordre** :

| # | Point de contrôle | Attendu |
|---|---|---|
| 1 | Cartes de métriques | Chiffres qui se rafraîchissent |
| 2 | Badge de connexion | **`connecté`** |
| 3 | Bouton **Démarrer** | Le moteur démarre |
| 4 | Graphiques | Mise à jour en direct |
| 5 | Onglets Rapports / Utilisateurs | Accessibles |

Puis **déconnecte-toi** : le badge doit repasser à `déconnecté` et plus aucune donnée ne doit arriver. C'est la preuve que la partie E fonctionne.

### G.5 — Commit

⚠️ **Depuis la racine**, pas depuis `dashboard/`.

```powershell
cd C:\Users\charles.nguessan\Documents\simulateur_V5
```

```powershell
git add .
```

```powershell
git status --short
```

```powershell
git commit -m "securite: exige un jeton sur les routes de consultation, le reset et le flux temps reel"
```

```powershell
git push origin main
```

---

## Récapitulatif

| Partie | Fichier | Modification |
|---|---|---|
| **A** | `api/routers/factures.py` | 🔴 Protège les données de santé — `observateur` |
| **B** | `api/routers/metrics.py` | 🔴 Lecture `observateur`, reset `operateur` |
| **C.1** | `api/routers/kpi.py` | `observateur` sur le routeur |
| **C.2** | `api/routers/centres.py` | `observateur` sur le routeur |
| **C.3** | `api/routers/simulation.py` | `observateur` sur `/status` |
| **D.1** | `dashboard/src/services/api.ts` | 6 fonctions reçoivent le jeton |
| **D.2** | `dashboard/src/App.tsx` | Transmet le jeton + dépendance d'effet |
| **D.3** | `dashboard/src/components/Header.tsx` | 2 appels + dépendance d'effet |
| **D.4** | `dashboard/src/hooks/useKpiSocket.tsx` | `useAuth` + 2 appels + dépendance |
| **E.1** | `realtime/socket_server.py` | 🔴 Vérifie le JWT à la connexion |
| **E.2** | `dashboard/src/hooks/useKpiSocket.tsx` | Envoie le jeton au socket |
| **F** | 4 composants React | Suppression de code mort |

---

## Ce qu'on ne fait PAS dans ce chantier

**Le rafraîchissement automatique du jeton.** Les jetons expirent au bout de 8 heures (`auth/security.py:15`). Passé ce délai, l'utilisateur doit se reconnecter à la main.

Un mécanisme de *refresh token* serait plus confortable, mais c'est une fonctionnalité à part entière — pas une réparation. À traiter séparément si le besoin se confirme.

---

## Suite du plan

| Chantier | Objet |
|---|---|
| ~~0~~ | ~~Remise en route sur la nouvelle machine~~ ✅ |
| ~~1~~ | ~~Hygiène git & secrets~~ ✅ `fad04bd` |
| ~~2~~ | ~~Nettoyage des doublons~~ ✅ `7ef5a3c` |
| ~~3~~ | ~~Docker & temps réel~~ ✅ `dedd982` |
| **4** | **Sécurisation des endpoints** ← *ce guide* |
| 5 | Brancher les anomalies sur le moteur (ou corriger la doc) |
| 6 | Performance des KPI (agrégations SQL) |
| 7 | Tests automatisés (pytest + CI) |
| 8 | Figer la migration `0001` en SQL explicite |
