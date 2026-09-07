# Alignement du format de campagne sur la vraie base (LIBRE)

> Correctif transversal aux modules M3/M5/M6 du cahier « Qualité des
> données », demandé après coup : le jeu produit par une campagne (type
> **QUALITE**) doit porter les mêmes noms de colonnes, la même échelle et le
> même format que ce que le moteur temps réel écrit réellement en base
> (type **LIBRE**) — sans quoi un outil testé sur l'un se trompe sur l'autre.

---

## Le problème trouvé

Le générateur de campagne (`campagnes/generateur.py`) avait inventé son
propre vocabulaire au lieu de reprendre celui de la vraie base
(`app/models/schema.py`, `seed/runner.py`). Cinq écarts, deux d'entre eux
trompant carrément l'anomalie censée les cibler :

| Écart | Avant | Après | Gravité |
|---|---|---|---|
| Champ ciblé par `NUMERO_SECU_INVALIDE` | `NUMERO_IMMATRICULATION` (n'existe pas côté vraie base) | `NUMERO_SECU` — comme `anomalies/config.py:tirer_numero_secu`, côté moteur | **Anomalie mal posée** |
| Échelle de `PRESTATION_TAUX_REMBOURSEMENT` | Fraction (`1.00` / `0.70`) | Pourcentage (`100` / `70`), comme `REGIME_TAUX` en base | **Anomalie mal posée** |
| Identifiant de l'assuré | `NUMERO_IMMATRICULATION`, préfixe `394` inventé | `ASSURE_NUMERO_IDENTIFIANT`, préfixe `CMU` — le vrai champ | Nom et format faux |
| Montant remboursé par le régime | `PRESTATION_MONTANT_CMU` | `PRESTATION_MONTANT_RQ` — la vraie colonne | Nom faux |
| Code du centre de santé | Entier nu (`12`) | `CSxxx` — comme `TB_REF_CENTRES_SANTE.CENTRE_SANTE_CODE` | Format faux |

Un sixième écart, plus profond, reste **assumé et non corrigé** : la vraie
base modélise les droits **mois par mois**, avec un statut (`TB_ASSURES_DROITS`,
`DROITS_ANNEE` + `DROITS_MOIS` + `DROITS_STATUT`), alors qu'une campagne
produit **un CSV à plat**, une ligne par facture. On ne peut pas y loger un
historique mensuel sans changer la forme même de l'export — ce serait un
autre chantier, pas un alignement de format. Ce qui *a* été aligné : les deux
dates de droits sont désormais horodatées (`DateTime(timezone=True)`, comme
la vraie colonne), plutôt que des dates nues.

---

## Ce qui a changé, précisément

- **`ASSURE_NUMERO_IDENTIFIANT`** remplace `NUMERO_IMMATRICULATION` : format
  `CMU` + dix chiffres, générés par bijection (comme avant), pour rester
  uniques et reproductibles à graine égale.
- **`NUMERO_SECU`** est un nouveau champ, séparé : treize chiffres, préfixe
  `384`, même principe de bijection — indépendant de l'identifiant.
- **`NUMERO_SECU_INVALIDE`** cible désormais `NUMERO_SECU`, avec deux
  corruptions possibles : la sentinelle `00000000000000` (identique à ce que
  pose le moteur temps réel) ou une troncature.
- **`PRESTATION_TAUX_REMBOURSEMENT`** vaut `100` (RAM) ou `70` (RGB), plus
  jamais `1.00` / `0.70`. Le calcul de `PRESTATION_MONTANT_RQ` divise
  maintenant par 100 en conséquence.
- **`MONTANT_HORS_BAREME`** (`_taux_hors_bareme`) pose le taux de l'*autre*
  régime — `70` sur du RAM, `100` sur du RGB — exactement la logique de
  `anomalies/config.py:tirer_taux` côté moteur.
- **`PRESTATION_MONTANT_CMU`** renommé **`PRESTATION_MONTANT_RQ`**.
- **`CENTRE_SANTE_CODE`** au format `CSxxx` (trois chiffres), plus un entier
  nu.
- **`DROITS_DATE_DEBUT` / `DROITS_DATE_FIN`** sont maintenant des horodatages
  ISO complets (`2025-01-01T00:00:00+00:00`), pas des dates nues.
- **`DOUBLON_EXACT`** (catalogue) cible désormais `ASSURE_NUMERO_IDENTIFIANT`,
  et non plus `NUMERO_IMMATRICULATION`.
- Le témoin (`temoin/regles.py`) a été mis à jour en miroir : même échelle de
  taux, mêmes deux champs d'identité, et sait désormais lire une date de
  droits horodatée aussi bien qu'une date nue.

**Conséquence assumée** : ce changement casse la reproductibilité des
campagnes déjà générées avant lui — même graine, mais un fichier différent
puisque les colonnes elles-mêmes ont changé. Aucune donnée réelle n'est
concernée, seulement les jeux de test.

---

## Comment vérifier à l'écran

1. Crée une campagne avec quelques anomalies actives, dont
   **Numéro de sécurité sociale invalide** et **Taux étranger au régime**,
   puis génère-la.
2. Dans le corrigé, cherche une ligne de type `NUMERO_SECU_INVALIDE` :
   le champ touché doit être `NUMERO_SECU`, pas un champ d'immatriculation.
3. Télécharge le CSV : la colonne `ASSURE_NUMERO_IDENTIFIANT` commence par
   `CMU`, `NUMERO_SECU` par `384`, `CENTRE_SANTE_CODE` par `CS`, et
   `PRESTATION_TAUX_REMBOURSEMENT` affiche `100.00` ou `70.00` — jamais
   `1.00` ni `0.70`.
4. Transmets la campagne au témoin (bloc M6 de la fiche) : le rapport doit
   détecter les anomalies `NUMERO_SECU_INVALIDE` et `MONTANT_HORS_BAREME`
   que tu as injectées, sur les bons champs.

---

## Fichiers touchés

| Fichier | Nature |
|---|---|
| `campagnes/generateur.py` | Les cinq alignements ci-dessus |
| `anomalies/catalogue.py` | `colonne_cible` de `DOUBLON_EXACT` |
| `temoin/regles.py` | Mise en miroir : taux, champs d'identité, dates de droits |
| `tests/test_campagnes.py`, `tests/test_temoin.py` | Mis à jour en conséquence |

Pas de migration : rien de tout ceci ne touche une table, seulement le
contenu du fichier produit par une campagne.

---

> Non vérifié à l'écran de mon côté — c'est un correctif de fond demandé
> après la recette de M6, pas un nouveau module. Le scénario ci-dessus est à
> dérouler avant de considérer l'alignement acquis.
