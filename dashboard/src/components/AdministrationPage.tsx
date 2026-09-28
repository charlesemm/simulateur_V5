// dashboard/src/components/AdministrationPage.tsx
import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../hooks/useToast";
import { api } from "../services/api";
import type { FicheGouvernance, SimulationRun } from "../types";
import { UsersPage } from "./UsersPage";
import { StatutPastille, dateCourte } from "./format-execution";
import "./Screens.css";

type Volet = "comptes" | "volumetrie" | "purge";

const VOLETS: Array<[Volet, string]> = [
  ["comptes", "Comptes"],
  ["volumetrie", "Volumétrie"],
  ["purge", "Purge des données"],
];

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
  const { toast } = useToast();
  const [volet, setVolet] = useState<Volet>("comptes");
  // Volets déjà chargés une fois : avant, une liste vide n'est pas « rien ».
  const [charges, setCharges] = useState<Set<Volet>>(new Set());
  const ongletsRef = useRef<Array<HTMLButtonElement | null>>([]);
  const apercuRef = useRef<HTMLElement>(null);
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
    } finally {
      setCharges((precedents) => new Set(precedents).add(volet));
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
      // L'aperçu s'ouvre sous une liste de cinquante lignes : on l'amène
      // sous les yeux, sans quoi « Examiner » semblait ne rien faire.
      requestAnimationFrame(() => {
        const sansAnimation = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        apercuRef.current?.scrollIntoView({ behavior: sansAnimation ? "auto" : "smooth", block: "start" });
      });
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
      toast("succes", "Purge effectuée", `${supprimees.total} ligne(s) supprimée(s)`);
      setApercu(null);
      setCible(null);
      setConfirmation(false);
      await charger();
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
      toast("erreur", "Purge impossible", (raison as Error).message);
    } finally {
      setOccupe(false);
    }
  }

  /** Flèches, Début et Fin déplacent d'un onglet à l'autre, comme attendu. */
  function surToucheOnglet(evenement: KeyboardEvent<HTMLButtonElement>, rang: number) {
    const cibles: Record<string, number> = {
      ArrowRight: (rang + 1) % VOLETS.length,
      ArrowLeft: (rang - 1 + VOLETS.length) % VOLETS.length,
      Home: 0,
      End: VOLETS.length - 1,
    };
    const suivant = cibles[evenement.key];
    if (suivant === undefined) return;
    evenement.preventDefault();
    setVolet(VOLETS[suivant][0]);
    ongletsRef.current[suivant]?.focus();
  }

  const totalLignes = tables.reduce((somme, fiche) => somme + fiche.lignes, 0);

  return (
    <div className="screen">
      {erreur && <p className="screen-error" role="alert">{erreur}</p>}
      {message && <div className="bandeau-info" role="status">{message}</div>}

      <div className="onglets" role="tablist" aria-label="Volets de l'administration">
        {VOLETS.map(([code, libelle], rang) => (
          <button
            key={code}
            ref={(element) => { ongletsRef.current[rang] = element; }}
            type="button"
            role="tab"
            id={`onglet-${code}`}
            aria-selected={volet === code}
            aria-controls={`panneau-${code}`}
            tabIndex={volet === code ? 0 : -1}
            className={`onglet${volet === code ? " actif" : ""}`}
            onClick={() => setVolet(code)}
            onKeyDown={(evenement) => surToucheOnglet(evenement, rang)}
          >
            {libelle}
          </button>
        ))}
      </div>

      {volet === "comptes" && (
        <div role="tabpanel" id="panneau-comptes" aria-labelledby="onglet-comptes" className="onglet-panneau">
          <UsersPage />
        </div>
      )}

      {volet === "volumetrie" && (
        <section role="tabpanel" id="panneau-volumetrie" aria-labelledby="onglet-volumetrie" className="onglet-panneau">
          <div className="stat-strip">
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
                  <th className="num">Lignes</th>
                </tr>
              </thead>
              <tbody>
                {!charges.has("volumetrie") && (
                  <tr>
                    <td colSpan={6} aria-busy="true">
                      <span className="ui-skeleton ui-skeleton--texte" style={{ width: "60%" }} />
                    </td>
                  </tr>
                )}
                {tables.map((fiche) => (
                  <tr key={fiche.table}>
                    <td>{fiche.table}</td>
                    <td>{fiche.domaine}</td>
                    <td>{fiche.proprietaire}</td>
                    <td>{fiche.criticite}</td>
                    <td>{fiche.donnees_personnelles ? "oui" : "non"}</td>
                    <td className="num">{fiche.lignes.toLocaleString("fr-FR")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {volet === "purge" && (
        <section role="tabpanel" id="panneau-purge" aria-labelledby="onglet-purge" className="onglet-panneau">
          <div className="bandeau-info bandeau-alerte">
            ÉCHO conserve toutes les lignes de chaque exécution. La purge est la
            seule sortie — elle est définitive et ne concerne que l'exécution
            choisie.
          </div>

          <div className="screen-table-wrap">
            <table className="screen-table">
              <thead>
                <tr>
                  <th>Début</th>
                  <th>Type</th>
                  <th>Statut</th>
                  <th className="num">Réussis</th>
                  <th><span className="ui-sr-only">Action</span></th>
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
                    <td className="num">{execution.passages_reussis}</td>
                    <td>
                      <button
                        className="btn btn-outline"
                        onClick={() => void previsualiser(execution.simulation_id)}
                        disabled={occupe}
                        aria-label={`Examiner l'exécution du ${dateCourte(execution.simulation_date_debut)}`}
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
            <article className="fiche fiche--ouverte" ref={apercuRef}>
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
                <p className="fiche-note">
                  Cette exécution n'a laissé aucune donnée : il n'y a rien à purger.
                </p>
              ) : (
                <div className="purge-confirmation">
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
                    aria-busy={occupe}
                  >
                    {occupe && (
                      <span className="ui-spinner ui-spinner--petit ui-spinner--inverse" aria-hidden="true" />
                    )}
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
