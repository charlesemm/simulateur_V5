import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { API_URL } from "../services/api";

type Role = "administrateur" | "operateur" | "observateur";

interface AuthState {
  token: string | null;
  role: Role | null;
  nomComplet: string | null;
}

interface AuthContextValue extends AuthState {
  login: (email: string, motDePasse: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);
const STORAGE_KEY = "cmu_dashboard_auth";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : { token: null, role: null, nomComplet: null };
  });

  useEffect(() => {
    if (state.token) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [state]);

  async function login(email: string, motDePasse: string) {
    const response = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, mot_de_passe: motDePasse }),
    });
    if (!response.ok) {
      throw new Error("Email ou mot de passe incorrect.");
    }
    const data = await response.json();
    setState({ token: data.access_token, role: data.role, nomComplet: data.nom_complet });
  }

  function logout() {
    setState({ token: null, role: null, nomComplet: null });
  }

  return (
    <AuthContext.Provider value={{ ...state, login, logout, isAuthenticated: state.token !== null }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth doit être utilisé sous AuthProvider.");
  return context;
}