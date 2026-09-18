# Corriger ce que l'audit a trouvé

> Suite de `docs/guides/sonarqube.md`. Celui-là explique **comment lire** le
> bulletin ; celui-ci explique **quoi faire** de ce qu'il contient.

> ### ✅ Appliqué le 1er septembre 2026
>
> Les trois correctifs de ce guide sont **dans le code**, et les six `random`
> sont statués dans SonarQube. Le texte est conservé : il explique *pourquoi*
> chaque correction a la forme qu'elle a — c'est ce qu'on cherche quand on
> revient dessus dans six mois, pas le diff. Après la seconde analyse :
> **0 bug, 0 vulnérabilité, notes A en fiabilité et en sécurité**, couverture
> passée de 0 à 68,2 %. Détail dans
> [`docs/rapports/sonarqube_2026-09-01.md`](../rapports/sonarqube_2026-09-01.md).

---

## D'abord, remettre le tableau sous les yeux

Le serveur SonarQube était éteint (le conteneur s'était arrêté après la
dernière analyse). Il a été redémarré :

```bash
podman compose -f compose.sonar.yaml up -d
```

Le tableau est de nouveau lisible ici :
**http://172.31.104.114:9000/dashboard?id=ECHO---simulateur-CMU**

> L'adresse `172.31.104.114` est celle de la machine WSL, pas `localhost` :
> c'est le même sujet que le `localhost:8000` d'ÉCHO (voir `GUIDE_PODMAN.md`).

---

## Comprendre les deux colonnes qu'on confond toujours

SonarQube range la sécurité en **deux piles distinctes**, et l'erreur la plus
fréquente est de les traiter pareil.

| | **Vulnerabilities** | **Security Hotspots** |
|---|---|---|
| Ce que ça dit | « c'est un défaut » | « regarde, et dis-moi si c'est voulu » |
| Ce qu'on en fait | on **corrige le code** | on **tranche** : *Safe* ou *À corriger* |
| Si on ne fait rien | la dette reste | le compteur reste rouge **même si tout va bien** |

Un *hotspot* laissé sans réponse n'est pas un bug : c'est une question sans
réponse. Tant qu'on ne répond pas, le tableau ne peut plus dire si le code est
sain — et un tableau qui ne distingue plus le sain du douteux, on arrête de le
regarder. **Répondre à un hotspot fait partie de la correction.**

---

## Ce que l'audit a réellement trouvé

> **La liste de SonarQube elle-même est extraite dans
> [`docs/rapports/sonarqube_2026-09-01.md`](../rapports/sonarqube_2026-09-01.md)** :
> 4 bugs et 5 vulnérabilités, avec le correctif de chacun. Aucun des deux
> inventaires ne remplace l'autre — SonarQube voit des choses que la passe
> ci-dessous ne voit pas, et l'inverse est vrai aussi. Lis les deux.

Passe faite sur les 16 dossiers de code déclarés dans
`sonar-project.properties`, plus les dépendances.

### Le bilan en une ligne

**Aucune faille exploitable.** Trois endroits à durcir, six à justifier, et
rien du tout côté dépendances.

| Vérifié | Résultat |
|---|---|
| Dépendances Python (`requirements.txt`) | ✅ aucune CVE connue |
| Dépendances du dashboard (`npm audit`) | ✅ 0 sur 120 paquets |
| Mots de passe / jetons en dur dans le code | ✅ aucun |
| `.env` suivi par git | ✅ non — il est ignoré |
| Hachage des mots de passe | ✅ bcrypt, sel unique par mot de passe |
| Clé JWT | ✅ obligatoire par variable d'environnement, aucune valeur par défaut |
| CORS | ✅ liste fermée + motif local, refermable par `CORS_ORIGIN_REGEX` |
| Conteneur | ✅ tourne sous l'utilisateur `echo`, pas sous root |
| Frontend (`innerHTML`, `eval`) | ✅ aucun usage |

---

## Correctif 1 — les noms de colonnes de l'export SQL

**Fichier :** `campagnes/export.py`, fonction `_en_sql` (lignes 323 et 327)

**Le problème.** Les *valeurs* sont bien protégées par `_echapper_sql`, qui
double les apostrophes. Mais les **noms de colonnes**, eux, sont recopiés tels
quels depuis l'en-tête du CSV. Un en-tête tordu — volontairement ou par un
fichier mal formé — écrit ce qu'il veut dans le script généré. Le script n'est
pas exécuté par ÉCHO, il est livré à quelqu'un qui le jouera sur **sa** base :
le dégât se produirait chez lui.

**Le correctif.** Ajouter à côté de `_echapper_sql` :

```python
def _identifiant_sql(nom: str) -> str:
    """Met un nom de colonne entre guillemets, en doublant ceux qu'il contient.

    Pendant que `_echapper_sql` protège les valeurs, celle-ci protège les
    noms : un en-tête de CSV n'est pas plus digne de confiance qu'une cellule.
    """

    return '"' + nom.replace('"', '""') + '"'
```

Puis remplacer les deux lignes qui composent les colonnes :

```python
# ligne 323
morceaux.append(",\n".join(f"    {_identifiant_sql(colonne)} TEXT" for colonne in entete))

# ligne 327
colonnes = ", ".join(_identifiant_sql(colonne) for colonne in entete)
```

**Après ça, le signalement restera.** L'outil voit une chaîne qui compose du
SQL et ne sait pas que tout est échappé. C'est un cas de *hotspot* : dans
SonarQube, ouvre la ligne et marque-la **Safe** avec la justification
« script d'export livré, jamais exécuté par ÉCHO ; valeurs et identifiants
échappés ». La question est posée, la réponse est écrite : le compteur peut
redevenir vert honnêtement.

---

## Correctif 2 — le nom de table du panorama

**Fichier :** `gouvernance/panorama.py`, ligne 46

```python
nombre = (await session.execute(
    text(f'SELECT count(*) FROM "{table}"')
)).scalar_one()
```

**Le problème.** `table` vient de `pg_tables`, filtré sur le préfixe `TB_` :
en pratique, personne d'extérieur ne choisit cette valeur. Mais les guillemets
autour du nom sont posés à la main, sans doubler ceux que le nom pourrait
contenir. C'est le genre de détail qui tient tant que personne ne crée une
table au nom exotique — donc jusqu'au jour où quelqu'un le fait.

**Le correctif.** La même fonction que ci-dessus, en haut du module :

```python
def _identifiant(nom: str) -> str:
    """Un nom de table, protégé. PostgreSQL double les guillemets internes."""

    return '"' + nom.replace('"', '""') + '"'
```

et ligne 46 :

```python
nombre = (await session.execute(
    text(f"SELECT count(*) FROM {_identifiant(table)}")
)).scalar_one()
```

> Pourquoi pas un paramètre `:table` comme partout ailleurs ? Parce qu'un
> paramètre SQL remplace une **valeur**, jamais un **nom d'objet**. Écrire
> `FROM :table` produirait `FROM 'TB_FACTURES'` — une chaîne de caractères, pas
> une table, et la requête échouerait. Échapper l'identifiant est ici la bonne
> réponse, pas un contournement.

Ce signalement-là disparaîtra pour de bon.

---

## Correctif 3 — l'erreur avalée en silence

**Fichier :** `metrics/registry.py`, lignes 53-55

```python
except Exception:
    pass
return 0.0
```

**Le problème.** La mesure mémoire échoue et personne ne le saura jamais. Le
rapport affichera `0 Mo` — une valeur qui a l'air d'une mesure alors que c'est
un aveu d'échec. On cherchera la fuite mémoire pendant des heures dans un
chiffre qui n'a jamais été mesuré.

**Le correctif.** Garder la tolérance (une mesure de confort ne doit jamais
faire tomber l'API), mais laisser une trace. En haut du module :

```python
import logging

journal = logging.getLogger(__name__)
```

et à la place du `pass` :

```python
except Exception:
    # La mémoire est un indicateur de confort : son absence ne doit jamais
    # faire échouer un appel. Mais elle doit se voir dans le journal, sinon
    # « 0 Mo » se lit comme une mesure au lieu d'un échec.
    journal.debug("Mesure mémoire indisponible", exc_info=True)
return 0.0
```

---

## Les six `random` — à justifier, pas à corriger

`anomalies/config.py:92` · `campagnes/generateur.py:648` ·
`entrepot/generateur.py:56` · `mdm/generateur.py:181` ·
`simulation/engine.py:55` · `simulation/passage.py:74`

L'outil signale « générateur pseudo-aléatoire non adapté à la cryptographie ».
C'est vrai, et **sans objet ici** : ces tirages fabriquent des assurés, des
factures et des anomalies fictives. Aucun ne produit un mot de passe, un jeton
ou une clé. Mieux : `random` est *reproductible* par graine, et c'est
précisément ce qu'on veut d'un simulateur — deux exécutions avec la même graine
donnent le même jeu. `secrets`, lui, est irreproductible par construction :
l'employer ici casserait la reproductibilité pour zéro gain.

**Ce qu'il faut faire :** dans SonarQube, marquer ces six hotspots **Safe**,
justification « données de simulation, aucun usage cryptographique ; la
reproductibilité par graine est un besoin du simulateur ».

⚠️ Le jour où ÉCHO tirera un jeton, un mot de passe temporaire ou un
identifiant de session, ce sera `secrets.token_urlsafe()` — jamais `random`.

---

## Refaire tourner l'analyse pour vérifier

Les trois commandes du guide SonarQube, `.venv` activé, depuis la racine :

```bash
python -m pytest --cov=. --cov-report=xml
```

```bash
pysonar --sonar-host-url=http://172.31.104.114:9000 --sonar-token=sqp_TON_JETON
```

Puis rouvrir le tableau. **Attendu après correction :** *Vulnerabilities* à 0,
et *Security Hotspots* tous revus (le compteur « à examiner » tombe à 0, les
autres passent en « Reviewed / Safe »).

---

## Le réflexe à garder

Deux commandes qui répondent à des questions différentes, et qui ne coûtent
rien à lancer avant chaque livraison :

```bash
python -m pip_audit -r requirements.txt
```

```bash
npm audit --prefix dashboard
```

Ces deux-là regardent les **dépendances** — les failles publiées dans les
bibliothèques qu'on utilise. SonarQube, lui, ne regarde que **le code écrit
ici**. Les deux sont nécessaires : la faille la plus probable d'une application
n'est presque jamais dans son propre code, elle est dans ce qu'elle importe.
Aujourd'hui les deux sont propres ; ça ne le restera pas tout seul.
