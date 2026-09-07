// Centralise les appels HTTP, le typage et les messages d'erreur français.

import type {
  CadenceMoteur, Campagne, Corrige, DimensionQualite, ExecutionDetail,
  FicheGouvernance, FormatExport, HealthCenterList, PalierCampagne,
  ProgressionCampagne,
  RapportExecution, TypeAnomalieCampagne,
  InjectionJournal, KpiHistory, KpiSnapshot, PaireMdm, ProfilSimulation,
  RapportQualite, ScenarioAlea, SimulationRun, SimulationStatus, TypeAnomalie,
} from "../types";

/**
 * Adresse de l'API.
 *
 * En production, **vide** : toutes les requêtes deviennent relatives et
 * partent vers l'origine qui a servi la page. C'est ce qui permet au même
 * paquet compilé de fonctionner derrière n'importe quelle adresse — une IP
 * interne, un nom de machine, un domaine — sans être recompilé.
 *
 * Une adresse en dur ici serait figée au moment du `npm run build` : le
 * navigateur d'un utilisateur appellerait `127.0.0.1`, c'est-à-dire sa propre
 * machine, et l'application serait inutilisable pour tout le monde sauf pour
 * qui la consulte depuis le serveur lui-même.
 *
 * En développement, Vite sert l'interface sur son port et l'API vit ailleurs :
 * il faut donc l'adresse complète. `VITE_API_URL` reste prioritaire dans les
 * deux cas, pour les montages particuliers.
 */
export const API_URL =
  (import.meta.env.VITE_API_URL as string | undefined)
  ?? (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");

function authHeaders(token: string | null): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    const message = detail?.detail ?? `Erreur HTTP ${response.status}`;
    if (response.status === 401) {
      // Un jeton refusé ferme la session : sans ce signal, l'interface
      // restait sur un tableau de bord vide en répétant la même erreur.
      window.dispatchEvent(new CustomEvent("echo:session-expiree"));
      throw new Error(
        typeof message === "string" && message !== "Not authenticated"
          ? message
          : "Session expirée — reconnectez-vous."
      );
    }
    throw new Error(typeof message === "string" ? message : `Erreur HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  /** KPI – lecture seule, endpoint public */
  async getSnapshot(token: string | null, signal?: AbortSignal): Promise<KpiSnapshot> {
    const response = await fetch(`${API_URL}/kpi/snapshot`, {
      headers: authHeaders(token),
      signal,
    });
    return parseOrThrow<KpiSnapshot>(response);
  },

   async getPassageHistory(token: string | null, signal?: AbortSignal): Promise<KpiHistory> {
    const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    const response = await fetch(
      `${API_URL}/kpi/passages/history?since=${encodeURIComponent(since)}&granularite=heure`,
      { headers: authHeaders(token), signal }
    );
    return parseOrThrow<KpiHistory>(response);
  },

  /** Centres de santé – lecture seule, endpoint public */
   async getCenters(token: string | null, signal?: AbortSignal): Promise<HealthCenterList> {
    const response = await fetch(`${API_URL}/centres-sante`, {
      headers: authHeaders(token),
      signal,
    });
    return parseOrThrow<HealthCenterList>(response);
  },

  /** Simulation – lecture seule, endpoint public */
  async getSimulationStatus(token: string | null = null): Promise<SimulationStatus> {
    const response = await fetch(`${API_URL}/simulation/status`, {
      headers: authHeaders(token),
    });
    return parseOrThrow<SimulationStatus>(response);
  },

  /** Simulation – endpoints protégés (nécessitent un token JWT) */
  async startSimulation(
    vitesse: number | null = null,
    nombrePassagesSimultanesMax: number | null = null,
    token: string | null = null,
    typeSimulation: string | null = null
  ): Promise<SimulationStatus> {
    // Les champs nuls sont omis : l'API applique alors le réglage du profil.
    const corps: Record<string, unknown> = {};
    if (vitesse !== null) corps.vitesse = vitesse;
    if (nombrePassagesSimultanesMax !== null) {
      corps.nombre_passages_simultanes_max = nombrePassagesSimultanesMax;
    }
    if (typeSimulation !== null) corps.type_simulation = typeSimulation;

    const response = await fetch(`${API_URL}/simulation/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify(corps),
    });
    return parseOrThrow<SimulationStatus>(response);
  },

  /** Démarrage paramétré : nom, cadence, anomalies et aléas de cette exécution. */
  async demarrerSimulation(
    token: string | null,
    parametres: {
      type_simulation: string;
      libelle?: string;
      vitesse?: number;
      nombre_passages_simultanes_max?: number;
      duree_visee_minutes?: number;
      anomalies?: Record<string, Record<string, unknown>>;
      aleas?: Record<string, Record<string, unknown>>;
    }
  ): Promise<SimulationStatus> {
    const response = await fetch(`${API_URL}/simulation/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify(parametres),
    });
    return parseOrThrow<SimulationStatus>(response);
  },

  /** Les quatre types de simulation et leur réglage par défaut. */
  async getProfils(token: string | null): Promise<ProfilSimulation[]> {
    const response = await fetch(`${API_URL}/simulation/profils`, {
      headers: authHeaders(token),
    });
    return parseOrThrow<ProfilSimulation[]>(response);
  },

  /** Les quatre paliers de charge du banc d'essai. */
  async getPaliers(token: string | null): Promise<PalierCampagne[]> {
    const response = await fetch(`${API_URL}/campagnes/paliers`, {
      headers: authHeaders(token),
    });
    return parseOrThrow<PalierCampagne[]>(response);
  },

  /** Les formats dans lesquels le jeu d'une campagne peut être téléchargé. */
  async getFormatsExport(token: string | null): Promise<FormatExport[]> {
    const response = await fetch(`${API_URL}/campagnes/formats`, {
      headers: authHeaders(token),
    });
    return parseOrThrow<FormatExport[]>(response);
  },

  /**
   * Télécharge le jeu d'une campagne et le remet au navigateur.
   *
   * Une simple balise `<a href>` ne conviendrait pas : la route exige un
   * jeton, et le navigateur n'en joint aucun à une navigation ordinaire. On
   * récupère donc le fichier par `fetch`, on en fait un objet local, et on
   * déclenche l'enregistrement sur un lien fabriqué pour l'occasion.
   *
   * Le nom du fichier vient de l'en-tête `Content-Disposition` : c'est le
   * serveur qui le décide, pas l'écran.
   */
  async telechargerJeu(
    campagneId: string,
    format: string,
    token: string | null
  ): Promise<void> {
    const response = await fetch(
      `${API_URL}/campagnes/${campagneId}/export?format=${encodeURIComponent(format)}`,
      { headers: authHeaders(token) }
    );
    if (!response.ok) {
      // Le corps d'une erreur est du JSON, pas le fichier attendu : il porte
      // le motif du refus, qui doit remonter tel quel à l'écran.
      let motif = `Téléchargement refusé (${response.status}).`;
      try {
        const corps = await response.json();
        if (corps?.detail) motif = String(corps.detail);
      } catch {
        // Réponse illisible : le message par défaut suffit.
      }
      throw new Error(motif);
    }

    const entete = response.headers.get("Content-Disposition") ?? "";
    const trouve = /filename="([^"]+)"/.exec(entete);
    const nom = trouve ? trouve[1] : `campagne-${campagneId}.${format}`;

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const lien = document.createElement("a");
    lien.href = url;
    lien.download = nom;
    document.body.appendChild(lien);
    lien.click();
    lien.remove();
    // Sans cette libération, le fichier resterait en mémoire tant que l'onglet
    // est ouvert — et un gros jeu s'y ferait sentir.
    URL.revokeObjectURL(url);
  },

  /** Les huit dimensions de qualité, et ce que chacune éprouve. */
  async getDimensions(token: string | null): Promise<DimensionQualite[]> {
    const response = await fetch(`${API_URL}/campagnes/dimensions`, {
      headers: authHeaders(token),
    });
    return parseOrThrow<DimensionQualite[]>(response);
  },

  /** Les types d'anomalies qu'une campagne peut poser. */
  async getTypesCampagne(token: string | null): Promise<TypeAnomalieCampagne[]> {
    const response = await fetch(`${API_URL}/campagnes/anomalies`, {
      headers: authHeaders(token),
    });
    return parseOrThrow<TypeAnomalieCampagne[]>(response);
  },

  /** Les libellés français des statuts de campagne, tenus par le serveur. */
  async getStatutsCampagne(token: string | null): Promise<Record<string, string>> {
    const response = await fetch(`${API_URL}/campagnes/statuts`, {
      headers: authHeaders(token),
    });
    return parseOrThrow<Record<string, string>>(response);
  },

  /** La référence que porterait la prochaine campagne, sans la réserver. */
  async getProchaineReference(token: string | null): Promise<string> {
    const response = await fetch(`${API_URL}/campagnes/prochaine-reference`, {
      headers: authHeaders(token),
    });
    const corps = await parseOrThrow<{ reference: string }>(response);
    return corps.reference;
  },

  /** Ouvre une campagne. Rien n'est généré à ce stade. */
  async creerCampagne(
    token: string | null,
    corps: {
      palier?: string;
      volume_cible?: number;
      graine?: number | null;
      anomalies?: Record<string, { taux: number }>;
    }
  ): Promise<Campagne> {
    const response = await fetch(`${API_URL}/campagnes`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify(corps),
    });
    return parseOrThrow<Campagne>(response);
  },

  async getCampagnes(token: string | null, limite = 50): Promise<Campagne[]> {
    const response = await fetch(`${API_URL}/campagnes?limite=${limite}`, {
      headers: authHeaders(token),
    });
    return parseOrThrow<Campagne[]>(response);
  },

  async getCampagne(campagneId: string, token: string | null): Promise<Campagne> {
    const response = await fetch(`${API_URL}/campagnes/${campagneId}`, {
      headers: authHeaders(token),
    });
    return parseOrThrow<Campagne>(response);
  },

  /** Lance la production du jeu piégé. Retourne aussitôt : la suite se suit
   *  par `getProgression`. */
  async genererCampagne(
    campagneId: string, token: string | null
  ): Promise<ProgressionCampagne> {
    const response = await fetch(`${API_URL}/campagnes/${campagneId}/generer`, {
      method: "POST",
      headers: authHeaders(token),
    });
    return parseOrThrow<ProgressionCampagne>(response);
  },

  async getProgression(
    campagneId: string, token: string | null
  ): Promise<ProgressionCampagne> {
    const response = await fetch(
      `${API_URL}/campagnes/${campagneId}/progression`,
      { headers: authHeaders(token) }
    );
    return parseOrThrow<ProgressionCampagne>(response);
  },

  async getCorrige(
    campagneId: string, token: string | null, limite = 50, decalage = 0
  ): Promise<Corrige> {
    const response = await fetch(
      `${API_URL}/campagnes/${campagneId}/corrige`
      + `?limite=${limite}&decalage=${decalage}`,
      { headers: authHeaders(token) }
    );
    return parseOrThrow<Corrige>(response);
  },

  /** Les exécutions d'une journée et les rapports déjà produits pour chacune. */
  async getRapportsExecutions(
    jour: string, token: string | null
  ): Promise<RapportExecution[]> {
    const response = await fetch(
      `${API_URL}/reports/executions?jour=${encodeURIComponent(jour)}`,
      { headers: authHeaders(token) },
    );
    return parseOrThrow<RapportExecution[]>(response);
  },

  async getCadence(token: string | null): Promise<CadenceMoteur> {
    const response = await fetch(`${API_URL}/simulation/cadence`, {
      headers: authHeaders(token),
    });
    return parseOrThrow<CadenceMoteur>(response);
  },

  async getExecutions(token: string | null, limite = 50): Promise<SimulationRun[]> {
    const response = await fetch(`${API_URL}/simulation/executions?limite=${limite}`, {
      headers: authHeaders(token),
    });
    return parseOrThrow<SimulationRun[]>(response);
  },

  async getExecution(simulationId: string, token: string | null): Promise<ExecutionDetail> {
    const response = await fetch(`${API_URL}/simulation/executions/${simulationId}`, {
      headers: authHeaders(token),
    });
    return parseOrThrow<ExecutionDetail>(response);
  },

  async getAleas(token: string | null): Promise<ScenarioAlea[]> {
    const response = await fetch(`${API_URL}/simulation/aleas`, {
      headers: authHeaders(token),
    });
    return parseOrThrow<ScenarioAlea[]>(response);
  },

  /** Dépose un ordre pour le moteur en cours : armer, désarmer, déclencher. */
  async commander(ordre: string, cible: string, token: string | null): Promise<{ message: string }> {
    const response = await fetch(`${API_URL}/simulation/commandes`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify({ ordre, cible }),
    });
    return parseOrThrow<{ message: string }>(response);
  },

  /** Catalogue d'anomalies – administrateur */
  async getCatalogue(token: string | null): Promise<TypeAnomalie[]> {
    const response = await fetch(`${API_URL}/anomalies/catalogue`, {
      headers: authHeaders(token),
    });
    return parseOrThrow<TypeAnomalie[]>(response);
  },

  async modifierTypeAnomalie(
    code: string,
    reglage: Partial<{ active: boolean; taux: number; declenchement: string; delai_secondes: number }>,
    token: string | null
  ): Promise<TypeAnomalie> {
    const response = await fetch(`${API_URL}/anomalies/catalogue/${code}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify(reglage),
    });
    return parseOrThrow<TypeAnomalie>(response);
  },

  async getJournalAnomalies(
    token: string | null,
    simulationId: string | null = null,
    limite = 100
  ): Promise<InjectionJournal[]> {
    const filtre = simulationId ? `&simulation_id=${simulationId}` : "";
    const response = await fetch(`${API_URL}/anomalies/journal?limite=${limite}${filtre}`, {
      headers: authHeaders(token),
    });
    return parseOrThrow<InjectionJournal[]>(response);
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

  /** Qualité des données (T1) et vérité terrain du rapprochement (T2) */
  async getRapportQualite(
    token: string | null,
    simulationId: string | null = null,
    inclureReferentiel = true
  ): Promise<RapportQualite> {
    const filtre = simulationId ? `simulation_id=${simulationId}&` : "";
    const response = await fetch(
      `${API_URL}/qualite/rapport?${filtre}inclure_referentiel=${inclureReferentiel}`,
      { headers: authHeaders(token) }
    );
    return parseOrThrow<RapportQualite>(response);
  },

  async getVeriteTerrain(
    token: string | null,
    simulationId: string | null = null
  ): Promise<PaireMdm[]> {
    const filtre = simulationId ? `?simulation_id=${simulationId}` : "";
    const response = await fetch(`${API_URL}/mdm/verite-terrain${filtre}`, {
      headers: authHeaders(token),
    });
    return parseOrThrow<PaireMdm[]>(response);
  },

  /** Gouvernance (T4) – volumétrie par table du catalogue */
  async getVolumetrie(token: string | null): Promise<FicheGouvernance[]> {
    const response = await fetch(`${API_URL}/gouvernance/volumetrie`, {
      headers: authHeaders(token),
    });
    return parseOrThrow<FicheGouvernance[]>(response);
  },

  /** Volumétrie et purge d'une exécution – administrateur */
  async previsualiserPurge(
    simulationId: string,
    token: string | null
  ): Promise<Record<string, number>> {
    const response = await fetch(
      `${API_URL}/simulation/executions/${simulationId}/purge`,
      { headers: authHeaders(token) }
    );
    return parseOrThrow<Record<string, number>>(response);
  },

  async purgerExecution(
    simulationId: string,
    token: string | null
  ): Promise<Record<string, number>> {
    const response = await fetch(
      `${API_URL}/simulation/executions/${simulationId}/donnees`,
      { method: "DELETE", headers: authHeaders(token) }
    );
    return parseOrThrow<Record<string, number>>(response);
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

  async exporterPeriode(
    dateMin: string,
    dateMax: string,
    token: string | null
  ): Promise<{ excel: string }> {
    const response = await fetch(
      `${API_URL}/reports/periode?date_min=${dateMin}&date_max=${dateMax}`,
      { method: "POST", headers: authHeaders(token) }
    );
    return parseOrThrow<{ excel: string }>(response);
  },

  async exporterExecution(
    simulationId: string,
    token: string | null
  ): Promise<{ pdf: string; excel: string }> {
    const response = await fetch(`${API_URL}/reports/execution/${simulationId}`, {
      method: "POST",
      headers: authHeaders(token),
    });
    return parseOrThrow<{ pdf: string; excel: string }>(response);
  },

  async viderRapports(token: string | null): Promise<{ supprimes: number }> {
    const response = await fetch(`${API_URL}/reports`, {
      method: "DELETE",
      headers: authHeaders(token),
    });
    return parseOrThrow<{ supprimes: number }>(response);
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
  async getTechnicalMetrics(
    token: string | null,
    signal?: AbortSignal
  ): Promise<import("../types").TechnicalMetricsSnapshot> {
    const response = await fetch(`${API_URL}/metrics/technical`, {
      headers: authHeaders(token),
      signal,
    });
    return parseOrThrow<import("../types").TechnicalMetricsSnapshot>(response);
  },

  async resetTechnicalMetrics(token: string | null = null): Promise<{ message: string }> {
    const response = await fetch(`${API_URL}/metrics/technical/reset`, {
      method: "POST",
      headers: authHeaders(token),
    });
    return parseOrThrow<{ message: string }>(response);
  },
};
