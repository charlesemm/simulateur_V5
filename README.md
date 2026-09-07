# Simulateur CMU — Cockpit de Supervision & Télémétrie

Plateforme de simulation haute performance du parcours de soins CMU (Caisse Nationale d'Assurance Maladie - CNAM-CI) avec tableau de bord d'observabilité technique SRE en temps réel.

---

## ⚡ Démarrage Rapide

Deux façons de lancer le projet : **sans conteneur** (tout en local) ou avec
**Podman** pour PostgreSQL + l'API (option recommandée au quotidien — voir le
détail complet dans [GUIDE_PODMAN.md](GUIDE_PODMAN.md)).

### Option A — Routine du matin avec Podman

```powershell
podman machine start
podman compose up -d
podman compose ps
curl http://localhost:8000/health
```

Puis, pour le dashboard avec hot-reload :
```powershell
cd dashboard
npm run dev
```
*(sans cette étape, [http://localhost:8000](http://localhost:8000) sert directement la version compilée du dashboard — rien à lancer côté front.)*

Premier lancement seulement : suivre les étapes 2 et 4 de
[GUIDE_PODMAN.md](GUIDE_PODMAN.md) (`.env` avec `JWT_SECRET_KEY`, puis créer le
premier administrateur).

### Option B — Tout en local, sans conteneur

PostgreSQL installé sur la machine, l'API et le dashboard lancés directement.

#### 1. Configurer l'environnement
```powershell
copy .env.exemple .env
```

Renseigne `DATABASE_URL` avec ton mot de passe PostgreSQL local :
`postgresql+asyncpg://postgres:VOTRE_MOT_DE_PASSE@localhost:5432/cmu_simulator`

#### 2. Base de données, migrations et données
```powershell
.\.venv\Scripts\Activate.ps1
python -m alembic upgrade head
python -m auth.bootstrap
python -m seed
```

#### 3. Démarrage de l'API & WebSocket
```powershell
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

#### 4. Démarrage du Dashboard Frontend
```powershell
cd dashboard
npm install
npm run dev
```

### Accéder aux services 🌐
* 📊 **Dashboard (Interface React 19, mode dev)** : [http://localhost:5173](http://localhost:5173)
* 📊 **Dashboard (version compilée, servie par l'API)** : [http://localhost:8000](http://localhost:8000)
* 📡 **API FastAPI & Documentation Swagger** : [http://localhost:8000/docs](http://localhost:8000/docs)
* 🩺 **Healthcheck** : [http://localhost:8000/health](http://localhost:8000/health)

### 🩹 Dépannage — le dashboard affiche « NetworkError » ou « n'ont pas pu être chargés »

Sur ce type de poste, la machine Podman tourne parfois en mode *rootful* : le
port 8000 n'est alors publié que par une règle réseau interne à la VM WSL, et
`http://localhost:8000` reste injoignable depuis Windows le temps que ça dure
(l'API répond pourtant très bien à l'intérieur). C'est intermittent — pas
systématique.

1. Teste d'abord la voie normale :
   ```powershell
   curl http://localhost:8000/health
   ```
2. **Si ça répond**, vérifie que [dashboard/.env.local](dashboard/.env.local) pointe
   bien vers `http://localhost:8000` (pas une IP figée d'une session
   précédente), puis **redémarre** `npm run dev` — il ne relit pas le fichier
   à chaud.
3. **Si ça ne répond pas**, récupère l'IP interne de la VM et mets-la dans
   `dashboard/.env.local` (`VITE_API_URL=http://<IP>:8000`) :
   ```powershell
   podman machine ssh "ip -4 -o addr show eth0"
   ```
   Cette IP change à chaque redémarrage de la VM — à relire si le problème
   revient après un `podman machine start`.

---

## 🏗️ Architecture du Projet

```text
simulateur_v5/
├── api/                     ← Endpoints REST FastAPI & WebSocket Socket.IO
│   ├── main.py              ← Point d'entrée ASGI & configuration CORS
│   └── routes/              ← Routes (auth, simulation, métriques, rapports)
├── app/                     ← Configuration DB SQLAlchemy asynchrone & modèles
├── auth/                    ← Authentification JWT, hash bcrypt & bootstrap admin
├── dashboard/               ← Frontend SPA (React 19 + TypeScript + Vite + Tailwind/CSS)
│   ├── src/                 ← Composants télémétrie, graphiques Recharts & cockpit
│   └── nginx.conf           ← Configuration Nginx conservée pour la mise en production
├── events/                  ← Bus d'événements asynchrone interne
├── kpi/                     ← Calculateurs d'agrégations et métriques temps réel
├── metrics/                 ← Registre de métriques système (Prometheus / SRE)
├── realtime/                ← Gestionnaire des connexions Socket.IO
├── reports/                 ← Générateur de rapports PDF / Excel
├── seed/                    ← Scripts d'alimentation des données de santé
├── simulation/              ← Moteur de simulation (passages de soins, agents, files)
├── alembic/                 ← Migrations de schéma PostgreSQL
└── .github/workflows/       ← Pipeline CI/CD GitHub Actions (tests, build, image)
```

---

## 📊 Guide des Métriques du Tableau de Bord

Le tableau de bord est un **cockpit de supervision et d'observabilité 100% technique** permettant d'analyser en temps réel les performances du moteur asynchrone, de l'API FastAPI et du pipeline d'événements.

### 1. Compteurs de Performance Système (Rangée 1)

| Métrique | Description & Rôle | Formule / Source |
| :--- | :--- | :--- |
| **Concurrence Moteur** | Nombre de coroutines/passages exécutés simultanément par rapport à la limite fixée par le sémaphore asyncio (ex: 20 slots max). Le badge indique le pourcentage de saturation du moteur et le pic historique atteint. | `passages_actifs / passages_simultanes_max` (`asyncio.Semaphore`) |
| **Débit d'Événements** | Vitesse instantanée de génération des événements asynchrones sur le bus interne (`events.bus`). Permet d'observer l'accélération du moteur ($x1$ à $x3600$). | `evenements_totaux / uptime_secondes` ($ev/s$) |
| **Taux de Succès** | Pourcentage de passages de soins qui se sont exécutés de bout en bout sans lever d'exception ni d'erreur d'écriture en base de données. | `100 * passages_reussis / passages_totaux` (%) |
| **Latence Moyenne API** | Temps moyen mis par FastAPI pour traiter et retourner les requêtes HTTP (hors WebSocket), mesuré par le middleware de chronométrage. | `duree_totale_requetes / total_requetes` (en $ms$) |
| **Clients WebSocket** | Nombre de navigateurs ou clients connectés en direct au canal temps réel Socket.IO (`/kpi`) recevant les diffusions de données. | `clients_socketio_actifs` (temps réel) |
| **Mémoire & Uptime** | Empreinte mémoire vive résidente réelle (RAM RSS) occupée par le processus Python/Uvicorn et durée d'activité ininterrompue depuis le lancement. | `WorkingSetSize` (Win32 API) & `uptime_secondes` |

---

### 2. Graphiques de Télémétrie en Direct (Rangée 2)

* **Concurrence & Capacité Moteur** :
  * **Courbe verte** : Évolution seconde par seconde des passages actifs dans l'Event Loop asyncio.
  * **Ligne pointillée** : Plafond de capacité maximale du sémaphore.
  * *Interprétation* : Si la courbe verte colle au plafond pointillé, le moteur fonctionne à plein régime (saturation 100%).
* **Latence Réseau & Recalcul (ms)** :
  * **Courbe bleue** : Temps de réponse des requêtes HTTP FastAPI (latence API).
  * **Courbe orange** : Temps d'exécution du calcul d'agrégation du pipeline de données.

---

### 3. Fiabilité & Résilience aux Pannes (Rangée 3)

* **Fiabilité d'Exécution (Donut Recharts)** :
  * Répartition proportionnelle entre les passages réussis (vert) et les éventuelles exceptions système (rouge).
* **Test de Résilience & Anomalies (Chaos Testing)** :
  * Panneau de contrôle permettant d'injecter à chaud un pourcentage de données atypiques dans le moteur de simulation : montants négatifs ou démesurés, dates de soins antidatées, quantités servies supérieures aux quantités prescrites. Le compteur « Anomalies injectées » monte en direct pendant la simulation. La configuration est persistée en base et survit au redémarrage de l'API.

---

### 4. Console de Logs & Flux d'Événements (Rangée 4)

* **Journal Système en Streaming (Terminal SRE)** :
  * Affiche en direct le fil des opérations du moteur asynchrone, les passages validés, les recalculs de snapshots et les connexions réseau, avec filtrage multi-niveaux (`INFO`, `SUCCESS`, `WARN`, `ERROR`).

---

## 🛑 Arrêt Propre
1. Cliquer sur **Arrêter** dans la barre supérieure du Dashboard.
2. Interrompre `uvicorn` et `npm run dev` avec `Ctrl + C` dans leurs terminaux respectifs.

---

## 🚀 Conteneurisation, CI/CD et déploiement

**Lancer le projet en conteneurs** (PostgreSQL + API + dashboard, en une
commande) : voir **[GUIDE_PODMAN.md](GUIDE_PODMAN.md)**. Le `Containerfile` et
le `compose.yaml` sont à la racine.

**Le pipeline** (`.github/workflows/ci.yml`) : voir **[GUIDE_CICD.md](GUIDE_CICD.md)**.
À chaque poussée, il vérifie que le code compile, que les migrations passent sur
une base vierge, que les tests sont verts, que l'API démarre et que le dashboard
se construit. Sur `main` et sur les tags de version, il publie en plus l'image
sur GHCR (`ghcr.io/charlesemm/simulateur_v5`).

**Déploiement sur un serveur** : voir **[GUIDE_DEPLOIEMENT.md](GUIDE_DEPLOIEMENT.md)**.
Le pipeline s'arrête à une image publiée ; le serveur la tire. Les fichiers de
production sont dans `deploiement/` — un compose qui installe l'image au lieu de
la construire, Caddy pour le TLS, et le script de sauvegarde de la base. La mise
à jour reste lancée à la main : automatiser le déploiement depuis la CI est le
point ouvert du chantier X2.
