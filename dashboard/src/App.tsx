import { Header } from "./components/Header";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { LoginPage } from "./auth/LoginPage";
import { RequireRole } from "./auth/RequireRole";
import { UsersPage } from "./components/UsersPage";
import { useState } from "react";
import { KpiSocketProvider } from "./hooks/useKpiSocket.tsx";
import { ChargeTraitementChart } from "./components/ChargeTraitementChart";
import { ReportsPage } from "./components/ReportsPage";

function DashboardShell() {
  const { isAuthenticated } = useAuth();
  const [ongletActif, setOngletActif] = useState<"dashboard" | "utilisateurs" | "rapports">("dashboard");

  if (!isAuthenticated) return <LoginPage />;

  let kpiSocketProvider = <><KpiSocketProvider>
    <Header onNaviguer={setOngletActif}
      ongletActif={ongletActif} />
    {ongletActif === "dashboard" && (
      <main className="dashboard-grid">
        {/* MetricCards, graphiques, CenterLoadTable : inchangés */}
        <ChargeTraitementChart />
      </main>
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
  </KpiSocketProvider></>;
  return kpiSocketProvider;
}


export default function App() {
  return (
    <AuthProvider>
      <DashboardShell />
    </AuthProvider>
  );
}