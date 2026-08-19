import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";

interface AnomaliesConfig {
  enabled: boolean;
  rate: number;
  severity: "soft" | "hard";
  injected_count: number;
}

const API_URL = import.meta.env.VITE_API_URL as string;

export function AnomaliesPanel() {
  const { token } = useAuth();
  const [config, setConfig] = useState<AnomaliesConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchConfig();
  }, [token]);

  async function fetchConfig() {
    try {
      const response = await fetch(`${API_URL}/anomalies`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error(`Erreur ${response.status}`);
      setConfig(await response.json());
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function updateConfig(update: Partial<AnomaliesConfig>) {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/anomalies`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(update),
      });
      if (!response.ok) throw new Error(`Erreur ${response.status}`);
      setConfig(await response.json());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  if (!config) {
    return <div className="chart-card chart-empty">Chargement de la configuration des anomalies...</div>;
  }

  return (
    <article className="chart-card anomalies-card">
      <div className="chart-card-header">
        <div>
          <h2 className="chart-title">Test de Résilience & Anomalies</h2>
          <p className="chart-subtitle">Injection d'incohérences de données dans le flux synthétique</p>
        </div>
        <div className="chart-header-badge">
          <span className={`status-indicator ${config.enabled ? "indicator-warning" : "indicator-gray"}`}>
            {config.enabled ? "Actif" : "Désactivé"}
          </span>
        </div>
      </div>

      <div className="anomalies-controls-grid">
        <div className="anomalie-field">
          <label className="toggle-switch-label">
            <input
              type="checkbox"
              checked={config.enabled}
              onChange={(e) => updateConfig({ enabled: e.target.checked })}
              disabled={loading}
              className="toggle-checkbox"
            />
            <span className="toggle-label-text">Activer l'injection d'anomalies</span>
          </label>
        </div>

        <div className="anomalie-field">
          <div className="range-header">
            <span>Taux de perturbation</span>
            <strong>{(config.rate * 100).toFixed(0)}%</strong>
          </div>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={config.rate}
            onChange={(e) => updateConfig({ rate: parseFloat(e.target.value) })}
            disabled={loading || !config.enabled}
            className="clean-slider"
          />
        </div>

        <div className="anomalie-stats-row">
          <div className="stats-box">
            <span className="stats-box-label">Anomalies injectées</span>
            <strong className="stats-box-value">{config.injected_count}</strong>
          </div>
          <button
            onClick={() =>
              fetch(`${API_URL}/anomalies/reset`, {
                method: "POST",
                headers: { Authorization: `Bearer ${token}` },
              }).then(() => fetchConfig())
            }
            disabled={loading}
            className="btn btn-outline"
          >
            Réinitialiser le compteur
          </button>
        </div>
      </div>

      {error && <p className="panel-error-text">{error}</p>}
    </article>
  );
}