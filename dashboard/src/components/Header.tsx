// dashboard/src/components/Header.tsx
import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { RequireRole } from "../auth/RequireRole";
import { useKpiSocket } from "../hooks/useKpiSocket";
import { TITRES, type Onglet } from "../navigation";
import { api } from "../services/api";
import type { SimulationStatus } from "../types";
import { ConnectionBadge } from "./ConnectionBadge";

interface TopbarProps {
  ongletActif: Onglet;
}

/**
 * Bandeau supérieur : où l'on est, et ce que le moteur fait.
 *
 * Les commandes de lancement n'y figurent plus. Une simulation se paramètre
 * d'abord — nom, anomalies, aléas — sur son écran ; démarrer sans avoir rien
 * choisi ne voulait pas dire grand-chose. Seul l'arrêt reste ici, et
 * seulement quand il y a quelque chose à arrêter.
 */
export function Header({ ongletActif }: TopbarProps) {
  const { connectionStatus } = useKpiSocket();
  const { token } = useAuth();
  const [status, setStatus] = useState<SimulationStatus | null>(null);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function refreshStatus() {
      try {
        const value = await api.getSimulationStatus(token);
        if (!cancelled) {
          setStatus(value);
          setError(null);
        }
      } catch (reason) {
        if (!cancelled) setError((reason as Error).message);
      }
    }

    void refreshStatus();
    const interval = setInterval(refreshStatus, 2000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [token]);

  async function handleArreter() {
    setStopping(true);
    setError(null);
    try {
      await api.stopSimulation(token);
      setStatus(await api.getSimulationStatus(token));
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setStopping(false);
    }
  }

  const enCours = status?.etat === "en_cours";
  const { titre: title, sousTitre: subtitle } = TITRES[ongletActif];

  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="topbar-title-group">
          <h1 className="topbar-title">{title}</h1>
          <span className="topbar-subtitle">{subtitle}</span>
        </div>
      </div>

      <div className="topbar-right">
        <ConnectionBadge status={connectionStatus} />

        {enCours && (
          <>
            <div className="topbar-divider" />
            <span className="speed-caption">
              {status?.type_simulation ?? "Simulation"} · vitesse{" "}
              <strong>×{status?.vitesse ?? 0}</strong> ·{" "}
              <strong>{status?.passages_actifs ?? 0}</strong> passage(s)
            </span>

            <RequireRole minimum="operateur">
              <button
                id="btn-stop-simulation"
                className="btn-engine btn-engine-stop"
                onClick={handleArreter}
                disabled={stopping}
                title="Arrêter la simulation en cours"
              >
                {stopping ? (
                  <span className="btn-engine-spinner" />
                ) : (
                  <svg className="btn-engine-icon" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clipRule="evenodd" />
                  </svg>
                )}
                {stopping ? "Arrêt…" : "Arrêter"}
              </button>
            </RequireRole>
          </>
        )}

        {error && (
          <div className="topbar-error" role="alert">
            {error}
          </div>
        )}
      </div>
    </header>
  );
}
