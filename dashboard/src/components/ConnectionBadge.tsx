// Affiche un état de connexion compréhensible pendant une présentation.
import type { ConnectionStatus } from "../types";

const LABELS: Record<ConnectionStatus, string> = {
  connexion: "Connexion…", connecte: "Temps réel connecté",
  reconnexion: "Reconnexion…", deconnecte: "Temps réel déconnecté",
};

export function ConnectionBadge({ status }: { status: ConnectionStatus }) {
  return <span className={`connection-badge connection-${status}`} role="status">
    <span className="connection-dot" />{LABELS[status]}
  </span>;
}