// dashboard/src/components/LancementPage.tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { api } from "../services/api";
import type { ProfilSimulation, TypeAnomalie } from "../types";
import "./Screens.css";

interface LancementPageProps {
  /** Type de simulation à préparer : QUALITE, MDM, ENTREPOT ou GOUVERNANCE. */
  typeSimulation: string;
  onAnnuler: () => void;
  onDemarre: (simulationId: string | null) => void;
}

interface ReglageAnomalie {
  active: boolean;
  /** En pourcentage entier, tel que l'opérateur le saisit. */
  pourcentage: number;
  declenchement: string;
  delaiSecondes: number;
}

const DECLENCHEMENTS = [
  { valeur: "continu", libelle: "Continu" },
  { valeur: "demarrage", libelle: "Au démarrage" },
  { valeur: "differe", libelle: "Différé" },
  { valeur: "manuel", libelle: "Manuel" },
];

/** Ordre d'affichage des familles, du plus courant au plus structurel. */
const ORDRE_FAMILLES = [
  "MONTANTS", "DATES", "QUANTITES", "IDENTITE", "FORMAT", "REFERENTIEL",
];

/**
 * Écran de lancement d'une simulation.
 *
 * Le type choisi propose ses réglages ; tout se retouche avant de démarrer.
 * Ce qui est saisi ici ne vaut que pour cette exécution : le catalogue
 * d'anomalies, réglé dans la console, n'est pas réécrit au passage.
 *
 * Les aléas ne s'y règlent pas. Ce sont des gestes que l'on pose pendant
 * l'exécution, depuis l'écran de suivi : un crash test décidé une heure à
 * l'avance n'apprend rien, on ne sait plus s'il a frappé au moment qui
 * comptait.
 */
export function LancementPage({ typeSimulation, onAnnuler, onDemarre }: LancementPageProps) {
  const { token } = useAuth();
  const [profil, setProfil] = useState<ProfilSimulation | null>(null);
  const [catalogue, setCatalogue] = useState<TypeAnomalie[]>([]);
  const [erreur, setErreur] = useState<string | null>(null);
  const [demarrage, setDemarrage] = useState(false);

  const [nom, setNom] = useState("");
  const [vitesse, setVitesse] = useState(60);
  const [limite, setLimite] = useState(20);
  const [reglages, setReglages] = useState<Record<string, ReglageAnomalie>>({});

  const preparer = useCallback(async () => {
    try {
      const [profils, liste] = await Promise.all([
        api.getProfils(token),
        api.getCatalogue(token),
      ]);
      const retenu = profils.find((candidat) => candidat.code === typeSimulation)
        ?? profils[0] ?? null;

      setProfil(retenu);
      setCatalogue(liste);

      if (retenu) {
        setVitesse(retenu.vitesse);
        setLimite(retenu.passages_simultanes_max);
        setNom(`${retenu.libelle} — ${new Date().toLocaleDateString("fr-FR")}`);

        // Le profil sert d'amorce : les types qu'il ne mentionne pas partent
        // éteints, pour que l'écran dise exactement ce qui sera injecté.
        const depart: Record<string, ReglageAnomalie> = {};
        for (const type of liste) {
          const propose = retenu.anomalies[type.anomalie_code] as
            | { taux?: number; declenchement?: string; delai_secondes?: number }
            | undefined;
          depart[type.anomalie_code] = {
            active: propose !== undefined,
            pourcentage: Math.round((propose?.taux ?? 0) * 100),
            declenchement: propose?.declenchement ?? "continu",
            delaiSecondes: propose?.delai_secondes ?? 60,
          };
        }
        setReglages(depart);
      }
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    }
  }, [token, typeSimulation]);

  useEffect(() => {
    void preparer();
  }, [preparer]);

  function modifier(code: string, modification: Partial<ReglageAnomalie>) {
    setReglages((courants) => ({
      ...courants,
      [code]: { ...courants[code], ...modification },
    }));
  }

  async function demarrer() {
    setDemarrage(true);
    setErreur(null);
    try {
      const anomalies: Record<string, Record<string, unknown>> = {};
      for (const [code, reglage] of Object.entries(reglages)) {
        anomalies[code] = reglage.active
          ? {
            active: true,
            taux: reglage.pourcentage / 100,
            declenchement: reglage.declenchement,
            delai_secondes: reglage.delaiSecondes,
          }
          : { active: false, taux: 0 };
      }

      // Aucun aléa n'est transmis : ils se déclenchent à la main, plus tard.
      const statut = await api.demarrerSimulation(token, {
        type_simulation: typeSimulation,
        libelle: nom,
        vitesse,
        nombre_passages_simultanes_max: limite,
        anomalies,
        aleas: {},
      });
      onDemarre(statut.simulation_id);
    } catch (raison) {
      setErreur((raison as Error).message);
    } finally {
      setDemarrage(false);
    }
  }

  const parFamille = useMemo(() => {
    const groupes: Record<string, TypeAnomalie[]> = {};
    for (const type of catalogue) {
      (groupes[type.anomalie_famille] ??= []).push(type);
    }
    return groupes;
  }, [catalogue]);

  const actives = Object.values(reglages).filter(
    (reglage) => reglage.active && reglage.pourcentage > 0
  ).length;

  return (
    <div className="screen">
      {erreur && <p className="screen-error">{erreur}</p>}

      <section>
        <div
          className="fiche fiche--type"
          style={{ ["--type-couleur" as string]: profil?.couleur ?? "var(--cnam-green)" }}
        >
          <div className="fiche-tete">
            <div>
              <span className="type-card-code">{typeSimulation}</span>
              <div className="fiche-titre">{profil?.libelle ?? typeSimulation}</div>
            </div>
            <button className="btn btn-outline" onClick={onAnnuler}>
              Retour
            </button>
          </div>
          {profil && <p className="type-card-desc">{profil.description}</p>}

          <div className="formulaire-lancement">
            <label className="champ-groupe">
              <span className="champ-libelle">Nom de la simulation</span>
              <input
                className="champ-console"
                value={nom}
                maxLength={150}
                placeholder="Par exemple : recette MDM du 24 août"
                onChange={(evenement) => setNom(evenement.target.value)}
              />
            </label>

            <label className="champ-groupe champ-court">
              <span className="champ-libelle">Vitesse (× temps réel)</span>
              <input
                type="number"
                className="champ-console"
                min={1}
                max={86400}
                value={vitesse}
                onChange={(evenement) => setVitesse(Number(evenement.target.value))}
              />
            </label>

            <label className="champ-groupe champ-court">
              <span className="champ-libelle">Passages en parallèle</span>
              <input
                type="number"
                className="champ-console"
                min={1}
                max={200}
                value={limite}
                onChange={(evenement) => setLimite(Number(evenement.target.value))}
              />
            </label>
          </div>
        </div>
      </section>

      <section>
        <h2 className="screen-section-title">
          Anomalies à injecter — {actives} type(s) actif(s)
        </h2>

        {ORDRE_FAMILLES.filter((famille) => parFamille[famille]).map((famille) => (
          <div key={famille} className="famille-bloc">
            <div
              className="famille-titre"
              style={{
                ["--famille-couleur" as string]: parFamille[famille][0].anomalie_couleur,
              }}
            >
              <span className="dot" />
              {famille}
            </div>

            <div className="screen-table-wrap">
              <table className="screen-table">
                <thead>
                  <tr>
                    <th>Anomalie</th>
                    <th>Cible</th>
                    <th style={{ width: 120 }}>Taux</th>
                    <th style={{ width: 150 }}>Moment</th>
                    <th style={{ width: 110 }}>Délai (s)</th>
                  </tr>
                </thead>
                <tbody>
                  {parFamille[famille].map((type) => {
                    const reglage = reglages[type.anomalie_code];
                    if (!reglage) return null;
                    return (
                      <tr key={type.anomalie_code}>
                        <td>
                          <label className="toggle-switch-label">
                            <input
                              type="checkbox"
                              className="toggle-checkbox"
                              checked={reglage.active}
                              onChange={(evenement) =>
                                modifier(type.anomalie_code, {
                                  active: evenement.target.checked,
                                })
                              }
                            />
                            <span className="toggle-label-text">
                              {type.anomalie_libelle}
                            </span>
                          </label>
                        </td>
                        <td>
                          <span className="anomalie-cible">
                            {type.anomalie_table_cible}.{type.anomalie_colonne_cible}
                          </span>
                        </td>
                        <td>
                          <div className="champ-pourcentage">
                            <input
                              type="number"
                              className="champ-console"
                              min={0}
                              max={100}
                              value={reglage.pourcentage}
                              disabled={!reglage.active}
                              onChange={(evenement) =>
                                modifier(type.anomalie_code, {
                                  pourcentage: Math.max(
                                    0, Math.min(100, Number(evenement.target.value))
                                  ),
                                })
                              }
                            />
                            <span>%</span>
                          </div>
                        </td>
                        <td>
                          <select
                            className="champ-console"
                            value={reglage.declenchement}
                            disabled={!reglage.active}
                            onChange={(evenement) =>
                              modifier(type.anomalie_code, {
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
                        </td>
                        <td>
                          <input
                            type="number"
                            className="champ-console"
                            min={0}
                            value={reglage.delaiSecondes}
                            disabled={
                              !reglage.active
                              || reglage.declenchement === "continu"
                              || reglage.declenchement === "manuel"
                            }
                            onChange={(evenement) =>
                              modifier(type.anomalie_code, {
                                delaiSecondes: Number(evenement.target.value),
                              })
                            }
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </section>

      <section className="bandeau-info">
        Les scénarios d'aléa ne se règlent pas ici : ce sont des actions que
        vous déclencherez à la main, pendant l'exécution, depuis l'écran de
        suivi qui s'ouvrira au démarrage.
      </section>

      <div className="barre-lancement">
        <button className="btn btn-outline" onClick={onAnnuler} disabled={demarrage}>
          Annuler
        </button>
        <button className="btn btn-start" onClick={() => void demarrer()} disabled={demarrage}>
          {demarrage ? "Démarrage…" : "Démarrer la simulation"}
        </button>
      </div>
    </div>
  );
}
