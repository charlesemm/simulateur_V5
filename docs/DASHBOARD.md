# Le dashboard

Application mono-page **React 19 + TypeScript + Vite 8**, graphiques **Recharts**, temps réel **socket.io-client**, lint **oxlint**. Sources dans `dashboard/src/`.

## Lancer

```powershell
cd dashboard
npm install
npm run dev        # http://localhost:5173, hot-reload
npm run build      # tsc --noEmit puis vite build → dashboard/dist
npm run lint       # oxlint
```

`VITE_API_URL` (dans `dashboard/.env.local`) donne l'adresse de l'API vue du navigateur. Vite ne relit pas ce fichier à chaud : redémarrer `npm run dev` après modification. Voir le dépannage « NetworkError » du [README](../README.md).

Compilé, le dashboard est servi par l'API elle-même (`http://localhost:8000`). `dashboard/nginx.conf` est conservé pour une mise en production avec Nginx séparé.

## Écrans

Déclarés dans `src/navigation.ts` (un seul endroit pour la barre latérale, l'en-tête et le routage).

| Onglet | Composant | Contenu |
|---|---|---|
| Vue d'ensemble (`accueil`) | `AccueilPage` | Cartes des types de simulation, activité récente |
| Nouvelle simulation (`lancement`) | `LancementPage`, `ConsoleInjectionPage` | Scénario, cadence, anomalies à injecter |
| Pilotage en direct (`encours`) | `ExecutionEnCoursPage` | Suivi du moteur, déclenchement des aléas, journal en direct (`LiveLogTerminal`) |
| Bilan d'exécution (`bilan`) | `BilanExecutionPage` | Ce que la simulation a produit |
| Historique (`simulations`) | `SimulationsPage` | Exécutions passées et détail |
| Contrôle qualité (`qualite`) | `QualitePage` | Anomalies demandées / injectées / détectées |
| Campagnes de test (`campagnes`) | `CampagnesPage`, `FicheCampagne` | Liste et fiche d'une campagne |
| Nouvelle campagne (`campagne-nouvelle`) | `NouvelleCampagnePage` | Palier, volume, graine, anomalies |
| Rapports et exports (`rapports`) | `ReportsPage` | Synthèses par période ou par exécution |
| Administration (`administration`) | `AdministrationPage`, `UsersPage` | Comptes, volumétrie, purge |
| Explorateur API (`explorateur-api`) | `ApiExplorerPage` | Toutes les routes, description, banc d'essai |

## Composants de supervision

| Composant | Montre |
|---|---|
| `TechMetricCards` | Concurrence moteur, débit d'événements, taux de succès, latence API, clients WebSocket, mémoire et uptime |
| `ChargeTraitementChart` | Passages actifs seconde par seconde, plafond du sémaphore |
| `LatencyPerformanceChart` | Latence API et temps de recalcul |
| `SystemHealthDonut` | Passages réussis vs en erreur |
| `TopPathologiesChart`, `ActesRepartitionChart`, `PassagesHistoryChart` | Activité métier |
| `EntentesPanel`, `FilEtapes` | Ententes préalables, fil des étapes d'un parcours |

Lecture des métriques : si la courbe de concurrence colle au plafond pointillé, le moteur est saturé à 100 %.

## Structure du code

| Dossier / fichier | Rôle |
|---|---|
| `src/App.tsx`, `main.tsx` | Racine et routage par onglet |
| `src/auth/` | `AuthContext` (jeton, utilisateur), `LoginPage`, `ChangePasswordPage`, `RequireRole` (masque ce que le rôle ne permet pas) |
| `src/services/api.ts` | Client REST : joint le jeton à chaque appel |
| `src/hooks/useKpiSocket.tsx` | Connexion Socket.IO au namespace `/kpi` avec le jeton |
| `src/types.ts` | Types partagés avec l'API |
| `src/components/` | Écrans et graphiques ; `format*.ts` = formatage ; `chartTheme.ts` = thème des graphiques |
| `src/*.css`, `components/*.css` | Styles (`brand-refresh.css`, `Cockpit.css`, `Screens.css`, `layout-flow.css`) |

## Comportement selon le rôle

- Après connexion, un compte sous **mot de passe temporaire** n'accède qu'à `ChangePasswordPage`.
- `observateur` : lecture seule. `operateur` : démarrer/arrêter, aléas, rapports. `administrateur` : comptes, configuration des anomalies, purge.
- Le serveur reste l'autorité : masquer un bouton côté navigateur ne remplace jamais le contrôle du rôle côté API.
