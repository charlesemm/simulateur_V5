<!-- Guide autonome des rapports automatiques du simulateur (PDF technique + export Excel). -->

# Simulateur de parcours assuré CMU

## Étape 9/10 — Rapports automatiques (PDF technique + export Excel)

**Tutoriel d'exécution manuelle — à la suite des étapes 7 (authentification)
et 8 (dashboard).**

Cette étape ajoute deux livrables générés automatiquement chaque nuit à
minuit (et déclenchables à la demande depuis le dashboard) :

1. **Un rapport PDF technique** — uniquement des métriques liées au
   fonctionnement du simulateur lui-même (charge, fiabilité, temps de
   réponse) : **aucune métrique métier CMU**, conformément à ta demande.
2. **Un export Excel multi-feuilles** des données générées par la
   simulation ce jour-là (factures, prestations, ententes, journal
   technique) — pour analyser ou manipuler les données en dehors du
   dashboard.

---

## 1. Résultat attendu

- Un registre de métriques techniques (`metrics/registry.py`), alimenté en
  continu par le moteur, le pipeline KPI, Socket.IO et l'API elle-même.
- Un générateur PDF (`reports/pdf_generator.py`) qui produit un rapport
  lisible avec ces métriques.
- Un générateur Excel (`reports/excel_generator.py`) avec 5 feuilles :
  Résumé, Factures, Prestations, Ententes préalables, Journal technique.
- Une planification automatique à minuit (`reports/scheduler.py`, via
  `APScheduler`).
- Un endpoint `/reports` protégé (rôle `operateur` minimum, conforme au
  tableau de visibilité de l'étape 7) : lister, générer manuellement,
  télécharger.
- Un onglet **Rapports** dans le dashboard.

---

## 2. Choix techniques et limite assumée

| Choix | Pourquoi |
|---|---|
| `fpdf2` pour le PDF | Bibliothèque Python pure, aucune dépendance système (contrairement à `weasyprint`, qui demande GTK — pénible à installer sous Windows). |
| `openpyxl` pour l'Excel | Standard, pur Python, gère nativement plusieurs feuilles. |
| `APScheduler` pour la planification | Léger, s'intègre nativement à une boucle `asyncio` existante, pas besoin d'un service externe (type cron) séparé. |
| Registre de métriques **en mémoire**, pas en base | Simplicité : ces métriques techniques n'ont pas besoin de survivre à un redémarrage pour l'usage visé (surveillance/démo). |
| Fichiers stockés sur disque (`reports/output/`), pas en base | Un PDF/Excel est un fichier binaire ; le disque est plus adapté que PostgreSQL pour ça. L'historique se fait par la liste des fichiers présents. |

**Limite importante à connaître, assumée pour cette v1 :** le registre de
métriques (section 3) se réinitialise à chaque redémarrage du serveur
Uvicorn. Concrètement, le rapport de minuit reflète les métriques
**depuis le dernier redémarrage du serveur**, pas nécessairement toute la
journée si le serveur a été relancé entre-temps. Pour une démonstration ou
une session de travail continue, ce n'est pas un problème ; si tu veux
plus tard un historique qui survit aux redémarrages, il faudrait persister
des instantanés du registre en base à intervalles réguliers — hors
périmètre de cette étape.

---

## 3. Arborescence des fichiers à créer ou modifier

```text
metrics/
|-- __init__.py
`-- registry.py                        (nouveau)
reports/
|-- __init__.py
|-- paths.py                           (nouveau)
|-- pdf_generator.py                   (nouveau)
|-- excel_generator.py                 (nouveau)
`-- scheduler.py                       (nouveau)
api/routers/reports.py                 (nouveau)
main.py                                (modifié)
simulation/engine.py                   (modifié)
kpi/consumer.py                        (modifié)
realtime/socket_server.py              (modifié)
requirements.txt                       (modifié)

dashboard/src/
|-- components/ReportsPage.tsx         (nouveau)
|-- services/api.ts                    (modifié)
|-- App.tsx                            (modifié)
`-- components/Header.tsx              (modifié)
```

### Ajouter à `requirements.txt`

```text
# Rapports automatiques : PDF, export Excel, planification.
fpdf2==2.8.1
openpyxl==3.1.5
APScheduler==3.10.4
```

```powershell
python -m pip install -r requirements.txt
```

---

## 4. Le registre de métriques techniques

### 4.1 `metrics/registry.py`

```python
"""Registre en mémoire des métriques TECHNIQUES du simulateur.

Volontairement : aucune métrique métier CMU ici (montants remboursés,
répartition des pathologies, etc.) -- uniquement des indicateurs sur le
fonctionnement du simulateur lui-même (charge, fiabilité, latence).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class TechnicalMetricsRegistry:
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    passages_reussis: int = 0
    passages_echoues: int = 0
    pic_passages_simultanes: int = 0

    recalculs_kpi: int = 0
    duree_totale_recalculs_kpi_secondes: float = 0.0

    connexions_socketio_total: int = 0
    deconnexions_socketio_total: int = 0
    clients_socketio_actifs: int = 0

    requetes_api_total: int = 0
    duree_totale_requetes_api_secondes: float = 0.0

    def enregistrer_passage(self, succes: bool) -> None:
        if succes:
            self.passages_reussis += 1
        else:
            self.passages_echoues += 1

    def enregistrer_pic(self, valeur: int) -> None:
        self.pic_passages_simultanes = max(self.pic_passages_simultanes, valeur)

    def enregistrer_recalcul_kpi(self, duree_secondes: float) -> None:
        self.recalculs_kpi += 1
        self.duree_totale_recalculs_kpi_secondes += duree_secondes

    def enregistrer_connexion_socketio(self) -> None:
        self.connexions_socketio_total += 1
        self.clients_socketio_actifs += 1

    def enregistrer_deconnexion_socketio(self) -> None:
        self.deconnexions_socketio_total += 1
        self.clients_socketio_actifs = max(0, self.clients_socketio_actifs - 1)

    def enregistrer_requete_api(self, duree_secondes: float) -> None:
        self.requetes_api_total += 1
        self.duree_totale_requetes_api_secondes += duree_secondes

    def uptime_secondes(self) -> float:
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()

    def temps_moyen_recalcul_kpi_ms(self) -> float:
        if self.recalculs_kpi == 0:
            return 0.0
        return (self.duree_totale_recalculs_kpi_secondes / self.recalculs_kpi) * 1000

    def temps_moyen_reponse_api_ms(self) -> float:
        if self.requetes_api_total == 0:
            return 0.0
        return (self.duree_totale_requetes_api_secondes / self.requetes_api_total) * 1000

    def snapshot(self) -> dict:
        total_passages = self.passages_reussis + self.passages_echoues
        return {
            "demarre_depuis": self.started_at.isoformat(),
            "uptime_secondes": round(self.uptime_secondes(), 1),
            "passages_reussis": self.passages_reussis,
            "passages_echoues": self.passages_echoues,
            "taux_echec_pourcent": round(100 * self.passages_echoues / max(1, total_passages), 2),
            "pic_passages_simultanes": self.pic_passages_simultanes,
            "recalculs_kpi": self.recalculs_kpi,
            "temps_moyen_recalcul_kpi_ms": round(self.temps_moyen_recalcul_kpi_ms(), 1),
            "connexions_socketio_total": self.connexions_socketio_total,
            "deconnexions_socketio_total": self.deconnexions_socketio_total,
            "clients_socketio_actifs": self.clients_socketio_actifs,
            "requetes_api_total": self.requetes_api_total,
            "temps_moyen_reponse_api_ms": round(self.temps_moyen_reponse_api_ms(), 1),
        }


# Instance unique partagée par tout le processus (moteur, KPI, Socket.IO, API).
registry = TechnicalMetricsRegistry()
```

### 4.2 `metrics/__init__.py`

```python
"""Métriques techniques du simulateur (hors périmètre métier)."""
```

---

## 5. Brancher le registre sur les composants existants

Quatre petites modifications sur des fichiers déjà créés aux étapes 3, 4 et
5 — chacune ajoute quelques lignes, sans rien réécrire d'existant.

### 5.1 `simulation/engine.py` — passages réussis/échoués et pic de charge

Ajouter en haut du fichier :

```python
from metrics.registry import registry as metrics_registry
```

Dans `_reserve_insured`, juste après
`self._insured_in_progress.add(insured_id)`, ajouter :

```python
metrics_registry.enregistrer_pic(len(self._insured_in_progress))
```

Dans `_run_one`, remplacer :

```python
        except Exception:
            logger.exception("Le passage %s a échoué.", sequence)
        finally:
```

par :

```python
        except Exception:
            logger.exception("Le passage %s a échoué.", sequence)
            metrics_registry.enregistrer_passage(succes=False)
        else:
            metrics_registry.enregistrer_passage(succes=True)
        finally:
```

### 5.2 `kpi/consumer.py` — temps de recalcul des KPI

Ajouter en haut du fichier :

```python
import time
from metrics.registry import registry as metrics_registry
```

Dans `_run`, remplacer :

```python
                snapshot = await self.service.calculate_snapshot()
```

par :

```python
                debut_calcul = time.perf_counter()
                snapshot = await self.service.calculate_snapshot()
                metrics_registry.enregistrer_recalcul_kpi(time.perf_counter() - debut_calcul)
```

### 5.3 `realtime/socket_server.py` — connexions et déconnexions

Ajouter en haut du fichier :

```python
from metrics.registry import registry as metrics_registry
```

Dans la fonction `connect(sid, environ, auth)` existante, ajouter en toute
première ligne du corps :

```python
    metrics_registry.enregistrer_connexion_socketio()
```

Ajouter une nouvelle fonction (aucun équivalent n'existait avant cette
étape) :

```python
@sio.event(namespace="/kpi")
async def disconnect(sid) -> None:
    """Suit les déconnexions pour le rapport technique quotidien."""

    metrics_registry.enregistrer_deconnexion_socketio()
```

### 5.4 `main.py` — temps de réponse de l'API

Ajouter, à côté des imports existants :

```python
import time

from metrics.registry import registry as metrics_registry
```

Puis, juste après la création de `app = FastAPI(...)` (étape 5) :

```python
@app.middleware("http")
async def mesurer_temps_reponse(request, call_next):
    """Chronomètre chaque requête REST pour le rapport technique quotidien."""

    if request.url.path.startswith("/socket.io"):
        return await call_next(request)
    debut = time.perf_counter()
    reponse = await call_next(request)
    metrics_registry.enregistrer_requete_api(time.perf_counter() - debut)
    return reponse
```

---

## 6. Générer le PDF technique

### `reports/paths.py`

```python
"""Emplacement partagé des rapports générés sur le disque."""
from pathlib import Path

OUTPUT_DIR = Path("reports/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
```

### `reports/pdf_generator.py`

```python
"""Construit le rapport technique quotidien au format PDF."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from fpdf import FPDF

from metrics.registry import registry
from reports.paths import OUTPUT_DIR


def build_daily_pdf_report(jour: date) -> Path:
    """Génère un PDF récapitulant les métriques techniques du registre."""

    donnees = registry.snapshot()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Rapport technique quotidien - Simulateur CMU", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Date du rapport : {jour.isoformat()}", ln=True)
    pdf.ln(4)

    sections = [
        ("Disponibilité de l'API", [
            ("Serveur démarré depuis", donnees["demarre_depuis"]),
            ("Uptime (secondes)", donnees["uptime_secondes"]),
            ("Requêtes API traitées", donnees["requetes_api_total"]),
            ("Temps de réponse moyen (ms)", donnees["temps_moyen_reponse_api_ms"]),
        ]),
        ("Moteur de simulation", [
            ("Passages réussis", donnees["passages_reussis"]),
            ("Passages échoués", donnees["passages_echoues"]),
            ("Taux d'échec (%)", donnees["taux_echec_pourcent"]),
            ("Pic de passages simultanés atteint", donnees["pic_passages_simultanes"]),
        ]),
        ("Pipeline KPI (étape 4)", [
            ("Recalculs déclenchés", donnees["recalculs_kpi"]),
            ("Temps moyen par recalcul (ms)", donnees["temps_moyen_recalcul_kpi_ms"]),
        ]),
        ("Connexions temps réel (Socket.IO)", [
            ("Connexions totales", donnees["connexions_socketio_total"]),
            ("Déconnexions totales", donnees["deconnexions_socketio_total"]),
            ("Clients actuellement connectés", donnees["clients_socketio_actifs"]),
        ]),
    ]

    for titre, paires in sections:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 9, titre, ln=True)
        pdf.set_font("Helvetica", "", 11)
        for libelle, valeur in paires:
            pdf.cell(0, 7, f"    {libelle} : {valeur}", ln=True)
        pdf.ln(3)

    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(
        0, 5,
        "Ce rapport ne contient volontairement aucune métrique métier CMU "
        "(montants, pathologies, ententes) -- uniquement des indicateurs sur "
        "le fonctionnement technique du simulateur.",
    )

    chemin = OUTPUT_DIR / f"rapport_technique_{jour.isoformat()}.pdf"
    pdf.output(str(chemin))
    return chemin
```

---

## 7. Générer l'export Excel multi-feuilles

### `reports/excel_generator.py`

```python
"""Construit l'export Excel multi-feuilles des données générées ce jour-là."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import select

from app.database import async_session_factory
from app.models import Invoice, InvoiceProvision, PriorAuthorization
from events.models import EventJournal
from reports.paths import OUTPUT_DIR


def _bornes_journee(jour: date) -> tuple[datetime, datetime]:
    """Renvoie les bornes [00:00, 23:59:59] du jour, en UTC."""

    debut = datetime.combine(jour, time.min, tzinfo=timezone.utc)
    fin = datetime.combine(jour, time.max, tzinfo=timezone.utc)
    return debut, fin


async def build_daily_excel_export(jour: date) -> Path:
    """Exporte les factures, prestations, ententes et événements du jour."""

    debut, fin = _bornes_journee(jour)
    classeur = Workbook()
    compteurs: dict[str, int] = {}

    async with async_session_factory() as session:
        factures = list((await session.execute(
            select(Invoice).where(Invoice.date_creation.between(debut, fin))
        )).scalars())
        compteurs["Factures"] = len(factures)
        feuille = classeur.create_sheet("Factures")
        feuille.append([
            "Numéro facture", "Assuré (UUID)", "Centre", "Type facture",
            "Date des soins", "Dossier", "Créée le",
        ])
        for f in factures:
            feuille.append([
                f.facture_numero, str(f.personne_uuid), f.centre_sante_code,
                f.type_facture_code, f.facture_date_soins.isoformat(),
                f.dossier_numero, f.date_creation.isoformat(),
            ])

        prestations = list((await session.execute(
            select(InvoiceProvision).where(InvoiceProvision.date_creation.between(debut, fin))
        )).scalars())
        compteurs["Prestations"] = len(prestations)
        feuille = classeur.create_sheet("Prestations")
        feuille.append([
            "Facture", "Prestation", "Professionnel", "Statut remboursement",
            "Montant dépensé", "Montant remboursé", "Montant assuré",
        ])
        for p in prestations:
            feuille.append([
                p.facture_numero, p.prestation_code, p.professionnel_sante_code,
                p.statut_remboursement, float(p.prestation_montant_depense or 0),
                float(p.prestation_montant_rq or 0), float(p.prestation_montant_assure or 0),
            ])

        ententes = list((await session.execute(
            select(PriorAuthorization).where(PriorAuthorization.date_creation.between(debut, fin))
        )).scalars())
        compteurs["Ententes préalables"] = len(ententes)
        feuille = classeur.create_sheet("Ententes préalables")
        feuille.append([
            "Numéro entente", "Centre", "Assuré (UUID)", "Dossier",
            "Type demande", "Date début", "Facture liée",
        ])
        for e in ententes:
            feuille.append([
                e.entente_prealable_numero, e.centre_sante_code, str(e.personne_uuid),
                e.dossier_numero, e.type_demande_code,
                e.entente_prealable_date_debut.isoformat(), e.facture_numero or "",
            ])

        # Limité à 2000 lignes : le journal technique peut grossir vite,
        # inutile de tout charger dans un fichier destiné à être lu à l'oeil.
        evenements = list((await session.execute(
            select(EventJournal).where(EventJournal.date_creation.between(debut, fin))
            .order_by(EventJournal.simulated_at).limit(2000)
        )).scalars())
        compteurs["Événements techniques (max. 2000)"] = len(evenements)
        feuille = classeur.create_sheet("Journal technique")
        feuille.append(["Type d'événement", "Passage", "Horodatage simulé"])
        for ev in evenements:
            feuille.append([ev.type_evenement, ev.passage_id, ev.simulated_at.isoformat()])

    resume = classeur.active
    resume.title = "Résumé"
    resume.append(["Export de données -- Simulateur CMU"])
    resume.append(["Date", jour.isoformat()])
    resume.append([])
    resume.append(["Feuille", "Lignes exportées"])
    for nom, total in compteurs.items():
        resume.append([nom, total])

    chemin = OUTPUT_DIR / f"export_donnees_{jour.isoformat()}.xlsx"
    classeur.save(chemin)
    return chemin
```

---

## 8. Planification automatique à minuit

### `reports/scheduler.py`

```python
"""Planifie la génération quotidienne des rapports et l'expose à la demande."""
from __future__ import annotations

import logging
from datetime import date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from reports.excel_generator import build_daily_excel_export
from reports.pdf_generator import build_daily_pdf_report

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def generate_reports_for_day(jour: date) -> dict[str, str]:
    """Génère les deux rapports (PDF + Excel) pour le jour indiqué."""

    pdf_path = build_daily_pdf_report(jour)
    excel_path = await build_daily_excel_export(jour)
    logger.info("Rapports générés pour %s : %s, %s", jour, pdf_path.name, excel_path.name)
    return {"pdf": pdf_path.name, "excel": excel_path.name}


async def _job_minuit() -> None:
    """Génère le rapport de la journée qui vient de s'achever."""

    hier = date.today() - timedelta(days=1)
    await generate_reports_for_day(hier)


def start_scheduler() -> None:
    scheduler.add_job(_job_minuit, CronTrigger(hour=0, minute=0), id="rapports_quotidiens", replace_existing=True)
    scheduler.start()


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
```

### `reports/__init__.py`

```python
"""Génération des rapports techniques et des exports de données."""
```

### Brancher le planificateur dans `main.py`

Ajouter, à côté des imports :

```python
from reports.scheduler import start_scheduler, stop_scheduler
```

Dans le `lifespan` déjà présent depuis l'étape 5, ajouter
`start_scheduler()` juste après le démarrage du consommateur KPI, et
`stop_scheduler()` juste avant son arrêt :

```python
async def lifespan(app: FastAPI):
    await kpi_consumer.start()
    start_scheduler()
    yield
    stop_scheduler()
    await kpi_consumer.stop()
```

---

## 9. L'endpoint `/reports`

### `api/routers/reports.py`

Accessible aux rôles `operateur` et `administrateur` — pas `observateur`,
conformément au tableau de visibilité de l'étape 7.

```python
"""Consultation et génération manuelle des rapports quotidiens."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from auth.dependencies import require_role
from reports.paths import OUTPUT_DIR
from reports.scheduler import generate_reports_for_day

router = APIRouter(
    prefix="/reports",
    tags=["rapports"],
    dependencies=[Depends(require_role("operateur"))],
)


@router.get("")
async def list_reports() -> list[str]:
    """Liste les rapports déjà générés, du plus récent au plus ancien."""

    fichiers = sorted(OUTPUT_DIR.glob("*.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [f.name for f in fichiers]


@router.post("/generate")
async def generate_report(jour: date | None = None) -> dict[str, str]:
    """Déclenche la génération manuelle pour le jour indiqué (aujourd'hui par défaut)."""

    return await generate_reports_for_day(jour or date.today())


@router.get("/{nom_fichier}")
async def download_report(nom_fichier: str) -> FileResponse:
    """Télécharge un rapport précis, en se protégeant d'un chemin détourné."""

    chemin = (OUTPUT_DIR / nom_fichier).resolve()
    if chemin.parent != OUTPUT_DIR.resolve() or not chemin.is_file():
        raise HTTPException(status_code=404, detail="Rapport introuvable.")
    return FileResponse(chemin, filename=nom_fichier)
```

Brancher dans `main.py`, à côté des autres routers :

```python
from api.routers import reports as reports_router
# ...
app.include_router(reports_router.router)
```

---

## 10. Frontend : onglet Rapports

### Ajouter à `services/api.ts`

```typescript
async listReports(token: string | null) {
  const response = await fetch(`${API_URL}/reports`, { headers: authHeaders(token) });
  return parseOrThrow<string[]>(response);
},

async generateReport(token: string | null) {
  const response = await fetch(`${API_URL}/reports/generate`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return parseOrThrow<{ pdf: string; excel: string }>(response);
},

async downloadReport(nomFichier: string, token: string | null) {
  const response = await fetch(`${API_URL}/reports/${nomFichier}`, { headers: authHeaders(token) });
  if (!response.ok) throw new Error("Téléchargement impossible.");
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const lien = document.createElement("a");
  lien.href = url;
  lien.download = nomFichier;
  lien.click();
  window.URL.revokeObjectURL(url);
},
```

**Pourquoi passer par un blob plutôt qu'un simple lien `<a href>` :**
l'endpoint est protégé par jeton JWT (section 9) ; un lien HTML classique ne
peut pas envoyer d'en-tête `Authorization`. Télécharger via `fetch` (qui,
lui, peut porter le jeton) puis fabriquer un lien temporaire est la façon
standard de contourner cette limite.

### `dashboard/src/components/ReportsPage.tsx`

```tsx
import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { api } from "../services/api";

export function ReportsPage() {
  const { token } = useAuth();
  const [fichiers, setFichiers] = useState<string[]>([]);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  async function refresh() {
    try {
      setFichiers(await api.listReports(token));
    } catch (reason) {
      setErreur((reason as Error).message);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function handleGenerer() {
    setEnCours(true);
    setErreur(null);
    try {
      await api.generateReport(token);
      await refresh();
    } catch (reason) {
      setErreur((reason as Error).message);
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div className="reports-page">
      <div className="reports-header">
        <h2>Rapports quotidiens</h2>
        <button onClick={handleGenerer} disabled={enCours}>
          {enCours ? "Génération..." : "Générer maintenant"}
        </button>
      </div>

      {erreur && <p className="login-error">{erreur}</p>}

      <p className="reports-note">
        Le rapport technique (PDF) et l'export des données (Excel) sont
        générés automatiquement chaque nuit à minuit pour la journée
        précédente. Le bouton ci-dessus permet d'en déclencher un pour
        aujourd'hui, sans attendre.
      </p>

      <ul className="reports-list">
        {fichiers.map((nom) => (
          <li key={nom}>
            <span>{nom}</span>
            <button onClick={() => api.downloadReport(nom, token)}>Télécharger</button>
          </li>
        ))}
        {fichiers.length === 0 && (
          <li className="reports-empty">Aucun rapport généré pour le moment.</li>
        )}
      </ul>
    </div>
  );
}
```

### Ajouter l'onglet dans `App.tsx`

```tsx
import { ReportsPage } from "./components/ReportsPage";
// ...
const [ongletActif, setOngletActif] = useState<"dashboard" | "utilisateurs" | "rapports">("dashboard");
// ...
{ongletActif === "rapports" && (
  <RequireRole minimum="operateur">
    <ReportsPage />
  </RequireRole>
)}
```

### Ajouter le bouton de navigation dans `Header.tsx`

Dans le `<nav className="app-nav">` déjà présent depuis l'étape 8, ajouter,
entre le bouton "Tableau de bord" et le bloc `RequireRole minimum="administrateur"` :

```tsx
<RequireRole minimum="operateur">
  <button
    className={ongletActif === "rapports" ? "nav-active" : ""}
    onClick={() => onNaviguer("rapports")}
  >
    Rapports
  </button>
</RequireRole>
```

Et mettre à jour le type de la prop `onNaviguer` dans `HeaderProps` pour
inclure `"rapports"`.

### Quelques classes CSS à ajouter dans `index.css`

```css
.reports-header { display: flex; justify-content: space-between; align-items: center; }
.reports-note { color: var(--muted); font-size: 0.9rem; margin: 8px 0 16px; }
.reports-list { list-style: none; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.reports-list li { display: flex; justify-content: space-between; align-items: center;
  padding: 8px 12px; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; }
.reports-empty { color: var(--muted); justify-content: center; }
```

---

## 11. Vérification

```powershell
python -m compileall metrics reports api main.py simulation kpi realtime
python -m pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Génération manuelle, en tant qu'utilisateur `operateur` ou `administrateur` :

```powershell
curl.exe -X POST http://127.0.0.1:8000/reports/generate -H "Authorization: Bearer TON_JETON"
curl.exe http://127.0.0.1:8000/reports -H "Authorization: Bearer TON_JETON"
```

**Résultat attendu :** la première commande renvoie
`{"pdf": "rapport_technique_....pdf", "excel": "export_donnees_....xlsx"}`,
et ces deux fichiers apparaissent bien dans `reports/output/` sur le disque
ainsi que dans la réponse de la seconde commande.

Ouvre le PDF et l'Excel générés pour vérifier :
- le PDF affiche des chiffres cohérents avec ce que tu viens de faire tourner (uptime, requêtes, éventuels passages) ;
- l'Excel contient bien les feuilles Résumé / Factures / Prestations / Ententes préalables / Journal technique, avec des lignes si une simulation a tourné dans la journée.

---

## 12. Checklist

- [ ] `metrics/registry.py` centralise bien les 4 familles de métriques (moteur, KPI, Socket.IO, API) ;
- [ ] les 4 fichiers existants (`engine.py`, `kpi/consumer.py`, `socket_server.py`, `main.py`) sont patchés sans rien casser d'existant ;
- [ ] `python -m compileall` ne renvoie aucune erreur sur les nouveaux modules ;
- [ ] `POST /reports/generate` fonctionne en `operateur` et en `administrateur` ;
- [ ] `POST /reports/generate` renvoie `403` pour un `observateur` ;
- [ ] les fichiers apparaissent bien dans `reports/output/` ;
- [ ] le PDF ne contient **aucune** donnée métier (montants, pathologies, ententes) ;
- [ ] l'Excel contient bien 5 feuilles, avec le Résumé en premier onglet ;
- [ ] l'onglet Rapports du dashboard liste les fichiers et permet de les télécharger ;
- [ ] un `observateur` ne voit pas l'onglet Rapports.

---

## 13. Dépannage

| Problème | Cause probable | Solution |
|---|---|---|
| `ModuleNotFoundError: fpdf` | Le paquet installé s'appelle `fpdf2`, mais s'importe comme `fpdf` | Vérifie `pip show fpdf2` ; l'import `from fpdf import FPDF` est correct malgré le nom du paquet |
| Le rapport de minuit ne se déclenche jamais | Le serveur Uvicorn était arrêté à minuit | Normal avec un planificateur en mémoire — génère manuellement via le bouton, ou laisse le serveur tourner en continu pendant tes tests |
| Le PDF/Excel semble "vide" ou avec des zéros partout | Le registre vient d'être réinitialisé par un redémarrage récent | Relis la limite de la section 2 — c'est le comportement attendu, pas un bug |
| `404` en téléchargeant un rapport pourtant listé | Nom de fichier mal encodé dans l'URL côté frontend | Vérifie que `nomFichier` n'est pas modifié entre `listReports` et `downloadReport` |
| Le fichier Excel a une feuille "Sheet" vide en trop | `classeur.active` créé par défaut par `openpyxl.Workbook()` réutilisé comme "Résumé" | C'est déjà géré dans le code (section 7) — vérifie que tu n'as pas ajouté un `classeur.create_sheet` supplémentaire avant la ligne `resume = classeur.active` |

---

## 14. Ce qui reste à faire (pas dans cette étape)

- Injecteur d'anomalies configurable → **étape 10**.
- Persistance du registre de métriques en base pour survivre aux redémarrages (amélioration possible, hors périmètre actuel — voir section 2).

**Fin du guide de l'étape 9.**
