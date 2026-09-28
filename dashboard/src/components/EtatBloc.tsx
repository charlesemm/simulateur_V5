// dashboard/src/components/EtatBloc.tsx
// Les quatre états qu'un écran peut avoir à annoncer, en un seul objet.
//
// Avant, chaque écran inventait les siens : six habillages pour l'erreur
// (dont deux oranges), six pour l'état vide, cinq façons de dire qu'on
// charge. L'utilisateur apprenait un vocabulaire différent par écran.
// Ici le ton change, la forme non.

import type { ReactNode } from "react";

export type TonEtat = "vide" | "chargement" | "erreur" | "succes";

interface EtatBlocProps {
  ton: TonEtat;
  /** Sans encadré : à l'intérieur d'un graphique ou d'une cellule. */
  discret?: boolean;
  /** Une icône au-dessus du message : pour un écran entièrement vide. */
  icone?: ReactNode;
  /** La phrase qui dit quoi faire, sous le message. */
  aide?: ReactNode;
  className?: string;
  children: ReactNode;
}

export function EtatBloc({
  ton,
  discret = false,
  icone,
  aide,
  className = "",
  children,
}: EtatBlocProps) {
  // Dès qu'il y a une icône ou une aide, le bloc s'empile au lieu de
  // tenir sur une ligne : c'est la forme longue de l'écran vide, celle
  // qui accueille quelqu'un qui n'a encore rien produit.
  const riche = Boolean(icone || aide);
  const classes = [
    "etat-bloc",
    `etat-bloc--${ton}`,
    discret ? "etat-bloc--discret" : "",
    riche ? "etat-bloc--riche" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={classes}
      // Une erreur interrompt ; un succès se signale sans voler le focus.
      role={ton === "erreur" ? "alert" : undefined}
      aria-live={ton === "succes" ? "polite" : undefined}
      aria-busy={ton === "chargement" ? true : undefined}
    >
      {ton === "chargement" && <span className="etat-pouls" aria-hidden="true" />}
      {icone && <span className="etat-bloc-icone" aria-hidden="true">{icone}</span>}
      <span>{children}</span>
      {aide && <span className="etat-bloc-aide">{aide}</span>}
    </div>
  );
}
