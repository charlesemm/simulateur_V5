// Formatages partagés par les composants de l'activité métier.

/** Les montants CMU se comptent en francs CFA, sans décimale utile. */
export function formatMontant(montant: number): string {
  return `${Math.round(montant).toLocaleString("fr-FR")} F CFA`;
}

/** Un délai de traitement d'entente se lit mieux en minutes au-delà d'une. */
export function formatDelai(secondes: number | null): string {
  if (secondes === null) return "—";
  if (secondes < 60) return `${secondes.toFixed(1)} s`;
  return `${Math.floor(secondes / 60)} min ${Math.round(secondes % 60)} s`;
}
