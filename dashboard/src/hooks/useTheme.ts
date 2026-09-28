// Thème de l'interface : préférence de l'utilisateur (système, clair,
// sombre), mémorisée dans le navigateur, et thème effectivement appliqué.
//
// Le thème résolu est posé sur <html data-theme="light|dark"> : toute la
// feuille de styles/tokens.css s'y accroche. Les graphiques, eux, en ont
// besoin en JavaScript — Recharts écrit ses couleurs en attributs SVG.
import { useSyncExternalStore } from "react";

export type PreferenceTheme = "systeme" | "clair" | "sombre";
export type ThemeResolu = "light" | "dark";

const CLE = "echo-theme";
const requeteSombre = "(prefers-color-scheme: dark)";

function lirePreference(): PreferenceTheme {
  try {
    const valeur = localStorage.getItem(CLE);
    if (valeur === "clair" || valeur === "sombre") return valeur;
  } catch {
    // Stockage indisponible (navigation privée stricte) : on suit le système.
  }
  return "systeme";
}

function systemeSombre(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.(requeteSombre).matches === true;
}

function resoudre(preference: PreferenceTheme): ThemeResolu {
  if (preference === "clair") return "light";
  if (preference === "sombre") return "dark";
  return systemeSombre() ? "dark" : "light";
}

let preference: PreferenceTheme = lirePreference();
let resolu: ThemeResolu = resoudre(preference);
const abonnes = new Set<() => void>();

function appliquer() {
  resolu = resoudre(preference);
  document.documentElement.dataset.theme = resolu;
  abonnes.forEach((prevenir) => prevenir());
}

/** À appeler une fois, avant le premier rendu : pas de flash de thème. */
export function initialiserTheme() {
  appliquer();
  window.matchMedia?.(requeteSombre).addEventListener("change", () => {
    if (preference === "systeme") appliquer();
  });
}

export function choisirTheme(nouvelle: PreferenceTheme) {
  preference = nouvelle;
  try {
    if (nouvelle === "systeme") localStorage.removeItem(CLE);
    else localStorage.setItem(CLE, nouvelle);
  } catch {
    // Le choix vaut pour la session, à défaut d'être mémorisé.
  }
  appliquer();
}

function sAbonner(prevenir: () => void) {
  abonnes.add(prevenir);
  return () => abonnes.delete(prevenir);
}

/** Préférence choisie et thème effectivement appliqué. */
export function useTheme() {
  const pref = useSyncExternalStore(sAbonner, () => preference, () => preference);
  const theme = useSyncExternalStore(sAbonner, () => resolu, () => resolu);
  return { preference: pref, theme, choisirTheme };
}
