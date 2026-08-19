import type { TechnicalMetricsSnapshot } from "../types";
import { ActivityIcon, BoltIcon, ClockIcon, CpuIcon, ShieldCheckIcon, WifiIcon } from "./Icons";

interface TechMetricCardsProps {
  metrics: TechnicalMetricsSnapshot | null;
  loading: boolean;
}

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export function TechMetricCards({ metrics, loading }: TechMetricCardsProps) {
  if (loading && !metrics) {
    return (
      <section className="tech-metric-grid" aria-label="Chargement des métriques">
        <div className="skeleton tech-metric-card" />
        <div className="skeleton tech-metric-card" />
        <div className="skeleton tech-metric-card" />
        <div className="skeleton tech-metric-card" />
        <div className="skeleton tech-metric-card" />
        <div className="skeleton tech-metric-card" />
      </section>
    );
  }

  if (!metrics) {
    return <p className="empty-state">Aucune métrique technique disponible.</p>;
  }

  const saturation = metrics.passages_simultanes_max
    ? Math.round((metrics.passages_actifs / metrics.passages_simultanes_max) * 100)
    : 0;

  const cards = [
    {
      id: "charge",
      label: "Concurrence Moteur",
      value: `${metrics.passages_actifs} / ${metrics.passages_simultanes_max}`,
      badge: `${saturation}%`,
      badgeType: saturation >= 85 ? "badge-orange" : "badge-green",
      subtext: `Pic : ${metrics.pic_passages_simultanes} passages`,
      icon: <BoltIcon className="card-icon-svg icon-green" />,
    },
    {
      id: "events",
      label: "Débit Événements",
      value: `${metrics.debit_evenements_par_sec} ev/s`,
      badge: "Actif",
      badgeType: "badge-blue",
      subtext: `${metrics.evenements_totaux.toLocaleString("fr-FR")} événements`,
      icon: <ActivityIcon className="card-icon-svg icon-blue" />,
    },
    {
      id: "fiabilite",
      label: "Taux de Succès",
      value: `${metrics.taux_succes_pourcent.toFixed(1)}%`,
      badge: metrics.taux_echec_pourcent > 5 ? "Dégradé" : "Optimal",
      badgeType: metrics.taux_echec_pourcent > 5 ? "badge-orange" : "badge-green",
      subtext: `${metrics.passages_reussis} succès · ${metrics.passages_echoues} échecs`,
      icon: <ShieldCheckIcon className="card-icon-svg icon-green" />,
    },
    {
      id: "latence",
      label: "Latence API",
      value: `${metrics.temps_moyen_reponse_api_ms.toFixed(1)} ms`,
      badge: "HTTP",
      badgeType: "badge-blue",
      subtext: `Dernière : ${metrics.derniere_latence_api_ms.toFixed(1)} ms`,
      icon: <ClockIcon className="card-icon-svg icon-cyan" />,
    },
    {
      id: "socketio",
      label: "Clients WebSocket",
      value: `${metrics.clients_socketio_actifs}`,
      badge: "Socket.IO",
      badgeType: "badge-green",
      subtext: `${metrics.connexions_socketio_total} connectés au total`,
      icon: <WifiIcon className="card-icon-svg icon-green" />,
    },
    {
      id: "ressources",
      label: "Mémoire & Uptime",
      value: `${metrics.memoire_rss_mo} Mo`,
      badge: "RSS",
      badgeType: "badge-gray",
      subtext: `Uptime : ${formatUptime(metrics.uptime_secondes)}`,
      icon: <CpuIcon className="card-icon-svg icon-slate" />,
    },
  ];

  return (
    <section className="tech-metric-grid" aria-label="Indicateurs de télémétrie">
      {cards.map((c) => (
        <article className="tech-metric-card" key={c.id}>
          <div className="card-header">
            <div className="card-header-title">
              {c.icon}
              <span className="card-label">{c.label}</span>
            </div>
            <span className={`card-badge ${c.badgeType}`}>{c.badge}</span>
          </div>
          <div className="card-body">
            <strong className="card-value">{c.value}</strong>
            <span className="card-subtext">{c.subtext}</span>
          </div>
        </article>
      ))}
    </section>
  );
}
