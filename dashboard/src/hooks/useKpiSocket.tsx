// Fournit une connexion Socket.IO unique et un fallback REST immédiat.
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { io, type Socket } from "socket.io-client";
import { useAuth } from "../auth/AuthContext";
import { API_URL, api } from "../services/api";
import type {
  ConnectionStatus, EvenementParcours, HistoryPoint, KpiSnapshot, KpiUpdate,
  PaquetParcours,
} from "../types";

interface KpiContextValue {
  snapshot: KpiSnapshot | null;
  history: HistoryPoint[];
  loading: boolean;
  error: string | null;
  connectionStatus: ConnectionStatus;
  /** Derniers événements de parcours reçus, le plus récent en dernier. */
  evenements: EvenementParcours[];
  /** Événements écartés par le serveur faute de place dans un paquet. */
  evenementsEcartes: number;
}

// Le terminal n'affiche qu'une fenêtre : garder tout ferait grossir la
// mémoire du navigateur pendant qu'une simulation tourne des heures.
const FENETRE_EVENEMENTS = 300;

const KpiContext = createContext<KpiContextValue | null>(null);

export function KpiSocketProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  const [snapshot, setSnapshot] = useState<KpiSnapshot | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("connexion");
  const [evenements, setEvenements] = useState<EvenementParcours[]>([]);
  const [evenementsEcartes, setEvenementsEcartes] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let socket: Socket | null = null;

// REST et Socket.IO démarrent en parallèle pour réduire le premier affichage.
    Promise.all([
      api.getSnapshot(token, controller.signal),
      api.getPassageHistory(token, controller.signal),
    ]).then(([initialSnapshot, initialHistory]) => {
      setSnapshot(initialSnapshot);
      setHistory(initialHistory.points);
      setError(null);
    }).catch((reason: Error) => {
      if (reason.name !== "AbortError") setError(`Chargement initial impossible : ${reason.message}`);
    }).finally(() => setLoading(false));

    socket = io(`${API_URL}/kpi`, {
      path: "/socket.io",
      auth: { token },
      transports: ["websocket", "polling"],
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    });

    socket.on("connect", () => { setConnectionStatus("connecte"); setError(null); });
    socket.on("disconnect", () => setConnectionStatus("deconnecte"));
    socket.on("connect_error", (reason) => {
      setConnectionStatus("reconnexion");
      setError(`Connexion temps réel indisponible : ${reason.message}`);
    });
    socket.io.on("reconnect_attempt", () => setConnectionStatus("reconnexion"));
    socket.on("kpi:snapshot", (payload: KpiSnapshot) => {
      setSnapshot(payload);
      setLoading(false);
    });
    socket.on("kpi:update", (payload: KpiUpdate) => {
      setSnapshot(payload.data);
      // Le point courant maintient la courbe vivante sans nouvel appel REST.
      setHistory((current) => {
        const next = { timestamp: payload.data.generated_at, value: payload.data.passages.total };
        return [...current.filter((point) => point.timestamp !== next.timestamp), next].slice(-48);
      });
    });

    socket.on("parcours:evenements", (payload: PaquetParcours) => {
      setEvenements((courants) =>
        [...courants, ...payload.evenements].slice(-FENETRE_EVENEMENTS)
      );
      if (payload.ecartes > 0) {
        setEvenementsEcartes((total) => total + payload.ecartes);
      }
    });

    return () => {
      controller.abort();
      socket?.removeAllListeners();
      socket?.disconnect();
    };
  }, [token]);

  const value = useMemo(
    () => ({
      snapshot, history, loading, error, connectionStatus,
      evenements, evenementsEcartes,
    }),
    [snapshot, history, loading, error, connectionStatus, evenements, evenementsEcartes]
  );
  return <KpiContext.Provider value={value}>{children}</KpiContext.Provider>;
}

export function useKpiSocket(): KpiContextValue {
  // Une erreur explicite détecte immédiatement un composant placé hors provider.
  const context = useContext(KpiContext);
  if (!context) throw new Error("useKpiSocket doit être utilisé dans KpiSocketProvider.");
  return context;
}