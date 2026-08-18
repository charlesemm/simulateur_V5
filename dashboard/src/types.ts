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