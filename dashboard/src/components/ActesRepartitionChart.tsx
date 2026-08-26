// Répartition des actes produits sur la fenêtre glissante du snapshot KPI.
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { KpiSnapshot } from "../types";
import { TOOLTIP_STYLE } from "./chartTheme";

interface ActesRepartitionChartProps {
  snapshot: KpiSnapshot | null;
}

// Une couleur par famille d'actes, pour que la lecture reste stable d'un
// rafraîchissement à l'autre même si l'ordre des barres change.
const COULEURS: Record<string, string> = {
  ambulatoire: "#4caf2a",
  dentaire: "#0088ce",
  pharmacie: "#f07800",
  hospitalisation: "#005888",
  "biologie-imagerie": "#1a9cdc",
};

const COULEUR_PAR_DEFAUT = "#94a3b8";

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
                width={110}
                tick={{ fontSize: 11, fill: "#64748b" }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: "#f8fafc" }}
                contentStyle={TOOLTIP_STYLE}
                formatter={(valeur: number, _nom, element) => [
                  `${valeur.toLocaleString("fr-FR")} actes (${element.payload.pourcentage}%)`,
                  "Volume",
                ]}
              />
              <Bar dataKey="nombre" name="Volume" radius={[0, 4, 4, 0]} maxBarSize={26}>
                {donnees.map((acte) => (
                  <Cell key={acte.type} fill={COULEURS[acte.type] ?? COULEUR_PAR_DEFAUT} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </article>
  );
}
