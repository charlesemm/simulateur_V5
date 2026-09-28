// dashboard/src/components/clavier.ts
import type { KeyboardEvent } from "react";

/**
 * Rend activable au clavier un élément qui ne l'est pas d'origine — une
 * ligne de tableau cliquable, par exemple. Entrée et Espace y déclenchent
 * la même action que le clic ; sans cela, la souris était le seul accès.
 */
export function activableAuClavier(action: () => void) {
  return {
    tabIndex: 0,
    onKeyDown: (event: KeyboardEvent) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        action();
      }
    },
  };
}
