<!-- Guide autonome des ajustements visuels et fonctionnels du dashboard (logo, bouton, graphique). -->

# Simulateur de parcours assuré CMU

## Étape 8/10 — Logo, bouton Arrêter dédié, graphique de charge

**Tutoriel d'exécution manuelle — à la suite de l'étape 7 (authentification).**

Cette étape ne touche ni la base de données ni les migrations : uniquement
le dashboard React. Trois changements :
1. Le logo de la structure dans l'en-tête.
2. Un bouton **Arrêter** distinct du bouton **Démarrer** (plutôt qu'un seul
   bouton qui change de libellé).
3. Le graphique "passages par heure" est retiré et remplacé par un graphique
   de **charge de traitement** : passages actifs en temps réel comparés à la
   limite du moteur (le sémaphore de 20, vu à l'étape 3) — une métrique
   technique du simulateur, pas une métrique métier.

> Cette étape **remplace intégralement** le fichier `Header.tsx` déjà modifié
> par les indications de la section 11 de l'étape 7 : le code complet
> ci-dessous inclut déjà l'authentification, les rôles et le logo — pas
> besoin de recombiner les deux.

---

## 1. Résultat attendu

- Un logo affiché dans l'en-tête du dashboard.
- Deux boutons séparés, chacun avec son propre état activé/désactivé selon
  que la simulation tourne ou non.
- Un nouveau composant `ChargeTraitementChart.tsx` qui affiche, en direct,
  le nombre de passages actifs comparé à la capacité maximale du moteur —
  sans passer par le pipeline KPI de l'étape 4 (c'est une donnée du moteur
  lui-même, pas une donnée métier calculée depuis le journal d'événements).
- L'ancien `PassagesLineChart.tsx` est retiré.

---

## 2. Choix techniques

| Choix | Pourquoi |
|---|---|
| Le graphique interroge directement `GET /simulation/status` toutes les 2 secondes, plutôt que de passer par Socket.IO/KPI | `passages_actifs` et `passages_simultanes_max` sont déjà renvoyés par cet endpoint (ajouté à l'étape 5) ; c'est une донnée du moteur, pas un indicateur métier calculé par `kpi/service.py` — inutile de faire transiter cette donnée par le pipeline KPI de l'étape 4. |
| Fenêtre glissante de 60 points conservés côté client | À 2 secondes d'intervalle, ça représente 2 minutes d'historique visible — largement suffisant pour une démonstration, sans consommer de mémoire inutilement. |
| Deux boutons distincts plutôt qu'un bouton bascule | Demande explicite : plus lisible visuellement, chaque bouton a son propre état désactivé (Démarrer désactivé si déjà en cours, Arrêter désactivé si déjà arrêté). |
| Le logo est un simple fichier image statique, avec repli textuel | Pas besoin de composant dynamique pour un logo ; un `<img>` avec `onError` qui bascule sur le nom de la structure si le fichier est absent évite un écran cassé si le fichier n'a pas encore été fourni. |

---

## 3. Arborescence des fichiers à créer, modifier ou supprimer

```text
dashboard/src/
|-- assets/
|   `-- logo.png                      (nouveau -- à fournir par toi)
|-- components/
|   |-- ChargeTraitementChart.tsx     (nouveau)
|   |-- PassagesLineChart.tsx         (SUPPRIMÉ)
|   `-- Header.tsx                    (remplacé intégralement)
|-- services/api.ts                   (modifié -- jetons d'authentification)
`-- App.tsx                            (modifié -- import du nouveau graphique)
```

### Le fichier logo

Dépose ton fichier logo (format PNG ou SVG, fond transparent de préférence)
à l'emplacement `dashboard/src/assets/logo.png`. Si tu utilises un `.svg`,
adapte simplement l'extension dans l'import de `Header.tsx` (section 6) —
aucun autre changement nécessaire.

---

## 4. Mettre à jour `services/api.ts` : envoyer le jeton sur chaque appel

**Rappel de l'étape 7 :** les endpoints de pilotage exigent maintenant un
jeton JWT. Chaque fonction qui appelle une route protégée reçoit désormais
le jeton en dernier paramètre.

```typescript
// dashboard/src/services/api.ts
const API_URL = import.meta.env.VITE_API_URL as string;

function authHeaders(token: string | null): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? `Erreur ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  async getSimulationStatus() {
    const response = await fetch(`${API_URL}/simulation/status`);
    return parseOrThrow(response);
  },

  async startSimulation(vitesse: number, nombrePassagesSimultanesMax: number, token: string | null) {
    const response = await fetch(`${API_URL}/simulation/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify({ vitesse, nombre_passages_simultanes_max: nombrePassagesSimultanesMax }),
    });
    return parseOrThrow(response);
  },

  async stopSimulation(token: string | null) {
    const response = await fetch(`${API_URL}/simulation/stop`, {
      method: "POST",
      headers: authHeaders(token),
    });
    return parseOrThrow(response);
  },

  async setSpeed(vitesse: number, token: string | null) {
    const response = await fetch(`${API_URL}/simulation/speed`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify({ vitesse }),
    });
    return parseOrThrow(response);
  },

  async getKpiSnapshot() {
    const response = await fetch(`${API_URL}/kpi/snapshot`);
    return parseOrThrow(response);
  },
};
```

**Ce qui change concrètement par rapport à l'étape 5 :** `startSimulation`,
`stopSimulation` et `setSpeed` prennent désormais un paramètre `token` en
plus ; `getSimulationStatus` et `getKpiSnapshot` restent publics (lecture
seule, non protégée côté API — rappel de la section 7 de l'étape 7).

---

## 5. Le nouveau graphique : `ChargeTraitementChart.tsx`

```tsx
// dashboard/src/components/ChargeTraitementChart.tsx
// Charge de traitement du moteur : passages actifs vs capacité maximale.
// Interroge directement /simulation/status, sans passer par le pipeline KPI --
// c'est une métrique du moteur lui-même, pas un indicateur métier.
import { useEffect, useRef, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../services/api";

interface PointCharge {
  heure: string;
  passagesActifs: number;
  capaciteMax: number;
}

const INTERVALLE_MS = 2000;
const POINTS_MAX = 60; // 2 minutes d'historique à 2 secondes d'intervalle.

export function ChargeTraitementChart() {
  const [points, setPoints] = useState<PointCharge[]>([]);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    async function poll() {
      try {
        const status = await api.getSimulationStatus();
        const maintenant = new Date().toLocaleTimeString("fr-FR", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });
        setPoints((precedents) => {
          const suivant = [
            ...precedents,
            {
              heure: maintenant,
              passagesActifs: status.passages_actifs,
              capaciteMax: status.passages_simultanes_max,
            },
          ];
          return suivant.slice(-POINTS_MAX);
        });
      } catch {
        // Une erreur ponctuelle de sondage ne doit pas casser le graphique --
        // le prochain intervalle réessaiera simplement.
      }
    }

    void poll();
    intervalRef.current = setInterval(poll, INTERVALLE_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  const dernierPoint = points.at(-1);
  const proche = dernierPoint && dernierPoint.passagesActifs >= dernierPoint.capaciteMax * 0.9;

  return (
    <div className="chart-card">
      <div className="chart-card-header">
        <h3>Charge de traitement du moteur</h3>
        {proche && <span className="badge-alerte">Proche de la capacité maximale</span>}
      </div>
      {points.length === 0 ? (
        <p className="chart-empty">En attente des premières mesures...</p>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={points}>
            <XAxis dataKey="heure" tick={{ fontSize: 11 }} />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Line type="monotone" dataKey="passagesActifs" name="Passages actifs" stroke="#006b67" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="capaciteMax" name="Capacité max" stroke="#d95055" strokeDasharray="4 4" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
```

Le badge d'alerte (`proche >= 90 % de la capacité`) reprend l'idée suggérée
en fin de proposition — un seuil visuel simple, sans configuration
supplémentaire à cette étape.

**Retirer l'ancien fichier :**

```powershell
Remove-Item dashboard/src/components/PassagesLineChart.tsx
```

---

## 6. Le nouveau `Header.tsx` complet

Ce fichier remplace entièrement celui de l'étape 6 — logo, deux boutons
distincts, informations de connexion et navigation entre onglets.

```tsx
// dashboard/src/components/Header.tsx
import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { RequireRole } from "../auth/RequireRole";
import { useKpiSocket } from "../hooks/useKpiSocket";
import { api } from "../services/api";
import type { SimulationStatus } from "../types";
import { ConnectionBadge } from "./ConnectionBadge";
import logo from "../assets/logo.png";

interface HeaderProps {
  ongletActif: "dashboard" | "utilisateurs";
  onNaviguer: (onglet: "dashboard" | "utilisateurs") => void;
}

export function Header({ ongletActif, onNaviguer }: HeaderProps) {
  const { connectionStatus } = useKpiSocket();
  const { token, role, nomComplet, logout } = useAuth();
  const [status, setStatus] = useState<SimulationStatus | null>(null);
  const [speed, setSpeed] = useState(60);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [logoManquant, setLogoManquant] = useState(false);

  useEffect(() => {
    api
      .getSimulationStatus()
      .then((value) => {
        setStatus(value);
        setSpeed(value.vitesse);
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleDemarrer() {
    setLoading(true);
    setError(null);
    try {
      setStatus(await api.startSimulation(speed, 20, token));
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleArreter() {
    setLoading(true);
    setError(null);
    try {
      await api.stopSimulation(token);
      setStatus(await api.getSimulationStatus());
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function applySpeed() {
    if (status?.etat !== "en_cours") return;
    setLoading(true);
    setError(null);
    try {
      setStatus(await api.setSpeed(speed, token));
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const enCours = status?.etat === "en_cours";

  return (
    <header className="app-header">
      <div className="app-header-brand">
        {logoManquant ? (
          <span className="brand-fallback">CNAM Côte d'Ivoire</span>
        ) : (
          <img
            src={logo}
            alt="Logo de la structure"
            className="app-logo"
            onError={() => setLogoManquant(true)}
          />
        )}
        <div>
          <p className="eyebrow">CNAM Côte d'Ivoire</p>
          <h1>Parcours assuré CMU</h1>
        </div>
      </div>

      <nav className="app-nav">
        <button
          className={ongletActif === "dashboard" ? "nav-active" : ""}
          onClick={() => onNaviguer("dashboard")}
        >
          Tableau de bord
        </button>
        <RequireRole minimum="administrateur">
          <button
            className={ongletActif === "utilisateurs" ? "nav-active" : ""}
            onClick={() => onNaviguer("utilisateurs")}
          >
            Utilisateurs
          </button>
        </RequireRole>
      </nav>

      <div className="simulation-controls">
        <ConnectionBadge status={connectionStatus} />

        <RequireRole minimum="operateur">
          <label>
            Vitesse <strong>×{speed}</strong>
            <input
              type="range"
              min="1"
              max="3600"
              step="1"
              value={speed}
              onChange={(event) => setSpeed(Number(event.target.value))}
              onMouseUp={applySpeed}
              onTouchEnd={applySpeed}
              disabled={loading}
            />
          </label>
          <button className="button-start" onClick={handleDemarrer} disabled={loading || enCours}>
            {loading && !enCours ? "Démarrage..." : "Démarrer"}
          </button>
          <button className="button-stop" onClick={handleArreter} disabled={loading || !enCours}>
            {loading && enCours ? "Arrêt..." : "Arrêter"}
          </button>
        </RequireRole>

        {error && (
          <p className="control-error" role="alert">
            {error}
          </p>
        )}

        <div className="account-menu">
          <span className="account-name">
            {nomComplet} <em>({role})</em>
          </span>
          <button className="button-logout" onClick={logout}>
            Déconnexion
          </button>
        </div>
      </div>
    </header>
  );
}
```

---

## 7. Ajustements dans `App.tsx`

Remplacer l'import de l'ancien graphique par le nouveau, dans la grille du
tableau de bord :

```tsx
// Retirer :
// import { PassagesLineChart } from "./components/PassagesLineChart";
// Ajouter :
import { ChargeTraitementChart } from "./components/ChargeTraitementChart";
```

Et dans le rendu (`<main className="dashboard-grid">`), remplacer
`<PassagesLineChart />` par `<ChargeTraitementChart />` — la position dans
la grille ne change pas, seul le composant affiché change.

---

## 8. Quelques classes CSS à ajouter dans `index.css`

```css
.app-header-brand { display: flex; align-items: center; gap: 12px; }
.app-logo { height: 40px; width: auto; }
.brand-fallback { font-weight: 700; font-size: 1.1rem; color: var(--primary); }

.app-nav { display: flex; gap: 8px; }
.app-nav button { background: none; border: none; padding: 6px 12px; cursor: pointer; color: var(--muted); }
.app-nav button.nav-active { color: var(--primary); font-weight: 600; border-bottom: 2px solid var(--primary); }

.button-start { background: var(--primary); color: #fff; }
.button-stop { background: var(--red); color: #fff; }
.button-start:disabled, .button-stop:disabled { opacity: 0.5; cursor: not-allowed; }

.account-menu { display: flex; align-items: center; gap: 8px; margin-left: 12px; }
.account-name em { font-style: normal; color: var(--muted); }
.button-logout { background: none; border: 1px solid var(--border); border-radius: 6px; padding: 4px 10px; cursor: pointer; }

.badge-alerte { background: var(--amber); color: #fff; border-radius: 999px; padding: 2px 10px; font-size: 0.8rem; }
.chart-card-header { display: flex; justify-content: space-between; align-items: center; }
.chart-empty { color: var(--muted); text-align: center; padding: 40px 0; }
```

---

## 9. Vérification

```powershell
npm run build
npm run dev
```

Dans le navigateur :

1. Le logo s'affiche dans l'en-tête (ou le nom de la structure si le
   fichier `logo.png` est absent — vérifie qu'aucune icône d'image cassée
   n'apparaît).
2. Connecté en `operateur` ou `administrateur` : les boutons **Démarrer** et
   **Arrêter** sont bien deux boutons séparés, chacun désactivé selon
   l'état courant.
3. Connecté en `observateur` : aucun des deux boutons n'apparaît (rappel de
   la visibilité définie à l'étape 7).
4. Le nouveau graphique affiche une ligne qui monte quand la simulation
   tourne, une ligne pointillée constante à 20 (ou la valeur configurée), et
   un badge d'alerte quand on approche 90 % de la capacité.

---

## 10. Checklist

- [ ] Le logo (ou son repli textuel) s'affiche sans image cassée ;
- [ ] Démarrer et Arrêter sont deux boutons distincts, chacun avec son état désactivé ;
- [ ] `PassagesLineChart.tsx` n'existe plus dans le dossier `components/` ;
- [ ] `ChargeTraitementChart.tsx` se met à jour toutes les 2 secondes ;
- [ ] le badge d'alerte apparaît bien autour de 90 % de la capacité max ;
- [ ] `npm run build` ne renvoie aucune erreur TypeScript ;
- [ ] la visibilité par rôle (étape 7) reste respectée après ce remplacement de `Header.tsx`.

---

## 11. Dépannage

| Problème | Cause probable | Solution |
|---|---|---|
| Icône d'image cassée au lieu du repli textuel | Le fichier n'est pas au bon chemin exact (`src/assets/logo.png`) | Vérifie l'extension et le chemin ; `onError` ne se déclenche que si le fichier est réellement introuvable, pas s'il est mal formé |
| `401` lors d'un clic sur Démarrer/Arrêter | Le token n'est plus transmis après le remplacement de `Header.tsx` | Vérifie que `token` (issu de `useAuth()`) est bien passé en dernier argument à `api.startSimulation` / `stopSimulation` / `setSpeed` |
| Le graphique reste vide | `/simulation/status` inaccessible (API arrêtée) ou erreur CORS | Vérifie que l'API tourne sur le port 8000 ; l'erreur est absorbée silencieusement (section 5), regarde l'onglet réseau du navigateur |
| Les boutons Démarrer/Arrêter restent visibles pour un observateur | Ancien `Header.tsx` pas remplacé en entier | Assure-toi d'avoir bien collé tout le fichier de la section 6, pas juste les boutons |

---

## 12. Ce qui reste à faire (pas dans cette étape)

- Rapports PDF/Excel automatiques → **étape 9**.
- Injecteur d'anomalies configurable → **étape 10**.

**Fin du guide de l'étape 8.**
