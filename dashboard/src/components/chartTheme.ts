// Style commun des graphiques Recharts : les cartes de l'activité métier
// doivent rester visuellement identiques aux graphiques de télémétrie.
//
// Recharts écrit ses couleurs en attributs SVG, où une variable CSS ne se
// résout pas partout : les valeurs sont donc recopiées ici, en miroir exact
// des jetons de styles/tokens.css. Toute retouche de la charte se reporte ici.
import { createElement, type CSSProperties } from "react";

/**
 * Couleurs de série.
 *
 * Les teintes du logo (vert #4caf2a, orange #f07800) tiennent moins de 3:1
 * sur fond blanc : un trait de 2 px s'y perd. On prend leur nuance « encre »,
 * même teinte, un cran plus sombre.
 */
export const SERIE = {
  /** Bleu CNAM — série principale d'un graphique à une seule série. */
  bleu: "#0088ce",
  /** Vert encre — la charge du moteur. */
  vert: "#3a8620",
  /** Orange encre — la seconde série d'une comparaison (latence). */
  orange: "#ba5d00",
} as const;

/**
 * Réussite / échec, côte à côte dans un même graphique.
 *
 * Le vert et l'orange de la charte se confondent pour un œil deutéranope
 * (ΔE 4,8, sous le plancher de 6) : réussis et échoués devenaient une seule
 * masse. Cette paire garde les deux teintes mais les écarte en clarté —
 * ΔE 9,7 en protanopie, 27 en vision normale, les deux au-dessus de 3:1
 * sur fond blanc (validée par le script du skill dataviz).
 */
export const ETAT = {
  reussite: "#2a6f15",
  echec: "#d9731a",
} as const;

/** Habillage du graphique : grille, axes, curseur — tout en retrait. */
export const HABILLAGE = {
  grille: "#e4eef4",
  axe: "#cfe3ee",
  /** Graduations : 4,6:1 sur le fond de carte, lisibles à distance. */
  graduation: "#5b7480",
  /** Libellés de catégories (axe des barres) : encre secondaire. */
  libelle: "#506874",
  curseur: "#f2f8fb",
  /** Ligne de référence (capacité, seuil) : présente, jamais au premier plan. */
  reference: "#a9c1cd",
} as const;

export const GRADUATION = { fontSize: 12, fill: HABILLAGE.graduation };
export const GRADUATION_LIBELLE = { fontSize: 12, fill: HABILLAGE.libelle };

export const TOOLTIP_STYLE: CSSProperties = {
  background: "#ffffff",
  border: "1px solid #cfe3ee",
  borderRadius: "10px",
  boxShadow: "0 14px 36px rgba(0, 80, 124, 0.12), 0 4px 10px rgba(0, 136, 206, 0.08)",
  fontSize: "13px",
  color: "#123041",
};

/** Libellé de l'infobulle (l'heure, la catégorie) : lisible, pas criard. */
export const TOOLTIP_LIBELLE: CSSProperties = {
  color: "#506874",
  fontWeight: 600,
  marginBottom: 4,
};

/** Légende : texte en encre, jamais à la couleur de la série. */
export const LEGENDE_STYLE: CSSProperties = {
  fontSize: "13px",
  color: "#506874",
  paddingTop: 8,
};

/**
 * Libellé de légende en encre. Recharts l'écrit sinon à la couleur de la
 * série : « Capacité max », en gris clair, devenait presque illisible. La
 * pastille ou le trait à côté porte l'identité ; le texte, lui, doit se lire.
 */
export function legendeEnEncre(valeur: string) {
  return createElement("span", { style: { color: "#506874" } }, valeur);
}
