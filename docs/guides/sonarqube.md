# SonarQube — le bulletin de santé du code

> Guide d'installation et de recette.
> Hors des modules du cahier « Qualité des données » : celui-ci note **le code
> d'ÉCHO**, pas les données que traite ÉCHO. Ne pas confondre les deux.

---

## À quoi ça sert

Jusqu'ici, la seule chose qui surveillait le code, c'était la suite de tests :
elle répond « ça marche » ou « ça ne marche pas ». Elle ne dit rien de l'état
du code lui-même — les morceaux copiés-collés, les fonctions devenues trop
longues à suivre, les bouts de code que plus personne n'appelle, les endroits
qu'aucun test ne traverse.

SonarQube est une application web qui lit tout le code et en fait un bulletin :
une page par projet, une note par sujet, et l'évolution dans le temps. C'est le
même geste que ta recette visuelle des modules, mais appliqué au code.

Elle couvre le Python **et** le TypeScript du dashboard : les deux moitiés
d'ÉCHO dans un seul tableau.

---

## Ce qui a été ajouté

| Fichier | Rôle |
|---|---|
| `compose.sonar.yaml` | Démarre le serveur SonarQube et sa base, **séparément** d'ÉCHO |
| `sonar-project.properties` | Dit au scanner quels dossiers lire et lesquels ignorer |
| `requirements-dev.txt` | Ajout de `pytest-cov`, qui mesure la couverture des tests |
| `.gitignore` | Écarte les rapports régénérés à chaque analyse |

Rien n'a été touché dans l'application : **ÉCHO fonctionne exactement comme
avant**, et `compose.yaml` est inchangé. SonarQube s'allume et s'éteint à part.

---

## Installation — une seule fois

### 1. Démarrer le serveur

```bash
podman compose -f compose.sonar.yaml up -d
```

> **`podman compose`, en deux mots séparés.** Le `podman-compose` avec un trait
> d'union du `GUIDE_PODMAN.md` est un programme Python distinct, qui n'est pas
> installé sur ce poste Windows. Podman 6 sait faire le travail lui-même via sa
> sous-commande `compose` : c'est la forme à utiliser ici.

> **Patience au premier démarrage.** SonarQube met **1 à 3 minutes** à devenir
> utilisable : il construit ses index. Pendant ce temps la page affiche
> « SonarQube is starting », ce n'est pas une panne. Pour suivre :
> `podman compose -f compose.sonar.yaml logs -f sonarqube`

### 2. Ouvrir l'interface et changer le mot de passe

Va sur **http://localhost:9000**

Identifiants du premier accès : `admin` / `admin`. SonarQube **exige** de le
changer immédiatement — c'est normal, choisis-en un et note-le.

> **Si la page ne répond pas depuis Windows :** c'est le même sujet que le
> `localhost:8000` d'ÉCHO avec Podman rootful sous WSL. Voir `GUIDE_PODMAN.md`.

### 3. Créer le projet et son jeton

Dans l'interface : **Create Project → Local project**

- Project display name : `ÉCHO — Simulateur CMU`
- Project key : SonarQube le déduit du nom et donne `ECHO---simulateur-CMU`.
  **Cette clé doit correspondre à celle de `sonar-project.properties`** — si tu
  en choisis une autre, reporte-la dans ce fichier.
- Main branch name : `main`
- Puis **Use the global setting** pour la définition du code neuf

SonarQube propose ensuite **Analyze locally** et affiche un **jeton**
(`sqp_…`). Copie-le : il ne sera plus jamais réaffiché.

> Ce jeton est un mot de passe. Il ne va **pas** dans le dépôt — il se passe en
> ligne de commande, ou dans ton `.env` local qui est déjà ignoré par git.

### 4. Installer le scanner

Le scanner est l'outil qui lit ton code et l'envoie au serveur ; le serveur ne
va jamais chercher le code tout seul. Pour un projet Python, SonarQube fournit
`pysonar`, qui s'installe dans le `.venv` du projet :

```bash
pip install pysonar
```

---

## Lancer une analyse

Trois commandes, dans cet ordre, depuis la racine du dépôt, **le `.venv`
activé**.

> **Tout sur une seule ligne.** Le `\` en fin de ligne que propose SonarQube
> pour couper une commande en plusieurs morceaux est de la syntaxe Linux :
> PowerShell ne la comprend pas et rejette chaque morceau séparément. Les
> commandes ci-dessous tiennent volontairement sur une ligne.

**1. Mesurer la couverture des tests Python**

```bash
python -m pytest --cov=. --cov-report=xml
```

**2. Envoyer le tout à SonarQube** (remplace l'adresse et le jeton par les tiens)

```bash
pysonar --sonar-host-url=http://172.31.104.114:9000 --sonar-token=sqp_TON_JETON
```

La clé du projet, les dossiers à lire et les exclusions sont déjà dans
`sonar-project.properties` : inutile de les repasser en ligne de commande.

L'analyse prend **1 à 2 minutes**. Elle se termine par
`ANALYSIS SUCCESSFUL, you can find the results at…`

---

## Le scénario de test

> À dérouler **dans l'interface web**, sur http://localhost:9000

### Étape 1 — la page d'accueil du projet

Après l'analyse, ouvre le projet. Tu dois voir un tableau avec **cinq
compteurs** : Bugs, Vulnerabilities, Security Hotspots, Code Smells, Coverage,
et un pourcentage de Duplications.

✅ **Attendu :** les compteurs sont remplis, la ligne « Lines of Code » indique
plusieurs milliers de lignes, et le langage détecté mentionne **Python et
TypeScript**.

❌ **Si Lines of Code est proche de zéro :** le scanner n'a pas trouvé les
dossiers. Vérifie que tu as lancé la commande depuis la racine du dépôt.

### Étape 2 — regarder un défaut de près

Clique sur le compteur **Code Smells**, puis sur n'importe quelle ligne de la
liste.

✅ **Attendu :** SonarQube ouvre **le fichier concerné, à la bonne ligne**,
surligne le passage, et explique en clair pourquoi c'est signalé. L'onglet
« Why is this an issue? » donne un exemple de code fautif et sa correction.

C'est le geste que tu répéteras : le tableau donne l'alerte, le clic donne la
raison.

### Étape 3 — vérifier que la couverture est bien remontée

Va dans l'onglet **Measures → Coverage**.

✅ **Attendu :** un pourcentage, et l'arborescence de tes dossiers avec la
couverture de chacun. Tu verras probablement que `campagnes/` et `anomalies/`
sont bien couverts, et que d'autres modules sont à zéro.

❌ **Si la couverture affiche « — » ou 0 % partout :** le fichier
`coverage.xml` n'a pas été produit. Reprends la commande `pytest --cov`.

### Étape 4 — vérifier que l'historique se construit

Modifie n'importe quel fichier Python (ajoute un commentaire), relance les deux
commandes d'analyse, puis retourne dans l'onglet **Activity**.

✅ **Attendu :** **deux points** sur le graphique au lieu d'un. C'est ce qui
prouve que SonarQube garde la mémoire et que tu pourras suivre la progression.

---

## Comment s'en servir au quotidien

Le réflexe utile n'est **pas** de vouloir vider les compteurs. Sur un projet
existant, ils affichent des centaines de défauts hérités, et vouloir tout
corriger décourage en une semaine.

Le bon réflexe est celui que SonarQube appelle **« Clean as You Code »** :
regarder uniquement l'onglet **New Code** — ce que tu viens d'écrire. Le passé
reste là, visible, mais tu ne t'engages que sur le neuf. C'est la seule
approche qui tienne dans la durée.

**Rythme conseillé :** une analyse à la fin de chaque module, avant de
committer. C'est le même moment que ta recette visuelle.

---

## Éteindre le serveur

```bash
podman compose -f compose.sonar.yaml down
```

Les données sont conservées : au prochain démarrage, tout l'historique est là.
Pour effacer réellement (jeton compris), ajouter `-v`.

---

## Ce que ce guide ne couvre pas

- **La couverture du dashboard.** Le projet n'a pas de tests frontend, donc
  aucun `lcov.info` n'est produit. La configuration l'attend déjà : le jour où
  des tests TypeScript existent, la mesure remontera sans rien changer ici.
- **L'analyse automatique en CI.** Le pipeline GitHub tourne sur une machine
  distante qui ne peut pas joindre un SonarQube installé sur ton poste. La
  brancher suppose soit d'héberger SonarQube sur un serveur accessible, soit
  de passer par SonarCloud. `ci.yml` est donc **inchangé** : l'analyse reste un
  geste manuel, à faire chez toi.
