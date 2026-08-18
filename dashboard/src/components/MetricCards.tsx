// Présente les quatre indicateurs prioritaires avec leurs états UI.
import { useKpiSocket } from "../hooks/useKpiSocket";

export function MetricCards() {
  const { snapshot, loading, error } = useKpiSocket();
  if (loading && !snapshot) return <section className="metric-grid" aria-label="Chargement des compteurs"><div className="skeleton metric-card" /><div className="skeleton metric-card" /><div className="skeleton metric-card" /><div className="skeleton metric-card" /></section>;
  if (error && !snapshot) return <p className="panel-error" role="alert">{error}</p>;
  if (!snapshot) return <p className="empty-state">Aucun KPI disponible.</p>;

  const rates = snapshot.ententes.global;
  const accepted = (rates.acceptee?.nombre ?? 0) + (rates.validee_office?.nombre ?? 0);
  const total = Object.values(rates).reduce((sum, item) => sum + item.nombre, 0);
  const acceptance = total ? accepted * 100 / total : 0;
  const currency = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "XOF", maximumFractionDigits: 0 });
  const cards = [
    ["Passages en cours", snapshot.passages.en_cours.toLocaleString("fr-FR"), "live"],
    ["Passages clôturés", snapshot.passages.clotures.toLocaleString("fr-FR"), "closed"],
    ["Ententes acceptées", `${acceptance.toFixed(1)} %`, "agreement"],
    ["Prise en charge CMU", currency.format(snapshot.montants.cumule.cmu), "amount"],
  ];
  return <section className="metric-grid" aria-label="Indicateurs principaux">
    {cards.map(([label, value, tone]) => <article className={`metric-card metric-${tone}`} key={label}>
      <p>{label}</p><strong>{value}</strong><span>Fenêtre simulée de 24 h</span>
    </article>)}
  </section>;
}