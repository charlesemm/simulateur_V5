# Module « Qualité des données » — ce qui est demandé

> Lecture du cahier `Simulateur_Module_Test_Qualite_Donnees_v1.docx` (v1).
> Ce document reformule la demande. Il ne propose aucune solution technique et
> ne préjuge d'aucun développement.

## 0. Périmètre

Il s'agit **d'une fonctionnalité d'ÉCHO**, pas d'une refonte d'ÉCHO : le
deuxième type de simulation de l'accueil, aujourd'hui grisé et libellé
« En attente du cahier des charges ». Le cahier est ce cahier des charges.

Les autres types (MDM, Entrepôt, Gouvernance) restent hors sujet, ainsi que le
mode LIBRE, qui continue de fonctionner comme aujourd'hui.

## 1. Ce que la fonctionnalité doit permettre

Répondre à une question : **« l'outil chargé de repérer les erreurs dans nos
données fait-il vraiment bien son travail ? »**

Le principe est celui du devoir piégé et de son corrigé, en quatre temps :

1. ÉCHO fabrique un jeu de données fictif mais réaliste, sur les tables du
   parcours bénéficiaire ;
2. il y insère volontairement des anomalies, par type et par pourcentage
   choisis à l'avance ;
3. comme c'est lui qui les pose, il garde la liste exacte et l'emplacement de
   chaque erreur : c'est **le corrigé** ;
4. le jeu piégé est transmis à **l'outil de qualité des données à tester** ;
   ÉCHO récupère le rapport de cet outil et le compare à son corrigé.

Le point à retenir : **ÉCHO n'est pas le détecteur, il est l'examinateur.**
L'outil qui détecte est un outil extérieur, et c'est lui qu'on note.

## 2. La campagne, unité de base

Tout se rattache à une **campagne de test** : une exécution complète du cycle
ci-dessus, portant un identifiant unique et un horodatage, et regroupant en une
seule unité indivisible et traçable :

- le jeu de données généré ;
- le corrigé associé ;
- les paramètres utilisés : dimensions testées, taux d'anomalies, volume, graine ;
- le rapport reçu de l'outil testé ;
- le résultat du rapprochement.

C'est cette unité qui rend possibles trois usages exigés plus loin : comparer
deux campagnes, rejouer une campagne à l'identique par sa graine, et retrouver
le détail exact d'une campagne réalisée plusieurs semaines auparavant.

## 3. Les anomalies à savoir poser

Chaque type doit pouvoir être **activé ou désactivé indépendamment**, et son
**pourcentage d'injection réglé exactement** (exigences C1 et C2).

### 3.1 Les huit dimensions

| Dimension | Incohérence à tester | Exemple donné (contexte CMU/CNAM) |
|---|---|---|
| Unicité | Doublons stricts et flous | Deux fiches pour la même personne, variation orthographique (« N'Guessan » vs « Nguessan ») ou même numéro d'immatriculation (13 chiffres) |
| Complétude | Champs obligatoires manquants | Numéro d'immatriculation absent d'une fiche bénéficiaire ; nom de famille vide sur une ligne de décompte |
| Validité (format) | Formats hors normes, règles syntaxiques | Téléphone à moins de 10 chiffres ; RCCM ou compte contribuable mal structuré ; immatriculation qui n'a pas 13 chiffres |
| Exactitude (domaine) | Valeurs hors limites, aberrations | Montant remboursé négatif ; taux de prise en charge à 100 % pour un bénéficiaire RGB, alors que le RGB plafonne à 70 % (ticket modérateur) et que seul le RAM ouvre 100 % |
| Cohérence temporelle | Séquences illogiques | Date de liquidation antérieure à la feuille de soins ; première prestation moins d'un mois après l'affiliation, alors que le délai de carence CMU est d'un mois |
| Intégrité référentielle | Rupture de liens inter-tables | Prestation attribuée à un professionnel de santé dont le code n'existe nulle part ; affiliation rattachée à un OGD inconnu (CNPS, CGRAE, mutuelle…) |
| Cohérence croisée | Contradiction logique entre champs | Régime RAM (non contributif) alors qu'une cotisation employeur existe ; droits « Actif » alors que la date de radiation est passée |
| Conformité technique | Altération de caractères, encodage | « N'Guessan » devenu `N&#39;Guessan` ou `N?Guessan` à l'import |

### 3.2 Les types nommés dans la maquette d'écran

L'écran « Nouvelle campagne — sélection des anomalies » liste des types
identifiés B1 à B11, chacun avec son taux et son état actif/inactif :

| ID | Type | Exemple de réglage montré |
|---|---|---|
| B1 | Doublons exacts | 5 %, actif |
| B2 | Doublons approximatifs (fuzzy) | 3 %, actif |
| B3 | Champs obligatoires vides | 4 %, actif |
| B4 | Formats de date incohérents | inactif |
| B6 | Caractères spéciaux et encodages | 2 %, actif |
| B7 | Valeurs hors liste autorisée | inactif |
| B8 | Références brisées (intégrité référentielle) | 1 %, actif |
| B9 | Incohérences logiques inter-champs | inactif |
| B11 | Tentatives d'injection basique | 1 %, actif |

**B5 et B10 ne sont pas nommés dans le document.** À faire préciser.

## 4. L'échange avec l'outil testé

### 4.1 Envoi du jeu piégé

ÉCHO **ne modifie pas le fonctionnement de l'outil testé** : il lui transmet le
jeu par le canal que cet outil utilise déjà en production. Deux modes doivent
être possibles, ÉCHO s'adaptant à ce que l'outil impose :

| Mode | Fonctionnement | Quand |
|---|---|---|
| Poussé (push) | ÉCHO dépose le fichier ou appelle l'API d'entrée de l'outil | L'outil expose un point d'entrée standard (dossier surveillé, API d'import) |
| À la demande (pull) | ÉCHO met le jeu à disposition dans un emplacement partagé, l'outil vient le chercher à sa fréquence | L'outil fonctionne par cycles planifiés (traitement de nuit, import périodique) |

Formats de fichier : **CSV, Excel, JSON ou script d'insertion SQL** — celui qui
correspond au canal réel de l'outil, pas un format imposé.

### 4.2 Marquage des données de test

Chaque enregistrement envoyé porte un **marquage systématique et non
désactivable** indiquant qu'il s'agit d'une donnée fictive. Ce marquage doit
suivre la donnée **même après son passage dans l'outil testé** : ni les
journaux, ni les tableaux de bord, ni les exports de cet outil ne doivent
pouvoir confondre une donnée de test avec une donnée réelle.

### 4.3 Réception du rapport

ÉCHO récupère le rapport de l'outil testé par le même canal qu'à l'envoi. Pour
que la comparaison soit possible, ce rapport doit permettre d'identifier, pour
chaque anomalie signalée, au minimum :

- la ligne concernée ;
- le champ concerné ;
- le type d'anomalie signalé.

Si l'outil testé ne produit qu'un score global sans détail ligne par ligne,
**aucune mesure fiable n'est possible** : c'est une information sur l'outil, à
documenter, pas à contourner.

### 4.4 Rapprochement automatique

Le rapport reçu est confronté au corrigé, ligne par ligne :

| Cas | Comptage |
|---|---|
| Anomalie du corrigé retrouvée dans le rapport | Vrai positif (détection réussie) |
| Anomalie du corrigé absente du rapport | Faux négatif (anomalie manquée) |
| Anomalie signalée mais absente du corrigé | Faux positif (fausse alerte) |

Deux indicateurs sont affichés :

- **Taux de rappel (sensibilité)** = vrais positifs ÷ total des erreurs injectées ;
- **Taux de précision** = vrais positifs ÷ total des alertes levées.

L'écran de résultats montre le score global de la campagne, puis un détail
**par type d'anomalie** : injectées, vrais positifs, faux négatifs, faux positifs.

### 4.5 Robustesse de l'échange

Deux situations doivent être traitées pour elles-mêmes, sans les confondre avec
un mauvais score de l'outil testé :

- **l'outil ne répond pas** dans un délai raisonnable → afficher un échec
  d'échange, surtout pas un taux de détection de 0 %, et conserver la trace de
  la tentative ;
- **le rapport revient malformé ou incomplet** → signaler l'anomalie d'échange
  plutôt que tenter une comparaison partielle, qui produirait une mesure fausse.

Chaque échange, envoi comme réception, est **horodaté et conservé** : la
campagne doit rester intégralement traçable en cas de litige sur la performance
réelle de l'outil testé.

## 5. Banc d'essai et rejouabilité

### 5.1 Paliers de charge

ÉCHO doit générer des volumes variables à la demande, de quelques centaines de
lignes à plusieurs millions :

| Palier | Volume | Ce qu'il vérifie |
|---|---|---|
| Échantillon | Quelques centaines de lignes | Vérification rapide après une modification |
| Volume courant | Représentatif du réel (ex. 100 000 bénéficiaires) | Performance en usage normal |
| Volume élevé | Plusieurs centaines de milliers à un million | Tenue à l'échelle de la base CMU complète |
| Afflux soudain | Très gros volume transmis d'un bloc | Comportement face à un pic (enrôlement massif) |

À chaque palier, ÉCHO **mesure et conserve** le temps mis par l'outil testé pour
rendre son rapport, et si la qualité de détection se maintient ou se dégrade
quand le volume augmente. Un outil qui détecte 96 % sur 1 000 lignes et 80 % sur
500 000 n'est pas fiable à l'échelle réelle.

### 5.2 La graine

Chaque campagne peut être lancée avec une **graine** (seed) qui détermine
entièrement le jeu produit : mêmes enregistrements, mêmes anomalies, aux mêmes
emplacements. Rejouer la même graine doit reproduire un jeu **strictement
identique, à l'octet près**. L'écran de lancement propose « graine aléatoire »
ou « graine spécifique ».

Sans graine, deux campagnes ne sont pas comparables : une différence de
résultat pourrait venir du jeu de données plutôt que de l'outil testé.

Quatre usages l'exigent : comparer deux versions d'un même outil, reproduire un
problème signalé, auditer une campagne passée, et vérifier la non-régression.

### 5.3 Robustesse du banc d'essai

- **Interruption pendant la génération d'un gros volume** → reprendre proprement
  où elle s'est arrêtée, jamais produire un jeu à moitié généré et
  silencieusement incomplet.
- **Saturation de l'outil testé sous charge** → le signaler comme *limite de
  charge atteinte*, qui est une information en soi, et non comme un échec du
  test à corriger.

## 6. Écrans attendus (donnés à titre indicatif)

1. **Nouvelle campagne** en trois étapes : paramètres de génération → sélection
   des anomalies (liste B1–B11 avec taux et état) → récapitulatif.
2. **Lancer un test de charge** : choix du palier, graine aléatoire ou
   spécifique.
3. **Résultats de campagne** : rappel, précision, vrais positifs sur total, puis
   le tableau par type d'anomalie.

## 7. Points tranchés le 2026-08-28

1. **L'outil testé n'est pas encore connu**, mais l'échange se fera **par API**,
   dans les deux sens : envoi du jeu et réception du rapport. Le mode « à la
   demande » (dépôt de fichier repris par lots) n'est donc pas le cas nominal ;
   le canal se conçoit comme un appel d'API vers un point d'entrée à paramétrer,
   l'outil précis restant inconnu.
2. **B5 et B10 sont volontairement absents.** Ce ne sont pas des oublis : la
   numérotation saute, il n'y a rien à leur demander.
3. **Les tables de cotisations, paiements, OGD, RCCM, compte contribuable, date
   de liquidation et délai de carence ne sont pas encore intégrées à ÉCHO**, et
   le parcours métier correspondant reste à documenter. Le module se construit
   **sans les attendre**, sur le périmètre actuel (assurés, droits, factures,
   prestations, ententes préalables, centres et professionnels de santé,
   référentiels). Les dimensions concernées sont donc livrées **partiellement**,
   et complétées quand ces tables arriveront — voir le tableau ci-dessous.
4. **La rejouabilité porte sur le fichier exporté**, pas sur la base générée.
   Deux campagnes lancées avec la même graine doivent produire deux fichiers
   identiques à l'octet près ; l'état interne de la base n'est pas concerné par
   cette exigence.

### 7.1 Couverture des huit dimensions sur le périmètre actuel

| Dimension | Constructible aujourd'hui | Ce qui attend les tables manquantes |
|---|---|---|
| Unicité | Oui, entièrement | — |
| Complétude | Oui, entièrement | — |
| Validité (format) | Oui : numéro d'immatriculation, adresse électronique | Téléphone (aucun champ dans le modèle), RCCM, compte contribuable |
| Exactitude (domaine) | Oui, entièrement (montants, taux RGB/RAM) | — |
| Cohérence temporelle | Partiel : date de soins hors période de droits, date antidatée, date future | Date de liquidation, délai de carence d'un mois après affiliation |
| Intégrité référentielle | Oui : prestation, type de centre, professionnel de santé, centre | OGD |
| Cohérence croisée | Partiel : droits actifs alors que la période est close | Régime RAM contredit par une cotisation employeur |
| Conformité technique | Oui, entièrement (anomalie de fichier, indépendante du modèle) | — |

Cinq dimensions sur huit sont couvrables intégralement dès maintenant, et deux
le sont pour moitié. Aucune n'est bloquée.

## Annexe — ce dont ÉCHO dispose déjà pour cette fonctionnalité

Repères de lecture, sans engagement de conception :

| Demande | Existant dans ÉCHO |
|---|---|
| Le corrigé (liste et emplacement des erreurs posées) | `TB_ANOMALIES_INJECTIONS` : type, cible, valeur d'origine, valeur injectée, par exécution |
| Campagne tracée et horodatée avec ses paramètres | `TB_SIMULATIONS` |
| Activation et taux par type d'anomalie | Catalogue de 13 types (`TB_REF_ANOMALIES`) + écran de lancement |
| Doublons approximatifs, variations orthographiques | Générateur d'identités jumelles du module `mdm/` |
| Exports | CSV et Excel |
| Règle RGB 70 % / RAM 100 % | Modélisée dans les régimes |
| Graine de génération | Existe dans la configuration du moteur, valeur fixe |

Ce qui relève de l'échange avec un outil extérieur — envoi, marquage, réception
du rapport, rapprochement, rappel et précision, paliers de charge — n'a
aujourd'hui aucun équivalent.
