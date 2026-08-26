import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { RequireRole } from "../auth/RequireRole";
import { api } from "../services/api";
import type { RapportExecution, SimulationRun } from "../types";
import { dateCourte } from "./format-execution";
import { DownloadIcon, RefreshIcon, ReportsIcon, TrashIcon } from "./Icons";
import "./Screens.css";

/** L'heure seule : la journee est deja donnee par le titre de la section. */
function heureCourte(valeur: string): string {
  return new Date(valeur).toLocaleTimeString("fr-FR", {
    hour: "2-digit", minute: "2-digit",
  });
}

/** Date du jour au format attendu par un champ date. */
function aujourdhui(): string {
  return new Date().toISOString().slice(0, 10);
}

export function ReportsPage() {
  const { token } = useAuth();
  const [fichiers, setFichiers] = useState<string[]>([]);
  // Quel export travaille, plutôt qu'un simple « quelque chose tourne » : le
  // bouton pressé doit pouvoir le dire lui-même, et lui seul.
  const [travail, setTravail] = useState<"jour" | "periode" | "execution" | null>(null);
  const enCours = travail !== null;
  const [erreur, setErreur] = useState<string | null>(null);
  const [succes, setSucces] = useState<string | null>(null);

  // Export par période et par exécution : le rapport quotidien n'est plus le
  // seul découpage possible.
  const [dateMin, setDateMin] = useState(aujourdhui());
  const [dateMax, setDateMax] = useState(aujourdhui());
  const [executions, setExecutions] = useState<SimulationRun[]>([]);
  const [execution, setExecution] = useState("");
  const [confirmPurge, setConfirmPurge] = useState(false);
  const [purgeEnCours, setPurgeEnCours] = useState(false);
  // Les exécutions du jour choisi, avec leurs rapports. La date de début de
  // la période pilote cette section : une seule date à régler pour les deux.
  const [rapportsJour, setRapportsJour] = useState<RapportExecution[]>([]);

  /** Recharge la liste et la rend, pour pouvoir dire ce qui vient d'apparaître. */
  async function refresh(): Promise<string[]> {
    try {
      const liste = await api.listReports(token);
      setFichiers(liste);
      return liste;
    } catch (reason) {
      setErreur((reason as Error).message);
      return [];
    }
  }

  useEffect(() => {
    void refresh();
    void (async () => {
      try {
        const liste = await api.getExecutions(token, 50);
        setExecutions(liste);
        if (liste.length > 0) setExecution((actuelle) => actuelle || liste[0].simulation_id);
      } catch {
        // La liste des exécutions n'est pas indispensable pour télécharger.
      }
    })();
  }, [token]);

  /**
   * Mène un export et dit ce qu'il a produit.
   *
   * Le bouton se contentait de se griser : rien ne distinguait « ça travaille »
   * de « c'est planté », et une fois fini, rien ne disait quels fichiers
   * étaient apparus dans une liste qui en compte déjà des dizaines.
   */
  async function mener(
    quoi: "jour" | "periode" | "execution",
    action: () => Promise<unknown>,
  ) {
    setTravail(quoi);
    setErreur(null);
    setSucces(null);
    const avant = new Set(fichiers);
    try {
      await action();
      const apres = await refresh();
      const nouveaux = apres.filter((nom) => !avant.has(nom));
      setSucces(nouveaux.length > 0
        ? `Export terminé — ${nouveaux.length} fichier(s) : ${nouveaux.join(", ")}`
        : "Export terminé, mais aucun fichier nouveau : le périmètre choisi est peut-être vide.");
    } catch (reason) {
      setErreur((reason as Error).message);
    } finally {
      setTravail(null);
    }
  }

  /** Recharge la liste des exécutions du jour affiché. */
  const rafraichirJour = useCallback(async () => {
    try {
      setRapportsJour(await api.getRapportsExecutions(dateMin, token));
    } catch (reason) {
      setErreur((reason as Error).message);
    }
  }, [dateMin, token]);

  useEffect(() => {
    void rafraichirJour();
  }, [rafraichirJour]);

  /** Produit PDF et Excel pour une exécution, depuis sa propre ligne. */
  async function produirePour(simulationId: string) {
    await mener("execution", () => api.exporterExecution(simulationId, token));
    await rafraichirJour();
  }

  const exporterPeriode = () =>
    mener("periode", () => api.exporterPeriode(dateMin, dateMax, token));

  const exporterExecution = () => {
    if (!execution) return Promise.resolve();
    return mener("execution", () => api.exporterExecution(execution, token));
  };

  const handleGenerer = () => mener("jour", () => api.generateReport(token));

  async function viderRapports() {
    setPurgeEnCours(true);
    setErreur(null);
    try {
      const resultat = await api.viderRapports(token);
      setConfirmPurge(false);
      await refresh();
      if (resultat.supprimes === 0) {
        setErreur("Aucun fichier à supprimer.");
      }
    } catch (reason) {
      setErreur((reason as Error).message);
    } finally {
      setPurgeEnCours(false);
    }
  }

  function getFileTypeBadge(filename: string) {
    if (filename.endsWith(".pdf")) return { label: "PDF", class: "badge-pdf" };
    if (filename.endsWith(".xlsx") || filename.endsWith(".xls")) return { label: "EXCEL", class: "badge-excel" };
    if (filename.endsWith(".csv.zip") || filename.endsWith(".csv")) return { label: "CSV", class: "badge-csv" };
    if (filename.endsWith(".zip")) return { label: "ZIP", class: "badge-csv" };
    return { label: "FICHIER", class: "badge-gray" };
  }

  return (
    <main className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Rapports Quotidiens & Exports</h1>
          <p className="page-subtitle">
            Génération et téléchargement des synthèses d'activité et des audits techniques
          </p>
        </div>
        {/* Le libellé dit ce qui sort vraiment : un PDF *technique* sur le
            fonctionnement du serveur, et l'export des données du jour. Le
            précédent laissait croire à un rapport métier, et son PDF plein de
            zéros passait pour une panne du simulateur. */}
        <button className="btn btn-start" onClick={() => void handleGenerer()} disabled={enCours}>
          {travail === "jour"
            ? <span className="rouet" aria-hidden="true" />
            : <ReportsIcon size={16} />}
          <span>
            {travail === "jour"
              ? "Génération en cours…"
              : "Rapport technique + données du jour"}
          </span>
        </button>
      </div>

      {/* Le résultat de l'export se dit ici, sous le titre : la liste des
          fichiers en compte trop pour qu'on y repère le nouveau à l'œil. */}
      {succes && <div className="bandeau-succes">{succes}</div>}

      {erreur && (
        <div className="alert-box alert-error" role="alert">
          {erreur}
        </div>
      )}

      <div className="info-banner">
        <div className="info-banner-badge">NOTE</div>
        <div className="info-banner-text">
          <strong>Automatisation nocturne :</strong> Le rapport technique (PDF) et l'export tabulaire
          (Excel) sont générés automatiquement chaque nuit à 00h00 pour la journée écoulée. Vous pouvez
          déclencher une extraction immédiate à tout moment.
        </div>
      </div>

      <section style={{ marginBottom: 22 }}>
        <h2 className="screen-section-title">Export par période</h2>
        <div className="alea-carte">
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <label className="alea-code">Du</label>
            <input
              type="date"
              className="champ-console"
              style={{ width: 170 }}
              value={dateMin}
              onChange={(evenement) => setDateMin(evenement.target.value)}
            />
            <label className="alea-code">au</label>
            <input
              type="date"
              className="champ-console"
              style={{ width: 170 }}
              value={dateMax}
              onChange={(evenement) => setDateMax(evenement.target.value)}
            />
          </div>
          <button className="btn btn-start" onClick={() => void exporterPeriode()} disabled={enCours}>
            {travail === "periode" && <span className="rouet" aria-hidden="true" />}
            {travail === "periode" ? "Export en cours…" : "Exporter la période"}
          </button>
        </div>
      </section>

      {/* ── Rapports par exécution, sous leur nom ──
          Les fichiers portent un identifiant technique illisible. Ici on les
          présente sous le nom donné à la simulation au départ, groupés par
          journée — c'est le seul repère dont dispose l'opérateur. */}
      <section style={{ marginBottom: 22 }}>
        <h2 className="screen-section-title">
          Rapports par exécution
          <span className="rule" />
          <span className="bilan-total">
            {rapportsJour.length} exécution(s) le {dateCourte(`${dateMin}T00:00:00`)}
          </span>
        </h2>

        {rapportsJour.length === 0 ? (
          <div className="screen-empty">
            Aucune exécution lancée ce jour-là. Changez la date ci-dessus.
          </div>
        ) : (
          <div className="rapports-grille">
            <div className="rapports-entete">
              <span>Exécution</span>
              <span>Rapport PDF</span>
              <span>Données Excel</span>
            </div>

            {rapportsJour.map((fiche) => (
              <div className="rapports-ligne" key={fiche.simulation_id}>
                <div className="rapports-nom">
                  <strong>{fiche.simulation_libelle || "Sans nom"}</strong>
                  <span className="rapports-meta">
                    {heureCourte(fiche.simulation_date_debut)}
                    {" · "}{fiche.simulation_type ?? "sans type"}
                    {" · "}{fiche.passages_reussis} passage(s)
                  </span>
                </div>

                <div className="rapports-fichier">
                  {fiche.fichiers.pdf ? (
                    <button
                      className="btn btn-download"
                      onClick={() => api.downloadReport(fiche.fichiers.pdf as string, token)}
                    >
                      <DownloadIcon size={14} />
                      Télécharger
                    </button>
                  ) : (
                    <span className="rapports-absent">pas encore produit</span>
                  )}
                </div>

                <div className="rapports-fichier">
                  {fiche.fichiers.excel ? (
                    <button
                      className="btn btn-download"
                      onClick={() => api.downloadReport(fiche.fichiers.excel as string, token)}
                    >
                      <DownloadIcon size={14} />
                      Télécharger
                    </button>
                  ) : (
                    <span className="rapports-absent">pas encore produit</span>
                  )}
                </div>

                {/* Une exécution sans rapport n'est pas une impasse : on le
                    produit d'ici, sans repasser par une liste déroulante. */}
                {!fiche.fichiers.pdf && !fiche.fichiers.excel && (
                  <div className="rapports-produire">
                    <button
                      className="btn btn-outline"
                      disabled={enCours}
                      onClick={() => void produirePour(fiche.simulation_id)}
                    >
                      {travail === "execution" ? "Production…" : "Produire les rapports"}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section style={{ marginBottom: 22 }}>
        <h2 className="screen-section-title">Export d'une exécution</h2>
        <div className="alea-carte">
          <select
            className="champ-console"
            style={{ maxWidth: 420 }}
            value={execution}
            onChange={(evenement) => setExecution(evenement.target.value)}
          >
            {executions.length === 0 && <option value="">Aucune exécution enregistrée</option>}
            {/* Le nom donné à l'exécution et son volume, pas seulement sa date :
                trois exécutions du même jour s'affichaient à l'identique, et
                l'on exportait sans savoir laquelle — ni si elle contenait
                deux lignes ou deux mille. */}
            {executions.map((ligne) => (
              <option key={ligne.simulation_id} value={ligne.simulation_id}>
                {dateCourte(ligne.simulation_date_debut)}
                {" · "}{ligne.simulation_libelle || ligne.simulation_type || "sans nom"}
                {" · "}{ligne.passages_reussis} passage(s)
              </option>
            ))}
          </select>
          <button
            className="btn btn-start"
            onClick={() => void exporterExecution()}
            disabled={enCours || !execution}
          >
            {travail === "execution" && <span className="rouet" aria-hidden="true" />}
            {travail === "execution" ? "Export en cours…" : "Exporter (PDF + Excel)"}
          </button>
        </div>
      </section>

      <div className="reports-card">
        <div className="reports-card-header">
          <h2>Fichiers disponibles ({fichiers.length})</h2>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button className="btn-icon-refresh" onClick={refresh} title="Actualiser la liste">
              <RefreshIcon size={14} />
            </button>
            <RequireRole minimum="administrateur">
              {fichiers.length > 0 && (
                <button
                  className="btn btn-danger-outline"
                  onClick={() => setConfirmPurge(true)}
                  disabled={purgeEnCours}
                  title="Supprimer tous les rapports générés"
                >
                  <TrashIcon size={14} />
                  <span>Vider</span>
                </button>
              )}
            </RequireRole>
          </div>
        </div>

        {confirmPurge && (
          <div className="confirm-banner confirm-danger">
            <span>
              Supprimer les <strong>{fichiers.length}</strong> fichier(s) ?
              Cette action est irréversible.
            </span>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                className="btn btn-outline"
                onClick={() => setConfirmPurge(false)}
                disabled={purgeEnCours}
              >
                Annuler
              </button>
              <button
                className="btn btn-danger"
                onClick={() => void viderRapports()}
                disabled={purgeEnCours}
              >
                {purgeEnCours ? "Suppression…" : "Confirmer la suppression"}
              </button>
            </div>
          </div>
        )}

        {fichiers.length === 0 ? (
          <div className="empty-reports">
            <ReportsIcon size={36} className="empty-icon-svg" />
            <p>Aucun rapport généré pour le moment.</p>
            <span className="empty-subtext">Cliquez sur « Générer les rapports du jour » pour créer un premier export.</span>
          </div>
        ) : (
          <ul className="reports-list-clean">
            {fichiers.map((nom) => {
              const badge = getFileTypeBadge(nom);
              return (
                <li className="report-item" key={nom}>
                  <div className="report-item-left">
                    <div className={`report-icon-box ${nom.endsWith(".pdf") ? "icon-box-pdf" : "icon-box-excel"}`}>
                      <ReportsIcon size={18} />
                    </div>
                    <div className="report-file-info">
                      <strong className="report-file-name">{nom}</strong>
                      <span className="report-file-meta">Prêt pour téléchargement</span>
                    </div>
                  </div>
                  <div className="report-item-right">
                    <span className={`file-type-pill ${badge.class}`}>{badge.label}</span>
                    <button
                      className="btn btn-download"
                      onClick={() => api.downloadReport(nom, token)}
                    >
                      <DownloadIcon size={14} />
                      Télécharger
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </main>
  );
}