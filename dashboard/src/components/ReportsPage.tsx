import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { api } from "../services/api";
import { DownloadIcon, RefreshIcon, ReportsIcon } from "./Icons";

export function ReportsPage() {
  const { token } = useAuth();
  const [fichiers, setFichiers] = useState<string[]>([]);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  async function refresh() {
    try {
      setFichiers(await api.listReports(token));
    } catch (reason) {
      setErreur((reason as Error).message);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

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

      <div className="reports-card">
        <div className="reports-card-header">
          <h2>Fichiers disponibles ({fichiers.length})</h2>
          <button className="btn-icon-refresh" onClick={refresh} title="Actualiser la liste">
            <RefreshIcon size={14} />
          </button>
        </div>

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