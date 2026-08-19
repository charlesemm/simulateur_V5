import { useEffect, useRef, useState } from "react";
import type { TechnicalMetricsSnapshot } from "../types";
import { TerminalIcon } from "./Icons";

interface LogEntry {
  id: string;
  timestamp: string;
  level: "INFO" | "SUCCESS" | "WARN" | "ERROR";
  source: "ENGINE" | "KPI_CONSUMER" | "FASTAPI" | "SOCKETIO";
  message: string;
}

interface LiveLogTerminalProps {
  metrics: TechnicalMetricsSnapshot | null;
}

export function LiveLogTerminal({ metrics }: LiveLogTerminalProps) {
  const [logs, setLogs] = useState<LogEntry[]>([
    {
      id: "1",
      timestamp: new Date().toLocaleTimeString("fr-FR"),
      level: "INFO",
      source: "ENGINE",
      message: "Démarrage du cockpit de supervision CNAM-CI...",
    },
    {
      id: "2",
      timestamp: new Date().toLocaleTimeString("fr-FR"),
      level: "SUCCESS",
      source: "FASTAPI",
      message: "Télémétrie active et connectée sur /metrics/technical.",
    },
  ]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filterLevel, setFilterLevel] = useState<string>("ALL");
  const terminalEndRef = useRef<HTMLDivElement | null>(null);
  const prevMetricsRef = useRef<TechnicalMetricsSnapshot | null>(null);

  useEffect(() => {
    if (!metrics) return;
    const prev = prevMetricsRef.current;
    const now = new Date().toLocaleTimeString("fr-FR");
    const newLogs: LogEntry[] = [];

    if (prev) {
      if (metrics.moteur_etat !== prev.moteur_etat) {
        newLogs.push({
          id: Math.random().toString(36).substring(2, 9),
          timestamp: now,
          level: metrics.moteur_etat === "en_cours" ? "SUCCESS" : "WARN",
          source: "ENGINE",
          message: `Moteur ${metrics.moteur_etat.toUpperCase()} (vitesse ×${metrics.moteur_vitesse}).`,
        });
      }

      if (metrics.passages_reussis > prev.passages_reussis) {
        const delta = metrics.passages_reussis - prev.passages_reussis;
        newLogs.push({
          id: Math.random().toString(36).substring(2, 9),
          timestamp: now,
          level: "INFO",
          source: "ENGINE",
          message: `+${delta} passage(s) clôturé(s) avec succès (Total: ${metrics.passages_reussis}).`,
        });
      }

      if (metrics.passages_echoues > prev.passages_echoues) {
        const delta = metrics.passages_echoues - prev.passages_echoues;
        newLogs.push({
          id: Math.random().toString(36).substring(2, 9),
          timestamp: now,
          level: "ERROR",
          source: "ENGINE",
          message: `+${delta} anomalie(s) survenue(s) lors de l'exécution asynchrone.`,
        });
      }

      if (metrics.recalculs_kpi > prev.recalculs_kpi) {
        newLogs.push({
          id: Math.random().toString(36).substring(2, 9),
          timestamp: now,
          level: "INFO",
          source: "KPI_CONSUMER",
          message: `Calcul du snapshot d'état achevé en ${metrics.derniere_duree_recalcul_kpi_ms} ms.`,
        });
      }

      if (metrics.clients_socketio_actifs !== prev.clients_socketio_actifs) {
        newLogs.push({
          id: Math.random().toString(36).substring(2, 9),
          timestamp: now,
          level: "INFO",
          source: "SOCKETIO",
          message: `Clients WebSocket actifs : ${metrics.clients_socketio_actifs}.`,
        });
      }
    }

    prevMetricsRef.current = metrics;

    if (newLogs.length > 0) {
      setLogs((prevLogs) => [...prevLogs, ...newLogs].slice(-100));
    }
  }, [metrics]);

  useEffect(() => {
    if (autoScroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll]);

  const filteredLogs = logs.filter((log) => (filterLevel === "ALL" ? true : log.level === filterLevel));

  return (
    <article className="clean-terminal-card">
      <div className="terminal-topbar">
        <div className="terminal-header-left">
          <TerminalIcon className="terminal-icon-svg" />
          <strong className="terminal-heading">Journal Système & Événements Moteur</strong>
        </div>

        <div className="terminal-actions">
          <select
            className="terminal-select"
            value={filterLevel}
            onChange={(e) => setFilterLevel(e.target.value)}
          >
            <option value="ALL">Tous les flux</option>
            <option value="INFO">INFO</option>
            <option value="SUCCESS">SUCCESS</option>
            <option value="WARN">WARN</option>
            <option value="ERROR">ERROR</option>
          </select>
          <label className="terminal-toggle">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
            />
            <span>Auto-scroll</span>
          </label>
          <button className="terminal-btn-clear" onClick={() => setLogs([])}>
            Effacer
          </button>
        </div>
      </div>

      <div className="terminal-content">
        {filteredLogs.map((log) => (
          <div className="terminal-row" key={log.id}>
            <span className="row-time">{log.timestamp}</span>
            <span className={`row-badge tag-${log.level.toLowerCase()}`}>{log.level}</span>
            <span className="row-source">[{log.source}]</span>
            <span className="row-message">{log.message}</span>
          </div>
        ))}
        <div ref={terminalEndRef} />
      </div>
    </article>
  );
}
