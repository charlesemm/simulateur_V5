# Moteur de simulation, anomalies et aléas

## Les cinq types de simulation

Définis dans `src/echo/moteur/simulation/profils.py` et servis par `GET /simulation/profils`. Chaque profil règle la vitesse de départ, le nombre de passages simultanés, les anomalies et aléas préconfigurés, et une préparation éventuelle.

| Code | Libellé | Parcours | Usage |
|---|---|---|---|
| `LIBRE` | Simulation libre | Moteur temps réel | Bac à sable : aucune anomalie préconfigurée, on compose à la main et on déclenche les aléas depuis le cockpit |
| `QUALITE` | Qualité des données | Campagne | Mène aux campagnes de test (voir [CAMPAGNES_QUALITE.md](CAMPAGNES_QUALITE.md)) |
| `MDM` | Rapprochement d'identités | aucun (en attente) | Réglage défini ; carte grisée tant que le cahier des charges n'est pas livré. Le moteur MDM existe côté API |
| `ENTREPOT` | Entrepôt de données | aucun (en attente) | Idem ; `POST /entrepot/historique` existe côté API |
| `GOUVERNANCE` | Gouvernance | aucun (en attente) | Idem ; les routes `/gouvernance/*` existent côté API |

Seuls `LIBRE` et `QUALITE` sont aujourd'hui ouverts (`disponible=True`). Le serveur dit quels types sont ouverts (`disponible`) et où mène chaque carte (`parcours` : `moteur` ou `campagne`) : le navigateur ne code rien en dur.

## Le moteur temps réel

Code : `src/echo/moteur/simulation/`.

- `engine.py` — `SimulationEngine` : lance les passages à la cadence voulue, borne la concurrence par un sémaphore asyncio.
- `passage.py` — `PassageSimulation` : un parcours de soins complet.
- `profils.py`, `aleas.py`, `commandes.py` — réglages, pannes, commandes de l'opérateur.
- `runs.py` — enregistrement des exécutions ; `purge.py` — suppression des données d'une exécution.
- `inscription.py` — inscription d'un assuré neuf pour porter une anomalie d'identité.
- `src/echo/web/api/services/simulation_manager.py` — pilote le moteur pour l'API (démarrer, arrêter, vitesse, état).

### Déroulement d'un passage

1. **Accueil** : tirage d'un assuré et vérification de ses droits. Si les droits sont fermés, le passage est refusé (`passage.refuse`, ligne dans `TB_REFUS_ACCUEIL`).
2. **Facture** : création (`facture.creee`), pathologies (`facture.pathologies`).
3. **Prestations** : actes servis au tarif du réseau de soins (`prestation.servie`), montants tirés autour du tarif.
4. **Médicaments** : prescription et retrait (`medicament.prescrit`, `medicament.retire`).
5. **Entente préalable** si l'acte l'exige (`entente.creee`, puis `entente.traitee`).
6. **Statuts** de la facture au fil du parcours (`facture.statut`).

Tous les tirages passent par un générateur aléatoire ensemencé : une exécution est rejouable à l'identique.

### Vitesse et cadence

La vitesse accélère l'horloge simulée (de ×1 jusqu'à ×3600). `GET /simulation/cadence` donne la cadence effective ; `POST /simulation/speed` la change en cours de route. La contre-pression est gérée : si le consommateur ne suit plus, le moteur ralentit au lieu d'accumuler.

## Anomalies

Une anomalie **fausse une valeur**. Catalogue : `src/echo/metier/anomalies/catalogue.py`, persisté dans `TB_REF_ANOMALIES` (la base fait foi après le premier peuplement).

### Types

| Famille | Types |
|---|---|
| Montants | `MONTANT_ABERRANT`, `MONTANT_HORS_BAREME`, `REPARTITION_FAUSSEE` |
| Dates | `DATE_ANTIDATEE`, `DATE_SOINS_FUTURE`, `DATE_HORS_DROITS`, `DATE_NAISSANCE_ABERRANTE` |
| Quantités | `QUANTITE_EXCESSIVE`, `QUANTITE_NULLE` |
| Identité | `NUMERO_SECU_INVALIDE`, `DOUBLON_EXACT`, `DOUBLON_APPROCHANT`, `CHAMP_OBLIGATOIRE_VIDE`, `TENTATIVE_INJECTION` |
| Format | `EMAIL_INVALIDE`, `ENCODAGE_CASSE`, `FORMAT_DATE_INCOHERENT` |
| Référentiel | `TYPE_CENTRE_INCONNU`, `PRESTATION_ORPHELINE` |

Chaque type porte : famille, dimension de qualité, cible, **sévérité** (`douce` : passe les contraintes SQL mais ment sur le métier ; `dure` : manifestement invalide), interrupteur, taux et moment d'entrée en scène.

**Portée** : la plupart des types valent partout. `FORMAT_DATE_INCOHERENT` n'est possible qu'en campagne (le moteur écrit en base, la colonne est typée `date`).

### Déclenchement

| Mode | Effet |
|---|---|
| `continu` | Pendant toute l'exécution |
| `demarrage` | Seulement pendant la fenêtre initiale |
| `differe` | Rien avant le délai, puis jusqu'à la fin |
| `manuel` | Rien tant que l'opérateur ne l'arme en cours de route |

### Règle d'or du catalogue

Les nouveaux types s'ajoutent **toujours en fin de liste**. L'ordre du catalogue fixe l'ordre des tirages : insérer au milieu changerait tous les fichiers déjà produits à graine constante. Les codes nomment aussi les lignes du journal : ne pas les renommer sans migration.

### Réglage

Via le dashboard (écran Lancement, console d'injection) ou l'API : `PATCH /anomalies/catalogue/{code}`, `PATCH /anomalies`, `POST /anomalies/reset`. Le journal des injections est lisible sur `GET /anomalies/journal`. Variables de démarrage : `ANOMALIES_ENABLED`, `ANOMALIES_RATE`.

## Aléas

Un aléa **maltraite le déroulement** (crash tests) : il révèle si les données restent cohérentes quand tout ne se passe pas bien. Chacun est réglable par probabilité, déclenchable à la main, journalisé et rejouable.

| Aléa | Nature | Effet | Réglages par défaut |
|---|---|---|---|
| `COUPURE_BRUTALE` | Interruption | Le moteur s'arrête au milieu d'un passage : facture ouverte, sans prestation ni clôture | probabilité |
| `PERTE_CONNEXION` | Interruption | Une écriture échoue franchement, le passage est perdu | probabilité |
| `RAFALE` | Charge | Une salve de passages part d'un coup | probabilité, taille (25) |
| `BASE_RALENTIE` | Charge | Chaque écriture attend, comme une base saturée | probabilité, latence (0,5 s) |
| `HORLOGE_DECALEE` | Dérive | L'horloge du passage part en avant ou en arrière | probabilité, amplitude (72 h) |
| `SATURATION_MEMOIRE` | Dérive | Le processus retient de la mémoire le temps du passage | probabilité, Mo (50) |

Tous sont à l'arrêt par défaut. Déclenchement manuel : `POST /simulation/commandes`. Liste et réglages : `GET /simulation/aleas`.

## Autres moteurs

- **MDM** (`metier/mdm/`) : génère des paires d'identités (mêmes personnes, variations d'écriture) avec une **vérité terrain** ; `POST /mdm/evaluer` note un rapprochement soumis.
- **Entrepôt** (`metier/entrepot/`) : `POST /entrepot/historique` génère un historique. Les types de centre BIO et HOS sont toujours présents, les autres une fois sur trois environ.
- **Gouvernance** (`metier/gouvernance/`) : catalogue des tables, inventaire, volumétrie, panorama (JSON ou Markdown), provenance des données et rapport.
- **KPI** (`metier/kpi/`) : agrège les événements du bus et alimente `/kpi/snapshot` et le temps réel.
- **Qualité** (`metier/qualite/`) : règles de contrôle et rapport comparant anomalies demandées, injectées et détectées.
