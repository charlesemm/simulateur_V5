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