// dashboard/src/components/ConsoleInjectionPage.tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { API_URL, api } from "../services/api";
import type { SimulationStatus, TypeAnomalie } from "../types";
import "./Screens.css";

const DECLENCHEMENTS: Array<{ valeur: string; libelle: string }> = [
  { valeur: "continu", libelle: "Continu — toute l'exécution" },
  { valeur: "demarrage", libelle: "Démarrage — une salve initiale" },
  { valeur: "differe", libelle: "Différé — après un délai" },
  { valeur: "manuel", libelle: "Manuel — sur ordre en cours de route" },
];

/** Ordre d'affichage des familles, du plus courant au plus structurel.
 *  Le même que sur l'écran de lancement : deux écrans qui rangent les mêmes
 *  anomalies dans deux ordres différents obligent à réapprendre à chaque fois. */
const ORDRE_FAMILLES = [
  "MONTANTS", "DATES", "QUANTITES", "IDENTITE", "FORMAT", "REFERENTIEL",
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
  const [statut, setStatut] = useState<SimulationStatus | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [occupe, setOccupe] = useState(false);
  // Distingue « pas encore reçu » de « rien reçu » : le catalogue vide ne
  // doit s'annoncer en échec qu'après la première réponse.
  const [charge, setCharge] = useState(false);

  const chargerGlobal = useCallback(async () => {
    const reponse = await fetch(`${API_URL}/anomalies`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!reponse.ok) throw new Error(`Réglage global indisponible (${reponse.status}).`);
    setGlobal((await reponse.json()) as ReglageGlobal);
  }, [token]);

  const rafraichir = useCallback(async () => {
    try {
      const [liste, etat] = await Promise.all([
        api.getCatalogue(token),
        api.getSimulationStatus(token),
      ]);
      setCatalogue(liste);
      setStatut(etat);
      await chargerGlobal();
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    } finally {
      setCharge(true);
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

  const parFamille = useMemo(() => {
    const groupes: Record<string, TypeAnomalie[]> = {};
    for (const type of catalogue) {
      (groupes[type.anomalie_famille] ??= []).push(type);
    }
    return groupes;
  }, [catalogue]);

  // Les familles connues d'abord, dans l'ordre voulu ; toute famille ajoutée
  // au catalogue plus tard suit derrière plutôt que de disparaître de l'écran.
  const famillesOrdonnees = useMemo(() => {
    const presentes = Object.keys(parFamille);
    const connues = ORDRE_FAMILLES.filter((famille) => presentes.includes(famille));
    const autres = presentes.filter((famille) => !ORDRE_FAMILLES.includes(famille));
    // localeCompare, et non le tri par défaut : celui-ci compare des codes
    // UTF-16, où « Éligibilité » passerait après « Zone ». Sur un écran qui
    // sert à retrouver une famille dans une liste, l'ordre est tout.
    return [...connues, ...autres.sort((a, b) => a.localeCompare(b, "fr"))];
  }, [parFamille]);

  return (
    <div className="screen">
      {erreur && <p className="screen-error" role="alert">{erreur}</p>}
      {message && <div className="bandeau-info" role="status">{message}</div>}

      {!enCours && (
        <div className="bandeau-info">
          Le moteur est arrêté : les réglages ci-dessous s'appliqueront à la
          prochaine exécution. Armer un type manuel ou déclencher un aléa
          demande un moteur en marche.
        </div>
      )}

      <section>
        <div className="screen-section-head">
          <h2 className="screen-section-title">Interrupteur général</h2>
          {/* Chaque réglage s'enregistre aussitôt : on le dit pendant qu'il part. */}
          <span className="enregistrement" role="status">
            {occupe && (
              <>
                <span className="ui-spinner ui-spinner--petit" aria-hidden="true" />
                Enregistrement…
              </>
            )}
          </span>
        </div>
        <div className="stat-strip">
          <div className="stat-tile">
            <span className="stat-tile-label">Injection</span>
            <span className="stat-tile-value">{global?.enabled ? "Ouverte" : "Coupée"}</span>
            <label className="toggle-switch-label console-tuile-reglage">
              <input
                type="checkbox"
                role="switch"
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
            <div className="champ-pourcentage console-tuile-reglage">
              <input
                type="number"
                className="champ-console"
                aria-label="Taux de repli, en pourcentage"
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

      {/* Une section par famille : treize cartes en vrac se ressemblent
          toutes, rangées par nature elles se retrouvent. */}
      {famillesOrdonnees.map((famille) => {
        const types = parFamille[famille];
        const allumes = types.filter(
          (type) => type.anomalie_active && !globalCoupe
        ).length;

        return (
        <section key={famille}>
          <h2
            className="screen-section-title famille-section"
            style={{ ["--famille-couleur" as string]: types[0].anomalie_couleur }}
          >
            <span className="dot" aria-hidden="true" />
            {famille}
            <span className="rule" aria-hidden="true" />
            <span className="famille-section-compte">
              {allumes} / {types.length} actif(s)
            </span>
          </h2>
        <div className="console-grid">
          {types.map((type) => (
            <article
              key={type.anomalie_code}
              className={`anomalie-carte${type.anomalie_active && !globalCoupe ? " active" : ""}`}
              style={{ ["--famille-couleur" as string]: type.anomalie_couleur }}
            >
              <div className="anomalie-carte-tete">
                <span className="anomalie-famille">
                  <span className="dot" aria-hidden="true" />
                  {type.anomalie_famille}
                </span>
                <label className="toggle-switch-label">
                  <input
                    type="checkbox"
                    role="switch"
                    className="toggle-checkbox"
                    aria-label={`Activer « ${type.anomalie_libelle} »`}
                    checked={type.anomalie_active}
                    disabled={occupe}
                    onChange={(evenement) =>
                      void modifierType(type.anomalie_code, { active: evenement.target.checked })
                    }
                  />
                  <span className="toggle-etat" aria-hidden="true">
                    {type.anomalie_active ? "Actif" : "Coupé"}
                  </span>
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
                    aria-label={`Taux — ${type.anomalie_libelle}`}
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

              <div className="anomalie-ligne anomalie-ligne--espacee">
                <span>Moment</span>
              </div>
              <select
                className="champ-console"
                aria-label={`Moment — ${type.anomalie_libelle}`}
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
                <div className="anomalie-ligne anomalie-ligne--espacee">
                  <span>Délai (s)</span>
                  <input
                    type="number"
                    min={0}
                    className="champ-console champ-delai"
                    aria-label={`Délai en secondes — ${type.anomalie_libelle}`}
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
                <div className="anomalie-actions">
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
        );
      })}

      {!charge && (
        <div className="console-grid" aria-busy="true" aria-label="Chargement du catalogue">
          {[0, 1, 2].map((carte) => (
            <div key={carte} className="anomalie-carte">
              <span className="ui-skeleton ui-skeleton--texte" style={{ width: "40%" }} />
              <span className="ui-skeleton ui-skeleton--titre" style={{ width: "75%", marginTop: 12 }} />
              <span className="ui-skeleton ui-skeleton--texte" style={{ width: "60%" }} />
            </div>
          ))}
        </div>
      )}
      {charge && catalogue.length === 0 && (
        <div className="screen-empty">Le catalogue d'anomalies n'a pas pu être chargé.</div>
      )}

      {/* Les aléas ne sont plus ici : ils se déclenchent depuis l'écran de
          suivi, pendant l'exécution. Deux endroits pour le même geste, c'est
          un endroit de trop — et celui-ci ne montre pas ce que l'aléa produit.

          Le journal des injections a suivi le même chemin : il se lit à froid,
          après coup, et sa place est dans le contrôle qualité — pas sur une
          console où l'on prépare. */}
    </div>
  );
}
