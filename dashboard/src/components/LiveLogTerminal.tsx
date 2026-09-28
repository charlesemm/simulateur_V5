import { useEffect, useMemo, useRef, useState } from "react";
import { useKpiSocket } from "../hooks/useKpiSocket";
import type { EvenementParcours } from "../types";
import { TerminalIcon } from "./Icons";

// Chaque type d'événement du moteur, avec le niveau sous lequel l'afficher.
// Un type absent de cette table reste lisible : il s'affiche en INFO.
const NIVEAUX: Record<string, "INFO" | "SUCCESS" | "WARN" | "ERROR"> = {
  "facture.creee": "SUCCESS",
  "facture.statut": "INFO",
  "facture.pathologies": "INFO",
  "prestation.servie": "SUCCESS",
  "medicament.prescrit": "INFO",
  "medicament.retire": "INFO",
  "entente.creee": "INFO",
  "entente.traitee": "SUCCESS",
  "passage.refuse": "WARN",
  "alea.interruption": "ERROR",
  "alea.base_ralentie": "WARN",
  "alea.horloge_decalee": "WARN",
  "alea.saturation_memoire": "WARN",
};

/** Résume la charge utile d'un événement en une ligne lisible. */
function resumer(evenement: EvenementParcours): string {
  const details = Object.entries(evenement.payload)
    .map(([clef, valeur]) => `${clef}=${String(valeur)}`)
    .join(" ");
  return details || "—";
}

function niveau(evenement: EvenementParcours) {
  return NIVEAUX[evenement.type] ?? "INFO";
}

/**
 * Le journal des événements réellement produits par le moteur.
 *
 * Il affichait auparavant des lignes déduites des écarts entre deux relevés de
 * métriques : plausibles, mais fabriquées. Elles viennent maintenant du bus
 * d'événements, celui-là même qui alimente le journal en base.
 */
export function LiveLogTerminal() {
  const { evenements, evenementsEcartes, connectionStatus } = useKpiSocket();
  const [autoScroll, setAutoScroll] = useState(true);
  const [filtre, setFiltre] = useState<string>("ALL");
  const contenuRef = useRef<HTMLDivElement | null>(null);

  const affiches = useMemo(
    () => evenements.filter((evenement) => filtre === "ALL" || niveau(evenement) === filtre),
    [evenements, filtre]
  );

  // On fait défiler le terminal, et lui seul. scrollIntoView faisait
  // défiler toute la page jusqu'à lui à chaque événement : impossible de
  // lire un graphique pendant qu'une simulation tournait.
  useEffect(() => {
    const contenu = contenuRef.current;
    if (autoScroll && contenu) {
      contenu.scrollTop = contenu.scrollHeight;
    }
  }, [affiches, autoScroll]);

  return (
    <article className="clean-terminal-card">
      <div className="terminal-topbar">
        <div className="terminal-header-left">
          <TerminalIcon className="terminal-icon-svg" />
          <strong className="terminal-heading">Parcours en temps réel</strong>
        </div>

        <div className="terminal-actions">
          <select
            className="terminal-select"
            aria-label="Filtrer les événements par niveau"
            value={filtre}
            onChange={(evenement) => setFiltre(evenement.target.value)}
          >
            <option value="ALL">Tous les événements</option>
            <option value="INFO">INFO</option>
            <option value="SUCCESS">SUCCESS</option>
            <option value="WARN">WARN</option>
            <option value="ERROR">ERROR</option>
          </select>
          <label className="terminal-toggle">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(evenement) => setAutoScroll(evenement.target.checked)}
            />
            <span>Auto-scroll</span>
          </label>
        </div>
      </div>

      {/* Un journal : les lecteurs d'écran le trouvent et le parcourent, sans
          qu'il leur lise chaque ligne à mesure — à plusieurs événements par
          seconde, ce serait inaudible. */}
      <div
        ref={contenuRef}
        className="terminal-content"
        role="log"
        aria-live="off"
        aria-label="Événements des parcours"
      >
        {affiches.length === 0 && (
          <div className="terminal-row">
            <span className="row-message">
              {connectionStatus === "connecte"
                ? "En attente d'événements — démarrez une simulation."
                : "Flux temps réel non connecté."}
            </span>
          </div>
        )}

        {affiches.map((evenement, rang) => (
          <div className="terminal-row" key={`${evenement.passage_id}-${rang}`}>
            <span className="row-time">
              {new Date(evenement.simulated_at).toLocaleTimeString("fr-FR")}
            </span>
            <span className={`row-badge tag-${niveau(evenement).toLowerCase()}`}>
              {niveau(evenement)}
            </span>
            <span className="row-source">[{evenement.passage_id.slice(0, 8)}]</span>
            <span className="row-message">
              {evenement.type} · {resumer(evenement)}
            </span>
          </div>
        ))}
      </div>

      {evenementsEcartes > 0 && (
        <p className="terminal-row">
          <span className="row-message">
            {evenementsEcartes} événement(s) non affiché(s) : le moteur produit plus
            vite que le terminal ne se lit. Le journal en base les a tous conservés.
          </span>
        </p>
      )}
    </article>
  );
}
