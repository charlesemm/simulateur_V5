// Décrit exactement les payloads REST et Socket.IO de l'API CMU.
export type ConnectionStatus = "connexion" | "connecte" | "reconnexion" | "deconnecte";

export interface AgreementRate { nombre: number; pourcentage: number }
export interface AmountPair { cmu: number; assure: number }

export interface KpiSnapshot {
  generated_at: string;
  window: { hours: number; from: string; to: string };
  passages: { en_cours: number; clotures: number; total: number };
  actes_repartition: Array<{ type: string; nombre: number; pourcentage: number }>;
  ententes: {
    global: Record<string, AgreementRate>;
    par_centre: Record<string, Record<string, number>>;
    delai_moyen_secondes: { medecin_conseil: number | null; validation_office: number | null };
  };
  montants: { cumule: AmountPair; par_centre: Record<string, AmountPair> };
  top_pathologies: Array<{ code: string; libelle: string; nombre: number }>;
  charge_centres: Array<{ centre_sante_code: string; passages_actifs: number }>;
}

export interface HistoryPoint { timestamp: string; value: number }
export interface KpiHistory { kpi_name: string; granularite: string; since: string; points: HistoryPoint[] }
export interface KpiUpdate { changed: string[]; data: KpiSnapshot }

export interface SimulationStatus {
  etat: "en_cours" | "arrete";
  vitesse: number;
  passages_actifs: number;
  passages_simultanes_max: number;
  simulation_id: string | null;
  type_simulation: string | null;
  passages_interrompus: number;
}

/** Une exécution enregistrée du moteur. */
export interface SimulationRun {
  simulation_id: string;
  simulation_libelle: string;
  simulation_statut: "en_cours" | "terminee" | "arretee" | "echouee";
  simulation_type: string | null;
  simulation_parametres: Record<string, unknown>;
  simulation_date_debut: string;
  simulation_date_fin: string | null;
  utilisateur_uuid: string | null;
  passages_reussis: number;
  passages_echoues: number;
}

export interface ExecutionDetail {
  execution: SimulationRun;
  volumetrie: Record<string, number>;
  anomalies_par_type: Record<string, number>;
}

/** Un des quatre types de simulation, avec son réglage par défaut. */
export interface ProfilSimulation {
  code: string;
  libelle: string;
  description: string;
  couleur: string;
  vitesse: number;
  passages_simultanes_max: number;
  anomalies: Record<string, Record<string, unknown>>;
  aleas: Record<string, Record<string, unknown>>;
}

/** Une exécution d'une journée donnée, avec les rapports produits pour elle.
 *
 *  Les fichiers portent l'identifiant technique de l'exécution ; c'est le
 *  serveur qui les rapproche du nom donné au départ, seul repère utilisable. */
export interface RapportExecution {
  simulation_id: string;
  simulation_libelle: string;
  simulation_type: string | null;
  simulation_statut: string;
  simulation_date_debut: string;
  simulation_date_fin: string | null;
  passages_reussis: number;
  fichiers: { pdf: string | null; excel: string | null; csv: string | null };
}

/** La cadence du moteur, servie par l'API pour projeter un volume.
 *
 *  L'écran de lancement ne peut pas la deviner : elle vit dans la
 *  configuration du moteur, et la recopier ici la ferait dériver. */
export interface CadenceMoteur {
  passage_arrival_mean_seconds: number;
  vitesse_par_defaut: number;
  passages_simultanes_max: number;
}

/** Une entrée du catalogue d'anomalies. */
export interface TypeAnomalie {
  anomalie_code: string;
  anomalie_libelle: string;
  anomalie_famille: string;
  anomalie_couleur: string;
  anomalie_table_cible: string;
  anomalie_colonne_cible: string;
  anomalie_severite: string;
  anomalie_active: boolean;
  anomalie_taux: number;
  anomalie_declenchement: string;
  anomalie_delai_secondes: number | null;
}

export interface InjectionJournal {
  injection_id: string;
  anomalie_code: string;
  simulation_id: string | null;
  passage_id: string | null;
  cible_cle: string | null;
  valeur_origine: string | null;
  valeur_injectee: string | null;
}

/** Un réglage propre à un aléa : taille de salve, latence, amplitude… */
export interface ReglageAlea {
  nom: string;
  libelle: string;
  unite: string;
  defaut: number;
  minimum: number;
  maximum: number;
}

export interface ScenarioAlea {
  code: string;
  libelle: string;
  /** Interruption, Charge ou Dérive — la nature colore le bouton. */
  nature: string;
  couleur: string;
  /** Vide pour les aléas qui n'ont rien à régler : ils frappent ou non. */
  parametres: ReglageAlea[];
}

/** Un événement de parcours diffusé en temps réel par le moteur. */
export interface EvenementParcours {
  type: string;
  passage_id: string;
  simulation_id: string | null;
  simulated_at: string;
  payload: Record<string, unknown>;
}

export interface PaquetParcours {
  evenements: EvenementParcours[];
  /** Événements écartés par le serveur pour ne pas noyer le navigateur. */
  ecartes: number;
}

/** Rapport du moteur de qualité (T1), avec sa confrontation. */
export interface RegleQualite {
  code: string;
  libelle: string;
  dimension: string;
  anomalie_visee: string | null;
  referentielle: boolean;
  constats: number;
  exemples: Array<{ cle: string; valeur: string }>;
}

export interface LigneConfrontation {
  anomalie_code: string;
  taux_demande_pourcent: number;
  injectees: number;
  detectees: number;
  taux_detection_pourcent: number | null;
  regles: string[];
}

export interface RapportQualite {
  simulation_id: string | null;
  genere_le: string;
  total_constats: number;
  par_dimension: Record<string, number>;
  regles: RegleQualite[];
  confrontation: LigneConfrontation[];
}

/** Une paire de la vérité terrain du rapprochement d'identités (T2). */
export interface PaireMdm {
  paire_id: string;
  simulation_id: string | null;
  personne_uuid_source: string;
  personne_uuid_variante: string;
  type_variation: string;
  meme_personne: boolean;
  commentaire: string | null;
}

/** Une fiche du catalogue de gouvernance, avec sa volumétrie. */
export interface FicheGouvernance {
  table: string;
  domaine: string;
  proprietaire: string;
  criticite: string;
  donnees_personnelles: boolean;
  lignes: number;
}

export interface HealthCenter {
  centre_sante_code: string;
  denomination: string;
  type_code: string | null;
  numero_immatriculation: string;
}

export interface HealthCenterList { total: number; centres: HealthCenter[] }

export interface TechnicalMetricsSnapshot {
  demarre_depuis: string;
  uptime_secondes: number;
  passages_reussis: number;
  passages_echoues: number;
  passages_total: number;
  taux_echec_pourcent: number;
  taux_succes_pourcent: number;
  debit_passages_par_sec: number;
  pic_passages_simultanes: number;
  evenements_totaux: number;
  debit_evenements_par_sec: number;
  recalculs_kpi: number;
  temps_moyen_recalcul_kpi_ms: number;
  derniere_duree_recalcul_kpi_ms: number;
  connexions_socketio_total: number;
  deconnexions_socketio_total: number;
  clients_socketio_actifs: number;
  requetes_api_total: number;
  temps_moyen_reponse_api_ms: number;
  derniere_latence_api_ms: number;
  debit_requetes_par_sec: number;
  memoire_rss_mo: number;
  moteur_etat: "en_cours" | "arrete";
  moteur_vitesse: number;
  passages_actifs: number;
  passages_simultanes_max: number;
}