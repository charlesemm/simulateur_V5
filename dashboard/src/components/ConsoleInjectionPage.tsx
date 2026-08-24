// dashboard/src/components/ConsoleInjectionPage.tsx
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { API_URL, api } from "../services/api";
import type { InjectionJournal, SimulationStatus, TypeAnomalie } from "../types";
import "./Screens.css";

const DECLENCHEMENTS: Array<{ valeur: string; libelle: string }> = [
  { valeur: "continu", libelle: "Continu — toute l'exécution" },
  { valeur: "demarrage", libelle: "Démarrage — une salve initiale" },
  { valeur: "differe", libelle: "Différé — après un délai" },
  { valeur: "manuel", libelle: "Manuel — sur ordre en cours de route" },
];

interface ReglageGlobal {
  enabled: boolean;
  rate: number;
  severity: string;
  injected_count: number;
}

/**
 * W2 — Console d'injection.
 *
 * Un bouton par type d'anomalie, à la couleur de sa famille : on compose son
 * jeu avant de lancer, on choisit quand chaque type entre en scène, et on peut
 * armer un type manuel ou déclencher un aléa pendant que le moteur tourne.
 */
export function ConsoleInjectionPage() {
  const { token } = useAuth();
  const [global, setGlobal] = useState<ReglageGlobal | null>(null);
  const [catalogue, setCatalogue] = useState<TypeAnomalie[]>([]);
  const [journal, setJournal] = useState<InjectionJournal[]>([]);
  const [statut, setStatut] = useState<SimulationStatus | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [occupe, setOccupe] = useState(false);

  const chargerGlobal = useCallback(async () => {
    const reponse = await fetch(`${API_URL}/anomalies`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!reponse.ok) throw new Error(`Réglage global indisponible (${reponse.status}).`);
    setGlobal((await reponse.json()) as ReglageGlobal);
  }, [token]);

  const rafraichir = useCallback(async () => {
    try {
      const [liste, etat, injections] = await Promise.all([
        api.getCatalogue(token),
        api.getSimulationStatus(token),
        api.getJournalAnomalies(token, null, 20),
      ]);
      setCatalogue(liste);
      setStatut(etat);
      setJournal(injections);
      await chargerGlobal();
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    }
  }, [token, chargerGlobal]);

  useEffect(() => {
    void rafraichir();
    const minuterie = setInterval(() => void rafraichir(), 4000);
    return () => clearInterval(minuterie);
  }, [rafraichir]);

  async function modifierGlobal(modification: Partial<ReglageGlobal>) {
    setOccupe(true);
    try {
      const reponse = await fetch(`${API_URL}/anomalies`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(modification),
      });
      if (!reponse.ok) throw new Error(`Modification refusée (${reponse.status}).`);
      setGlobal((await reponse.json()) as ReglageGlobal);
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    } finally {
      setOccupe(false);
    }
  }

  async function modifierType(
    code: string,
    reglage: Partial<{ active: boolean; taux: number; declenchement: string; delai_secondes: number }>
  ) {
    setOccupe(true);
    try {
      const modifie = await api.modifierTypeAnomalie(code, reglage, token);
      setCatalogue((liste) =>
        liste.map((type) => (type.anomalie_code === code ? modifie : type))
      );
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    } finally {
      setOccupe(false);
    }
  }

  async function commander(ordre: string, cible: string) {
    setOccupe(true);
    setMessage(null);
    try {
      const reponse = await api.commander(ordre, cible, token);
      setMessage(reponse.message);
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    } finally {
      setOccupe(false);
    }
  }

  const enCours = statut?.etat === "en_cours";
  const globalCoupe = !global?.enabled;

  return (
    <div className="screen">
      {erreur && <p className="screen-error">{erreur}</p>}
      {message && <div className="bandeau-info">{message}</div>}

      {!enCours && (
        <div className="bandeau-info">
          Le moteur est arrêté : les réglages ci-dessous s'appliqueront à la
          prochaine exécution. Armer un type manuel ou déclencher un aléa
          demande un moteur en marche.
        </div>
      )}

      <section>
        <h2 className="screen-section-title">Interrupteur général</h2>
        <div className="stat-strip">
          <div className="stat-tile">
            <span className="stat-tile-label">Injection</span>
            <span className="stat-tile-value">{global?.enabled ? "Ouverte" : "Coupée"}</span>
            <label className="toggle-switch-label" style={{ marginTop: 10 }}>
              <input
                type="checkbox"
                className="toggle-checkbox"
                checked={global?.enabled ?? false}
                disabled={occupe || global === null}
                onChange={(evenement) =>
                  void modifierGlobal({ enabled: evenement.target.checked })
                }
              />
              <span className="toggle-label-text">Autoriser l'injection</span>
            </label>
          </div>
          <div className="stat-tile">
            <span className="stat-tile-label">Taux de repli</span>
            <span className="stat-tile-value">
              {((global?.rate ?? 0) * 100).toFixed(0)} %
            </span>
            <span className="stat-tile-hint">
              Utilisé par les types qui n'ont pas de taux propre
            </span>
            <div className="champ-pourcentage" style={{ marginTop: 8 }}>
              <input
                type="number"
                className="champ-console"
                min={0}
                max={100}
                value={Math.round((global?.rate ?? 0) * 100)}
                disabled={occupe || globalCoupe}
                onChange={(evenement) =>
                  void modifierGlobal({
                    rate: Math.max(0, Math.min(100, Number(evenement.target.value))) / 100,
                  })
                }
              />
              <span>%</span>
            </div>
          </div>
          <div className="stat-tile">
            <span className="stat-tile-label">Injectées</span>
            <span className="stat-tile-value">{global?.injected_count ?? 0}</span>
            <span className="stat-tile-hint">Depuis le dernier compteur remis à zéro</span>
          </div>
        </div>
      </section>

      <section>
        <h2 className="screen-section-title">Types d'anomalies</h2>
        <div className="console-grid">
          {catalogue.map((type) => (
            <article
              key={type.anomalie_code}
              className={`anomalie-carte${type.anomalie_active && !globalCoupe ? " active" : ""}`}
              style={{ ["--famille-couleur" as string]: type.anomalie_couleur }}
            >
              <div className="anomalie-carte-tete">
                <span className="anomalie-famille">
                  <span className="dot" />
                  {type.anomalie_famille}
                </span>
                <label className="toggle-switch-label">
                  <input
                    type="checkbox"
                    className="toggle-checkbox"
                    checked={type.anomalie_active}
                    disabled={occupe}
                    onChange={(evenement) =>
                      void modifierType(type.anomalie_code, { active: evenement.target.checked })
                    }
                  />
                </label>
              </div>

              <h3 className="anomalie-nom">{type.anomalie_libelle}</h3>
              <p className="anomalie-cible">
                {type.anomalie_table_cible}.{type.anomalie_colonne_cible} · {type.anomalie_severite}
              </p>

              <div className="anomalie-ligne">
                <span>Taux</span>
                <div className="champ-pourcentage">
                  <input
                    type="number"
                    className="champ-console"
                    min={0}
                    max={100}
                    value={Math.round(type.anomalie_taux * 100)}
                    disabled={occupe || !type.anomalie_active}
                    onChange={(evenement) =>
                      void modifierType(type.anomalie_code, {
                        taux:
                          Math.max(0, Math.min(100, Number(evenement.target.value))) / 100,
                      })
                    }
                  />
                  <span>%</span>
                </div>
              </div>

              <div className="anomalie-ligne" style={{ marginTop: 12 }}>
                <span>Moment</span>
              </div>
              <select
                className="champ-console"
                value={type.anomalie_declenchement}
                disabled={occupe || !type.anomalie_active}
                onChange={(evenement) =>
                  void modifierType(type.anomalie_code, {
                    declenchement: evenement.target.value,
                  })
                }
              >
                {DECLENCHEMENTS.map((choix) => (
                  <option key={choix.valeur} value={choix.valeur}>
                    {choix.libelle}
                  </option>
                ))}
              </select>

              {(type.anomalie_declenchement === "differe" ||
                type.anomalie_declenchement === "demarrage") && (
                <div className="anomalie-ligne" style={{ marginTop: 10 }}>
                  <span>Délai (s)</span>
                  <input
                    type="number"
                    min={0}
                    className="champ-console"
                    style={{ width: 90 }}
                    value={type.anomalie_delai_secondes ?? 60}
                    disabled={occupe}
                    onChange={(evenement) =>
                      void modifierType(type.anomalie_code, {
                        delai_secondes: Number(evenement.target.value),
                      })
                    }
                  />
                </div>
              )}

              {type.anomalie_declenchement === "manuel" && (
                <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                  <button
                    className="btn btn-start"
                    disabled={occupe || !enCours}
                    onClick={() => void commander("armer_anomalie", type.anomalie_code)}
                    title={enCours ? "Armer maintenant" : "Le moteur est arrêté"}
                  >
                    Armer
                  </button>
                  <button
                    className="btn btn-outline"
                    disabled={occupe || !enCours}
                    onClick={() => void commander("desarmer_anomalie", type.anomalie_code)}
                  >
                    Désarmer
                  </button>
                </div>
              )}
            </article>
          ))}
        </div>
      </section>

      {/* Les aléas ne sont plus ici : ils se déclenchent depuis l'écran de
          suivi, pendant l'exécution. Deux endroits pour le même geste, c'est
          un endroit de trop — et celui-ci ne montre pas ce que l'aléa produit. */}

      <section>
        <h2 className="screen-section-title">Journal des injections</h2>
        {journal.length === 0 ? (
          <div className="screen-empty">
            Aucune anomalie injectée pour l'instant.
          </div>
        ) : (
          <div className="screen-table-wrap">
            <table className="screen-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Ligne visée</th>
                  <th>Valeur d'origine</th>
                  <th>Valeur injectée</th>
                </tr>
              </thead>
              <tbody>
                {journal.map((injection) => (
                  <tr key={injection.injection_id}>
                    <td>{injection.anomalie_code}</td>
                    <td>{injection.cible_cle ?? "—"}</td>
                    <td>{injection.valeur_origine ?? "—"}</td>
                    <td>{injection.valeur_injectee ?? "—"}</td>
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
