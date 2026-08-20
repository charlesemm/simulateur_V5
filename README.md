# Simulateur CMU — Cockpit de Supervision & Télémétrie

Plateforme de simulation haute performance du parcours de soins CMU (Caisse Nationale d'Assurance Maladie - CNAM-CI) avec tableau de bord d'observabilité technique SRE en temps réel.

---

## ⚡ Démarrage Rapide (avec Docker Compose — Recommandé)

### 1. Cloner et configurer l'environnement
```powershell
# Copier le fichier d'exemple
copy .env.exemple .env
```

### 2. Lancer toute l'infrastructure (Base, API, Dashboard)
```powershell
docker compose up --build
```

### 3. Dans un deuxième terminal — Initialiser l'admin et charger les données
```powershell
# 1. Créer le compte administrateur
docker compose exec api python -m auth.bootstrap

# 2. Charger les données référentielles (Centres de santé, affections, assurés)
docker compose exec api python -m seed
```

### 4. Accéder aux services 🌐
* 📊 **Dashboard (Interface React 19)** : [http://localhost:5173](http://localhost:5173)
* 📡 **API FastAPI & Documentation Swagger** : [http://localhost:8000/docs](http://localhost:8000/docs)
* 🩺 **Healthcheck** : [http://localhost:8000/health](http://localhost:8000/health)

---

## 💻 Démarrage Local Alternatif (sans Docker)

### 1. Base de données & Migrations
```powershell
.\.venv\Scripts\Activate.ps1
$env:DATABASE_URL = "postgresql+asyncpg://postgres:VOTRE_MOT_DE_PASSE@localhost:5432/cmu_simulator"
python -m alembic upgrade head
python -m auth.bootstrap
python -m seed
```

### 2. Démarrage de l'API & WebSocket
```powershell
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Démarrage du Dashboard Frontend
```powershell
cd dashboard
npm install
npm run dev
```

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
│   ├── Dockerfile           ← Build multi-étapes Node.js + Nginx pour la prod
│   └── nginx.conf           ← Configuration serveur Nginx & reverse proxy
├── events/                  ← Bus d'événements asynchrone interne
├── kpi/                     ← Calculateurs d'agrégations et métriques temps réel
├── metrics/                 ← Registre de métriques système (Prometheus / SRE)
├── realtime/                ← Gestionnaire des connexions Socket.IO
├── reports/                 ← Générateur de rapports PDF / Excel
├── seed/                    ← Scripts d'alimentation des données de santé
├── simulation/              ← Moteur de simulation (passages de soins, agents, files)
├── alembic/                 ← Migrations de schéma PostgreSQL
├── Dockerfile               ← Image Docker backend Python 3.12-slim
├── docker-compose.yml       ← Environnement de développement avec hot reload
├── docker-compose.prod.yml  ← Environnement de production
└── .github/workflows/       ← Pipeline CI/CD GitHub Actions (Tests & Déploiement auto)
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
  * Panneau de contrôle permettant d'injecter à chaud un pourcentage de données atypiques ou malformées (incohérence de dates, numéros de sécurité sociale tronqués, montants atypiques) afin d'éprouver la robustesse du moteur.

---

### 4. Console de Logs & Flux d'Événements (Rangée 4)

* **Journal Système en Streaming (Terminal SRE)** :
  * Affiche en direct le fil des opérations du moteur asynchrone, les passages validés, les recalculs de snapshots et les connexions réseau, avec filtrage multi-niveaux (`INFO`, `SUCCESS`, `WARN`, `ERROR`).

---

## 🛑 Arrêt Propre
1. Cliquer sur **Arrêter** dans la barre supérieure du Dashboard.
2. Pour arrêter Docker : `Ctrl + C` puis `docker compose down`.

---

## 🐳 Déploiement Production, CI/CD & Hébergement Gratuit (0€)

Pour conteneuriser l'application, mettre en place la CI/CD ou l'héberger sans débourser un centime, consulte le guide complet :

👉 **[GUIDE_DOCKER_CICD_PRODUCTION.md](./GUIDE_DOCKER_CICD_PRODUCTION.md)**

Ce guide détaille :
* **Déploiement Serveur Entreprise** : Docker Compose figé, reverse proxy Nginx, CI/CD GitHub Actions vers serveur dédié.
* **Hébergement 100% Gratuit** :
  * Backend & WebSockets sur **Koyeb** ou **Render** (0€)
  * Frontend React sur **Vercel** ou **Cloudflare Pages** (0€)
  * PostgreSQL managé sur **Neon.tech** ou **Supabase** (0€)
  * Alternative VPS tout-en-un sur **Oracle Cloud Always Free** (4 CPU ARM, 24 Go RAM gratuits à vie)
* **Noms de domaine gratuits & SSL HTTPS** : Sous-domaines automatiques avec certificats SSL ou **DuckDNS**.
