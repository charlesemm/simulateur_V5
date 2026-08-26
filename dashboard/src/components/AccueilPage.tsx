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
  /** Ouvre l'écran de paramétrage du type choisi. */
  onConfigurer: (typeSimulation: string) => void;
  /** Rejoint le poste de pilotage tant qu'une exécution tourne. */
  onRejoindreCockpit?: () => void;
  /** Ouvre l'historique complet. */
  onVoirHistorique?: () => void;
}

/**
 * W1 — Accueil commun aux trois rôles.
 *
 * Trois choses au même endroit : où en est le moteur, les quatre types qu'on
 * peut lancer, et les dernières exécutions. Le lancement n'apparaît qu'aux
 * opérateurs et aux administrateurs.
 */
export function AccueilPage({
  onVoirExecution,
  onConfigurer,
  onRejoindreCockpit,
  onVoirHistorique,
}: AccueilPageProps) {
  const { token } = useAuth();
  const [profils, setProfils] = useState<ProfilSimulation[]>([]);
  const [executions, setExecutions] = useState<SimulationRun[]>([]);
  const [statut, setStatut] = useState<SimulationStatus | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

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

  const enCours = statut?.etat === "en_cours";
  const passagesCumules = executions.reduce(
    (total, execution) => total + execution.passages_reussis,
    0
  );
  // La tuile « type en cours » emprunte la couleur du type qui tourne.
  const couleurDuType =
    profils.find((profil) => profil.code === statut?.type_simulation)?.couleur
    ?? "var(--text-light)";

  return (
    <div className="screen">
      {erreur && <p className="screen-error">{erreur}</p>}

      <section className="home-hero">
        <div className={`home-status${enCours ? " home-status--live" : ""}`}>
          <div>
            <span className="home-kicker">
              {enCours && <span className="pouls pouls-clair" aria-hidden="true" />}
              {enCours ? "Simulation active" : "Prêt à simuler"}
            </span>
            <h2>
              {enCours
                ? `${statut?.type_simulation ?? "Simulation"} tourne actuellement`
                : "Choisissez un type, puis lancez"}
            </h2>
            <p>
              {enCours
                ? `${statut?.passages_actifs ?? 0} passage(s) en parallèle · vitesse ×${statut?.vitesse ?? 0}`
                : "Un seul type est opérationnel pour l'instant. Les autres attendront leur cahier des charges."}
            </p>
          </div>
          {enCours && onRejoindreCockpit ? (
            <button type="button" className="btn btn-start" onClick={onRejoindreCockpit}>
              Rejoindre le pilotage
            </button>
          ) : null}
        </div>

        <div className="home-kpis">
          <div
            className="stat-tile stat-tile--accent"
            style={{ ["--tuile-couleur" as string]: couleurDuType }}
          >
            <span className="stat-tile-label">Type</span>
            <span className="stat-tile-value">
              {enCours ? (statut?.type_simulation ?? "—") : "—"}
            </span>
            <span className="stat-tile-hint">
              {enCours ? `Vitesse ×${statut?.vitesse ?? 0}` : "Aucun moteur ouvert"}
            </span>
          </div>
          <div
            className="stat-tile stat-tile--accent"
            style={{ ["--tuile-couleur" as string]: "var(--cnam-blue-vif)" }}
          >
            <span className="stat-tile-label">Exécutions</span>
            <span className="stat-tile-value">{executions.length}</span>
            <span className="stat-tile-hint">Les cinq dernières</span>
          </div>
          <div
            className="stat-tile stat-tile--accent"
            style={{ ["--tuile-couleur" as string]: "var(--cnam-green-vif)" }}
          >
            <span className="stat-tile-label">Passages réussis</span>
            <span className="stat-tile-value">{passagesCumules}</span>
            <span className="stat-tile-hint">Sur ces cinq exécutions</span>
          </div>
          <div className={`stat-tile stat-tile--accent${enCours ? " vivante" : ""}`}>
            <span className="stat-tile-label">Moteur</span>
            <span className="stat-tile-value">{enCours ? "En cours" : "Arrêté"}</span>
            <span className="stat-tile-hint">
              {enCours
                ? `${statut?.passages_actifs ?? 0} passage(s) en parallèle`
                : "Aucune exécution ouverte"}
            </span>
          </div>
        </div>
      </section>

      <section>
        <div className="screen-section-head">
          <h2 className="screen-section-title">Lancer une simulation</h2>
        </div>
        <p className="screen-section-lead">
          Le type LIBRE ouvre le paramétrage, puis le poste de pilotage. Les autres cartes restent visibles, sans action.
        </p>
        <div className="type-grid">
          {profils.map((profil) => {
            // Les quatre types spécialisés sont désactivés en attendant le
            // cahier des charges. Seul LIBRE est opérationnel.
            const enAttente = profil.code !== "LIBRE";

            return (
            <RequireRole
              key={profil.code}
              minimum="operateur"
              sinon={
                <article
                  className={`type-card type-card--lecture${enAttente ? " type-card--desactive" : " type-card--featured"}`}
                  style={{ ["--type-couleur" as string]: profil.couleur }}
                >
                  <span className="type-card-code">{profil.code}</span>
                  <h3 className="type-card-title">{profil.libelle}</h3>
                  <p className="type-card-desc">{profil.description}</p>
                  {enAttente && (
                    <span className="type-card-attente">En attente du cahier des charges</span>
                  )}
                  <div className="type-card-meta">
                    <span>Vitesse ×{profil.vitesse}</span>
                    <span>{profil.passages_simultanes_max} en parallèle</span>
                  </div>
                </article>
              }
            >
              <button
                type="button"
                className={`type-card type-card--action${enAttente ? " type-card--desactive" : " type-card--featured"}`}
                style={{ ["--type-couleur" as string]: profil.couleur }}
                onClick={() => onConfigurer(profil.code)}
                disabled={enCours || enAttente}
                title={
                  enAttente
                    ? "En attente du cahier des charges"
                    : enCours
                      ? "Une exécution est déjà en cours"
                      : "Paramétrer puis lancer ce type"
                }
              >
                <span className="type-card-code">{profil.code}</span>
                <span className="type-card-title">{profil.libelle}</span>
                <span className="type-card-desc">{profil.description}</span>
                {enAttente && (
                  <span className="type-card-attente">En attente du cahier des charges</span>
                )}
                <span className="type-card-meta">
                  <span>Vitesse ×{profil.vitesse}</span>
                  <span>{profil.passages_simultanes_max} en parallèle</span>
                </span>
                {!enAttente && (
                  <span className="type-card-appel">
                    Paramétrer une simulation
                    <span className="type-card-fleche" aria-hidden="true">→</span>
                  </span>
                )}
              </button>
            </RequireRole>
            );
          })}
          {profils.length === 0 && (
            <div className="screen-empty">Les types de simulation n'ont pas pu être chargés.</div>
          )}
        </div>
      </section>

      <section>
        <div className="screen-section-head">
          <h2 className="screen-section-title">Dernières exécutions</h2>
          {onVoirHistorique && executions.length > 0 && (
            <button type="button" className="btn-text" onClick={onVoirHistorique}>
              Tout l'historique →
            </button>
          )}
        </div>
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
