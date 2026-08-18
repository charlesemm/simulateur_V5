// Assemble les composants du tableau de bord de soutenance.
import { ActsDonut } from "./components/ActsDonut";
import { CenterLoadTable } from "./components/CenterLoadTable";
import { Header } from "./components/Header";
import { MetricCards } from "./components/MetricCards";
import { PassagesLineChart } from "./components/PassagesLineChart";
import { PathologiesBar } from "./components/PathologiesBar";

export default function App() {
  return <div className="app-shell"><Header /><main>
    <MetricCards />
    <section className="chart-grid"><PassagesLineChart /><ActsDonut /><PathologiesBar /></section>
    <CenterLoadTable />
  </main><footer>Données entièrement synthétiques — Démonstrateur de mémoire CMU</footer></div>;
}