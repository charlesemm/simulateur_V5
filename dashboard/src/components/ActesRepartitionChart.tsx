// Répartition des actes produits sur la fenêtre glissante du snapshot KPI.
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { KpiSnapshot } from "../types";
import {
  GRADUATION, GRADUATION_LIBELLE, HABILLAGE, SERIE, TOOLTIP_LIBELLE, TOOLTIP_STYLE,
} from "./chartTheme";

interface ActesRepartitionChartProps {
  snapshot: KpiSnapshot | null;
}

// Une seule teinte pour toutes les barres. Chaque famille d'actes est déjà
// nommée sur l'axe : la colorier en plus faisait porter deux fois la même
// information, et trois des cinq couleurs étaient des bleus qu'on ne
// distinguait pas l'un de l'autre.

export function ActesRepartitionChart({ snapshot }: ActesRepartitionChartProps) {
  const donnees = (snapshot?.actes_repartition ?? [])
    .filter((acte) => acte.nombre > 0)
    .map((acte) => ({
      type: acte.type,
      // La majuscule initiale est purement d'affichage : le type reste la clé.
      libelle: acte.type.charAt(0).toUpperCase() + acte.type.slice(1),
      nombre: acte.nombre,
      pourcentage: acte.pourcentage,
    }))
    .sort((a, b) => b.nombre - a.nombre);

  const total = donnees.reduce((somme, acte) => somme + acte.nombre, 0);

  return (
    <article className="chart-card">
      <div className="chart-card-header">
        <div>
          <h2 className="chart-title">Répartition des Actes</h2>
          <p className="chart-subtitle">
            {total > 0
              ? `${total.toLocaleString("fr-FR")} actes sur les ${snapshot?.window.hours ?? 24} dernières heures`
              : "En attente des premiers actes"}
          </p>
        </div>
      </div>

      {donnees.length === 0 ? (
        <p className="chart-empty">Aucun acte enregistré sur la fenêtre.</p>
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
                width={110}
                tick={GRADUATION_LIBELLE}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: HABILLAGE.curseur }}
                contentStyle={TOOLTIP_STYLE}
                labelStyle={TOOLTIP_LIBELLE}
                formatter={(valeur: number, _nom, element) => [
                  `${valeur.toLocaleString("fr-FR")} actes (${element.payload.pourcentage}%)`,
                  "Volume",
                ]}
              />
              <Bar dataKey="nombre" name="Volume" fill={SERIE.bleu} radius={[0, 4, 4, 0]} maxBarSize={26} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </article>
  );
}
