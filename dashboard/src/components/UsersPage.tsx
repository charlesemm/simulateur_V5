import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../hooks/useToast";
import { API_URL } from "../services/api";
import { EtatBloc } from "./EtatBloc";

interface UserRow {
  utilisateur_uuid: string;
  email: string;
  nom_utilisateur: string | null;
  nom_complet: string;
  role: string;
  statut_actif: boolean;
  doit_changer_mot_de_passe: boolean;
}

const ROLES = ["administrateur", "operateur", "observateur"] as const;

/**
 * Tire un message lisible de la réponse d'erreur de l'API.
 *
 * FastAPI répond `detail` en **texte** pour nos refus métier (409, 404), mais
 * en **liste d'objets** dès que le corps ne valide pas — un e-mail sans point
 * après l'arobase, par exemple, que le navigateur laisse pourtant passer.
 * Poser cette liste telle quelle dans l'état faisait rendre un objet à React,
 * qui refuse : l'écran d'administration se vidait au lieu d'afficher la cause.
 */
function messageErreur(corps: unknown, defaut: string): string {
  const detail = (corps as { detail?: unknown } | null)?.detail;

  if (typeof detail === "string" && detail.trim() !== "") return detail;

  if (Array.isArray(detail)) {
    const messages = detail
      .map((entree) => (entree as { msg?: unknown } | null)?.msg)
      .filter((msg): msg is string => typeof msg === "string");
    if (messages.length > 0) return messages.join(" · ");
  }

  return defaut;
}

export function UsersPage() {
  const { token, email: emailConnecte } = useAuth();
  const { toast } = useToast();
  // Une liste vide avant la première réponse veut dire « pas encore ».
  const [chargee, setChargee] = useState(false);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [email, setEmail] = useState("");
  const [nomUtilisateur, setNomUtilisateur] = useState("");
  const [nomComplet, setNomComplet] = useState("");
  // Le mot de passe temporaire n'est lisible qu'une fois, dans la reponse de
  // creation : il n'existe nulle part ailleurs en clair.
  const [motDePasseTemporaire, setMotDePasseTemporaire] = useState<string | null>(null);
  const [role, setRole] = useState<(typeof ROLES)[number]>("operateur");
  const [erreur, setErreur] = useState<string | null>(null);
  const [succes, setSucces] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  // Compte dont la désactivation attend confirmation. « Désactiver » voisinait
  // « Réinitialiser », deux boutons minuscules et sans garde-fou : on éteignait
  // un compte en croyant lui refaire un mot de passe, et rien ne le disait.
  const [confirmExtinction, setConfirmExtinction] = useState<string | null>(null);
  // Même garde-fou pour la réinitialisation : en un clic, l'ancien mot de
  // passe cessait de fonctionner, et la personne se retrouvait à la porte.
  const [confirmReinit, setConfirmReinit] = useState<string | null>(null);
  // Et pour la suppression : irréversible, contrairement à la désactivation.
  const [confirmSuppression, setConfirmSuppression] = useState<string | null>(null);
  const [suppression, setSuppression] = useState<string | null>(null);

  async function refresh() {
    try {
      const response = await fetch(`${API_URL}/users`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const corps = await response.json().catch(() => null);
        // Sans ce message, une liste vide voulait dire aussi bien « aucun
        // compte » que « le jeton a expiré » — indiscernables à l'écran.
        setErreur(messageErreur(corps, `La liste des comptes n'a pas pu être lue (${response.status}).`));
        return;
      }
      setUsers(await response.json());
    } catch (raison) {
      setErreur((raison as Error).message);
    } finally {
      setChargee(true);
    }
  }

  /** Copie le mot de passe temporaire : le recopier à la main, c'est une faute de frappe assurée. */
  async function copierMotDePasse(valeur: string) {
    try {
      await navigator.clipboard.writeText(valeur);
      toast("succes", "Mot de passe copié", "Transmettez-le par un canal sûr.");
    } catch {
      toast("alerte", "Copie impossible", "Sélectionnez le mot de passe et copiez-le à la main.");
    }
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setErreur(null);
    setSucces(null);
    setMotDePasseTemporaire(null);
    setCreating(true);

    try {
      const response = await fetch(`${API_URL}/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          email,
          nom_utilisateur: nomUtilisateur,
          nom_complet: nomComplet,
          role,
        }),
      });

      if (!response.ok) {
        const corps = await response.json().catch(() => null);
        setErreur(messageErreur(corps, "Impossible de créer l'utilisateur."));
        return;
      }

      const cree = await response.json();
      setEmail("");
      setNomUtilisateur("");
      setNomComplet("");
      setMotDePasseTemporaire(cree.mot_de_passe_temporaire);
      setSucces(`Compte créé. Transmettez ce mot de passe à ${cree.utilisateur.nom_complet} :`);
      toast("succes", "Compte créé", cree.utilisateur.nom_complet);
      await refresh();
    } catch (err) {
      setErreur((err as Error).message);
    } finally {
      setCreating(false);
    }
  }

  async function toggleActif(user: UserRow) {
    setErreur(null);
    setSucces(null);
    setConfirmExtinction(null);
    const response = await fetch(`${API_URL}/users/${user.utilisateur_uuid}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ statut_actif: !user.statut_actif }),
    });
    if (!response.ok) {
      const corps = await response.json().catch(() => null);
      setErreur(messageErreur(
        corps, `Le statut de ${user.nom_complet} n'a pas pu être changé.`
      ));
      return;
    }
    // Une extinction silencieuse est précisément ce qui a fait perdre du temps :
    // le compte se taisait, et la connexion refusée n'en disait pas la cause.
    setSucces(user.statut_actif
      ? `${user.nom_complet} est désactivé : ses connexions seront refusées.`
      : `${user.nom_complet} est réactivé.`);
    // Le bouton est dans la liste, le message dans la colonne d'à côté :
    // le toast dit le résultat là où l'on regarde.
    toast(
      "succes",
      user.statut_actif ? "Compte désactivé" : "Compte réactivé",
      user.nom_complet,
    );
    await refresh();
  }

  async function reinitialiser(user: UserRow) {
    setConfirmReinit(null);
    setErreur(null);
    setSucces(null);
    setMotDePasseTemporaire(null);
    const response = await fetch(
      `${API_URL}/users/${user.utilisateur_uuid}/reinitialiser-mot-de-passe`,
      { method: "POST", headers: { Authorization: `Bearer ${token}` } },
    );
    if (!response.ok) {
      const corps = await response.json().catch(() => null);
      setErreur(messageErreur(corps, `La réinitialisation a échoué (${response.status}).`));
      return;
    }
    const resultat = await response.json();
    setMotDePasseTemporaire(resultat.mot_de_passe_temporaire);
    setSucces(`Mot de passe réinitialisé pour ${user.nom_complet} :`);
    toast("succes", "Mot de passe réinitialisé", "Le nouveau mot de passe s'affiche à droite.");
    await refresh();
  }

  async function supprimer(user: UserRow) {
    setConfirmSuppression(null);
    setErreur(null);
    setSucces(null);
    setSuppression(user.utilisateur_uuid);
    try {
      const response = await fetch(`${API_URL}/users/${user.utilisateur_uuid}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const corps = await response.json().catch(() => null);
        setErreur(messageErreur(corps, `${user.nom_complet} n'a pas pu être supprimé.`));
        return;
      }
      setSucces(`${user.nom_complet} a été supprimé définitivement.`);
      toast("succes", "Compte supprimé", user.nom_complet);
      await refresh();
    } finally {
      setSuppression(null);
    }
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
    <div className="page-container">
      <div className="page-header">
        <div>
          <h2 className="page-title">Gestion des Utilisateurs & Rôles</h2>
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

          <div className="screen-table-wrap">
            <table className="screen-table">
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
                        <div className="user-avatar-sm" aria-hidden="true">
                          {u.nom_complet.charAt(0).toUpperCase()}
                        </div>
                        <div className="user-text">
                          <strong className="user-name">{u.nom_complet}</strong>
                          <span className="user-email">
                            {u.nom_utilisateur ? `${u.nom_utilisateur} · ` : ""}
                            {u.email}
                          </span>
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
                      {u.doit_changer_mot_de_passe && (
                        <span className="status-pill pill-inactive">
                          Mot de passe temporaire
                        </span>
                      )}
                    </td>
                    <td>
                      <div className="user-actions">
                        {confirmSuppression === u.utilisateur_uuid ? (
                          <>
                            <button
                              type="button"
                              className="btn-action-toggle btn-disable"
                              onClick={() => void supprimer(u)}
                              aria-label={`Confirmer la suppression définitive de ${u.nom_complet}`}
                            >
                              Confirmer la suppression
                            </button>
                            <button
                              type="button"
                              className="btn-action-toggle btn-neutre"
                              onClick={() => setConfirmSuppression(null)}
                            >
                              Annuler
                            </button>
                          </>
                        ) : confirmReinit === u.utilisateur_uuid ? (
                          <>
                            <button
                              type="button"
                              className="btn-action-toggle btn-disable"
                              onClick={() => void reinitialiser(u)}
                              aria-label={`Confirmer la réinitialisation du mot de passe de ${u.nom_complet}`}
                            >
                              Confirmer la réinitialisation
                            </button>
                            <button
                              type="button"
                              className="btn-action-toggle btn-neutre"
                              onClick={() => setConfirmReinit(null)}
                            >
                              Annuler
                            </button>
                          </>
                        ) : confirmExtinction === u.utilisateur_uuid ? (
                          <>
                            <button
                              type="button"
                              className="btn-action-toggle btn-disable"
                              onClick={() => void toggleActif(u)}
                              aria-label={`Confirmer la désactivation de ${u.nom_complet}`}
                            >
                              Confirmer la désactivation
                            </button>
                            <button
                              type="button"
                              className="btn-action-toggle btn-neutre"
                              onClick={() => setConfirmExtinction(null)}
                            >
                              Annuler
                            </button>
                          </>
                        ) : (
                          <>
                            {/* Éteindre demande confirmation ; rallumer non —
                                seul le premier geste ferme une porte. */}
                            <button
                              type="button"
                              aria-label={`${u.statut_actif ? "Désactiver" : "Réactiver"} ${u.nom_complet}`}
                              className={`btn-action-toggle ${u.statut_actif ? "btn-disable" : "btn-enable"}`}
                              onClick={() => {
                                setConfirmReinit(null);
                                if (u.statut_actif) setConfirmExtinction(u.utilisateur_uuid);
                                else void toggleActif(u);
                              }}
                            >
                              {u.statut_actif ? "Désactiver" : "Réactiver"}
                            </button>
                            <button
                              type="button"
                              className="btn-action-toggle btn-neutre"
                              onClick={() => {
                                setConfirmExtinction(null);
                                setConfirmReinit(u.utilisateur_uuid);
                              }}
                              aria-label={`Réinitialiser le mot de passe de ${u.nom_complet}`}
                            >
                              Réinitialiser
                            </button>
                            {/* Son propre compte ne peut pas se supprimer lui-même :
                                l'API le refuserait, autant ne pas montrer le bouton.
                                Comparaison sur l'e-mail (toujours renseigné et unique),
                                pas le nom d'utilisateur (facultatif). */}
                            {u.email !== emailConnecte && (
                              <button
                                type="button"
                                className="btn-action-toggle btn-disable"
                                onClick={() => {
                                  setConfirmExtinction(null);
                                  setConfirmReinit(null);
                                  setConfirmSuppression(u.utilisateur_uuid);
                                }}
                                disabled={suppression === u.utilisateur_uuid}
                                aria-label={`Supprimer définitivement ${u.nom_complet}`}
                              >
                                Supprimer
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {!chargee && (
                  <tr>
                    <td colSpan={4} aria-busy="true">
                      <span className="ui-skeleton ui-skeleton--texte" style={{ width: "70%" }} />
                      <span className="ui-skeleton ui-skeleton--texte" style={{ width: "55%" }} />
                    </td>
                  </tr>
                )}
                {chargee && users.length === 0 && (
                  <tr>
                    <td colSpan={4}>
                      <EtatBloc ton="vide" discret>Aucun utilisateur trouvé.</EtatBloc>
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
            <p className="form-card-subtitle">
              Le mot de passe est généré automatiquement et remis une seule fois
            </p>
          </div>

          {erreur && <EtatBloc ton="erreur">{erreur}</EtatBloc>}
          {succes && <EtatBloc ton="succes">{succes}</EtatBloc>}
          {motDePasseTemporaire && (
            <div className="etat-bloc etat-bloc--succes bloc-mot-de-passe">
              <div className="temp-password-ligne">
                <code className="temp-password">{motDePasseTemporaire}</code>
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => void copierMotDePasse(motDePasseTemporaire)}
                >
                  Copier
                </button>
              </div>
              <span className="temp-password-note">
                Il ne sera plus affiché : notez-le maintenant. Son remplacement
                sera exigé à la première connexion.
              </span>
            </div>
          )}

          <form className="clean-form" onSubmit={handleCreate}>
            <div className="form-group">
              <label className="form-label" htmlFor="compte-nom-complet">Nom complet</label>
              <input
                id="compte-nom-complet"
                className="form-input"
                autoComplete="name"
                placeholder="Ex. : Jean Kouassi"
                value={nomComplet}
                onChange={(e) => setNomComplet(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="compte-email">Adresse e-mail</label>
              <input
                id="compte-email"
                type="email"
                className="form-input"
                autoComplete="email"
                placeholder="nom@cnam.ci"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="compte-identifiant">Nom d'utilisateur</label>
              <input
                id="compte-identifiant"
                className="form-input"
                autoComplete="username"
                placeholder="Ex. : j.kouassi"
                value={nomUtilisateur}
                onChange={(e) => setNomUtilisateur(e.target.value)}
                required
                minLength={3}
                maxLength={80}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="compte-role">Rôle attribué</label>
              <select
                id="compte-role"
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

            <button
              type="submit"
              className="btn btn-start btn-block"
              disabled={creating}
              aria-busy={creating}
            >
              {creating && (
                <span className="ui-spinner ui-spinner--petit ui-spinner--inverse" aria-hidden="true" />
              )}
              {creating ? "Création en cours…" : "Enregistrer le compte"}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}