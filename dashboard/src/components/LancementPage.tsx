// dashboard/src/components/LancementPage.tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { api } from "../services/api";
import type { CadenceMoteur, ProfilSimulation, TypeAnomalie } from "../types";
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

  // La cadence du moteur vient de l'API : la recopier ici la ferait dériver
  // à la première retouche de la configuration.
  const [cadence, setCadence] = useState<CadenceMoteur | null>(null);
  // Durée que l'opérateur vise, en minutes. Elle ne pilote pas le moteur —
  // elle ne sert qu'à projeter un volume avant de partir.
  const [dureeVisee, setDureeVisee] = useState(60);
  // Familles repliées. Une famille sans anomalie active n'a rien à montrer :
  // six tableaux dépliés d'un coup, c'est ce qui rendait l'écran illisible.
  const [repliees, setRepliees] = useState<Set<string>>(new Set());

  const preparer = useCallback(async () => {
    try {
      const [profils, liste, rythme] = await Promise.all([
        api.getProfils(token),
        api.getCatalogue(token),
        api.getCadence(token),
      ]);
      const retenu = profils.find((candidat) => candidat.code === typeSimulation)
        ?? profils[0] ?? null;

      setProfil(retenu);
      setCatalogue(liste);
      setCadence(rythme);

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

        // On ne déplie que les familles qui ont quelque chose à montrer.
        const allumees = new Set<string>();
        for (const type of liste) {
          if (depart[type.anomalie_code]?.active) allumees.add(type.anomalie_famille);
        }
        setRepliees(new Set(
          liste
            .map((type) => type.anomalie_famille)
            .filter((famille) => !allumees.has(famille))
        ));
      }
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    }
  }, [token, typeSimulation]);

  useEffect(() => {
    void preparer();
  }, [preparer]);

  /** Taux de repli quand ni le profil ni le catalogue n'en proposent un. */
  const TAUX_PAR_DEFAUT = 5;

  function modifier(code: string, modification: Partial<ReglageAnomalie>) {
    setReglages((courants) => {
      const suivant = { ...courants[code], ...modification };

      // Activer un type sans lui donner de taux n'injecte rien : la case
      // cochée promettrait une anomalie que le moteur ne poserait jamais, et
      // l'estimation resterait à zéro sans qu'on comprenne pourquoi. Le mode
      // LIBRE ne préréglant aucune anomalie, c'est le cas de départ de tous
      // les types — on reprend donc le taux du catalogue, à défaut un repli.
      if (modification.active === true && suivant.pourcentage <= 0) {
        const duCatalogue = catalogue
          .find((type) => type.anomalie_code === code)?.anomalie_taux ?? 0;
        suivant.pourcentage = duCatalogue > 0
          ? Math.round(duCatalogue * 100)
          : TAUX_PAR_DEFAUT;
      }

      return { ...courants, [code]: suivant };
    });
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
        // Elle n'arrête pas le moteur : elle sert de repère au poste de
        // pilotage, qui n'avait jusqu'ici aucun objectif à afficher.
        duree_visee_minutes: dureeVisee,
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

  function basculerFamille(famille: string) {
    setRepliees((courantes) => {
      const suivantes = new Set(courantes);
      if (suivantes.has(famille)) suivantes.delete(famille);
      else suivantes.add(famille);
      return suivantes;
    });
  }

  /**
   * Ce que ces réglages produiront, avant de partir.
   *
   * Le moteur fait arriver un passage toutes les
   * `passage_arrival_mean_seconds` secondes simulées ; à la vitesse v, cela
   * fait 3600 × v / moyenne passages par heure réelle. C'est la seule
   * projection que le moteur autorise sans tourner — le nombre de factures,
   * lui, dépend des droits ouverts dans les données semées, qu'on ne peut
   * pas connaître d'ici.
   */
  const estimation = useMemo(() => {
    const moyenne = cadence?.passage_arrival_mean_seconds ?? 0;
    if (moyenne <= 0 || vitesse <= 0) return null;

    const parHeure = (3600 * vitesse) / moyenne;
    const surLaDuree = parHeure * (dureeVisee / 60);

    // Chaque type actif tire indépendamment : la part du flux épargnée est le
    // produit des « aucune injection », et le reste porte une anomalie.
    const partSaine = Object.values(reglages)
      .filter((reglage) => reglage.active && reglage.pourcentage > 0)
      .reduce((reste, reglage) => reste * (1 - reglage.pourcentage / 100), 1);
    const partTouchee = 1 - partSaine;

    return { parHeure, surLaDuree, partTouchee, anomalies: surLaDuree * partTouchee };
  }, [cadence, vitesse, dureeVisee, reglages]);

  const entier = (valeur: number) => Math.round(valeur).toLocaleString("fr-FR");

  return (
    <div className="screen">
      {erreur && <p className="screen-error">{erreur}</p>}

      <div className="launch-grid">
      <section className="launch-setup">
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
                onChange={(evenement) =>
                  setVitesse(Math.max(1, Math.min(86400, Number(evenement.target.value))))
                }
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
                onChange={(evenement) =>
                  // Le serveur refuse tout au-delà de 200 (HTTP 422) : sans ce
                  // garde-fou, taper une valeur au clavier au-delà du `max`
                  // affiché envoie une requête que le moteur ne démarre jamais,
                  // et rien n'expliquait pourquoi aucune anomalie n'apparaissait.
                  setLimite(Math.max(1, Math.min(200, Number(evenement.target.value))))
                }
              />
            </label>

            <label className="champ-groupe champ-court">
              <span className="champ-libelle">Durée visée (min)</span>
              <input
                type="number"
                className="champ-console"
                min={1}
                max={1440}
                value={dureeVisee}
                onChange={(evenement) =>
                  setDureeVisee(Math.max(1, Number(evenement.target.value)))
                }
              />
            </label>
          </div>
        </div>

        {/* L'estimation se tient sous les réglages, dans la colonne collante :
            elle doit rester sous les yeux pendant qu'on bouge les curseurs,
            sans quoi on règle de nouveau à l'aveugle. */}
        {estimation && (
          <div className="estimation">
            <div className="estimation-tete">
              <span className="pouls" aria-hidden="true" />
              Estimation en direct
            </div>

            <div className="estimation-corps">
              <div className="estimation-ligne">
                <span className="estimation-valeur">≈ {entier(estimation.parHeure)}</span>
                <div>
                  <div className="estimation-quoi">passages par heure</div>
                  <div className="estimation-detail">au rythme d’arrivée du moteur</div>
                </div>
              </div>

              <div className="estimation-ligne">
                <span className="estimation-valeur">≈ {entier(estimation.surLaDuree)}</span>
                <div>
                  <div className="estimation-quoi">passages en tout</div>
                  <div className="estimation-detail">
                    sur les {dureeVisee} min visées
                  </div>
                </div>
              </div>

              <div className="estimation-ligne">
                <span className="estimation-valeur estimation-valeur--alerte">
                  ≈ {entier(estimation.anomalies)}
                </span>
                <div>
                  <div className="estimation-quoi">porteront une anomalie</div>
                  <div className="estimation-detail">
                    soit {(estimation.partTouchee * 100).toFixed(1)} % du flux
                    &nbsp;·&nbsp; {actives} type(s) actif(s)
                  </div>
                </div>
              </div>
            </div>

            {/* Les taux se cumulent : la part saine est le produit des « pas
                touché », donc sept types à 10 % suffisent à dépasser la moitié
                du flux. Sans ce garde-fou, on fabrique un jeu majoritairement
                abîmé sans l'avoir voulu. */}
            {estimation.partTouchee >= 0.5 && (
              <p className="estimation-alerte">
                <b>Plus d’une ligne sur deux</b> portera une anomalie. C’est
                utile pour éprouver les règles de contrôle, mais un tel jeu ne
                ressemble plus à des données réelles — évitez-le pour alimenter
                le MDM ou l’entrepôt.
              </p>
            )}

            <p className="estimation-note">
              Recalculé à chaque réglage. Le nombre de <b>factures</b> sera
              inférieur : les assurés sans droits ouverts sont refusés à
              l’accueil et ne produisent aucune facture.
            </p>
          </div>
        )}
      </section>

      <section>
        <h2 className="screen-section-title">
          Anomalies à injecter — {actives} type(s) actif(s)
        </h2>

        {ORDRE_FAMILLES.filter((famille) => parFamille[famille]).map((famille) => {
          const typesFamille = parFamille[famille];
          const allumes = typesFamille.filter(
            (type) => reglages[type.anomalie_code]?.active
          ).length;
          const repliee = repliees.has(famille);

          return (
          <div key={famille} className="famille-bloc">
            <button
              type="button"
              className="famille-titre famille-bascule"
              aria-expanded={!repliee}
              onClick={() => basculerFamille(famille)}
              style={{
                ["--famille-couleur" as string]: typesFamille[0].anomalie_couleur,
              }}
            >
              <span className="dot" />
              {famille}
              <span className="famille-compte">
                {allumes} / {typesFamille.length}
              </span>
              <span className="famille-chevron" aria-hidden="true">
                {repliee ? "▸" : "▾"}
              </span>
            </button>

            {!repliee && (
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
            )}
          </div>
          );
        })}
      </section>
      </div>

      <section className="bandeau-info">
        Les scénarios d'aléa ne se règlent pas ici : ce sont des actions que
        vous déclencherez à la main, pendant l'exécution, depuis l'écran de
        suivi qui s'ouvrira au démarrage.
      </section>

      {/* Le dernier coup d'œil avant le départ : une erreur de saisie coûte
          encore zéro ici, et deux heures une fois le moteur parti. */}
      <div className="recap-lancement">
        <span className="recap-libelle">Au départ</span>
        <span className="recap-texte">
          <b style={{ color: profil?.couleur ?? "var(--cnam-green-dark)" }}>
            {typeSimulation}
          </b>
          {" · vitesse "}<b>×{vitesse}</b>
          {" · "}<b>{limite}</b>{" passages en parallèle"}
          {" · "}<b>{actives}</b>{" type(s) d’anomalie"}
          {estimation && (
            <>
              {" pour "}
              <b>{(estimation.partTouchee * 100).toFixed(1)} %</b>
              {" du flux · durée visée "}<b>{dureeVisee} min</b>
            </>
          )}
        </span>
      </div>

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
