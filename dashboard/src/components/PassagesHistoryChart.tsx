// Courbe des passages ouverts, historique REST prolongé par le flux Socket.IO.
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { HistoryPoint } from "../types";
import { TOOLTIP_STYLE } from "./chartTheme";

interface PassagesHistoryChartProps {
  history: HistoryPoint[];
}

export function PassagesHistoryChart({ history }: PassagesHistoryChartProps) {
  // L'historique arrive dans l'ordre du serveur, mais le point courant poussé
  // par Socket.IO est concaténé en fin de liste : on retrie sur l'horodatage.
  const points = [...history]
    .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
    .map((point) => ({
      horodatage: point.timestamp,
      heure: new Date(point.timestamp).toLocaleTimeString("fr-FR", {
        hour: "2-digit",
        minute: "2-digit",
      }),
      passages: point.value,
    }));

  const dernier = points.at(-1);
  const precedent = points.at(-2);
  const tendance = dernier && precedent ? dernier.passages - precedent.passages : 0;

  return (
    <article className="chart-card">
      <div className="chart-card-header">
        <div>
          <h2 className="chart-title">Passages Ouverts</h2>
          <p className="chart-subtitle">Historique consolidé et flux temps réel</p>
        </div>
        {dernier && (
          <div className="chart-header-badge">
            <span className={`status-indicator ${tendance >= 0 ? "indicator-normal" : "indicator-gray"}`}>
              {tendance >= 0 ? "+" : ""}{tendance.toLocaleString("fr-FR")} depuis le point précédent
            </span>
          </div>
        )}
      </div>

      {points.length === 0 ? (
        <p className="chart-empty">En attente des premiers passages...</p>
      ) : (
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={points} margin={{ top: 10, right: 15, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="gradientPassages" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0088ce" stopOpacity={0.28} />
                  <stop offset="95%" stopColor="#0088ce" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis
                dataKey="heure"
                tick={{ fontSize: 11, fill: "#94a3b8" }}
                axisLine={{ stroke: "#e2e8f0" }}
                minTickGap={24}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fontSize: 11, fill: "#94a3b8" }}
                axisLine={false}
              />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                itemStyle={{ color: "#0088ce", fontWeight: 600 }}
                formatter={(valeur: number) => [`${valeur.toLocaleString("fr-FR")} passages`, "Ouverts"]}
              />
              <Area
                type="monotone"
                dataKey="passages"
                name="Passages ouverts"
                stroke="#0088ce"
                strokeWidth={2}
                fill="url(#gradientPassages)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </article>
  );
}
