// dashboard/src/components/FilEtapes.tsx
// Le fil d'étapes, commun aux deux parcours de configuration.
//
// Les deux partent des mêmes cartes de l'accueil et promettent la même
// chose — régler, puis lancer — mais l'un s'annonçait en trois étapes
// numérotées et l'autre en une page muette : on ne savait pas, sur le
// second, combien il restait à faire.
//
// Le modèle d'interaction, lui, reste propre à chaque écran. La nouvelle
// campagne avance vraiment d'étape en étape ; le lancement garde sa page
// unique, où les réglages restent tous visibles pendant qu'on les ajuste,
// et le fil n'y sert que de repère : il dit où l'on se trouve et permet
// d'y revenir d'un clic.

interface FilEtapesProps {
  etapes: readonly string[];
  /** Rang de l'étape courante, à partir de 1. */
  courante: number;
  /** Fourni quand le fil sert à naviguer plutôt qu'à décrire une progression. */
  onAller?: (rang: number) => void;
}

export function FilEtapes({ etapes, courante, onAller }: FilEtapesProps) {
  return (
    <ol className="fil-etapes">
      {etapes.map((libelle, index) => {
        const rang = index + 1;
        const classes = [
          "fil-etape",
          rang === courante ? "fil-etape--active" : "",
          rang < courante ? "fil-etape--faite" : "",
          onAller ? "fil-etape--cliquable" : "",
        ]
          .filter(Boolean)
          .join(" ");

        const contenu = (
          <>
            <span className="fil-etape-rang">{rang}</span>
            <span className="fil-etape-libelle">{libelle}</span>
          </>
        );

        return (
          <li key={libelle} className={classes} aria-current={rang === courante ? "step" : undefined}>
            {onAller ? (
              <button type="button" className="fil-etape-bouton" onClick={() => onAller(rang)}>
                {contenu}
              </button>
            ) : (
              contenu
            )}
          </li>
        );
      })}
    </ol>
  );
}
