# M6 — Le canal API

> Sixième module du cahier « Qualité des données ».
> Suite de [M5_anomalies_manquantes.md](M5_anomalies_manquantes.md).

---

## Ce que le module apporte

Jusqu'ici, une campagne s'arrêtait au fichier téléchargeable (M4). M6 fait
le pas suivant : **transmettre ce fichier à un outil de qualité, et recevoir
son rapport** — l'échange que M7 confrontera au corrigé.

L'outil réel n'est pas encore choisi. En attendant, ÉCHO se teste
lui-même : ses 19 règles de qualité sont exposées derrière le même contrat
que devra tenir le vrai outil un jour, dans un rôle à part — **le témoin**.
Brancher un vrai outil plus tard ne demandera de changer qu'une adresse.

Trois pannes sont distinguées, et **aucune ne doit jamais ressembler à
« l'outil n'a rien détecté »** — c'est l'exigence centrale du chapitre :

| Panne | Ce qui s'est passé |
|---|---|
| Silence | L'outil n'a pas répondu (éteint, mauvaise adresse, temps dépassé) |
| Rapport malformé | La réponse n'est pas exploitable (pas du JSON, pas la forme attendue) |
| Rapport sans détail | La réponse est valide, mais sans le détail ligne par ligne |

---

## Le scénario de test

> À dérouler dans l'application, jamais dans un terminal. Une
> **reconstruction est nécessaire** : ce module ajoute la migration `0022`,
> qui crée la table des échanges.

```bash
podman compose up -d --build
```

### Étape 1 — Générer une campagne à transmettre

Crée une campagne (ou reprends-en une déjà générée), avec quelques
anomalies actives — sans quoi le témoin n'aura rien à trouver.

### Étape 2 — Transmettre au témoin

Sur la fiche de la campagne, une fois le jeu produit, tu trouves un nouveau
bloc **« Transmettre à l'outil testé »**. Laisse le champ d'adresse vide et
clique **Transmettre**.

**Ce que tu dois voir :** une ligne apparaît dans l'historique en dessous,
avec une heure d'envoi, une heure de réception, un badge **« Reçu »**, et un
nombre de constats supérieur à zéro si tu as bien injecté des anomalies.

### Étape 3 — Provoquer un silence

Retransmets la même campagne, mais cette fois avec une adresse qui ne
répond à rien — par exemple `http://127.0.0.1:9/rien`.

**Ce que tu dois voir :** une nouvelle ligne, avec le badge **« L'outil n'a
pas répondu »**. Pas de nombre de constats, pas de score à zéro — l'écran ne
dit jamais que l'outil a échoué à détecter quoi que ce soit, il dit qu'il
n'a pas pu le lui demander.

### Étape 4 — Provoquer un rapport sans détail

Retransmets une troisième fois, avec l'adresse
`http://127.0.0.1:8000/temoin/analyser-resume` — un outil imaginaire, posé
exprès pour cette recette, qui ne rend qu'un résumé.

**Ce que tu dois voir :** le badge **« Le rapport ne détaille pas les
lignes »**. C'est différent du silence : l'outil a bien répondu, il n'a
simplement pas rendu ce que le contrat exige.

### Étape 5 — L'historique garde tout

Reviens sur la fiche de la campagne : les trois lignes de l'historique sont
toujours là, dans l'ordre inverse de leur envoi. Rien n'est écrasé — c'est
ce que le banc d'essai de M8 comparera plus tard, plusieurs outils sur la
même campagne.

---

## Ce qu'il faut savoir sur la conception

### Le témoin n'est pas un raccourci

`api/routers/temoin.py` répond exactement au contrat que devra tenir le
vrai outil : il reçoit le fichier en pièce jointe, il rend
`{"outil": ..., "constats": [{"ligne", "champ", "type"}, ...]}`. Rien dans
`campagnes/echange.py` ne sait qu'il s'agit du témoin plutôt que d'un
service externe — c'est justement ce qui rend le canal réutilisable tel
quel le jour où le vrai outil sera choisi.

### Pourquoi le rapport ne porte pas les codes internes d'ÉCHO

Le témoin décrit ce qu'il trouve en texte libre (`"Montant hors norme"`),
jamais avec un code du catalogue (`MONTANT_ABERRANT`). Un vrai outil externe
ne connaîtra jamais notre vocabulaire interne. Le rapprochement de M7
travaillera sur **ligne + champ**, pas sur ce texte — c'est la seule
information qu'un outil, quel qu'il soit, peut raisonnablement rendre.

### Comment les trois pannes sont distinguées en code

Tout se joue dans `_classer_rapport()` (`campagnes/echange.py`) :

- pas de réponse, ou un code HTTP autre que 200 → **silence** ;
- une réponse qui n'est pas un objet JSON exploitable, ou dont la liste
  `constats` est absente de sa forme, ou dont une entrée n'a pas de
  numéro de ligne → **rapport malformé** ;
- une réponse JSON valide, mais sans la clé `constats` du tout → **rapport
  sans détail**.

Le dernier cas est délibérément séparé du premier malformage : l'outil a
répondu correctement, il n'a simplement pas tenu le contrat en détail. Les
deux pannes appellent des diagnostics différents pour celui qui les lit.

### Pourquoi l'adresse n'est pas un réglage de la campagne

Elle est donnée à chaque transmission (`campagnes/echange.py:transmettre`),
pas rangée sur `TB_CAMPAGNES`. Une campagne peut être retransmise vers des
adresses différentes — exactement ce que M8 comparera. La ranger sur la
campagne aurait imposé de choisir une seule adresse « officielle » par
campagne, ce que rien dans le cahier ne demande.

### Ce que l'historique conserve

`TB_CAMPAGNES_ECHANGES` garde une ligne par tentative, échecs compris,
avec le rapport brut reçu (`ECHANGE_RAPPORT`, JSON) quand il y en a un. Rien
n'est réutilisé pour recalculer un rapprochement : M7 s'appuiera sur ce
rapport déjà en base, sans redemander à l'outil.

---

## Ce qui a changé dans le dépôt

| Fichier | Nature |
|---|---|
| `temoin/regles.py` | **nouveau** — les règles du témoin, réécrites pour lire un fichier |
| `temoin/service.py` | **nouveau** — décode le CSV et applique les règles |
| `api/routers/temoin.py` | **nouveau** — `/temoin/analyser` et `/temoin/analyser-resume` |
| `campagnes/echange.py` | **nouveau** — l'adaptateur : transmet, classe les trois pannes, historise |
| `campagnes/models.py` | `EchangeCampagne`, les motifs d'échec |
| `alembic/versions/20260907_0022_*.py` | **nouveau** — crée `TB_CAMPAGNES_ECHANGES` |
| `api/routers/campagnes.py` | `/campagnes/{id}/transmettre`, `/campagnes/{id}/echanges`, `/campagnes/motifs-echec` |
| `dashboard/src/components/FicheCampagne.tsx` | le bloc « Transmettre à l'outil testé » |
| `tests/test_temoin.py`, `tests/test_echange.py` | **nouveaux** |

**Migration `0022` à appliquer** — elle part toute seule avec
`podman compose up -d --build`.

Variable d'environnement `ADRESSE_OUTIL_TESTE` : l'adresse par défaut si
aucune n'est donnée à la transmission. Non réglée, elle pointe vers le
témoin lui-même (`http://127.0.0.1:8000/temoin/analyser`) — brancher le vrai
outil un jour se fera par cette variable, sans toucher au code.

---

> Non vérifié à l'écran de mon côté. Le scénario ci-dessus est la recette —
> les étapes 3 et 4 sont celles qu'il ne faut pas sauter : c'est elles qui
> prouvent que le canal ne ment jamais sur une panne.
>
> Rappel : la recette de M1 à M5 n'a jamais été faite. Elle reste en dette,
> et la checklist est là pour ça.
