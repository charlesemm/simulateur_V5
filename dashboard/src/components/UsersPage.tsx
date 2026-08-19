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
  const [succes, setSucces] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

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
    setSucces(null);
    setCreating(true);

    try {
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
      setSucces("Compte créé avec succès !");
      await refresh();
    } catch (err) {
      setErreur((err as Error).message);
    } finally {
      setCreating(false);
    }
  }

  async function toggleActif(user: UserRow) {
    await fetch(`${API_URL}/users/${user.utilisateur_uuid}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ statut_actif: !user.statut_actif }),
    });
    await refresh();
  }

  function getRoleBadge(roleName: string) {
    switch (roleName) {
      case "administrateur":
        return "badge-blue";
      case "operateur":
        return "badge-green";
      default:
        return "badge-gray";
    }
  }

  return (
    <main className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Gestion des Utilisateurs & Rôles</h1>
          <p className="page-subtitle">
            Administration des comptes d'accès, permissions et statuts
          </p>
        </div>
      </div>

      <div className="users-layout-grid">
        {/* Colonne Gauche : Liste des utilisateurs */}
        <section className="users-table-card">
          <div className="card-table-header">
            <h2>Comptes enregistrés ({users.length})</h2>
          </div>

          <div className="table-wrapper">
            <table className="clean-table">
              <thead>
                <tr>
                  <th>Utilisateur</th>
                  <th>Rôle</th>
                  <th>Statut</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.utilisateur_uuid}>
                    <td>
                      <div className="user-cell">
                        <div className="user-avatar-sm">
                          {u.nom_complet.charAt(0).toUpperCase()}
                        </div>
                        <div className="user-text">
                          <strong className="user-name">{u.nom_complet}</strong>
                          <span className="user-email">{u.email}</span>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className={`role-badge ${getRoleBadge(u.role)}`}>
                        {u.role}
                      </span>
                    </td>
                    <td>
                      <span className={`status-pill ${u.statut_actif ? "pill-active" : "pill-inactive"}`}>
                        {u.statut_actif ? "Actif" : "Désactivé"}
                      </span>
                    </td>
                    <td>
                      <button
                        className={`btn-action-toggle ${u.statut_actif ? "btn-disable" : "btn-enable"}`}
                        onClick={() => toggleActif(u)}
                      >
                        {u.statut_actif ? "Désactiver" : "Réactiver"}
                      </button>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={4} className="table-empty">
                      Aucun utilisateur trouvé.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Colonne Droite : Formulaire de création */}
        <section className="users-form-card">
          <div className="form-card-header">
            <h2>Créer un utilisateur</h2>
            <p className="form-card-subtitle">Ajouter un nouveau collaborateur au simulateur</p>
          </div>

          {erreur && <div className="alert-box alert-error">{erreur}</div>}
          {succes && <div className="alert-box alert-success">{succes}</div>}

          <form className="clean-form" onSubmit={handleCreate}>
            <div className="form-group">
              <label className="form-label">Nom complet</label>
              <input
                className="form-input"
                placeholder="Ex: Jean Kouassi"
                value={nomComplet}
                onChange={(e) => setNomComplet(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Adresse email</label>
              <input
                type="email"
                className="form-input"
                placeholder="nom@cnam.ci"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Mot de passe</label>
              <input
                type="password"
                className="form-input"
                placeholder="Au moins 8 caractères"
                value={motDePasse}
                onChange={(e) => setMotDePasse(e.target.value)}
                required
                minLength={8}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Rôle attribué</label>
              <select
                className="form-select"
                value={role}
                onChange={(e) => setRole(e.target.value as typeof role)}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r.charAt(0).toUpperCase() + r.slice(1)}
                  </option>
                ))}
              </select>
            </div>

            <button type="submit" className="btn btn-start btn-block" disabled={creating}>
              {creating ? "Création en cours..." : "Enregistrer le compte"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}