# Campagnes de test de la qualité des données

Une **campagne** produit un jeu de données volontairement piégé, le transmet à un outil de qualité des données, puis compare ce que l'outil a trouvé avec ce qu'ÉCHO a réellement posé. Le détail de chaque étape est dans les guides [M1 à M6](guides/).

## Cycle de vie

```text
creee → generation → generee → transmise → rapport_recu → notee
                                   └──────→ echec_echange
```

| Statut | Sens |
|---|---|
| `creee` | La campagne existe : référence `C-AAAA-NNN`, palier, volume, **graine** fixée et visible avant génération |
| `generation` | Le jeu est en cours de production |
| `generee` | Le jeu et le **corrigé** sont prêts |
| `transmise` | Le jeu a été envoyé à l'outil testé |
| `rapport_recu` | L'outil a répondu avec son rapport |
| `notee` | La réponse a été comparée au corrigé |
| `echec_echange` | Silence, rapport malformé ou sans détail (motifs : `silence`, `rapport_malforme`, `rapport_sans_detail`) |

## Paliers de charge

Définis dans `metier/campagnes/paliers.py`. Le volume proposé est un point de départ ajustable ; bornes acceptées : **100 à 5 000 000** lignes. Un code de palier inconnu retombe sur l'échantillon (jamais sur un million de lignes par erreur).

| Palier | Volume proposé | Pour éprouver |
|---|---|---|
| `ECHANTILLON` | 500 | Une vérification rapide après modification |
| `COURANT` | 100 000 | La performance en usage normal |
| `ELEVE` | 500 000 | La tenue en charge à l'échelle de la base CMU |
| `AFFLUX` | 1 000 000 | Un très gros volume d'un seul bloc (enrôlement massif) |

## Les huit dimensions de qualité

Une **famille** dit où l'anomalie est posée ; une **dimension** dit ce qu'elle éprouve chez l'outil testé. La campagne affiche les dimensions (`GET /campagnes/dimensions`).

| Dimension | Exemple |
|---|---|
| Unicité | Deux fiches pour la même personne, à une variation près |
| Complétude | Immatriculation absente, nom vide |
| Validité (format) | Treize chiffres manquants, e-mail mal formé |
| Exactitude (domaine) | Montant négatif, taux étranger au régime |
| Cohérence temporelle | Date de soins antidatée ou postérieure à la facture |
| Intégrité référentielle | Code de prestation ou type d'établissement inexistant |
| Cohérence croisée | Quantité servie sans prescription, soins hors période de droits |
| Conformité technique | « N'Guessan » devenu « N?Guessan » |

## Générateur et corrigé

Le générateur (`campagnes/generateur.py`, `generation.py`) est **déterministe** : même graine, mêmes volumes et mêmes anomalies donnent exactement le même fichier. Le **corrigé** (`TB_CAMPAGNES_CORRIGE`) enregistre chaque anomalie posée (type, ligne, valeur d'origine et valeur faussée) ; il reste côté ÉCHO. Progression : `GET /campagnes/{id}/progression`.

## Export

`GET /campagnes/{id}/export?format=…` — formats `csv`, `xlsx`, `json`, `sql` (`campagnes/export.py`). Le fichier exporté est **marqué** (voir [M4](guides/M4_export_marque.md)) pour que l'outil testé et ÉCHO parlent des mêmes lignes.

## Canal API (M6) et outil témoin

`POST /campagnes/{id}/transmettre` envoie le jeu à l'outil testé en HTTP (`httpx`) et lit sa réponse ; chaque tentative est conservée dans `TB_CAMPAGNES_ECHANGES`. Par défaut la cible est le **témoin** intégré (`/temoin/analyser`).

Garde-fous (`campagnes/echange.py`) :

| Variable | Rôle |
|---|---|
| `ECHO_HOTES_OUTIL_TESTE` | Liste blanche des hôtes que ÉCHO a le droit d'appeler. Toute autre cible est refusée |
| `ECHO_CLE_OUTIL_TESTE` | Clé partagée présentée à l'outil testé, et exigée par `/temoin/*` quand elle est définie |
| `ECHO_TEMOIN_TAILLE_MAX_MIO` | Plafond de l'envoi reçu par le témoin (512 Mio par défaut) |

## Parcours dans le dashboard

Accueil → carte « Qualité des données » → **Nouvelle campagne** (palier, volume, graine) → choix des anomalies → **Générer** → suivi → **Exporter** ou **Transmettre** → lecture du rapport et du corrigé dans la fiche campagne.
