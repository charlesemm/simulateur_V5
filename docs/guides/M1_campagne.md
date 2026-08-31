# M1 — La campagne existe · guide et scénario de test

> Module 1 sur 8 du [découpage](../../cahier%20des%20charges/Module_Qualite_Donnees_decoupage.md)
> du module Qualité des données. À valider à l'écran, pas dans le terminal.

## En clair

La carte « Qualité des données » de l'accueil était grise. Elle ne l'est plus :
elle ouvre une **campagne de test**, l'unité que réclame le cahier des charges.

Une campagne, à ce stade, c'est un objet qui existe et qu'on retrouve : un
numéro lisible (`C-2026-001`), un nom, un palier de charge, un volume visé et
**une graine**. Rien n'est encore généré — c'est le module suivant. Ce qui
compte ici, c'est que la graine soit fixée et visible **avant** la génération :
sans elle, rien ne serait rejouable, et une graine tirée en douce au moment de
produire le jeu arriverait trop tard pour qu'on la note.

## Ce qui a été fait

### Côté serveur

| Fichier | Rôle |
|---|---|
| `campagnes/models.py` | La table `TB_CAMPAGNES` et les sept statuts du cycle d'une campagne |
| `campagnes/paliers.py` | Les quatre paliers du cahier et leur volume proposé |
| `campagnes/service.py` | Création (graine, référence `C-AAAA-NNN`, bornes), lecture, liste |
| `alembic/versions/20260828_0019_campagnes_de_test.py` | La migration qui crée la table |
| `api/routers/campagnes.py` | `GET /campagnes/paliers`, `GET /campagnes/statuts`, `POST /campagnes`, `GET /campagnes`, `GET /campagnes/{id}` |
| `simulation/profils.py` | Chaque type déclare `disponible` et `parcours` |

**Le grisage a changé de camp.** Il était écrit en dur dans l'écran d'accueil
(`profil.code !== "LIBRE"`) : ouvrir un type demandait de retoucher le
navigateur. C'est le serveur qui le dit maintenant. LIBRE mène au moteur temps
réel, QUALITE mène à une campagne — deux parcours, pas un seul avec une
variante.

### Côté écran

| Fichier | Rôle |
|---|---|
| `dashboard/src/components/NouvelleCampagnePage.tsx` | Nom, palier, volume, graine |
| `dashboard/src/components/CampagnesPage.tsx` | La liste et la fiche d'une campagne |
| `dashboard/src/components/AccueilPage.tsx` | Obéit au serveur, et ne montre plus « vitesse / passages » sur une campagne |
| `dashboard/src/components/Sidebar.tsx` | Nouvelle entrée « Campagnes de test » |
| `dashboard/src/App.tsx`, `navigation.ts` | Les deux nouveaux onglets |

Aucun vocabulaire CSS nouveau : ce sont des écrans ordinaires, ils parlent
`Screens.css` comme les autres. Seules les pastilles de statut de campagne ont
été ajoutées.

## Avant de tester : la migration

La table `TB_CAMPAGNES` n'existe pas encore dans ta base de travail. Une seule
commande, à lancer à la racine du projet :

```bash
.venv/Scripts/python.exe -m alembic upgrade head
```

Elle ne touche à rien d'existant : elle crée une table neuve. Pour vérifier :

```bash
.venv/Scripts/python.exe -m alembic current
```

La réponse doit finir par `20260828_0019`.

## Démarrer

Deux terminaux, comme d'habitude :

```bash
.venv/Scripts/python.exe -m uvicorn api.main:app --reload
```

```bash
npm run dev --prefix dashboard
```

> Rappel de la panne du 23/08 : un seul `npm run dev` à la fois. Un second
> occuperait un autre port, et l'origine inconnue ferait échouer la connexion.

---

## Scénario de test

### 1. La carte n'est plus grise

Connecte-toi, reste sur **Vue d'ensemble**.

- [ ] La carte **QUALITE — « Qualité des données »** est en couleur, cliquable.
- [ ] Sa description parle de jeu piégé, de corrigé et de notation d'un outil
      extérieur — plus de « flux corrompu ».
- [ ] En bas de la carte : **« Jeu piégé, corrigé et note de l'outil testé »**,
      et non « Vitesse ×60 · 20 en parallèle ». Une campagne n'a pas de vitesse.
- [ ] MDM, ENTREPOT et GOUVERNANCE restent grisés, avec « En attente du cahier
      des charges ».
- [ ] LIBRE est toujours en couleur et mène toujours à l'écran de lancement.

### 2. Créer une campagne

Clique la carte QUALITE.

- [ ] L'écran **Nouvelle campagne de test** s'ouvre (pas l'écran de lancement
      du moteur).
- [ ] Un nom est déjà proposé, avec la date du jour.
- [ ] Les **quatre paliers** sont là : Échantillon, Volume courant, Volume
      élevé, Afflux soudain. Chacun annonce son volume.
- [ ] Clique **Volume courant** : la carte se cerne de vert **et** le champ
      « Volume visé » passe à 100 000. C'est voulu : garder l'ancien nombre
      donnerait une campagne qui ment sur son palier.
- [ ] Reviens sur **Échantillon** (500 lignes) pour la suite.
- [ ] Laisse la graine sur « Aléatoire ». Clique **Créer la campagne**.

### 3. La campagne existe et se retrouve

- [ ] Tu arrives sur **Campagnes de test**, et la campagne créée est déjà
      ouverte en bas de l'écran.
- [ ] Elle porte une référence du type **C-2026-001**.
- [ ] Son statut est **Créée** (pastille grise).
- [ ] La fiche affiche sa **graine** — un nombre, pas un tiret.
- [ ] Clique **Campagnes de test** dans la barre latérale, puis reviens : la
      campagne est toujours là. Elle est en base, pas dans le navigateur.

### 4. La graine se choisit — le point important

Clique **Nouvelle campagne**, puis :

- [ ] Passe la graine sur **Graine précise** et saisis `4242`.
- [ ] Nomme-la « Rejouabilité — essai 1 », palier Échantillon, crée-la.
- [ ] Recommence à l'identique : « Rejouabilité — essai 2 », graine `4242`.
- [ ] Dans la liste, les deux campagnes affichent **la même graine 4242** et
      **deux références différentes** (…002 et …003).

C'est le socle de la rejouabilité : au module 3, ces deux campagnes devront
produire deux jeux de données identiques à l'octet près. Aujourd'hui on vérifie
seulement que la graine est bien retenue et affichée.

### 5. Les gardes-fous

- [ ] Nouvelle campagne, saisis un volume de `5` : le champ refuse de descendre
      sous 100 (et si tu forces la valeur, le serveur la ramène à 100).
- [ ] Crée une campagne **sans toucher au nom** : elle prend « Campagne du
      … » avec la date — jamais un nom vide.

### 6. Ce qui doit *ne pas* arriver

- [ ] Créer une campagne **ne démarre aucun moteur** : la barre latérale ne
      fait pas apparaître « Simulation en cours », et le tableau de bord
      technique reste à l'arrêt.
- [ ] Inversement, si une simulation LIBRE tourne, la carte QUALITE **reste
      cliquable** : une campagne ne passe pas par le moteur, rien ne s'y
      oppose.

---

## Ce que M1 ne fait pas encore

- Le choix des anomalies (module M2) — l'écran n'a que les paramètres de
  génération.
- La génération du jeu et le corrigé (M3).
- L'export, le canal API, le score, les paliers réellement éprouvés (M4 à M8).

Une campagne reste donc au statut **Créée** : c'est normal, et les six autres
statuts sont déjà en place côté serveur pour les modules suivants.

## Vérifications automatiques

`tests/test_campagnes.py` — 11 tests : graine toujours présente, graine
choisie conservée, références qui se suivent, palier inconnu qui retombe sur
l'échantillon, volume borné, tri de la liste, ce que le serveur déclare
ouvert, et le parcours complet vu de l'API.

Suite complète : **215 tests verts**, `npm run build` passe.
