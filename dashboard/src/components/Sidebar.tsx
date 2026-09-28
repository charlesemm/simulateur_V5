// dashboard/src/components/Sidebar.tsx
import { useAuth } from "../auth/AuthContext";
import { RequireRole } from "../auth/RequireRole";
import logoCnam from "../assets/logo.png";
import type { Onglet } from "../navigation";
import { EchoLogo } from "./EchoLogo";
import {
  ApiIcon, HomeIcon, LogoutIcon, QualiteIcon, ReportsIcon, SimulationsIcon,
  UsersIcon,
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
        {/* La marque ÉCHO — logo et nom sur une ligne — ramène à l'accueil,
            comme sur tout site. La CNAM, la maison, juste en dessous. */}
        <div className="sidebar-brand">
          <button
            type="button"
            className="sidebar-accueil"
            onClick={() => onNaviguer("accueil")}
            title="Revenir à la vue d'ensemble"
          >
            <EchoLogo size={40} className="sidebar-logo" id="sidebar" />
            <span className="sidebar-brand-title">ÉCHO</span>
          </button>
          <span className="sidebar-logo-cnam-fond">
            <img
              src={logoCnam}
              alt="Caisse Nationale d'Assurance Maladie"
              className="sidebar-logo-cnam"
            />
          </span>
        </div>

        <nav className="sidebar-nav" aria-label="Navigation principale">
          <div className="sidebar-nav-group">
            <span className="sidebar-nav-section-title">Piloter</span>

          <button
            className={`sidebar-nav-item ${ongletActif === "accueil" ? "active" : ""}`}
            onClick={() => onNaviguer("accueil")}
          >
            <HomeIcon className="nav-icon" />
            <span className="nav-text">Vue d'ensemble</span>
          </button>

          </div>

          <div className="sidebar-nav-group">
            <span className="sidebar-nav-section-title">Analyser</span>

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
            <span className="nav-text">Historique</span>
          </button>

          <button
            className={`sidebar-nav-item ${
              ongletActif === "campagnes" || ongletActif === "campagne-nouvelle"
                ? "active"
                : ""
            }`}
            onClick={() => onNaviguer("campagnes")}
          >
            <QualiteIcon className="nav-icon" />
            <span className="nav-text">Campagnes de test</span>
          </button>

          <button
            className={`sidebar-nav-item ${ongletActif === "qualite" ? "active" : ""}`}
            onClick={() => onNaviguer("qualite")}
          >
            <QualiteIcon className="nav-icon" />
            <span className="nav-text">Contrôle qualité</span>
          </button>

          <RequireRole minimum="operateur">
            <button
              className={`sidebar-nav-item ${ongletActif === "rapports" ? "active" : ""}`}
              onClick={() => onNaviguer("rapports")}
            >
              <ReportsIcon className="nav-icon" />
              <span className="nav-text">Rapports & exports</span>
            </button>
          </RequireRole>

          </div>

          <div className="sidebar-nav-group">
            <span className="sidebar-nav-section-title">Gérer</span>

          <RequireRole minimum="administrateur">
            <button
              className={`sidebar-nav-item ${ongletActif === "administration" ? "active" : ""}`}
              onClick={() => onNaviguer("administration")}
            >
              <UsersIcon className="nav-icon" />
              <span className="nav-text">Administration</span>
            </button>
          </RequireRole>

          <RequireRole minimum="administrateur">
            <button
              className={`sidebar-nav-item ${ongletActif === "explorateur-api" ? "active" : ""}`}
              onClick={() => onNaviguer("explorateur-api")}
            >
              <ApiIcon className="nav-icon" />
              <span className="nav-text">Explorateur API</span>
            </button>
          </RequireRole>
          </div>
        </nav>
      </div>

      <div className="sidebar-bottom">
        <div className="sidebar-environment">
          <span className="sidebar-environment-dot" aria-hidden="true" />
          Environnement de simulation
        </div>
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
