// Section « activité métier » du tableau de bord.
//
// Le snapshot KPI était recalculé environ une fois par seconde et diffusé par
// Socket.IO sans qu'aucun composant ne l'affiche : seul `connectionStatus`
// était consommé. Cette section est le point de sortie de ce flux.
import { useKpiSocket } from "../hooks/useKpiSocket";
import { ActiviteMetierCards } from "./ActiviteMetierCards";
import { ActesRepartitionChart } from "./ActesRepartitionChart";
import { EntentesPanel } from "./EntentesPanel";
import { PassagesHistoryChart } from "./PassagesHistoryChart";
import { TopPathologiesChart } from "./TopPathologiesChart";

export function ActiviteMetierSection() {
  const { snapshot, history, loading, error } = useKpiSocket();

  // La fenêtre glisse côté serveur : l'afficher évite de lire les volumes
  // comme des cumuls depuis le démarrage du moteur.
  const fenetre = snapshot
    ? `Fenêtre glissante de ${snapshot.window.hours} h · recalculé à ${new Date(snapshot.generated_at).toLocaleTimeString("fr-FR")}`
    : "En attente du premier snapshot";

  return (
    <section className="dashboard-section" aria-label="Activité métier">
      <header className="dashboard-section-header">
        <h2 className="dashboard-section-title">Activité Métier</h2>
        <span className="dashboard-section-meta">{fenetre}</span>
      </header>

      {error && <p className="dashboard-section-error">{error}</p>}

      <ActiviteMetierCards snapshot={snapshot} loading={loading} />

      <section className="dashboard-row-2">
        <PassagesHistoryChart history={history} />
        <ActesRepartitionChart snapshot={snapshot} />
      </section>

      <section className="dashboard-row-3">
        <EntentesPanel snapshot={snapshot} />
        <TopPathologiesChart snapshot={snapshot} />
      </section>
    </section>
  );
}
