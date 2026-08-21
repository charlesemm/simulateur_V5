import { useState, type FormEvent } from "react";
import { useAuth } from "./AuthContext";
import "./LoginPage.css";

const LONGUEUR_MINIMALE = 8;

/**
 * Écran imposé à la première connexion, tant que le mot de passe temporaire
 * n'a pas été remplacé. L'API refuse toute autre route dans cet état, il n'y
 * a donc rien d'autre à afficher.
 */
export function ChangePasswordPage() {
  const { changerMotDePasse, logout, nomComplet } = useAuth();
  const [actuel, setActuel] = useState("");
  const [nouveau, setNouveau] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setErreur(null);

    if (nouveau.length < LONGUEUR_MINIMALE) {
      setErreur(`Le nouveau mot de passe doit faire au moins ${LONGUEUR_MINIMALE} caractères.`);
      return;
    }
    if (nouveau !== confirmation) {
      setErreur("Les deux saisies ne correspondent pas.");
      return;
    }

    setEnCours(true);
    try {
      await changerMotDePasse(actuel, nouveau);
    } catch (echec) {
      setErreur(echec instanceof Error ? echec.message : "Le changement a échoué.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div className="lp-root">
      <div className="lp-bg">
        <div className="lp-orb lp-orb-1" />
        <div className="lp-orb lp-orb-2" />
        <div className="lp-grid" />
      </div>

      <div className="lp-form-col">
        <form className="lp-card" onSubmit={handleSubmit} noValidate>
          <div className="lp-card-header">
            <h2 className="lp-card-title">Nouveau mot de passe</h2>
            <p className="lp-card-sub">
              Bonjour {nomComplet ?? ""} — votre mot de passe a été généré
              automatiquement. Choisissez-en un avant de continuer.
            </p>
          </div>

          <div className="lp-fields">
            <div className="lp-field-group">
              <label className="lp-label" htmlFor="cp-actuel">
                Mot de passe temporaire
              </label>
              <div className="lp-input-wrap">
                <input
                  id="cp-actuel"
                  type="password"
                  className="lp-input"
                  value={actuel}
                  onChange={(e) => setActuel(e.target.value)}
                  required
                  autoComplete="current-password"
                />
              </div>
            </div>

            <div className="lp-field-group">
              <label className="lp-label" htmlFor="cp-nouveau">
                Nouveau mot de passe
              </label>
              <div className="lp-input-wrap">
                <input
                  id="cp-nouveau"
                  type="password"
                  className="lp-input"
                  value={nouveau}
                  onChange={(e) => setNouveau(e.target.value)}
                  required
                  minLength={LONGUEUR_MINIMALE}
                  autoComplete="new-password"
                />
              </div>
            </div>

            <div className="lp-field-group">
              <label className="lp-label" htmlFor="cp-confirmation">
                Confirmation
              </label>
              <div className="lp-input-wrap">
                <input
                  id="cp-confirmation"
                  type="password"
                  className="lp-input"
                  value={confirmation}
                  onChange={(e) => setConfirmation(e.target.value)}
                  required
                  autoComplete="new-password"
                />
              </div>
            </div>
          </div>

          {erreur && (
            <div className="lp-error" role="alert">
              {erreur}
            </div>
          )}

          <button type="submit" className={`lp-btn${enCours ? " lp-btn--loading" : ""}`} disabled={enCours}>
            {enCours ? "Enregistrement…" : "Enregistrer et continuer"}
          </button>

          <p className="lp-footer-note">
            <button type="button" className="lp-link-btn" onClick={logout}>
              Se déconnecter
            </button>
          </p>
        </form>
      </div>
    </div>
  );
}
