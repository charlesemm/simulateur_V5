# M2 — Le choix des anomalies · guide et scénario de test

> Module 2 sur 8 du [découpage](../../cahier%20des%20charges/Module_Qualite_Donnees_decoupage.md).
> À valider à l'écran.

## En clair

À M1, on créait une campagne mais on ne disait pas **ce qu'elle allait piéger**.
C'est fait : l'écran est devenu l'assistant en trois étapes du cahier des
charges — paramètres de génération, sélection des anomalies, récapitulatif — et
chaque type d'anomalie s'active seul, avec son propre pourcentage.

Une chose nouvelle et importante : les anomalies ne sont plus groupées par
**famille** (montants, dates, identité…) mais par **dimension de qualité**.
La différence n'est pas cosmétique :

- une **famille** dit *où* l'anomalie est posée — dans quelle colonne ;
- une **dimension** dit *ce qu'elle éprouve* chez l'outil testé — sa capacité à
  voir un doublon, une valeur hors domaine, une contradiction entre champs.

C'est le vocabulaire du cahier des charges, et c'est celui que le score de M7
reprendra. Un outil peut très bien exceller sur les montants et être aveugle
aux incohérences croisées : c'est cette lecture-là qu'on veut pouvoir faire.

## Le tableau des dimensions

Les treize types du catalogue ont été rattachés aux huit dimensions du cahier :

| Dimension | Types disponibles |
|---|---|
| Unicité | *aucun — arrive à M5* |
| Complétude | *aucun — arrive à M5* |
| Validité (format) | Numéro de sécurité sociale invalide, adresse électronique invalide |
| Exactitude (domaine) | Montant aberrant, taux hors barème, date de naissance impossible |
| Cohérence temporelle | Date antidatée, date de soins future |
| Intégrité référentielle | Type d'établissement inconnu, prestation orpheline |
| Cohérence croisée | Date hors droits, répartition faussée, quantité excessive, quantité nulle |
| Conformité technique | *aucun — arrive à M5* |

**Cinq dimensions sur huit sont éprouvables aujourd'hui.** Les trois autres sont
affichées quand même, en bas de l'étape 2 : une dimension qu'on croirait testée
alors que rien ne la vise fausserait la lecture du score.

> Un arbitrage à connaître : « date de soins hors période de droits » est
> classée en **Cohérence croisée** et non en Cohérence temporelle. Ce n'est pas
> une date mal formée ni une chronologie impossible — c'est la facture qui
> contredit les droits de l'assuré. À trancher avec l'auteur du cahier si son
> intention était autre.

## Ce qui a été fait

### Côté serveur

| Fichier | Rôle |
|---|---|
| `anomalies/catalogue.py` | Les 8 dimensions (`DIMENSIONS`) et la dimension de chacun des 13 types (`DIMENSION_PAR_CODE`), plus deux propriétés sur `TypeAnomalie` |
| `api/routers/campagnes.py` | `GET /campagnes/dimensions` et `GET /campagnes/anomalies` |
| `campagnes/service.py` | `normaliser_anomalies` (filtre et borne) et `dimensions_couvertes` |
| `api/schema.py` | `POST /campagnes` accepte désormais `anomalies` |

Deux choix à signaler :

- **La dimension vit dans le code, pas en base.** C'est une lecture du
  catalogue, pas un réglage : la modifier en base la ferait diverger du cahier
  des charges sans que personne ne le voie. Aucune migration pour M2.
- **Les types d'une campagne sont servis par `/campagnes/anomalies`**, pas par
  la console d'injection. Une campagne porte ses propres taux ; le réglage de
  la console, qui vaut pour le moteur temps réel, ne doit pas déteindre sur
  elle — ni l'inverse.

### Côté écran

`NouvelleCampagnePage.tsx` devient l'assistant : fil des trois étapes en haut,
tableau par dimension à l'étape 2, récapitulatif complet à l'étape 3. La fiche
de campagne (`CampagnesPage.tsx`) affiche maintenant les anomalies retenues.

---

## Scénario de test

Rappel : si tu es en local, `alembic upgrade head` est déjà passé, il n'y a
**aucune migration** pour M2. Si tu es en conteneur : `podman compose up --build -d`.

### 1. L'assistant apparaît

Accueil → carte **QUALITE**.

- [ ] En haut, un fil de **trois étapes** : « Paramètres de génération »,
      « Sélection des anomalies », « Récapitulatif ». La première est verte.
- [ ] L'étape 1 contient ce que tu connais de M1 : nom, quatre paliers, volume,
      graine.
- [ ] En bas à droite : **Suivant →**. À gauche, **Annuler**.

### 2. Le choix des anomalies

Clique **Suivant →**.

- [ ] La deuxième pastille du fil devient verte, la première passe en « faite ».
- [ ] **Cinq sections** apparaissent, une par dimension pourvue : Validité,
      Exactitude, Cohérence temporelle, Intégrité référentielle, Cohérence
      croisée.
- [ ] Chaque section explique en une phrase ce qu'elle éprouve.
- [ ] Chaque ligne montre le type, **où il frappe** (`TB_FACTURES.FACTURE_DATE_SOINS`
      par exemple) et un taux.
- [ ] **Rien n'est coché au départ.** C'est voulu : une campagne doit dire
      exactement ce qu'elle pose.
- [ ] En haut à droite du titre : « 0 type actif sur 13 ».

Maintenant règle :

- [ ] Coche **Montant aberrant** → le compteur passe à « 1 type actif sur 13 ».
- [ ] Change son taux à **15** → la case reste cochée.
- [ ] Sur une ligne **décochée**, saisis directement un taux (par exemple 3) :
      la case **se coche toute seule**. Saisir un taux sur une ligne éteinte
      perdrait le réglage autrement.
- [ ] Clique **Tout activer** sur « Intégrité référentielle » : ses deux lignes
      se cochent. Le bouton devient **Tout désactiver**.
- [ ] Tout en bas : le rappel que **Unicité, Complétude et Conformité
      technique** n'ont encore aucun injecteur.

### 3. Le récapitulatif

Clique **Suivant →**.

- [ ] Quatre tuiles : palier, graine, types actifs, **dimensions éprouvées
      (x / 8)**.
- [ ] Un tableau « Ce qui sera injecté » avec dimension, type et taux — il doit
      correspondre exactement à ce que tu as coché.
- [ ] Une section « Dimensions hors périmètre » qui nomme celles que cette
      campagne n'éprouvera pas.
- [ ] Le bouton de droite est devenu **Créer la campagne**.

Reviens en arrière pour vérifier que rien ne se perd :

- [ ] **← Précédent** deux fois : tu retrouves l'étape 1 avec ton nom, ton
      palier et ta graine.
- [ ] **Suivant →** deux fois : tes anomalies et tes taux sont toujours là.

### 4. Créer, et retrouver le réglage

- [ ] Clique **Créer la campagne**.
- [ ] Tu arrives sur la liste, la campagne est ouverte en dessous.
- [ ] Sa fiche affiche un tableau **« Anomalies retenues »** : les mêmes types,
      les mêmes taux, avec leur dimension.
- [ ] La phrase en dessous compte les dimensions éprouvées (« 3 dimensions
      éprouvées sur huit »).

### 5. Le cas de la campagne sans anomalie

- [ ] Crée une campagne en ne cochant **rien** du tout.
- [ ] Le récapitulatif l'annonce clairement : le jeu sera sain, et la campagne
      ne mesurera **que les fausses alertes** de l'outil testé.
- [ ] La fiche le redit après création.

Ce n'est pas un cas dégénéré : un outil qui signale des anomalies dans un jeu
sain est un outil qui crie au loup, et c'est une mesure en soi.

### 6. Les gardes-fous

- [ ] Saisis un taux de **0** sur une ligne cochée puis crée la campagne : ce
      type **n'apparaît pas** dans les anomalies retenues. Un type à 0 %
      n'injecte rien ; le garder promettrait une ligne de score toujours vide.
- [ ] Le champ de taux refuse de dépasser 100 et de descendre sous 1.

---

## Ce que M2 ne fait pas encore

- Aucune anomalie n'est **posée** : c'est le générateur de M3.
- Une campagne créée ne se modifie pas encore après coup.
- Les trois dimensions vides attendent leurs injecteurs (M5).

## Vérifications automatiques

`tests/test_campagnes.py` passe de 11 à **20 tests** : réglages rangés avec la
campagne, code inconnu écarté sans tout faire échouer, taux nul non retenu,
dimensions déduites du réglage, chaque type du catalogue rattaché à une
dimension, les trois dimensions vides annoncées comme telles, et le refus d'un
taux hors bornes.

Suite complète : **224 tests verts**, `npm run build` passe.

> Non vérifié à l'écran de mon côté : je n'ai pas de session ouverte dans ton
> navigateur. Le scénario ci-dessus est la recette.
