import { useCallback, useEffect, useRef, useState } from "react";
import { Header } from "./components/Header";
import { Sidebar } from "./components/Sidebar";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { LoginPage } from "./auth/LoginPage";
import { ChangePasswordPage } from "./auth/ChangePasswordPage";
import { RequireRole } from "./auth/RequireRole";
import { KpiSocketProvider } from "./hooks/useKpiSocket";
import { TechMetricCards } from "./components/TechMetricCards";
import { ChargeTraitementChart } from "./components/ChargeTraitementChart";
import { LatencyPerformanceChart } from "./components/LatencyPerformanceChart";
import { SystemHealthDonut } from "./components/SystemHealthDonut";
import { LiveLogTerminal } from "./components/LiveLogTerminal";
import { ReportsPage } from "./components/ReportsPage";
import { ExecutionEnCoursCard } from "./components/ExecutionEnCoursCard";
import { ExecutionEnCoursPage } from "./components/ExecutionEnCoursPage";
import { ActiviteMetierSection } from "./components/ActiviteMetierSection";
import { AccueilPage } from "./components/AccueilPage";
import { CampagnesPage } from "./components/CampagnesPage";
import { NouvelleCampagnePage } from "./components/NouvelleCampagnePage";
import { BilanExecutionPage, type FrappeBilan } from "./components/BilanExecutionPage";
import { AdministrationPage } from "./components/AdministrationPage";
import { ConsoleInjectionPage } from "./components/ConsoleInjectionPage";
import { LancementPage } from "./components/LancementPage";
import { QualitePage } from "./components/QualitePage";
import { SimulationsPage } from "./components/SimulationsPage";
import type { Onglet } from "./navigation";
import { api } from "./services/api";
import type { TechnicalMetricsSnapshot } from "./types";

function DashboardShell() {
  const { isAuthenticated, token, doitChangerMotDePasse } = useAuth();
  const [ongletActif, setOngletActif] = useState<Onglet>("accueil");
  // Exécution ouverte depuis l'accueil : elle voyage jusqu'à l'écran
  // Simulations, qui l'affiche d'emblée.
  const [executionOuverte, setExecutionOuverte] = useState<string | null>(null);
  // Type choisi sur l'accueil, que l'écran de lancement vient paramétrer.
  const [typeAConfigurer, setTypeAConfigurer] = useState("LIBRE");
  // Campagne créée à l'instant : l'écran des campagnes l'ouvre d'emblée.
  const [campagneOuverte, setCampagneOuverte] = useState<string | null>(null);
  // Ce que le poste de pilotage lègue au bilan en s'arrêtant. Les aléas
  // frappés ne vivent nulle part ailleurs : ils se perdraient sans ce relais.
  const [bilan, setBilan] = useState<
    { simulationId: string; frappes: FrappeBilan[] } | null
  >(null);
  const [metrics, setMetrics] = useState<TechnicalMetricsSnapshot | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Inutile de sonder les métriques tant que l'API refuse les autres
    // routes : le compte est encore sous mot de passe temporaire.
    if (!isAuthenticated || doitChangerMotDePasse) return;
    let cancelled = false;

    async function fetchTechMetrics() {
      try {
        const data = await api.getTechnicalMetrics(token);
        if (!cancelled) {
          setMetrics(data);
          setLoading(false);
        }
      } catch {
        // En cas d'erreur ponctuelle, le prochain sondage réessaiera
      }
    }

    void fetchTechMetrics();
    const interval = setInterval(fetchTechMetrics, 1500);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [isAuthenticated, token, doitChangerMotDePasse]);

  const moteurEnCours = metrics?.moteur_etat === "en_cours";

  // Quand on navigue vers le cockpit (après un démarrage), les métriques
  // polled toutes les 1,5 s n'ont pas encore rattrapé le nouvel état du
  // moteur. Sans délai de grâce, l'effet ci-dessous renvoie à l'accueil
  // avant même que le cockpit n'apparaisse.
  const graceRef = useRef(false);

  const allerAuCockpit = useCallback(() => {
    graceRef.current = true;
    setOngletActif("encours");
    // 5 secondes : assez pour que 3 polls confirment l'état du moteur.
    setTimeout(() => { graceRef.current = false; }, 5000);
  }, []);

  // Le cockpit n'existe que pendant l'exécution : si le moteur s'arrête alors
  // qu'on y est, on revient à l'accueil plutôt que de laisser un écran qui ne
  // décrit plus rien.
  useEffect(() => {
    if (ongletActif === "encours" && metrics && !moteurEnCours && !graceRef.current) {
      setOngletActif("accueil");
    }
  }, [ongletActif, metrics, moteurEnCours]);

  if (!isAuthenticated) return <LoginPage />;
  if (doitChangerMotDePasse) return <ChangePasswordPage />;

  // Le cockpit sort du cadre : ni barre latérale, ni en-tête. Il n'a rien à
  // partager avec les écrans de consultation, pas même leur gabarit. Le
  // fournisseur temps réel reste au-dessus des deux branches : le sortir et le
  // remettre à chaque bascule rouvrirait la connexion et perdrait le flux
  // d'événements déjà reçu.
  return (
    <KpiSocketProvider>
      {ongletActif === "encours" ? (
        <ExecutionEnCoursPage
          onQuitter={() => setOngletActif("accueil")}
          onArret={(simulationId, frappes) => {
            // Sans exécution identifiable il n'y a pas de bilan à dresser :
            // on retombe alors sur l'accueil plutôt que d'ouvrir un écran vide.
            if (simulationId) {
              setBilan({ simulationId, frappes });
              setOngletActif("bilan");
              return;
            }
            setOngletActif("accueil");
          }}
        />
      ) : (
      <div className="enterprise-layout">
        {/* Navigation Latérale Gauche */}
        <Sidebar
          ongletActif={ongletActif}
          onNaviguer={(onglet) => onglet === "encours" ? allerAuCockpit() : setOngletActif(onglet)}
          moteurEnCours={moteurEnCours}
        />

        {/* Zone de contenu principale avec Topbar */}
        <div className="enterprise-main">
          <Header ongletActif={ongletActif} onRejoindreCockpit={allerAuCockpit} />

          <div className="content-scrollable">
            {ongletActif === "accueil" && (
              <AccueilPage
                onVoirExecution={(simulationId) => {
                  setExecutionOuverte(simulationId);
                  setOngletActif("simulations");
                }}
                onConfigurer={(type, parcours) => {
                  // Deux parcours derrière les cartes : le moteur temps réel,
                  // et la campagne de test, qui ne le traverse jamais.
                  if (parcours === "campagne") {
                    setOngletActif("campagne-nouvelle");
                    return;
                  }
                  setTypeAConfigurer(type);
                  setOngletActif("lancement");
                }}
                onRejoindreCockpit={allerAuCockpit}
                onVoirHistorique={() => setOngletActif("simulations")}
              />
            )}

            {ongletActif === "lancement" && (
              <RequireRole minimum="operateur">
                <LancementPage
                  typeSimulation={typeAConfigurer}
                  onAnnuler={() => setOngletActif("accueil")}
                  // Le démarrage mène droit au poste de pilotage : c'est le
                  // seul endroit d'où l'on déclenche un aléa.
                  onDemarre={() => allerAuCockpit()}
                />
              </RequireRole>
            )}

            {ongletActif === "bilan" && bilan && (
              <BilanExecutionPage
                simulationId={bilan.simulationId}
                frappes={bilan.frappes}
                onVoirQualite={() => setOngletActif("qualite")}
                onExporter={() => setOngletActif("rapports")}
                onAccueil={() => setOngletActif("accueil")}
              />
            )}

            {ongletActif === "injection" && (
              <RequireRole minimum="operateur">
                <ConsoleInjectionPage />
              </RequireRole>
            )}

            {ongletActif === "simulations" && (
              <SimulationsPage executionInitiale={executionOuverte} />
            )}

            {ongletActif === "qualite" && <QualitePage />}

            {ongletActif === "campagnes" && (
              <CampagnesPage
                campagneInitiale={campagneOuverte}
                onNouvelle={() => setOngletActif("campagne-nouvelle")}
              />
            )}

            {ongletActif === "campagne-nouvelle" && (
              <RequireRole minimum="operateur">
                <NouvelleCampagnePage
                  onAnnuler={() => setOngletActif("campagnes")}
                  onCreee={(campagneId) => {
                    setCampagneOuverte(campagneId);
                    setOngletActif("campagnes");
                  }}
                />
              </RequireRole>
            )}

            {ongletActif === "dashboard" && (
              <div className="dashboard-content-space">
                {/* Rangée 1 : Compteurs & KPIs SRE avec icônes SVG */}
                <TechMetricCards metrics={metrics} loading={loading} />

                {/* Rangée 2 : Graphiques de Concurrence & Latence */}
                <section className="dashboard-row-2">
                  <ChargeTraitementChart metrics={metrics} />
                  <LatencyPerformanceChart metrics={metrics} />
                </section>

                {/* Rangée 3 : Fiabilité & Test de Résilience */}
                {/* Le panneau d'anomalies a quitté cette page : la console
                    d'injection le remplace entièrement, et deux endroits pour
                    régler le même interrupteur se contrediraient. */}
                <section className="dashboard-row-3">
                  <SystemHealthDonut metrics={metrics} />
                  <ExecutionEnCoursCard />
                </section>

                {/* Rangée 4 : Terminal de Logs & Événements en Direct */}
                <section className="dashboard-row-4">
                  <LiveLogTerminal />
                </section>

                {/* Rangée 5 : Activité métier issue du snapshot KPI temps réel */}
                <ActiviteMetierSection />
              </div>
            )}

            {ongletActif === "rapports" && (
              <RequireRole minimum="operateur">
                <ReportsPage />
              </RequireRole>
            )}

            {ongletActif === "administration" && (
              <RequireRole minimum="administrateur">
                <AdministrationPage />
              </RequireRole>
            )}
          </div>
        </div>
      </div>
      )}
    </KpiSocketProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <DashboardShell />
    </AuthProvider>
  );
}