// dashboard/src/components/Header.tsx
import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { RequireRole } from "../auth/RequireRole";
import { useKpiSocket } from "../hooks/useKpiSocket";
import { api } from "../services/api";
import type { SimulationStatus } from "../types";
import { ConnectionBadge } from "./ConnectionBadge";

interface TopbarProps {
  ongletActif: "dashboard" | "utilisateurs" | "rapports";
}

export function Header({ ongletActif }: TopbarProps) {
  const { connectionStatus } = useKpiSocket();
  const { token } = useAuth();
  const [status, setStatus] = useState<SimulationStatus | null>(null);
  const [speed, setSpeed] = useState(60);
  const [maxPassages, setMaxPassages] = useState(20);
  const [showLimitModal, setShowLimitModal] = useState(false);
  const [limitInput, setLimitInput] = useState(20);
  const [initialLoading, setInitialLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [speedLoading, setSpeedLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function refreshStatus() {
      try {
        const value = await api.getSimulationStatus(token);
        if (cancelled) return;
        setStatus(value);
        setSpeed(value.vitesse);
        if (value.passages_simultanes_max) {
          setMaxPassages(value.passages_simultanes_max);
          setLimitInput(value.passages_simultanes_max);
        }
        setError(null);
      } catch (reason) {
        if (!cancelled) setError((reason as Error).message);
      } finally {
        if (!cancelled) setInitialLoading(false);
      }
    }

    void refreshStatus();
    const interval = setInterval(refreshStatus, 2000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [token]);

  async function handleDemarrer() {
    setStarting(true);
    setError(null);
    try {
      setStatus(await api.startSimulation(speed, maxPassages, token));
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setStarting(false);
    }
  }

  async function handleArreter() {
    setStopping(true);
    setError(null);
    try {
      await api.stopSimulation(token);
      setStatus(await api.getSimulationStatus(token));
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setStopping(false);
    }
  }

  async function applySpeed() {
    if (status?.etat !== "en_cours") return;
    setSpeedLoading(true);
    setError(null);
    try {
      setStatus(await api.setSpeed(speed, token));
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setSpeedLoading(false);
    }
  }

  function applyLimit() {
    const val = Math.max(1, Math.min(200, limitInput));
    setMaxPassages(val);
    setLimitInput(val);
    setShowLimitModal(false);
  }

  const enCours = status?.etat === "en_cours";
  const controlsBusy = initialLoading || starting || stopping || speedLoading;

  function getPageTitle() {
    switch (ongletActif) {
      case "dashboard":
        return { title: "Supervision Technique", subtitle: "Télémétrie en temps réel du moteur de simulation" };
      case "rapports":
        return { title: "Rapports Quotidiens", subtitle: "Génération et archivage des états du simulateur" };
      case "utilisateurs":
        return { title: "Gestion des Accès", subtitle: "Administration des comptes et permissions" };
    }
  }

  const { title, subtitle } = getPageTitle();

  return (
    <>
      <header className="topbar">
        <div className="topbar-left">
          <div className="topbar-title-group">
            <h1 className="topbar-title">{title}</h1>
            <span className="topbar-subtitle">{subtitle}</span>
          </div>
        </div>

        <div className="topbar-right">
          <ConnectionBadge status={connectionStatus} />

          <RequireRole minimum="operateur">
            <div className="topbar-divider" />

            {/* Vitesse */}
            <div className="speed-widget">
              <span className="speed-caption">
                Vitesse <strong>×{speed}</strong>
              </span>
              <input
                type="range"
                min="1"
                max="3600"
                step="1"
                value={speed}
                onChange={(event) => setSpeed(Number(event.target.value))}
                onMouseUp={applySpeed}
                onTouchEnd={applySpeed}
                disabled={controlsBusy}
                className="speed-range"
              />
            </div>

            {/* Limite de passages */}
            <button
              className="btn-limit"
              onClick={() => setShowLimitModal(true)}
              title="Configurer la limite de passages simultanés"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                <circle cx="9" cy="7" r="4"/>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
              </svg>
              Limite : <strong>{maxPassages}</strong>
            </button>

            <div className="topbar-divider" />

            {/* ── Boutons DÉMARRER / ARRÊTER côte à côte ── */}
            <div className="engine-actions">
              <button
                id="btn-start-simulation"
                className={`btn-engine btn-engine-start${enCours ? " btn-engine-active-dimmed" : ""}`}
                onClick={handleDemarrer}
                disabled={controlsBusy || enCours}
                title={enCours ? "Simulation en cours" : "Démarrer la simulation"}
              >
                {starting ? (
                  <span className="btn-engine-spinner" />
                ) : (
                  <svg className="btn-engine-icon" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
                  </svg>
                )}
                {starting ? "Démarrage…" : "Démarrer"}
              </button>

              <button
                id="btn-stop-simulation"
                className={`btn-engine btn-engine-stop${!enCours ? " btn-engine-inactive-dimmed" : ""}`}
                onClick={handleArreter}
                disabled={initialLoading || stopping || !enCours}
                title={!enCours ? "Simulation arrêtée" : "Arrêter la simulation"}
              >
                {stopping ? (
                  <span className="btn-engine-spinner" />
                ) : (
                  <svg className="btn-engine-icon" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clipRule="evenodd" />
                  </svg>
                )}
                {stopping ? "Arrêt…" : "Arrêter"}
              </button>
            </div>
          </RequireRole>

          {error && (
            <div className="topbar-error" role="alert">
              {error}
            </div>
          )}
        </div>
      </header>

      {/* ── Modal Limite de passages ── */}
      {showLimitModal && (
        <div className="limit-modal-overlay" onClick={() => setShowLimitModal(false)}>
          <div className="limit-modal" onClick={(e) => e.stopPropagation()}>
            <div className="limit-modal-header">
              <div className="limit-modal-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                  <circle cx="9" cy="7" r="4"/>
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                  <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                </svg>
              </div>
              <div>
                <h3 className="limit-modal-title">Limite de passages simultanés</h3>
                <p className="limit-modal-desc">Nombre maximum d'assurés traités en parallèle</p>
              </div>
            </div>

            <div className="limit-modal-explain">
              <div className="limit-explain-row">
                <span className="limit-tag limit-tag-low">1–5</span>
                <span>Simulation légère — idéal pour débugger ou serveur limité</span>
              </div>
              <div className="limit-explain-row">
                <span className="limit-tag limit-tag-med">10–30</span>
                <span>Simulation équilibrée — valeur recommandée en production</span>
              </div>
              <div className="limit-explain-row">
                <span className="limit-tag limit-tag-high">50–200</span>
                <span>Test de charge intensif — nécessite un serveur puissant</span>
              </div>
            </div>

            <div className="limit-modal-input-row">
              <label className="limit-modal-label" htmlFor="limit-input">
                Votre limite :
              </label>
              <div className="limit-input-group">
                <button
                  className="limit-step-btn"
                  onClick={() => setLimitInput(Math.max(1, limitInput - 1))}
                >−</button>
                <input
                  id="limit-input"
                  type="number"
                  min={1}
                  max={200}
                  value={limitInput}
                  onChange={(e) => setLimitInput(Number(e.target.value))}
                  className="limit-number-input"
                />
                <button
                  className="limit-step-btn"
                  onClick={() => setLimitInput(Math.min(200, limitInput + 1))}
                >+</button>
              </div>
              <span className="limit-unit">passages max</span>
            </div>

            <div className="limit-presets">
              {[5, 10, 20, 50, 100].map((v) => (
                <button
                  key={v}
                  className={`limit-preset-btn${limitInput === v ? " limit-preset-active" : ""}`}
                  onClick={() => setLimitInput(v)}
                >
                  {v}
                </button>
              ))}
            </div>

            <div className="limit-modal-footer">
              <button className="limit-cancel-btn" onClick={() => setShowLimitModal(false)}>
                Annuler
              </button>
              <button className="limit-apply-btn" onClick={applyLimit}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                Appliquer
              </button>
            </div>

            {enCours && (
              <p className="limit-modal-warning">
                ⚠️ La nouvelle limite sera prise en compte au prochain démarrage.
              </p>
            )}
          </div>
        </div>
      )}
    </>
  );
}