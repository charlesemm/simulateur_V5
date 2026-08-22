// dashboard/src/components/DonneesPage.tsx
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { API_URL, api } from "../services/api";
import type { AssureFiche, AssureListe, HealthCenterList } from "../types";
import "./Screens.css";

type Volet = "assures" | "factures" | "centres";

interface FactureListe {
  total: number;
  factures: Array<{
    facture_numero: string;
    facture_date_soins: string;
    type_facture_code: string;
    centre_denomination: string | null;
    assure_nom_complet: string;
    regime_code: string | null;
    statut_courant: string | null;
    montant_depense: number;
  }>;
}

const PAGE = 25;

/**
 * W5 — Données.
 *
 * Trois volets pour regarder ce qui est en base : les assurés du référentiel,
 * les factures produites, et les centres de santé. C'est la vitrine des jeux
 * de données, celle qu'on ouvre pour vérifier de ses yeux.
 */
export function DonneesPage() {
  const { token } = useAuth();
  const [volet, setVolet] = useState<Volet>("assures");
  const [erreur, setErreur] = useState<string | null>(null);

  const [recherche, setRecherche] = useState("");
  const [page, setPage] = useState(0);
  const [assures, setAssures] = useState<AssureListe | null>(null);
  const [fiche, setFiche] = useState<AssureFiche | null>(null);

  const [factures, setFactures] = useState<FactureListe | null>(null);
  const [centres, setCentres] = useState<HealthCenterList | null>(null);

  const charger = useCallback(async () => {
    try {
      if (volet === "assures") {
        setAssures(await api.getAssures(token, recherche, PAGE, page * PAGE));
      } else if (volet === "centres") {
        setCentres(await api.getCenters(token));
      } else {
        const reponse = await fetch(`${API_URL}/factures?limite=${PAGE}&decalage=${page * PAGE}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!reponse.ok) throw new Error(`Factures indisponibles (${reponse.status}).`);
        setFactures((await reponse.json()) as FactureListe);
      }
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    }
  }, [token, volet, recherche, page]);

  useEffect(() => {
    void charger();
  }, [charger]);

  // Changer de volet remet la pagination et la fiche ouverte à zéro : sans
  // cela, on arrive page 4 d'une liste qui n'en compte qu'une.
  function ouvrirVolet(suivant: Volet) {
    setVolet(suivant);
    setPage(0);
    setFiche(null);
  }

  async function ouvrirFiche(personneUuid: string) {
    try {
      setFiche(await api.getAssure(personneUuid, token));
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    }
  }

  const total =
    volet === "assures" ? assures?.total ?? 0
      : volet === "factures" ? factures?.total ?? 0
        : centres?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE));

  return (
    <div className="screen">
      {erreur && <p className="screen-error">{erreur}</p>}

      <section>
        <div className="onglets">
          {([
            ["assures", "Assurés"],
            ["factures", "Factures"],
            ["centres", "Centres de santé"],
          ] as Array<[Volet, string]>).map(([code, libelle]) => (
            <button
              key={code}
              className={`onglet${volet === code ? " actif" : ""}`}
              onClick={() => ouvrirVolet(code)}
            >
              {libelle}
            </button>
          ))}
        </div>
      </section>

      {volet === "assures" && (
        <section>
          <div className="alea-carte" style={{ marginBottom: 14 }}>
            <input
              className="champ-console"
              style={{ maxWidth: 420 }}
              placeholder="Nom, prénoms, numéro de sécurité sociale…"
              value={recherche}
              onChange={(evenement) => {
                setRecherche(evenement.target.value);
                setPage(0);
              }}
            />
            <span className="alea-code">{total} assuré(s)</span>
          </div>

          {assures && assures.assures.length > 0 ? (
            <div className="screen-table-wrap">
              <table className="screen-table">
                <thead>
                  <tr>
                    <th>Nom</th>
                    <th>Prénoms</th>
                    <th>Numéro</th>
                    <th>Naissance</th>
                    <th>Régime</th>
                    <th>Droits du mois</th>
                  </tr>
                </thead>
                <tbody>
                  {assures.assures.map((assure) => (
                    <tr
                      key={assure.personne_uuid}
                      className={`cliquable${
                        fiche?.personne_uuid === assure.personne_uuid ? " selectionnee" : ""
                      }`}
                      onClick={() => void ouvrirFiche(assure.personne_uuid)}
                    >
                      <td>{assure.nom}</td>
                      <td>{assure.prenoms ?? "—"}</td>
                      <td>{assure.numero_secu}</td>
                      <td>{assure.date_naissance ?? "—"}</td>
                      <td>{assure.regime_code ?? "—"}</td>
                      <td>
                        <span
                          className={`pastille pastille-${
                            assure.droits_ouverts ? "en_cours" : "arretee"
                          }`}
                        >
                          {assure.droits_ouverts ? "ouverts" : "fermés"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="screen-empty">Aucun assuré ne correspond.</div>
          )}
        </section>
      )}

      {volet === "factures" && (
        <section>
          {factures && factures.factures.length > 0 ? (
            <div className="screen-table-wrap">
              <table className="screen-table">
                <thead>
                  <tr>
                    <th>Numéro</th>
                    <th>Date des soins</th>
                    <th>Assuré</th>
                    <th>Centre</th>
                    <th>Régime</th>
                    <th>Statut</th>
                    <th>Dépensé</th>
                  </tr>
                </thead>
                <tbody>
                  {factures.factures.map((facture) => (
                    <tr key={facture.facture_numero}>
                      <td>{facture.facture_numero}</td>
                      <td>{facture.facture_date_soins}</td>
                      <td>{facture.assure_nom_complet}</td>
                      <td>{facture.centre_denomination ?? "—"}</td>
                      <td>{facture.regime_code ?? "—"}</td>
                      <td>{facture.statut_courant ?? "—"}</td>
                      <td>{facture.montant_depense}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="screen-empty">
              Aucune facture. Lancez une simulation depuis l'accueil.
            </div>
          )}
        </section>
      )}

      {volet === "centres" && (
        <section>
          {centres && centres.centres.length > 0 ? (
            <div className="screen-table-wrap">
              <table className="screen-table">
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Dénomination</th>
                    <th>Type</th>
                    <th>Immatriculation</th>
                  </tr>
                </thead>
                <tbody>
                  {centres.centres.map((centre) => (
                    <tr key={centre.centre_sante_code}>
                      <td>{centre.centre_sante_code}</td>
                      <td>{centre.denomination}</td>
                      <td>{centre.type_code ?? "—"}</td>
                      <td>{centre.numero_immatriculation}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="screen-empty">Aucun centre de santé au référentiel.</div>
          )}
        </section>
      )}

      {volet !== "centres" && pages > 1 && (
        <div className="pagination">
          <button
            className="btn btn-outline"
            disabled={page === 0}
            onClick={() => setPage((actuelle) => actuelle - 1)}
          >
            Précédent
          </button>
          <span className="alea-code">
            Page {page + 1} sur {pages}
          </span>
          <button
            className="btn btn-outline"
            disabled={page + 1 >= pages}
            onClick={() => setPage((actuelle) => actuelle + 1)}
          >
            Suivant
          </button>
        </div>
      )}

      {fiche && volet === "assures" && (
        <section>
          <h2 className="screen-section-title">Fiche de l'assuré</h2>
          <article className="fiche">
            <div className="fiche-tete">
              <div>
                <div className="fiche-titre">
                  {fiche.nom} {fiche.prenoms ?? ""}
                </div>
                <div className="fiche-identifiant">{fiche.personne_uuid}</div>
              </div>
              <span className="alea-code">{fiche.factures} facture(s)</span>
            </div>

            <div className="stat-strip">
              <div className="stat-tile">
                <span className="stat-tile-label">Numéro de sécurité sociale</span>
                <span className="stat-tile-value" style={{ fontSize: "1.1rem" }}>
                  {fiche.numero_secu}
                </span>
              </div>
              <div className="stat-tile">
                <span className="stat-tile-label">Régime</span>
                <span className="stat-tile-value" style={{ fontSize: "1.1rem" }}>
                  {fiche.regime_code ?? "—"}
                </span>
              </div>
              <div className="stat-tile">
                <span className="stat-tile-label">Naissance</span>
                <span className="stat-tile-value" style={{ fontSize: "1.1rem" }}>
                  {fiche.date_naissance ?? "—"}
                </span>
                <span className="stat-tile-hint">{fiche.lieu_naissance ?? ""}</span>
              </div>
            </div>

            <h3 className="screen-section-title" style={{ marginTop: 22 }}>
              Droits, mois par mois
            </h3>
            <div className="pastilles-droits">
              {fiche.droits.length === 0 && <span className="alea-code">Aucun droit enregistré</span>}
              {fiche.droits.map((droit) => (
                <span
                  key={`${droit.annee}-${droit.mois}`}
                  className={`pastille pastille-${droit.ouverts ? "en_cours" : "arretee"}`}
                >
                  {String(droit.mois).padStart(2, "0")}/{droit.annee}
                </span>
              ))}
            </div>

            <h3 className="screen-section-title" style={{ marginTop: 22 }}>
              Professions successives
            </h3>
            <div className="screen-table-wrap">
              <table className="screen-table">
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Début</th>
                    <th>Fin</th>
                  </tr>
                </thead>
                <tbody>
                  {fiche.professions.map((profession) => (
                    <tr key={`${profession.code}-${profession.date_debut}`}>
                      <td>{profession.code}</td>
                      <td>{profession.date_debut.slice(0, 10)}</td>
                      <td>{profession.date_fin?.slice(0, 10) ?? "en cours"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </section>
      )}
    </div>
  );
}
