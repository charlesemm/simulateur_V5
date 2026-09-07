// dashboard/src/components/FicheCampagne.tsx
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { RequireRole } from "../auth/RequireRole";
import { api } from "../services/api";
import type {
  Campagne, Corrige, FormatExport, ProgressionCampagne, TypeAnomalieCampagne,
} from "../types";
import { dateCourte } from "./format-execution";
import "./Screens.css";

interface FicheCampagneProps {
  campagne: Campagne;
  types: TypeAnomalieCampagne[];
  statuts: Record<string, string>;
  /** Prévient la liste qu'il faut relire la campagne en base. */
  onChangement: () => void;
}

/** Lignes de corrigé montrées d'un coup. Au-delà, on pagine. */
const PAR_PAGE = 25;

/** Cadence de rafraîchissement pendant une génération, en millisecondes. */
const PERIODE_SUIVI = 700;

function entier(valeur: number): string {
  return valeur.toLocaleString("fr-FR");
}

/**
 * M1 à M3 — La fiche d'une campagne : ce qu'elle vise, et ce qu'elle a produit.
 *
 * L'empreinte tient la place la plus visible une fois le jeu généré. C'est
 * elle qui rend la rejouabilité vérifiable à l'œil : deux campagnes de même
 * graine affichent la même suite de caractères, sans qu'on ait à ouvrir les
 * fichiers ni à lancer quoi que ce soit dans un terminal.
 */
export function FicheCampagne({
  campagne, types, statuts, onChangement,
}: FicheCampagneProps) {
  const { token } = useAuth();
  const [suivi, setSuivi] = useState<ProgressionCampagne | null>(null);
  const [corrige, setCorrige] = useState<Corrige | null>(null);
  const [page, setPage] = useState(0);
  const [erreur, setErreur] = useState<string | null>(null);
  const [demarrage, setDemarrage] = useState(false);
  // M4 — les formats sont déclarés par le serveur, jamais recopiés ici.
  const [formats, setFormats] = useState<FormatExport[]>([]);
  // Le format en cours de téléchargement, pour n'occuper que son bouton.
  const [enCours, setEnCours] = useState<string | null>(null);
  // Évite de prévenir la liste deux fois de la même fin de génération.
  const finSignalee = useRef(false);

  const genere = campagne.campagne_empreinte !== null;
  const enGeneration = campagne.campagne_statut === "generation";

  const reglages = useMemo(
    () =>
      (campagne.campagne_parametres?.anomalies ?? {}) as Record<
        string,
        { taux?: number }
      >,
    [campagne]
  );

  const anomalies = useMemo(
    () =>
      types
        .filter((type) => reglages[type.code])
        .map((type) => ({
          type,
          pourcentage: Math.round((reglages[type.code]?.taux ?? 0) * 1000) / 10,
        })),
    [types, reglages]
  );

  const libelleType = useCallback(
    (code: string) => types.find((type) => type.code === code)?.libelle ?? code,
    [types]
  );

  // ── Suivi de la génération ────────────────────────────────────────────
  useEffect(() => {
    if (!enGeneration) return;
    finSignalee.current = false;
    let annule = false;

    const sonder = async () => {
      try {
        const etat = await api.getProgression(campagne.campagne_id, token);
        if (annule) return;
        setSuivi(etat);
        if (etat.terminee && !finSignalee.current) {
          finSignalee.current = true;
          // La campagne en base porte maintenant l'empreinte et les comptes :
          // c'est elle qu'il faut relire, pas la progression en mémoire.
          onChangement();
        }
      } catch (raison) {
        if (!annule) setErreur((raison as Error).message);
      }
    };

    void sonder();
    const minuterie = setInterval(() => void sonder(), PERIODE_SUIVI);
    return () => {
      annule = true;
      clearInterval(minuterie);
    };
  }, [enGeneration, campagne.campagne_id, token, onChangement]);

  // ── Corrigé ───────────────────────────────────────────────────────────
  const chargerCorrige = useCallback(
    async (numeroPage: number) => {
      if (!genere) {
        setCorrige(null);
        return;
      }
      try {
        setCorrige(
          await api.getCorrige(
            campagne.campagne_id, token, PAR_PAGE, numeroPage * PAR_PAGE
          )
        );
        setErreur(null);
      } catch (raison) {
        setErreur((raison as Error).message);
      }
    },
    [campagne.campagne_id, token, genere]
  );

  useEffect(() => {
    setPage(0);
  }, [campagne.campagne_id]);

  useEffect(() => {
    void chargerCorrige(page);
  }, [chargerCorrige, page]);

  const generer = useCallback(async () => {
    setDemarrage(true);
    try {
      setSuivi(await api.genererCampagne(campagne.campagne_id, token));
      setErreur(null);
      onChangement();
    } catch (raison) {
      setErreur((raison as Error).message);
    } finally {
      setDemarrage(false);
    }
  }, [campagne.campagne_id, token, onChangement]);

  // Les formats ne changent pas d'une campagne à l'autre : une seule lecture
  // au montage suffit, et elle n'est faite que si un jeu est téléchargeable.
  useEffect(() => {
    if (!genere) return;
    let vivant = true;
    api
      .getFormatsExport(token)
      .then((liste) => {
        if (vivant) setFormats(liste);
      })
      .catch(() => {
        // Un format indisponible ne doit pas masquer la fiche : les boutons
        // ne s'affichent simplement pas.
      });
    return () => {
      vivant = false;
    };
  }, [token, genere]);

  const telecharger = useCallback(
    async (format: string) => {
      setEnCours(format);
      try {
        await api.telechargerJeu(campagne.campagne_id, format, token);
        setErreur(null);
      } catch (raison) {
        setErreur((raison as Error).message);
      } finally {
        setEnCours(null);
      }
    },
    [campagne.campagne_id, token]
  );

  const pages = corrige ? Math.ceil(corrige.total / PAR_PAGE) : 0;

  return (
    <div className="fiche">
      <div className="fiche-tete">
        <div>
          <span className="fiche-identifiant">{campagne.campagne_reference}</span>
          <div className="fiche-titre">{campagne.campagne_libelle}</div>
        </div>
        <div className="fiche-actions">
          <span className={`pastille pastille-${campagne.campagne_statut}`}>
            {statuts[campagne.campagne_statut] ?? campagne.campagne_statut}
          </span>
          <RequireRole minimum="operateur">
            <button
              className="btn btn-start"
              onClick={() => void generer()}
              disabled={demarrage || enGeneration}
              title={
                genere
                  ? "Reproduit le même jeu : la graine n'a pas changé"
                  : "Produit le jeu piégé et son corrigé"
              }
            >
              {enGeneration
                ? "Génération…"
                : genere
                  ? "Régénérer le jeu"
                  : "Générer le jeu de données"}
            </button>
          </RequireRole>
        </div>
      </div>

      {erreur && <p className="screen-error">{erreur}</p>}
      {suivi?.erreur && (
        <p className="screen-error">
          Génération interrompue : {suivi.erreur}. La campagne est repassée à
          « créée » — un jeu à moitié produit n'a aucune valeur.
        </p>
      )}

      <div className="stat-strip">
        <div className="stat-tile">
          <span className="stat-tile-label">Graine</span>
          <span className="stat-tile-value">{entier(campagne.campagne_graine)}</span>
          <span className="stat-tile-hint">Rejoue le même jeu à l'identique</span>
        </div>
        <div className="stat-tile">
          <span className="stat-tile-label">Palier</span>
          <span className="stat-tile-value">{campagne.campagne_palier}</span>
          <span className="stat-tile-hint">
            {entier(campagne.campagne_volume_cible)} lignes visées
          </span>
        </div>
        <div className="stat-tile">
          <span className="stat-tile-label">Lignes produites</span>
          <span className="stat-tile-value">
            {entier(campagne.campagne_lignes_generees)}
          </span>
          <span className="stat-tile-hint">
            {campagne.campagne_date_generation
              ? `Généré le ${dateCourte(campagne.campagne_date_generation)}`
              : "Pas encore généré"}
          </span>
        </div>
        <div className="stat-tile">
          <span className="stat-tile-label">Anomalies posées</span>
          <span className="stat-tile-value">
            {entier(campagne.campagne_anomalies_posees)}
          </span>
          <span className="stat-tile-hint">C'est le corrigé du test</span>
        </div>
      </div>

      {/* ── La génération en cours ── */}
      {enGeneration && suivi && (
        <div className="progression-bloc">
          <div className="progression-tete">
            <span className="pouls" aria-hidden="true" />
            {entier(suivi.lignes_generees)} / {entier(suivi.volume_cible)} lignes
            <b>{suivi.pourcentage} %</b>
          </div>
          <div className="progression-piste">
            <div
              className="progression-avance"
              style={{ width: `${Math.min(100, suivi.pourcentage)}%` }}
            />
          </div>
        </div>
      )}

      {/* ── L'empreinte, une fois le jeu produit ── */}
      {genere && (
        <div className="empreinte-bloc">
          <span className="empreinte-libelle">Empreinte du jeu produit (SHA-256)</span>
          <code className="empreinte-valeur">{campagne.campagne_empreinte}</code>
          <span className="empreinte-aide">
            Deux campagnes lancées avec la même graine et les mêmes anomalies
            affichent la même empreinte. Si elle diffère, les jeux diffèrent —
            et les scores ne sont pas comparables.
          </span>
          {campagne.campagne_fichier && (
            <span className="empreinte-aide">
              Fichier : <code>{campagne.campagne_fichier}</code>
            </span>
          )}
        </div>
      )}

      {/* ── M4 : le jeu à emporter ── */}
      {genere && formats.length > 0 && (
        <div className="export-bloc">
          <h3 className="screen-section-title">Télécharger le jeu</h3>
          <p className="export-aide">
            Chaque ligne porte son marquage : <code>DONNEE_FICTIVE</code> et la
            référence de la campagne, en tête de fichier. Ce marquage ne peut
            pas être retiré — c'est ce qui empêche un jeu produit ici d'être
            pris un jour pour des données réelles.
          </p>
          <div className="export-boutons">
            {formats.map((format) => (
              <button
                key={format.code}
                type="button"
                className="export-bouton"
                onClick={() => void telecharger(format.code)}
                disabled={enCours !== null}
                title={format.description}
              >
                <span className="export-bouton-libelle">
                  {enCours === format.code ? "Préparation…" : format.libelle}
                </span>
                <span className="export-bouton-extension">
                  .{format.extension}
                </span>
              </button>
            ))}
          </div>
          <p className="export-aide">
            Deux téléchargements du même format, pour la même campagne, donnent
            deux fichiers rigoureusement identiques.
          </p>
        </div>
      )}

      {/* ── Ce qui a été demandé ── */}
      <h3 className="screen-section-title" style={{ marginTop: 20 }}>
        Anomalies demandées
      </h3>
      {anomalies.length === 0 ? (
        <div className="screen-empty">
          Aucune anomalie : le jeu produit est sain. Cette campagne ne mesurera
          que les fausses alertes de l'outil testé.
        </div>
      ) : (
        <div className="screen-table-wrap">
          <table className="screen-table">
            <thead>
              <tr>
                <th>Dimension</th>
                <th>Type d'anomalie</th>
                <th>Taux demandé</th>
                <th>Posées</th>
              </tr>
            </thead>
            <tbody>
              {anomalies.map(({ type, pourcentage }) => (
                <tr key={type.code}>
                  <td>{type.dimension_libelle}</td>
                  <td>
                    <b>{type.libelle}</b>
                    <div className="cellule-pied">
                      {type.table_cible}.{type.colonne_cible}
                    </div>
                  </td>
                  <td>{pourcentage} %</td>
                  <td>
                    {corrige
                      ? entier(corrige.par_anomalie[type.code] ?? 0)
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Le corrigé ── */}
      {genere && corrige && (
        <>
          <h3 className="screen-section-title" style={{ marginTop: 20 }}>
            Corrigé — {entier(corrige.total)} anomalie
            {corrige.total > 1 ? "s" : ""} posée{corrige.total > 1 ? "s" : ""}
          </h3>
          <p className="screen-section-lead">
            Pour chaque anomalie : la ligne du fichier, le champ touché, la
            valeur d'origine et celle qui a été posée. C'est ce corrigé que le
            rapport de l'outil testé viendra confronter.
          </p>

          {corrige.total === 0 ? (
            <div className="screen-empty">
              Aucune anomalie posée : le jeu est sain, comme demandé.
            </div>
          ) : (
            <>
              <div className="screen-table-wrap">
                <table className="screen-table">
                  <thead>
                    <tr>
                      <th>Ligne</th>
                      <th>Champ</th>
                      <th>Anomalie</th>
                      <th>Valeur d'origine</th>
                      <th>Valeur posée</th>
                    </tr>
                  </thead>
                  <tbody>
                    {corrige.lignes.map((ligne) => (
                      <tr key={`${ligne.corrige_ligne}-${ligne.anomalie_code}`}>
                        <td>{entier(ligne.corrige_ligne)}</td>
                        <td className="cellule-pied">{ligne.corrige_champ}</td>
                        <td>{libelleType(ligne.anomalie_code)}</td>
                        <td>{ligne.corrige_valeur_origine}</td>
                        <td>
                          <b>{ligne.corrige_valeur_injectee}</b>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {pages > 1 && (
                <div className="pagination">
                  <button
                    className="btn btn-outline"
                    onClick={() => setPage((actuelle) => Math.max(0, actuelle - 1))}
                    disabled={page === 0}
                  >
                    ← Précédentes
                  </button>
                  <span>
                    Page {page + 1} sur {pages}
                  </span>
                  <button
                    className="btn btn-outline"
                    onClick={() =>
                      setPage((actuelle) => Math.min(pages - 1, actuelle + 1))
                    }
                    disabled={page >= pages - 1}
                  >
                    Suivantes →
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}

      {!genere && !enGeneration && (
        <p className="screen-section-lead" style={{ marginTop: 16 }}>
          Le jeu de données n'est pas encore produit. La campagne existe, elle
          est numérotée, et sa graine est fixée : elle produira toujours le même
          jeu.
        </p>
      )}
    </div>
  );
}
