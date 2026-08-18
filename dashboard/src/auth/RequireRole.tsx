import type { ReactNode } from "react";
import { useAuth } from "./AuthContext";

const HIERARCHY: Record<string, number> = { observateur: 0, operateur: 1, administrateur: 2 };

export function RequireRole({
  minimum,
  children,
}: {
  minimum: "administrateur" | "operateur" | "observateur";
  children: ReactNode;
}) {
  const { role } = useAuth();
  if (!role || HIERARCHY[role] < HIERARCHY[minimum]) return null;
  return <>{children}</>;
}