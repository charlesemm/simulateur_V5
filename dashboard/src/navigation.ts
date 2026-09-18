// dashboard/src/navigation.ts
// Un seul endroit décrit les onglets : la barre latérale, l'en-tête et le
// routage d'App doivent parler du même jeu de valeurs.

export type Onglet =
  | "accueil"
  | "lancement"
  | "encours"
  | "bilan"
  | "injection"
  | "simulations"
  | "qualite"
  | "campagnes"
  | "campagne-nouvelle"
  | "rapports"
  | "dashboard"
  | "administration"
  | "explorateur-api";

export const TITRES: Record<Onglet, { titre: string; sousTitre: string }> = {
  accueil: {
    titre: "Vue d'ensemble",
    sousTitre: "Lancez une simulation et retrouvez l'activité récente",
  },
  injection: {
    titre: "Scénarios & anomalies",
    sousTitre: "Préparez les données atypiques et les aléas à simuler",
  },
  simulations: {
    titre: "Historique des simulations",
    sousTitre: "Consultez les exécutions et leurs résultats détaillés",
  },
  lancement: {
    titre: "Nouvelle simulation",
    sousTitre: "Définissez le scénario, la cadence et les anomalies à injecter",
  },
  bilan: {
    titre: "Bilan d'exécution",
    sousTitre: "Ce que la simulation a produit, avant de l'analyser ou de l'exporter",
  },
  encours: {
    titre: "Pilotage en direct",
    sousTitre: "Suivez le moteur et déclenchez les aléas au bon moment",
  },
  qualite: {
    titre: "Contrôle qualité",
    sousTitre: "Comparez les anomalies demandées, injectées et détectées",
  },
  campagnes: {
    titre: "Campagnes de test",
    sousTitre: "Éprouvez un outil de qualité des données avec un jeu piégé",
  },
  "campagne-nouvelle": {
    titre: "Nouvelle campagne",
    sousTitre: "Volume à générer et graine de reproduction",
  },
  dashboard: {
    titre: "Supervision technique",
    sousTitre: "Surveillez la santé et les performances du moteur en temps réel",
  },
  rapports: {
    titre: "Rapports & exports",
    sousTitre: "Générez des synthèses par période ou par exécution",
  },
  administration: {
    titre: "Administration",
    sousTitre: "Comptes, volumétrie des tables et purge des exécutions",
  },
  "explorateur-api": {
    titre: "Explorateur API",
    sousTitre: "Toutes les routes de l'API, leur description et un banc de test",
  },
};
