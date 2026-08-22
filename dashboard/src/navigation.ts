// dashboard/src/navigation.ts
// Un seul endroit décrit les onglets : la barre latérale, l'en-tête et le
// routage d'App doivent parler du même jeu de valeurs.

export type Onglet =
  | "accueil"
  | "injection"
  | "simulations"
  | "qualite"
  | "donnees"
  | "rapports"
  | "dashboard"
  | "administration";

export const TITRES: Record<Onglet, { titre: string; sousTitre: string }> = {
  accueil: {
    titre: "Accueil",
    sousTitre: "Lancer une simulation et suivre les dernières exécutions",
  },
  injection: {
    titre: "Console d'injection",
    sousTitre: "Composer les anomalies et les scénarios d'aléa",
  },
  simulations: {
    titre: "Simulations",
    sousTitre: "Historique des exécutions et détail de ce qu'elles ont produit",
  },
  qualite: {
    titre: "Qualité",
    sousTitre: "Ce qui a été demandé, injecté, puis détecté",
  },
  donnees: {
    titre: "Données",
    sousTitre: "Assurés, factures et référentiels produits",
  },
  dashboard: {
    titre: "Supervision Technique",
    sousTitre: "Télémétrie en temps réel du moteur de simulation",
  },
  rapports: {
    titre: "Rapports & Exports",
    sousTitre: "Export par période, par exécution, et rapports quotidiens",
  },
  administration: {
    titre: "Administration",
    sousTitre: "Comptes, volumétrie des tables et purge des exécutions",
  },
};
