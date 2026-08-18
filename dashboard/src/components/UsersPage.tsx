import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "../auth/AuthContext";

interface UserRow {
  utilisateur_uuid: string;
  email: string;
  nom_complet: string;
  role: string;
  statut_actif: boolean;
}

const API_URL = import.meta.env.VITE_API_URL as string;
const ROLES = ["administrateur", "operateur", "observateur"] as const;

export function UsersPage() {
  const { token } = useAuth();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [email, setEmail] = useState("");
  const [nomComplet, setNomComplet] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [role, setRole] = useState<(typeof ROLES)[number]>("operateur");
  const [erreur, setErreur] = useState<string | null>(null);

  async function refresh() {
    const response = await fetch(`${API_URL}/users`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (response.ok) setUsers(await response.json());
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setErreur(null);
    const response = await fetch(`${API_URL}/users`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ email, mot_de_passe: motDePasse, nom_complet: nomComplet, role }),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      setErreur(detail?.detail ?? "Impossible de créer l'utilisateur.");
      return;
    }
    setEmail("");
    setNomComplet("");
    setMotDePasse("");
    await refresh();
  }

  async function toggleActif(user: UserRow) {
    await fetch(`${API_URL}/users/${user.utilisateur_uuid}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ statut_actif: !user.statut_actif }),
    });
    await refresh();
  }

  return (
    <div className="users-page">
      <h2>Gestion des utilisateurs</h2>

      <table className="users-table">
        <thead>
          <tr>
            <th>Nom</th><th>Email</th><th>Rôle</th><th>Statut</th><th></th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.utilisateur_uuid}>
              <td>{u.nom_complet}</td>
              <td>{u.email}</td>
              <td>{u.role}</td>
              <td>{u.statut_actif ? "Actif" : "Désactivé"}</td>
              <td>
                <button onClick={() => toggleActif(u)}>
                  {u.statut_actif ? "Désactiver" : "Réactiver"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <form className="users-form" onSubmit={handleCreate}>
        <h3>Nouvel utilisateur</h3>
        <input placeholder="Nom complet" value={nomComplet} onChange={(e) => setNomComplet(e.target.value)} required />
        <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input type="password" placeholder="Mot de passe" value={motDePasse} onChange={(e) => setMotDePasse(e.target.value)} required minLength={8} />
        <select value={role} onChange={(e) => setRole(e.target.value as typeof role)}>
          {ROLES.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
        {erreur && <p className="login-error">{erreur}</p>}
        <button type="submit">Créer</button>
      </form>
    </div>
  );
}