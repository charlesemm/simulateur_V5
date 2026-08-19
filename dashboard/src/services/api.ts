// Centralise les appels HTTP, le typage et les messages d'erreur français.

import type { HealthCenterList, KpiHistory, KpiSnapshot, SimulationStatus } from "../types";

export const API_URL = (import.meta.env.VITE_API_URL as string) ?? "http://127.0.0.1:8000";

function authHeaders(token: string | null): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    const message = detail?.detail ?? `Erreur HTTP ${response.status}`;
    if (response.status === 401) {
      throw new Error(
        typeof message === "string" && message !== "Not authenticated"
          ? message
          : "Session expirée ou non authentifiée — reconnectez-vous."
      );
    }
    throw new Error(typeof message === "string" ? message : `Erreur HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  /** KPI – lecture seule, endpoint public */
  async getSnapshot(signal?: AbortSignal): Promise<KpiSnapshot> {
    const response = await fetch(`${API_URL}/kpi/snapshot`, { signal });
    return parseOrThrow<KpiSnapshot>(response);
  },

  async getPassageHistory(signal?: AbortSignal): Promise<KpiHistory> {
    const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    const response = await fetch(
      `${API_URL}/kpi/passages/history?since=${encodeURIComponent(since)}&granularite=heure`,
      { signal }
    );
    return parseOrThrow<KpiHistory>(response);
  },

  /** Centres de santé – lecture seule, endpoint public */
  async getCenters(signal?: AbortSignal): Promise<HealthCenterList> {
    const response = await fetch(`${API_URL}/centres-sante`, { signal });
    return parseOrThrow<HealthCenterList>(response);
  },

  /** Simulation – lecture seule, endpoint public */
  async getSimulationStatus(): Promise<SimulationStatus> {
    const response = await fetch(`${API_URL}/simulation/status`);
    return parseOrThrow<SimulationStatus>(response);
  },

  /** Simulation – endpoints protégés (nécessitent un token JWT) */
  async startSimulation(
    vitesse: number,
    nombrePassagesSimultanesMax: number = 20,
    token: string | null = null
  ): Promise<SimulationStatus> {
    const response = await fetch(`${API_URL}/simulation/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify({ vitesse, nombre_passages_simultanes_max: nombrePassagesSimultanesMax }),
    });
    return parseOrThrow<SimulationStatus>(response);
  },

  async stopSimulation(token: string | null = null): Promise<{ message: string }> {
    const response = await fetch(`${API_URL}/simulation/stop`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
    });
    return parseOrThrow<{ message: string }>(response);
  },

  async setSpeed(vitesse: number, token: string | null = null): Promise<SimulationStatus> {
    const response = await fetch(`${API_URL}/simulation/speed`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify({ vitesse }),
    });
    return parseOrThrow<SimulationStatus>(response);
  },

  /** Rapports – endpoints protégés (opérateur minimum) */
  async listReports(token: string | null): Promise<string[]> {
    const response = await fetch(`${API_URL}/reports`, {
      headers: authHeaders(token),
    });
    return parseOrThrow<string[]>(response);
  },

  async generateReport(token: string | null): Promise<{ pdf: string; excel: string }> {
    const response = await fetch(`${API_URL}/reports/generate`, {
      method: "POST",
      headers: authHeaders(token),
    });
    return parseOrThrow<{ pdf: string; excel: string }>(response);
  },

  async downloadReport(nomFichier: string, token: string | null): Promise<void> {
    const response = await fetch(`${API_URL}/reports/${nomFichier}`, {
      headers: authHeaders(token),
    });
    if (!response.ok) throw new Error("Téléchargement impossible.");
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const lien = document.createElement("a");
    lien.href = url;
    lien.download = nomFichier;
    lien.click();
    window.URL.revokeObjectURL(url);
  },

  /** Métriques Techniques SRE & Performance */
  async getTechnicalMetrics(signal?: AbortSignal): Promise<import("../types").TechnicalMetricsSnapshot> {
    const response = await fetch(`${API_URL}/metrics/technical`, { signal });
    return parseOrThrow<import("../types").TechnicalMetricsSnapshot>(response);
  },

  async resetTechnicalMetrics(): Promise<{ message: string }> {
    const response = await fetch(`${API_URL}/metrics/technical/reset`, { method: "POST" });
    return parseOrThrow<{ message: string }>(response);
  },
};
