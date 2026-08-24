import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { RequireRole } from "../auth/RequireRole";
import { api } from "../services/api";
import type { SimulationRun } from "../types";
import { dateCourte } from "./format-execution";
import { DownloadIcon, RefreshIcon, ReportsIcon, TrashIcon } from "./Icons";
import "./Screens.css";

/** Date du jour au format attendu par un champ date. */
function aujourdhui(): string {
  return new Date().toISOString().slice(0, 10);
}

export function ReportsPage() {
  const { token } = useAuth();
  const [fichiers, setFichiers] = useState<string[]>([]);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  // Export par période et par exécution : le rapport quotidien n'est plus le
  // seul découpage possible.
  const [dateMin, setDateMin] = useState(aujourdhui());
  const [dateMax, setDateMax] = useState(aujourdhui());
  const [executions, setExecutions] = useState<SimulationRun[]>([]);
  const [execution, setExecution] = useState("");
  const [confirmPurge, setConfirmPurge] = useState(false);
  const [purgeEnCours, setPurgeEnCours] = useState(false);

  async function refresh() {
    try {
      setFichiers(await api.listReports(token));
    } catch (reason) {
      setErreur((reason as Error).message);
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

  async function exporterPeriode() {
    setEnCours(true);
    setErreur(null);
    try {
      await api.exporterPeriode(dateMin, dateMax, token);
      await refresh();
    } catch (reason) {
      setErreur((reason as Error).message);
    } finally {
      setEnCours(false);
    }
  }

  async function exporterExecution() {
    if (!execution) return;
    setEnCours(true);
    setErreur(null);
    try {
      await api.exporterExecution(execution, token);
      await refresh();
    } catch (reason) {
      setErreur((reason as Error).message);
    } finally {
      setEnCours(false);
    }
  }

  async function handleGenerer() {
    setEnCours(true);
    setErreur(null);
    try {
      await api.generateReport(token);
      await refresh();
    } catch (reason) {
      setErreur((reason as Error).message);
    } finally {
      setEnCours(false);
    }
  }

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
        <button className="btn btn-start" onClick={handleGenerer} disabled={enCours}>
          <ReportsIcon size={16} />
          <span>{enCours ? "Génération en cours..." : "Générer les rapports du jour"}</span>
        </button>
      </div>

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
          <button className="btn btn-start" onClick={exporterPeriode} disabled={enCours}>
            Exporter la période
          </button>
        </div>
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
            {executions.map((ligne) => (
              <option key={ligne.simulation_id} value={ligne.simulation_id}>
                {dateCourte(ligne.simulation_date_debut)} · {ligne.simulation_type ?? "sans type"}
              </option>
            ))}
          </select>
          <button
            className="btn btn-start"
            onClick={exporterExecution}
            disabled={enCours || !execution}
          >
            Exporter (PDF + Excel)
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