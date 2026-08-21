// Suivi des ententes préalables : issue des décisions et délais de traitement.
import type { KpiSnapshot } from "../types";
import { formatDelai } from "./format";

interface EntentesPanelProps {
  snapshot: KpiSnapshot | null;
}

// Les statuts remontés par le moteur sont des codes : le tableau leur donne un
// libellé lisible et une couleur qui traduit l'issue.
// Les trois valeurs viennent de simulation/passage.py : « validee_office »
// quand l'accord est automatique, sinon « acceptee » ou « refusee ».
const STATUTS: Record<string, { libelle: string; indicateur: string }> = {
  acceptee: { libelle: "Acceptées", indicateur: "indicator-normal" },
  validee_office: { libelle: "Validées d'office", indicateur: "indicator-blue" },
  refusee: { libelle: "Refusées", indicateur: "indicator-warning" },
};

export function EntentesPanel({ snapshot }: EntentesPanelProps) {
  const global = snapshot?.ententes.global ?? {};
  const lignes = Object.entries(global)
    .map(([statut, valeurs]) => ({
      statut,
      libelle: STATUTS[statut]?.libelle ?? statut,
      indicateur: STATUTS[statut]?.indicateur ?? "indicator-gray",
      ...valeurs,
    }))
    .sort((a, b) => b.nombre - a.nombre);

  const total = lignes.reduce((somme, ligne) => somme + ligne.nombre, 0);
  const delais = snapshot?.ententes.delai_moyen_secondes;

  return (
    <article className="chart-card">
      <div className="chart-card-header">
        <div>
          <h2 className="chart-title">Ententes Préalables</h2>
          <p className="chart-subtitle">
            {total > 0
              ? `${total.toLocaleString("fr-FR")} décisions sur les ${snapshot?.window.hours ?? 24} dernières heures`
              : "En attente des premières décisions"}
          </p>
        </div>
      </div>

      {lignes.length === 0 ? (
        <p className="chart-empty">Aucune entente traitée sur la fenêtre.</p>
      ) : (
        <div className="ententes-repartition">
          {lignes.map((ligne) => (
            <div className="ententes-ligne" key={ligne.statut}>
              <div className="ententes-ligne-entete">
                <span className={`status-indicator ${ligne.indicateur}`}>{ligne.libelle}</span>
                <span className="ententes-ligne-valeur">
                  {ligne.nombre.toLocaleString("fr-FR")} · {ligne.pourcentage}%
                </span>
              </div>
              <div className="ententes-jauge">
                <div
                  className={`ententes-jauge-remplissage jauge-${ligne.statut}`}
                  style={{ width: `${Math.min(ligne.pourcentage, 100)}%` }}
                />
              </div>
            </div>
          ))}

          <div className="ententes-delais">
            <div className="ententes-delai">
              <span className="card-label">Délai médecin conseil</span>
              <strong className="card-value">{formatDelai(delais?.medecin_conseil ?? null)}</strong>
            </div>
            <div className="ententes-delai">
              <span className="card-label">Délai validation d'office</span>
              <strong className="card-value">{formatDelai(delais?.validation_office ?? null)}</strong>
            </div>
          </div>
        </div>
      )}
    </article>
  );
}
