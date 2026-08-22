// dashboard/src/components/AdministrationPage.tsx
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { api } from "../services/api";
import type { FicheGouvernance, SimulationRun } from "../types";
import { UsersPage } from "./UsersPage";
import { StatutPastille, dateCourte } from "./format-execution";
import "./Screens.css";

type Volet = "comptes" | "volumetrie" | "purge";

/**
 * W8 — Administration.
 *
 * Les comptes, l'inventaire des tables avec leur propriétaire, et la purge —
 * seule sortie d'un simulateur qui conserve par principe toutes les lignes
 * qu'il produit. La purge demande une confirmation explicite : elle est
 * irréversible et ne prévient qu'une fois.
 */
export function AdministrationPage() {
  const { token } = useAuth();
  const [volet, setVolet] = useState<Volet>("comptes");
  const [erreur, setErreur] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [tables, setTables] = useState<FicheGouvernance[]>([]);
  const [executions, setExecutions] = useState<SimulationRun[]>([]);
  const [cible, setCible] = useState<string | null>(null);
  const [apercu, setApercu] = useState<Record<string, number> | null>(null);
  const [confirmation, setConfirmation] = useState(false);
  const [occupe, setOccupe] = useState(false);

  const charger = useCallback(async () => {
    try {
      if (volet === "volumetrie") setTables(await api.getVolumetrie(token));
      if (volet === "purge") setExecutions(await api.getExecutions(token, 50));
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    }
  }, [token, volet]);

  useEffect(() => {
    void charger();
  }, [charger]);

  async function previsualiser(simulationId: string) {
    setCible(simulationId);
    setConfirmation(false);
    setMessage(null);
    try {
      setApercu(await api.previsualiserPurge(simulationId, token));
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    }
  }

  async function purger() {
    if (!cible) return;
    setOccupe(true);
    try {
      const supprimees = await api.purgerExecution(cible, token);
      setMessage(`${supprimees.total} ligne(s) supprimée(s). L'exécution reste dans l'historique.`);
      setApercu(null);
      setCible(null);
      setConfirmation(false);
      await charger();
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    } finally {
      setOccupe(false);
    }
  }

  const totalLignes = tables.reduce((somme, fiche) => somme + fiche.lignes, 0);

  return (
    <div className="screen">
      {erreur && <p className="screen-error">{erreur}</p>}
      {message && <div className="bandeau-info">{message}</div>}

      <section>
        <div className="onglets">
          {([
            ["comptes", "Comptes"],
            ["volumetrie", "Volumétrie"],
            ["purge", "Purge des données"],
          ] as Array<[Volet, string]>).map(([code, libelle]) => (
            <button
              key={code}
              className={`onglet${volet === code ? " actif" : ""}`}
              onClick={() => setVolet(code)}
            >
              {libelle}
            </button>
          ))}
        </div>
      </section>

      {volet === "comptes" && <UsersPage />}

      {volet === "volumetrie" && (
        <section>
          <div className="stat-strip" style={{ marginBottom: 14 }}>
            <div className="stat-tile">
              <span className="stat-tile-label">Tables au catalogue</span>
              <span className="stat-tile-value">{tables.length}</span>
            </div>
            <div className="stat-tile">
              <span className="stat-tile-label">Lignes en base</span>
              <span className="stat-tile-value">{totalLignes.toLocaleString("fr-FR")}</span>
              <span className="stat-tile-hint">Sur les tables déclarées</span>
            </div>
          </div>

          <div className="screen-table-wrap">
            <table className="screen-table">
              <thead>
                <tr>
                  <th>Table</th>
                  <th>Domaine</th>
                  <th>Propriétaire</th>
                  <th>Criticité</th>
                  <th>Données personnelles</th>
                  <th>Lignes</th>
                </tr>
              </thead>
              <tbody>
                {tables.map((fiche) => (
                  <tr key={fiche.table}>
                    <td>{fiche.table}</td>
                    <td>{fiche.domaine}</td>
                    <td>{fiche.proprietaire}</td>
                    <td>{fiche.criticite}</td>
                    <td>{fiche.donnees_personnelles ? "oui" : "non"}</td>
                    <td>{fiche.lignes.toLocaleString("fr-FR")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {volet === "purge" && (
        <section>
          <div className="bandeau-info bandeau-alerte">
            ÉCHO conserve toutes les lignes de chaque exécution. La purge est la
            seule sortie — elle est définitive et ne concerne que l'exécution
            choisie.
          </div>

          <div className="screen-table-wrap" style={{ marginTop: 14 }}>
            <table className="screen-table">
              <thead>
                <tr>
                  <th>Début</th>
                  <th>Type</th>
                  <th>Statut</th>
                  <th>Réussis</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {executions.map((execution) => (
                  <tr
                    key={execution.simulation_id}
                    className={execution.simulation_id === cible ? "selectionnee" : ""}
                  >
                    <td>{dateCourte(execution.simulation_date_debut)}</td>
                    <td>{execution.simulation_type ?? "—"}</td>
                    <td><StatutPastille statut={execution.simulation_statut} /></td>
                    <td>{execution.passages_reussis}</td>
                    <td>
                      <button
                        className="btn btn-outline"
                        onClick={() => void previsualiser(execution.simulation_id)}
                        disabled={occupe}
                      >
                        Examiner
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {apercu && cible && (
            <article className="fiche" style={{ marginTop: 18 }}>
              <div className="fiche-tete">
                <div>
                  <div className="fiche-titre">Ce que la purge supprimerait</div>
                  <div className="fiche-identifiant">{cible}</div>
                </div>
              </div>

              <div className="stat-strip">
                {Object.entries(apercu)
                  .filter(([, nombre]) => nombre > 0)
                  .map(([nom, nombre]) => (
                    <div key={nom} className="stat-tile">
                      <span className="stat-tile-label">{nom.replace(/_/g, " ")}</span>
                      <span className="stat-tile-value">{nombre}</span>
                    </div>
                  ))}
              </div>

              {Object.values(apercu).every((nombre) => nombre === 0) ? (
                <p className="stat-tile-hint" style={{ marginTop: 14 }}>
                  Cette exécution n'a laissé aucune donnée : il n'y a rien à purger.
                </p>
              ) : (
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 18 }}>
                  <label className="toggle-switch-label">
                    <input
                      type="checkbox"
                      className="toggle-checkbox"
                      checked={confirmation}
                      onChange={(evenement) => setConfirmation(evenement.target.checked)}
                    />
                    <span className="toggle-label-text">
                      Je confirme la suppression définitive de ces lignes
                    </span>
                  </label>
                  <button
                    className="btn btn-outline-danger"
                    disabled={!confirmation || occupe}
                    onClick={() => void purger()}
                  >
                    {occupe ? "Purge…" : "Purger"}
                  </button>
                </div>
              )}
            </article>
          )}
        </section>
      )}
    </div>
  );
}
