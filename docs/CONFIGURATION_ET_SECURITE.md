# Configuration et sécurité

## Variables d'environnement

Fichier modèle : `.env.exemple` (copier en `.env`). En production : `deploiement/.env.exemple`.

| Variable | Obligatoire | Rôle |
|---|---|---|
| `DATABASE_URL` | oui | `postgresql+asyncpg://utilisateur:motdepasse@hôte:5432/echo_db_v2`. Hôte `postgres` en conteneur, `localhost` en local |
| `JWT_SECRET_KEY` | oui | Clé de signature des jetons. L'API refuse de démarrer sans elle. Générer une valeur longue et aléatoire |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | conteneur | Initialisation de PostgreSQL ; doivent rester alignés sur `compose.yaml` |
| `CORS_ORIGINS` | non | Origines autorisées, séparées par des virgules (défaut : `http://localhost:5173,http://127.0.0.1:5173`) |
| `CORS_ORIGIN_REGEX` | non | Motif d'origine autorisé (défaut : localhost / 127.0.0.1 sur tout port) |
| `VITE_API_URL` | front | URL de l'API vue du navigateur |
| `ECHO_ADMIN_PASSWORD` | bootstrap | Mot de passe du premier administrateur, lu par `python -m echo.web.auth.bootstrap --creer` (par l'environnement, jamais en argument) |
| `ECHO_DOCS_PUBLIQUES` | non | `true` (défaut) : `/docs`, `/redoc`, `/openapi.json` ouverts. `false` en production |
| `SEED_ON_START` | non | Alimenter les données au démarrage |
| `ANOMALIES_ENABLED`, `ANOMALIES_RATE` | non | Injection d'anomalies au démarrage du seed |
| `TAUX_COUVERTURE` | non | Couverture des référentiels du seed (0,60) |
| `HISTORIQUE_DATABASE_URL` | non | Base cible de la génération d'historique pour l'entrepôt |
| `ECHO_HOTES_OUTIL_TESTE` | non | Liste blanche des hôtes que le canal M6 peut appeler |
| `ECHO_CLE_OUTIL_TESTE` | non | Clé partagée du canal M6 et du témoin |
| `ECHO_TEMOIN_TAILLE_MAX_MIO` | non | Plafond d'envoi du témoin (512) |
| `TEST_DATABASE_URL` | tests | Base de test explicite ; sinon dérivée de `DATABASE_URL` avec le suffixe `_test` |

## Authentification

- **Jeton** : JWT (PyJWT) obtenu par `POST /auth/login`, relu côté serveur à chaque appel (un compte désactivé ou dont le mot de passe a changé est refusé).
- **Mots de passe** : hachés avec bcrypt. L'administrateur ne choisit jamais le mot de passe d'un autre : il est **généré** (12 caractères, alphabet de 55 signes sans caractères ambigus), affiché une seule fois, et le compte doit le changer à la première connexion (`doit_changer_mot_de_passe`).
- **Premier administrateur** : `python -m echo.web.auth.bootstrap` (interactif) ou, sans clavier (conteneur), `--creer --email <e-mail> --utilisateur <nom> --nom <nom complet>` avec `ECHO_ADMIN_PASSWORD` dans l'environnement.

## Rôles

| Rôle | Niveau | Accès |
|---|---|---|
| `observateur` | 0 | Toutes les lectures : factures, assurés, KPI, qualité, campagnes (lecture), gouvernance, métriques |
| `operateur` | 1 | + démarrer/arrêter/régler la simulation, commandes d'aléas, génération MDM/entrepôt, rapports, remise à zéro des métriques |
| `administrateur` | 2 | + comptes (`/users`), configuration des anomalies (`/anomalies`), purge des exécutions, suppression des rapports |

`require_role(minimum)` autorise le rôle demandé et tous les rôles supérieurs.

## Mesures de protection en place

| Risque | Mesure |
|---|---|
| Essais de mot de passe répétés | Limiteur en mémoire : 8 échecs / 5 min par identifiant (existant ou non, pour ne pas révéler les comptes), 30 par adresse source. Réponse `429` |
| Énumération de comptes | Un identifiant inconnu est freiné comme un identifiant réel |
| Écoute Socket.IO non autorisée | Jeton vérifié à la connexion, compte relu comme en REST ; CORS partagé avec le REST (`web/app/cors.py`) |
| Fuite de la carte de l'API | `ECHO_DOCS_PUBLIQUES=false` ferme `/docs` et protège `/openapi.json` |
| Traversée de chemin | Le service du dashboard vérifie l'appartenance au dossier `dist` après résolution |
| Appels sortants détournés (SSRF) | Le canal M6 n'appelle que les hôtes de `ECHO_HOTES_OUTIL_TESTE` |
| Envois démesurés au témoin | Plafond de taille |
| Secrets dans l'image | `.env` exclu de l'image (`.containerignore`) ; secrets passés par l'environnement |
| Dépendances | Versions et empreintes figées (`requirements.lock`), vérifiées par `pip-audit` en CI ; code audité par `bandit` |
| Exécution du conteneur | Utilisateur non-root `echo` |

## Limites connues

- **Un seul worker uvicorn** : le limiteur de connexions et plusieurs compteurs sont en mémoire et repartent à zéro au redémarrage. Plusieurs workers demanderaient un stockage partagé.
- Derrière Caddy, l'adresse source n'est exacte que si uvicorn fait confiance à `X-Forwarded-For` (`FORWARDED_ALLOW_IPS`, posé dans `deploiement/compose.prod.yaml`).
- Pour un audit complet avant mise en production, voir [GUIDE_DEPLOIEMENT.md](GUIDE_DEPLOIEMENT.md).
