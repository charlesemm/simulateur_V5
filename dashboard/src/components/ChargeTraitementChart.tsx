import { useEffect, useRef, useState } from "react";
import { Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TechnicalMetricsSnapshot } from "../types";
import {
  GRADUATION, HABILLAGE, LEGENDE_STYLE, SERIE, TOOLTIP_LIBELLE, TOOLTIP_STYLE,
} from "./chartTheme";

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
                  <stop offset="5%" stopColor={SERIE.vert} stopOpacity={0.22} />
                  <stop offset="95%" stopColor={SERIE.vert} stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={HABILLAGE.grille} vertical={false} />
              <XAxis dataKey="heure" tick={GRADUATION} axisLine={{ stroke: HABILLAGE.axe }} tickLine={false} minTickGap={24} />
              <YAxis allowDecimals={false} domain={[0, (dataMax: number) => Math.max(dataMax + 2, 22)]} tick={GRADUATION} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                labelStyle={TOOLTIP_LIBELLE}
                cursor={{ stroke: HABILLAGE.axe, strokeWidth: 1 }}
              />
              {/* Deux séries : une légende, pour que la ligne pointillée ne
                  se lise pas comme une seconde mesure. */}
              <Legend verticalAlign="bottom" iconType="plainline" iconSize={16} wrapperStyle={LEGENDE_STYLE} />
              <Area
                type="monotone"
                dataKey="passagesActifs"
                name="Passages actifs"
                stroke={SERIE.vert}
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#gradientCnamGreen)"
                activeDot={{ r: 4, strokeWidth: 2, stroke: "#ffffff" }}
              />
              <Area
                type="step"
                dataKey="capaciteMax"
                name="Capacité max"
                stroke={HABILLAGE.reference}
                strokeDasharray="4 4"
                strokeWidth={1.5}
                fill="none"
                activeDot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </article>
  );
}