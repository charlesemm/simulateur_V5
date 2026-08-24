# Déployer ÉCHO avec Podman

Ce guide suppose que **Podman** et **podman-compose** sont installés.
Les commandes fonctionnent aussi avec Docker — remplacer `podman` par `docker`.

---

## 1. Prérequis

| Outil | Version minimum | Vérification |
|---|---|---|
| Podman | 4.0+ | `podman --version` |
| podman-compose | 1.0+ | `podman-compose --version` |
| Git | 2.30+ | `git --version` |

Sur Fedora/RHEL :
```bash
sudo dnf install podman podman-compose
```

Sur Ubuntu/Debian :
```bash
sudo apt install podman
pip install podman-compose
```

Sur Windows (avec Podman Desktop) :
```powershell
winget install RedHat.Podman-Desktop
```

---

## 2. Configuration

Créer un fichier `.env` à la racine du projet :

```bash
# Mot de passe PostgreSQL (obligatoire en production)
POSTGRES_PASSWORD=un_vrai_mot_de_passe_ici

# Mot de passe du premier compte administrateur
ECHO_ADMIN_PASSWORD=MotDePasseAdmin1
```

> **Ne jamais committer le `.env`** — il est déjà dans le `.gitignore`.

---

## 3. Lancement

### Tout construire et démarrer

```bash
podman-compose up --build -d
```

Cette commande :
1. Construit l'image ÉCHO (dashboard + API)
2. Démarre PostgreSQL
3. Exécute les migrations Alembic
4. Lance l'API sur le port 8000

### Vérifier que tout tourne

```bash
podman-compose ps
```

Les trois services doivent apparaître :
- `postgres` : **running**
- `api` : **running**
- `migrations` : **exited (0)** — c'est normal, il s'exécute une fois puis s'arrête

### Tester l'API

```bash
curl http://localhost:8000/health
```

Réponse attendue :
```json
{"status": "ok"}
```

---

## 4. Créer le premier administrateur

Au premier lancement, la base est vide. Créer un compte :

```bash
podman-compose exec api python -m auth.bootstrap \
  --email admin@cnam.ci \
  --utilisateur admin \
  --mot-de-passe "$ECHO_ADMIN_PASSWORD"
```

---

## 5. Accéder au dashboard

Le dashboard est accessible à : **http://localhost:8000**

> En développement local, Vite tourne séparément (`npm run dev` dans `dashboard/`).
> En conteneur, le dashboard compilé est servi directement par l'API.

Pour servir le dashboard compilé, il faut configurer FastAPI pour servir les
fichiers statiques de `dashboard/dist/`. En attendant, le dashboard en
développement pointe vers `http://localhost:8000` pour l'API.

---

## 6. Commandes utiles

### Voir les logs

```bash
# Tous les services
podman-compose logs -f

# Seulement l'API
podman-compose logs -f api

# Seulement PostgreSQL
podman-compose logs -f postgres
```

### Relancer les migrations

```bash
podman-compose run --rm migrations
```

### Peupler la base (seed)

```bash
podman-compose exec api python -m seed
```

### Arrêter

```bash
podman-compose down
```

### Arrêter et supprimer les données

```bash
podman-compose down -v
```

> ⚠️ `-v` supprime les volumes PostgreSQL et les rapports. Irréversible.

### Reconstruire après modification du code

```bash
podman-compose build --no-cache api
podman-compose up -d api
```

---

## 7. Volumes

| Volume | Contenu | Monté dans |
|---|---|---|
| `pgdata` | Données PostgreSQL | `/var/lib/postgresql/data` |
| `rapports` | PDF, Excel et CSV générés | `/app/reports/output` |

Pour extraire un rapport du conteneur :

```bash
podman cp $(podman-compose ps -q api):/app/reports/output/. ./rapports_locaux/
```

---

## 8. Variables d'environnement

| Variable | Obligatoire | Défaut | Description |
|---|---|---|---|
| `DATABASE_URL` | Oui | — | Chaîne de connexion PostgreSQL |
| `POSTGRES_PASSWORD` | Oui | `echo_dev_2026` | Mot de passe PostgreSQL |
| `ECHO_ADMIN_PASSWORD` | Non | `MotDePasseAdmin1` | Mot de passe du premier admin |
| `CORS_ORIGIN_REGEX` | Non | — | Regex des origines autorisées |
| `JWT_SECRET` | Recommandé | généré au démarrage | Clé de signature des jetons |
| `TAUX_COUVERTURE` | Non | `0.85` | Part des assurés avec droits ouverts |

---

## 9. Production

En production, quelques ajustements :

1. **Changer tous les mots de passe** dans le `.env`
2. **Générer un `JWT_SECRET` solide** :
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
3. **Ne pas exposer PostgreSQL** : retirer le `ports: "5432:5432"` du compose
4. **Placer un reverse proxy** (Nginx, Caddy, Traefik) devant le port 8000 pour le TLS
5. **Limiter les ressources** :
   ```yaml
   # Dans compose.yaml, sous le service api :
   deploy:
     resources:
       limits:
         memory: 512M
         cpus: "1.0"
   ```

---

## 10. Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| `api` redémarre en boucle | PostgreSQL pas encore prêt | Vérifier `podman-compose logs postgres` |
| `connection refused` sur 5432 | Le conteneur postgres n'a pas démarré | `podman-compose up -d postgres` puis attendre le healthcheck |
| Migrations échouent | Base déjà à jour ou conflit | `podman-compose run --rm migrations python -m alembic current` |
| Permission denied sur reports/output | Droits du volume | `podman-compose exec api chown -R echo:echo /app/reports/output` |
| Image trop grosse | Cache de build | `podman system prune` puis rebuild |
