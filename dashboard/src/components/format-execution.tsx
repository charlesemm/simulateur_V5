// dashboard/src/components/format-execution.tsx
// Mise en forme commune aux écrans Accueil et Simulations : sans elle, les
// dates et les statuts d'une même exécution s'afficheraient différemment
// d'un écran à l'autre.

const LIBELLES_STATUT: Record<string, string> = {
  en_cours: "En cours",
  terminee: "Terminée",
  arretee: "Arrêtée",
  echouee: "Échouée",
};

export function StatutPastille({ statut }: { statut: string }) {
  return (
    <span className={`pastille pastille-${statut}`}>
      {LIBELLES_STATUT[statut] ?? statut}
    </span>
  );
}

/** Date et heure courtes, en français. */
export function dateCourte(valeur: string | null): string {
  if (!valeur) return "—";
  return new Date(valeur).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** Durée entre deux instants ; « en cours » tant que la fin manque. */
export function duree(debut: string, fin: string | null): string {
  if (!fin) return "en cours";
  const secondes = Math.max(
    0,
    Math.round((new Date(fin).getTime() - new Date(debut).getTime()) / 1000)
  );
  if (secondes < 60) return `${secondes} s`;
  const minutes = Math.floor(secondes / 60);
  if (minutes < 60) return `${minutes} min ${secondes % 60} s`;
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}
