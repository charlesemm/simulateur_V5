# Rapport SonarQube — ÉCHO, Simulateur CMU

**Analyse du 1er septembre 2026, 12h47** · version `1.0` · 21 167 lignes de code
Serveur : http://172.31.104.114:9000/dashboard?id=ECHO---simulateur-CMU

> Rapport extrait de l'API SonarQube. L'édition Community n'a pas de bouton
> d'export : voir la dernière section pour le régénérer.

---

## ✅ Suite donnée — corrigé le jour même

Tout ce que décrit ce rapport a été traité, et une seconde analyse l'a
confirmé. **L'état ci-dessous est l'état d'avant** : il est conservé tel quel,
c'est lui qui donne son sens à la comparaison.

| | Avant | Après |
|---|---:|---:|
| Bugs | 4 (note **D**) | **0** (note **A**) |
| Vulnérabilités | 5 (note **C**) | **0** (note **A**) |
| Couverture des tests | 0 % | **68,2 %** |
| Duplication | 0,2 % | 0,2 % |

Les 4 bugs et les 2 `http://` dupliqués ont été **corrigés dans le code** —
SonarQube les a lui-même reclassés en *Fixed*. Les 3 tirages `random` et le
motif CORS désormais unique ont été passés en ***Accepted*** avec leur
justification, consultable dans l'interface sur chaque ligne.

Deux corrections de fond sont allées au-delà du signalement :

- la configuration CORS, **dupliquée** entre `api/main.py` et
  `realtime/socket_server.py`, vit maintenant dans `app/cors.py` — une seule
  variable d'environnement referme les deux portes ;
- les trois durcissements repérés hors SonarQube (`campagnes/export.py`,
  `gouvernance/panorama.py`, `metrics/registry.py`) sont appliqués : voir
  [le guide de correction](../guides/corriger_les_vulnerabilites.md).

Restent les **368 code smells**, dont les 35 signalements d'accessibilité —
inchangés, et décrits plus bas.

---

## Les compteurs

| Mesure | Valeur | Note |
|---|---:|:---:|
| Lignes de code | 21 167 | — |
| **Bugs** | **4** | **D** |
| **Vulnérabilités** | **5** | **C** |
| Security Hotspots | 0 | — |
| Code Smells | 367 | A |
| Dette technique | 1 517 min (≈ 25 h) | A |
| Duplication | 0,2 % | ✅ |
| **Couverture des tests** | **0 %** | ⚠️ voir plus bas |

**Quality Gate : OK** — mais ne t'y fie pas encore. La porte ne juge que le
*code neuf*, et il n'y a qu'une seule analyse dans l'historique : il n'existe
pas encore de « neuf » à comparer. Elle deviendra parlante à la deuxième
analyse.

Les deux notes qui comptent ici sont **D en fiabilité** et **C en sécurité**.
Elles ne reflètent pas un état délabré — SonarQube note sur le **pire** défaut
trouvé, pas sur une moyenne. Un seul bug critique suffit à faire tomber la note
à D. Les neuf défauts ci-dessous les expliquent en entier.

---

## Les 4 bugs

### 1. Tri alphabétique non fiable — `CRITICAL`

`dashboard/src/components/ConsoleInjectionPage.tsx:141` · règle `typescript:S2871`

```tsx
return [...connues, ...autres.sort()];
```

`.sort()` sans fonction de comparaison trie sur les codes UTF-16, pas sur
l'alphabet. Les familles d'anomalies portent des libellés français : « Éligibilité »
se retrouverait **après** « Zone » au lieu d'être à sa place. Sur un écran qui
sert à retrouver une famille dans une liste, c'est le tri qui devient inutile.

```tsx
return [...connues, ...autres.sort((a, b) => a.localeCompare(b, "fr"))];
```

### 2 et 3. Une assertion qui se compare à elle-même — `MAJOR` × 2

`tests/test_identifiants.py:71` et `tests/test_securite.py:26` · règle `python:S5863`

```python
# test_identifiants.py
assert [insured_profession(index) for index in range(50)] == \
       [insured_profession(index) for index in range(50)]

# test_securite.py
assert hash_password("identique") != hash_password("identique")
```

Les deux tests sont **justes dans leur intention** — l'un vérifie que la
profession est déterministe, l'autre que le sel bcrypt est unique. Mais écrits
comme ça, l'outil ne peut pas les distinguer d'une faute de copier-coller, et
un relecteur non plus. Nommer les deux côtés dit ce qu'on éprouve :

```python
# test_identifiants.py
premier_passage = [insured_profession(index) for index in range(50)]
second_passage = [insured_profession(index) for index in range(50)]
assert premier_passage == second_passage

# test_securite.py
premiere_empreinte = hash_password("identique")
seconde_empreinte = hash_password("identique")
assert premiere_empreinte != seconde_empreinte
```

Le test ne change pas de sens, il devient lisible — et le signalement tombe.

### 4. Une annulation avalée — `MAJOR`

`simulation/engine.py:182` · règle `python:S7497`

```python
try:
    await self._pause_task
except asyncio.CancelledError:
    break
```

**Le problème.** Ce `break` traite toute annulation comme un arrêt demandé.
Or il y a deux façons d'arriver là : `stop()` qui annule `_pause_task`
volontairement — et une annulation venue d'au-dessus, quand c'est la boucle
entière qu'on arrête (fermeture de l'API, `asyncio.timeout`). Dans le second
cas, avaler l'exception ment à l'appelant : il croit son annulation refusée
alors que la boucle sort quand même. C'est le genre d'arrêt qui se fige à
l'extinction du serveur sans qu'on comprenne pourquoi.

Le discriminant existe déjà : `stop()` pose `self._running = False` **avant**
d'annuler.

```python
except asyncio.CancelledError:
    if self._running:
        # Ce n'est pas notre stop() : l'annulation vient de plus haut et
        # doit poursuivre sa route, sinon l'appelant attend un arrêt qui
        # ne se signale jamais.
        raise
    break
```

---

## Les 5 vulnérabilités

### `http://` en dur dans la configuration CORS — `MINOR` × 2

`api/main.py:86` et `realtime/socket_server.py:30` · règle `python:S5332`

```python
_cors_regex = os.getenv("CORS_ORIGIN_REGEX", r"http://(localhost|127\.0\.0\.1)(:\d+)?")
```

**Verdict : à accepter, pas à corriger.** La règle signale tout `http://`
écrit en dur. Ici il ne décrit pas une destination qu'ÉCHO appelle, mais le
motif des origines locales acceptées en développement — du trafic qui ne quitte
jamais la machine, où le chiffrement n'a rien à protéger. Le commentaire
au-dessus dit déjà comment refermer en déploiement : `CORS_ORIGIN_REGEX` à vide.

Dans SonarQube : ouvrir chaque ligne → **Accept**, justification
*« motif d'origines locales de développement ; refermé en déploiement par CORS_ORIGIN_REGEX vide »*.

> **Au passage, un vrai défaut que Sonar n'a pas vu.** Cette ligne est
> **dupliquée à l'identique** dans les deux fichiers. Le jour où on referme
> l'un, on oublie l'autre — et le temps réel reste ouvert pendant que le REST
> est fermé. À sortir dans une constante partagée, lue par les deux.

### Générateur pseudo-aléatoire — `MAJOR` × 3

`entrepot/generateur.py:87` · `mdm/generateur.py:196` et `:200` · règle `python:S2245`

```python
droits_statut=1 if tirage.random() < 0.75 else 0
if tirage.random() < part_leurres:
variantes.append(_fabriquer(source, tirage.choice(VARIATIONS), tirage, numeros_pris))
```

**Verdict : à accepter, pas à corriger.** Ces tirages fabriquent des droits
ouverts ou fermés et des doublons MDM — des données fictives. Aucun ne produit
un mot de passe, un jeton ou une clé. Et `tirage` est un `Random` **ensemencé** :
la reproductibilité par graine est un besoin explicite du simulateur, deux
exécutions avec la même graine doivent donner le même jeu. `secrets` est
irreproductible par construction : l'employer ici casserait cette garantie pour
zéro gain de sécurité.

Dans SonarQube : **Accept**, justification
*« données de simulation, aucun usage cryptographique ; la reproductibilité par graine est un besoin du simulateur »*.

⚠️ Le jour où ÉCHO tirera un jeton, un mot de passe temporaire ou un
identifiant de session, ce sera `secrets` — jamais `random`. Le module
`auth/security.py` respecte déjà cette règle.

---

## Les 367 code smells

Aucun n'est un défaut de fonctionnement. Répartition : **153 TypeScript,
111 Python, 103 CSS**. Les dix règles qui en portent l'essentiel :

| Nb | Sévérité | Règle | Ce qu'elle demande |
|---:|---|---|---|
| 46 | MAJOR | `typescript:S9011` | `<button>` sans attribut `type` — dans un formulaire il vaut `submit` par défaut et envoie la page |
| 43 | MINOR | `typescript:S6759` | props de composant à passer en `readonly` |
| 32 | MINOR | `python:S8409` | `response_model` redondant avec l'annotation de retour |
| 32 | MAJOR | `python:S8415` | `HTTPException` 404/409/422 absente de `responses` — la doc OpenAPI ment sur les erreurs possibles |
| 29 | MINOR | `typescript:S7718` | paramètre de `catch` à nommer `error` |
| 29 | MAJOR | `css:S7924` | **contraste insuffisant** — accessibilité |
| 8 | MINOR | `python:S8410` | injection de dépendance FastAPI à écrire en `Annotated` |
| 6 | MAJOR | `typescript:S6853` | `<label>` non associé à son champ — accessibilité |
| 5 | CRITICAL | `python:S3776` | 5 fonctions trop complexes à suivre |
| 4 | MINOR | `python:S7503` | `async` sur une fonction qui n'attend rien |

**Les deux lots qui méritent une décision, pas un tri au fil de l'eau :**

- **Le contraste (29 + 6 = 35 signalements d'accessibilité).** Sur une
  application CNAM destinée à des agents qui la regardent toute la journée, ce
  n'est pas cosmétique. À traiter avec la direction visuelle de la rangée A,
  pas isolément.
- **Les 32 `responses` manquants.** La documentation OpenAPI est le contrat que
  lit celui qui branche un client. Une erreur 404 non déclarée est un contrat
  faux.

Les fichiers les plus chargés : `dashboard/src/index.css` (65),
`dashboard/src/brand-refresh.css` (23), `api/routers/campagnes.py` (20),
`dashboard/src/components/Icons.tsx` (18), `api/routers/simulation.py` (17).

---

## Le point aveugle : 0 % de couverture

`sonar-project.properties` attend deux rapports :

```
sonar.python.coverage.reportPaths=coverage.xml
sonar.javascript.lcov.reportPaths=dashboard/coverage/lcov.info
```

Ni l'un ni l'autre n'existait au moment de l'analyse. **SonarQube n'affiche donc
pas « couverture inconnue », il affiche « 0 % »** — et 0 %, ça se lit comme
« rien n'est testé », ce qui est faux : la suite `tests/` existe et passe.

C'est la mesure la plus trompeuse du tableau. Pour la remplir, l'étape 1 du
guide, **avant** de lancer le scanner :

```bash
python -m pytest --cov=. --cov-report=xml
```

---

## Ce que SonarQube ne regarde pas

Complété par une passe locale le même jour, sur le terrain que l'édition
Community ne couvre pas :

| Vérifié | Résultat |
|---|---|
| Dépendances Python (`pip-audit`) | ✅ aucune CVE connue |
| Dépendances du dashboard (`npm audit`) | ✅ 0 sur 120 paquets |
| Secrets en dur / `.env` suivi par git | ✅ aucun / non suivi |
| bcrypt, clé JWT obligatoire, conteneur non-root | ✅ conformes |
| `campagnes/export.py`, `gouvernance/panorama.py`, `metrics/registry.py` | ⚠️ 3 durcissements — voir [le guide de correction](../guides/corriger_les_vulnerabilites.md) |

---

## Régénérer ce rapport

Le serveur doit tourner (`podman compose -f compose.sonar.yaml up -d`), et
`SONAR_TOKEN` doit être dans `.env` — un **User Token**, pas un jeton d'analyse.

```bash
curl -s -u "$SONAR_TOKEN:" "http://172.31.104.114:9000/api/measures/component?component=ECHO---simulateur-CMU&metricKeys=ncloc,bugs,vulnerabilities,security_hotspots,code_smells,coverage,duplicated_lines_density,sqale_index"
```

```bash
curl -s -u "$SONAR_TOKEN:" "http://172.31.104.114:9000/api/issues/search?componentKeys=ECHO---simulateur-CMU&ps=500"
```

Après une nouvelle analyse, dater le fichier du jour plutôt que d'écraser
celui-ci : c'est la suite des rapports qui montre si la dette monte ou descend,
pas un rapport isolé.
