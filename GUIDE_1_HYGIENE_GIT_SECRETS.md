# GUIDE 1 — Hygiène git & secrets

> **Chantier 1 sur 8** du plan de remise en ordre du projet `simulateur_V5`.
> Prérequis : [GUIDE_0_REMISE_EN_ROUTE.md](./GUIDE_0_REMISE_EN_ROUTE.md) terminé (l'application démarre en local).

---

## Table des matières

- [Contexte : pourquoi ce chantier est le plus urgent](#contexte--pourquoi-ce-chantier-est-le-plus-urgent)
- [La vérité à accepter avant de commencer](#-la-vérité-à-accepter-avant-de-commencer)
- [Partie A — Rotation des secrets](#partie-a--rotation-des-secrets)
- [Partie B — Créer le `.gitignore`](#partie-b--créer-le-gitignore)
- [Partie C — Sortir les fichiers du suivi git](#partie-c--sortir-les-fichiers-du-suivi-git)
- [Partie D — Purger les secrets écrits en dur](#partie-d--purger-les-secrets-écrits-en-dur)
- [Partie E — Valider, pousser, prévenir](#partie-e--valider-pousser-prévenir)
- [Ce qu'on ne fait PAS, et pourquoi](#ce-quon-ne-fait-pas-et-pourquoi)
- [Récapitulatif des fichiers touchés](#récapitulatif-des-fichiers-touchés)
- [Annexe A — Vérifications finales](#annexe-a--vérifications-finales)
- [Annexe B — Décision à valider](#annexe-b--décision-à-valider)

---

## Contexte : pourquoi ce chantier est le plus urgent

### État des lieux constaté

| Constat | Détail |
|---|---|
| `.env` est sur GitHub | Entré à l'historique au commit `0a976cc` — dépôt `charlesemm/simulateur_V5`, **public** |
| Secret JWT exposé | `4e312a61ea72...d460` — permet de **forger un jeton `administrateur`** |
| Mot de passe exposé | `azerty2001`, présent dans **7 fichiers** en plus du `.env` |
| Aucun `.gitignore` | 61 fichiers `.pyc`, 7 fichiers `.idea/` et 2 rapports générés sont suivis |
| Collaborateurs | **Oui** — d'autres personnes ont cloné le dépôt |

### Ce que ça permet concrètement à un attaquant

Le fichier `auth/security.py` signe les jetons JWT avec `JWT_SECRET_KEY`. Cette clé étant publique, n'importe qui peut fabriquer un jeton valide :

```python
# Ce que peut faire un attaquant avec la clé publiée
import jwt
from datetime import datetime, timedelta, timezone

token = jwt.encode(
    {"sub": "attaquant@exemple.com", "role": "administrateur",
     "exp": datetime.now(timezone.utc) + timedelta(hours=8)},
    "4e312a61ea720258bee5837148d30725a00b9e8f2330c591947443d4f730d460",
    algorithm="HS256",
)
```

⚠️ **Ce jeton serait accepté par toute instance de l'API utilisant encore cette clé** — et donnerait un accès `administrateur` complet : gestion des utilisateurs, pilotage du moteur, téléchargement des rapports.

> **Note :** `auth/dependencies.py:38` vérifie ensuite que l'email existe en base et que le compte est actif. Un email inventé serait donc rejeté. Mais un attaquant connaissant **un seul email réel** de la base contourne toute l'authentification sans jamais avoir eu besoin du mot de passe.

---

## ⚠️ La vérité à accepter avant de commencer

**Un secret poussé sur un dépôt public est compromis définitivement.** Réécrire l'historique git ne le « dé-compromet » pas :

- GitHub conserve les commits devenus orphelins, **accessibles par leur SHA**, même après un force-push
- Chaque **fork** garde une copie intégrale de l'historique, hors de ton contrôle
- Des **robots scannent GitHub en continu** ; un secret publié est typiquement indexé en quelques minutes

👉 **La rotation des secrets est le seul vrai correctif.**
Le `.gitignore` empêche la récidive. La réécriture d'historique est du confort — et vu les collaborateurs, son coût dépasse son bénéfice (voir [Ce qu'on ne fait PAS](#ce-quon-ne-fait-pas-et-pourquoi)).

**Ordre impératif : Partie A d'abord.** Les parties B, C et D ne réduisent en rien le risque déjà pris.

---

## Partie A — Rotation des secrets

> 🔴 **Priorité immédiate.** À faire avant toute autre chose.

**Fichier concerné :** `.env`

**À quoi ça sert :** rendre l'ancien secret **inutilisable**. C'est la seule action de ce guide qui neutralise réellement la fuite.

### A.1 — Générer une nouvelle clé JWT

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

**Ce que fait la commande :** `secrets.token_hex(32)` produit 32 octets d'aléa cryptographique (256 bits) rendus en 64 caractères hexadécimaux — même format que l'ancienne clé, mais issue du générateur sécurisé du système d'exploitation.

> **Pourquoi `secrets` et pas `random` ?** Le module `random` est un générateur pseudo-aléatoire prévisible, conçu pour la simulation — c'est d'ailleurs celui qu'utilise `simulation/engine.py`. Le module `secrets` s'appuie sur le CSPRNG du système, seul adapté à un usage cryptographique.

**Copie le résultat**, il sert à l'étape suivante.

### A.2 — Mettre à jour le `.env`

Trois lignes à corriger dans `.env` :

```
JWT_SECRET_KEY=colle_ici_la_cle_generee_en_A1
DATABASE_URL=postgresql+asyncpg://postgres:TON_MOT_DE_PASSE_ACTUEL@localhost:5432/cmu_simulator
POSTGRES_PASSWORD=TON_MOT_DE_PASSE_ACTUEL
```

**Pourquoi corriger aussi `DATABASE_URL` :** la valeur d'origine pointe sur l'hôte `db`, qui est le **nom du service Docker**. Sans Docker, ce nom ne résout pas.

**Ne pas oublier `POSTGRES_PASSWORD`** : `docker-compose.yml:12` porte désormais `${POSTGRES_PASSWORD:?...}`. Si la variable est absente du `.env`, **Docker refusera de démarrer**. C'est le comportement voulu, mais la variable doit exister.

**Conséquence immédiate :** tous les jetons émis avec l'ancienne clé deviennent invalides. Tu devras te reconnecter au dashboard. **C'est exactement l'effet recherché.**

### A.3 — Le mot de passe PostgreSQL

> ⚠️ **Correction du 2026-08-20.** Une version antérieure de ce guide affirmait que la rotation était « déjà effective », en supposant que la nouvelle machine utilisait un autre mot de passe. **C'est faux.**

Le mot de passe PostgreSQL réellement utilisé sur le poste ne différait de celui publié dans le dépôt que par une majuscule initiale — **une telle différence ne protège rien** : c'est la première variante que teste n'importe quel outil de dérivation de mot de passe.

➡️ **La rotation du mot de passe PostgreSQL est donc à faire.**

#### Quel est le risque réel

| Scénario | Risque |
|---|---|
| PostgreSQL local, sur ce poste | 🟢 **Faible** — il écoute sur `localhost`, pas sur Internet. Inatteignable depuis l'extérieur |
| Ce mot de passe réutilisé ailleurs | 🔴 **Élevé** — autre serveur, base de production, autre projet, compte quelconque |

**Le vrai danger, c'est la réutilisation.** Si ce mot de passe ou une variante sert ailleurs, c'est là qu'il faut agir en priorité, avant même le PostgreSQL local.

#### Procédure de rotation

**1. Générer un mot de passe solide**

```powershell
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

> `token_urlsafe` ne produit que des caractères sûrs pour une URL — ni `@`, ni `:`, ni `/`, qui casseraient `DATABASE_URL`.

**2. Changer le mot de passe dans PostgreSQL**

```powershell
psql -U postgres -h localhost -c "ALTER USER postgres WITH PASSWORD 'colle_ici_le_nouveau';"
```

Attendu : `ALTER ROLE`

**3. Mettre à jour la session courante**

```powershell
$env:PGPASSWORD = 'colle_ici_le_nouveau'
```

```powershell
$mdp = 'colle_ici_le_nouveau'
$env:DATABASE_URL = "postgresql+asyncpg://postgres:$([uri]::EscapeDataString($mdp))@localhost:5432/cmu_simulator"
```

**4. Vérifier**

```powershell
psql -U postgres -h localhost -d cmu_simulator -c "SELECT count(*) FROM \"TB_REF_ASSURES\";"
```

Attendu : **100000**

**5. Mettre à jour le `.env`**

```
DATABASE_URL=postgresql+asyncpg://postgres:LE_NOUVEAU@localhost:5432/cmu_simulator
POSTGRES_PASSWORD=LE_NOUVEAU
```

**6. Mettre à jour le rituel de démarrage quotidien** consigné en fin de [GUIDE_0_REMISE_EN_ROUTE.md](./GUIDE_0_REMISE_EN_ROUTE.md) — il contient l'ancien mot de passe.

---

## Partie B — Créer le `.gitignore`

**Fichier à créer :** `.gitignore` (à la racine du projet)

**À quoi ça sert :** empêcher que `.env`, les caches Python, les modules Node, la configuration PyCharm et les rapports générés soient à nouveau ajoutés au dépôt. Sans ce fichier, un simple `git add .` remet tout — c'est précisément ce qui s'est produit.

**Contenu complet :**

```gitignore
# ── Secrets & configuration locale ──────────────────────────────────────────
.env
.env.local
.env.*.local

# ── Python ──────────────────────────────────────────────────────────────────
__pycache__/
*.py[cod]
*$py.class
*.so
.venv/
venv/
env/
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/
dist/
build/

# ── Node / Frontend ─────────────────────────────────────────────────────────
node_modules/
dashboard/dist/
dashboard/.vite/
npm-debug.log*
yarn-error.log*

# ── IDE ─────────────────────────────────────────────────────────────────────
.idea/
.vscode/
*.swp

# ── Rapports générés à l'exécution ──────────────────────────────────────────
reports/output/

# ── Système ─────────────────────────────────────────────────────────────────
Thumbs.db
desktop.ini
.DS_Store
```

### Points d'attention

| Règle | Pourquoi |
|---|---|
| `.env` | Ne correspond **qu'au** fichier nommé exactement `.env`. **`.env.exemple` reste donc suivi** — et c'est voulu : sans secret réel, il documente les variables attendues. |
| `reports/output/` | Le dossier est recréé automatiquement au démarrage par `reports/paths.py:5` (`OUTPUT_DIR.mkdir(parents=True, exist_ok=True)`). Aucun risque à l'ignorer. |
| `.venv/` | Déjà non suivi aujourd'hui, mais la règle protège d'un ajout accidentel — c'est le plus gros dossier du projet. |
| `.idea/` | Configuration PyCharm, propre à ta machine. Elle n'a pas sa place dans un dépôt partagé. |

---

## Partie C — Sortir les fichiers du suivi git

**Fichiers concernés :** aucun fichier n'est *modifié* — on agit sur **l'index git**.

**À quoi ça sert :** le `.gitignore` n'agit **que sur les fichiers non encore suivis**. Un fichier déjà présent dans l'index git y reste, même s'il correspond à une règle d'exclusion. Il faut donc purger l'index et le reconstruire.

### C.1 — Réinitialiser l'index

```powershell
git rm -r --cached . --quiet
```

> 🔴 **Le drapeau `--cached` est vital.**
> Il retire les fichiers de **l'index git uniquement**. **Rien n'est supprimé de ton disque.**
> Sans `--cached`, cette commande effacerait l'intégralité du projet.

```powershell
git add .
```

**Ce qui se passe :** `git add .` réajoute tout le contenu du dossier, mais cette fois **en appliquant le `.gitignore`**. Les fichiers ignorés ne reviennent pas dans l'index.

### C.2 — Contrôler avant de valider

```powershell
git status
```

Tu verras une longue liste de `deleted:`. **Ce sont des suppressions d'index, pas de disque.** Vérifie que la liste contient bien :

| Attendu en `deleted:` | Nombre approximatif |
|---|---|
| `.env` | 1 |
| `__pycache__/*.pyc` | ~61 |
| `.idea/*` | 7 |
| `reports/output/*` | 2 |
| `.gitignore` en `new file:` | 1 |

> 🛑 **Si tu vois du code source Python ou TypeScript en `deleted:`, arrête-toi.**
> Cela signifierait qu'une règle du `.gitignore` est trop large. Ne valide pas, et signale-le.

### C.3 — Vérifications ciblées

Confirme que `.env` n'est plus suivi :

```powershell
git ls-files | Select-String -Pattern "^\.env$"
```

**Aucune sortie = correct.**

Confirme que le fichier est **toujours sur ton disque** :

```powershell
Test-Path .env
```

**Doit répondre `True`.** Si c'est `False`, tu as oublié `--cached` — préviens-moi immédiatement, on récupère le fichier depuis git.

---

## Partie D — Purger les secrets écrits en dur

Le `.env` est neutralisé, mais `azerty2001` et la clé de développement subsistent dans **7 fichiers**.

**Principe directeur : le *fail fast*.** Plutôt qu'une valeur par défaut qui laisse l'application démarrer silencieusement dans une mauvaise configuration, on veut une **erreur immédiate et explicite**.

### D.1 — `app/database.py` *(lignes 10 à 13)*

**Remplace :**

```python
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:azerty2001@localhost:5432/cmu_simulator",
)
```

**Par :**

```python
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "La variable d'environnement DATABASE_URL est obligatoire. "
        "Exemple : postgresql+asyncpg://postgres:<mot_de_passe>@localhost:5432/cmu_simulator"
    )
```

**Pourquoi supprimer le défaut :** une valeur par défaut fait croire que tout va bien alors que l'application se connecte à la mauvaise base — ou échoue plus tard, avec un message incompréhensible. Une erreur immédiate et nommée coûte trente secondes ; un diagnostic tardif coûte une heure.

### D.2 — `auth/security.py` *(ligne 12)*

**Remplace :**

```python
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-change-me-en-production")
```

**Par :**

```python
SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "La variable d'environnement JWT_SECRET_KEY est obligatoire. "
        "Génère-la avec : python -c \"import secrets; print(secrets.token_hex(32))\""
    )
```

> 🔴 **C'est la plus importante des sept modifications.**
> Avec un défaut, une mise en production où l'on oublie la variable **démarre sans la moindre erreur**, avec une clé publiquement connue. N'importe qui peut alors forger un jeton `administrateur`. C'est exactement le scénario à rendre structurellement impossible.

### D.3 — `alembic.ini` *(ligne 7)*

**Remplace :**

```ini
sqlalchemy.url = postgresql+asyncpg://postgres:azerty2001@localhost:5432/cmu_simulator
```

**Par :**

```ini
sqlalchemy.url = postgresql+asyncpg://postgres:CHANGEME@localhost:5432/cmu_simulator
```

**Pourquoi une valeur bidon suffit :** `alembic/env.py:19` écrase systématiquement cette URL par `DATABASE_URL` dès que la variable existe. Cette ligne n'est qu'un gabarit — elle ne doit jamais contenir un vrai mot de passe.

### D.4 — `docker-compose.yml` *(lignes 12, 41, 42)*

**Ligne 12 — remplace :**

```yaml
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-azerty2001}
```

**par :**

```yaml
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD est obligatoire dans le .env}
```

**Ligne 41 — remplace :**

```yaml
      DATABASE_URL: ${DATABASE_URL:-postgresql+asyncpg://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-azerty2001}@db:5432/${POSTGRES_DB:-cmu_simulator}}
```

**par :**

```yaml
      DATABASE_URL: ${DATABASE_URL:?DATABASE_URL est obligatoire dans le .env}
```

**Ligne 42 — remplace :**

```yaml
      JWT_SECRET_KEY: ${JWT_SECRET_KEY:-dev-secret-change-me-en-production}
```

**par :**

```yaml
      JWT_SECRET_KEY: ${JWT_SECRET_KEY:?JWT_SECRET_KEY est obligatoire dans le .env}
```

> **La syntaxe `${VAR:?message}`** est propre à Docker Compose : si `VAR` est absente ou vide, Compose **refuse de démarrer** et affiche ton message. C'est l'équivalent Compose du *fail fast* de D.1 et D.2.
>
> À noter : la ligne 41 d'origine contient une accolade fermante en trop (`...cmu_simulator}}`) — le remplacement corrige ce bug au passage.

### D.5 — `setup_db.sh` *(ligne 12)*

**Remplace :**

```bash
DB_PASSWORD="${POSTGRES_PASSWORD:-azerty2001}"
```

**Par :**

```bash
DB_PASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD est obligatoire}"
```

> La syntaxe `${VAR:?message}` existe aussi en Bash, avec la même sémantique : le script s'arrête avec le message si la variable est vide.

### D.6 — `README.md` *(lignes 12 et 41)*

**Ligne 41 — remplace :**

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://postgres:azerty2001@localhost:5432/cmu_simulator"
```

**par :**

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://postgres:VOTRE_MOT_DE_PASSE@localhost:5432/cmu_simulator"
```

**Ligne 12 — bonus, un nom de fichier erroné.** Remplace :

```powershell
copy .env.example .env
```

**par :**

```powershell
copy .env.exemple .env
```

**Pourquoi :** le fichier du dépôt s'appelle `.env.exemple` (orthographe française). La commande du README échoue donc telle quelle.

### D.7 — `GUIDE_0_REMISE_EN_ROUTE.md` *(lignes 128 et 136)*

Ton guide cite `azerty2001` à titre d'illustration. Ce n'est plus un secret vivant, mais autant le neutraliser : remplace les deux occurrences par `ancien_mot_de_passe`.

### D.8 — Vérifier qu'il ne reste rien

```powershell
git grep -n "azerty2001"
```

```powershell
git grep -n "dev-secret-change-me"
```

**Occurrences tolérées** pour `dev-secret-change-me` :

| Fichier | Statut |
|---|---|
| `ETAPE_7_GUIDE_COMPLET.md` | Documentation pédagogique — cite l'ancien code, sans danger |
| `GUIDE_DOCKER_CICD_PRODUCTION.md` | Idem |
| `docker-compse.yml` | ⚠️ Fichier en doublon (faute de frappe) — **supprimé au chantier 2** |

Pour `azerty2001`, l'objectif est **zéro occurrence**.

---

## Partie E — Valider, pousser, prévenir

### E.1 — Vérifier que l'application démarre toujours

Les modifications D.1 et D.2 rendent deux variables **obligatoires**. Teste **avant** de pousser :

```powershell
python -c "import app.database, auth.security; print('Configuration OK')"
```

| Résultat | Signification |
|---|---|
| ✅ `Configuration OK` | Tes variables de session sont bien définies |
| ❌ `RuntimeError: La variable ... est obligatoire` | **C'est le comportement voulu** — redéfinis `DATABASE_URL` et `JWT_SECRET_KEY` dans la session |

Puis un test réel de bout en bout :

```powershell
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Vérifie <http://127.0.0.1:8000/health>, puis `Ctrl+C`.

### E.2 — Commit

```powershell
git add .
```

```powershell
git commit -m "securite: retire .env du suivi, ajoute .gitignore, supprime les secrets en dur"
```

```powershell
git push origin main
```

### E.3 — Prévenir les collaborateurs *(obligatoire)*

D'autres personnes ont cloné le dépôt. Après ton push, il leur faut :

1. **Considérer `azerty2001` et l'ancienne clé JWT comme morts** — et les changer partout où ils les auraient réutilisés.
2. **Créer leur propre `.env` local** à partir de `.env.exemple`, avec leurs propres valeurs.
3. **Définir `DATABASE_URL` et `JWT_SECRET_KEY`** — sinon l'application refusera de démarrer (D.1 et D.2). Ce n'est pas une régression, c'est le nouveau comportement voulu.

> ⚠️ Après ton push, `git pull` **ne recréera pas** leur `.env` (il n'est plus suivi). Leur `.env` local existant reste intact sur leur disque — mais il contient les anciens secrets. Ils doivent le mettre à jour eux-mêmes.

### E.4 — Hygiène GitHub

Deux actions dans l'interface web du dépôt, à faire toi-même :

| Action | Où | Effet |
|---|---|---|
| **Activer le *secret scanning*** | Settings → Code security & analysis | GitHub t'alerte automatiquement si un secret est repoussé |
| **Envisager de passer le dépôt en privé** | Settings → General → Danger Zone | Réduit l'exposition future. ⚠️ Ne supprime **pas** ce qui est déjà indexé, et coupe l'accès à d'éventuels collaborateurs externes |

---

## Ce qu'on ne fait PAS, et pourquoi

**On ne réécrit pas l'historique git** — ni `git filter-repo`, ni BFG, ni force-push.

| Raison | Détail |
|---|---|
| **Efficacité nulle** | Le dépôt est public depuis le commit `0a976cc`. Le secret est déjà indexé par des tiers ; le retirer maintenant ne le reprend à personne |
| **Coût élevé** | Un force-push casse le clone de **chacun** de tes collaborateurs, qui doivent alors re-cloner |
| **Résidus** | Les forks et les commits orphelins accessibles par leur SHA survivent au nettoyage |

**La rotation de la partie A rend l'ancien secret inutilisable. C'est ce qui compte.**

> Si tu veux malgré tout nettoyer l'historique plus tard, c'est faisable — mais ça se planifie **avec** tes collaborateurs, et **après** la rotation. Un guide dédié sera rédigé sur demande.

---

## Récapitulatif des fichiers touchés

| Partie | Fichier | Nature | Priorité |
|---|---|---|---|
| **A** | `.env` | Modifié — nouveaux secrets | 🔴 immédiat |
| **B** | `.gitignore` | **Créé** | 🟠 |
| **C** | *(index git seul)* | Aucun fichier modifié | 🟠 |
| **D.1** | `app/database.py` | Modifié — *fail fast* | 🟠 |
| **D.2** | `auth/security.py` | Modifié — *fail fast* | 🔴 |
| **D.3** | `alembic.ini` | Modifié — gabarit neutre | 🟠 |
| **D.4** | `docker-compose.yml` | Modifié — 3 lignes | 🟠 |
| **D.5** | `setup_db.sh` | Modifié — 1 ligne | 🟡 |
| **D.6** | `README.md` | Modifié — 2 lignes | 🟡 |
| **D.7** | `GUIDE_0_REMISE_EN_ROUTE.md` | Modifié — 2 lignes | 🟡 |
| **E** | — | Push & communication | 🟡 |

---

## Annexe A — Vérifications finales

Une fois tout terminé, cette séquence valide le chantier :

```powershell
git grep -n "azerty2001"
```
→ **aucune sortie**

```powershell
git ls-files | Select-String -Pattern "^\.env$"
```
→ **aucune sortie**

```powershell
Test-Path .env
```
→ **`True`**

```powershell
git ls-files | Select-String -Pattern "__pycache__" | Measure-Object -Line
```
→ **0**

```powershell
git ls-files | Measure-Object -Line
```
→ environ **127** fichiers (contre 197 avant)

```powershell
python -c "import app.database, auth.security; print('Configuration OK')"
```
→ **`Configuration OK`**

---

## Annexe B — Décision à valider

Les modifications **D.1** et **D.2** changent le comportement de l'application :

| Avant | Après |
|---|---|
| Sans `DATABASE_URL`, l'app se connectait à une base par défaut | Sans `DATABASE_URL`, l'app **refuse de démarrer** |
| Sans `JWT_SECRET_KEY`, l'app signait avec une clé publique connue | Sans `JWT_SECRET_KEY`, l'app **refuse de démarrer** |

**C'est plus sûr, mais plus strict.** Concrètement :

- ✅ Impossible de déployer en production avec une clé de développement
- ✅ Impossible de se tromper de base sans s'en apercevoir
- ⚠️ Chaque terminal de développement doit définir les deux variables (déjà le cas — voir le rituel de démarrage du GUIDE 0)
- ⚠️ Tes collaborateurs devront s'adapter (voir E.3)

**Alternative possible si tu préfères moins strict :** conserver un défaut pour `DATABASE_URL` **sans mot de passe** (`postgresql+asyncpg://postgres@localhost:5432/cmu_simulator`) et n'appliquer le *fail fast* qu'à `JWT_SECRET_KEY`, qui est le seul enjeu de sécurité réel.

> **Ce point reste à trancher avant d'appliquer la partie D.**

---

## Suite du plan

| Chantier | Objet |
|---|---|
| ~~0~~ | ~~Remise en route sur la nouvelle machine~~ ✅ |
| **1** | **Hygiène git & secrets** ← *ce guide* |
| 2 | Nettoyage des doublons (`docker-compse.yml`, `run()` dupliqué, imports morts) |
| 3 | Réparer Docker (`Dockerfile`, `COPY alembic/`, CORS Socket.IO) |
| 4 | Sécuriser les endpoints non protégés |
| 5 | Brancher les anomalies sur le moteur (ou corriger la doc) |
| 6 | Performance des KPI (agrégations SQL) |
| 7 | Tests automatisés (pytest + CI) |
| 8 | Figer la migration `0001` en SQL explicite |
