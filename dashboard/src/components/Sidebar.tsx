// dashboard/src/components/Sidebar.tsx
import { useEffect, useRef } from "react";
import { useAuth } from "../auth/AuthContext";
import { useTheme, type PreferenceTheme } from "../hooks/useTheme";
import { RequireRole } from "../auth/RequireRole";
import logoCnam from "../assets/logo.png";
import type { Onglet } from "../navigation";
import { EchoLogo } from "./EchoLogo";
import {
  ApiIcon, CampagneIcon, CloseIcon, DashboardIcon, HomeIcon, InjectionIcon,
  LogoutIcon, QualiteIcon, ReportsIcon, SimulationsIcon, UsersIcon,
} from "./Icons";

const THEMES: { valeur: PreferenceTheme; libelle: string }[] = [
  { valeur: "systeme", libelle: "Système" },
  { valeur: "clair", libelle: "Clair" },
  { valeur: "sombre", libelle: "Sombre" },
];

interface SidebarProps {
  ongletActif: Onglet;
  onNaviguer: (onglet: Onglet) => void;
  /** Vrai tant qu'une exécution tourne : le poste de pilotage n'existe alors. */
  moteurEnCours: boolean;
  /** Tiroir ouvert — n'a d'effet qu'en mobile, où la barre est masquée. */
  ouvert?: boolean;
  onFermer?: () => void;
}

export function Sidebar({
  ongletActif, onNaviguer: naviguer, moteurEnCours, ouvert = false, onFermer,
}: SidebarProps) {
  const { nomComplet, role, logout } = useAuth();
  const fermer = useRef<HTMLButtonElement>(null);
  const { preference, choisirTheme } = useTheme();

  // Choisir un écran referme le tiroir : on veut voir ce qu'on a demandé.
  function onNaviguer(onglet: Onglet) {
    naviguer(onglet);
    onFermer?.();
  }

  // Tiroir ouvert : Échap le referme, et le focus y entre pour que le
  // clavier ne reste pas derrière le voile.
  useEffect(() => {
    if (!ouvert) return;
    fermer.current?.focus();
    function surTouche(event: KeyboardEvent) {
      if (event.key === "Escape") onFermer?.();
    }
    window.addEventListener("keydown", surTouche);
    return () => window.removeEventListener("keydown", surTouche);
  }, [ouvert, onFermer]);

  /** Signale l'écran courant aux lecteurs d'écran, pas seulement à l'œil. */
  const courant = (actif: boolean) => (actif ? ("page" as const) : undefined);

  return (
    <>
    <div
      className={`sidebar-voile ${ouvert ? "est-visible" : ""}`}
      onClick={onFermer}
      aria-hidden="true"
    />
    <aside className={`app-sidebar ${ouvert ? "est-ouverte" : ""}`}>
      <button
        ref={fermer}
        type="button"
        className="sidebar-close"
        onClick={onFermer}
        aria-label="Fermer le menu"
      >
        <CloseIcon />
      </button>
      <div className="sidebar-top">
        <div className="sidebar-brand">
          <div className="sidebar-product">
            <EchoLogo size={42} className="sidebar-logo" id="sidebar" />
            <div className="sidebar-brand-meta">
              <span className="sidebar-brand-title">ÉCHO</span>
              <span className="sidebar-brand-sub">Simulation & qualité des données</span>
            </div>
          </div>
          <div className="sidebar-cnam-lockup">
            <span className="sidebar-cnam-caption">Une solution pour</span>
            <img
              src={logoCnam}
              alt="Caisse Nationale d'Assurance Maladie"
              className="sidebar-logo-cnam"
            />
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Navigation principale">
          <div className="sidebar-nav-group">
            <span className="sidebar-nav-section-title">Piloter</span>

          <button
            className={`sidebar-nav-item ${ongletActif === "accueil" ? "active" : ""}`}
              aria-current={courant(ongletActif === "accueil")}
            onClick={() => onNaviguer("accueil")}
          >
            <HomeIcon className="nav-icon" />
            <span className="nav-text">Vue d'ensemble</span>
          </button>

          <RequireRole minimum="operateur">
            <button
              className={`sidebar-nav-item sidebar-nav-item--injection ${ongletActif === "injection" ? "active" : ""}`}
              aria-current={courant(ongletActif === "injection")}
              onClick={() => onNaviguer("injection")}
            >
              <InjectionIcon className="nav-icon" />
              <span className="nav-text">Scénarios & anomalies</span>
            </button>
          </RequireRole>

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
              aria-current={courant(ongletActif === "encours")}
              onClick={() => onNaviguer("encours")}
            >
              <span className="pouls" aria-hidden="true" />
              <span className="nav-text">Simulation en cours</span>
            </button>
          )}

          <button
            className={`sidebar-nav-item ${ongletActif === "simulations" ? "active" : ""}`}
              aria-current={courant(ongletActif === "simulations")}
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
            aria-current={courant(ongletActif === "campagnes" || ongletActif === "campagne-nouvelle")}
            onClick={() => onNaviguer("campagnes")}
          >
            <CampagneIcon className="nav-icon" />
            <span className="nav-text">Campagnes de test</span>
          </button>

          <button
            className={`sidebar-nav-item ${ongletActif === "qualite" ? "active" : ""}`}
              aria-current={courant(ongletActif === "qualite")}
            onClick={() => onNaviguer("qualite")}
          >
            <QualiteIcon className="nav-icon" />
            <span className="nav-text">Contrôle qualité</span>
          </button>

          <RequireRole minimum="operateur">
            <button
              className={`sidebar-nav-item ${ongletActif === "rapports" ? "active" : ""}`}
              aria-current={courant(ongletActif === "rapports")}
              onClick={() => onNaviguer("rapports")}
            >
              <ReportsIcon className="nav-icon" />
              <span className="nav-text">Rapports & exports</span>
            </button>
          </RequireRole>

          </div>

          <div className="sidebar-nav-group">
            <span className="sidebar-nav-section-title">Gérer</span>

          <RequireRole minimum="operateur">
            <button
              className={`sidebar-nav-item ${ongletActif === "dashboard" ? "active" : ""}`}
              aria-current={courant(ongletActif === "dashboard")}
              onClick={() => onNaviguer("dashboard")}
            >
              <DashboardIcon className="nav-icon" />
              <span className="nav-text">Supervision</span>
            </button>
          </RequireRole>

          <RequireRole minimum="administrateur">
            <button
              className={`sidebar-nav-item ${ongletActif === "administration" ? "active" : ""}`}
              aria-current={courant(ongletActif === "administration")}
              onClick={() => onNaviguer("administration")}
            >
              <UsersIcon className="nav-icon" />
              <span className="nav-text">Administration</span>
            </button>
          </RequireRole>

          <RequireRole minimum="administrateur">
            <button
              className={`sidebar-nav-item ${ongletActif === "explorateur-api" ? "active" : ""}`}
              aria-current={courant(ongletActif === "explorateur-api")}
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
        <div className="sidebar-theme" role="group" aria-label="Thème de l'interface">
          {THEMES.map(({ valeur, libelle }) => (
            <button
              key={valeur}
              type="button"
              className="sidebar-theme-choix"
              aria-pressed={preference === valeur}
              onClick={() => choisirTheme(valeur)}
            >
              {libelle}
            </button>
          ))}
        </div>
        <div className="sidebar-user-card">
          <div className="sidebar-user-avatar" aria-hidden="true">
            {(nomComplet ?? "U").charAt(0).toUpperCase()}
          </div>
          <div className="sidebar-user-details">
            <span className="sidebar-user-name">{nomComplet ?? "Utilisateur"}</span>
            <span className="sidebar-user-role">{role}</span>
          </div>
          <button
            type="button"
            className="sidebar-logout-btn"
            onClick={logout}
            title="Se déconnecter"
            aria-label="Se déconnecter"
          >
            <LogoutIcon className="logout-icon" />
          </button>
        </div>
      </div>
    </aside>
    </>
  );
}
