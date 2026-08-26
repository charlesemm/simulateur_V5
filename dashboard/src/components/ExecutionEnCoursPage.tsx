// dashboard/src/components/ExecutionEnCoursPage.tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { useKpiSocket } from "../hooks/useKpiSocket";
import { api } from "../services/api";
import type {
  ExecutionDetail, ProfilSimulation, ScenarioAlea, SimulationStatus, TypeAnomalie,
} from "../types";
import { EchoLogo } from "./EchoLogo";
import "./Cockpit.css";

interface ExecutionEnCoursPageProps {
  /** Quitter le suivi sans toucher au moteur : il continue de tourner. */
  onQuitter: () => void;
  /** Appelé une fois le moteur réellement arrêté, avec de quoi dresser le
   *  bilan : l'exécution qui vient de se clore et les aléas frappés — ces
   *  derniers ne vivent que dans cet écran, personne d'autre ne les a vus. */
  onArret: (simulationId: string | null, frappes: Frappe[]) => void;
}

/** Durée écoulée depuis le début, en h / min / s. */
function depuis(debut: string | null): string {
  if (!debut) return "—";
  const secondes = Math.max(0, Math.round((Date.now() - new Date(debut).getTime()) / 1000));
  const heures = Math.floor(secondes / 3600);
  const minutes = Math.floor((secondes % 3600) / 60);
  if (heures > 0) return `${heures} h ${String(minutes).padStart(2, "0")}`;
  if (minutes > 0) return `${minutes} min ${String(secondes % 60).padStart(2, "0")}`;
  return `${secondes} s`;
}

/** Un aléa effectivement frappé, avec l'heure du geste. */
interface Frappe {
  code: string;
  libelle: string;
  nature: string;
  couleur: string;
  horodatage: Date;
}

/** L'heure d'une frappe, à la seconde. */
function heure(instant: Date): string {
  return instant.toLocaleTimeString("fr-FR", {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

/** Une durée en minutes, dite en heures et minutes quand elle est longue. */
function enClair(minutes: number): string {
  const arrondi = Math.max(0, Math.round(minutes));
  if (arrondi < 60) return `${arrondi} min`;
  return `${Math.floor(arrondi / 60)} h ${String(arrondi % 60).padStart(2, "0")}`;
}

const NOMS_VOLUMETRIE: Record<string, string> = {
  factures: "Factures ouvertes",
  prestations: "Prestations servies",
  ententes: "Ententes préalables",
  evenements: "Événements journalisés",
  anomalies: "Anomalies posées",
  refus_accueil: "Refusés à l'accueil",
};

/**
 * Le cockpit d'une simulation en cours.
 *
 * Il prend tout l'écran, sans barre latérale ni en-tête, et se tient sur fond
 * sombre quand tout le reste de l'application est clair : pendant qu'une
 * exécution tourne, on ne consulte pas, on pilote.
 *
 * Il ne montre que ce qui n'a de sens qu'en direct — les compteurs qui
 * montent, les aléas à frapper, les anomalies posées, le flux qui défile. Tout
 * ce qui se lit à froid appartient à l'écran Simulations, et n'a rien à faire
 * ici.
 */
export function ExecutionEnCoursPage({ onQuitter, onArret }: ExecutionEnCoursPageProps) {
  const { token } = useAuth();
  const { evenements } = useKpiSocket();
  const [statut, setStatut] = useState<SimulationStatus | null>(null);
  const [detail, setDetail] = useState<ExecutionDetail | null>(null);
  const [profils, setProfils] = useState<ProfilSimulation[]>([]);
  const [aleas, setAleas] = useState<ScenarioAlea[]>([]);
  const [catalogue, setCatalogue] = useState<TypeAnomalie[]>([]);
  // Un tableau daté, et non un compteur par code : « frappé 2 fois » ne dit
  // ni quand, ni dans quel ordre — or c'est exactement ce qu'on cherche à
  // relire quand on veut savoir ce qui a produit tel creux dans les chiffres.
  const [frappes, setFrappes] = useState<Frappe[]>([]);
  const [erreur, setErreur] = useState<string | null>(null);
  const [arretEnCours, setArretEnCours] = useState(false);
  const [battement, setBattement] = useState(0);

  useEffect(() => {
    void (async () => {
      try {
        const [listeProfils, scenarios, types] = await Promise.all([
          api.getProfils(token), api.getAleas(token), api.getCatalogue(token),
        ]);
        setProfils(listeProfils);
        setAleas(scenarios);
        setCatalogue(types);
      } catch (raison) {
        setErreur((raison as Error).message);
      }
    })();
  }, [token]);

  const rafraichir = useCallback(async () => {
    try {
      const etat = await api.getSimulationStatus(token);
      setStatut(etat);
      if (etat.simulation_id) setDetail(await api.getExecution(etat.simulation_id, token));
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    }
  }, [token]);

  useEffect(() => {
    void rafraichir();
    const minuterie = setInterval(() => {
      void rafraichir();
      setBattement((valeur) => valeur + 1);
    }, 1500);
    return () => clearInterval(minuterie);
  }, [rafraichir]);

  async function frapper(alea: ScenarioAlea) {
    try {
      await api.commander("declencher_alea", alea.code, token);
      // En tête de liste : le dernier geste est celui qu'on relit d'abord.
      setFrappes((courants) => [
        {
          code: alea.code, libelle: alea.libelle,
          nature: alea.nature, couleur: alea.couleur,
          horodatage: new Date(),
        },
        ...courants,
      ]);
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    }
  }

  async function arreter() {
    setArretEnCours(true);
    try {
      await api.stopSimulation(token);
      // L'identifiant est lu avant l'arrêt : une fois le moteur clos, le
      // statut ne le porte plus, et le bilan n'aurait plus rien à ouvrir.
      onArret(execution?.simulation_id ?? statut?.simulation_id ?? null, frappes);
    } catch (raison) {
      setErreur((raison as Error).message);
      setArretEnCours(false);
    }
  }

  const profil = profils.find((candidat) => candidat.code === statut?.type_simulation);
  const teinte = profil?.couleur ?? "#4caf2a";
  const execution = detail?.execution ?? null;

  const injections = useMemo(() => {
    const comptes = detail?.anomalies_par_type ?? {};
    return Object.entries(comptes)
      .map(([code, nombre]) => {
        const type = catalogue.find((entree) => entree.anomalie_code === code);
        return {
          code,
          libelle: type?.anomalie_libelle ?? code,
          couleur: type?.anomalie_couleur ?? "#7fd1a3",
          nombre,
        };
      })
      .sort((premier, second) => second.nombre - premier.nombre);
  }, [detail, catalogue]);

  const derniers = evenements.slice(-16).reverse();
  void battement; // recalcule le chronomètre à chaque tour

  /** Combien de fois chaque aléa a été frappé, tiré du fil lui-même. */
  const comptes = useMemo(() => {
    const total: Record<string, number> = {};
    for (const frappe of frappes) total[frappe.code] = (total[frappe.code] ?? 0) + 1;
    return total;
  }, [frappes]);

  /**
   * Où en est l'exécution par rapport à la durée que l'opérateur visait.
   *
   * Rien n'arrête le moteur à l'échéance : la barre est un repère, pas une
   * minuterie. Sans durée visée — les exécutions ouvertes avant que ce champ
   * existe, par exemple — il n'y a pas d'objectif, donc pas de barre.
   */
  const progression = useMemo(() => {
    const parametres = execution?.simulation_parametres as
      { duree_visee_minutes?: number | null } | undefined;
    const objectif = parametres?.duree_visee_minutes ?? null;
    const debut = execution?.simulation_date_debut ?? null;
    if (!objectif || !debut) return null;

    const ecoulees = (Date.now() - new Date(debut).getTime()) / 60000;
    return {
      objectif,
      ecoulees,
      part: Math.min(1, Math.max(0, ecoulees / objectif)),
      restant: objectif - ecoulees,
      fin: new Date(new Date(debut).getTime() + objectif * 60000),
    };
    // `battement` fait battre le calcul au même rythme que le chronomètre.
  }, [execution?.simulation_parametres, execution?.simulation_date_debut, battement]);

  return (
    <div className="cockpit" style={{ ["--teinte" as string]: teinte }}>
      <div className="cockpit-contenu">

        <header className="cockpit-tete">
          <div className="cockpit-identite">
            <EchoLogo size={46} className="cockpit-marque" id="cockpit" />
            <div>
              <span className="cockpit-badge">
                <span className="cockpit-battement" aria-hidden="true" />
                {profil?.libelle ?? statut?.type_simulation ?? "Simulation"}
              </span>
              <h1 className="cockpit-nom">
                {execution?.simulation_libelle ?? "Simulation en cours"}
              </h1>
              <span className="cockpit-cadence">
                vitesse ×{statut?.vitesse ?? 0} · {statut?.passages_simultanes_max ?? 0} passages
                en parallèle au maximum
              </span>
            </div>
          </div>

          <div className="cockpit-actions">
            <div className="cockpit-chrono">
              <span className="cockpit-chrono-valeur">
                {depuis(execution?.simulation_date_debut ?? null)}
              </span>
              <span className="cockpit-chrono-libelle">en cours</span>
            </div>
            <button className="cockpit-bouton cockpit-quitter" onClick={onQuitter}>
              Quitter le suivi
            </button>
            <button
              className="cockpit-bouton cockpit-arret"
              onClick={() => void arreter()}
              disabled={arretEnCours}
            >
              {arretEnCours ? "Arrêt…" : "Arrêter"}
            </button>
          </div>
        </header>

        {erreur && <p className="cockpit-erreur">{erreur}</p>}

        {progression && (
          <section className="cockpit-progression">
            <div className="cockpit-progression-tete">
              <span className="cockpit-progression-libelle">
                Progression vers la durée visée
              </span>
              <span className="cockpit-progression-chiffres">
                {progression.restant > 0 ? (
                  <>
                    Il reste <b>{enClair(progression.restant)}</b>
                    {" · fin visée "}
                    <b>{progression.fin.toLocaleTimeString("fr-FR",
                      { hour: "2-digit", minute: "2-digit" })}</b>
                  </>
                ) : (
                  <b>Durée visée atteinte — le moteur tourne toujours</b>
                )}
              </span>
              <span
                className="cockpit-progression-part"
                style={{ ["--teinte" as string]: teinte }}
              >
                {Math.round(progression.part * 100)} %
              </span>
            </div>

            <div
              className="cockpit-jauge"
              role="progressbar"
              aria-valuenow={Math.round(progression.part * 100)}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Progression vers la durée visée"
            >
              <div
                className="cockpit-jauge-remplie"
                style={{
                  width: `${progression.part * 100}%`,
                  ["--teinte" as string]: teinte,
                }}
              />
            </div>

            <div className="cockpit-progression-bornes">
              <span>{enClair(progression.ecoulees)} écoulées</span>
              <span>objectif {enClair(progression.objectif)}</span>
            </div>
          </section>
        )}

        <section>
          <h2 className="cockpit-titre">Ce qui se produit</h2>
          <div className="cockpit-compteurs">
            <div className="cockpit-compteur" style={{ ["--accent" as string]: teinte }}>
              <span className="cockpit-compteur-valeur">{statut?.passages_actifs ?? 0}</span>
              <span className="cockpit-compteur-nom">Passages en cours</span>
            </div>
            <div className="cockpit-compteur" style={{ ["--accent" as string]: "#7fd1a3" }}>
              <span className="cockpit-compteur-valeur">{execution?.passages_reussis ?? 0}</span>
              <span className="cockpit-compteur-nom">Passages clôturés</span>
            </div>
            <div className="cockpit-compteur" style={{ ["--accent" as string]: "#ff8a5c" }}>
              <span className="cockpit-compteur-valeur">
                {statut?.passages_interrompus ?? 0}
              </span>
              <span className="cockpit-compteur-nom">Coupés par un aléa</span>
            </div>
            <div className="cockpit-compteur" style={{ ["--accent" as string]: "#e5a44d" }}>
              <span className="cockpit-compteur-valeur">{execution?.passages_echoues ?? 0}</span>
              <span className="cockpit-compteur-nom">Échecs du moteur</span>
            </div>

            {Object.entries(detail?.volumetrie ?? {}).map(([cle, nombre]) => (
              <div key={cle} className="cockpit-compteur" style={{ ["--accent" as string]: "#79c0e8" }}>
                <span className="cockpit-compteur-valeur">{nombre}</span>
                <span className="cockpit-compteur-nom">{NOMS_VOLUMETRIE[cle] ?? cle}</span>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h2 className="cockpit-titre">Frapper un aléa</h2>
          <p className="cockpit-aide">
            Un clic vaut un ordre, une seule fois. Le moteur le lit entre deux
            passages : l'effet arrive au suivant, pas à l'instant du clic.
          </p>
          <div className="cockpit-aleas">
            {aleas.map((alea) => (
              <button
                key={alea.code}
                type="button"
                className={`cockpit-alea${comptes[alea.code] ? " frappe" : ""}`}
                style={{ ["--alea" as string]: alea.couleur }}
                onClick={() => void frapper(alea)}
              >
                <span className="cockpit-alea-nature">{alea.nature}</span>
                <span className="cockpit-alea-nom">{alea.libelle}</span>
                <span className="cockpit-alea-compte">
                  {comptes[alea.code]
                    ? `frappé ${comptes[alea.code]} fois`
                    : "cliquer pour déclencher"}
                </span>
              </button>
            ))}
          </div>
        </section>

        {frappes.length > 0 && (
          <section>
            <h2 className="cockpit-titre">Aléas frappés</h2>
            <div className="cockpit-fil">
              {frappes.map((frappe) => (
                <div
                  key={`${frappe.code}-${frappe.horodatage.getTime()}`}
                  className="cockpit-fil-ligne"
                  style={{ ["--alea" as string]: frappe.couleur }}
                >
                  <span className="cockpit-fil-heure">{heure(frappe.horodatage)}</span>
                  <span className="cockpit-fil-puce" aria-hidden="true" />
                  <span className="cockpit-fil-nom">{frappe.libelle}</span>
                  <span className="cockpit-fil-nature">{frappe.nature}</span>
                </div>
              ))}
            </div>
            <p className="cockpit-aide">
              Ce fil vaut pour la session en cours : il repart à vide si vous
              quittez le poste de pilotage et y revenez.
            </p>
          </section>
        )}

        <section>
          <h2 className="cockpit-titre">Anomalies posées</h2>
          {injections.length === 0 ? (
            <div className="cockpit-flux">
              <p className="cockpit-vide">Aucune anomalie posée pour l'instant.</p>
            </div>
          ) : (
            <div className="cockpit-injections">
              {injections.map((ligne) => (
                <div
                  key={ligne.code}
                  className="cockpit-injection"
                  style={{ ["--famille" as string]: ligne.couleur }}
                >
                  <span className="cockpit-injection-nom">{ligne.libelle}</span>
                  <span className="cockpit-injection-nombre">{ligne.nombre}</span>
                </div>
              ))}
            </div>
          )}
        </section>

        <section>
          <h2 className="cockpit-titre">Flux des passages</h2>
          <div className="cockpit-flux">
            {derniers.length === 0 && (
              <p className="cockpit-vide">En attente du premier événement…</p>
            )}
            {derniers.map((evenement, rang) => (
              <div className="cockpit-flux-ligne" key={`${evenement.passage_id}-${rang}`}>
                <span className="cockpit-flux-heure">
                  {new Date(evenement.simulated_at).toLocaleTimeString("fr-FR")}
                </span>
                <span
                  className={`cockpit-flux-type${
                    evenement.type.startsWith("alea.") ? " alea" : ""
                  }`}
                >
                  {evenement.type}
                </span>
                <span className="cockpit-flux-passage">
                  {evenement.passage_id.slice(0, 8)}
                </span>
              </div>
            ))}
          </div>
        </section>

      </div>
    </div>
  );
}
