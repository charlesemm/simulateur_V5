// dashboard/src/components/ExecutionEnCoursCard.tsx
import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { api } from "../services/api";
import type { SimulationStatus } from "../types";
import "./Screens.css";

/**
 * Ce que le moteur est en train de faire, du point de vue de la supervision.
 *
 * Les passages interrompus sont montrés à part des échecs : ce sont des
 * coupures demandées par un scénario d'aléa, pas des pannes du simulateur.
 * Les confondre ferait passer un crash test réussi pour une avarie.
 */
export function ExecutionEnCoursCard() {
  const { token } = useAuth();
  const [statut, setStatut] = useState<SimulationStatus | null>(null);

  useEffect(() => {
    let annule = false;

    async function rafraichir() {
      try {
        const valeur = await api.getSimulationStatus(token);
        if (!annule) setStatut(valeur);
      } catch {
        // Un sondage manqué n'a pas d'importance : le suivant réessaiera.
      }
    }

    void rafraichir();
    const minuterie = setInterval(() => void rafraichir(), 2000);
    return () => {
      annule = true;
      clearInterval(minuterie);
    };
  }, [token]);

  const enCours = statut?.etat === "en_cours";

  return (
    <article className="chart-card">
      <div className="chart-card-header">
        <div>
          <h2 className="chart-title">Exécution en cours</h2>
          <p className="chart-subtitle">
            Ce que le moteur produit en ce moment, et pour quel type
          </p>
        </div>
        <div className="chart-header-badge">
          <span className={`status-indicator ${enCours ? "indicator-success" : "indicator-gray"}`}>
            {enCours ? "En cours" : "Arrêté"}
          </span>
        </div>
      </div>

      <div className="stat-strip">
        <div className="stat-tile">
          <span className="stat-tile-label">Type</span>
          <span className="stat-tile-value" style={{ fontSize: "1.2rem" }}>
            {enCours ? statut?.type_simulation ?? "—" : "—"}
          </span>
        </div>
        <div className="stat-tile">
          <span className="stat-tile-label">Passages actifs</span>
          <span className="stat-tile-value">{statut?.passages_actifs ?? 0}</span>
          <span className="stat-tile-hint">
            Limite : {statut?.passages_simultanes_max ?? 0}
          </span>
        </div>
        <div className="stat-tile">
          <span className="stat-tile-label">Interrompus par un aléa</span>
          <span className="stat-tile-value">{statut?.passages_interrompus ?? 0}</span>
          <span className="stat-tile-hint">Coupures demandées, pas des pannes</span>
        </div>
      </div>

      {enCours && statut?.simulation_id && (
        <p className="fiche-identifiant" style={{ marginTop: 14 }}>
          {statut.simulation_id}
        </p>
      )}
    </article>
  );
}
