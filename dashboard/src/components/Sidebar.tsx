// dashboard/src/components/Sidebar.tsx
import { useAuth } from "../auth/AuthContext";
import { RequireRole } from "../auth/RequireRole";
import logoCnam from "../assets/logo.png";
import type { Onglet } from "../navigation";
import { EchoLogo } from "./EchoLogo";
import {
  DashboardIcon, HomeIcon, InjectionIcon, LogoutIcon, QualiteIcon,
  ReportsIcon, SimulationsIcon, UsersIcon,
} from "./Icons";

interface SidebarProps {
  ongletActif: Onglet;
  onNaviguer: (onglet: Onglet) => void;
  /** Vrai tant qu'une exécution tourne : le poste de pilotage n'existe alors. */
  moteurEnCours: boolean;
}

export function Sidebar({ ongletActif, onNaviguer, moteurEnCours }: SidebarProps) {
  const { nomComplet, role, logout } = useAuth();

  return (
    <aside className="app-sidebar">
      <div className="sidebar-top">
        <div className="sidebar-brand">
          <div className="sidebar-marques">
            <EchoLogo size={34} className="sidebar-logo" id="sidebar" />
            <span className="sidebar-marques-filet" />
            <img
              src={logoCnam}
              alt="Caisse Nationale d'Assurance Maladie"
              className="sidebar-logo-cnam"
            />
          </div>
          <div className="sidebar-brand-meta">
            <span className="sidebar-brand-title">ÉCHO</span>
            <span className="sidebar-brand-sub">Simulateur de données · Côte d'Ivoire</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          <span className="sidebar-nav-section-title">Navigation</span>

          <button
            className={`sidebar-nav-item ${ongletActif === "accueil" ? "active" : ""}`}
            onClick={() => onNaviguer("accueil")}
          >
            <HomeIcon className="nav-icon" />
            <span className="nav-text">Accueil</span>
          </button>

          <RequireRole minimum="operateur">
            <button
              className={`sidebar-nav-item ${ongletActif === "injection" ? "active" : ""}`}
              onClick={() => onNaviguer("injection")}
            >
              <InjectionIcon className="nav-icon" />
              <span className="nav-text">Console d'injection</span>
            </button>
          </RequireRole>

          {/* N'apparaît que pendant qu'une simulation tourne : un onglet vide
              le reste du temps n'aurait rien à montrer. */}
          {moteurEnCours && (
            <button
              className={`sidebar-nav-item sidebar-nav-item--vif ${
                ongletActif === "encours" ? "active" : ""
              }`}
              onClick={() => onNaviguer("encours")}
            >
              <span className="pouls" aria-hidden="true" />
              <span className="nav-text">Simulation en cours</span>
            </button>
          )}

          <button
            className={`sidebar-nav-item ${ongletActif === "simulations" ? "active" : ""}`}
            onClick={() => onNaviguer("simulations")}
          >
            <SimulationsIcon className="nav-icon" />
            <span className="nav-text">Simulations</span>
          </button>

          <button
            className={`sidebar-nav-item ${ongletActif === "qualite" ? "active" : ""}`}
            onClick={() => onNaviguer("qualite")}
          >
            <QualiteIcon className="nav-icon" />
            <span className="nav-text">Qualité</span>
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

          <RequireRole minimum="operateur">
            <button
              className={`sidebar-nav-item ${ongletActif === "dashboard" ? "active" : ""}`}
              onClick={() => onNaviguer("dashboard")}
            >
              <DashboardIcon className="nav-icon" />
              <span className="nav-text">Supervision</span>
            </button>
          </RequireRole>

          <RequireRole minimum="administrateur">
            <button
              className={`sidebar-nav-item ${ongletActif === "administration" ? "active" : ""}`}
              onClick={() => onNaviguer("administration")}
            >
              <UsersIcon className="nav-icon" />
              <span className="nav-text">Administration</span>
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
