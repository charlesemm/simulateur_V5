# M4 — L'export marqué

> Quatrième module du cahier « Qualité des données ».
> Suite de [M3_generateur_et_corrige.md](M3_generateur_et_corrige.md).

---

## Ce que le module apporte

Jusqu'ici, le jeu piégé restait un fichier CSV sur le disque du serveur. Il
fallait s'y connecter pour le voir. Et rien, dans ce fichier, ne disait qu'il
s'agissait de données fabriquées.

M4 règle les deux points :

1. **Chaque ligne porte son marquage**, en tête : `DONNEE_FICTIVE` et la
   référence de la campagne. Aucun réglage ne permet de l'enlever.
2. **Le jeu se télécharge depuis l'écran**, dans quatre formats : CSV, Excel,
   JSON et script SQL.

Le marquage n'est pas une formalité. C'est le fichier qu'on va confier à
l'éditeur d'un outil extérieur ; il circulera, sera copié, peut-être chargé
dans une base. La première colonne de la première ligne doit dire ce que c'est.

---

## Le scénario de test

> À dérouler dans l'application, comme les précédents. Rappel : l'adresse est
> `http://<IP-de-la-machine-Podman>:8000`, pas `localhost`.

### Étape 1 — Ouvrir une campagne générée

Va dans **Campagnes** et ouvre une campagne dont le jeu a déjà été produit
(statut « générée », empreinte affichée).

⚠️ **Les campagnes générées avant aujourd'hui n'ont pas de marquage** : leur
fichier date d'avant ce module. Si ta campagne est ancienne, relance sa
génération — le bouton la refait avec la même graine.

### Étape 2 — Voir le bloc de téléchargement

Sous l'empreinte, un nouvel encadré **« Télécharger le jeu »** est apparu, avec
quatre boutons : `CSV`, `Excel`, `JSON`, `Script SQL`. Chacun affiche son
extension en dessous, et son rôle en infobulle au survol.

*Si l'encadré n'apparaît pas :* la campagne n'est pas générée, ou l'API n'a pas
répondu. Les boutons ne s'affichent jamais pour une campagne vide — il n'y
aurait rien à télécharger.

### Étape 3 — Télécharger le CSV et l'ouvrir

Clique sur **CSV**. Le fichier arrive sous le nom `C-2026-00X_jeu.csv`.

Ouvre-le (Bloc-notes, ou Excel en choisissant le point-virgule comme
séparateur). **Ce que tu dois voir :**

- La première ligne d'en-tête commence par `DONNEE_FICTIVE;CAMPAGNE_REFERENCE;`
- **Toutes** les lignes suivantes commencent par `FICTIF-ECHO;C-2026-00X;`
- Puis les 21 colonnes de données habituelles — 23 colonnes en tout

Descends jusqu'à la dernière ligne : elle est marquée comme la première.

### Étape 4 — Télécharger l'Excel

Clique sur **Excel**, ouvre le fichier. Tu retrouves les mêmes colonnes, dans
une feuille nommée « Jeu de test ».

Regarde une date aberrante ou un montant absurde : **ils sont restés tels
quels**. Toutes les cellules sont du texte, délibérément — laisser Excel les
interpréter reviendrait à le laisser corriger les pièges qu'on vient de poser.

### Étape 5 — La preuve de reproductibilité

C'est l'étape à ne pas sauter, l'équivalent de celle de M3.

**Télécharge deux fois le même format**, sans rien changer entre les deux. Ton
navigateur nommera le second `..._jeu(1).csv`.

Compare-les. Le plus simple, dans un terminal :

```bash
certutil -hashfile "C-2026-001_jeu.csv" SHA256
```

```bash
certutil -hashfile "C-2026-001_jeu(1).csv" SHA256
```

Les deux empreintes doivent être **identiques**, y compris pour l'Excel. C'est
ce que le cahier exige, et ce n'était pas gagné — voir la note technique plus
bas.

### Étape 6 — Le script SQL

Clique sur **Script SQL** et ouvre le fichier dans un éditeur de texte. En
tête :

```sql
-- Jeu de test ECHO — campagne C-2026-001
-- DONNEES FICTIVES : ne jamais charger dans une base de production.
```

Puis un `CREATE TABLE` et une ligne `INSERT` par enregistrement, marquage
compris. **Toutes les colonnes sont en TEXT** — y compris les dates. C'est
voulu : une colonne `DATE` refuserait justement les dates impossibles, qui font
tout l'intérêt du jeu.

### Étape 7 — Le refus

Ouvre une campagne **non générée** et vérifie qu'aucun bouton de téléchargement
n'apparaît. Rien à exporter, rien à proposer.

---

## Ce qu'il faut savoir sur la conception

### L'arbitrage entre M3 et M4

Les deux chapitres du cahier se contredisaient sur un point :

- M3 veut que deux campagnes de **même graine** affichent la **même empreinte**.
- M4 veut que chaque ligne porte la **référence de sa campagne** — qui est
  précisément ce qui distingue ces deux campagnes.

Faire entrer le marquage dans le calcul de l'empreinte aurait donné deux
empreintes différentes, et rendu la preuve de rejouabilité illisible à l'écran.

**La décision retenue : l'empreinte porte sur les données seules.** Ce qu'elle
atteste est donc précis — *le contenu piégé est le même* — et elle ne prétend
pas être la somme de contrôle du fichier livré. Les deux exigences tiennent
ensemble.

Concrètement, deux campagnes de même graine : même empreinte affichée, mais
fichiers différant par leur seconde colonne. Rejouer *la même* campagne, en
revanche, redonne un fichier rigoureusement identique.

### Pourquoi le format Excel est écrit à la main

Le projet utilise openpyxl pour ses rapports. Je l'ai d'abord employé ici
aussi, et **il a échoué à l'exigence de reproductibilité** : deux exports du
même contenu, dans le même processus, donnaient des octets différents une fois
sur deux.

La cause : un classeur Excel est une archive, et une archive porte l'heure de
sa fabrication. Figer ces dates n'a pas suffi — openpyxl introduit en plus un
ordre interne qu'on ne peut pas fixer de l'extérieur.

Un classeur minimal ne compte que six parties XML. Elles sont désormais écrites
directement dans `campagnes/export.py`. Le fichier obtenu est identique à
l'octet près d'une exécution à l'autre, ne dépend d'aucune bibliothèque, et
s'écrit plus vite. `reports/excel_generator.py` continue d'utiliser openpyxl :
ses rapports n'ont pas à être reproductibles, et ils sont mis en forme.

### La limite de volume

Le CSV est renvoyé tel qu'il est sur le disque, sans jamais tenir en mémoire :
aucune limite. Les trois autres formats sont construits en mémoire et sont
donc **plafonnés à 200 000 lignes**. Au-delà, l'API refuse avec un message qui
le dit — et rappelle que le CSV, lui, reste disponible.

Ce plafond deviendra un sujet à M8, avec les paliers élevés. Le cahier interdit
qu'une saturation ressemble à autre chose qu'à ce qu'elle est : mieux vaut un
refus qui s'explique qu'un processus qui tombe.

---

## Ce qui a changé dans le dépôt

| Fichier | Nature |
|---|---|
| `campagnes/export.py` | **nouveau** — les quatre formats, le classeur écrit à la main |
| `campagnes/generateur.py` | le marquage, et l'empreinte calculée hors marquage |
| `campagnes/generation.py` | la référence transmise au générateur |
| `api/routers/campagnes.py` | `GET /campagnes/formats` et `GET /campagnes/{id}/export` |
| `api/schema.py` | `FormatExportResponse` |
| `dashboard/src/services/api.ts` | `getFormatsExport`, `telechargerJeu` |
| `dashboard/src/components/FicheCampagne.tsx` | le bloc de téléchargement |
| `dashboard/src/components/Screens.css` | les styles `export-*` |
| `tests/test_campagnes.py` | 10 tests de plus |

**244 tests verts**, `npx tsc --noEmit` et `npm run build` passent.

### Deux points appelant ton attention

**Les campagnes déjà générées n'ont pas de marquage.** Leur fichier date
d'avant ce module. Il faut relancer leur génération — la graine étant
conservée, le contenu piégé sera identique.

**Un défaut préexistant, repéré au passage** : `.empreinte-valeur` dans
`Screens.css` utilise `var(--text)`, une variable qui n'est définie nulle part
dans `index.css` (le nom réel est `--text-main`). La couleur affichée est donc
celle héritée du parent, par accident. Ce n'est pas dans le périmètre de M4,
je n'y ai pas touché.

---

> Non vérifié à l'écran de mon côté : je n'ai pas de session ouverte dans ton
> navigateur. Le scénario ci-dessus est la recette — et l'étape 5 est celle
> qu'il ne faut pas sauter.
>
> Rappel : la recette de M1 à M3 n'a jamais été faite non plus. Elle reste en
> dette.
