// dashboard/src/components/SimulationsPage.tsx
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { api } from "../services/api";
import type { ExecutionDetail, SimulationRun } from "../types";
import { StatutPastille, dateCourte, duree } from "./format-execution";
import "./Screens.css";

interface SimulationsPageProps {
  /** Exécution à ouvrir d'emblée, quand on arrive depuis l'accueil. */
  executionInitiale?: string | null;
}

const LIBELLES_VOLUMETRIE: Record<string, string> = {
  factures: "Factures",
  prestations: "Prestations",
  ententes: "Ententes préalables",
  evenements: "Événements",
  anomalies: "Anomalies injectées",
};

/**
 * W3 — Historique des exécutions et fiche de l'une d'elles.
 *
 * La fiche compte ce que l'exécution a laissé en base. Les lignes produites
 * avant que les exécutions n'existent portent un identifiant nul : elles
 * n'apparaissent dans aucune fiche, et c'est voulu.
 */
export function SimulationsPage({ executionInitiale = null }: SimulationsPageProps) {
  const { token } = useAuth();
  const [executions, setExecutions] = useState<SimulationRun[]>([]);
  const [selection, setSelection] = useState<string | null>(executionInitiale);
  const [fiche, setFiche] = useState<ExecutionDetail | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  const chargerListe = useCallback(async () => {
    try {
      setExecutions(await api.getExecutions(token, 50));
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    }
  }, [token]);

  useEffect(() => {
    void chargerListe();
    // Une exécution en cours voit ses compteurs bouger : la liste se rafraîchit
    // sans qu'on ait à quitter l'écran.
    const minuterie = setInterval(() => void chargerListe(), 5000);
    return () => clearInterval(minuterie);
  }, [chargerListe]);

  useEffect(() => {
    if (!selection) {
      setFiche(null);
      return;
    }
    let annule = false;

    async function charger(identifiant: string) {
      try {
        const detail = await api.getExecution(identifiant, token);
        if (!annule) {
          setFiche(detail);
          setErreur(null);
        }
      } catch (raison) {
        if (!annule) setErreur((raison as Error).message);
      }
    }

    void charger(selection);
    return () => {
      annule = true;
    };
  }, [selection, token, executions]);

  return (
    <div className="screen">
      {erreur && <p className="screen-error">{erreur}</p>}

      <section>
        <h2 className="screen-section-title">Historique des exécutions</h2>
        {executions.length === 0 ? (
          <div className="screen-empty">
            Aucune exécution enregistrée. Lancez un type depuis l'accueil.
          </div>
        ) : (
          <div className="screen-table-wrap">
            <table className="screen-table">
              <thead>
                <tr>
                  <th>Début</th>
                  <th>Fin</th>
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
                    className={`cliquable${
                      execution.simulation_id === selection ? " selectionnee" : ""
                    }`}
                    onClick={() =>
                      setSelection(
                        execution.simulation_id === selection ? null : execution.simulation_id
                      )
                    }
                  >
                    <td>{dateCourte(execution.simulation_date_debut)}</td>
                    <td>{dateCourte(execution.simulation_date_fin)}</td>
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

      {fiche && (
        <section>
          <h2 className="screen-section-title">Fiche d'exécution</h2>
          <article className="fiche">
            <div className="fiche-tete">
              <div>
                <div className="fiche-titre">{fiche.execution.simulation_libelle}</div>
                <div className="fiche-identifiant">{fiche.execution.simulation_id}</div>
              </div>
              <StatutPastille statut={fiche.execution.simulation_statut} />
            </div>

            <div className="stat-strip">
              {Object.entries(fiche.volumetrie).map(([cle, nombre]) => (
                <div key={cle} className="stat-tile">
                  <span className="stat-tile-label">{LIBELLES_VOLUMETRIE[cle] ?? cle}</span>
                  <span className="stat-tile-value">{nombre}</span>
                </div>
              ))}
            </div>

            {Object.keys(fiche.anomalies_par_type).length > 0 && (
              <>
                <h3 className="screen-section-title" style={{ marginTop: 22 }}>
                  Anomalies par type
                </h3>
                <div className="screen-table-wrap">
                  <table className="screen-table">
                    <thead>
                      <tr>
                        <th>Type</th>
                        <th>Injections</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(fiche.anomalies_par_type).map(([code, nombre]) => (
                        <tr key={code}>
                          <td>{code}</td>
                          <td>{nombre}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            <h3 className="screen-section-title" style={{ marginTop: 22 }}>
              Paramètres du run
            </h3>
            <pre className="fiche-parametres">
              {JSON.stringify(fiche.execution.simulation_parametres, null, 2)}
            </pre>
          </article>
        </section>
      )}
    </div>
  );
}
