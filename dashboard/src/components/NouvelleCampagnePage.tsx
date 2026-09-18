// dashboard/src/components/NouvelleCampagnePage.tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { api } from "../services/api";
import type { DimensionQualite, PalierCampagne, TypeAnomalieCampagne } from "../types";
import "./Screens.css";

interface NouvelleCampagnePageProps {
  onAnnuler: () => void;
  /** Appelé avec la campagne créée, pour l'ouvrir aussitôt. */
  onCreee: (campagneId: string) => void;
}

/** Réglage d'un type d'anomalie, tel que l'écran le manipule. */
interface ReglageType {
  actif: boolean;
  /** En pourcentage entier, comme l'opérateur le saisit. */
  pourcentage: number;
}

/** Taux proposé quand on active un type sans en avoir choisi un. */
const POURCENTAGE_PAR_DEFAUT = 5;

const ETAPES = [
  "Paramètres de génération",
  "Sélection des anomalies",
  "Récapitulatif",
];

/** Sépare les milliers : 100000 se lit mal, 100 000 se lit d'un coup d'œil. */
function entier(valeur: number): string {
  return valeur.toLocaleString("fr-FR");
}

/**
 * M1 + M2 — Ouverture d'une campagne de test, en trois étapes.
 *
 * Les anomalies sont groupées par **dimension de qualité** et non par famille :
 * une famille dit où l'anomalie est posée, une dimension dit ce qu'elle
 * éprouve chez l'outil testé. C'est le vocabulaire du cahier des charges, et
 * c'est celui que le score reprendra.
 *
 * La graine est visible dès la première étape : tirée en douce au moment de
 * générer, elle arriverait trop tard pour qu'on puisse rejouer la campagne.
 */
export function NouvelleCampagnePage({ onAnnuler, onCreee }: NouvelleCampagnePageProps) {
  const { token } = useAuth();
  const [etape, setEtape] = useState(1);
  const [paliers, setPaliers] = useState<PalierCampagne[]>([]);
  const [dimensions, setDimensions] = useState<DimensionQualite[]>([]);
  const [types, setTypes] = useState<TypeAnomalieCampagne[]>([]);
  const [erreur, setErreur] = useState<string | null>(null);
  const [creation, setCreation] = useState(false);
  // Prévisionnelle : calculée à l'affichage, pas réservée. Elle peut donc
  // différer de la référence réellement attribuée si une autre campagne se
  // crée entre-temps — c'est le compromis pour ne rien réserver en base
  // tant que rien n'est confirmé.
  const [referencePrevisionnelle, setReferencePrevisionnelle] = useState<string | null>(null);

  const [palierChoisi, setPalierChoisi] = useState("ECHANTILLON");
  const [volume, setVolume] = useState(500);
  // Le mode de graine est un choix explicite : « aléatoire » et « une graine
  // que je saisis » ne se devinent pas d'un champ laissé vide.
  const [graineAleatoire, setGraineAleatoire] = useState(true);
  const [graine, setGraine] = useState(1);
  const [reglages, setReglages] = useState<Record<string, ReglageType>>({});

  useEffect(() => {
    let annule = false;
    void (async () => {
      try {
        const [listePaliers, listeDimensions, listeTypes, reference] = await Promise.all([
          api.getPaliers(token),
          api.getDimensions(token),
          api.getTypesCampagne(token),
          api.getProchaineReference(token),
        ]);
        if (annule) return;
        setPaliers(listePaliers);
        setDimensions(listeDimensions);
        setTypes(listeTypes);
        setReferencePrevisionnelle(reference);

        const premier = listePaliers[0];
        if (premier) {
          setPalierChoisi(premier.code);
          setVolume(premier.volume_propose);
        }
        // Rien n'est pré-coché : la campagne doit dire exactement ce qu'elle
        // pose, et un réglage hérité en douce fausserait la lecture du score.
        setReglages(
          Object.fromEntries(
            listeTypes.map((type) => [
              type.code,
              { actif: false, pourcentage: POURCENTAGE_PAR_DEFAUT },
            ])
          )
        );
      } catch (raison) {
        if (!annule) setErreur((raison as Error).message);
      }
    })();
    return () => {
      annule = true;
    };
  }, [token]);

  const palierCourant = useMemo(
    () => paliers.find((candidat) => candidat.code === palierChoisi) ?? null,
    [paliers, palierChoisi]
  );

  // Les dimensions qui ont au moins un type : afficher les trois autres
  // donnerait trois sections vides à cliquer, sans rien à y régler.
  const dimensionsPourvues = useMemo(
    () => dimensions.filter((dimension) => dimension.types_disponibles > 0),
    [dimensions]
  );

  const dimensionsVides = useMemo(
    () => dimensions.filter((dimension) => dimension.types_disponibles === 0),
    [dimensions]
  );

  const actifs = useMemo(
    () => types.filter((type) => reglages[type.code]?.actif),
    [types, reglages]
  );

  const dimensionsCouvertes = useMemo(() => {
    const codes = new Set(actifs.map((type) => type.dimension));
    return dimensions.filter((dimension) => codes.has(dimension.code));
  }, [actifs, dimensions]);

  // Changer de palier réaligne le volume : garder l'ancien nombre après avoir
  // cliqué « Volume élevé » donnerait une campagne qui ment sur son palier.
  const choisirPalier = useCallback((choisi: PalierCampagne) => {
    setPalierChoisi(choisi.code);
    setVolume(choisi.volume_propose);
  }, []);

  const basculer = useCallback((code: string) => {
    setReglages((precedents) => ({
      ...precedents,
      [code]: {
        actif: !precedents[code]?.actif,
        pourcentage: precedents[code]?.pourcentage ?? POURCENTAGE_PAR_DEFAUT,
      },
    }));
  }, []);

  const changerTaux = useCallback((code: string, pourcentage: number) => {
    setReglages((precedents) => ({
      ...precedents,
      [code]: {
        // Régler un taux vaut activation : décocher ensuite reste possible,
        // mais saisir « 3 % » sur une ligne éteinte ne doit rien perdre.
        actif: true,
        pourcentage: Math.max(1, Math.min(pourcentage, 100)),
      },
    }));
  }, []);

  const basculerDimension = useCallback(
    (codeDimension: string, actif: boolean) => {
      setReglages((precedents) => {
        const suivants = { ...precedents };
        for (const type of types) {
          if (type.dimension !== codeDimension) continue;
          suivants[type.code] = {
            actif,
            pourcentage: precedents[type.code]?.pourcentage ?? POURCENTAGE_PAR_DEFAUT,
          };
        }
        return suivants;
      });
    },
    [types]
  );

  const creer = useCallback(async () => {
    setCreation(true);
    try {
      const anomalies = Object.fromEntries(
        actifs.map((type) => [
          type.code,
          { taux: (reglages[type.code]?.pourcentage ?? 0) / 100 },
        ])
      );
      const campagne = await api.creerCampagne(token, {
        palier: palierChoisi,
        volume_cible: volume,
        graine: graineAleatoire ? null : graine,
        anomalies,
      });
      setErreur(null);
      onCreee(campagne.campagne_id);
    } catch (raison) {
      setErreur((raison as Error).message);
    } finally {
      setCreation(false);
    }
  }, [
    token, palierChoisi, volume, graineAleatoire, graine, actifs,
    reglages, onCreee,
  ]);

  return (
    <div className="screen">
      {erreur && <p className="screen-error">{erreur}</p>}

      {referencePrevisionnelle && (
        <p className="fiche-identifiant" style={{ marginBottom: 10 }}>
          Référence prévisionnelle : {referencePrevisionnelle}
        </p>
      )}

      <ol className="fil-etapes">
        {ETAPES.map((libelle, index) => {
          const rang = index + 1;
          return (
            <li
              key={libelle}
              className={`fil-etape${rang === etape ? " fil-etape--active" : ""}${
                rang < etape ? " fil-etape--faite" : ""
              }`}
            >
              <span className="fil-etape-rang">{rang}</span>
              <span className="fil-etape-libelle">{libelle}</span>
            </li>
          );
        })}
      </ol>

      {/* ── Étape 1 : ce que la campagne va produire ── */}
      {etape === 1 && (
        <>
          <div className="fiche">
            <div className="fiche-tete">
              <div>
                <span className="type-card-code">QUALITE</span>
                <div className="fiche-titre">Nouvelle campagne de test</div>
              </div>
            </div>
            <p className="type-card-desc">
              ÉCHO va fabriquer un jeu de données piégé et garder le corrigé de
              ce qu'il y a posé. Ce jeu sera transmis à l'outil de qualité à
              tester, dont le rapport sera confronté au corrigé.
            </p>

            <p className="screen-section-lead">
              Le nom de la campagne est attribué automatiquement, de façon
              incrémentielle, à la création — plus rien à saisir ici.
            </p>
          </div>

          <section>
            <div className="screen-section-head">
              <h2 className="screen-section-title">Palier de charge</h2>
            </div>
            <p className="screen-section-lead">
              Le palier dit à quelle échelle on éprouve l'outil. Le volume
              proposé reste modifiable.
            </p>
            <div className="type-grid">
              {paliers.map((candidat) => (
                <button
                  key={candidat.code}
                  type="button"
                  className={`type-card type-card--action${
                    candidat.code === palierChoisi ? " type-card--choisi" : ""
                  }`}
                  style={{ ["--type-couleur" as string]: "var(--cnam-blue-vif)" }}
                  onClick={() => choisirPalier(candidat)}
                  aria-pressed={candidat.code === palierChoisi}
                >
                  <span className="type-card-code">{candidat.code}</span>
                  <span className="type-card-title">{candidat.libelle}</span>
                  <span className="type-card-desc">{candidat.description}</span>
                  <span className="type-card-meta">
                    <span>≈ {entier(candidat.volume_propose)} lignes</span>
                  </span>
                </button>
              ))}
              {paliers.length === 0 && (
                <div className="screen-empty">
                  Les paliers n'ont pas pu être chargés.
                </div>
              )}
            </div>
          </section>

          <section>
            <div className="screen-section-head">
              <h2 className="screen-section-title">Volume et graine</h2>
            </div>
            <p className="screen-section-lead">
              Deux campagnes lancées avec la même graine produisent le même jeu
              de données, aux mêmes emplacements. C'est ce qui permet de
              comparer deux versions d'un outil sans se demander si le jeu avait
              changé.
            </p>

            <div className="fiche">
              <div className="formulaire-lancement">
                <label className="champ-groupe champ-court">
                  <span className="champ-libelle">Volume visé (lignes)</span>
                  <input
                    type="number"
                    className="champ-console"
                    min={100}
                    max={5000000}
                    step={100}
                    value={volume}
                    onChange={(evenement) =>
                      setVolume(Math.max(100, Number(evenement.target.value)))
                    }
                  />
                </label>

                <label className="champ-groupe champ-court">
                  <span className="champ-libelle">Graine</span>
                  <select
                    className="champ-console"
                    value={graineAleatoire ? "aleatoire" : "precise"}
                    onChange={(evenement) =>
                      setGraineAleatoire(evenement.target.value === "aleatoire")
                    }
                  >
                    <option value="aleatoire">Aléatoire</option>
                    <option value="precise">Graine précise</option>
                  </select>
                </label>

                {!graineAleatoire && (
                  <label className="champ-groupe champ-court">
                    <span className="champ-libelle">Valeur de la graine</span>
                    <input
                      type="number"
                      className="champ-console"
                      min={1}
                      max={2147483647}
                      value={graine}
                      onChange={(evenement) =>
                        setGraine(Math.max(1, Number(evenement.target.value)))
                      }
                    />
                  </label>
                )}
              </div>

              {palierCourant && (
                <p className="screen-section-lead" style={{ marginTop: 14 }}>
                  {palierCourant.libelle} — {entier(volume)} lignes visées,{" "}
                  {graineAleatoire
                    ? "graine tirée à la création et affichée sur la campagne."
                    : `graine ${entier(graine)}.`}
                </p>
              )}
            </div>
          </section>
        </>
      )}

      {/* ── Étape 2 : ce qu'on va piéger ── */}
      {etape === 2 && (
        <>
          <section>
            <div className="screen-section-head">
              <h2 className="screen-section-title">Anomalies à injecter</h2>
              <span className="screen-section-compte">
                {actifs.length} type{actifs.length > 1 ? "s" : ""} actif
                {actifs.length > 1 ? "s" : ""} sur {types.length}
              </span>
            </div>
            <p className="screen-section-lead">
              Chaque type s'active seul et porte son propre taux. Les groupes
              sont les <b>dimensions de qualité</b> du cahier des charges : ce
              n'est pas l'endroit où l'anomalie est posée, c'est ce qu'elle
              éprouve chez l'outil testé.
            </p>
          </section>

          {dimensionsPourvues.map((dimension) => {
            const typesDeLaDimension = types.filter(
              (type) => type.dimension === dimension.code
            );
            const tousActifs = typesDeLaDimension.every(
              (type) => reglages[type.code]?.actif
            );

            return (
              <section key={dimension.code}>
                <div className="screen-section-head">
                  <h3 className="screen-section-title">{dimension.libelle}</h3>
                  <button
                    type="button"
                    className="btn btn-outline"
                    onClick={() => basculerDimension(dimension.code, !tousActifs)}
                  >
                    {tousActifs ? "Tout désactiver" : "Tout activer"}
                  </button>
                </div>
                <p className="screen-section-lead">{dimension.description}</p>

                <div className="screen-table-wrap">
                  <table className="screen-table">
                    <thead>
                      <tr>
                        <th style={{ width: 90 }}>Injecté</th>
                        <th>Type d'anomalie</th>
                        <th>Où</th>
                        <th style={{ width: 140 }}>Taux</th>
                      </tr>
                    </thead>
                    <tbody>
                      {typesDeLaDimension.map((type) => {
                        const reglage = reglages[type.code] ?? {
                          actif: false,
                          pourcentage: POURCENTAGE_PAR_DEFAUT,
                        };
                        return (
                          <tr key={type.code}>
                            <td>
                              <input
                                type="checkbox"
                                className="case-anomalie"
                                checked={reglage.actif}
                                onChange={() => basculer(type.code)}
                                aria-label={`Injecter ${type.libelle}`}
                              />
                            </td>
                            <td>
                              <b>{type.libelle}</b>
                              <div className="cellule-pied">{type.code}</div>
                            </td>
                            <td className="cellule-pied">
                              {type.table_cible}.{type.colonne_cible}
                            </td>
                            <td>
                              <div className="champ-taux">
                                <input
                                  type="number"
                                  className="champ-console"
                                  min={1}
                                  max={100}
                                  value={reglage.pourcentage}
                                  onChange={(evenement) =>
                                    changerTaux(
                                      type.code,
                                      Number(evenement.target.value)
                                    )
                                  }
                                />
                                <span>%</span>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>
            );
          })}

          {dimensionsVides.length > 0 && (
            <section>
              <div className="screen-empty">
                <b>Trois dimensions n'ont encore aucun injecteur :</b>{" "}
                {dimensionsVides.map((dimension) => dimension.libelle).join(", ")}.
                Une campagne ne peut donc pas les éprouver aujourd'hui, et son
                score n'en dira rien.
              </div>
            </section>
          )}
        </>
      )}

      {/* ── Étape 3 : ce qui va être créé ── */}
      {etape === 3 && (
        <>
          <section>
            <div className="screen-section-head">
              <h2 className="screen-section-title">Récapitulatif</h2>
            </div>
            <div className="stat-strip stat-strip--recap">
              <div className="stat-tile">
                <span className="stat-tile-label">Palier</span>
                <span className="stat-tile-value">
                  {palierCourant?.libelle ?? palierChoisi}
                </span>
                <span className="stat-tile-hint">{entier(volume)} lignes visées</span>
              </div>
              <div className="stat-tile">
                <span className="stat-tile-label">Graine</span>
                <span className="stat-tile-value">
                  {graineAleatoire ? "Aléatoire" : entier(graine)}
                </span>
                <span className="stat-tile-hint">
                  {graineAleatoire ? "Tirée et affichée à la création" : "Rejoue un jeu connu"}
                </span>
              </div>
              <div className="stat-tile">
                <span className="stat-tile-label">Types actifs</span>
                <span className="stat-tile-value">{actifs.length}</span>
                <span className="stat-tile-hint">sur {types.length} au catalogue</span>
              </div>
              <div className="stat-tile">
                <span className="stat-tile-label">Dimensions éprouvées</span>
                <span className="stat-tile-value">
                  {dimensionsCouvertes.length} / {dimensions.length}
                </span>
                <span className="stat-tile-hint">Périmètre du futur score</span>
              </div>
            </div>
          </section>

          <section>
            <h3 className="screen-section-title">Ce qui sera injecté</h3>
            {actifs.length === 0 ? (
              <div className="screen-empty">
                Aucune anomalie retenue : le jeu produit sera sain. C'est un
                test valable — il ne mesure que les fausses alertes de l'outil —
                mais il ne dira rien de ce qu'il sait détecter.
              </div>
            ) : (
              <div className="screen-table-wrap">
                <table className="screen-table">
                  <thead>
                    <tr>
                      <th>Dimension</th>
                      <th>Type d'anomalie</th>
                      <th>Taux</th>
                    </tr>
                  </thead>
                  <tbody>
                    {actifs.map((type) => (
                      <tr key={type.code}>
                        <td>{type.dimension_libelle}</td>
                        <td>
                          <b>{type.libelle}</b>
                          <div className="cellule-pied">{type.code}</div>
                        </td>
                        <td>{reglages[type.code]?.pourcentage} %</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section>
            <h3 className="screen-section-title">Dimensions hors périmètre</h3>
            <p className="screen-section-lead">
              Le score de cette campagne ne dira rien de ces dimensions : aucune
              anomalie ne les vise. C'est à retenir avant de comparer deux
              campagnes entre elles.
            </p>
            <div className="screen-empty">
              {dimensions
                .filter(
                  (dimension) =>
                    !dimensionsCouvertes.some(
                      (couverte) => couverte.code === dimension.code
                    )
                )
                .map((dimension) => dimension.libelle)
                .join(", ") || "Aucune : les huit dimensions sont éprouvées."}
            </div>
          </section>
        </>
      )}

      <div className="barre-lancement">
        <button
          className="btn btn-outline"
          onClick={() => (etape === 1 ? onAnnuler() : setEtape(etape - 1))}
          disabled={creation}
        >
          {etape === 1 ? "Annuler" : "← Précédent"}
        </button>
        {etape < 3 ? (
          <button className="btn btn-start" onClick={() => setEtape(etape + 1)}>
            Suivant →
          </button>
        ) : (
          <button
            className="btn btn-start"
            onClick={() => void creer()}
            disabled={creation}
          >
            {creation ? "Création…" : "Créer la campagne"}
          </button>
        )}
      </div>
    </div>
  );
}
