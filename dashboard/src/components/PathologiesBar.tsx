// Compare les cinq pathologies les plus fréquentes dans un bar chart horizontal.
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useKpiSocket } from "../hooks/useKpiSocket";

export function PathologiesBar() {
  const { snapshot, loading, error } = useKpiSocket();
  if (loading && !snapshot) return <div className="chart-panel skeleton" />;
  if (error && !snapshot) return <div className="chart-panel"><p className="panel-error">{error}</p></div>;
  const data = snapshot?.top_pathologies ?? [];
  return <article className="chart-panel"><h2>Top 5 pathologies</h2><p className="panel-subtitle">Diagnostics les plus fréquents</p>
    {data.length ? <ResponsiveContainer width="100%" height={280}><BarChart data={data} layout="vertical" margin={{ left: 24, right: 16 }}>
      <CartesianGrid strokeDasharray="3 3" horizontal={false} /><XAxis type="number" allowDecimals={false} />
      <YAxis type="category" dataKey="libelle" width={125} tick={{ fontSize: 11 }} />
      <Tooltip /><Bar dataKey="nombre" name="Factures" fill="#e9a23b" radius={[0, 5, 5, 0]} />
    </BarChart></ResponsiveContainer> : <p className="empty-state">Aucune pathologie sur la période.</p>}
  </article>;
}