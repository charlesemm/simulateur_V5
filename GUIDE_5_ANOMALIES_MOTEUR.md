# GUIDE 5 — Brancher les anomalies sur le moteur

> **Chantier 5 sur 8** du plan de remise en ordre du projet `simulateur_V5`.
> Prérequis : [GUIDE_4_SECURISATION_ENDPOINTS.md](./GUIDE_4_SECURISATION_ENDPOINTS.md) terminé (commit `dfcd1eb` poussé).

---

## En deux mots

C'est le **premier chantier qui ajoute une fonctionnalité** au lieu de réparer. Les quatre précédents remettaient le projet d'aplomb ; celui-ci fait exister une promesse qui n'était pas tenue.

Le dashboard affiche un panneau « Test de Résilience & Anomalies ». Le README annonce qu'on peut *« injecter à chaud un pourcentage de données atypiques afin d'éprouver la robustesse du moteur »*.

**Aujourd'hui, bouger ce curseur ne fait rien.** Le compteur « Anomalies injectées » reste à zéro quoi qu'on fasse.

À la fin de ce chantier, il fonctionnera vraiment.

---

## Table des matières

- [Le diagnostic](#le-diagnostic)
- [L'architecture cible](#larchitecture-cible)
- [⚠️ Le piège de la migration 0001](#-le-piège-de-la-migration-0001)
- [Partie A — Créer le module `anomalies/`](#partie-a--créer-le-module-anomalies)
- [Partie B — Mettre à jour les imports](#partie-b--mettre-à-jour-les-imports)
- [Partie C — Persister la configuration](#partie-c--persister-la-configuration)
- [Partie D — Brancher le moteur](#partie-d--brancher-le-moteur)
- [Partie E — Corriger la documentation](#partie-e--corriger-la-documentation)
- [Partie F — Vérifier et commiter](#partie-f--vérifier-et-commiter)
- [Récapitulatif](#récapitulatif)

---

## Le diagnostic

| Élément | Réalité constatée |
|---|---|
| `anomalies_config` | Lu **uniquement** par `seed/runner.py`, au moment du seed |
| Ce qui est réellement injecté | 2 champs : l'email d'un agent, le n° de sécu d'un assuré |
| `inject_montant()` et `inject_date_cohesion()` | Écrits mais **jamais appelés** — code mort |
| `simulation/passage.py` | **Ne consulte jamais** la configuration |
| `TB_CONFIG_ANOMALIES` | Table créée par la migration `0005`, aucun modèle, aucune lecture, aucune écriture |
| Panneau du dashboard | Modifie un objet en mémoire que seul le seed lit — et le seed a déjà tourné |

**Une bonne nouvelle pour la faisabilité :** les colonnes de montants sont en `Numeric(15,2)` **sans contrainte `CHECK`**. Des montants négatifs ou aberrants sont donc stockables — aucune migration n'est nécessaire.

---

## L'architecture cible

```
                    TB_CONFIG_ANOMALIES  (persistance)
                              ▲ │
                   sauvegarder│ │charger au démarrage
                              │ ▼
   PATCH /anomalies ──▶  anomalies_config  (objet en mémoire)
   (panneau dashboard)         │
                               │ consulté à chaque écriture
                               ▼
                    simulation/passage.py
                    seed/runner.py
```

Trois changements de fond :

1. La configuration **survit au redémarrage** — elle est chargée depuis la base au démarrage de l'API
2. Le moteur **la consulte** à chaque écriture de montant, de date ou de quantité
3. Le compteur d'injections **monte en direct** pendant la simulation, et le panneau l'affiche

---

## ⚠️ Le piège de la migration 0001

**À lire avant de créer le modèle SQLAlchemy.**

La migration `20260814_0001` ne décrit aucune table en dur :

```python
Base.metadata.create_all(bind=op.get_bind(), checkfirst=False)
```

Elle construit le schéma à partir des modèles **tels qu'ils existent aujourd'hui**. C'est exactement ce qui a cassé la migration `0006` au chantier 0.

👉 **Si le nouveau modèle est importé par `app/models/__init__.py`, la migration `0001` créera `TB_CONFIG_ANOMALIES`, puis la migration `0005` échouera** sur une base neuve avec `DuplicateTableError`.

**La règle à respecter :** le nouveau modèle utilise le même `Base`, mais **ne doit jamais être importé depuis `app/models/__init__.py`**.

C'est déjà le procédé retenu pour `auth/models.py` (table `TB_UTILISATEURS`) et `events/models.py` (table `TB_EVENEMENTS_METIER`) — et c'est précisément pourquoi les migrations `0003` et `0004` fonctionnent sur une base neuve.

---

## Partie A — Créer le module `anomalies/`

**Pourquoi un nouveau module :** la configuration vit aujourd'hui dans `seed/anomalies.py`. Or elle va désormais servir au **moteur** autant qu'au seed. Laisser `simulation/passage.py` importer depuis `seed/` serait trompeur.

### A.1 — `anomalies/__init__.py` *(nouveau fichier)*

```python
"""Injection contrôlée de données atypiques, pour éprouver la robustesse."""

from anomalies.config import AnomaliesConfig, anomalies_config, apply_anomalies_to_row
from anomalies.models import AnomaliesConfigRow

__all__ = [
    "AnomaliesConfig",
    "AnomaliesConfigRow",
    "anomalies_config",
    "apply_anomalies_to_row",
]
```

### A.2 — `anomalies/models.py` *(nouveau fichier)*

```python
"""Modèle SQLAlchemy de la table de configuration des anomalies."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import TIMESTAMP, Boolean, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AnomaliesConfigRow(Base):
    """Persiste la configuration du chaos testing entre deux démarrages.

    Ce modèle partage le Base déclaratif commun mais n'est volontairement pas
    exporté par app/models/__init__.py : la migration 0001 appelle
    Base.metadata.create_all() et créerait sinon la table en double avec la
    migration 0005. Même procédé que auth/models.py et events/models.py.
    """

    __tablename__ = "TB_CONFIG_ANOMALIES"

    config_id: Mapped[int] = mapped_column(
        "CONFIG_ID", Integer, primary_key=True, autoincrement=True
    )
    enabled: Mapped[bool] = mapped_column(
        "ENABLED", Boolean, nullable=False, default=False
    )
    rate: Mapped[Decimal] = mapped_column(
        "RATE", Numeric(3, 2), nullable=False, default=Decimal("0.00")
    )
    severity: Mapped[str] = mapped_column(
        "SEVERITY", String(20), nullable=False, default="soft"
    )
    injected_count: Mapped[int] = mapped_column(
        "INJECTED_COUNT", Integer, nullable=False, default=0
    )
    date_modification: Mapped[datetime] = mapped_column(
        "DATE_MODIFICATION",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

> **Note :** cette table n'a pas les quatre colonnes d'audit. Le modèle n'hérite donc **pas** de `AuditMixin`, contrairement aux autres.

### A.3 — `anomalies/config.py` *(nouveau fichier)*

Reprend le contenu de `seed/anomalies.py`, avec trois injecteurs supplémentaires destinés au moteur.

```python
"""Configuration et injecteurs d'anomalies « douces ».

Les anomalies douces sont des données incohérentes qui respectent les
contraintes SQL mais révèlent les bugs métier : montants négatifs, dates
antidatées, quantités servies supérieures aux quantités prescrites.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal
from typing import Any


class AnomaliesConfig:
    """Configuration en mémoire, pilotée par l'API et persistée en base."""

    def __init__(
        self,
        enabled: bool = False,
        rate: float = 0.0,
        seed: int = 42,
        severity: str = "soft",
    ) -> None:
        self.enabled = enabled
        self.rate = max(0.0, min(1.0, rate))
        self.random = random.Random(seed)
        self.severity = severity
        self.injected_count = 0

    def should_inject(self) -> bool:
        """Décide aléatoirement s'il faut injecter une anomalie."""
        if not self.enabled:
            return False
        return self.random.random() < self.rate

    def record_injection(self) -> None:
        """Incrémente le compteur affiché par le dashboard."""
        self.injected_count += 1

    # ── Injecteurs utilisés par le moteur de simulation ──────────────────

    def injecter_montant(self, montant: Decimal) -> Decimal:
        """Retourne un montant négatif ou démesuré, ou la valeur d'origine."""
        if not self.should_inject():
            return montant
        self.record_injection()
        if self.random.random() < 0.5:
            return Decimal("-1000.00")
        return Decimal("999999999.99")

    def injecter_date(self, valeur: date) -> date:
        """Retourne une date antidatée jusqu'à un an, ou la valeur d'origine."""
        if not self.should_inject():
            return valeur
        self.record_injection()
        return valeur - timedelta(days=self.random.randint(1, 365))

    def injecter_quantite(self, prescrite: int, servie: int) -> int:
        """Retourne une quantité servie supérieure à la quantité prescrite."""
        if not self.should_inject():
            return servie
        self.record_injection()
        return prescrite + self.random.randint(1, 20)

    # ── Injecteurs utilisés par le seed ──────────────────────────────────

    def injecter_numero_secu(self, numero: str) -> str:
        """Retourne un numéro de sécurité sociale manifestement invalide."""
        if not self.should_inject():
            return numero
        self.record_injection()
        return "00000000000000"

    def injecter_email(self, email: str) -> str:
        """Retourne une adresse électronique invalide."""
        if not self.should_inject():
            return email
        self.record_injection()
        return "pas_un_email_valide"


# Instance unique partagée par tout le processus (seed, moteur, API).
anomalies_config = AnomaliesConfig()


def apply_anomalies_to_row(
    row: dict[str, Any], config: AnomaliesConfig, row_type: str
) -> dict[str, Any]:
    """Applique les anomalies à une ligne du seed selon son type."""
    if not config.enabled:
        return row

    if row_type == "agent" and "agent_email" in row:
        row["agent_email"] = config.injecter_email(row["agent_email"])
    elif row_type == "insured" and "numero_secu" in row:
        row["numero_secu"] = config.injecter_numero_secu(row["numero_secu"])

    return row
```

> **Ce qui change par rapport à `seed/anomalies.py` :** les fonctions libres deviennent des méthodes (plus besoin de passer `config` en paramètre), `inject_date_cohesion` disparaît (elle ne concernait que `center_assignment`, un type jamais utilisé), et trois injecteurs destinés au moteur apparaissent.

### A.4 — `anomalies/repository.py` *(nouveau fichier)*

```python
"""Charge et sauvegarde la configuration des anomalies en base."""
from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select

from anomalies.config import anomalies_config
from anomalies.models import AnomaliesConfigRow
from app.database import async_session_factory

logger = logging.getLogger(__name__)

# La table ne contient qu'une seule ligne, identifiée par cette clé.
CONFIG_ID = 1


async def charger_configuration() -> None:
    """Restaure la configuration persistée dans l'instance en mémoire."""

    async with async_session_factory() as session:
        ligne = await session.get(AnomaliesConfigRow, CONFIG_ID)
        if ligne is None:
            logger.info("Aucune configuration d'anomalies en base : valeurs par défaut.")
            return
        anomalies_config.enabled = ligne.enabled
        anomalies_config.rate = float(ligne.rate)
        anomalies_config.severity = ligne.severity
        anomalies_config.injected_count = ligne.injected_count
    logger.info(
        "Configuration d'anomalies restaurée (activee=%s, taux=%s).",
        anomalies_config.enabled,
        anomalies_config.rate,
    )


async def sauvegarder_configuration() -> None:
    """Écrit l'état courant de l'instance en mémoire dans la base."""

    async with async_session_factory() as session:
        ligne = await session.get(AnomaliesConfigRow, CONFIG_ID)
        if ligne is None:
            ligne = AnomaliesConfigRow(config_id=CONFIG_ID)
            session.add(ligne)
        ligne.enabled = anomalies_config.enabled
        ligne.rate = Decimal(str(round(anomalies_config.rate, 2)))
        ligne.severity = anomalies_config.severity
        ligne.injected_count = anomalies_config.injected_count
        await session.commit()
```

### A.5 — Supprimer l'ancien fichier

```powershell
git rm seed/anomalies.py
```

---

## Partie B — Mettre à jour les imports

Trois fichiers importaient depuis `seed.anomalies`.

### B.1 — `seed/runner.py` ligne 29

**Remplace :**

```python
from seed.anomalies import anomalies_config, apply_anomalies_to_row
```

**Par :**

```python
from anomalies import anomalies_config, apply_anomalies_to_row
```

### B.2 — `seed/__main__.py` ligne 4

**Remplace :**

```python
from seed.anomalies import anomalies_config
```

**Par :**

```python
from anomalies import anomalies_config
```

### B.3 — `api/routers/anomalies.py` ligne 8

**Remplace :**

```python
from seed.anomalies import anomalies_config
```

**Par :**

```python
from anomalies import anomalies_config
from anomalies.repository import sauvegarder_configuration
```

---

## Partie C — Persister la configuration

### C.1 — Sauvegarder à chaque modification

**Fichier :** `api/routers/anomalies.py`

Dans `update_anomalies_config`, **ajoute l'appel de sauvegarde** juste avant le `return`.

**Remplace :**

```python
    if payload.severity is not None:
        anomalies_config.severity = payload.severity

    return AnomaliesConfigResponse(
```

**Par :**

```python
    if payload.severity is not None:
        anomalies_config.severity = payload.severity

    await sauvegarder_configuration()

    return AnomaliesConfigResponse(
```

**Puis, dans `reset_anomalies_count`, remplace :**

```python
    anomalies_config.injected_count = 0
    return {"message": "Compteur d'anomalies réinitialisé."}
```

**Par :**

```python
    anomalies_config.injected_count = 0
    await sauvegarder_configuration()
    return {"message": "Compteur d'anomalies réinitialisé."}
```

### C.2 — Charger au démarrage, sauvegarder à l'extinction

**Fichier :** `api/main.py`

**Ajoute cet import** avec les autres :

```python
from anomalies.repository import charger_configuration, sauvegarder_configuration
```

**Puis remplace la fonction `lifespan` :**

```python
@asynccontextmanager
async def lifespan(application: FastAPI):
    """Démarre le consommateur KPI puis arrête toutes les tâches à l'extinction."""

    del application
    await startup_event_pipeline()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()
        await simulation_manager.stop()
        await shutdown_event_pipeline()
```

**Par :**

```python
@asynccontextmanager
async def lifespan(application: FastAPI):
    """Démarre le consommateur KPI puis arrête toutes les tâches à l'extinction."""

    del application
    await charger_configuration()
    await startup_event_pipeline()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()
        await simulation_manager.stop()
        await shutdown_event_pipeline()
        # Le compteur d'injections monte en mémoire : on le fige avant de quitter.
        await sauvegarder_configuration()
```

---

## Partie D — Brancher le moteur

**Fichier :** `simulation/passage.py`

C'est le cœur du chantier : trois points d'injection dans le parcours de soins.

### D.1 — Importer la configuration

**Ajoute cet import** après `from app.models import (...)`, avant `from metrics.registry ...` :

```python
from anomalies import anomalies_config
```

> Même procédé que `metrics_registry` juste en dessous : une instance unique partagée par le processus.

### D.2 — Date de soins de la facture

**Remplace, dans `run()` :**

```python
                type_facture_code=invoice_type, facture_date_soins=self.simulated_at.date(),
```

**Par :**

```python
                type_facture_code=invoice_type,
                facture_date_soins=anomalies_config.injecter_date(self.simulated_at.date()),
```

> **Ce que ça produit :** une facture dont la date de soins précède parfois de plusieurs mois l'ouverture du dossier. Les agrégations KPI par fenêtre de 24 h devraient l'ignorer — c'est justement ce qu'on veut éprouver.

### D.3 — Montants et quantités de la prestation

**Remplace, dans `run()` :**

```python
        async with async_session_factory() as session:
            session.add(InvoiceProvision(
                facture_numero=invoice_number, prestation_code=base_code,
                professionnel_sante_code=professional.professionnel_sante_code,
                statut_remboursement="couvert", prestation_base_remboursement=Decimal("10000"),
                prestation_taux_remboursement=Decimal("70"), prestation_quantite_prescrite=1,
                prestation_quantite_servie=1, prestation_prix_unitaire=Decimal("10000"),
                prestation_montant_depense=Decimal("10000"), prestation_montant_assure=Decimal("3000"),
                statut_code="servie", utilisateur_id_creation="simulation",
            ))
            await session.commit()
```

**Par :**

```python
        montant_depense = anomalies_config.injecter_montant(Decimal("10000"))
        quantite_servie = anomalies_config.injecter_quantite(1, 1)
        async with async_session_factory() as session:
            session.add(InvoiceProvision(
                facture_numero=invoice_number, prestation_code=base_code,
                professionnel_sante_code=professional.professionnel_sante_code,
                statut_remboursement="couvert", prestation_base_remboursement=Decimal("10000"),
                prestation_taux_remboursement=Decimal("70"), prestation_quantite_prescrite=1,
                prestation_quantite_servie=quantite_servie, prestation_prix_unitaire=Decimal("10000"),
                prestation_montant_depense=montant_depense, prestation_montant_assure=Decimal("3000"),
                statut_code="servie", utilisateur_id_creation="simulation",
            ))
            await session.commit()
```

> **Ce que ça produit :** des prestations à `-1000` ou `999999999.99` F CFA, et des quantités servies dépassant la quantité prescrite. Deux incohérences que tout contrôle de facturation devrait rejeter.

### D.4 — Montant de l'entente préalable

**Remplace, dans `process_prior_authorization()` :**

```python
        amount = Decimal("50000") if hospital else Decimal("15000")
```

**Par :**

```python
        amount = anomalies_config.injecter_montant(
            Decimal("50000") if hospital else Decimal("15000")
        )
```

> **Ce que ça produit :** un montant aberrant se propage à `acte_medical_montant_cmu` et `acte_medical_montant_assure`, donc aux cumuls du dashboard. C'est le test le plus intéressant : il vérifie qu'une donnée corrompue **en amont** ne fausse pas silencieusement les indicateurs.

---

## Partie E — Corriger la documentation

**Fichier :** `README.md` ligne 124

La promesse devient enfin exacte, mais elle décrit mal ce qui est injecté.

**Remplace :**

```markdown
  * Panneau de contrôle permettant d'injecter à chaud un pourcentage de données atypiques ou malformées (incohérence de dates, numéros de sécurité sociale tronqués, montants atypiques) afin d'éprouver la robustesse du moteur.
```

**Par :**

```markdown
  * Panneau de contrôle permettant d'injecter à chaud un pourcentage de données atypiques dans le moteur de simulation : montants négatifs ou démesurés, dates de soins antidatées, quantités servies supérieures aux quantités prescrites. Le compteur « Anomalies injectées » monte en direct pendant la simulation. La configuration est persistée en base et survit au redémarrage de l'API.
```

---

## Partie F — Vérifier et commiter

### F.1 — Le backend compile

```powershell
python -m compileall app api auth events kpi metrics realtime reports seed simulation anomalies run_simulation.py
```

### F.2 — Aucune référence à l'ancien module

```powershell
git grep -n "seed.anomalies"
```

Attendu : **aucune sortie**.

### F.3 — L'API démarre et charge la configuration

```powershell
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Au démarrage, un message doit apparaître :

```
INFO - Aucune configuration d'anomalies en base : valeurs par défaut.
```

C'est normal au premier lancement : la table est vide.

### F.4 — Le test de bout en bout

C'est **la** vérification qui valide le chantier. Dans le dashboard, connecté en administrateur :

| # | Action | Attendu |
|---|---|---|
| 1 | Panneau « Test de Résilience » → activer l'injection, taux **0.5** | La configuration est enregistrée |
| 2 | Cliquer sur **Démarrer** | Le moteur tourne |
| 3 | Observer le compteur « Anomalies injectées » | 🎯 **Il monte** — c'était impossible avant |
| 4 | Arrêter, puis **redémarrer l'API** (`Ctrl+C` puis relancer) | Au démarrage : `Configuration d'anomalies restaurée (activee=True, taux=0.5)` |

Vérifie enfin en base que les anomalies sont bien écrites :

```powershell
psql -U postgres -h localhost -d cmu_simulator -c "SELECT count(*) FROM \"TB_FACTURES_PRESTATIONS\" WHERE \"PRESTATION_MONTANT_DEPENSE\" < 0;"
```

Un résultat supérieur à zéro prouve que le moteur écrit réellement des montants aberrants.

```powershell
psql -U postgres -h localhost -d cmu_simulator -c "SELECT * FROM \"TB_CONFIG_ANOMALIES\";"
```

Une ligne doit exister, avec ton taux et ton compteur.

### F.5 — Remettre à zéro avant de continuer

Les anomalies faussent volontairement les données. Une fois le test concluant, **désactive l'injection** dans le panneau et clique sur la remise à zéro du compteur.

### F.6 — Commit

⚠️ **Depuis la racine.**

```powershell
cd C:\Users\charles.nguessan\Documents\simulateur_V5
```

```powershell
git add .
```

```powershell
git status --short
```

```powershell
git commit -m "anomalies: branche l'injection sur le moteur et persiste la configuration en base"
```

```powershell
git push origin main
```

---

## Récapitulatif

| Partie | Fichier | Nature |
|---|---|---|
| **A.1** | `anomalies/__init__.py` | **Créé** |
| **A.2** | `anomalies/models.py` | **Créé** — modèle de `TB_CONFIG_ANOMALIES` |
| **A.3** | `anomalies/config.py` | **Créé** — remplace `seed/anomalies.py`, + 3 injecteurs |
| **A.4** | `anomalies/repository.py` | **Créé** — charger / sauvegarder |
| **A.5** | `seed/anomalies.py` | **Supprimé** |
| **B** | `seed/runner.py`, `seed/__main__.py`, `api/routers/anomalies.py` | Imports mis à jour |
| **C.1** | `api/routers/anomalies.py` | Sauvegarde après `PATCH` et après `reset` |
| **C.2** | `api/main.py` | Charge au démarrage, sauvegarde à l'extinction |
| **D.1-4** | `simulation/passage.py` | 🎯 **3 points d'injection** dans le parcours |
| **E** | `README.md` | La promesse devient exacte |

---

## Ce qu'on ne fait PAS dans ce chantier

**Le mode `severity: "hard"`.** Le champ existe et se pilote par l'API, mais seul `"soft"` a un sens aujourd'hui : des données incohérentes qui passent les contraintes SQL.

Un mode `"hard"` — violations de clés étrangères, transactions interrompues en plein vol — serait un tout autre exercice : il éprouverait la gestion d'erreurs et non la cohérence métier. À traiter séparément si le besoin apparaît.

---

## Suite du plan

| Chantier | Objet |
|---|---|
| ~~0~~ | ~~Remise en route sur la nouvelle machine~~ ✅ |
| ~~1~~ | ~~Hygiène git & secrets~~ ✅ `fad04bd` |
| ~~2~~ | ~~Nettoyage des doublons~~ ✅ `7ef5a3c` |
| ~~3~~ | ~~Docker & temps réel~~ ✅ `dedd982` |
| ~~4~~ | ~~Sécurisation des endpoints~~ ✅ `dfcd1eb` |
| **5** | **Anomalies branchées sur le moteur** ← *ce guide* |
| 6 | Performance des KPI (agrégations SQL) |
| 7 | Tests automatisés (pytest + CI) |
| 8 | Figer la migration `0001` en SQL explicite |
