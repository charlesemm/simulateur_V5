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

/**
 * Dit si un jeton JWT a dépassé sa date d'expiration.
 *
 * Un jeton ne vit que huit heures. Sans cette vérification au démarrage,
 * l'application se croyait connectée avec un jeton mort : elle affichait le
 * tableau de bord, chaque appel retournait 401, et rien ne ramenait jamais
 * l'écran de connexion. On paraissait connecté sans l'être.
 */
function jetonExpire(token: string | null): boolean {
  if (!token) return true;
  try {
    const charge = JSON.parse(
      atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))
    ) as { exp?: number };
    if (!charge.exp) return false;
    return charge.exp * 1000 <= Date.now();
  } catch {
    // Un jeton illisible est un jeton inutilisable.
    return true;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return ETAT_VIDE;
    const enregistre = { ...ETAT_VIDE, ...JSON.parse(raw) } as AuthState;
    return jetonExpire(enregistre.token) ? ETAT_VIDE : enregistre;
  });

  useEffect(() => {
    if (state.token) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [state]);

  // L'API signale un jeton refusé ; la session se ferme alors d'elle-même et
  // l'écran de connexion revient, plutôt que de laisser un tableau de bord
  // couvert de messages d'erreur.
  useEffect(() => {
    function fermerLaSession() {
      setState(ETAT_VIDE);
    }
    window.addEventListener("echo:session-expiree", fermerLaSession);
    return () => window.removeEventListener("echo:session-expiree", fermerLaSession);
  }, []);

  async function login(identifiant: string, motDePasse: string) {
    let response: Response;
    try {
      response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifiant, mot_de_passe: motDePasse }),
      });
    } catch {
      // Sans cette distinction, une API éteinte s'annonçait « mot de passe
      // incorrect » : on cherchait la faute dans son clavier.
      throw new Error(
        `Le serveur ne répond pas (${API_URL}). Vérifiez que l'API est démarrée.`
      );
    }

    if (response.status === 401) {
      throw new Error("Identifiant ou mot de passe incorrect.");
    }
    if (!response.ok) {
      throw new Error(
        `Connexion impossible : le serveur a répondu ${response.status}.`
      );
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
    // Changer le mot de passe révoque tous les jetons émis avant, y compris
    // celui qui vient de servir : l'API en rend un nouveau, qu'on adopte.
    const data = await response.json();
    setState((precedent) => ({
      ...precedent,
      token: data.access_token,
      doitChangerMotDePasse: data.doit_changer_mot_de_passe === true,
    }));
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