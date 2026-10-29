import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { TechnicalMetricsSnapshot } from "../types";
import { LEGENDE_STYLE, TOOLTIP_STYLE, legendeEnEncre, usePaletteGraphique } from "./chartTheme";
import { EtatBloc } from "./EtatBloc";

interface SystemHealthDonutProps {
  metrics: TechnicalMetricsSnapshot | null;
}

export function SystemHealthDonut({ metrics }: SystemHealthDonutProps) {
  const { etat, fond } = usePaletteGraphique();
  if (!metrics) {
    return (
      <article className="chart-card">
        <h2 className="chart-title">Fiabilité d'Exécution</h2>
        <p className="chart-subtitle">Taux d'exécution du moteur</p>
        <EtatBloc ton="vide" discret>En attente de données…</EtatBloc>
      </article>
    );
  }

  const success = metrics.passages_reussis;
  const errors = metrics.passages_echoues;
  const total = success + errors;

  const data = [
    // Réussite et échec sont des états, pas des séries quelconques : une paire
    // choisie pour rester distincte aux daltoniens, et toujours accompagnée
    // de son libellé dans la légende.
    { name: "Passages réussis", value: success, color: etat.reussite },
    { name: "Passages échoués", value: errors, color: etat.echec },
  ];

  return (
    <article className="chart-card">
      <div className="chart-card-header">
        <div>
          <h2 className="chart-title">Fiabilité d'Exécution</h2>
          <p className="chart-subtitle">
            {total > 0
              ? `${metrics.taux_succes_pourcent.toFixed(1)}% de succès sur ${total.toLocaleString("fr-FR")} passages`
              : "En attente des premiers passages"}
          </p>
        </div>
      </div>

      {total === 0 ? (
        <EtatBloc ton="vide" discret>Aucun passage exécuté depuis le démarrage.</EtatBloc>
      ) : (
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                innerRadius={52}
                outerRadius={78}
                paddingAngle={2}
                stroke={fond}
                strokeWidth={2}
              >
                {data.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                formatter={(val) => [Number(val).toLocaleString("fr-FR"), "Passages"]}
              />
              <Legend
                verticalAlign="bottom"
                height={32}
                iconType="circle"
                iconSize={10}
                wrapperStyle={LEGENDE_STYLE} formatter={legendeEnEncre}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}
    </article>
  );
}
