// dashboard/src/components/ChargeTraitementChart.tsx
// Charge de traitement du moteur : passages actifs vs capacité maximale.
// Interroge directement /simulation/status, sans passer par le pipeline KPI --
// c'est une métrique du moteur lui-même, pas un indicateur métier.
import { useEffect, useRef, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../services/api";

interface PointCharge {
  heure: string;
  passagesActifs: number;
  capaciteMax: number;
}

const INTERVALLE_MS = 2000;
const POINTS_MAX = 60; // 2 minutes d'historique à 2 secondes d'intervalle.

export function ChargeTraitementChart() {
  const [points, setPoints] = useState<PointCharge[]>([]);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    async function poll() {
      try {
        const status = await api.getSimulationStatus();
        const maintenant = new Date().toLocaleTimeString("fr-FR", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });
        setPoints((precedents) => {
          const suivant = [
            ...precedents,
            {
              heure: maintenant,
              passagesActifs: status.passages_actifs,
              capaciteMax: status.passages_simultanes_max,
            },
          ];
          return suivant.slice(-POINTS_MAX);
        });
      } catch {
        // Une erreur ponctuelle de sondage ne doit pas casser le graphique --
        // le prochain intervalle réessaiera simplement.
      }
    }

    void poll();
    intervalRef.current = setInterval(poll, INTERVALLE_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  const dernierPoint = points.at(-1);
  const proche = dernierPoint && dernierPoint.passagesActifs >= dernierPoint.capaciteMax * 0.9;

  return (
    <div className="chart-card">
      <div className="chart-card-header">
        <h3>Charge de traitement du moteur</h3>
        {proche && <span className="badge-alerte">Proche de la capacité maximale</span>}
      </div>
      {points.length === 0 ? (
        <p className="chart-empty">En attente des premières mesures...</p>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={points}>
            <XAxis dataKey="heure" tick={{ fontSize: 11 }} />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Line type="monotone" dataKey="passagesActifs" name="Passages actifs" stroke="#006b67" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="capaciteMax" name="Capacité max" stroke="#d95055" strokeDasharray="4 4" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}