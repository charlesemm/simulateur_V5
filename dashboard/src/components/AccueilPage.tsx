// dashboard/src/components/AccueilPage.tsx
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { RequireRole } from "../auth/RequireRole";
import { api } from "../services/api";
import type { ProfilSimulation, SimulationRun, SimulationStatus } from "../types";
import { StatutPastille, dateCourte, duree } from "./format-execution";
import "./Screens.css";

interface AccueilPageProps {
  onVoirExecution: (simulationId: string) => void;
}

/**
 * W1 — Accueil commun aux trois rôles.
 *
 * Trois choses au même endroit : où en est le moteur, les quatre types qu'on
 * peut lancer, et les dernières exécutions. Le lancement n'apparaît qu'aux
 * opérateurs et aux administrateurs.
 */
export function AccueilPage({ onVoirExecution }: AccueilPageProps) {
  const { token } = useAuth();
  const [profils, setProfils] = useState<ProfilSimulation[]>([]);
  const [executions, setExecutions] = useState<SimulationRun[]>([]);
  const [statut, setStatut] = useState<SimulationStatus | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [lancement, setLancement] = useState<string | null>(null);

  const rafraichir = useCallback(async () => {
    try {
      const [listeExecutions, etat] = await Promise.all([
        api.getExecutions(token, 5),
        api.getSimulationStatus(token),
      ]);
      setExecutions(listeExecutions);
      setStatut(etat);
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    }
  }, [token]);

  useEffect(() => {
    let annule = false;

    async function charger() {
      try {
        const listeProfils = await api.getProfils(token);
        if (!annule) setProfils(listeProfils);
      } catch (raison) {
        if (!annule) setErreur((raison as Error).message);
      }
    }

    void charger();
    void rafraichir();
    // Le rythme suit celui de l'en-tête : l'état du moteur doit être le même
    // aux deux endroits, sans quoi l'écran se contredit lui-même.
    const minuterie = setInterval(() => void rafraichir(), 2000);
    return () => {
      annule = true;
      clearInterval(minuterie);
    };
  }, [token, rafraichir]);

  async function lancer(code: string) {
    setLancement(code);
    setErreur(null);
    try {
      await api.startSimulation(null, null, token, code);
      await rafraichir();
    } catch (raison) {
      setErreur((raison as Error).message);
    } finally {
      setLancement(null);
    }
  }

  const enCours = statut?.etat === "en_cours";
  const passagesCumules = executions.reduce(
    (total, execution) => total + execution.passages_reussis,
    0
  );

  return (
    <div className="screen">
      {erreur && <p className="screen-error">{erreur}</p>}

      <section>
        <h2 className="screen-section-title">État</h2>
        <div className="stat-strip">
          <div className="stat-tile">
            <span className="stat-tile-label">Moteur</span>
            <span className="stat-tile-value">{enCours ? "En cours" : "Arrêté"}</span>
            <span className="stat-tile-hint">
              {enCours
                ? `${statut?.passages_actifs ?? 0} passage(s) en parallèle`
                : "Aucune exécution ouverte"}
            </span>
          </div>
          <div className="stat-tile">
            <span className="stat-tile-label">Type en cours</span>
            <span className="stat-tile-value">
              {enCours ? (statut?.type_simulation ?? "—") : "—"}
            </span>
            <span className="stat-tile-hint">
              {enCours ? `Vitesse ×${statut?.vitesse ?? 0}` : "Choisissez un type ci-dessous"}
            </span>
          </div>
          <div className="stat-tile">
            <span className="stat-tile-label">Exécutions récentes</span>
            <span className="stat-tile-value">{executions.length}</span>
            <span className="stat-tile-hint">Les cinq dernières</span>
          </div>
          <div className="stat-tile">
            <span className="stat-tile-label">Passages réussis</span>
            <span className="stat-tile-value">{passagesCumules}</span>
            <span className="stat-tile-hint">Sur ces cinq exécutions</span>
          </div>
        </div>
      </section>

      <section>
        <h2 className="screen-section-title">Les quatre types de simulation</h2>
        <div className="type-grid">
          {profils.map((profil) => (
            <article key={profil.code} className="type-card">
              <span className="type-card-code">{profil.code}</span>
              <h3 className="type-card-title">{profil.libelle}</h3>
              <p className="type-card-desc">{profil.description}</p>
              <div className="type-card-meta">
                <span>Vitesse ×{profil.vitesse}</span>
                <span>{profil.passages_simultanes_max} en parallèle</span>
              </div>
              <RequireRole minimum="operateur">
                <button
                  className="btn btn-start"
                  onClick={() => void lancer(profil.code)}
                  disabled={enCours || lancement !== null}
                  title={enCours ? "Une exécution est déjà en cours" : "Lancer ce type"}
                >
                  {lancement === profil.code ? "Lancement…" : "Lancer"}
                </button>
              </RequireRole>
            </article>
          ))}
          {profils.length === 0 && (
            <div className="screen-empty">Les types de simulation n'ont pas pu être chargés.</div>
          )}
        </div>
      </section>

      <section>
        <h2 className="screen-section-title">Dernières exécutions</h2>
        {executions.length === 0 ? (
          <div className="screen-empty">
            Aucune exécution enregistrée pour l'instant. Lancez un type ci-dessus.
          </div>
        ) : (
          <div className="screen-table-wrap">
            <table className="screen-table">
              <thead>
                <tr>
                  <th>Début</th>
                  <th>Type</th>
                  <th>Statut</th>
                  <th>Durée</th>
                  <th>Réussis</th>
                  <th>Échoués</th>
                </tr>
              </thead>
              <tbody>
                {executions.map((execution) => (
                  <tr
                    key={execution.simulation_id}
                    className="cliquable"
                    onClick={() => onVoirExecution(execution.simulation_id)}
                  >
                    <td>{dateCourte(execution.simulation_date_debut)}</td>
                    <td>{execution.simulation_type ?? "—"}</td>
                    <td><StatutPastille statut={execution.simulation_statut} /></td>
                    <td>{duree(execution.simulation_date_debut, execution.simulation_date_fin)}</td>
                    <td>{execution.passages_reussis}</td>
                    <td>{execution.passages_echoues}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
