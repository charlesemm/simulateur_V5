// Les cinq pathologies les plus fréquentes sur la fenêtre du snapshot KPI.
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { KpiSnapshot } from "../types";
import { TOOLTIP_STYLE } from "./chartTheme";

interface TopPathologiesChartProps {
  snapshot: KpiSnapshot | null;
}

/** Les libellés CNAM sont longs : au-delà, la barre déborde de la carte. */
function tronquer(libelle: string): string {
  return libelle.length > 24 ? `${libelle.slice(0, 23)}…` : libelle;
}

export function TopPathologiesChart({ snapshot }: TopPathologiesChartProps) {
  const donnees = (snapshot?.top_pathologies ?? []).map((pathologie) => ({
    code: pathologie.code,
    libelle: tronquer(pathologie.libelle),
    libelleComplet: pathologie.libelle,
    nombre: pathologie.nombre,
  }));

  return (
    <article className="chart-card">
      <div className="chart-card-header">
        <div>
          <h2 className="chart-title">Top Pathologies</h2>
          <p className="chart-subtitle">
            Motifs de consultation les plus fréquents ({snapshot?.window.hours ?? 24} h)
          </p>
        </div>
      </div>

      {donnees.length === 0 ? (
        <p className="chart-empty">Aucune pathologie enregistrée sur la fenêtre.</p>
      ) : (
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={donnees} layout="vertical" margin={{ top: 5, right: 20, left: 20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
              <XAxis
                type="number"
                allowDecimals={false}
                tick={{ fontSize: 11, fill: "#94a3b8" }}
                axisLine={{ stroke: "#e2e8f0" }}
              />
              <YAxis
                type="category"
                dataKey="libelle"
                width={150}
                tick={{ fontSize: 11, fill: "#64748b" }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: "#f8fafc" }}
                contentStyle={TOOLTIP_STYLE}
                formatter={(valeur: number, _nom, element) => [
                  `${valeur.toLocaleString("fr-FR")} passages`,
                  `${element.payload.code} — ${element.payload.libelleComplet}`,
                ]}
              />
              <Bar dataKey="nombre" name="Passages" fill="#0088ce" radius={[0, 4, 4, 0]} maxBarSize={26} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </article>
  );
}
