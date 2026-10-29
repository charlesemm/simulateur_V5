# Référence de l'API

Documentation interactive : `/docs` (Swagger) et `/redoc`, schéma sur `/openapi.json`. Le dashboard propose aussi un **Explorateur API** qui joint le jeton à chaque appel.

> En production, positionner `ECHO_DOCS_PUBLIQUES=false` : `/docs` et `/redoc` répondent alors 404 et `/openapi.json` exige un jeton (rôle observateur minimum).

## Conventions

- **Authentification** : `Authorization: Bearer <jeton>`, obtenu par `POST /auth/login`.
- **Rôles** : `observateur` (lecture) < `operateur` (pilotage) < `administrateur` (comptes, configuration, purge). Les rôles ci-dessous sont les minimums requis.
- **Langue** : routes, champs et messages sont en français.
- Les codes d'erreur usuels : `401` jeton absent ou refusé, `403` rôle insuffisant, `404` introuvable, `422` validation, `429` trop de tentatives de connexion.
- Cette page est un guide ; **le schéma OpenAPI fait foi** pour les corps de requête et de réponse.

## Technique (publique)

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/` | Dashboard compilé, ou message d'orientation si absent |
| GET | `/health` | Aucun — confirme que le processus répond (ne touche pas la base) |

## Authentification — `/auth`

| Méthode | Route | Rôle | Description |
|---|---|---|---|
| POST | `/auth/login` | public | Échange identifiant + mot de passe contre un jeton. Freiné après 8 échecs / 5 min par identifiant (30 par adresse source) |
| POST | `/auth/change-password` | tout compte connecté | Change le mot de passe ; seule route ouverte à un compte sous mot de passe temporaire |

## Comptes — `/users` (administrateur)

| Méthode | Route | Description |
|---|---|---|
| GET | `/users` | Liste des comptes |
| POST | `/users` | Crée un compte (mot de passe temporaire généré) |
| PATCH | `/users/{utilisateur_uuid}` | Modifie rôle, statut actif, nom |
| POST | `/users/{utilisateur_uuid}/reinitialiser-mot-de-passe` | Génère un nouveau mot de passe temporaire |

## Simulation — `/simulation`

| Méthode | Route | Rôle | Description |
|---|---|---|---|
| POST | `/simulation/start` | opérateur | Démarre une exécution (202) |
| POST | `/simulation/stop` | opérateur | Arrête l'exécution |
| POST | `/simulation/speed` | opérateur | Change la vitesse |
| GET | `/simulation/status` | observateur | État courant |
| GET | `/simulation/profils` | observateur | Les cinq types de simulation et leurs réglages |
| GET | `/simulation/cadence` | observateur | Cadence du moteur |
| GET | `/simulation/aleas` | observateur | Aléas disponibles et réglages |
| POST | `/simulation/commandes` | opérateur | Déclenche un aléa ou arme une anomalie en cours d'exécution |
| GET | `/simulation/executions` | observateur | Historique des exécutions |
| GET | `/simulation/executions/{id}` | observateur | Détail d'une exécution |
| GET | `/simulation/executions/{id}/refus` | observateur | Registre des refus d'accueil |
| GET | `/simulation/executions/{id}/purge` | administrateur | Aperçu de ce qu'une purge supprimerait |
| DELETE | `/simulation/executions/{id}/donnees` | administrateur | Purge les données d'une exécution |

## Données métier (observateur)

| Méthode | Route | Description |
|---|---|---|
| GET | `/factures` | Liste paginée/filtrée des factures |
| GET | `/factures/{facture_numero}` | Détail d'une facture |
| GET | `/factures/{facture_numero}/parcours` | Parcours de la facture |
| GET | `/parcours/{passage_id}` | Parcours d'un passage |
| GET | `/centres-sante` | Centres de santé |
| GET | `/assures` | Recherche d'assurés |
| GET | `/assures/{personne_uuid}` | Fiche d'un assuré |
| GET | `/kpi/snapshot` | Instantané des indicateurs |
| GET | `/kpi/{kpi_name}/history` | Historique d'un indicateur |

## Anomalies — `/anomalies` (administrateur)

| Méthode | Route | Description |
|---|---|---|
| GET / PATCH | `/anomalies` | Lit / modifie la configuration d'injection |
| POST | `/anomalies/reset` | Réinitialise la configuration et le compteur |
| GET | `/anomalies/catalogue` | Types d'anomalies |
| PATCH | `/anomalies/catalogue/{code}` | Règle un type (interrupteur, taux, déclenchement, délai) |
| GET | `/anomalies/familles` | Les six familles |
| GET | `/anomalies/journal` | Journal des injections |

## Qualité — `/qualite` (observateur)

| Méthode | Route | Description |
|---|---|---|
| GET | `/qualite/regles` | Règles de contrôle |
| GET | `/qualite/rapport` | Compare anomalies demandées, injectées et détectées |

## Campagnes de test — `/campagnes`

| Méthode | Route | Description |
|---|---|---|
| GET | `/campagnes/paliers` | Les quatre paliers de charge |
| GET | `/campagnes/formats` | Formats d'export : csv, xlsx, json, sql |
| GET | `/campagnes/statuts` | Statuts du cycle de vie |
| GET | `/campagnes/motifs-echec` | Motifs d'échec d'un échange |
| GET | `/campagnes/dimensions` | Les huit dimensions de qualité |
| GET | `/campagnes/anomalies` | Types d'anomalies disponibles pour une campagne |
| GET | `/campagnes/prochaine-reference` | Prochain numéro `C-AAAA-NNN` |
| POST | `/campagnes` | Crée une campagne |
| GET | `/campagnes` | Liste |
| GET | `/campagnes/{id}` | Détail |
| POST | `/campagnes/{id}/generer` | Lance la génération |
| GET | `/campagnes/{id}/progression` | Avancement de la génération |
| GET | `/campagnes/{id}/corrige` | Le corrigé (anomalies posées) |
| GET | `/campagnes/{id}/export` | Télécharge le jeu dans un format |
| POST | `/campagnes/{id}/transmettre` | Envoie le jeu à l'outil testé (ou au témoin) |
| GET | `/campagnes/{id}/echanges` | Historique des échanges |

## Témoin — `/temoin`

| Méthode | Route | Description |
|---|---|---|
| POST | `/temoin/analyser` | Analyse un fichier reçu, renvoie le rapport complet |
| POST | `/temoin/analyser-resume` | Variante abrégée |

Protégé par une clé partagée si `ECHO_CLE_OUTIL_TESTE` est définie.

## Moteurs complémentaires

| Méthode | Route | Rôle | Description |
|---|---|---|---|
| POST | `/mdm/generer` | opérateur | Génère des paires d'identités à rapprocher |
| GET | `/mdm/verite-terrain` | observateur | Vérité terrain des paires |
| GET | `/mdm/variations` | observateur | Variations appliquées |
| POST | `/mdm/evaluer` | observateur | Évalue un rapprochement soumis |
| POST | `/entrepot/historique` | opérateur | Génère un historique pour l'entrepôt |
| GET | `/gouvernance/catalogue` | observateur | Catalogue des tables |
| GET | `/gouvernance/inventaire` | observateur | Inventaire |
| GET | `/gouvernance/volumetrie` | observateur | Volumétrie |
| GET | `/gouvernance/panorama` | observateur | Panorama (JSON) |
| GET | `/gouvernance/panorama.md` | observateur | Panorama (Markdown) |
| GET | `/gouvernance/provenance` | observateur | Provenance des données |
| GET | `/gouvernance/rapport` | observateur | Rapport de gouvernance |

## Rapports — `/reports` (opérateur)

| Méthode | Route | Description |
|---|---|---|
| GET | `/reports` | Liste des fichiers générés |
| GET | `/reports/executions` | Exécutions exportables |
| POST | `/reports/generate` | Génère les rapports du jour |
| POST | `/reports/periode` | Génère pour une période |
| POST | `/reports/execution/{simulation_id}` | Génère pour une exécution |
| GET | `/reports/{nom_fichier}` | Télécharge un fichier |
| DELETE | `/reports` | Supprime les rapports (administrateur) |

Un job planifié génère chaque nuit à 00h00 le PDF et l'export Excel de la veille.

## Métriques techniques — `/metrics`

| Méthode | Route | Rôle | Description |
|---|---|---|---|
| GET | `/metrics/technical` | observateur | Latence API, concurrence, mémoire, clients Socket.IO, état du moteur |
| POST | `/metrics/technical/reset` | opérateur | Remet les compteurs à zéro |

## Temps réel — Socket.IO

- Chemin : `/socket.io`, namespace **`/kpi`**.
- **Connexion** : fournir `auth: { token: "<jeton>" }`. Refus si jeton absent/invalide, compte désactivé, ou mot de passe temporaire non changé.
- **Serveur → client** : `kpi:snapshot` à la connexion, puis les mises à jour de KPI et du parcours des passages.
- **Client → serveur** : `kpi:subscribe` avec `{ "centre_sante_code": "..." }` pour rejoindre la room `centre:<code>`.

## Événements du bus interne

Publiés par le moteur pendant un passage : `facture.creee`, `facture.statut`, `facture.pathologies`, `prestation.servie`, `medicament.prescrit`, `medicament.retire`, `entente.creee`, `entente.traitee`, `passage.refuse`, `alea.interruption`, `alea.horloge_decalee`, `alea.saturation_memoire`, `alea.base_ralentie`. Ils sont aussi journalisés dans `TB_EVENEMENTS_METIER`.
