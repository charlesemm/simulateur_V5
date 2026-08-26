// dashboard/src/components/BilanExecutionPage.tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { api } from "../services/api";
import type { ExecutionDetail, TypeAnomalie } from "../types";
import { dateCourte, duree } from "./format-execution";
import "./Screens.css";

/** Un aléa frappé pendant l'exécution, tel que le poste de pilotage l'a vu. */
export interface FrappeBilan {
  code: string;
  libelle: string;
  nature: string;
  couleur: string;
  horodatage: Date;
}

interface BilanExecutionPageProps {
  simulationId: string;
  /** Les aléas frappés, transmis par le poste de pilotage qu'on vient de quitter. */
  frappes: FrappeBilan[];
  onVoirQualite: () => void;
  onExporter: () => void;
  onAccueil: () => void;
}

const NOMS_VOLUMETRIE: Record<string, string> = {
  factures: "Factures ouvertes",
  prestations: "Prestations servies",
  ententes: "Ententes préalables",
  evenements: "Événements journalisés",
  anomalies: "Anomalies posées",
  refus_accueil: "Refusés à l'accueil",
};

/**
 * Le bilan d'une exécution qui vient de se terminer.
 *
 * Sans lui, l'arrêt du moteur renvoyait sèchement à l'accueil : les chiffres
 * qu'on suivait en direct disparaissaient d'un coup, et il fallait aller les
 * repêcher dans l'historique. C'est le moment où l'on récolte, et il manquait.
 *
 * Il ne montre que ce qui se lit à froid, et propose les deux seules suites
 * qui aient un sens : vérifier la qualité, ou exporter.
 */
export function BilanExecutionPage({
  simulationId, frappes, onVoirQualite, onExporter, onAccueil,
}: BilanExecutionPageProps) {
  const { token } = useAuth();
  const [detail, setDetail] = useState<ExecutionDetail | null>(null);
  const [catalogue, setCatalogue] = useState<TypeAnomalie[]>([]);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(async () => {
    try {
      const [fiche, types] = await Promise.all([
        api.getExecution(simulationId, token),
        api.getCatalogue(token),
      ]);
      setDetail(fiche);
      setCatalogue(types);
      setErreur(null);
    } catch (raison) {
      setErreur((raison as Error).message);
    }
  }, [simulationId, token]);

  useEffect(() => {
    void charger();
  }, [charger]);

  const execution = detail?.execution ?? null;

  /** Les anomalies regroupées par famille, de la plus fournie à la plus rare. */
  const parFamille = useMemo(() => {
    const comptes = detail?.anomalies_par_type ?? {};
    const totaux: Record<string, { nombre: number; couleur: string }> = {};

    for (const [code, nombre] of Object.entries(comptes)) {
      const type = catalogue.find((entree) => entree.anomalie_code === code);
      const famille = type?.anomalie_famille ?? "AUTRES";
      const courant = totaux[famille] ?? {
        nombre: 0, couleur: type?.anomalie_couleur ?? "var(--text-light)",
      };
      totaux[famille] = { nombre: courant.nombre + nombre, couleur: courant.couleur };
    }

    const lignes = Object.entries(totaux)
      .map(([famille, valeurs]) => ({ famille, ...valeurs }))
      .sort((premier, second) => second.nombre - premier.nombre);

    // La barre la plus longue sert d'échelle : comparer des familles entre
    // elles est ce qui intéresse, pas leur valeur absolue.
    const maximum = lignes[0]?.nombre ?? 0;
    const total = lignes.reduce((somme, ligne) => somme + ligne.nombre, 0);

    return { lignes, maximum, total };
  }, [detail, catalogue]);

  if (erreur) {
    return (
      <div className="screen">
        <p className="screen-error">{erreur}</p>
        <button className="btn btn-outline" onClick={onAccueil}>
          Retour à l&rsquo;accueil
        </button>
      </div>
    );
  }

  if (!execution) {
    return <div className="screen"><div className="screen-empty">Chargement du bilan…</div></div>;
  }

  return (
    <div className="screen">

      {/* Bandeau de fin */}
      <div className="bilan-bandeau">
        <div className="bilan-sceau" aria-hidden="true">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="m5 13 4 4L19 7" />
          </svg>
        </div>

        <div className="bilan-identite">
          <div className="bilan-etiquettes">
            <span className="pastille pastille-terminee">
              {execution.simulation_statut === "arretee" ? "Arrêtée" : "Terminée"}
            </span>
            <span className="type-card-code">{execution.simulation_type ?? "—"}</span>
          </div>
          <h2 className="bilan-nom">{execution.simulation_libelle}</h2>
          <p className="bilan-quand">
            Du {dateCourte(execution.simulation_date_debut)}
            {execution.simulation_date_fin
              ? ` au ${dateCourte(execution.simulation_date_fin)}`
              : ""}
          </p>
        </div>

        <div className="bilan-chiffres-cles">
          <div>
            <span className="bilan-cle-valeur">
              {duree(execution.simulation_date_debut, execution.simulation_date_fin)}
            </span>
            <span className="bilan-cle-nom">Durée totale</span>
          </div>
          <div>
            <span className="bilan-cle-valeur bilan-cle-valeur--vert">
              {execution.passages_reussis.toLocaleString("fr-FR")}
            </span>
            <span className="bilan-cle-nom">Passages réussis</span>
          </div>
          <div>
            <span className={`bilan-cle-valeur${execution.passages_echoues > 0 ? " bilan-cle-valeur--rouge" : ""}`}>
              {execution.passages_echoues.toLocaleString("fr-FR")}
            </span>
            <span className="bilan-cle-nom">Passages échoués</span>
          </div>
        </div>
      </div>

      {/* Volumétrie */}
      <section>
        <h2 className="screen-section-title">Ce qui a été produit<span className="rule" /></h2>
        {Object.keys(detail?.volumetrie ?? {}).length === 0 ? (
          <div className="screen-empty">Cette exécution n&rsquo;a produit aucune ligne.</div>
        ) : (
          <div className="bilan-volumetrie">
            {Object.entries(detail?.volumetrie ?? {}).map(([cle, nombre]) => (
              <div key={cle} className="bilan-volume">
                <span className="bilan-volume-valeur">{nombre.toLocaleString("fr-FR")}</span>
                <span className="bilan-volume-nom">{NOMS_VOLUMETRIE[cle] ?? cle}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="bilan-colonnes">

        {/* Anomalies par famille */}
        <section>
          <h2 className="screen-section-title">
            Anomalies posées
            <span className="rule" />
            <span className="bilan-total">{parFamille.total.toLocaleString("fr-FR")} au total</span>
          </h2>
          {parFamille.lignes.length === 0 ? (
            <div className="screen-empty">Aucune anomalie n&rsquo;a été posée.</div>
          ) : (
            <div className="bilan-panneau">
              {parFamille.lignes.map((ligne) => (
                <div key={ligne.famille} className="bilan-famille">
                  <div className="bilan-famille-tete">
                    <span className="bilan-famille-nom">{ligne.famille}</span>
                    <span className="bilan-famille-compte">
                      <b>{ligne.nombre.toLocaleString("fr-FR")}</b>
                      {parFamille.total > 0
                        && ` · ${Math.round((ligne.nombre / parFamille.total) * 100)} %`}
                    </span>
                  </div>
                  <div className="bilan-piste">
                    <div
                      className="bilan-piste-remplie"
                      style={{
                        width: `${parFamille.maximum > 0
                          ? (ligne.nombre / parFamille.maximum) * 100 : 0}%`,
                        background: ligne.couleur,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Aléas frappés */}
        <section>
          <h2 className="screen-section-title">
            Aléas frappés
            <span className="rule" />
            <span className="bilan-total">{frappes.length}</span>
          </h2>
          {frappes.length === 0 ? (
            <div className="screen-empty">Aucun aléa n&rsquo;a été déclenché.</div>
          ) : (
            <div className="bilan-panneau">
              {frappes.map((frappe) => (
                <div
                  key={`${frappe.code}-${frappe.horodatage.getTime()}`}
                  className="bilan-frappe"
                  style={{ ["--alea" as string]: frappe.couleur }}
                >
                  <span className="bilan-frappe-heure">
                    {frappe.horodatage.toLocaleTimeString("fr-FR",
                      { hour: "2-digit", minute: "2-digit" })}
                  </span>
                  <span className="bilan-frappe-puce" aria-hidden="true" />
                  <div className="bilan-frappe-texte">
                    <div className="bilan-frappe-nom">{frappe.libelle}</div>
                    <div className="bilan-frappe-nature">{frappe.nature}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Les deux suites possibles */}
      <div className="bilan-suites">
        <button type="button" className="bilan-suite bilan-suite--qualite" onClick={onVoirQualite}>
          <span className="bilan-suite-icone" aria-hidden="true">
            <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="m9 12 2 2 4-4M12 3l8 4v5c0 5-3.4 8.5-8 9.9C7.4 20.5 4 17 4 12V7l8-4z" />
            </svg>
          </span>
          <span className="bilan-suite-texte">
            <span className="bilan-suite-titre">Voir le contrôle qualité</span>
            <span className="bilan-suite-desc">
              Comparer ce qui a été demandé, injecté et détecté
            </span>
          </span>
          <span className="bilan-suite-fleche" aria-hidden="true">→</span>
        </button>

        <button type="button" className="bilan-suite bilan-suite--export" onClick={onExporter}>
          <span className="bilan-suite-icone" aria-hidden="true">
            <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 3v12m-5-5 5 5 5-5M4 19h16" />
            </svg>
          </span>
          <span className="bilan-suite-texte">
            <span className="bilan-suite-titre">Exporter le rapport</span>
            <span className="bilan-suite-desc">
              PDF de synthèse, classeur Excel ou archive CSV
            </span>
          </span>
          <span className="bilan-suite-fleche" aria-hidden="true">→</span>
        </button>
      </div>

      <button className="btn btn-outline bilan-retour" onClick={onAccueil}>
        Retour à l&rsquo;accueil
      </button>
    </div>
  );
}
