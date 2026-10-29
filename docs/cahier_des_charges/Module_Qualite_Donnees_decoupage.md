# Module « Qualité des données » — découpage en modules livrables

> Suite de [Module_Qualite_Donnees_ce_qui_est_demande.md](Module_Qualite_Donnees_ce_qui_est_demande.md).
> Règle de ce découpage : **chaque module se termine par un écran testable à
> l'œil**, dans l'application, pas par une suite de tests dans le terminal.
> Un module qui ne se voit pas n'est pas un module : il est fondu dans le
> suivant.

## Décisions de conception actées le 2026-08-28

1. **Le jeu de données d'une campagne est produit par un générateur en lot**,
   séquentiel et graîné de bout en bout — pas par le moteur temps réel. Celui-ci
   est concurrent, daté sur l'horloge réelle et tire une partie de son hasard
   côté PostgreSQL : deux exécutions de même graine ne donneraient jamais le même
   fichier. Le générateur réutilise les injecteurs d'anomalies existants, pas le
   moteur de passages.
2. **La campagne a sa propre table.** Elle n'a ni vitesse ni passages
   simultanés ; elle a un volume, une graine, un fichier, un corrigé, un rapport
   reçu et un score. La confondre avec une exécution de simulation mélangerait
   deux objets qui ne se ressemblent qu'en surface.
3. **L'outil testé est inconnu mais parlera par API.** On écrit le contrat
   d'échange d'abord, et un adaptateur mince derrière. En attendant le vrai
   outil, ÉCHO se teste lui-même : ses 19 règles de qualité sont exposées
   derrière ce même contrat et jouent l'**outil témoin**.
4. **La rejouabilité porte sur le fichier exporté** : même graine, même fichier,
   à l'octet près.

## Vue d'ensemble

| # | Module | Ce que tu vois à la fin |
|---|---|---|
| M1 | La campagne existe | La carte « Qualité des données » n'est plus grise ; je crée une campagne et je la retrouve dans une liste |
| M2 | Choix des anomalies | Le parcours en trois étapes du cahier, avec taux par type et récapitulatif |
| M3 | Génération et corrigé | Le compteur monte, puis je consulte le corrigé ligne par ligne |
| M4 | Export marqué | Je télécharge le fichier, je l'ouvre, chaque ligne porte son marquage |
| M5 | Les anomalies manquantes | Les nouvelles familles apparaissent dans l'écran de choix et dans le corrigé |
| M6 | Le canal API | Je transmets à l'outil témoin et je vois son rapport revenir, horodaté |
| M7 | Le score | Rappel, précision, et le détail des anomalies manquées |
| M8 | Le banc d'essai | Je lance deux paliers et je compare leurs scores |

M1 à M4 ne dépendent d'aucun outil extérieur. M6 et M7 se valident contre
l'outil témoin. M8 est le seul qui demande du temps machine.

---

## M1 — La campagne existe et se lance

**Objectif** : faire exister l'objet campagne et dégriser l'entrée.

- Table des campagnes : identifiant, libellé, graine, palier ou volume visé,
  périmètre de dimensions, statut, horodatages de création et de fin.
- Le serveur déclare lui-même quels types de simulation sont disponibles
  (le grisage est aujourd'hui écrit en dur dans l'écran d'accueil).
- Écran « Nouvelle campagne », étape 1 : nom, volume, graine aléatoire ou
  saisie.
- Écran « Campagnes » : la liste, avec pour chacune sa graine et son statut.

**Test visuel** : je clique la carte Qualité des données, je crée une campagne,
je la retrouve dans la liste avec sa graine affichée. Rien n'est encore généré.

## M2 — Le choix des anomalies

**Objectif** : le parcours de création complet, tel que le cahier le dessine.

- Étape 2 : la liste des types, chacun activable et réglable en pourcentage,
  groupés par dimension.
- Étape 3 : récapitulatif avant lancement — ce qui sera injecté, et à quel taux.
- Les réglages valent pour la seule campagne : le catalogue en base n'est pas
  réécrit.

**Test visuel** : je coche, je règle des taux, et le récapitulatif dit
exactement ce qui sera posé. Je peux revenir en arrière sans rien perdre.

## M3 — Le générateur en lot et le corrigé

**Objectif** : produire le jeu piégé, et son corrigé, de façon reproductible.

- Générateur séquentiel graîné : mêmes lignes, mêmes anomalies, mêmes
  emplacements pour une même graine.
- Corrigé : pour chaque anomalie posée, la ligne, le champ, le type, la valeur
  d'origine et la valeur injectée.
- Empreinte du jeu produit, affichée sur la campagne.

**Test visuel** : je lance la génération, je vois la progression, puis je
consulte le corrigé dans un tableau. Je relance une seconde campagne avec la
**même graine** : les deux empreintes affichées sont identiques. C'est la preuve
de la rejouabilité, visible sans ouvrir un terminal.

## M4 — L'export marqué

**Objectif** : le fichier que l'outil testé recevra.

- Formats : CSV et Excel existent, JSON et script SQL à ajouter.
- Marquage systématique et non désactivable de chaque enregistrement comme
  donnée fictive, avec l'identifiant de campagne.

**Test visuel** : je télécharge le jeu au format de mon choix, je l'ouvre, et
chaque ligne porte son marquage. Deux téléchargements de la même campagne
donnent deux fichiers identiques.

## M5 — Les anomalies qui manquent au catalogue

**Objectif** : couvrir les huit dimensions du cahier sur le périmètre actuel.

- Doublons exacts et approximatifs (le générateur d'identités jumelles du
  module MDM ressert ici).
- Champs obligatoires vides.
- Caractères cassés et encodage — **anomalie de fichier** : elle ne peut pas
  exister dans une colonne typée, elle s'injecte à l'écriture de l'export.
- Formats de date incohérents — également à l'écriture du fichier.
- Tentatives d'injection basique.

**Test visuel** : les nouvelles familles apparaissent dans l'écran de choix, et
je les retrouve dans le corrigé après génération.

## M6 — Le canal API

**Objectif** : l'échange avec l'outil testé, et sa traçabilité.

- Contrat d'envoi et contrat de rapport : ligne, champ, type d'anomalie.
- Adresse de l'outil à paramétrer ; adaptateur isolé pour que le vrai outil ne
  coûte qu'un branchement.
- Outil témoin : les 19 règles de qualité d'ÉCHO exposées derrière le même
  contrat.
- Chaque envoi et chaque réception horodatés et conservés.
- Les trois échecs d'échange traités pour eux-mêmes : silence de l'outil,
  rapport malformé, rapport sans détail ligne par ligne. Aucun ne doit ressembler
  à un score de 0 %.

**Test visuel** : je transmets une campagne à l'outil témoin, je vois l'envoi
puis la réception apparaître, horodatés. Je coupe volontairement l'outil témoin
et je relance : l'écran dit « échec d'échange », pas « 0 % détecté ».

## M7 — Le rapprochement et le score

**Objectif** : la note de l'outil testé.

- Confrontation ligne à ligne du rapport reçu et du corrigé.
- Vrais positifs, faux négatifs, faux positifs.
- Taux de rappel et taux de précision, global et par type d'anomalie.
- Mention explicite des dimensions présentes dans la campagne : deux campagnes
  de périmètres différents ne se comparent pas.

**Test visuel** : l'écran Résultats affiche le score de la campagne et le
tableau par type. J'ouvre les faux négatifs et je vois quelles lignes précises
l'outil a manquées.

## M8 — Le banc d'essai

**Objectif** : la tenue en charge et la comparaison entre campagnes.

- Les quatre paliers : échantillon, volume courant, volume élevé, afflux soudain.
- Mesure du temps mis par l'outil testé pour rendre son rapport.
- Suivi de la dégradation : le rappel se maintient-il quand le volume monte ?
- Reprise propre après interruption d'une grosse génération.
- Saturation de l'outil testé signalée comme limite de charge atteinte, pas
  comme un échec du test.

**Test visuel** : je lance un palier échantillon puis un palier élevé avec la
même graine, et je compare les deux scores sur un même écran.

---

## Ce que ce découpage laisse dehors

- Les tables non encore intégrées (cotisations, paiements, OGD, RCCM, compte
  contribuable, date de liquidation, délai de carence). Leur arrivée ajoutera
  des types au catalogue et des lignes au corrigé — elle ne touchera ni le
  canal, ni le rapprochement, ni les écrans.
- Le mode de transmission « à la demande » (dépôt de fichier repris par lots) :
  l'échange se fera par API. Le fichier reste téléchargeable (M4), mais il n'est
  pas le canal nominal.
- B5 et B10, volontairement absents de la numérotation du cahier.
