// dashboard/src/components/EchoLogo.tsx

interface EchoLogoProps {
  /** Côté du carré, en pixels. Le tracé est vectoriel : toute taille convient. */
  size?: number;
  /** Ajoutée à l'élément racine, pour animer les ondes là où c'est souhaité. */
  className?: string;
  /** Rend le dégradé unique dans la page : deux logos afficheraient sinon le même. */
  id?: string;
}

/**
 * Marque d'ÉCHO : une source pleine, et trois ondes qui s'en éloignent.
 *
 * Le système réel émet, ÉCHO renvoie l'onde — d'où le noyau opaque et les
 * anneaux qui s'estompent. Le tracé est en ligne dans le composant plutôt que
 * dans un fichier image : il suit la taille demandée sans perte, se colore
 * depuis le même dégradé que le reste de l'interface, et évite une requête.
 */
export function EchoLogo({ size = 64, className = "", id = "echo" }: EchoLogoProps) {
  const degrade = `${id}-degrade`;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label="ÉCHO"
    >
      <defs>
        <linearGradient id={degrade} x1="8" y1="8" x2="56" y2="56" gradientUnits="userSpaceOnUse">
          <stop stopColor="#16a34a" />
          <stop offset="1" stopColor="#0284c7" />
        </linearGradient>
      </defs>

      {/* Onde la plus lointaine : la plus large et la plus effacée. */}
      <circle
        className="echo-ring echo-ring-3"
        cx="32" cy="32" r="27"
        stroke={`url(#${degrade})`} strokeWidth="2" opacity="0.22"
      />
      <circle
        className="echo-ring echo-ring-2"
        cx="32" cy="32" r="20"
        stroke={`url(#${degrade})`} strokeWidth="2.5" opacity="0.45"
      />
      <circle
        className="echo-ring echo-ring-1"
        cx="32" cy="32" r="13"
        stroke={`url(#${degrade})`} strokeWidth="3" opacity="0.75"
      />

      {/* Onde supplémentaire, invisible tant qu'aucune feuille de style ne
          l'anime : la marque reste entière partout, et seule la page de
          connexion la fait se propager. */}
      <circle
        className="echo-pulse"
        cx="32" cy="32" r="13"
        stroke={`url(#${degrade})`} strokeWidth="3" opacity="0"
      />

      {/* La source : le système réel, dont tout le reste n'est que l'écho. */}
      <circle cx="32" cy="32" r="6.5" fill={`url(#${degrade})`} />
    </svg>
  );
}
