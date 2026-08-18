// Fournit une connexion Socket.IO unique et un fallback REST immédiat.
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { io, type Socket } from "socket.io-client";
import { API_URL, api } from "../services/api";
import type { ConnectionStatus, HistoryPoint, KpiSnapshot, KpiUpdate } from "../types";

interface KpiContextValue {
  snapshot: KpiSnapshot | null;
  history: HistoryPoint[];
  loading: boolean;
  error: string | null;
  connectionStatus: ConnectionStatus;
}

const KpiContext = createContext<KpiContextValue | null>(null);

export function KpiSocketProvider({ children }: { children: ReactNode }) {
  const [snapshot, setSnapshot] = useState<KpiSnapshot | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("connexion");

  useEffect(() => {
    const controller = new AbortController();
    let socket: Socket | null = null;

// REST et Socket.IO démarrent en parallèle pour réduire le premier affichage.
    Promise.all([
      api.getSnapshot(controller.signal),
      api.getPassageHistory(controller.signal),
    ]).then(([initialSnapshot, initialHistory]) => {
      setSnapshot(initialSnapshot);
      setHistory(initialHistory.points);
      setError(null);
    }).catch((reason: Error) => {
      if (reason.name !== "AbortError") setError(`Chargement initial impossible : ${reason.message}`);
    }).finally(() => setLoading(false));

    socket = io(`${API_URL}/kpi`, {
      path: "/socket.io",
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

    return () => {
      controller.abort();
      socket?.removeAllListeners();
      socket?.disconnect();
    };
  }, []);

  const value = useMemo(() => ({ snapshot, history, loading, error, connectionStatus }),
    [snapshot, history, loading, error, connectionStatus]);
  return <KpiContext.Provider value={value}>{children}</KpiContext.Provider>;
}

export function useKpiSocket(): KpiContextValue {
  // Une erreur explicite détecte immédiatement un composant placé hors provider.
  const context = useContext(KpiContext);
  if (!context) throw new Error("useKpiSocket doit être utilisé dans KpiSocketProvider.");
  return context;
}