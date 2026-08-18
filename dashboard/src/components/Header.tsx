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
  ongletActif: "dashboard" | "utilisateurs" | "rapports";
  onNaviguer: (onglet: "dashboard" | "utilisateurs" | "rapports") => void;
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
        <RequireRole minimum="operateur">
          <button
            className={ongletActif === "rapports" ? "nav-active" : ""}
            onClick={() => onNaviguer("rapports")}
          >
            Rapports
          </button>
        </RequireRole>
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