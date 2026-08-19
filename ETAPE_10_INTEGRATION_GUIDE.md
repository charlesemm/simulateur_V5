# Étape 10 — Guide d'intégration pas-à-pas

## ⚠️ Important avant de commencer

**On va faire ça ensemble, étape par étape.**  
À chaque étape, je te montrerai :
- Exactement ce qu'il y a à faire
- Où le faire (fichier + ligne)
- Avant/Après pour voir la différence
- Toi, tu feras l'action et tu me dis "OK, j'ai fait"

---

## 📋 Vue d'ensemble des modifications

**Total : 5 fichiers à créer + 4 fichiers à modifier**

```
Fichiers À CRÉER (0 ligne existante) :
├── seed/anomalies.py              ← Module d'injection d'anomalies
├── api/routers/anomalies.py        ← Endpoint API
└── dashboard/src/components/AnomaliesPanel.tsx  ← Composant React

Fichiers À MODIFIER (ajouter du code) :
├── seed/__main__.py               ← Charger config anomalies
├── seed/runner.py                 ← Appliquer anomalies au seed
├── api/main.py                    ← Brancher router anomalies
└── dashboard/src/App.tsx          ← Ajouter onglet anomalies (optionnel)
```

---

## **ÉTAPE 1 : Créer `seed/anomalies.py`**

**Fichier entièrement nouveau.** Copie-colle ce contenu complet :

```python
"""Injecteur d'anomalies 'douces' pour le seed du simulateur.

Les anomalies 'douces' sont des données bizarres ou incohérentes qui
respectent les contraintes SQL mais qui révèlent des bugs métier.
"""
from __future__ import annotations

import random
from decimal import Decimal
from datetime import date, timedelta
from typing import Any, TypeVar

T = TypeVar("T")


class AnomaliesConfig:
    """Configuration en mémoire, chargeable depuis env ou modifiable via API."""

    def __init__(
        self,
        enabled: bool = False,
        rate: float = 0.0,  # Probabilité d'injection (0.0 à 1.0)
        seed: int = 42,
        severity: str = "soft",  # "soft" v1 ou "hard" v2
    ) -> None:
        self.enabled = enabled
        self.rate = max(0.0, min(1.0, rate))  # Clamp à [0, 1]
        self.random = random.Random(seed)
        self.severity = severity
        self.injected_count = 0

    def should_inject(self) -> bool:
        """Décide aléatoirement s'il faut injecter une anomalie."""
        if not self.enabled:
            return False
        return self.random.random() < self.rate

    def record_injection(self) -> None:
        """Enregistre une anomalie injectée (pour le rapport)."""
        self.injected_count += 1


# Instance unique, partagée par tout le processus.
anomalies_config = AnomaliesConfig()


def inject_numero_secu(numero: str, config: AnomaliesConfig) -> str:
    """Retourne un NUMERO_SECU potentiellement malformé."""
    if config.should_inject():
        config.record_injection()
        return "00000000000000"
    return numero


def inject_email(email: str, config: AnomaliesConfig) -> str:
    """Retourne un email potentiellement invalide."""
    if config.should_inject():
        config.record_injection()
        return "pas_un_email_valide"
    return email


def inject_date_cohesion(start: date, end: date | None, config: AnomaliesConfig) -> date | None:
    """Retourne une date de fin potentiellement avant la date de début."""
    if not end or not config.should_inject():
        return end
    config.record_injection()
    return start - timedelta(days=config.random.randint(1, 365))


def inject_montant(montant: Decimal, config: AnomaliesConfig) -> Decimal:
    """Retourne un montant potentiellement aberrant."""
    if config.should_inject():
        config.record_injection()
        choice = config.random.choice(["negatif", "extreme"])
        if choice == "negatif":
            return Decimal("-1000.00")
        else:
            return Decimal("999999999.99")
    return montant


def apply_anomalies_to_row(row: dict[str, Any], config: AnomaliesConfig, row_type: str) -> dict[str, Any]:
    """Applique des anomalies à une ligne selon son type.
    
    row_type : "agent", "insured", "center_assignment"
    """
    if not config.enabled:
        return row

    if row_type == "agent":
        if "agent_email" in row:
            row["agent_email"] = inject_email(row["agent_email"], config)
    elif row_type == "insured":
        if "numero_secu" in row:
            row["numero_secu"] = inject_numero_secu(row["numero_secu"], config)
    elif row_type == "center_assignment":
        if "date_fin" in row and "date_debut" in row:
            row["date_fin"] = inject_date_cohesion(row["date_debut"], row["date_fin"], config)

    return row
```

**✅ Action :**
1. Crée un nouveau fichier `seed/anomalies.py`
2. Copie-colle le code ci-dessus
3. Sauvegarde
4. Dis-moi "ÉTAPE 1 OK" quand c'est fait

---

## **ÉTAPE 2 : Modifier `seed/__main__.py`**

**Fichier actuellement très court (5 lignes).**

### AVANT :
```python
"""Permet d'exécuter le seed avec la commande python -m seed."""

from seed.runner import main


if __name__ == "__main__":
    main()
```

### APRÈS :
```python
"""Permet d'exécuter le seed avec la commande python -m seed."""

import os
from seed.anomalies import anomalies_config
from seed.runner import main


if __name__ == "__main__":
    # Charger la configuration des anomalies depuis les variables d'env
    anomalies_config.enabled = os.getenv("ANOMALIES_ENABLED", "false").lower() == "true"
    try:
        anomalies_config.rate = float(os.getenv("ANOMALIES_RATE", "0.0"))
    except ValueError:
        anomalies_config.rate = 0.0
    
    main()
    
    # Afficher un résumé après le seed
    if anomalies_config.injected_count > 0:
        print(f"\n✓ Seed complété. Anomalies injectées : {anomalies_config.injected_count}")
    else:
        print("\n✓ Seed complété. Aucune anomalie.")
```

**✅ Action :**
1. Ouvre `seed/__main__.py`
2. Remplace son contenu par le code APRÈS ci-dessus
3. Sauvegarde
4. Dis-moi "ÉTAPE 2 OK"

---

## **ÉTAPE 3 : Modifier `seed/runner.py` — Ajouter l'import**

**Fichier existant long. On va ajouter 1 ligne en haut.**

### Localisation : Ligne 1-25 (zone imports)

#### AVANT (lignes 1-25) :
```python
from __future__ import annotations

import asyncio
import logging
import random
from datetime import date
import unicodedata
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from faker import Faker
from sqlalchemy import  func, inspect
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session_factory
from app.models import (
    Agent, CenterHealthAgent, HealthCenter, HealthProfessional,
    HealthProfessionalCenter, HealthProfessionalMedicalSpecialty,
    InsuredPerson, MedicalAct, MedicalSpecialty, Medication, Pathology,
    TypeInvoice,
)

from seed.constants import (
    HEALTH_CENTER_TYPES, INVOICE_TYPES, IVORIAN_CITIES,
    IVORIAN_FIRST_NAMES, IVORIAN_LAST_NAMES, MEDICAL_ACTS,
    MEDICAL_SPECIALTIES, MEDICATION_SEEDS, PATHOLOGY_LABELS,
)
```

#### APRÈS (ajouter cette ligne après line 26) :
```python
from seed.constants import (
    HEALTH_CENTER_TYPES, INVOICE_TYPES, IVORIAN_CITIES,
    IVORIAN_FIRST_NAMES, IVORIAN_LAST_NAMES, MEDICAL_ACTS,
    MEDICAL_SPECIALTIES, MEDICATION_SEEDS, PATHOLOGY_LABELS,
)
from seed.anomalies import anomalies_config, apply_anomalies_to_row  # ← NOUVELLE LIGNE
```

**✅ Action :**
1. Ouvre `seed/runner.py`
2. Après la ligne `from seed.constants import ...`, ajoute :
   ```python
   from seed.anomalies import anomalies_config, apply_anomalies_to_row
   ```
3. Sauvegarde
4. Dis-moi "ÉTAPE 3 OK"

---

## **ÉTAPE 4 : Modifier `seed/runner.py` — Fonction `build_agents()`**

**Fonction existante, on ajoute 1 ligne.**

### Localisation : environ ligne 155-175

#### AVANT :
```python
def build_agents() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Crée cinquante agents d'accueil affectés et dix médecins conseils centraux."""

    agents, assignments = [], []
    for index in range(60):
        last_name, first_name = synthetic_identity(index)
        agent_code = f"AG{index + 1:03d}"
        agent_type = "accueil" if index < 50 else "medecin_conseil"
        email_root = normalize_text(f"{first_name}.{last_name}").lower().replace("'", "")
        agents.append({
            "agent_code": agent_code,
            "agent_code_gestion": f"GEST{index + 1:04d}",
            "agent_prenoms": first_name,
            "agent_nom": last_name,
            "agent_email": f"{email_root}.{index + 1}@cmu.demo.ci",
            "agent_type_code": agent_type,
            **audit_values(),
        })
        # Les médecins conseils appartiennent au niveau central...
        if agent_type == "accueil":
            assignments.append({
                "centre_sante_code": f"CS{index % 30 + 1:03d}",
                "agent_code": agent_code,
                "date_debut": VALID_FROM,
                "date_fin": None,
                **audit_values(),
            })
    return agents, assignments
```

#### APRÈS (ajouter 2 lignes) :
```python
def build_agents() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Crée cinquante agents d'accueil affectés et dix médecins conseils centraux."""

    agents, assignments = [], []
    for index in range(60):
        last_name, first_name = synthetic_identity(index)
        agent_code = f"AG{index + 1:03d}"
        agent_type = "accueil" if index < 50 else "medecin_conseil"
        email_root = normalize_text(f"{first_name}.{last_name}").lower().replace("'", "")
        agent_row = {
            "agent_code": agent_code,
            "agent_code_gestion": f"GEST{index + 1:04d}",
            "agent_prenoms": first_name,
            "agent_nom": last_name,
            "agent_email": f"{email_root}.{index + 1}@cmu.demo.ci",
            "agent_type_code": agent_type,
            **audit_values(),
        }
        # ← AJOUTE CES 2 LIGNES :
        agent_row = apply_anomalies_to_row(agent_row, anomalies_config, "agent")
        agents.append(agent_row)
        
        # Les médecins conseils appartiennent au niveau central...
        if agent_type == "accueil":
            assignments.append({
                "centre_sante_code": f"CS{index % 30 + 1:03d}",
                "agent_code": agent_code,
                "date_debut": VALID_FROM,
                "date_fin": None,
                **audit_values(),
            })
    return agents, assignments
```

**✅ Action :**
1. Ouvre `seed/runner.py`
2. Localise la fonction `build_agents()`
3. Remplace `agents.append({...})` par :
   ```python
   agent_row = {...}  # le dict existant
   agent_row = apply_anomalies_to_row(agent_row, anomalies_config, "agent")
   agents.append(agent_row)
   ```
4. Sauvegarde
5. Dis-moi "ÉTAPE 4 OK"

---

## **ÉTAPE 5 : Modifier `seed/runner.py` — Fonction `build_insured_people()`**

**Fonction existante, on ajoute 2 lignes.**

### Localisation : environ ligne 195-210

#### AVANT :
```python
def build_insured_people() -> list[dict[str, Any]]:
    """Crée deux mille assurés aux identifiants stables et non séquentiels."""

    rows = []
    for index in range(100000):
        last_name, first_name = synthetic_identity(index + 100)
        rows.append({
            "personne_uuid": uuid5(NAMESPACE_URL, f"cmu-demo-assure-{index + 1}"),
            "numero_recepisse": f"REC-{2026}-{index + 1:06d}",
            "assure_numero_identifiant": f"CMU{index + 1:010d}",
            "numero_secu": f"{index + 1:013d}",
            "civilite_code": "MME" if index % 2 == 0 else "M",
            "assure_nom": last_name,
            "assure_nom_patronymique": last_name if index % 5 else f"{last_name}-{first_name}",
            **audit_values(),
        })
    return rows
```

#### APRÈS :
```python
def build_insured_people() -> list[dict[str, Any]]:
    """Crée deux mille assurés aux identifiants stables et non séquentiels."""

    rows = []
    for index in range(100000):
        last_name, first_name = synthetic_identity(index + 100)
        insured_row = {
            "personne_uuid": uuid5(NAMESPACE_URL, f"cmu-demo-assure-{index + 1}"),
            "numero_recepisse": f"REC-{2026}-{index + 1:06d}",
            "assure_numero_identifiant": f"CMU{index + 1:010d}",
            "numero_secu": f"{index + 1:013d}",
            "civilite_code": "MME" if index % 2 == 0 else "M",
            "assure_nom": last_name,
            "assure_nom_patronymique": last_name if index % 5 else f"{last_name}-{first_name}",
            **audit_values(),
        }
        # ← AJOUTE CES 2 LIGNES :
        insured_row = apply_anomalies_to_row(insured_row, anomalies_config, "insured")
        rows.append(insured_row)
    return rows
```

**✅ Action :**
1. Ouvre `seed/runner.py`
2. Localise la fonction `build_insured_people()`
3. Remplace `rows.append({...})` par le même pattern (dict temp + anomalies)
4. Sauvegarde
5. Dis-moi "ÉTAPE 5 OK"

---

## **ÉTAPE 6 : Créer `api/routers/anomalies.py`**

**Fichier entièrement nouveau.**

```python
"""Gestion de la configuration des anomalies du simulateur."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from auth.dependencies import require_role
from seed.anomalies import anomalies_config

router = APIRouter(
    prefix="/anomalies",
    tags=["anomalies"],
    dependencies=[Depends(require_role("administrateur"))],
)


class AnomaliesConfigRequest(BaseModel):
    """Requête pour modifier la configuration."""
    enabled: bool | None = None
    rate: float | None = Field(None, ge=0.0, le=1.0)
    severity: str | None = None


class AnomaliesConfigResponse(BaseModel):
    """Réponse avec la configuration actuelle."""
    enabled: bool
    rate: float
    severity: str
    injected_count: int


@router.get("", response_model=AnomaliesConfigResponse)
async def get_anomalies_config() -> AnomaliesConfigResponse:
    """Retourne la configuration courante des anomalies."""
    return AnomaliesConfigResponse(
        enabled=anomalies_config.enabled,
        rate=anomalies_config.rate,
        severity=anomalies_config.severity,
        injected_count=anomalies_config.injected_count,
    )


@router.patch("", response_model=AnomaliesConfigResponse)
async def update_anomalies_config(payload: AnomaliesConfigRequest) -> AnomaliesConfigResponse:
    """Modifie la configuration à la volée (en mémoire uniquement pour v1)."""
    if payload.enabled is not None:
        anomalies_config.enabled = payload.enabled
    if payload.rate is not None:
        anomalies_config.rate = payload.rate
    if payload.severity is not None:
        anomalies_config.severity = payload.severity

    return AnomaliesConfigResponse(
        enabled=anomalies_config.enabled,
        rate=anomalies_config.rate,
        severity=anomalies_config.severity,
        injected_count=anomalies_config.injected_count,
    )


@router.post("/reset")
async def reset_anomalies_count() -> dict[str, str]:
    """Réinitialise le compteur d'anomalies injectées."""
    anomalies_config.injected_count = 0
    return {"message": "Compteur d'anomalies réinitialisé."}
```

**✅ Action :**
1. Crée un nouveau fichier `api/routers/anomalies.py`
2. Copie-colle le code ci-dessus
3. Sauvegarde
4. Dis-moi "ÉTAPE 6 OK"

---

## **ÉTAPE 7 : Modifier `api/main.py` — Ajouter l'import du router**

**Fichier existant, ajouter 1 ligne d'import.**

### Localisation : ligne 1-20 (zone imports)

#### AVANT (lignes 10-15) :
```python
import app
from api.routers import centres, factures, kpi, simulation
from api.schema import HealthResponse
from api.services.simulation_manager import simulation_manager
```

#### APRÈS (ajouter cette ligne) :
```python
import app
from api.routers import centres, factures, kpi, simulation
from api.routers import anomalies as anomalies_router  # ← NOUVELLE LIGNE
from api.schema import HealthResponse
from api.services.simulation_manager import simulation_manager
```

**✅ Action :**
1. Ouvre `api/main.py`
2. Après les autres imports de routers, ajoute :
   ```python
   from api.routers import anomalies as anomalies_router
   ```
3. Sauvegarde
4. Dis-moi "ÉTAPE 7A OK"

---

## **ÉTAPE 8 : Modifier `api/main.py` — Brancher le router**

### Localisation : ligne 65-72 (zone `include_router`)

#### AVANT (lignes 65-72) :
```python
fastapi_app.include_router(simulation.router)
fastapi_app.include_router(kpi.router)
fastapi_app.include_router(factures.router)
fastapi_app.include_router(centres.router)
fastapi_app.include_router(auth_router.router)
fastapi_app.include_router(users_router.router)
fastapi_app.include_router(reports_router.router)
```

#### APRÈS (ajouter 1 ligne) :
```python
fastapi_app.include_router(simulation.router)
fastapi_app.include_router(kpi.router)
fastapi_app.include_router(factures.router)
fastapi_app.include_router(centres.router)
fastapi_app.include_router(auth_router.router)
fastapi_app.include_router(users_router.router)
fastapi_app.include_router(reports_router.router)
fastapi_app.include_router(anomalies_router.router)  # ← NOUVELLE LIGNE
```

**✅ Action :**
1. Ouvre `api/main.py`
2. Après les autres `include_router(...)`, ajoute :
   ```python
   fastapi_app.include_router(anomalies_router.router)
   ```
3. Sauvegarde
4. Dis-moi "ÉTAPE 8 OK"

---

## **ÉTAPE 9 : Créer `dashboard/src/components/AnomaliesPanel.tsx`**

**Fichier entièrement nouveau (React).**

```tsx
import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";

interface AnomaliesConfig {
  enabled: boolean;
  rate: number;
  severity: "soft" | "hard";
  injected_count: number;
}

const API_URL = import.meta.env.VITE_API_URL as string;

export function AnomaliesPanel() {
  const { token } = useAuth();
  const [config, setConfig] = useState<AnomaliesConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchConfig();
  }, [token]);

  async function fetchConfig() {
    try {
      const response = await fetch(`${API_URL}/anomalies`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error(`Erreur ${response.status}`);
      setConfig(await response.json());
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function updateConfig(update: Partial<AnomaliesConfig>) {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/anomalies`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(update),
      });
      if (!response.ok) throw new Error(`Erreur ${response.status}`);
      setConfig(await response.json());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  if (!config) {
    return <div className="anomalies-loading">Chargement de la configuration...</div>;
  }

  return (
    <div className="anomalies-panel">
      <h2>🔧 Configuration des anomalies</h2>
      <p className="anomalies-description">
        Injection d'anomalies "douces" dans les données du seed — bon pour tester la robustesse.
      </p>

      <div className="config-group">
        <label>
          <input
            type="checkbox"
            checked={config.enabled}
            onChange={(e) => updateConfig({ enabled: e.target.checked })}
            disabled={loading}
          />
          Anomalies activées
        </label>
      </div>

      <div className="config-group">
        <label>
          Taux d'injection : <strong>{(config.rate * 100).toFixed(1)}%</strong>
        </label>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={config.rate}
          onChange={(e) => updateConfig({ rate: parseFloat(e.target.value) })}
          disabled={loading || !config.enabled}
          className="config-range"
        />
      </div>

      <div className="config-group">
        <label>
          Sévérité :
          <select
            value={config.severity}
            onChange={(e) => updateConfig({ severity: e.target.value as any })}
            disabled={loading}
          >
            <option value="soft">Douces (données bizarres, SQL valide)</option>
            <option value="hard">Durs (non implémenté v1)</option>
          </select>
        </label>
      </div>

      <div className="anomalies-stats">
        <p>
          Anomalies injectées (depuis ce démarrage) :<strong>{config.injected_count}</strong>
        </p>
        <button
          onClick={() =>
            fetch(`${API_URL}/anomalies/reset`, {
              method: "POST",
              headers: { Authorization: `Bearer ${token}` },
            }).then(() => fetchConfig())
          }
          disabled={loading}
          className="button-reset"
        >
          Réinitialiser le compteur
        </button>
      </div>

      {error && <p className="error">{error}</p>}
    </div>
  );
}
```

**✅ Action :**
1. Crée un nouveau fichier `dashboard/src/components/AnomaliesPanel.tsx`
2. Copie-colle le code ci-dessus
3. Sauvegarde
4. Dis-moi "ÉTAPE 9 OK"

---

## **ÉTAPE 10 : Modifier `dashboard/src/App.tsx` — Importer le composant**

**Fichier existant, ajouter 1 ligne d'import.**

### Localisation : ligne 1-20 (zone imports)

#### À chercher :
```tsx
import { RequireRole } from "./auth/RequireRole";
import { UsersPage } from "./components/UsersPage";
```

#### À ajouter après :
```tsx
import { RequireRole } from "./auth/RequireRole";
import { UsersPage } from "./components/UsersPage";
import { AnomaliesPanel } from "./components/AnomaliesPanel";  // ← NOUVELLE LIGNE
```

**✅ Action :**
1. Ouvre `dashboard/src/App.tsx`
2. Ajoute l'import du composant
3. Sauvegarde
4. Dis-moi "ÉTAPE 10A OK"

---

## **ÉTAPE 11 : Modifier `dashboard/src/App.tsx` — Ajouter le composant au rendu**

**Fichier existant, ajouter le composant dans le JSX.**

### Localisation : cherche `<main className="dashboard-grid">`

#### À chercher :
```tsx
return (
  <div className="app-container">
    <Header ... />
    <main className="dashboard-grid">
      {/* Autres composants */}
    </main>
  </div>
);
```

#### À ajouter :
```tsx
<main className="dashboard-grid">
  {/* Autres composants */}
  <RequireRole minimum="administrateur">
    <AnomaliesPanel />
  </RequireRole>
</main>
```

**✅ Action :**
1. Ouvre `dashboard/src/App.tsx`
2. Dans `<main className="dashboard-grid">`, ajoute (à la fin) :
   ```tsx
   <RequireRole minimum="administrateur">
     <AnomaliesPanel />
   </RequireRole>
   ```
3. Sauvegarde
4. Dis-moi "ÉTAPE 11 OK"

---

## **ÉTAPE 12 : Ajouter les variables d'environnement**

**Fichier `.env` (à la racine du projet).**

Ajoute ces 3 lignes :

```dotenv
# Anomalies du simulateur (étape 10)
ANOMALIES_ENABLED=false
ANOMALIES_RATE=0.0
ANOMALIES_SEVERITY=soft
```

**✅ Action :**
1. Ouvre ou crée `.env` à la racine
2. Ajoute les 3 lignes ci-dessus
3. Sauvegarde
4. Dis-moi "ÉTAPE 12 OK"

---

## **ÉTAPE 13 : Ajouter les styles CSS (optionnel mais recommandé)**

**Fichier `dashboard/src/index.css`**

Ajoute à la fin du fichier :

```css
/* Anomalies Panel */
.anomalies-panel {
  background: var(--surface);
  border: 2px solid var(--warning, #f59e0b);
  border-radius: 8px;
  padding: 16px;
  margin-top: 16px;
}

.anomalies-panel h2 {
  color: var(--warning, #f59e0b);
  margin-top: 0;
  margin-bottom: 8px;
}

.anomalies-description {
  font-size: 0.9rem;
  color: var(--muted, #666);
  margin-bottom: 16px;
}

.config-group {
  margin-bottom: 16px;
}

.config-group label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 0.95rem;
  margin-bottom: 8px;
}

.config-group input[type="checkbox"] {
  cursor: pointer;
  width: 18px;
  height: 18px;
}

.config-group input[type="range"] {
  flex: 1;
  min-width: 150px;
  cursor: pointer;
}

.config-group select {
  padding: 6px;
  border: 1px solid var(--border, #ddd);
  border-radius: 4px;
  font-size: 0.95rem;
}

.anomalies-stats {
  background: var(--surface-alt, #f5f5f5);
  border-left: 4px solid var(--warning, #f59e0b);
  padding: 12px;
  margin: 12px 0;
  border-radius: 4px;
}

.anomalies-stats p {
  margin: 8px 0;
  font-size: 0.9rem;
}

.button-reset {
  background: var(--warning, #f59e0b);
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  margin-top: 8px;
}

.button-reset:hover:not(:disabled) {
  opacity: 0.9;
}

.button-reset:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.anomalies-loading {
  padding: 20px;
  color: var(--muted, #666);
  text-align: center;
}

.error {
  color: #dc2626;
  padding: 8px 12px;
  background: #fee2e2;
  border-radius: 4px;
  margin-top: 8px;
}
```

**✅ Action :**
1. Ouvre `dashboard/src/index.css`
2. Ajoute le CSS ci-dessus à la fin
3. Sauvegarde
4. Dis-moi "ÉTAPE 13 OK"

---

## **VÉRIFICATION FINALE**

Une fois toutes les étapes faites, teste ceci :

### Test 1 : Vérifier que le code compile
```powershell
# Backend
python -m compileall seed api

# Frontend
cd dashboard
npm run build
```

### Test 2 : Lancer le seed SANS anomalies
```powershell
python -m seed
```

**Résultat attendu :** Seed normal, 0 anomalies.

### Test 3 : Lancer le seed AVEC anomalies (10%)
```powershell
$env:ANOMALIES_ENABLED = "true"
$env:ANOMALIES_RATE = "0.1"
python -m seed
```

**Résultat attendu :** Message `✓ Seed complété. Anomalies injectées : ~10000` (10% de 100k assurés)

### Test 4 : Tester l'API
```powershell
# Démarrer le serveur
uvicorn main:app --reload --port 8000

# Dans un autre terminal, tester l'endpoint (remplace TON_JETON par un vrai token)
curl.exe http://127.0.0.1:8000/anomalies -H "Authorization: Bearer TON_JETON"
```

**Résultat attendu :** JSON avec la config actuelle.

### Test 5 : Vérifier dans le dashboard
1. Connecte-toi en tant qu'administrateur
2. Tu dois voir un panneau "🔧 Configuration des anomalies" en bas
3. Change le slider, cochez/décochez, vois si ça répond

---

## **Résumé des étapes**

| # | Fichier | Action | Statut |
|---|---------|--------|--------|
| 1 | `seed/anomalies.py` | Créer | ☐ |
| 2 | `seed/__main__.py` | Modifier | ☐ |
| 3 | `seed/runner.py` | Import | ☐ |
| 4 | `seed/runner.py` | build_agents() | ☐ |
| 5 | `seed/runner.py` | build_insured_people() | ☐ |
| 6 | `api/routers/anomalies.py` | Créer | ☐ |
| 7 | `api/main.py` | Import | ☐ |
| 8 | `api/main.py` | Brancher router | ☐ |
| 9 | `dashboard/src/components/AnomaliesPanel.tsx` | Créer | ☐ |
| 10 | `dashboard/src/App.tsx` | Import | ☐ |
| 11 | `dashboard/src/App.tsx` | Ajouter composant | ☐ |
| 12 | `.env` | Ajouter variables | ☐ |
| 13 | `dashboard/src/index.css` | Ajouter styles | ☐ |

---

## **À toi de jouer ! 🚀**

Commence par l'**ÉTAPE 1** :
- Crée le fichier `seed/anomalies.py`
- Copie-colle le code
- Dis-moi "ÉTAPE 1 OK" quand c'est fait

Je serai là pour chaque étape ! On progresse ensemble.
