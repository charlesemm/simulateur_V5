import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { API_URL } from "../services/api";

type Role = "administrateur" | "operateur" | "observateur";

interface AuthState {
  token: string | null;
  role: Role | null;
  nomComplet: string | null;
  nomUtilisateur: string | null;
  doitChangerMotDePasse: boolean;
}

interface AuthContextValue extends AuthState {
  login: (identifiant: string, motDePasse: string) => Promise<void>;
  changerMotDePasse: (actuel: string, nouveau: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const ETAT_VIDE: AuthState = {
  token: null,
  role: null,
  nomComplet: null,
  nomUtilisateur: null,
  doitChangerMotDePasse: false,
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);
const STORAGE_KEY = "cmu_dashboard_auth";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? { ...ETAT_VIDE, ...JSON.parse(raw) } : ETAT_VIDE;
  });

  useEffect(() => {
    if (state.token) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [state]);

  async function login(identifiant: string, motDePasse: string) {
    const response = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifiant, mot_de_passe: motDePasse }),
    });
    if (!response.ok) {
      throw new Error("Identifiant ou mot de passe incorrect.");
    }
    const data = await response.json();
    setState({
      token: data.access_token,
      role: data.role,
      nomComplet: data.nom_complet,
      nomUtilisateur: data.nom_utilisateur ?? null,
      doitChangerMotDePasse: data.doit_changer_mot_de_passe === true,
    });
  }

  // Tant que le drapeau est levé, l'API refuse toutes les autres routes :
  // c'est le seul appel possible dans cet état.
  async function changerMotDePasse(actuel: string, nouveau: string) {
    const response = await fetch(`${API_URL}/auth/change-password`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${state.token}`,
      },
      body: JSON.stringify({
        mot_de_passe_actuel: actuel,
        nouveau_mot_de_passe: nouveau,
      }),
    });
    if (!response.ok) {
      const corps = await response.json().catch(() => null);
      throw new Error(corps?.detail ?? "Le changement de mot de passe a échoué.");
    }
    setState((precedent) => ({ ...precedent, doitChangerMotDePasse: false }));
  }

  function logout() {
    setState(ETAT_VIDE);
  }

  return (
    <AuthContext.Provider
      value={{
        ...state,
        login,
        changerMotDePasse,
        logout,
        isAuthenticated: state.token !== null,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth doit être utilisé sous AuthProvider.");
  return context;
}