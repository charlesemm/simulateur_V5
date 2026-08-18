// Centralise les appels HTTP, le typage et les messages d'erreur français.

import type { HealthCenterList, KpiHistory, KpiSnapshot, SimulationStatus } from "../types";

export const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Réponse non lisible." }));
    throw new Error(body.detail ?? `Erreur HTTP ${response.status}.`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getSnapshot: (signal?: AbortSignal) => request<KpiSnapshot>("/kpi/snapshot", { signal }),
  getPassageHistory: (signal?: AbortSignal) => {
    const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    return request<KpiHistory>(`/kpi/passages/history?since=${encodeURIComponent(since)}&granularite=heure`, { signal });
  },
  getCenters: (signal?: AbortSignal) => request<HealthCenterList>("/centres-sante", { signal }),
  getSimulationStatus: () => request<SimulationStatus>("/simulation/status"),
  startSimulation: (vitesse: number, maximum = 20) => request<SimulationStatus>("/simulation/start", {
    method: "POST", body: JSON.stringify({ vitesse, nombre_passages_simultanes_max: maximum }),
  }),
  stopSimulation: () => request<{ message: string }>("/simulation/stop", { method: "POST" }),
  setSpeed: (vitesse: number) => request<SimulationStatus>("/simulation/speed", {
    method: "POST", body: JSON.stringify({ vitesse }),
  }),
};


