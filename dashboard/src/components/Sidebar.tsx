// dashboard/src/components/Sidebar.tsx
import { useAuth } from "../auth/AuthContext";
import { RequireRole } from "../auth/RequireRole";
import { EchoLogo } from "./EchoLogo";
import { DashboardIcon, LogoutIcon, ReportsIcon, UsersIcon } from "./Icons";

interface SidebarProps {
  ongletActif: "dashboard" | "utilisateurs" | "rapports";
  onNaviguer: (onglet: "dashboard" | "utilisateurs" | "rapports") => void;
}

export function Sidebar({ ongletActif, onNaviguer }: SidebarProps) {
  const { nomComplet, role, logout } = useAuth();

  return (
    <aside className="app-sidebar">
      <div className="sidebar-top">
        <div className="sidebar-brand">
          <EchoLogo size={38} className="sidebar-logo" id="sidebar" />
          <div className="sidebar-brand-meta">
            <span className="sidebar-brand-title">ÉCHO</span>
            <span className="sidebar-brand-sub">CNAM-CI</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          <span className="sidebar-nav-section-title">Navigation</span>

          <button
            className={`sidebar-nav-item ${ongletActif === "dashboard" ? "active" : ""}`}
            onClick={() => onNaviguer("dashboard")}
          >
            <DashboardIcon className="nav-icon" />
            <span className="nav-text">Tableau de bord</span>
          </button>

          <RequireRole minimum="operateur">
            <button
              className={`sidebar-nav-item ${ongletActif === "rapports" ? "active" : ""}`}
              onClick={() => onNaviguer("rapports")}
            >
              <ReportsIcon className="nav-icon" />
              <span className="nav-text">Rapports & Exports</span>
            </button>
          </RequireRole>

          <RequireRole minimum="administrateur">
            <button
              className={`sidebar-nav-item ${ongletActif === "utilisateurs" ? "active" : ""}`}
              onClick={() => onNaviguer("utilisateurs")}
            >
              <UsersIcon className="nav-icon" />
              <span className="nav-text">Utilisateurs</span>
            </button>
          </RequireRole>
        </nav>
      </div>

      <div className="sidebar-bottom">
        <div className="sidebar-user-card">
          <div className="sidebar-user-avatar">
            {(nomComplet ?? "U").charAt(0).toUpperCase()}
          </div>
          <div className="sidebar-user-details">
            <span className="sidebar-user-name">{nomComplet ?? "Utilisateur"}</span>
            <span className="sidebar-user-role">{role}</span>
          </div>
          <button className="sidebar-logout-btn" onClick={logout} title="Se déconnecter">
            <LogoutIcon className="logout-icon" />
          </button>
        </div>
      </div>
    </aside>
  );
}
