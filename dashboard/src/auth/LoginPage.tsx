import { useState, type FormEvent } from "react";
import logoCnam from "../assets/logo.png";
import { EchoLogo } from "../components/EchoLogo";
import { useAuth } from "./AuthContext";
import "./LoginPage.css";

export function LoginPage() {
  const { login } = useAuth();
  const [identifiant, setIdentifiant] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setErreur(null);
    setEnCours(true);
    try {
      await login(identifiant, motDePasse);
    } catch (raison) {
      // On affiche la raison telle qu'elle remonte. L'écraser par un message
      // unique faisait passer une API éteinte ou un serveur en panne pour un
      // mot de passe erroné : on cherchait la faute dans son clavier pendant
      // que la panne était ailleurs.
      setErreur(
        raison instanceof Error ? raison.message : "La connexion a échoué."
      );
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div className="lp-root">
      {/* Fond animé avec particules */}
      <div className="lp-bg">
        <div className="lp-orb lp-orb-1" />
        <div className="lp-orb lp-orb-2" />
        <div className="lp-orb lp-orb-3" />
        <div className="lp-grid" />
      </div>

      {/* Colonne gauche — Branding */}
      <div className="lp-brand">
        <div className="lp-brand-content">
          <div className="lp-logo-wrap">
            <EchoLogo size={110} className="lp-logo-mark" id="lp" />
            {/* Le logo CNAM est sur fond blanc : une pastille claire le
                pose sur le fond sombre sans le dénaturer. */}
            <span className="lp-cnam-pastille">
              <img src={logoCnam} alt="Caisse Nationale d'Assurance Maladie" />
            </span>
          </div>
          <h1 className="lp-brand-title">
            <span className="lp-brand-name lp-brand-highlight">ÉCHO</span><br />
            <span className="lp-brand-org">CNAM-CI</span>
          </h1>
          <p className="lp-brand-desc">
            Le système réel parle, ÉCHO en renvoie l'écho : générateur de jeux
            de données du parcours assuré CMU, destinés aux outils du service.
          </p>
          <div className="lp-stats">
            <div className="lp-stat">
              <span className="lp-stat-value">MDM</span>
              <span className="lp-stat-label">Référentiel</span>
            </div>
            <div className="lp-stat-divider" />
            <div className="lp-stat">
              <span className="lp-stat-value">Entrepôt</span>
              <span className="lp-stat-label">Données</span>
            </div>
            <div className="lp-stat-divider" />
            <div className="lp-stat">
              <span className="lp-stat-value">Qualité</span>
              <span className="lp-stat-label">Gouvernance</span>
            </div>
          </div>
        </div>
      </div>

      {/* Colonne droite — Formulaire */}
      <div className="lp-form-col">
        <form className="lp-card" onSubmit={handleSubmit} noValidate>
          {/* Header formulaire */}
          <div className="lp-card-header">
            <div className="lp-badge">
              <span className="lp-badge-dot" />
              Système opérationnel
            </div>
            <h2 className="lp-card-title">Connexion</h2>
            <p className="lp-card-sub">Accédez à votre espace ÉCHO</p>
          </div>

          {/* Champs */}
          <div className="lp-fields">
            <div className="lp-field-group">
              <label className="lp-label" htmlFor="lp-email">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                  <polyline points="22,6 12,13 2,6"/>
                </svg>
                E-mail ou nom d'utilisateur
              </label>
              <div className="lp-input-wrap">
                <input
                  id="lp-email"
                  type="text"
                  className="lp-input"
                  placeholder="votre@email.ci ou n.utilisateur"
                  value={identifiant}
                  onChange={(e) => setIdentifiant(e.target.value)}
                  required
                  autoComplete="username"
                />
              </div>
            </div>

            <div className="lp-field-group">
              <label className="lp-label" htmlFor="lp-password">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
                Mot de passe
              </label>
              <div className="lp-input-wrap">
                <input
                  id="lp-password"
                  type={showPassword ? "text" : "password"}
                  className="lp-input"
                  placeholder="••••••••"
                  value={motDePasse}
                  onChange={(e) => setMotDePasse(e.target.value)}
                  required
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="lp-eye-btn"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Masquer" : "Afficher"}
                  tabIndex={-1}
                >
                  {showPassword ? (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                      <line x1="1" y1="1" x2="23" y2="23"/>
                    </svg>
                  ) : (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                      <circle cx="12" cy="12" r="3"/>
                    </svg>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Erreur */}
          {erreur && (
            <div className="lp-error" role="alert">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="15" y1="9" x2="9" y2="15"/>
                <line x1="9" y1="9" x2="15" y2="15"/>
              </svg>
              {erreur}
            </div>
          )}

          {/* Bouton */}
          <button type="submit" className={`lp-btn${enCours ? " lp-btn--loading" : ""}`} disabled={enCours}>
            {enCours ? (
              <>
                <span className="lp-spinner" />
                Vérification en cours…
              </>
            ) : (
              <>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
                  <polyline points="10 17 15 12 10 7"/>
                  <line x1="15" y1="12" x2="3" y2="12"/>
                </svg>
                Accéder à ÉCHO
              </>
            )}
          </button>

          {/* Footer */}
          <p className="lp-footer-note">
            Accès réservé aux agents autorisés CNAM-CI<br />
            <span>ÉCHO · © 2026</span>
          </p>
        </form>
      </div>
    </div>
  );
}