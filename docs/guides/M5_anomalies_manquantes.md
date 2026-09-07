# M5 — Les anomalies qui manquaient au catalogue

> Cinquième module du cahier « Qualité des données ».
> Suite de [M4_export_marque.md](M4_export_marque.md).

---

## Ce que le module apporte

Le cahier décrit **huit dimensions de qualité**. Jusqu'ici, trois d'entre elles
étaient décrites sans que rien ne sache les éprouver :

- **Unicité** — les doublons
- **Complétude** — les champs obligatoires manquants
- **Conformité technique** — les caractères cassés

L'écran de choix les affichait avec un compte à zéro, ce qui était honnête,
mais rendait le futur score bancal : on ne peut pas noter un outil sur une
dimension dont on ne lui a rien soumis.

M5 comble ces trois trous et ajoute deux types au passage. **Le catalogue passe
de 13 à 19 types, et plus aucune dimension n'est vide.**

| Type ajouté | Dimension | Ce qu'il éprouve |
|---|---|---|
| Doublon exact | Unicité | Deux fiches strictement identiques |
| Doublon approchant | Unicité | Même personne, une variation orthographique, **deux numéros** |
| Champ obligatoire vide | Complétude | Un nom, une immatriculation, une date absents |
| Encodage cassé | Conformité technique | « N'Guessan » devenu « N?Guessan » |
| Tentative d'injection | Conformité technique | Une chaîne hostile glissée dans un champ texte |
| Format de date incohérent | Validité | Une date juste, mal écrite |

---

## Le scénario de test

> À dérouler dans l'application. Une **reconstruction est nécessaire** :
> ce module ajoute la migration `0021`, qui inscrit les six types en base.

```bash
podman compose up -d --build
```

### Étape 1 — Les huit dimensions sont pleines

Crée une campagne et va jusqu'à l'étape 2, le choix des anomalies.

**Ce que tu dois voir :** les types groupés par dimension, et **plus aucune
dimension à zéro**. Unicité en compte 2, Complétude 1, Conformité technique 2.

C'était le repère qu'on avait posé en M2 pour que le manque se voie. Il doit
maintenant être clos partout.

### Étape 2 — Les six nouveaux types sont proposés

Dans la liste, tu trouves les six nouveaux libellés, chacun sous sa dimension.
Coche **Doublon approchant** et **Encodage cassé**, à 10 % chacun, puis génère.

### Étape 3 — Le corrigé montre ce qui a été posé

Ouvre le corrigé. Pour un doublon, le champ est `IDENTITE`, et les deux
colonnes montrent l'identité avant et après. Par exemple :

```
avant : 3690709333029 | Ouattara | Oumar | 1976-09-18
après : 3690709333029 | Kouuamé | Mariam | 1978-10-14
```

Pour l'encodage cassé, tu verras `Ouattara` devenir `Ouatt?ra`, ou un nom
accentué devenir du charabia — le mojibake du double encodage.

### Étape 4 — Retrouver un doublon dans le fichier

Télécharge le CSV et cherche l'identité d'une ligne signalée comme doublon
approchant. **Tu dois en trouver une autre, très proche mais pas identique**,
ailleurs dans le fichier : même prénom, même date de naissance, nom à une
lettre près — et surtout **une immatriculation différente**.

C'est tout l'enjeu de ce type : deux numéros pour une seule personne. Si les
numéros étaient identiques, n'importe quel outil trouverait le doublon en une
requête, et le test ne prouverait rien.

### Étape 5 — La console d'injection, elle, n'a pas changé

Va dans **Console d'injection** (celle du moteur temps réel).

**Ce que tu dois voir :** les 13 types d'avant, et **pas** les six nouveaux.
Ce n'est pas un oubli — voir la note ci-dessous.

### Étape 6 — La charge hostile ne casse rien

Crée une campagne avec **Tentative d'injection** à 20 %, génère, puis
télécharge le CSV **et** le script SQL.

**Ce que tu dois voir :** le CSV s'ouvre normalement dans Excel, toutes les
lignes ont bien leurs 23 colonnes. Dans le SQL, la charge apparaît avec ses
apostrophes doublées :

```sql
INSERT INTO TB_JEU_CAMPAGNE (...) VALUES (..., '''; DROP TABLE TB_FACTURES; --', ...);
```

C'est le test de notre propre export autant que du jeu : les charges
contiennent des points-virgules et des apostrophes, exactement les caractères
qui découpent un CSV et un script SQL.

### Étape 7 — La rejouabilité tient toujours

Refais le test pivot de M3 : deux campagnes, même graine, mêmes taux, avec les
nouveaux types. **Les empreintes doivent rester identiques.**

C'est la vérification la plus importante du module : les doublons sont les
premiers injecteurs à **lire ce qui précède** dans le fichier, ce qui aurait pu
casser la reproductibilité.

---

## Ce qu'il faut savoir sur la conception

### Pourquoi la console d'injection ne montre pas les nouveaux types

Un doublon suppose de connaître une ligne **déjà écrite**. Le moteur temps réel,
lui, traite un passage à la fois, en concurrence, sans mémoire de ce qui
précède : il ne peut pas en poser.

Chaque type porte donc désormais une **portée** : `toutes` ou `campagne`. La
console d'injection ne montre que les premiers. Afficher un interrupteur qui ne
produit rien serait pire que de ne pas l'afficher — on croirait avoir testé.

Les six nouveaux types sont de portée `campagne`. Ils restent en base, le
corrigé les désigne, et l'écran des campagnes les propose.

### Un écart assumé avec la lettre du cahier

Le cahier range les caractères cassés et les formats de date parmi les
« anomalies de fichier », à injecter **à l'écriture de l'export**, au motif
qu'elles ne peuvent pas exister dans une colonne typée.

L'objection tombe ici : le jeu est un **CSV**, où tout est du texte. Les poser
dans la ligne, comme les seize autres, garde le corrigé exact — ligne *et*
champ — dont le rapprochement de M7 aura absolument besoin. Injectées à
l'écriture, elles auraient été bien plus difficiles à rattacher à une ligne
précise.

### Un injecteur a le droit de ne rien poser

Nouveau dans ce module : un injecteur peut renoncer.

Si « champ obligatoire vide » a déjà effacé une date, « format de date
incohérent » n'a plus rien à réécrire. Il ne pose alors rien, et **n'inscrit
rien au corrigé**. Inscrire une anomalie qui n'a pas eu lieu fausserait le
score de M7 dans le plus mauvais sens : l'outil testé serait accusé d'avoir
manqué ce qui n'existait pas.

Le tirage, lui, a bien lieu dans tous les cas — sans quoi la suite du fichier
dépendrait du contenu de la ligne, et la rejouabilité tomberait.

### La fenêtre glissante des doublons

Les doublons puisent leur modèle dans les **300 dernières lignes**, pas dans
tout le fichier. Sur un palier à un million de lignes, garder chaque identité
épuiserait la mémoire pour un bénéfice nul : un doublon posé à trois cents
lignes d'écart est déjà un doublon.

### Le défaut trouvé en cours de route

La première version du doublon approchant pouvait produire une identité
**identique** à l'originale — un nom sans accent dont on retire les accents ne
change pas. Le corrigé annonçait alors une anomalie introuvable dans le
fichier.

Corrigé de deux façons : la variation retombe sur le doublement d'une lettre
quand elle n'a rien changé, et le doublon renonce si l'identité n'a pas bougé.

---

## Ce qui a changé dans le dépôt

| Fichier | Nature |
|---|---|
| `anomalies/catalogue.py` | 6 types, la notion de **portée**, `CODES_MOTEUR` |
| `alembic/versions/20260831_0021_*.py` | **nouveau** — inscrit les 6 types en base |
| `campagnes/generateur.py` | 6 injecteurs, la fenêtre d'historique, un injecteur peut renoncer |
| `api/routers/anomalies.py` | la console filtre sur la portée |
| `tests/test_campagnes.py` | 11 tests de plus |

**Migration `0021` à appliquer** — elle part toute seule avec
`podman compose up -d --build`.

Rien à changer côté écrans : l'étape 2 lit les types et leurs dimensions
depuis le serveur, elle affiche donc les six nouveaux sans retouche. C'était
l'intérêt de les avoir déclarés côté serveur dès M2.

---

> Non vérifié à l'écran de mon côté. Le scénario ci-dessus est la recette —
> l'étape 7 est celle qu'il ne faut pas sauter.
>
> Rappel : la recette de M1 à M4 n'a jamais été faite. Elle reste en dette,
> et la checklist est là pour ça.
