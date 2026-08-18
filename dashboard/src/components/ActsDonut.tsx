// Affiche la répartition proportionnelle des actes dans un donut Recharts.
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { useKpiSocket } from "../hooks/useKpiSocket";

const COLORS = ["#007f78", "#e9a23b", "#5c7cfa", "#e56b6f", "#8f6bb3"];

export function ActsDonut() {
  const { snapshot, loading, error } = useKpiSocket();
  if (loading && !snapshot) return <div className="chart-panel skeleton" />;
  if (error && !snapshot) return <div className="chart-panel"><p className="panel-error">{error}</p></div>;
  const data = snapshot?.actes_repartition ?? [];
  return <article className="chart-panel"><h2>Répartition des actes</h2><p className="panel-subtitle">Part par type de parcours</p>
    {data.length ? <ResponsiveContainer width="100%" height={280}><PieChart><Pie data={data} dataKey="nombre" nameKey="type" innerRadius={62} outerRadius={92} paddingAngle={2}>
      {data.map((item, index) => <Cell key={item.type} fill={COLORS[index % COLORS.length]} />)}
    </Pie><Tooltip formatter={(value) => [Number(value), "Actes"]} /><Legend /></PieChart></ResponsiveContainer>
      : <p className="empty-state">Aucun acte sur la période.</p>}
  </article>;
}