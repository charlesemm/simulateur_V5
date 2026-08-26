import { useEffect, useRef, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TechnicalMetricsSnapshot } from "../types";

interface PointLatence {
  heure: string;
  latenceApiMs: number;
  latenceKpiMs: number;
}

const POINTS_MAX = 40;

interface LatencyPerformanceChartProps {
  metrics: TechnicalMetricsSnapshot | null;
}

export function LatencyPerformanceChart({ metrics }: LatencyPerformanceChartProps) {
  const [points, setPoints] = useState<PointLatence[]>([]);
  const lastTimeRef = useRef<string>("");

  useEffect(() => {
    if (!metrics) return;
    const maintenant = new Date().toLocaleTimeString("fr-FR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });

    if (maintenant !== lastTimeRef.current) {
      lastTimeRef.current = maintenant;
      setPoints((precedents) => {
        const suivant = [
          ...precedents,
          {
            heure: maintenant,
            latenceApiMs: metrics.derniere_latence_api_ms || metrics.temps_moyen_reponse_api_ms,
            latenceKpiMs: metrics.derniere_duree_recalcul_kpi_ms || metrics.temps_moyen_recalcul_kpi_ms,
          },
        ];
        return suivant.slice(-POINTS_MAX);
      });
    }
  }, [metrics]);

  return (
    <article className="chart-card">
      <div className="chart-card-header">
        <div>
          <h2 className="chart-title">Latence Réseau & Recalcul (ms)</h2>
          <p className="chart-subtitle">Temps d'exécution API HTTP vs Pipeline d'ingestion</p>
        </div>
        <div className="chart-header-badge">
          <span className="status-indicator indicator-blue">
            API : {metrics?.temps_moyen_reponse_api_ms.toFixed(1) ?? 0} ms moy.
          </span>
        </div>
      </div>

      {points.length === 0 ? (
        <p className="chart-empty">En attente des mesures de latence...</p>
      ) : (
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={points} margin={{ top: 10, right: 15, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="heure" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={{ stroke: "#e2e8f0" }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} unit=" ms" />
              <Tooltip
                contentStyle={{
                  background: "#ffffff",
                  border: "1px solid #e2e8f0",
                  borderRadius: "8px",
                  boxShadow: "0 4px 12px rgba(0, 0, 0, 0.08)",
                  fontSize: "12px",
                  color: "#0f172a",
                }}
              />
              <Line
                type="monotone"
                dataKey="latenceApiMs"
                name="Latence API (ms)"
                stroke="#0088ce"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="latenceKpiMs"
                name="Pipeline KPI (ms)"
                stroke="#f07800"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </article>
  );
}
