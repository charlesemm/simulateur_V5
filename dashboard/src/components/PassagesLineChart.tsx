// Trace l'évolution des passages à partir de l'historique REST puis Socket.IO.
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useKpiSocket } from "../hooks/useKpiSocket";

export function PassagesLineChart() {
  const { history, loading, error } = useKpiSocket();
  if (loading && !history.length) return <div className="chart-panel skeleton" aria-label="Chargement de la courbe" />;
  if (error && !history.length) return <div className="chart-panel"><p className="panel-error">{error}</p></div>;
  const data = history.map((point) => ({
    heure: new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" }).format(new Date(point.timestamp)),
    passages: point.value,
  }));
  return <article className="chart-panel chart-wide"><h2>Évolution des passages</h2><p className="panel-subtitle">Dernières 24 heures simulées</p>
    {data.length ? <ResponsiveContainer width="100%" height={280}><LineChart data={data} margin={{ top: 12, right: 16, left: -12, bottom: 0 }}>
      <CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="heure" /><YAxis allowDecimals={false} />
      <Tooltip /><Line type="monotone" dataKey="passages" stroke="#007f78" strokeWidth={3} dot={false} activeDot={{ r: 5 }} />
    </LineChart></ResponsiveContainer> : <p className="empty-state">L'historique apparaîtra après les premiers passages.</p>}
  </article>;
}