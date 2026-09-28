// Messages éphémères : la confirmation qu'une action a porté, sans quitter l'écran.
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { CloseIcon } from "../components/Icons";

type Ton = "succes" | "erreur" | "alerte" | "info";

interface Toast {
  id: number;
  ton: Ton;
  titre: string;
  detail?: string;
}

interface ToastContextValue {
  /** Affiche un message quelques secondes. Une erreur reste deux fois plus longtemps. */
  toast: (ton: Ton, titre: string, detail?: string) => void;
}

// Assez pour lire une phrase, pas assez pour encombrer.
const DUREE_MS = 4500;
// Au-delà, les plus anciens cèdent la place : une rafale ne couvre pas l'écran.
const MAXIMUM = 4;

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const suivant = useRef(1);

  const retirer = useCallback((id: number) => {
    setToasts((liste) => liste.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback((ton: Ton, titre: string, detail?: string) => {
    const id = suivant.current++;
    setToasts((liste) => [...liste, { id, ton, titre, detail }].slice(-MAXIMUM));
    setTimeout(() => retirer(id), ton === "erreur" ? DUREE_MS * 2 : DUREE_MS);
  }, [retirer]);

  const value = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* Deux régions : une erreur s'annonce aussitôt, le reste attend que
          le lecteur d'écran ait fini sa phrase. */}
      <div className="ui-toasts">
        <div role="alert" aria-live="assertive" className="ui-toasts-pile">
          {toasts.filter((t) => t.ton === "erreur").map((t) => (
            <ToastCarte key={t.id} toast={t} onFermer={retirer} />
          ))}
        </div>
        <div role="status" aria-live="polite" className="ui-toasts-pile">
          {toasts.filter((t) => t.ton !== "erreur").map((t) => (
            <ToastCarte key={t.id} toast={t} onFermer={retirer} />
          ))}
        </div>
      </div>
    </ToastContext.Provider>
  );
}

function ToastCarte({ toast, onFermer }: { toast: Toast; onFermer: (id: number) => void }) {
  return (
    <div className={`ui-toast ui-toast--${toast.ton}`}>
      <div className="ui-toast-corps">
        <strong className="ui-toast-titre">{toast.titre}</strong>
        {toast.detail && <span className="ui-toast-detail">{toast.detail}</span>}
      </div>
      <button
        type="button"
        className="ui-toast-fermer"
        onClick={() => onFermer(toast.id)}
        aria-label="Fermer le message"
      >
        <CloseIcon size={16} />
      </button>
    </div>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast doit être utilisé dans ToastProvider.");
  return context;
}
