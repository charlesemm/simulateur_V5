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
  /** Appelé une fois le moteur réellement arrêté. */
  onArret: () => void;
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
  const [frappes, setFrappes] = useState<Record<string, number>>({});
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

  async function frapper(code: string) {
    try {
      await api.commander("declencher_alea", code, token);
      setFrappes((courants) => ({ ...courants, [code]: (courants[code] ?? 0) + 1 }));
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    }
  }

  async function arreter() {
    setArretEnCours(true);
    try {
      await api.stopSimulation(token);
      onArret();
    } catch (raison) {
      setErreur((raison as Error).message);
      setArretEnCours(false);
    }
  }

  const profil = profils.find((candidat) => candidat.code === statut?.type_simulation);
  const teinte = profil?.couleur ?? "#16a34a";
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
                className={`cockpit-alea${frappes[alea.code] ? " frappe" : ""}`}
                style={{ ["--alea" as string]: alea.couleur }}
                onClick={() => void frapper(alea.code)}
              >
                <span className="cockpit-alea-nature">{alea.nature}</span>
                <span className="cockpit-alea-nom">{alea.libelle}</span>
                <span className="cockpit-alea-compte">
                  {frappes[alea.code]
                    ? `frappé ${frappes[alea.code]} fois`
                    : "cliquer pour déclencher"}
                </span>
              </button>
            ))}
          </div>
        </section>

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
