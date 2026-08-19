import { useEffect, useState } from "react";
import { Header } from "./components/Header";
import { Sidebar } from "./components/Sidebar";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { LoginPage } from "./auth/LoginPage";
import { RequireRole } from "./auth/RequireRole";
import { UsersPage } from "./components/UsersPage";
import { KpiSocketProvider } from "./hooks/useKpiSocket";
import { TechMetricCards } from "./components/TechMetricCards";
import { ChargeTraitementChart } from "./components/ChargeTraitementChart";
import { LatencyPerformanceChart } from "./components/LatencyPerformanceChart";
import { SystemHealthDonut } from "./components/SystemHealthDonut";
import { LiveLogTerminal } from "./components/LiveLogTerminal";
import { ReportsPage } from "./components/ReportsPage";
import { AnomaliesPanel } from "./components/AnomaliesPanel";
import { api } from "./services/api";
import type { TechnicalMetricsSnapshot } from "./types";

function DashboardShell() {
  const { isAuthenticated } = useAuth();
  const [ongletActif, setOngletActif] = useState<"dashboard" | "utilisateurs" | "rapports">("dashboard");
  const [metrics, setMetrics] = useState<TechnicalMetricsSnapshot | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) return;
    let cancelled = false;

    async function fetchTechMetrics() {
      try {
        const data = await api.getTechnicalMetrics();
        if (!cancelled) {
          setMetrics(data);
          setLoading(false);
        }
      } catch {
        // En cas d'erreur ponctuelle, le prochain sondage réessaiera
      }
    }

    void fetchTechMetrics();
    const interval = setInterval(fetchTechMetrics, 1500);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [isAuthenticated]);

  if (!isAuthenticated) return <LoginPage />;

  return (
    <KpiSocketProvider>
      <div className="enterprise-layout">
        {/* Navigation Latérale Gauche */}
        <Sidebar ongletActif={ongletActif} onNaviguer={setOngletActif} />

        {/* Zone de contenu principale avec Topbar */}
        <div className="enterprise-main">
          <Header ongletActif={ongletActif} />

          <div className="content-scrollable">
            {ongletActif === "dashboard" && (
              <div className="dashboard-content-space">
                {/* Rangée 1 : Compteurs & KPIs SRE avec icônes SVG */}
                <TechMetricCards metrics={metrics} loading={loading} />

                {/* Rangée 2 : Graphiques de Concurrence & Latence */}
                <section className="dashboard-row-2">
                  <ChargeTraitementChart metrics={metrics} />
                  <LatencyPerformanceChart metrics={metrics} />
                </section>

                {/* Rangée 3 : Fiabilité & Test de Résilience */}
                <section className="dashboard-row-3">
                  <SystemHealthDonut metrics={metrics} />
                  <RequireRole minimum="administrateur">
                    <AnomaliesPanel />
                  </RequireRole>
                </section>

                {/* Rangée 4 : Terminal de Logs & Événements en Direct */}
                <section className="dashboard-row-4">
                  <LiveLogTerminal metrics={metrics} />
                </section>
              </div>
            )}

            {ongletActif === "rapports" && (
              <RequireRole minimum="operateur">
                <ReportsPage />
              </RequireRole>
            )}

            {ongletActif === "utilisateurs" && (
              <RequireRole minimum="administrateur">
                <UsersPage />
              </RequireRole>
            )}
          </div>
        </div>
      </div>
    </KpiSocketProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <DashboardShell />
    </AuthProvider>
  );
}