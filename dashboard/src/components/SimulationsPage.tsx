// dashboard/src/components/SimulationsPage.tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { api } from "../services/api";
import type {
  ExecutionDetail, ScenarioAlea, SimulationRun, TypeAnomalie,
} from "../types";
import { StatutPastille, dateCourte, duree } from "./format-execution";
import "./Screens.css";

interface SimulationsPageProps {
  /** Exécution à ouvrir d'emblée, quand on arrive depuis l'accueil. */
  executionInitiale?: string | null;
}

const LIBELLES_VOLUMETRIE: Record<string, string> = {
  factures: "Factures",
  prestations: "Prestations",
  ententes: "Ententes préalables",
  evenements: "Événements",
  anomalies: "Anomalies injectées",
};

/**
 * W3 — Historique des exécutions et fiche de l'une d'elles.
 *
 * La fiche compte ce que l'exécution a laissé en base. Les lignes produites
 * avant que les exécutions n'existent portent un identifiant nul : elles
 * n'apparaissent dans aucune fiche, et c'est voulu.
 */
export function SimulationsPage({ executionInitiale = null }: SimulationsPageProps) {
  const { token } = useAuth();
  const [executions, setExecutions] = useState<SimulationRun[]>([]);
  const [selection, setSelection] = useState<string | null>(executionInitiale);
  const [fiche, setFiche] = useState<ExecutionDetail | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  // Le catalogue donne aux codes leur libellé et leur couleur ; les aléas,
  // leur intitulé lisible.
  const [catalogue, setCatalogue] = useState<TypeAnomalie[]>([]);
  const [aleas, setAleas] = useState<ScenarioAlea[]>([]);

  const chargerListe = useCallback(async () => {
    try {
      setExecutions(await api.getExecutions(token, 50));
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    }
  }, [token]);

  useEffect(() => {
    // Ces deux référentiels ne bougent pas pendant qu'on lit une fiche.
    void (async () => {
      try {
        const [liste, scenarios] = await Promise.all([
          api.getCatalogue(token),
          api.getAleas(token),
        ]);
        setCatalogue(liste);
        setAleas(scenarios);
      } catch {
        // Sans eux, la fiche affiche les codes bruts : lisible, sans plus.
      }
    })();
  }, [token]);

  useEffect(() => {
    void chargerListe();
    // Une exécution en cours voit ses compteurs bouger : la liste se rafraîchit
    // sans qu'on ait à quitter l'écran.
    const minuterie = setInterval(() => void chargerListe(), 5000);
    return () => clearInterval(minuterie);
  }, [chargerListe]);

  useEffect(() => {
    if (!selection) {
      setFiche(null);
      return;
    }
    let annule = false;

    async function charger(identifiant: string) {
      try {
        const detail = await api.getExecution(identifiant, token);
        if (!annule) {
          setFiche(detail);
          setErreur(null);
        }
      } catch (raison) {
        if (!annule) setErreur((raison as Error).message);
      }
    }

    void charger(selection);
    return () => {
      annule = true;
    };
  }, [selection, token, executions]);

  // Ce qui a été demandé au lancement vit dans les paramètres de l'exécution ;
  // ce qui a réellement été fait vient du journal d'injection. Les deux côte à
  // côte, y compris les types restés à zéro — un type demandé qui n'a rien
  // produit est justement ce qu'on veut voir.
  const parametres = (fiche?.execution.simulation_parametres ?? {}) as {
    anomalies?: Record<string, { taux?: number; active?: boolean }>;
    aleas?: Record<string, { probabilite?: number }>;
    vitesse?: number;
    passages_simultanes_max?: number;
  };

  const anomaliesParametrees = useMemo(() => {
    const demandees = parametres.anomalies ?? {};
    const codes = new Set([
      ...Object.keys(demandees),
      ...Object.keys(fiche?.anomalies_par_type ?? {}),
    ]);
    return [...codes]
      .map((code) => {
        const type = catalogue.find((entree) => entree.anomalie_code === code);
        const reglage = demandees[code] ?? {};
        return {
          code,
          libelle: type?.anomalie_libelle ?? code,
          couleur: type?.anomalie_couleur ?? "var(--text-light)",
          pourcentage: Math.round((reglage.taux ?? 0) * 100),
          injectees: fiche?.anomalies_par_type[code] ?? 0,
        };
      })
      // Un type éteint et sans injection n'apprend rien : on l'écarte.
      .filter((ligne) => ligne.pourcentage > 0 || ligne.injectees > 0)
      .sort((premier, second) => second.injectees - premier.injectees);
  }, [parametres.anomalies, fiche, catalogue]);

  const aleasParametres = useMemo(() => {
    const demandes = parametres.aleas ?? {};
    return Object.entries(demandes)
      .map(([code, reglage]) => ({
        code,
        libelle: aleas.find((alea) => alea.code === code)?.libelle ?? code,
        pourcentage: Math.round((reglage.probabilite ?? 0) * 100),
      }))
      .filter((ligne) => ligne.pourcentage > 0);
  }, [parametres.aleas, aleas]);

  const vitesseDemandee = parametres.vitesse ?? "—";
  const limiteDemandee = parametres.passages_simultanes_max ?? "—";

  return (
    <div className="screen">
      {erreur && <p className="screen-error">{erreur}</p>}

      <section>
        <h2 className="screen-section-title">Historique des exécutions</h2>
        {executions.length === 0 ? (
          <div className="screen-empty">
            Aucune exécution enregistrée. Lancez un type depuis l'accueil.
          </div>
        ) : (
          <div className="screen-table-wrap">
            <table className="screen-table">
              <thead>
                <tr>
                  <th>Début</th>
                  <th>Fin</th>
                  <th>Type</th>
                  <th>Statut</th>
                  <th>Durée</th>
                  <th>Réussis</th>
                  <th>Échoués</th>
                </tr>
              </thead>
              <tbody>
                {executions.map((execution) => (
                  <tr
                    key={execution.simulation_id}
                    className={`cliquable${
                      execution.simulation_id === selection ? " selectionnee" : ""
                    }`}
                    onClick={() =>
                      setSelection(
                        execution.simulation_id === selection ? null : execution.simulation_id
                      )
                    }
                  >
                    <td>{dateCourte(execution.simulation_date_debut)}</td>
                    <td>{dateCourte(execution.simulation_date_fin)}</td>
                    <td>{execution.simulation_type ?? "—"}</td>
                    <td><StatutPastille statut={execution.simulation_statut} /></td>
                    <td>{duree(execution.simulation_date_debut, execution.simulation_date_fin)}</td>
                    <td>{execution.passages_reussis}</td>
                    <td>{execution.passages_echoues}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {fiche && (
        <section>
          <h2 className="screen-section-title">Fiche d'exécution</h2>
          <article className="fiche">
            <div className="fiche-tete">
              <div>
                <div className="fiche-titre">{fiche.execution.simulation_libelle}</div>
                <div className="fiche-identifiant">{fiche.execution.simulation_id}</div>
              </div>
              <StatutPastille statut={fiche.execution.simulation_statut} />
            </div>

            <div className="stat-strip">
              {Object.entries(fiche.volumetrie).map(([cle, nombre]) => (
                <div key={cle} className="stat-tile">
                  <span className="stat-tile-label">{LIBELLES_VOLUMETRIE[cle] ?? cle}</span>
                  <span className="stat-tile-value">{nombre}</span>
                </div>
              ))}
            </div>

            {anomaliesParametrees.length > 0 && (
              <>
                <h3 className="screen-section-title" style={{ marginTop: 22 }}>
                  Anomalies — demandé puis obtenu
                </h3>
                <div className="cellules">
                  {anomaliesParametrees.map((ligne) => (
                    <div
                      key={ligne.code}
                      className={`cellule${ligne.injectees > 0 ? " remplie" : ""}`}
                      style={{ ["--cellule-couleur" as string]: ligne.couleur }}
                    >
                      <span className="cellule-titre">{ligne.libelle}</span>
                      <span className="cellule-nombre">{ligne.injectees}</span>
                      <span className="cellule-pied">
                        <span>injectées</span>
                        <strong>demandé {ligne.pourcentage} %</strong>
                      </span>
                    </div>
                  ))}
                </div>
                {anomaliesParametrees.some((ligne) => ligne.injectees === 0) && (
                  <p className="stat-tile-hint" style={{ marginTop: 10 }}>
                    Un type demandé mais jamais injecté n'est pas forcément une
                    panne : à faible taux, une exécution courte peut ne jamais
                    tomber dessus.
                  </p>
                )}
              </>
            )}

            {aleasParametres.length > 0 && (
              <>
                <h3 className="screen-section-title" style={{ marginTop: 22 }}>
                  Aléas demandés
                </h3>
                <div className="cellules">
                  {aleasParametres.map((ligne) => (
                    <div key={ligne.code} className="cellule">
                      <span className="cellule-titre">{ligne.libelle}</span>
                      <span className="cellule-nombre">{ligne.pourcentage} %</span>
                      <span className="cellule-pied">
                        <span>probabilité par passage</span>
                      </span>
                    </div>
                  ))}
                </div>
              </>
            )}

            <h3 className="screen-section-title" style={{ marginTop: 22 }}>
              Cadence demandée
            </h3>
            <div className="cellules">
              <div className="cellule">
                <span className="cellule-titre">Vitesse</span>
                <span className="cellule-nombre">×{vitesseDemandee}</span>
                <span className="cellule-pied"><span>fois le temps réel</span></span>
              </div>
              <div className="cellule">
                <span className="cellule-titre">Passages en parallèle</span>
                <span className="cellule-nombre">{limiteDemandee}</span>
                <span className="cellule-pied"><span>au maximum</span></span>
              </div>
            </div>
          </article>
        </section>
      )}
    </div>
  );
}
