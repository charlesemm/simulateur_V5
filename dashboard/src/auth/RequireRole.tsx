import type { ReactNode } from "react";
import { useAuth } from "./AuthContext";

const HIERARCHY: Record<string, number> = { observateur: 0, operateur: 1, administrateur: 2 };

export function RequireRole({
  minimum,
  children,
  sinon = null,
}: {
  minimum: "administrateur" | "operateur" | "observateur";
  children: ReactNode;
  /** Ce qu'on affiche à qui n'a pas le rôle. Rien, par défaut.
   *  Utile quand la version en lecture seule vaut mieux qu'un trou. */
  sinon?: ReactNode;
}) {
  const { role } = useAuth();
  if (!role || HIERARCHY[role] < HIERARCHY[minimum]) return <>{sinon}</>;
  return <>{children}</>;
}