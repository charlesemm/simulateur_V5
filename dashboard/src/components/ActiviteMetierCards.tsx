// Cartes de synthèse de l'activité métier, alimentées par le snapshot KPI.
import type { KpiSnapshot } from "../types";
import { ActivityIcon, BoltIcon, ClockIcon, CpuIcon, ReportsIcon, ShieldCheckIcon } from "./Icons";
import { formatDelai, formatMontant } from "./format";

interface ActiviteMetierCardsProps {
  snapshot: KpiSnapshot | null;
  loading: boolean;
}

export function ActiviteMetierCards({ snapshot, loading }: ActiviteMetierCardsProps) {
  if (loading && !snapshot) {
    return (
      <section className="tech-metric-grid" aria-label="Chargement de l'activité métier">
        {Array.from({ length: 6 }, (_, index) => (
          <div className="skeleton tech-metric-card" key={index} />
        ))}
      </section>
    );
  }

  if (!snapshot) {
    return <p className="empty-state">Aucune donnée d'activité disponible.</p>;
  }

  const { passages, montants, ententes, charge_centres, actes_repartition, window } = snapshot;

  // Le taux de clôture dit si le moteur termine ce qu'il ouvre, alors que le
  // total seul monte quoi qu'il arrive.
  const tauxCloture = passages.total > 0
    ? Math.round((passages.clotures * 100) / passages.total)
    : 0;

  const ententesTraitees = Object.values(ententes.global)
    .reduce((somme, statut) => somme + statut.nombre, 0);

  const totalActes = actes_repartition.reduce((somme, acte) => somme + acte.nombre, 0);

  const totalMontants = montants.cumule.cmu + montants.cumule.assure;
  // La part réellement prise en charge varie avec le mélange RAM / RGB observé
  // dans la fenêtre : elle ne vaut ni 70 % ni 100 % en général.
  const partCmu = totalMontants > 0
    ? Math.round((montants.cumule.cmu * 100) / totalMontants)
    : 0;

  const cards = [
    {
      id: "passages-en-cours",
      label: "Passages en cours",
      value: passages.en_cours.toLocaleString("fr-FR"),
      badge: `${window.hours} h`,
      badgeType: "badge-blue",
      subtext: `${passages.total.toLocaleString("fr-FR")} ouverts sur la fenêtre`,
      icon: <BoltIcon className="card-icon-svg icon-green" />,
    },
    {
      id: "passages-clotures",
      label: "Passages clôturés",
      value: passages.clotures.toLocaleString("fr-FR"),
      badge: `${tauxCloture}%`,
      badgeType: tauxCloture >= 50 ? "badge-green" : "badge-orange",
      subtext: `Taux de clôture sur ${passages.total.toLocaleString("fr-FR")} passages`,
      icon: <ShieldCheckIcon className="card-icon-svg icon-green" />,
    },
    {
      id: "montant-cmu",
      label: "Pris en charge CMU",
      value: formatMontant(montants.cumule.cmu),
      badge: `${partCmu}%`,
      badgeType: "badge-green",
      subtext: `Sur ${formatMontant(totalMontants)} facturés`,
      icon: <ReportsIcon className="card-icon-svg icon-green" />,
    },
    {
      id: "montant-assure",
      label: "Reste à charge assuré",
      value: formatMontant(montants.cumule.assure),
      badge: `${100 - partCmu}%`,
      badgeType: "badge-orange",
      subtext: "Ticket modérateur cumulé",
      icon: <CpuIcon className="card-icon-svg icon-slate" />,
    },
    {
      id: "ententes",
      label: "Ententes traitées",
      value: ententesTraitees.toLocaleString("fr-FR"),
      badge: "Préalables",
      badgeType: "badge-blue",
      subtext: `Médecin conseil : ${formatDelai(ententes.delai_moyen_secondes.medecin_conseil)}`,
      icon: <ClockIcon className="card-icon-svg icon-cyan" />,
    },
    {
      id: "centres",
      label: "Centres actifs",
      value: charge_centres.length.toLocaleString("fr-FR"),
      badge: `${totalActes.toLocaleString("fr-FR")} actes`,
      badgeType: "badge-gray",
      subtext: "Centres portant au moins un passage ouvert",
      icon: <ActivityIcon className="card-icon-svg icon-blue" />,
    },
  ];

  return (
    <section className="tech-metric-grid" aria-label="Indicateurs d'activité métier">
      {cards.map((carte) => (
        <article className="tech-metric-card" key={carte.id}>
          <div className="card-header">
            <div className="card-header-title">
              {carte.icon}
              <span className="card-label">{carte.label}</span>
            </div>
            <span className={`card-badge ${carte.badgeType}`}>{carte.badge}</span>
          </div>
          <div className="card-body">
            <strong className="card-value">{carte.value}</strong>
            <span className="card-subtext">{carte.subtext}</span>
          </div>
        </article>
      ))}
    </section>
  );
}
