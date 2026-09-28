// dashboard/src/components/QualitePage.tsx
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { api } from "../services/api";
import type { PaireMdm, RapportQualite, SimulationRun } from "../types";
import { dateCourte } from "./format-execution";
import "./Screens.css";

/**
 * Ce qui a été semé et que les règles n'ont pas vu.
 *
 * L'écran donnait trois colonnes de chiffres et laissait faire la soustraction
 * de tête, type par type. Or c'est l'écart qui intéresse : le reste n'est là
 * que pour l'expliquer.
 *
 * Les seuils portent un jugement mesuré, à dessein. Un écart n'est pas
 * forcément un défaut — une date antidatée de moins d'une semaine échappe
 * légitimement à sa règle — donc seul un écart majoritaire s'affiche en rouge.
 */
function ecartDeLigne(injectees: number, detectees: number): {
  niveau: "aucun" | "leger" | "notable" | "fort" | "inconnu";
  libelle: string;
} {
  if (injectees === 0) return { niveau: "inconnu", libelle: "—" };

  const manquantes = injectees - detectees;
  if (manquantes <= 0) return { niveau: "aucun", libelle: "aucun" };

  const part = manquantes / injectees;
  const libelle = `−${manquantes}`;

  if (part <= 0.1) return { niveau: "leger", libelle };
  if (part <= 0.5) return { niveau: "notable", libelle };
  return { niveau: "fort", libelle };
}

/**
 * W4 — Qualité.
 *
 * Deux confrontations que seul un simulateur peut produire : ce qui a été
 * demandé contre ce qui a été injecté, et ce qui a été injecté contre ce qui a
 * été détecté. Sur des données réelles, la seconde colonne n'existe pas.
 */
export function QualitePage() {
  const { token } = useAuth();
  const [executions, setExecutions] = useState<SimulationRun[]>([]);
  const [selection, setSelection] = useState<string>("");
  const [rapport, setRapport] = useState<RapportQualite | null>(null);
  const [paires, setPaires] = useState<PaireMdm[]>([]);
  const [erreur, setErreur] = useState<string | null>(null);
  const [chargement, setChargement] = useState(false);

  useEffect(() => {
    let annule = false;
    async function charger() {
      try {
        const liste = await api.getExecutions(token, 50);
        if (!annule) {
          setExecutions(liste);
          if (liste.length > 0) setSelection((actuelle) => actuelle || liste[0].simulation_id);
        }
      } catch (raison) {
        if (!annule) setErreur((raison as Error).message);
      }
    }
    void charger();
    return () => {
      annule = true;
    };
  }, [token]);

  const analyser = useCallback(async () => {
    setChargement(true);
    try {
      const [resultat, verite] = await Promise.all([
        api.getRapportQualite(token, selection || null),
        api.getVeriteTerrain(token, selection || null),
      ]);
      setRapport(resultat);
      setPaires(verite);
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    } finally {
      setChargement(false);
    }
  }, [token, selection]);

  useEffect(() => {
    void analyser();
  }, [analyser]);

  const doublonsReels = paires.filter((paire) => paire.meme_personne).length;
  // Première analyse : rien encore à montrer, on dessine la forme qui vient.
  const premierChargement = chargement && rapport === null;

  return (
    <div className="screen">
      {erreur && <p className="screen-error" role="alert">{erreur}</p>}

      <section>
        <h2 className="screen-section-title">Périmètre analysé</h2>
        <div className="alea-carte">
          <label className="champ-groupe">
          <span className="champ-libelle">Exécution à analyser</span>
          <select
            className="champ-console"
            value={selection}
            onChange={(evenement) => setSelection(evenement.target.value)}
          >
            <option value="">Toutes les données en base</option>
            {executions.map((execution) => (
              <option key={execution.simulation_id} value={execution.simulation_id}>
                {dateCourte(execution.simulation_date_debut)} ·{" "}
                {execution.simulation_type ?? "sans type"}
              </option>
            ))}
          </select>
          </label>
          <button
            className="btn btn-start"
            onClick={() => void analyser()}
            disabled={chargement}
            aria-busy={chargement}
          >
            {chargement && (
              <span className="ui-spinner ui-spinner--petit ui-spinner--inverse" aria-hidden="true" />
            )}
            {chargement ? "Analyse…" : "Analyser"}
          </button>
        </div>
      </section>

      {premierChargement && (
        <section aria-busy="true" aria-label="Analyse en cours">
          <h2 className="screen-section-title">Constats par dimension</h2>
          <div className="stat-strip">
            {[0, 1, 2, 3].map((tuile) => (
              <span key={tuile} className="ui-skeleton" style={{ height: 128 }} />
            ))}
          </div>
        </section>
      )}

      {rapport && (
        <div className={`resultat-qualite${chargement ? " en-recalcul" : ""}`} aria-busy={chargement}>
          <section>
            <h2 className="screen-section-title">Constats par dimension</h2>
            <div className="stat-strip">
              {Object.entries(rapport.par_dimension).map(([dimension, nombre]) => (
                <div key={dimension} className="stat-tile">
                  <span className="stat-tile-label">{dimension}</span>
                  <span className="stat-tile-value">{nombre}</span>
                </div>
              ))}
              <div className="stat-tile">
                <span className="stat-tile-label">Total</span>
                <span className="stat-tile-value">{rapport.total_constats}</span>
                <span className="stat-tile-hint">
                  Analysé le {dateCourte(rapport.genere_le)}
                </span>
              </div>
            </div>
          </section>

          <section>
            <h2 className="screen-section-title">Demandé, injecté, détecté</h2>
            {rapport.confrontation.length === 0 ? (
              <div className="screen-empty">
                Aucune anomalie sur ce périmètre : rien à confronter.
              </div>
            ) : (
              <div className="screen-table-wrap">
                <table className="screen-table">
                  <thead>
                    <tr>
                      <th>Type d'anomalie</th>
                      <th className="num">Taux demandé</th>
                      <th className="num">Injectées</th>
                      <th className="num">Détectées</th>
                      <th className="num">Écart</th>
                      <th className="num">Taux de détection</th>
                      <th>Règles</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rapport.confrontation.map((ligne) => {
                      const ecart = ecartDeLigne(ligne.injectees, ligne.detectees);
                      return (
                      <tr key={ligne.anomalie_code}>
                        <td>{ligne.anomalie_code}</td>
                        <td className="num">{ligne.taux_demande_pourcent} %</td>
                        <td className="num">{ligne.injectees}</td>
                        <td className="num">{ligne.detectees}</td>
                        <td className="num">
                          <span className={`ecart ecart--${ecart.niveau}`}>
                            {ecart.libelle}
                          </span>
                        </td>
                        <td className="num">
                          {ligne.taux_detection_pourcent === null
                            ? "—"
                            : `${ligne.taux_detection_pourcent} %`}
                        </td>
                        <td>{ligne.regles.join(", ") || "—"}</td>
                      </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            <p className="fiche-note">
              Un taux de détection inférieur à 100 % n'est pas forcément un défaut :
              une date antidatée de moins d'une semaine échappe à sa règle par
              construction, pour ne pas confondre avec l'aléa d'horloge décalée.
            </p>
          </section>

          <section>
            <h2 className="screen-section-title">Règles appliquées</h2>
            <div className="screen-table-wrap">
              <table className="screen-table">
                <thead>
                  <tr>
                    <th>Règle</th>
                    <th>Dimension</th>
                    <th className="num">Constats</th>
                    <th>Exemple</th>
                  </tr>
                </thead>
                <tbody>
                  {rapport.regles.map((regle) => (
                    <tr key={regle.code}>
                      <td>
                        {regle.libelle}
                        {regle.referentielle && (
                          <span className="alea-code">référentiel</span>
                        )}
                      </td>
                      <td>{regle.dimension}</td>
                      <td className="num">{regle.constats}</td>
                      <td>
                        {regle.exemples.length === 0
                          ? "—"
                          : `${regle.exemples[0].cle} → ${regle.exemples[0].valeur}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}

      <section>
        <div className="screen-section-head">
          <h2 className="screen-section-title">Vérité terrain du rapprochement</h2>
          {paires.length > 25 && (
            <span className="screen-section-compte">
              25 premières paires sur {paires.length}
            </span>
          )}
        </div>
        {paires.length === 0 ? (
          <div className="screen-empty">
            Aucune identité jumelle sur ce périmètre. Lancez une simulation de
            type MDM pour en fabriquer.
          </div>
        ) : (
          <>
            <div className="stat-strip">
              <div className="stat-tile">
                <span className="stat-tile-label">Paires fabriquées</span>
                <span className="stat-tile-value">{paires.length}</span>
              </div>
              <div className="stat-tile">
                <span className="stat-tile-label">Vrais doublons</span>
                <span className="stat-tile-value">{doublonsReels}</span>
              </div>
              <div className="stat-tile">
                <span className="stat-tile-label">Leurres</span>
                <span className="stat-tile-value">{paires.length - doublonsReels}</span>
                <span className="stat-tile-hint">Homonymes à ne pas rapprocher</span>
              </div>
            </div>
            <div className="screen-table-wrap bloc-suite">
              <table className="screen-table">
                <thead>
                  <tr>
                    <th>Variation</th>
                    <th>Même personne</th>
                    <th>Commentaire</th>
                  </tr>
                </thead>
                <tbody>
                  {paires.slice(0, 25).map((paire) => (
                    <tr key={paire.paire_id}>
                      <td>{paire.type_variation}</td>
                      <td>
                        {/* « Non » n'est pas une erreur : c'est un leurre voulu,
                            un homonyme à ne pas rapprocher. Neutre, pas rouge. */}
                        <span
                          className={`pastille${paire.meme_personne ? " pastille-en_cours" : ""}`}
                        >
                          {paire.meme_personne ? "oui" : "non"}
                        </span>
                      </td>
                      <td>{paire.commentaire ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
