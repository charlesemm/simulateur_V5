# ÉCHO — Guide du pipeline CI/CD

> Ce que la machine fait à ta place à chaque fois que tu pousses du code,
> pourquoi elle le fait, et quoi regarder quand elle affiche du rouge.
>
> Le pipeline tient dans un seul fichier : [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

---

## 1. À quoi ça sert

Sans pipeline, c'est toi qui dois te souvenir, à chaque modification, de
relancer les tests, de refaire le build du dashboard et de vérifier que l'API
démarre encore. Le jour où tu es pressé, tu sautes une étape — et le dépôt se
retrouve avec du code cassé sans que personne ne s'en aperçoive avant des
semaines.

Le pipeline refait ces vérifications **systématiquement**, sur une machine
neuve, et te dit en cinq minutes si quelque chose est cassé. Puis, si tout est
vert, il fabrique l'image prête à installer.

Deux mots de vocabulaire, parce qu'ils reviennent partout :

- **CI** (intégration continue) — on vérifie. Tests, compilation, migrations.
- **CD** (déploiement continu) — on livre. Ici : on publie une image.

---

## 2. Le vocabulaire GitHub, si tu viens de GitLab

Le principe est le même, seuls les mots changent :

| GitLab | GitHub | Ce que c'est |
|---|---|---|
| `.gitlab-ci.yml` (un seul) | `.github/workflows/*.yml` (autant qu'on veut) | Le fichier de recette |
| *pipeline* | *workflow* | L'ensemble déclenché par un push |
| *stage* | *job* | Un chantier, sur sa propre machine |
| *job* | *step* | Une étape dans un chantier |
| *runner* | *runner* | La machine qui exécute |
| Settings → CI/CD → Variables | Settings → Secrets and variables → Actions | Les secrets |
| tu écris tes commandes | `uses:` réutilise une action publiée | Les briques toutes faites |

La grande différence pratique : sur GitHub, `uses:` te donne accès à des
briques écrites et maintenues par d'autres. Le pipeline en utilise cinq
(`checkout`, `setup-python`, `setup-node`, `login-action`, `build-push-action`),
ce qui évite d'écrire à la main l'installation de Python ou la connexion à
l'entrepôt d'images.

---

## 3. Ce que fait le pipeline, chantier par chantier

Le pipeline a **trois chantiers**. Les deux premiers partent en même temps, sur
deux machines différentes ; le troisième attend que les deux soient verts.

```
        push
          │
    ┌─────┴─────┐
    ▼           ▼
 backend    frontend        ← en parallèle, ~5 min
    │           │
    └─────┬─────┘
          ▼
        image               ← seulement si les deux sont verts
          │
          ▼
      ghcr.io
```

### Chantier `backend`

GitHub loue une machine Ubuntu neuve et y démarre **un vrai PostgreSQL 16** à
côté. Puis, dans l'ordre :

1. **Compilation Python** — attrape les fautes de frappe et les imports cassés.
2. **Migrations Alembic sur une base vierge** — c'est l'étape la plus précieuse.
   Ta base de travail a accumulé l'historique des migrations ; ici, elles
   repartent de zéro. Une migration qui ne marche que « parce que la table
   existait déjà chez toi » est démasquée ici.
3. **Création de la base de test**, puis **`pytest`** — toute la suite.
4. **Smoke test** — l'API est réellement démarrée, et le pipeline appelle
   `/health`. Si elle ne répond pas en 30 secondes, échec. Un projet peut très
   bien compiler, passer ses tests, et refuser de démarrer.

### Chantier `frontend`

Installation npm, lint, puis build de production du dashboard.

> **Point d'attention** : `npm ci` y utilise `--legacy-peer-deps`, comme dans le
> [Containerfile](Containerfile). Sans cet alignement, la CI passerait au vert
> sur un projet dont l'image refuse de se construire — le pire des cas, parce
> que tu ne l'apprendrais qu'au déploiement.

### Chantier `image` (le CD)

Ne démarre **que** si les deux précédents sont verts, et **seulement** sur
`main` ou sur un tag de version. Une pull request ne publie jamais rien : elle
propose du code, elle ne le livre pas.

Il construit l'image du `Containerfile` — les trois étages : dashboard React,
dépendances Python, image finale — et l'envoie sur **GHCR**, l'entrepôt
d'images intégré à GitHub, à l'adresse `ghcr.io/charlesemm/simulateur_v5`.

---

## 4. Les étiquettes de l'image, et laquelle utiliser

Une même image reçoit plusieurs noms selon ce qui a déclenché le pipeline :

| Étiquette | Quand | À quoi elle sert |
|---|---|---|
| `latest` | poussée sur `main` | La dernière version en date. **Bouge en permanence.** |
| `sha-a1b2c3…` | à chaque fois | Désigne **le commit exact**. Ne bouge jamais. |
| `1.2.3` | tag `v1.2.3` | Une version figée. |
| `1.2` | tag `v1.2.3` | Suit les correctifs de la 1.2 sans figer le numéro. |

**La règle à retenir** : `latest` pour essayer, `sha-…` ou un numéro de version
pour dire « la machine tourne sur celle-ci ». `latest` ne répond jamais à la
question « quelle version est installée ? », puisque la réponse change chaque
jour.

Récupérer une image :

```bash
podman pull ghcr.io/charlesemm/simulateur_v5:latest
```

L'adresse exacte s'affiche aussi en clair sur la page de l'exécution, dans le
récapitulatif — pas besoin de fouiller les journaux.

---

## 5. À faire une fois, avant la première publication

Deux réglages sur GitHub, à vérifier **avant** de pousser :

**a. Autoriser le pipeline à publier**

`Settings` → `Actions` → `General` → *Workflow permissions*. Si l'option est sur
« Read repository contents permission », le job `image` échouera en **403**. Le
workflow demande explicitement le droit `packages: write`, ce qui suffit sur un
compte personnel ; si le 403 persiste, c'est ce réglage qu'il faut ouvrir.

**b. Rendre l'image lisible (facultatif)**

Une image publiée est **privée** par défaut. Pour la tirer depuis un autre poste
sans s'authentifier, il faut la passer en public : page du dépôt → `Packages` →
le paquet → `Package settings` → *Change visibility*. À ne faire que si le code
n'est pas sensible.

---

## 6. Ce qu'il faut savoir quand ça devient rouge

| Symptôme | Cause la plus probable |
|---|---|
| `backend` échoue sur les migrations | Une migration suppose un état que la base vierge n'a pas |
| `backend` échoue sur `pytest` | Un test cassé — le journal donne lequel, en clair |
| `backend` échoue sur le smoke test | L'API ne démarre plus : import cassé, variable manquante |
| `frontend` échoue sur le lint | Une règle ESLint — c'est le motif le plus fréquent |
| `image` échoue en 403 | Le réglage de la section 5.a |
| `image` échoue sur un nom invalide | Une majuscule dans le nom : GHCR n'accepte que les minuscules |

Le pipeline s'arrête au premier échec d'un chantier. Les autres continuent :
`backend` et `frontend` sont indépendants, donc un lint cassé ne t'empêche pas
de voir si les tests passent.

---

## 7. Le déploiement (`deploy.yml`)

Un quatrième chantier existe, dans un fichier séparé :
[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml). Il pose sur
`srv-gouv` l'image que `ci.yml` a publiée — la même routine que
GUIDE_EXPLOITATION.md §2.1 (sauvegarde, migrations, puis API), en SSH.

**Déclenchement volontairement manuel.** Contrairement à `ci.yml`, ce
chantier ne part jamais tout seul sur une poussée : `srv-gouv` est une
machine partagée avec Socle, et lancer une migration sans personne pour
surveiller le résultat est justement ce que le guide d'exploitation met en
garde d'éviter. Pour le déclencher : onglet **Actions** du dépôt →
*Déploiement — srv-gouv* → **Run workflow**. Un champ optionnel permet de
choisir un repère d'image précis (`sha-a1b2c3d`) ; laissé vide, c'est le
commit sélectionné pour ce lancement qui est utilisé.

### Mise en service — à faire une fois, avant le premier déploiement

**a. Un compte SSH dédié sur `srv-gouv`**, plutôt que de prêter un compte
personnel au pipeline :

```bash
sudo useradd -m -s /bin/bash echo-deploy
sudo -u echo-deploy ssh-keygen -t ed25519 -f /home/echo-deploy/.ssh/id_ed25519 -N ""
sudo -u echo-deploy sh -c 'cat /home/echo-deploy/.ssh/id_ed25519.pub >> /home/echo-deploy/.ssh/authorized_keys'
sudo cat /home/echo-deploy/.ssh/id_ed25519          # à copier dans le secret GitHub, puis à effacer de l'écran
```

**b. Un `sudo` limité aux commandes utilisées par le workflow** — jamais un
`sudo` général sur une machine qui héberge aussi Socle :

```bash
sudo visudo -f /etc/sudoers.d/echo-deploy
```

```
echo-deploy ALL=(root) NOPASSWD: /opt/echo/sauvegarde.sh, \
  /usr/bin/podman-compose -f /opt/echo/compose.prod.yaml *, \
  /usr/bin/podman inspect echo_migrations_1 *, \
  /usr/bin/podman logs --tail 60 echo_migrations_1
```

> Le motif exact des chemins (`podman-compose`, `podman`) dépend de
> l'installation — vérifier avec `which podman-compose podman` avant de
> l'écrire. `visudo` valide la syntaxe avant d'enregistrer ; une erreur ici
> casserait `sudo` pour tout le monde sur la machine.

**c. Donner à `echo-deploy` le droit de modifier `/opt/echo/.env`** (le
workflow y écrit le nouveau repère d'image sans `sudo`, volontairement — un
secret ne doit transiter par `sudo` que si rien d'autre ne marche) :

```bash
sudo chgrp echo-deploy /opt/echo/.env /opt/echo
sudo chmod 660 /opt/echo/.env
```

**d. Trois secrets** dans `Settings` → `Secrets and variables` → `Actions` :

| Secret | Valeur |
|---|---|
| `SRV_GOUV_HOST` | `srv-gouv.ipscnam.ci` (ou son adresse IP) |
| `SRV_GOUV_USER` | `echo-deploy` |
| `SRV_GOUV_SSH_KEY` | La clé **privée** générée à l'étape a, entière, en-têtes `-----BEGIN...-----`/`-----END...-----` compris |

**e. (Optionnel mais recommandé) Une approbation humaine** avant chaque
déploiement : `Settings` → `Environments` → `New environment` → nommer
`production` → activer *Required reviewers* et s'y ajouter. Le workflow
déclare déjà `environment: production` ; sans cette configuration, la ligne
ne fait rien et le déploiement part dès le clic sur *Run workflow*.

### Ce que ce chantier ne fait toujours pas

Il touche `.env`, les migrations et le conteneur `api` — jamais nginx ni le
certificat, volontairement : ce sont les points où une erreur couperait
aussi Socle (GUIDE_EXPLOITATION.md §2.3), et ils changent rarement. Ces
gestes restent manuels.

**Autre écart connu, sans gravité mais bon à savoir** : la CI teste sur Python
3.12, alors que le `Containerfile` et ton poste utilisent 3.14. Les tests
valident donc une version que rien ne fait tourner en vrai. À aligner un jour.

---

## 8. Le coût

Sur un dépôt **public**, les exécutions sont gratuites et illimitées.

Sur un dépôt **privé**, tu disposes de 2 000 minutes par mois. Ce pipeline
consomme environ **5 minutes par poussée** (les deux premiers chantiers en
parallèle, puis la construction de l'image, largement accélérée par le cache).
Soit de l'ordre de 400 poussées par mois — très au-delà du rythme du projet.

---

## 9. Le flux de travail qui va avec

Le pipeline est écrit pour ce déroulé :

1. Tu crées une branche `feature/quelque-chose`
2. Tu pousses → **la CI tourne**, mais aucune image n'est publiée
3. Tu ouvres une pull request → la CI tourne à nouveau sur la fusion projetée
4. Tu fusionnes dans `main` → **l'image est construite et publiée**
5. Quand une version mérite d'être figée : `git tag v1.0.0 && git push --tags`
   → une image étiquetée `1.0.0` s'ajoute

Rien n'oblige à passer par une branche : une poussée directe sur `main`
déclenche le même pipeline. La branche apporte une seule chose, mais elle est
décisive — **savoir avant de fusionner**, plutôt qu'après.
