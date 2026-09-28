// Les cinq pathologies les plus fréquentes sur la fenêtre du snapshot KPI.
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { KpiSnapshot } from "../types";
import { GRADUATION, GRADUATION_LIBELLE, HABILLAGE, TOOLTIP_LIBELLE, TOOLTIP_STYLE, usePaletteGraphique } from "./chartTheme";
import { EtatBloc } from "./EtatBloc";

interface TopPathologiesChartProps {
  snapshot: KpiSnapshot | null;
}

/** Les libellés CNAM sont longs : au-delà, la barre déborde de la carte. */
function tronquer(libelle: string): string {
  return libelle.length > 24 ? `${libelle.slice(0, 23)}…` : libelle;
}

export function TopPathologiesChart({ snapshot }: TopPathologiesChartProps) {
  const { serie } = usePaletteGraphique();
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
        <EtatBloc ton="vide" discret>Aucune pathologie enregistrée sur la fenêtre.</EtatBloc>
      ) : (
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={donnees} layout="vertical" margin={{ top: 5, right: 20, left: 20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={HABILLAGE.grille} horizontal={false} />
              <XAxis
                type="number"
                allowDecimals={false}
                tick={GRADUATION}
                axisLine={{ stroke: HABILLAGE.axe }}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="libelle"
                width={150}
                tick={GRADUATION_LIBELLE}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: HABILLAGE.curseur }}
                contentStyle={TOOLTIP_STYLE}
                labelStyle={TOOLTIP_LIBELLE}
                formatter={(valeur: number, _nom, element) => [
                  `${valeur.toLocaleString("fr-FR")} passages`,
                  `${element.payload.code} — ${element.payload.libelleComplet}`,
                ]}
              />
              <Bar dataKey="nombre" name="Passages" fill={serie.bleu} radius={[0, 4, 4, 0]} maxBarSize={26} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </article>
  );
}
