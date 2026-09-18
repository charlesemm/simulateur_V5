# Mettre ÉCHO en service sur le serveur `srv-gouv`

> **Ce guide décrit une installation précise**, pas un cas général : ÉCHO, sur
> la machine `srv-gouv.ipscnam.ci` de l'IPS-CNAM, sous Oracle Linux, accessible
> depuis le réseau interne uniquement.
>
> Il est écrit pour être suivi **sans être développeur**. Une commande à la
> fois, chacune précédée de ce qu'elle fabrique et suivie de ce que vous devez
> voir à l'écran.
>
> Pour faire tourner ÉCHO sur le poste de développement, voir
> [GUIDE_PODMAN.md](GUIDE_PODMAN.md). Pour le pipeline, [GUIDE_CICD.md](GUIDE_CICD.md).

---

# 0. Lisez ceci en premier

## 0.1 Ce qu'on fabrique, en trois phrases

Aujourd'hui, ÉCHO ne tourne que sur un poste de travail. Si ce poste s'éteint,
il n'y a plus de service, et personne d'autre ne peut s'en servir.

À la fin de ce guide, un agent de l'IPS-CNAM ouvre son navigateur, tape
`echo.ipscnam.ci`, et l'application est là. Elle tourne sur `srv-gouv`, une
machine allumée en permanence.

Tout le reste de ce document n'est que la plomberie pour y arriver.

## 0.2 Les trois choses qui doivent se rencontrer

Imaginez que vous installez une machine-outil dans un local.

| | Ce que c'est ici | D'où ça vient |
|---|---|---|
| **Le local** | Le dossier `/opt/echo` sur le serveur | On le crée (partie 2) |
| **Les réglages** | Quatre fichiers texte : domaine, mots de passe, version | On les copie depuis le dépôt (partie 3) |
| **La machine** | ÉCHO lui-même : l'API, le dashboard, la base | Le serveur la télécharge **tout seul** (partie 5) |

**Retenez surtout la troisième ligne.** Le code d'ÉCHO ne passe jamais par
votre poste pour arriver sur le serveur. Il est fabriqué par GitHub, en un
paquet scellé, et le serveur va le chercher là-bas. C'est ce qui garantit que
ce qui tourne en production est exactement ce qui a été testé — pas l'état de
votre disque dur un mardi après-midi.

## 0.3 Deux choses ne dépendent pas de vous

Elles prennent des jours, pas des minutes. **Lancez-les avant tout le reste**,
sinon vous attendrez à la fin.

| | Qui | Quoi |
|---|---|---|
| **L'enregistrement DNS** | L'équipe réseau de l'IPS-CNAM | Faire exister le nom `echo.ipscnam.ci` |
| **La publication de l'image** | Vous, mais côté code | Fusionner le travail sur `main` pour que GitHub fabrique le paquet |

La partie 1 explique comment lancer les deux. **Tant qu'elles ne sont pas
faites, ÉCHO ne démarrera pas** — mais tout le reste peut être préparé pendant
l'attente.

## 0.4 Le tableau de bord

Cochez au fur et à mesure. En cas d'interruption, c'est ici qu'on reprend.

| # | Étape | Partie | Fait ? |
|---|---|---|---|
| 1 | Demande DNS envoyée à l'équipe réseau | 1.1 | ☐ |
| 2 | Travail fusionné sur `main`, image publiée | 1.2 | ☐ |
| 3 | Podman installé | 2.2 | ☐ |
| 4 | Pare-feu ouvert sur 80 et 443 | 2.3 | ☐ |
| 5 | Dossier `/opt/echo` créé et à vous | 2.5 | ☐ |
| 6 | Les quatre fichiers copiés | 3 | ☐ |
| 7 | Le `.env` rempli | 4 | ☐ |
| 8 | Session GHCR ouverte sur le serveur | 5.1 | ☐ |
| 9 | ÉCHO démarré | 5.2 | ☐ |
| 10 | Redémarrage automatique vérifié | 5.5 | ☐ |
| 11 | Premier compte créé | 6 | ☐ |
| 12 | Sauvegarde testée et planifiée | 7 | ☐ |

---

# Partie A — Comprendre

Cette partie ne contient aucune commande. Dix minutes de lecture, qui évitent
trois jours de confusion.

## A.1 Six mots, en français courant

### L'image

**Une image, c'est l'application entière mise en boîte** : le code, la version
de Python qu'il lui faut, ses dépendances, le dashboard déjà compilé. Tout,
dans un seul paquet scellé.

C'est l'équivalent du fichier `.iso` qu'on grave, ou du programme
d'installation qu'on télécharge. Ça ne fonctionne pas tout seul — il faut le
lancer.

**L'intérêt : le serveur ne compile rien.** Il télécharge le paquet et
l'ouvre. Aucune surprise du type « ça marchait sur ma machine ».

### Le conteneur

**Un conteneur, c'est une image en train de tourner.** L'image est le plan, le
conteneur est le bâtiment construit à partir du plan.

On peut en lancer plusieurs depuis la même image, les arrêter, les supprimer,
les relancer. **Un conteneur supprimé ne laisse rien derrière lui** — d'où la
notion suivante.

### Le volume

**Un volume, c'est un tiroir qui survit au conteneur.** Sans lui, supprimer le
conteneur PostgreSQL effacerait la base de données avec.

| Volume | Ce qu'il garde | Si on le perd |
|---|---|---|
| `pgdata` | **La base de données** | Tout est perdu : campagnes, comptes, résultats |
| `rapports` | Les rapports générés | Ils se régénèrent |
| `caddy_data` | Le certificat et l'autorité qui l'a signé | Les navigateurs réavertissent tout le monde |
| `caddy_config` | La configuration de Caddy | Elle se reconstruit |

**Un seul de ces quatre est irremplaçable : `pgdata`.** C'est lui, et lui seul,
que sauvegarde le script de la partie 7.

### GHCR

**GHCR, c'est l'entrepôt d'images de GitHub.** Le pipeline y dépose une image
neuve à chaque fois que du code arrive sur `main` ; le serveur va l'y chercher.

Un magasin d'applications privé, réservé à ce projet.

### Caddy

**Caddy est le portier du serveur.** C'est le seul programme joignable depuis
le réseau. Il reçoit toutes les visites et les transmet à l'application, qui
reste invisible.

Il rend trois services :

1. **Il chiffre les échanges** (le cadenas HTTPS).
2. **Il cache l'application et la base**, qui ne sont joignables ni l'une ni
   l'autre directement.
3. **Il ajoute des en-têtes de sécurité** qui durcissent le navigateur.

> **Pourquoi le chiffrement compte ici.** Sans lui, le mot de passe d'un agent
> qui se connecte à ÉCHO circulerait en clair sur le réseau de l'institution.
> N'importe qui sur le trajet pourrait le lire. Inacceptable pour une
> application qui manipule des données d'assurance maladie.

### Le DNS

**Le DNS, c'est l'annuaire du réseau.** Il traduit un nom lisible
(`echo.ipscnam.ci`) en adresse de machine (`10.10.4.165`).

Ici, l'annuaire concerné est **celui de l'IPS-CNAM** — le résolveur
`172.18.3.1` —, pas celui d'Internet. Tant que la traduction n'y existe pas, le
nom ne mène nulle part.

## A.2 La forme du déploiement

Quatre morceaux tournent sur le serveur. Chacun fait une seule chose.

```
              Réseau interne IPS-CNAM
                        │
                        │  ports 80 et 443, les seuls ouverts
                        ▼
                  ┌───────────┐
                  │   CADDY   │   le portier : chiffre, protège, transmet
                  └─────┬─────┘
                        │  réseau interne aux conteneurs, invisible
                        ▼
                  ┌───────────┐
                  │    API    │   ÉCHO : l'application et son dashboard
                  └─────┬─────┘
                        │
                        ▼
                  ┌───────────┐
                  │ POSTGRES  │   la base : tout ce qui doit être conservé
                  └───────────┘

           ┌────────────┐
           │ MIGRATIONS │   met la base à la bonne forme, puis s'arrête
           └────────────┘
```

**Le quatrième, `migrations`, surprend souvent.** Il ne tourne pas en
permanence : il démarre, met la structure de la base à jour, et s'arrête. Quand
vous le verrez marqué `exited (0)`, cela veut dire « terminé, sans erreur » —
pas « en panne ».

Il s'exécute **avant** l'application, délibérément : si l'application démarrait
la première, elle chercherait des tables qui n'existent pas encore.

## A.3 Pourquoi un second fichier de configuration

Le `compose.yaml` à la racine du projet sert au développement. Il fait trois
choses justes pour un poste de travail, et dangereuses sur un serveur :

| Il fait ça | Bien sur un poste | Grave sur un serveur |
|---|---|---|
| **Construit** l'image sur place | On teste ses modifications | Le serveur déroulerait du code non testé |
| Porte des **mots de passe par défaut** | On démarre sans rien configurer | Un mot de passe connu de tous, publié dans le dépôt |
| Publie le **port 8000 en clair** | On ouvre `localhost:8000` | L'application joignable sans chiffrement |

D'où `deploiement/compose.prod.yaml`, qui inverse les trois : il **télécharge**
l'image, **refuse de démarrer** si un secret manque, et **ne publie que 80 et
443**, derrière Caddy.

Rien n'a été retiré : le fichier de développement continue de servir votre
poste exactement comme avant.

## A.4 Les quatre fichiers fournis

| Fichier | Rôle |
|---|---|
| `deploiement/compose.prod.yaml` | La description des quatre services |
| `deploiement/Caddyfile` | La configuration du portier et du certificat |
| `deploiement/.env.exemple` | Le modèle des réglages — sans aucune vraie valeur |
| `deploiement/sauvegarde.sh` | La sauvegarde quotidienne de la base |

Environ 11 Ko de texte au total. **Aucun code de l'application** : il arrive par
GHCR.

## A.5 Ce que change cet environnement

Cinq particularités de `srv-gouv`. Les trois dernières font échouer un
déploiement **sans message compréhensible** si on les ignore.

| | Ici | Ce qui se passe si on l'ignore |
|---|---|---|
| Famille du système | Oracle Linux : `dnf`, et un dépôt à activer | `podman-compose` reste introuvable |
| Pare-feu | `firewall-cmd`, pas `ufw` | La commande des tutoriels n'existe pas |
| **SELinux** | Actif en permanence | « Permission refusée » sur un fichier aux droits corrects |
| **Comptes Active Directory** | Le groupe principal s'appelle « utilisateurs du domaine » | `chown user:user` échoue : ce groupe n'existe pas |
| **Redémarrage** | Rien ne repart tout seul | Le serveur revient en ligne **sans** ÉCHO |

---

# Partie 1 — Les deux demandes à lancer en premier

Elles ne dépendent pas de vous et prennent des jours. **Faites-les maintenant**,
puis continuez : la suite se prépare pendant l'attente.

## 1.1 L'enregistrement DNS

**Pourquoi.** Sans lui, le nom `echo.ipscnam.ci` ne mène nulle part, et aucun
agent n'atteindra l'application — même parfaitement installée.

Il se crée dans le DNS interne de l'IPS-CNAM, par l'équipe réseau. Pas depuis
le serveur.

**La demande, en trois lignes :**

| | Valeur |
|---|---|
| Type | A |
| Nom | `echo.ipscnam.ci` |
| Cible | `10.10.4.165` (le serveur `srv-gouv`) |

Rien d'autre. Pas d'ouverture de pare-feu périmétrique, pas d'adresse publique :
ÉCHO reste interne.

**Vérifier**, une fois la demande traitée :

```bash
dig +short echo.ipscnam.ci
```

**Ce que vous devez voir :** `10.10.4.165`, et rien d'autre.

**Une réponse vide** signifie simplement que l'enregistrement n'existe pas
encore. Ce n'est pas une panne, et rien de ce que vous ferez sur le serveur ne
changera cela.

## 1.2 La publication de l'image

**Pourquoi.** Le serveur ne compile rien : il télécharge un paquet déjà
construit. Ce paquet n'est fabriqué **que** lorsque du code arrive sur la
branche `main`.

**Tant que le travail reste sur une branche `feature/…`, il n'y a rien à
déployer.** Le serveur pourra être parfaitement préparé, il n'aura rien à
installer.

**Vérifier :** sur la page GitHub du dépôt, colonne de droite, section
**Packages**. Une image doit y figurer. Sinon, il faut d'abord faire arriver le
travail sur `main` — voir [GUIDE_CICD.md](GUIDE_CICD.md).

---

# Partie 2 — Préparer le serveur

Tout ce qui suit se fait **connecté en SSH sur `srv-gouv`**.

## 2.1 Le mode privilégié, et pourquoi `sudo` partout

Podman sait fonctionner de deux manières : sous votre compte, ou avec les
privilèges d'administrateur. **Ce guide choisit la seconde.**

**La raison :** Linux réserve les ports en dessous de 1024 — donc le 80 et le
443, ceux du web — aux programmes privilégiés. Sans privilèges, Caddy ne
pourrait pas les ouvrir, et rien ne serait joignable.

> ### La conséquence à connaître absolument
>
> **Le compte administrateur a son propre stockage**, complètement séparé du
> vôtre : ses images, ses volumes, ses conteneurs, sa session GHCR.
>
> Une commande lancée **sans** `sudo` ne verra rien. Elle ne produira pas
> d'erreur — elle affichera une liste vide, et vous croirez que le déploiement
> a disparu.
>
> **C'est l'erreur numéro un sur ce type d'installation.** Dans tout ce qui
> suit, `sudo` n'est jamais décoratif.

## 2.2 Installer Podman

**Podman est le programme qui fait tourner les conteneurs.** Il est à Oracle
Linux ce que Docker est ailleurs — mêmes commandes, sans service permanent en
arrière-plan.

`podman` est fourni d'origine, mais l'outil qui lit les fichiers `compose` —
`podman-compose` — vit dans un dépôt supplémentaire appelé **EPEL**, désactivé
par défaut. **L'ordre compte** : sans EPEL, la seconde commande ne trouvera pas
le paquet.

```bash
sudo dnf install -y oracle-epel-release-el9
```

```bash
sudo dnf install -y podman podman-compose git
```

> **Sous Oracle Linux 8** : le dépôt s'appelle `oracle-epel-release-el8`, et
> Podman s'installe par un module :
> `sudo dnf module install -y container-tools`.
>
> Pour connaître la version : `cat /etc/oracle-release`.

**Vérifier :**

```bash
podman --version && podman-compose --version
```

**Ce que vous devez voir :** deux numéros de version.

**Si la seconde répond « commande introuvable »**, EPEL n'a pas été activé :
reprenez les deux commandes dans l'ordre.

## 2.3 Le pare-feu

**Un pare-feu décide quelles portes de la machine sont ouvertes.** Le principe
ici : **deux portes, pas une de plus.**

- La **80** et la **443**, pour Caddy. Ce sont les seules.
- La base de données et l'application ne sont publiées nulle part. Elles se
  parlent sur un réseau interne aux conteneurs.

C'est ce qui fait qu'un attaquant présent sur le réseau ne peut pas tenter de se
connecter directement à la base : elle n'a aucune porte.

```bash
sudo firewall-cmd --permanent --add-service=http --add-service=https && sudo firewall-cmd --reload
```

`--permanent` inscrit la règle durablement ; `--reload` l'applique tout de
suite. Sans `--permanent`, elle disparaîtrait au prochain redémarrage.

**Vérifier :**

```bash
sudo firewall-cmd --list-services
```

**Ce que vous devez voir :** une liste contenant `http`, `https` et `ssh`.

> `ssh` doit y être. S'il n'y est pas, **ne redémarrez pas la machine** avant de
> l'avoir ajouté : vous perdriez l'accès au serveur.

## 2.4 SELinux — comprendre avant de subir

**SELinux est un gardien de sécurité, actif en permanence.** Son rôle : même si
un attaquant prenait le contrôle d'un conteneur, il ne pourrait pas toucher au
reste de la machine. Chaque fichier porte une étiquette, et chaque programme n'a
le droit de lire que les étiquettes qui le concernent.

**Ce que vous risquez de rencontrer :** un message « Permission denied » sur un
fichier dont les droits sont pourtant corrects. Rien dans les droits classiques
n'explique le refus — c'est SELinux, silencieux.

**C'est déjà géré dans le projet.** Le `Caddyfile` est monté avec le suffixe
`:Z`, qui demande à Podman de poser la bonne étiquette. Les autres volumes sont
des volumes Podman, étiquetés d'office.

> ### Ne désactivez pas SELinux
>
> `setenforce 0` est la réponse qu'on trouve sur tous les forums, et c'est la
> mauvaise. Elle supprime une protection entière du système pour régler un
> problème d'étiquette sur un seul fichier. Sur une machine qui héberge des
> données d'assurance maladie, c'est indéfendable.
>
> La partie 9.3 explique comment **lire** ce que SELinux a refusé : trente
> secondes, et la réponse est donnée.

**Vérifier :**

```bash
getenforce
```

**Ce que vous devez voir :** `Enforcing`.

## 2.5 Le dossier de travail

Tout le déploiement vit dans `/opt/echo`. Par convention sous Linux, `/opt`
accueille les applications installées à la main.

```bash
sudo mkdir -p /opt/echo
```

Le dossier appartient alors à `root`, puisqu'il a été créé sous `sudo`. Il faut
vous en rendre propriétaire, sans quoi la copie de la partie 3 sera refusée.

```bash
sudo chown "$USER" /opt/echo && ls -ld /opt/echo
```

**Ce que vous devez voir :** une ligne où `adm-mnguessan` figure en
propriétaire.

> ### Pourquoi `chown "$USER"` et pas `chown "$USER:$USER"`
>
> La forme habituelle des tutoriels est `chown utilisateur:groupe`, avec les
> deux identiques — parce que sur une machine classique, chaque utilisateur a un
> groupe personnel du même nom.
>
> **Ce n'est pas le cas ici.** `srv-gouv` est rattachée à l'annuaire Active
> Directory : votre groupe principal s'appelle **« utilisateurs du domaine »**,
> et aucun groupe `adm-mnguessan` n'existe. La commande échouerait sur « groupe
> incorrect ».
>
> Sans deux-points, `chown` ne change que le propriétaire et laisse le groupe
> tel quel. C'est tout ce dont on a besoin — et c'est même préférable :
> « utilisateurs du domaine » contient *tous* les comptes de l'institution. Lui
> donner l'écriture sur `/opt/echo` ouvrirait le dossier de production à tout le
> monde.
>
> Pour voir qui vous êtes aux yeux de la machine : `id`.

---

# Partie 3 — Copier les quatre fichiers

**Cette commande se lance depuis votre poste Windows**, pas depuis le serveur.
C'est le seul moment du guide où l'on change de machine.

Ouvrez PowerShell et placez-vous à la racine du projet :

```bash
cd C:\Users\charles.nguessan\Documents\simulateur_V5
```

Puis la copie, les quatre fichiers nommés explicitement :

```bash
scp deploiement/compose.prod.yaml deploiement/Caddyfile deploiement/sauvegarde.sh deploiement/.env.exemple adm-mnguessan@srv-gouv.ipscnam.ci:/opt/echo/
```

> **Pourquoi nommer les quatre plutôt qu'écrire `deploiement/*`.** L'étoile
> ramasse les fichiers visibles, mais **pas `.env.exemple`** : sous Linux, un
> nom commençant par un point est considéré comme caché. Le modèle des réglages
> serait resté sur votre poste, et l'oubli ne se verrait qu'à la partie 4.

**Vérifier**, côté serveur :

```bash
ls -a /opt/echo
```

**Ce que vous devez voir :** les quatre fichiers, `.env.exemple` compris.

### Si la copie est refusée

| Message | Cause | Solution |
|---|---|---|
| `Permission denied` sur chaque fichier | `/opt/echo` appartient encore à `root` | Reprendre 2.5 : `sudo chown "$USER" /opt/echo` |
| `Could not resolve hostname` | Votre poste n'utilise pas le résolveur interne | Remplacer le nom par `adm-mnguessan@10.10.4.165` |
| `scp` introuvable | Le client OpenSSH n'est pas installé sur le poste | Passer par WinSCP, ou l'installer |

> **Au premier passage, SSH demande de valider une empreinte** et l'enregistre
> sur votre poste. C'est la carte d'identité du serveur. Si la question revient
> plus tard pour la même machine, ce n'est pas anodin : cela signifie que le
> serveur a été réinstallé, ou que quelqu'un s'interpose.

---

# Partie 4 — Remplir le `.env`

**Un fichier `.env` rassemble les réglages propres à une installation** : mots
de passe, nom de domaine, version à déployer. Aucun code. C'est ce qui distingue
ce serveur de tout autre faisant tourner la même application.

**Il n'entre jamais dans le dépôt Git.** D'où le modèle `.env.exemple`, vide de
toute vraie valeur.

```bash
cd /opt/echo && cp .env.exemple .env && chmod 600 .env
```

`chmod 600` restreint la lecture au seul propriétaire. Sur une machine où
plusieurs personnes ont un compte — et c'est le cas ici, avec l'annuaire — sans
cela n'importe qui pourrait lire les mots de passe de production.

## 4.1 Générer les secrets

Trois secrets à produire. **Une exécution par secret**, pas une seule pour les
trois :

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Pourquoi cette commande plutôt qu'un mot de passe inventé.** Un mot de passe
choisi par un humain est toujours plus prévisible qu'il n'y paraît. Celle-ci
tire 32 octets au hasard d'une source cryptographique du système : personne ne
peut deviner le résultat, y compris vous.

## 4.2 Les six lignes

Ouvrez le fichier (`nano .env`, ou `vi .env`) et remplissez :

| Variable | Ce qu'on y met | À quoi ça sert |
|---|---|---|
| `ECHO_IMAGE` | `ghcr.io/charlesemm/simulateur_v5:latest` | Quelle version déployer |
| `ECHO_DOMAINE` | `echo.ipscnam.ci` (sans `https://`) | Le nom que Caddy sert |
| `CORS_ORIGIN_REGEX` | `https://echo\.ipscnam\.ci` | Quels sites le navigateur peut présenter à l'API |
| `POSTGRES_PASSWORD` | Un secret généré | Le mot de passe de la base |
| `JWT_SECRET_KEY` | Un secret généré | La signature des sessions ouvertes |
| `ECHO_ADMIN_PASSWORD` | Un secret généré | Le mot de passe du tout premier compte |

## 4.3 Trois pièges, expliqués

> ### 1. Les points de `CORS_ORIGIN_REGEX` doivent être précédés d'un `\`
>
> Cette ligne n'est pas une adresse : c'est un **motif de correspondance**. Dans
> un motif, le point ne veut pas dire « point » — il veut dire « n'importe quel
> caractère ».
>
> Écrit `https://echo.ipscnam.ci`, le motif accepte aussi
> `https://echoXipscnam.ci` — un nom qu'il suffirait de faire enregistrer dans
> le DNS interne pour être autorisé à parler à votre API depuis le navigateur de
> vos utilisateurs.
>
> Écrit `https://echo\.ipscnam\.ci`, il n'accepte que le vrai domaine.

> ### 2. `POSTGRES_PASSWORD` se choisit **une seule fois**
>
> Ce mot de passe est inscrit dans la base au tout premier démarrage, et il y
> reste. Le modifier plus tard dans le `.env` ne change **pas** celui de la
> base : l'application se présenterait avec un mot de passe que la base ne
> reconnaît plus, et ne se connecterait plus du tout.
>
> Le changer réellement suppose d'entrer dans la base pour l'y modifier. Autant
> le choisir correctement dès maintenant.

> ### 3. `latest` ou un repère fixe ?
>
> `latest` désigne toujours la dernière version publiée. Pratique, mais elle
> bouge : vous ne savez jamais exactement quel code tourne.
>
> Un repère fixe (`sha-a1b2c3d`, ou un numéro de version `1.2.3`) nomme un code
> précis. **Pour une vraie production, préférez-le** — le retour en arrière se
> résume alors à remettre l'ancienne valeur dans cette ligne.

## 4.4 Le garde-fou

**Cinq de ces six variables n'ont aucune valeur de repli.** S'il en manque une,
le lancement s'arrête net en la nommant.

C'est délibéré. L'alternative serait un démarrage silencieux sur un mot de passe
de développement connu de tous ceux qui ont accès au dépôt — bien pire qu'un
refus franc.

**La sixième, `ECHO_ADMIN_PASSWORD`, fait exception** : elle ne sert qu'une
fois, à la création du premier compte (partie 6), et le guide demande de la
vider juste après. Le déploiement démarre donc sans elle. C'est `auth.bootstrap`
qui refuse alors de créer un compte, en le disant — pas le lancement qui échoue.

---

# Partie 5 — Démarrer

**Deux conditions doivent être remplies** avant cette partie, toutes deux issues
de la partie 1 :

- `dig +short echo.ipscnam.ci` répond `10.10.4.165`
- Une image figure dans les **Packages** du dépôt GitHub

Si l'une manque, arrêtez-vous ici : la suite échouera sans message clair.

> **Pour tester avant que le DNS existe**, et uniquement pour cela, on peut
> déclarer le nom localement sur le serveur :
>
> ```bash
> echo "10.10.4.165 echo.ipscnam.ci" | sudo tee -a /etc/hosts
> ```
>
> Le fichier `/etc/hosts` est consulté avant le DNS. Vérifiez avec
> `getent hosts echo.ipscnam.ci`, et non `dig`, qui n'interroge que le DNS.
>
> **Cette ligne ne vaut que sur le serveur lui-même.** Aucun poste d'agent
> n'atteindra ÉCHO. C'est un échafaudage de test, à retirer une fois le vrai
> enregistrement en place — sinon vous aurez un jour deux vérités
> contradictoires sur la même machine.

## 5.1 Autoriser le serveur à télécharger l'image

Tant que le dépôt GitHub est privé, l'image l'est aussi. Le serveur doit prouver
son identité.

Il lui faut un **jeton personnel GitHub** avec la seule permission
`read:packages` — le droit de lire les images, rien d'autre. Ni écriture, ni
accès au code.

À créer sur GitHub : **Settings → Developer settings → Personal access tokens →
Fine-grained**.

```bash
read -rs GHCR_TOKEN && echo "$GHCR_TOKEN" | sudo podman login ghcr.io -u charlesemm --password-stdin
```

**Ce qui se passe :** le terminal attend, sans rien afficher. Collez le jeton,
appuyez sur Entrée. **Rien ne s'affiche pendant la saisie — c'est voulu**, ce
n'est pas un blocage.

**Pourquoi cette forme compliquée** plutôt que d'écrire le jeton dans la
commande : un jeton tapé directement se retrouve dans l'historique du terminal,
et reste visible dans la liste des processus pendant l'exécution. `read -rs` le
lit au clavier sans jamais l'exposer.

**Ce que vous devez voir :** `Login Succeeded!`

## 5.2 Démarrer

```bash
cd /opt/echo && sudo podman-compose -f compose.prod.yaml up -d
```

`up` démarre, `-d` rend la main immédiatement au lieu de rester attaché aux
journaux.

**Ce qui se passe, dans l'ordre** — l'enchaînement est réglé dans le fichier,
vous n'avez aucune attente à gérer :

1. Le serveur télécharge l'image depuis GHCR (**plusieurs minutes** la première
   fois : c'est le plus long de toute l'installation).
2. PostgreSQL démarre, et signale lui-même quand il est prêt.
3. `migrations` construit la structure de la base, puis **s'arrête**.
4. L'application démarre, et trouve une base à la bonne forme.
5. Caddy démarre et met en place le certificat.

**Vérifier :**

```bash
sudo podman-compose -f compose.prod.yaml ps
```

| Service | État attendu | Remarque |
|---|---|---|
| `postgres` | running (healthy) | |
| `migrations` | **exited (0)** | **Normal.** Il a fini son travail |
| `api` | running (healthy) | |
| `caddy` | running | |

> **`exited (0)` n'est pas une panne.** Le `0` veut dire « terminé sans
> erreur ». C'est exactement ce qu'on attend de ce service. Un autre chiffre
> signalerait un vrai problème.

## 5.3 Le certificat, et l'avertissement du navigateur

**Pourquoi c'est différent d'un site public.** Les certificats gratuits du web
sont délivrés par Let's Encrypt, qui vérifie qu'un domaine vous appartient en
venant frapper à la porte 80 **depuis Internet**. Un serveur d'adresse privée
n'est pas joignable de là : la demande échouerait indéfiniment.

**Ce qu'on fait à la place :** Caddy devient sa propre autorité de certification
et signe lui-même le certificat (`tls internal` dans le `Caddyfile`). C'est
immédiat, il n'y a rien à attendre.

```bash
sudo podman-compose -f compose.prod.yaml logs caddy
```

**Ce que vous devez voir :** une ligne mentionnant `certificate obtained` pour
votre domaine, sans erreur à la suite.

### L'avertissement, et ce qu'il veut vraiment dire

En ouvrant `https://echo.ipscnam.ci`, le navigateur affichera **« Connexion non
sécurisée »** ou l'équivalent. C'est attendu, et c'est mal nommé.

La connexion **est** chiffrée : personne sur le réseau ne peut lire ce qui y
circule. Ce que le navigateur signale, c'est qu'il ne connaît pas l'autorité qui
a signé le certificat — en l'occurrence Caddy lui-même. Il ne peut donc pas
garantir que le serveur est bien celui qu'il prétend être.

Sur un réseau interne maîtrisé, le risque est faible. Mais **un avertissement
qu'on apprend à ignorer est un réflexe dangereux à installer chez des agents**.
D'où les deux sorties ci-dessous.

### Sortie 1 — le certificat de l'autorité interne (la bonne)

Si l'IPS-CNAM dispose d'une autorité de certification interne — c'est le cas dès
qu'il existe un Active Directory avec les services de certificats, et l'annuaire
est là —, demandez-lui un certificat pour `echo.ipscnam.ci`. Les postes de
l'institution lui font **déjà** confiance : plus aucun avertissement, et rien à
distribuer.

Une fois les deux fichiers reçus :

```bash
mkdir -p /opt/echo/certs && cp echo.crt echo.key /opt/echo/certs/ && chmod 600 /opt/echo/certs/echo.key
```

Puis, dans `/opt/echo/Caddyfile`, remplacez `tls internal` par la ligne indiquée
juste en dessous dans les commentaires, décommentez le montage `./certs` dans
`compose.prod.yaml`, et relancez :

```bash
cd /opt/echo && sudo podman-compose -f compose.prod.yaml up -d
```

### Sortie 2 — distribuer l'autorité de Caddy

À défaut d'autorité interne, on peut faire connaître celle de Caddy aux postes.
Le fichier à distribuer :

```bash
sudo podman-compose -f compose.prod.yaml exec caddy cat /data/caddy/pki/authorities/local/root.crt
```

Il s'installe dans le magasin « Autorités de certification racines de
confiance » des postes — par stratégie de groupe si le parc est géré, à la main
sinon. Opération à confier à l'équipe qui administre les postes.

> **Ne repartez pas de zéro à chaque redémarrage.** Cette autorité vit dans le
> volume `caddy_data`. Le supprimer en fabriquerait une neuve, et tout ce qui
> aura été distribué serait à refaire.

## 5.4 La vérification qui compte

```bash
curl --cacert /dev/stdin https://echo.ipscnam.ci/health <<< "$(sudo podman-compose -f /opt/echo/compose.prod.yaml exec caddy cat /data/caddy/pki/authorities/local/root.crt)"
```

**Ce que vous devez voir :** `{"status": "ok"}`

Trois choses sont prouvées d'un coup : le nom mène bien au serveur, le
certificat présenté est bien celui de Caddy, et l'application répond.

> **La forme est inhabituelle, et c'est délibéré.** `--cacert` dit à `curl` de
> vérifier le certificat contre l'autorité de Caddy, qu'on vient de lui donner.
> Le test reste donc un vrai test.
>
> La tentation est d'écrire `curl -k`, qui ignore purement et simplement le
> certificat. Il passerait au vert même avec un chiffrement cassé : ce ne serait
> plus une vérification, mais une formalité.
>
> Une fois la sortie 1 ou 2 en place, un simple
> `curl https://echo.ipscnam.ci/health` suffira.

## 5.5 Survivre à un redémarrage — l'étape qu'on oublie

**Le problème.** Le fichier de configuration demande à Podman de relancer un
conteneur qui s'arrête tout seul. Mais cela ne vaut que **tant que la machine
tourne**. Après un redémarrage ou une coupure de courant, Podman ne relance
rien : le serveur revient en ligne, et ÉCHO ne démarre pas.

Personne ne s'en aperçoit avant qu'un utilisateur ne se plaigne.

**La solution, une seule commande :**

```bash
sudo systemctl enable --now podman-restart.service
```

Ce service, fourni avec Podman, relance à chaque démarrage tous les conteneurs
configurés pour cela — donc les nôtres.

**Vérifiez-le pour de vrai.** C'est la seule vérification de ce guide qui
demande de redémarrer la machine, et la seule qui prouve quelque chose.
Faites-la maintenant, pendant qu'aucun utilisateur ne dépend du service :

```bash
sudo reboot
```

Attendez deux minutes, reconnectez-vous, puis relancez la commande de 5.4. Si la
réponse est `{"status": "ok"}` **sans que vous ayez rien relancé**, le
déploiement tient debout tout seul. C'est le vrai critère de mise en production.

---

# Partie 6 — Créer le premier compte

**La base est vide : personne ne peut se connecter, pas même vous.** Sans cette
étape, la page de connexion refuse tout le monde.

```bash
sudo podman-compose -f compose.prod.yaml exec api python -m auth.bootstrap --creer --email admin@ipscnam.ci --utilisateur admin --nom "Administrateur ECHO"
```

`exec` exécute une commande **à l'intérieur** du conteneur déjà en marche.

**Remarquez ce qui manque : le mot de passe.** Il n'apparaît pas dans la
commande. Le programme lit `ECHO_ADMIN_PASSWORD`, déjà transmise au conteneur
par le `.env`. Un mot de passe tapé dans une commande resterait dans
l'historique du terminal.

La commande est sans danger à relancer : si le compte existe déjà, elle le dit
et ne touche à rien.

**Ensuite, dans cet ordre :**

1. Ouvrez `https://echo.ipscnam.ci` et connectez-vous.
2. **Changez ce mot de passe** depuis l'interface.
3. Videz la valeur de `ECHO_ADMIN_PASSWORD` dans le `.env`. Gardez la ligne,
   vide — c'est la seule des six que le déploiement accepte vide (partie 4.4).

---

# Partie 7 — Les sauvegardes

**La base est le seul élément irremplaçable.** L'image se retire de GHCR quand
on veut, la configuration se réécrit en dix minutes — mais une campagne perdue
l'est définitivement.

Le script fourni produit chaque nuit une copie compressée de la base, et efface
celles de plus de trente jours.

```bash
chmod +x /opt/echo/sauvegarde.sh
```

**Lancez-le une fois à la main.** Une sauvegarde jamais testée n'est pas une
sauvegarde :

```bash
sudo /opt/echo/sauvegarde.sh
```

**Ce que vous devez voir :** une ligne indiquant le fichier écrit et sa taille.
**Une taille de quelques kilo-octets seulement doit vous alerter** — la base
serait vide.

**Puis l'automatiser.** La tâche va dans les tâches planifiées de
l'administrateur — pas dans les vôtres, puisque les conteneurs tournent en mode
privilégié :

```bash
sudo crontab -e
```

La ligne à ajouter :

```
15 2 * * * /opt/echo/sauvegarde.sh >> /var/log/echo-sauvegarde.log 2>&1
```

Lecture : « à 2h15, chaque jour, chaque mois, chaque jour de la semaine ». La
fin de la ligne écrit le compte rendu dans un journal, erreurs comprises.

> ### Une sauvegarde qui reste sur le serveur ne sauvegarde rien
>
> Elle protège d'une fausse manœuvre ou d'une mise à jour ratée. Elle ne protège
> **pas** de la perte de la machine : disque mort, incendie, suppression
> accidentelle de la VM. Elle disparaît avec.
>
> Prévoyez une copie ailleurs — synchronisation vers une autre machine, ou le
> dispositif de sauvegarde de l'infrastructure. C'est un point à porter auprès
> de l'exploitation, pas un réglage à faire ici.

**Restaurer**, le jour venu :

```bash
gunzip -c /var/sauvegardes/echo/echo_AAAAMMJJ_HHMM.sql.gz | sudo podman-compose -f /opt/echo/compose.prod.yaml exec -T postgres psql -U echo -d echo_db
```

---

# Partie 8 — Mettre à jour

Une nouvelle version est publiée à chaque arrivée de code sur `main`. Pour
l'installer :

```bash
cd /opt/echo && sudo podman-compose -f compose.prod.yaml pull && sudo podman-compose -f compose.prod.yaml up -d
```

`pull` télécharge la nouvelle image, `up -d` remplace les conteneurs par des
neufs bâtis dessus. **Les volumes ne sont pas touchés : la base est conservée.**

Les migrations s'appliquent d'elles-mêmes : le service repart, met la base à
jour, et s'arrête avant que l'application ne redémarre. L'interruption dure
quelques secondes.

> **Sauvegardez avant toute mise à jour comportant une migration.** Le mécanisme
> sait revenir en arrière, mais une migration qui supprime une colonne ne rend
> pas son contenu. La sauvegarde est le seul filet.

**Revenir en arrière** : remettez l'ancienne valeur dans `ECHO_IMAGE` et
relancez `up -d`. C'est tout l'intérêt d'épingler un `sha-…` plutôt que de
suivre `latest`.

**Le ménage.** Chaque mise à jour laisse l'ancienne image sur le disque. Une
fois par trimestre :

```bash
sudo podman image prune -a
```

---

# Partie 9 — Dépannage

## 9.1 La méthode, avant les symptômes

Trois questions, dans cet ordre. Elles résolvent la grande majorité des cas.

**1. Est-ce que j'ai bien mis `sudo` ?** Sans lui, vous regardez un autre
stockage, vide. C'est l'erreur la plus fréquente et la plus déroutante.

**2. Qu'est-ce que les journaux disent ?** Ils nomment presque toujours la
cause :

```bash
sudo podman-compose -f compose.prod.yaml logs api
```

Remplacez `api` par `caddy`, `postgres` ou `migrations` selon le service.

**3. Quel service est réellement en panne ?**

```bash
sudo podman-compose -f compose.prod.yaml ps
```

En vous rappelant que `migrations` en `exited (0)` est normal.

## 9.2 Le tableau des symptômes

| Symptôme | Cause probable | Solution |
|---|---|---|
| `chown: groupe incorrect` | Compte Active Directory : pas de groupe du même nom | `sudo chown "$USER" /opt/echo` (partie 2.5) |
| `scp` : `Permission denied` sur chaque fichier | `/opt/echo` appartient encore à `root` | Partie 2.5 |
| `podman-compose : commande introuvable` | EPEL pas activé avant l'installation | Reprendre 2.2 dans l'ordre |
| `dig` ne renvoie rien | L'enregistrement DNS n'existe pas encore | Partie 1.1 — demande à l'équipe réseau |
| `up -d` s'arrête en nommant une variable | Elle manque au `.env` | La renseigner — le garde-fou fonctionne |
| `manifest unknown` au téléchargement | Aucune image publiée sur GHCR | Partie 1.2 — fusionner sur `main` |
| `unauthorized` au téléchargement | Session GHCR expirée, jeton sans `read:packages`, ou `login` fait sans `sudo` | Refaire 5.1 |
| Le navigateur affiche « Connexion non sécurisée » | Autorité de Caddy inconnue du poste | **Normal, la connexion est chiffrée** — partie 5.3 |
| `bind: permission denied` sur 80 ou 443 | Commande lancée **sans** `sudo` | Relancer avec `sudo` (partie 2.1) |
| `Permission denied` sur un fichier monté | Étiquette SELinux | **Ne pas désactiver SELinux** — voir 9.3 |
| Le dashboard s'affiche mais reste vide | `CORS_ORIGIN_REGEX` ne correspond pas au domaine | Ouvrir la console du navigateur : l'erreur CORS le dira |
| `api` redémarre en boucle | `JWT_SECRET_KEY` absente, ou base injoignable | Lire les journaux de `api` |
| Plus de connexion à la base après un `.env` modifié | `POSTGRES_PASSWORD` changé après le 1er démarrage | Le remettre à sa valeur d'origine (partie 4.3) |
| **Rien ne tourne après un redémarrage** | `podman-restart.service` pas activé | Partie 5.5 |
| Les conteneurs semblent avoir disparu | Commande lancée sans `sudo` | Le mode privilégié a son propre stockage (2.1) |
| Disque plein | Sauvegardes ou images accumulées | `sudo podman image prune -a`, vérifier la purge du script |

## 9.3 Lire ce que SELinux a refusé

Plutôt que de le désactiver :

```bash
sudo ausearch -m AVC -ts recent
```

Chaque refus y est écrit en clair, avec le fichier concerné et le programme
bloqué. Dans la quasi-totalité des cas, la réponse consiste à ajouter `:Z` au
montage fautif dans `compose.prod.yaml`.

**Jamais `setenforce 0`.**

---

# Partie 10 — Ce que ce déploiement ne fait pas encore

Trois limites assumées. À connaître avant de s'engager auprès de qui que ce soit
sur la disponibilité du service.

**Aucune automatisation.** Le pipeline publie l'image, il ne la déploie pas. La
mise à jour reste une commande lancée à la main, par quelqu'un, sur le serveur.
C'est volontaire pour un premier temps : on déploie, on comprend ce qui se
passe, on automatise ensuite.

**Une seule machine.** Pas de répartition de charge, pas de bascule. Si le
serveur tombe, le service tombe, et il faut quelqu'un pour le relever.

**Aucune supervision.** Les sondes de santé existent, et Podman relance un
conteneur mort — mais **personne n'est prévenu**. Si le service tombe une nuit,
vous l'apprendrez par un utilisateur. Une surveillance interne de l'adresse
`/health` est le premier pas, pour cinq minutes de travail.

Ces trois points relèvent du chantier X2 et sont à arbitrer avec l'exploitation.

---

# Annexe — Le dimensionnement du serveur

| | Minimum | Confortable |
|---|---|---|
| Processeur | 2 vCPU | 4 vCPU |
| Mémoire | 4 Go | 8 Go |
| Disque | 40 Go | 80 Go |

**Le disque est le poste à surveiller.** Trois choses s'y accumulent sans que
personne ne les regarde : la base qui grossit, les jeux de campagne générés, et
les sauvegardes quotidiennes. Une campagne au palier « Volume élevé » ne tient
pas dans un serveur de démonstration à 20 Go.

Pour connaître l'état de la machine :

```bash
df -h /; free -h; nproc
```
