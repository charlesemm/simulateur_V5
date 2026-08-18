import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { api } from "../services/api";

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

  return (
    <div className="reports-page">
      <div className="reports-header">
        <h2>Rapports quotidiens</h2>
        <button onClick={handleGenerer} disabled={enCours}>
          {enCours ? "Génération..." : "Générer maintenant"}
        </button>
      </div>

      {erreur && <p className="login-error">{erreur}</p>}

      <p className="reports-note">
        Le rapport technique (PDF) et l'export des données (Excel) sont
        générés automatiquement chaque nuit à minuit pour la journée
        précédente. Le bouton ci-dessus permet d'en déclencher un pour
        aujourd'hui, sans attendre.
      </p>

      <ul className="reports-list">
        {fichiers.map((nom) => (
          <li key={nom}>
            <span>{nom}</span>
            <button onClick={() => api.downloadReport(nom, token)}>Télécharger</button>
          </li>
        ))}
        {fichiers.length === 0 && (
          <li className="reports-empty">Aucun rapport généré pour le moment.</li>
        )}
      </ul>
    </div>
  );
}