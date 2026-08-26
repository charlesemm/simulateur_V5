import { useEffect, useRef, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TechnicalMetricsSnapshot } from "../types";

interface PointCharge {
  heure: string;
  passagesActifs: number;
  capaciteMax: number;
}

const POINTS_MAX = 40;

interface ChargeTraitementChartProps {
  metrics: TechnicalMetricsSnapshot | null;
}

export function ChargeTraitementChart({ metrics }: ChargeTraitementChartProps) {
  const [points, setPoints] = useState<PointCharge[]>([]);
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
            passagesActifs: metrics.passages_actifs,
            capaciteMax: metrics.passages_simultanes_max,
          },
        ];
        return suivant.slice(-POINTS_MAX);
      });
    }
  }, [metrics]);

  const dernierPoint = points.at(-1);
  const saturation = dernierPoint && dernierPoint.capaciteMax > 0
    ? Math.round((dernierPoint.passagesActifs / dernierPoint.capaciteMax) * 100)
    : 0;

  return (
    <article className="chart-card">
      <div className="chart-card-header">
        <div>
          <h2 className="chart-title">Concurrence & Capacité Moteur</h2>
          <p className="chart-subtitle">
            Passages en cours vs Limite du sémaphore ({metrics?.passages_simultanes_max ?? 20} slots)
          </p>
        </div>
        <div className="chart-header-badge">
          <span className={`status-indicator ${saturation >= 85 ? "indicator-warning" : "indicator-normal"}`}>
            {saturation}% de charge
          </span>
        </div>
      </div>

      {points.length === 0 ? (
        <p className="chart-empty">En attente des premières mesures du moteur...</p>
      ) : (
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={points} margin={{ top: 10, right: 15, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="gradientCnamGreen" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#4caf2a" stopOpacity={0.28} />
                  <stop offset="95%" stopColor="#4caf2a" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="heure" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={{ stroke: "#e2e8f0" }} />
              <YAxis allowDecimals={false} domain={[0, (dataMax: number) => Math.max(dataMax + 2, 22)]} tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} />
              <Tooltip
                contentStyle={{
                  background: "#ffffff",
                  border: "1px solid #e2e8f0",
                  borderRadius: "8px",
                  boxShadow: "0 4px 12px rgba(0, 0, 0, 0.08)",
                  fontSize: "12px",
                  color: "#0f172a",
                }}
                itemStyle={{ color: "#4caf2a", fontWeight: 600 }}
              />
              <Area
                type="monotone"
                dataKey="passagesActifs"
                name="Passages actifs"
                stroke="#4caf2a"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#gradientCnamGreen)"
              />
              <Area
                type="step"
                dataKey="capaciteMax"
                name="Capacité max"
                stroke="#cbd5e1"
                strokeDasharray="4 4"
                strokeWidth={1.5}
                fill="none"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </article>
  );
}