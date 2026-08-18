import { useState, type FormEvent } from "react";
import { useAuth } from "./AuthContext";

export function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setErreur(null);
    setEnCours(true);
    try {
      await login(email, motDePasse);
    } catch {
      setErreur("Email ou mot de passe incorrect.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>Simulateur CMU</h1>
        <p>Connexion au tableau de bord</p>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Mot de passe
          <input
            type="password"
            value={motDePasse}
            onChange={(e) => setMotDePasse(e.target.value)}
            required
          />
        </label>
        {erreur && <p className="login-error">{erreur}</p>}
        <button type="submit" disabled={enCours}>
          {enCours ? "Connexion..." : "Se connecter"}
        </button>
      </form>
    </div>
  );
}