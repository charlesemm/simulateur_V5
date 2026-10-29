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
# Clé de signature des jetons — OBLIGATOIRE, l'API refuse de démarrer sans.
# Le .env du dépôt n'entre pas dans l'image : cette valeur doit venir d'ici.
JWT_SECRET_KEY=collez_ici_le_resultat_de_la_commande_ci_dessous

# Mot de passe PostgreSQL (obligatoire en production)
POSTGRES_PASSWORD=un_vrai_mot_de_passe_ici

# Mot de passe du premier compte administrateur
ECHO_ADMIN_PASSWORD=MotDePasseAdmin1
```

Générez la clé :

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> Changer cette clé plus tard invalide toutes les sessions ouvertes : chacun
> devra se reconnecter. Ce n'est pas grave, mais il vaut mieux le savoir.

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

Au premier lancement, la base est vide : **aucun compte n'existe et personne ne
peut se connecter**. Cette étape n'est pas optionnelle.

```bash
podman-compose exec api python -m auth.bootstrap --creer \
  --email admin@cnam.ci \
  --utilisateur admin \
  --nom "Administrateur ÉCHO"
```

Le mot de passe n'est **pas** passé en argument : la commande lit
`ECHO_ADMIN_PASSWORD`, déjà transmise au conteneur par le compose. Il ne se
retrouve ainsi ni dans l'historique du terminal, ni dans la liste des
processus de la machine.

La commande est **sans risque à relancer** : si le compte existe déjà, elle le
dit et ne touche à rien.

### Vérifier, ou repartir d'un mot de passe oublié

```bash
podman-compose exec api python -m auth.bootstrap --lister
```

`--reinitialiser` redonne un mot de passe à un compte et le réactive au
passage — c'est la porte de secours si le dernier administrateur se retrouve
désactivé. Elle pose ses questions au clavier, donc lancez-la avec `-it` :

```bash
podman-compose exec -it api python -m auth.bootstrap --reinitialiser
```

---

## 5. Accéder au dashboard

Le dashboard est accessible à : **http://localhost:8000**

L'image embarque le dashboard compilé et l'API le sert lui-même : une seule
adresse, un seul port, pas de serveur web supplémentaire à tenir.

| Adresse | Sert |
|---|---|
| `/` et toute route d'écran | Le tableau de bord |
| `/docs` | La documentation de l'API |
| `/health` | L'état du processus |
| `/socket.io` | Le flux temps réel |

Les routes de l'API sont déclarées avant le rattrapage qui rend le dashboard :
elles gardent donc la main, et seules les adresses inconnues de l'API
retombent sur l'interface.

> En développement local, ce dossier `dashboard/dist` n'existe pas : Vite sert
> l'interface sur son propre port (`npm run dev` dans `dashboard/`) et la
> racine de l'API affiche alors un message d'orientation.

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
| `ECHO_ADMIN_PASSWORD` | Oui, pour créer le 1er compte | `MotDePasseAdmin1` | Lu par `auth.bootstrap --creer` (8 caractères minimum) |
| `CORS_ORIGIN_REGEX` | Non | — | Regex des origines autorisées |
| `JWT_SECRET_KEY` | **Oui** | aucun — l'API refuse de démarrer sans | Clé de signature des jetons |
| `TAUX_COUVERTURE` | Non | `0.60` | Part des assurés avec droits ouverts (lue au *seed*) |

---

## 9. Production

En production, quelques ajustements :

1. **Changer tous les mots de passe** dans le `.env`
2. **Générer un `JWT_SECRET_KEY` solide** :
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
3. **PostgreSQL n'est déjà plus exposé** : aucun port publié, la base n'est
   jointe que par les autres conteneurs. Pour l'inspecter :
   `podman-compose exec postgres psql -U echo -d echo_db`
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
