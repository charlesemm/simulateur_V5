// dashboard/src/components/CampagnesPage.tsx
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { RequireRole } from "../auth/RequireRole";
import { api } from "../services/api";
import type { Campagne, TypeAnomalieCampagne } from "../types";
import { FicheCampagne } from "./FicheCampagne";
import { dateCourte } from "./format-execution";
import "./Screens.css";

interface CampagnesPageProps {
  /** Campagne à ouvrir d'emblée, quand on arrive de sa création. */
  campagneInitiale?: string | null;
  onNouvelle: () => void;
}

function entier(valeur: number): string {
  return valeur.toLocaleString("fr-FR");
}

/**
 * M1 — Les campagnes de test, et la fiche de l'une d'elles.
 *
 * La liste est l'endroit où l'on retrouve une campagne « réalisée plusieurs
 * semaines auparavant », comme le demande le cahier des charges. D'où la
 * référence lisible en tête de chaque ligne : c'est elle qu'on cite, pas
 * l'identifiant technique.
 */
export function CampagnesPage({ campagneInitiale = null, onNouvelle }: CampagnesPageProps) {
  const { token } = useAuth();
  const [campagnes, setCampagnes] = useState<Campagne[]>([]);
  const [statuts, setStatuts] = useState<Record<string, string>>({});
  // Le catalogue donne aux codes rangés dans la campagne leur libellé et leur
  // dimension : sans lui, la fiche n'afficherait que des codes en majuscules.
  const [types, setTypes] = useState<TypeAnomalieCampagne[]>([]);
  const [selection, setSelection] = useState<string | null>(campagneInitiale);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(async () => {
    try {
      const [liste, libelles, catalogue] = await Promise.all([
        api.getCampagnes(token, 50),
        api.getStatutsCampagne(token),
        api.getTypesCampagne(token),
      ]);
      setCampagnes(liste);
      setStatuts(libelles);
      setTypes(catalogue);
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    }
  }, [token]);

  useEffect(() => {
    void charger();
  }, [charger]);

  useEffect(() => {
    setSelection(campagneInitiale);
  }, [campagneInitiale]);

  const ouverte = campagnes.find((candidate) => candidate.campagne_id === selection) ?? null;

  return (
    <div className="screen">
      {erreur && <p className="screen-error">{erreur}</p>}

      <section>
        <div className="screen-section-head">
          <h2 className="screen-section-title">Campagnes de test</h2>
          <RequireRole minimum="operateur">
            <button className="btn btn-start" onClick={onNouvelle}>
              Nouvelle campagne
            </button>
          </RequireRole>
        </div>
        <p className="screen-section-lead">
          Chaque campagne garde sa graine : c'est elle qui permet de la rejouer
          à l'identique, des semaines plus tard, pour comparer deux versions
          d'un même outil.
        </p>

        {campagnes.length === 0 ? (
          <div className="screen-empty">
            Aucune campagne pour l'instant. Créez-en une pour éprouver un outil
            de qualité des données.
          </div>
        ) : (
          <div className="screen-table-wrap">
            <table className="screen-table">
              <thead>
                <tr>
                  <th>Référence</th>
                  <th>Nom</th>
                  <th>Statut</th>
                  <th>Palier</th>
                  <th>Volume visé</th>
                  <th>Graine</th>
                  <th>Lignes</th>
                  <th>Empreinte</th>
                  <th>Créée le</th>
                </tr>
              </thead>
              <tbody>
                {campagnes.map((campagne) => (
                  <tr
                    key={campagne.campagne_id}
                    onClick={() => setSelection(campagne.campagne_id)}
                    className={`cliquable${
                      campagne.campagne_id === selection ? " selectionnee" : ""
                    }`}
                  >
                    <td>
                      <b>{campagne.campagne_reference}</b>
                    </td>
                    <td>{campagne.campagne_libelle}</td>
                    <td>
                      <span className={`pastille pastille-${campagne.campagne_statut}`}>
                        {statuts[campagne.campagne_statut] ?? campagne.campagne_statut}
                      </span>
                    </td>
                    <td>{campagne.campagne_palier}</td>
                    <td>{entier(campagne.campagne_volume_cible)}</td>
                    <td>{entier(campagne.campagne_graine)}</td>
                    <td>
                      {campagne.campagne_lignes_generees > 0
                        ? entier(campagne.campagne_lignes_generees)
                        : "—"}
                    </td>
                    <td className="cellule-empreinte">
                      {campagne.campagne_empreinte
                        ? campagne.campagne_empreinte.slice(0, 12)
                        : "—"}
                    </td>
                    <td>{dateCourte(campagne.date_creation)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {ouverte && (
        <section>
          <FicheCampagne
            campagne={ouverte}
            types={types}
            statuts={statuts}
            onChangement={() => void charger()}
          />
        </section>
      )}
    </div>
  );
}
