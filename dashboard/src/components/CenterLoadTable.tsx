// Affiche et filtre la charge active, enrichie avec le libellé des centres.
import { useEffect, useMemo, useState } from "react";
import { useKpiSocket } from "../hooks/useKpiSocket";
import { api } from "../services/api";
import type { HealthCenter } from "../types";

export function CenterLoadTable() {
  const { snapshot, loading: kpiLoading, error: kpiError } = useKpiSocket();
  const [centers, setCenters] = useState<HealthCenter[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    api.getCenters(controller.signal).then((result) => setCenters(result.centres))
      .catch((reason: Error) => { if (reason.name !== "AbortError") setError(reason.message); })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const rows = useMemo(() => {
    const loads = new Map(snapshot?.charge_centres.map((item) => [item.centre_sante_code, item.passages_actifs]));
    return centers.map((center) => ({ ...center, passages_actifs: loads.get(center.centre_sante_code) ?? 0 }))
      .filter((center) => !filter || center.centre_sante_code === filter)
      .sort((left, right) => right.passages_actifs - left.passages_actifs);
  }, [centers, filter, snapshot]);

  return <article className="table-panel"><div className="panel-heading"><div><h2>Charge par centre</h2><p className="panel-subtitle">Passages actuellement actifs</p></div>
    <label>Filtrer <select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="">Tous les centres</option>
      {centers.map((center) => <option value={center.centre_sante_code} key={center.centre_sante_code}>{center.centre_sante_code} — {center.denomination}</option>)}
    </select></label></div>
    {(loading || kpiLoading) && !snapshot ? <div className="skeleton table-skeleton" />
      : (error || kpiError) && !rows.length ? <p className="panel-error">{error ?? kpiError}</p>
      : <div className="table-scroll"><table><thead><tr><th>Centre</th><th>Type</th><th>Dénomination</th><th>Passages actifs</th></tr></thead>
        <tbody>{rows.map((row) => <tr key={row.centre_sante_code}><td><strong>{row.centre_sante_code}</strong></td><td>{row.type_code ?? "—"}</td><td>{row.denomination}</td><td><span className="load-pill">{row.passages_actifs}</span></td></tr>)}</tbody></table></div>}
  </article>;
}