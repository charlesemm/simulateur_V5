# M3 — Le générateur et le corrigé · guide et scénario de test

> Module 3 sur 8 du [découpage](../../cahier%20des%20charges/Module_Qualite_Donnees_decoupage.md).
> C'est le module le plus important des huit : sans lui, il n'y a ni jeu piégé,
> ni corrigé, donc rien à mesurer.

## En clair

Jusqu'ici une campagne annonçait ce qu'elle ferait. Maintenant **elle le fait** :
elle produit un fichier de données fictives, y pose les anomalies demandées, et
garde le **corrigé** — la liste exacte de ce qu'elle a posé, ligne par ligne et
champ par champ.

Et elle affiche une **empreinte**. C'est une signature du fichier produit : une
suite de 64 caractères qui change dès qu'un seul octet change. Deux campagnes
lancées avec la même graine et les mêmes anomalies doivent afficher **la même
empreinte**. C'est la preuve de la rejouabilité, vérifiable à l'œil, sans
ouvrir les fichiers ni lancer quoi que ce soit dans un terminal.

## Pourquoi un générateur à part du moteur

Le moteur temps réel d'ÉCHO ne pouvait pas faire ce travail, et c'est la
décision de conception de ce module :

| Le moteur temps réel | Le générateur de campagne |
|---|---|
| Concurrent : plusieurs passages en parallèle | Séquentiel, ligne après ligne |
| Daté sur l'horloge réelle | Ancré sur une date fixe (1ᵉʳ janvier 2026) |
| Tire une partie de son hasard côté PostgreSQL (`func.random()`) | Un seul `random.Random(graine)`, rien d'autre |
| Écrit dans la base | Écrit un fichier |

Avec le moteur, deux exécutions de même graine n'auraient jamais produit le
même fichier. Trois règles gouvernent désormais `campagnes/generateur.py`, et
les enfreindre casserait la rejouabilité sans que personne ne le voie tout de
suite :

1. **aucun appel à l'horloge** dans les données — une date « du jour »
   changerait le fichier d'un jour à l'autre ;
2. **aucune lecture de la base** pour composer une ligne ;
3. **un ordre de tirage fixe**, celui du catalogue — sinon l'ordre dans lequel
   l'opérateur coche ses cases déciderait du fichier.

## Le jeu produit

Un CSV de **21 colonnes**, point-virgule, UTF-8, une ligne d'en-tête. Les
colonnes couvrent exactement ce que les treize types d'anomalies savent
corrompre : immatriculation, identité, courriel, régime, période de droits,
facture, dates de soins et d'émission, centre, prestation, quantités, montants,
taux et répartition CMU/assuré.

Chaque ligne est **cohérente avant d'être piégée** : le montant découle de
l'acte et de la quantité, la part CMU découle du régime (RAM 100 %, RGB 70 %),
la date d'émission suit la date de soins. C'est ce qui donne du sens aux
anomalies : une incohérence n'a d'intérêt que dans un jeu par ailleurs sain.

## Le corrigé

Une table dédiée, `TB_CAMPAGNES_CORRIGE`, une ligne par anomalie posée :
**ligne du fichier, champ touché, type d'anomalie, valeur d'origine, valeur
posée**. C'est le minimum que le cahier exige pour pouvoir confronter le
rapport de l'outil testé (§2.3).

La clé primaire porte une règle : un même type ne frappe qu'une fois une ligne
donnée. Deux types différents peuvent en revanche viser le même champ — une
date antidatée puis une date hors droits.

## Ce qui a été fait

| Fichier | Rôle |
|---|---|
| `campagnes/generateur.py` | La production, les 13 injecteurs, l'empreinte |
| `campagnes/generation.py` | Le pilotage : progression, corrigé versé en base, statuts |
| `campagnes/models.py` | `CorrigeCampagne` + 5 colonnes sur la campagne |
| `alembic/versions/20260828_0020_corrige_de_campagne.py` | La migration |
| `api/routers/campagnes.py` | `POST /{id}/generer`, `GET /{id}/progression`, `GET /{id}/corrige` |
| `dashboard/src/components/FicheCampagne.tsx` | Bouton, barre de progression, empreinte, corrigé paginé |

La génération tourne **en arrière-plan** et hors de la boucle d'événements :
une requête qui attendrait la fin expirerait sur un gros palier, et un calcul
long dans la boucle figerait l'API — plus de progression consultable,
exactement pendant les minutes où l'on veut regarder.

## Avant de tester : la migration

```bash
.venv/Scripts/python.exe -m alembic upgrade head
```

`alembic current` doit finir par **`20260828_0020`**. En conteneur :
`podman compose up --build -d` (le service `migrations` s'en charge).

## Ordres de grandeur mesurés

| Volume | Durée | Taille du fichier |
|---|---|---|
| 500 lignes | instantané | 90 Ko |
| 10 000 lignes | 0,5 s | 1,8 Mo |
| 100 000 lignes | 5,6 s | 17,7 Mo |

Reste sous 100 000 lignes pour cette recette. Le million du palier « Afflux
soudain » demandera le traitement par lots de M8 — ce n'est pas encore le
moment.

---

## Scénario de test

### 1. Générer

Ouvre une campagne existante (ou crée-en une avec quelques anomalies, palier
Échantillon).

- [ ] La fiche montre un bouton **Générer le jeu de données**.
- [ ] Clique. Le statut passe à **Génération en cours** (pastille verte).
- [ ] Une barre de progression apparaît, avec le compte de lignes et le
      pourcentage.
- [ ] À la fin, le statut passe à **Jeu généré** (pastille bleue).

> Sur 500 lignes c'est quasi instantané. Pour **voir** la barre travailler,
> crée une campagne à **50 000 lignes** : deux à trois secondes de progression
> visible.

### 2. L'empreinte

- [ ] Un bloc **« Empreinte du jeu produit (SHA-256) »** affiche 64 caractères.
- [ ] Le chemin du fichier est indiqué en dessous
      (`campagnes/output/C-2026-00X_….csv`).
- [ ] Les tuiles du haut sont remplies : lignes produites, anomalies posées,
      date de génération.

### 3. Le corrigé

- [ ] Un tableau **« Corrigé — N anomalies posées »** liste : ligne, champ,
      anomalie, valeur d'origine, valeur posée.
- [ ] Les deux valeurs sont bien **différentes** sur chaque ligne.
- [ ] Au-delà de 25 anomalies, la pagination apparaît (**Précédentes** /
      **Suivantes**) et le numéro de page est juste.
- [ ] Dans le tableau « Anomalies demandées », la colonne **Posées** est
      remplie. Vérifie l'ordre de grandeur : sur 500 lignes à 20 %, environ
      100 anomalies posées. C'est un tirage, pas un quota — un écart de
      quelques pour cent est normal.

### 4. La rejouabilité — le test qui compte

C'est celui pour lequel tout le reste existe.

- [ ] Crée **campagne A** : graine **4242**, palier Échantillon, coche
      *Montant aberrant* à **20 %**. Génère-la. **Note son empreinte** (les 12
      premiers caractères suffisent, ils sont affichés dans la liste).
- [ ] Crée **campagne B** : graine **4242**, palier Échantillon, *Montant
      aberrant* à **20 %**. Génère-la.
- [ ] **Les deux empreintes sont identiques.** Dans la liste, la colonne
      « Empreinte » affiche exactement la même suite pour les deux lignes.
- [ ] Ouvre les deux corrigés : **les mêmes numéros de ligne**, les mêmes
      valeurs.

Puis casse volontairement l'égalité :

- [ ] Crée **campagne C** : même graine 4242, mais *Montant aberrant* à
      **21 %**. Génère.
- [ ] Son empreinte est **différente**. Normal : le jeu n'est pas le même, donc
      les scores ne seraient pas comparables.
- [ ] Crée **campagne D** : graine **9999**, tout le reste identique à A.
      Empreinte différente elle aussi.

### 5. Régénérer ne duplique rien

- [ ] Sur la campagne A, clique **Régénérer le jeu**.
- [ ] L'empreinte affichée après coup est **la même qu'avant**.
- [ ] Le total du corrigé est **le même** — il a été remplacé, pas empilé.

### 6. Le fichier existe vraiment

- [ ] Ouvre `campagnes/output/` : le fichier est là, nommé avec la référence de
      la campagne.
- [ ] Ouvre-le (Bloc-notes, Excel avec point-virgule comme séparateur) :
      21 colonnes, une ligne d'en-tête, et des données lisibles.
- [ ] Prends une ligne signalée dans le corrigé (numéro N) et va la voir dans
      le fichier : elle porte bien la **valeur posée**, pas la valeur
      d'origine. Attention : la ligne N du corrigé est la ligne N **de
      données**, donc la ligne N+1 du fichier — l'en-tête ne compte pas.

### 7. Ce qui doit *ne pas* arriver

- [ ] Pendant une génération, le bouton est **désactivé** : on ne lance pas
      deux productions sur le même fichier.
- [ ] Générer une campagne **sans aucune anomalie** produit un fichier et un
      corrigé **vide** — annoncé comme tel, pas comme une erreur.

---

## Ce que M3 ne fait pas encore

- **Pas de marquage** des données de test dans le fichier : le cahier l'exige
  (§2.2), c'est M4.
- **Pas de téléchargement** depuis l'écran, ni JSON, ni SQL : M4 aussi.
- Trois dimensions restent sans injecteur (unicité, complétude, encodage) : M5.
- Le million de lignes attend le traitement par lots de M8.

## Vérifications automatiques

`tests/test_campagnes.py` passe à **29 tests**. Les six ajoutés protègent le
cœur du module :

- même graine → **fichiers identiques à l'octet près** ;
- graine différente → jeu différent ;
- **l'ordre de saisie des anomalies ne change pas le fichier** ;
- aucune donnée ne vient de l'horloge ;
- le taux demandé est tenu, à la marge du tirage près ;
- **les treize types savent effectivement frapper** — un type qu'on peut
  cocher mais qui n'injecte rien afficherait « demandé 5 %, posé 0 » sans que
  rien ne l'explique.

Plus, côté API : génération de bout en bout, régénération qui ne duplique pas
le corrigé, campagne inconnue en 404.

Suite complète : **233 tests verts**, `npm run build` passe.

> Non vérifié à l'écran de mon côté : pas de session ouverte dans ton
> navigateur. Le scénario ci-dessus est la recette — et l'étape 4 est celle
> qu'il ne faut pas sauter.
