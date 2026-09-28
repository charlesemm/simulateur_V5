// Courbe des passages ouverts, historique REST prolongé par le flux Socket.IO.
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { HistoryPoint } from "../types";
import { GRADUATION, HABILLAGE, TOOLTIP_LIBELLE, TOOLTIP_STYLE, usePaletteGraphique } from "./chartTheme";
import { EtatBloc } from "./EtatBloc";

interface PassagesHistoryChartProps {
  history: HistoryPoint[];
}

export function PassagesHistoryChart({ history }: PassagesHistoryChartProps) {
  const { serie, fond } = usePaletteGraphique();
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
        <EtatBloc ton="vide" discret>En attente des premiers passages…</EtatBloc>
      ) : (
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={points} margin={{ top: 10, right: 15, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="gradientPassages" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={serie.bleu} stopOpacity={0.24} />
                  <stop offset="95%" stopColor={serie.bleu} stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={HABILLAGE.grille} vertical={false} />
              <XAxis
                dataKey="heure"
                tick={GRADUATION}
                axisLine={{ stroke: HABILLAGE.axe }}
                tickLine={false}
                minTickGap={24}
              />
              <YAxis
                allowDecimals={false}
                tick={GRADUATION}
                axisLine={false}
                tickLine={false}
              />
              {/* Valeur en encre, pas à la couleur de la série : le trait
                  porte l'identité, le texte doit se lire. */}
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                labelStyle={TOOLTIP_LIBELLE}
                itemStyle={{ color: "var(--couleur-texte)", fontWeight: 600 }}
                cursor={{ stroke: HABILLAGE.axe, strokeWidth: 1 }}
                formatter={(valeur: number) => [`${valeur.toLocaleString("fr-FR")} passages`, "Ouverts"]}
              />
              <Area
                type="monotone"
                dataKey="passages"
                name="Passages ouverts"
                stroke={serie.bleu}
                strokeWidth={2}
                fill="url(#gradientPassages)"
                activeDot={{ r: 4, strokeWidth: 2, stroke: fond }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </article>
  );
}
