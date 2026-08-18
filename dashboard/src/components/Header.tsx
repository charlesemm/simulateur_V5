// Pilote le simulateur et affiche l'état Socket.IO dans le header.
import { useEffect, useState } from "react";
import { useKpiSocket } from "../hooks/useKpiSocket";
import { api } from "../services/api";
import type { SimulationStatus } from "../types";
import { ConnectionBadge } from "./ConnectionBadge";

export function Header() {
  const { connectionStatus } = useKpiSocket();
  const [status, setStatus] = useState<SimulationStatus | null>(null);
  const [speed, setSpeed] = useState(60);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getSimulationStatus().then((value) => { setStatus(value); setSpeed(value.vitesse); })
      .catch((reason: Error) => setError(reason.message)).finally(() => setLoading(false));
  }, []);

  async function toggleSimulation() {
    setLoading(true); setError(null);
    try {
      if (status?.etat === "en_cours") {
        await api.stopSimulation();
        setStatus(await api.getSimulationStatus());
      } else setStatus(await api.startSimulation(speed, 20));
    } catch (reason) { setError((reason as Error).message); }
    finally { setLoading(false); }
  }

  async function applySpeed() {
    if (status?.etat !== "en_cours") return;
    setLoading(true); setError(null);
    try { setStatus(await api.setSpeed(speed)); }
    catch (reason) { setError((reason as Error).message); }
    finally { setLoading(false); }
  }

   return <header className="app-header">
    <div><p className="eyebrow">CNAM Côte d'Ivoire</p><h1>Parcours assuré CMU</h1></div>
    <div className="simulation-controls">
      <ConnectionBadge status={connectionStatus} />
      <label>Vitesse <strong>×{speed}</strong>
        <input type="range" min="1" max="3600" step="1" value={speed}
          onChange={(event) => setSpeed(Number(event.target.value))}
          onMouseUp={applySpeed} onTouchEnd={applySpeed} disabled={loading} />
      </label>
      <button className={status?.etat === "en_cours" ? "button-stop" : "button-start"}
        onClick={toggleSimulation} disabled={loading}>
        {loading ? "Traitement…" : status?.etat === "en_cours" ? "Arrêter" : "Démarrer"}
      </button>
      {error && <p className="control-error" role="alert">{error}</p>}
    </div>
  </header>;
}