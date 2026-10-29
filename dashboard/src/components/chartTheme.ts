// Style commun des graphiques Recharts : les cartes de l'activité métier
// doivent rester visuellement identiques aux graphiques de télémétrie.
//
// Recharts écrit ses couleurs en attributs SVG, où une variable CSS ne se
// résout pas partout : les valeurs sont donc recopiées ici, en miroir exact
// des jetons de styles/tokens.css. Toute retouche de la charte se reporte ici.
import { createElement, type CSSProperties } from "react";
import { useTheme } from "../hooks/useTheme";

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

/**
 * Thème sombre : mêmes rôles, nuances choisies sur le fond de carte sombre
 * (#0a2c40) et validées à part — pas une inversion automatique.
 *
 * Réussite / échec : aucun couple vert-orange ne tient à la fois la bande
 * de clarté du sombre et l'écart deutéranope. On garde donc la paire
 * bleu-orange, validée sans réserve (ΔE 23 en protanopie). La légende
 * « Passages réussis / échoués » nomme toujours chaque part : la couleur
 * n'est jamais seule à porter le sens.
 */
export const SERIE_SOMBRE = {
  bleu: "#3a9ad9",
  vert: "#4caf2a",
  orange: "#c97a2a",
} as const;

export const ETAT_SOMBRE = {
  reussite: "#3a9ad9",
  echec: "#c97a2a",
} as const;

/** Couleurs de série et d'état du thème appliqué, plus la teinte du fond
 *  de carte, pour l'anneau qui détache un point ou un secteur. */
export function usePaletteGraphique() {
  const { theme } = useTheme();
  return theme === "dark"
    ? { serie: SERIE_SOMBRE, etat: ETAT_SOMBRE, fond: "#0a2c40" }
    : { serie: SERIE, etat: ETAT, fond: "#ffffff" };
}

/**
 * Habillage du graphique : grille, axes, curseur — tout en retrait.
 *
 * Valeurs du thème clair. Recharts les pose en attributs SVG ; en thème
 * sombre, styles/supervision.css les reprend par des règles CSS, qui
 * l'emportent sur les attributs.
 */
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

// Infobulle, libellé, légende : du HTML, pas du SVG — les variables CSS
// s'y résolvent, et suivent donc le thème clair ou sombre.
export const TOOLTIP_STYLE: CSSProperties = {
  background: "var(--couleur-surface)",
  border: "1px solid var(--couleur-bord)",
  borderRadius: "10px",
  boxShadow: "var(--ombre-3)",
  fontSize: "13px",
  color: "var(--couleur-texte)",
};

/** Libellé de l'infobulle (l'heure, la catégorie) : lisible, pas criard. */
export const TOOLTIP_LIBELLE: CSSProperties = {
  color: "var(--couleur-texte-doux)",
  fontWeight: 600,
  marginBottom: 4,
};

/** Légende : texte en encre, jamais à la couleur de la série. */
export const LEGENDE_STYLE: CSSProperties = {
  fontSize: "13px",
  color: "var(--couleur-texte-doux)",
  paddingTop: 8,
};

/**
 * Libellé de légende en encre. Recharts l'écrit sinon à la couleur de la
 * série : « Capacité max », en gris clair, devenait presque illisible. La
 * pastille ou le trait à côté porte l'identité ; le texte, lui, doit se lire.
 */
export function legendeEnEncre(valeur: string) {
  return createElement("span", { style: { color: "var(--couleur-texte-doux)" } }, valeur);
}
