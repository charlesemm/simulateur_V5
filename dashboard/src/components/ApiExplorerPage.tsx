// dashboard/src/components/ApiExplorerPage.tsx
//
// W9 — Explorateur API.
//
// Lit le schéma OpenAPI que FastAPI publie déjà sur /openapi.json : chaque
// route y porte son résumé et sa description (les docstrings des routeurs),
// ses paramètres et le schéma de son corps. Rien n'est recopié à la main —
// un nouvel endpoint apparaît ici sans qu'on touche ce fichier.
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { API_URL } from "../services/api";
import "./Screens.css";

interface OpenApiParameter {
  name: string;
  in: "path" | "query" | "header" | "cookie";
  required?: boolean;
  description?: string;
  schema?: { type?: string; format?: string; enum?: unknown[]; default?: unknown };
}

interface OpenApiOperation {
  summary?: string;
  description?: string;
  operationId?: string;
  tags?: string[];
  parameters?: OpenApiParameter[];
  security?: unknown[];
  requestBody?: {
    required?: boolean;
    content?: Record<string, { schema?: JsonSchema }>;
  };
}

type JsonSchema = {
  $ref?: string;
  type?: string;
  format?: string;
  enum?: unknown[];
  default?: unknown;
  example?: unknown;
  items?: JsonSchema;
  properties?: Record<string, JsonSchema>;
  required?: string[];
  allOf?: JsonSchema[];
  anyOf?: JsonSchema[];
};

interface OpenApiDoc {
  paths: Record<string, Record<string, OpenApiOperation>>;
  components?: { schemas?: Record<string, JsonSchema> };
}

interface Endpoint {
  id: string;
  method: string;
  path: string;
  tag: string;
  summary: string;
  description: string;
  parametres: OpenApiParameter[];
  schemaCorps: JsonSchema | null;
  corpsRequis: boolean;
  protegee: boolean;
}

const METHODES_ORDRE = ["get", "post", "put", "patch", "delete"];

function resoudreSchema(schema: JsonSchema | undefined, doc: OpenApiDoc): JsonSchema | null {
  if (!schema) return null;
  if (schema.$ref) {
    const nom = schema.$ref.split("/").pop() ?? "";
    const cible = doc.components?.schemas?.[nom];
    return cible ? resoudreSchema(cible, doc) : null;
  }
  return schema;
}

/** Fabrique une valeur d'exemple à partir d'un schéma JSON — de quoi remplir
 *  le formulaire sans que l'admin doive deviner la forme attendue. */
function exempleDepuisSchema(schema: JsonSchema | undefined, doc: OpenApiDoc, profondeur = 0): unknown {
  const resolu = resoudreSchema(schema, doc);
  if (!resolu || profondeur > 6) return null;
  if (resolu.example !== undefined) return resolu.example;
  if (resolu.default !== undefined) return resolu.default;
  if (resolu.enum && resolu.enum.length > 0) return resolu.enum[0];

  if (resolu.allOf && resolu.allOf.length > 0) {
    return resolu.allOf.reduce<Record<string, unknown>>((acc, partie) => {
      const valeur = exempleDepuisSchema(partie, doc, profondeur + 1);
      return valeur && typeof valeur === "object" ? { ...acc, ...(valeur as object) } : acc;
    }, {});
  }

  switch (resolu.type) {
    case "object": {
      const proprietes = resolu.properties ?? {};
      const objet: Record<string, unknown> = {};
      for (const [nom, sousSchema] of Object.entries(proprietes)) {
        objet[nom] = exempleDepuisSchema(sousSchema, doc, profondeur + 1);
      }
      return objet;
    }
    case "array":
      return [exempleDepuisSchema(resolu.items, doc, profondeur + 1)];
    case "integer":
    case "number":
      return 0;
    case "boolean":
      return false;
    case "string":
      if (resolu.format === "date-time") return new Date().toISOString();
      if (resolu.format === "date") return new Date().toISOString().slice(0, 10);
      if (resolu.format === "uuid") return "00000000-0000-0000-0000-000000000000";
      return "";
    default:
      return null;
  }
}

function aplatirOpenApi(doc: OpenApiDoc): Endpoint[] {
  const routes: Endpoint[] = [];
  for (const [chemin, operations] of Object.entries(doc.paths ?? {})) {
    for (const methode of METHODES_ORDRE) {
      const operation = operations[methode];
      if (!operation) continue;
      const corpsSchemaBrut = operation.requestBody?.content?.["application/json"]?.schema;
      routes.push({
        id: `${methode}:${chemin}`,
        method: methode.toUpperCase(),
        path: chemin,
        tag: operation.tags?.[0] ?? "Sans catégorie",
        summary: operation.summary ?? chemin,
        description: operation.description ?? "",
        parametres: operation.parameters ?? [],
        schemaCorps: resoudreSchema(corpsSchemaBrut, doc),
        corpsRequis: operation.requestBody?.required ?? false,
        // FastAPI place `security` sur l'opération dès qu'une dépendance
        // `require_role`/OAuth2 s'applique : un tableau vide ou absent dit
        // que la route ne demande pas de jeton.
        protegee: Array.isArray(operation.security) && operation.security.length > 0,
      });
    }
  }
  return routes;
}

interface EtatReponse {
  statut: number;
  ok: boolean;
  duree: number;
  corps: string;
}

interface EtatErreur {
  message: string;
}

export function ApiExplorerPage() {
  const { token } = useAuth();
  const [doc, setDoc] = useState<OpenApiDoc | null>(null);
  const [erreurChargement, setErreurChargement] = useState<string | null>(null);
  const [chargement, setChargement] = useState(true);
  const [recherche, setRecherche] = useState("");

  const [groupesFermes, setGroupesFermes] = useState<Record<string, boolean>>({});
  const [ouverts, setOuverts] = useState<Record<string, boolean>>({});
  const [valeursParams, setValeursParams] = useState<Record<string, Record<string, string>>>({});
  const [corpsTexte, setCorpsTexte] = useState<Record<string, string>>({});
  const [erreursCorps, setErreursCorps] = useState<Record<string, string>>({});
  const [enCours, setEnCours] = useState<Record<string, boolean>>({});
  const [reponses, setReponses] = useState<Record<string, EtatReponse | EtatErreur>>({});

  useEffect(() => {
    let annule = false;
    (async () => {
      try {
        const reponse = await fetch(`${API_URL}/openapi.json`);
        if (!reponse.ok) throw new Error(`Schéma OpenAPI inaccessible (HTTP ${reponse.status}).`);
        const data = (await reponse.json()) as OpenApiDoc;
        if (!annule) setDoc(data);
      } catch (raison) {
        if (!annule) setErreurChargement((raison as Error).message);
      } finally {
        if (!annule) setChargement(false);
      }
    })();
    return () => { annule = true; };
  }, []);

  const endpoints = useMemo(() => (doc ? aplatirOpenApi(doc) : []), [doc]);

  const filtres = useMemo(() => {
    const terme = recherche.trim().toLowerCase();
    if (!terme) return endpoints;
    return endpoints.filter((ep) =>
      ep.path.toLowerCase().includes(terme)
      || ep.method.toLowerCase().includes(terme)
      || ep.summary.toLowerCase().includes(terme)
      || ep.description.toLowerCase().includes(terme)
      || ep.tag.toLowerCase().includes(terme)
    );
  }, [endpoints, recherche]);

  const groupes = useMemo(() => {
    const carte = new Map<string, Endpoint[]>();
    for (const ep of filtres) {
      const liste = carte.get(ep.tag) ?? [];
      liste.push(ep);
      carte.set(ep.tag, liste);
    }
    return [...carte.entries()].sort(([a], [b]) => a.localeCompare(b, "fr"));
  }, [filtres]);

  function basculerGroupe(tag: string) {
    setGroupesFermes((etat) => ({ ...etat, [tag]: !etat[tag] }));
  }

  function initialiser(ep: Endpoint) {
    if (!doc) return;
    setValeursParams((etat) => {
      if (etat[ep.id]) return etat;
      const valeurs: Record<string, string> = {};
      for (const param of ep.parametres) {
        const defaut = param.schema?.default;
        valeurs[param.name] = defaut !== undefined ? String(defaut) : "";
      }
      return { ...etat, [ep.id]: valeurs };
    });
    setCorpsTexte((etat) => {
      if (etat[ep.id] !== undefined) return etat;
      if (!ep.schemaCorps) return etat;
      const exemple = exempleDepuisSchema(ep.schemaCorps, doc);
      return { ...etat, [ep.id]: JSON.stringify(exemple, null, 2) };
    });
  }

  function basculerEndpoint(ep: Endpoint) {
    const prochainEtat = !ouverts[ep.id];
    if (prochainEtat) initialiser(ep);
    setOuverts((etat) => ({ ...etat, [ep.id]: prochainEtat }));
  }

  function changerParam(epId: string, nom: string, valeur: string) {
    setValeursParams((etat) => ({
      ...etat,
      [epId]: { ...(etat[epId] ?? {}), [nom]: valeur },
    }));
  }

  async function lireCorpsReponse(reponse: Response): Promise<string> {
    const typeContenu = reponse.headers.get("Content-Type") ?? "";
    if (typeContenu.includes("application/json")) {
      const data = await reponse.json().catch(() => null);
      return JSON.stringify(data, null, 2);
    }
    if (typeContenu.startsWith("text/")) {
      const texte = await reponse.text();
      return texte.length > 4000 ? `${texte.slice(0, 4000)}\n… (tronqué)` : texte;
    }
    return `[Réponse binaire non affichée — Content-Type : ${typeContenu || "inconnu"}]`;
  }

  async function tester(ep: Endpoint) {
    setErreursCorps((etat) => ({ ...etat, [ep.id]: "" }));

    let corpsJson: unknown = undefined;
    if (ep.schemaCorps) {
      const texte = corpsTexte[ep.id] ?? "";
      if (texte.trim()) {
        try {
          corpsJson = JSON.parse(texte);
        } catch {
          setErreursCorps((etat) => ({ ...etat, [ep.id]: "Le corps n'est pas un JSON valide." }));
          return;
        }
      }
    }

    const valeurs = valeursParams[ep.id] ?? {};
    let chemin = ep.path;
    const query = new URLSearchParams();
    for (const param of ep.parametres) {
      const valeur = valeurs[param.name] ?? "";
      if (param.in === "path") {
        chemin = chemin.replace(`{${param.name}}`, encodeURIComponent(valeur));
      } else if (param.in === "query" && valeur !== "") {
        query.set(param.name, valeur);
      }
    }
    const requete = `${API_URL}${chemin}${query.toString() ? `?${query.toString()}` : ""}`;

    const entetes: HeadersInit = {};
    if (token) entetes.Authorization = `Bearer ${token}`;
    if (corpsJson !== undefined) entetes["Content-Type"] = "application/json";

    setEnCours((etat) => ({ ...etat, [ep.id]: true }));
    const depart = performance.now();
    try {
      const reponse = await fetch(requete, {
        method: ep.method,
        headers: entetes,
        body: corpsJson !== undefined ? JSON.stringify(corpsJson) : undefined,
      });
      const corps = await lireCorpsReponse(reponse);
      setReponses((etat) => ({
        ...etat,
        [ep.id]: {
          statut: reponse.status,
          ok: reponse.ok,
          duree: Math.round(performance.now() - depart),
          corps,
        },
      }));
    } catch (raison) {
      setReponses((etat) => ({ ...etat, [ep.id]: { message: (raison as Error).message } }));
    } finally {
      setEnCours((etat) => ({ ...etat, [ep.id]: false }));
    }
  }

  const totalRoutes = endpoints.length;

  return (
    <div className="screen">
      {erreurChargement && <p className="screen-error">{erreurChargement}</p>}

      <section>
        <div className="stat-strip" style={{ marginBottom: 14 }}>
          <div className="stat-tile">
            <span className="stat-tile-label">Routes exposées</span>
            <span className="stat-tile-value">{totalRoutes}</span>
          </div>
          <div className="stat-tile">
            <span className="stat-tile-label">Correspondent à la recherche</span>
            <span className="stat-tile-value">{filtres.length}</span>
          </div>
          <div className="stat-tile">
            <span className="stat-tile-label">Catégories</span>
            <span className="stat-tile-value">{groupes.length}</span>
            <span className="stat-tile-hint">Sur {new Set(endpoints.map((e) => e.tag)).size} au total</span>
          </div>
        </div>

        <input
          className="champ-console"
          type="search"
          placeholder="Rechercher une route : chemin, méthode, mot dans la description…"
          value={recherche}
          onChange={(evenement) => setRecherche(evenement.target.value)}
          aria-label="Rechercher une route de l'API"
        />
      </section>

      {chargement && <p className="stat-tile-hint">Chargement du schéma de l'API…</p>}

      {!chargement && groupes.length === 0 && (
        <p className="screen-empty">Aucune route ne correspond à « {recherche} ».</p>
      )}

      {groupes.map(([tag, liste]) => {
        const ferme = groupesFermes[tag] ?? false;
        return (
          <section key={tag} className="famille-bloc endpoint-bloc">
            <button className="famille-bascule" onClick={() => basculerGroupe(tag)}>
              <span className="famille-section" style={{ display: "flex", alignItems: "center", gap: 8, flex: 1 }}>
                <span className="dot" />
                {tag}
                <span className="rule" />
              </span>
              <span className="famille-compte">{liste.length}</span>
              <span className="famille-chevron">{ferme ? "▸" : "▾"}</span>
            </button>

            {!ferme && (
              <div className="screen-table-wrap">
                {liste.map((ep) => {
                  const estOuvert = ouverts[ep.id] ?? false;
                  const reponse = reponses[ep.id];
                  const occupe = enCours[ep.id] ?? false;
                  return (
                    <div key={ep.id}>
                      <button
                        type="button"
                        className="endpoint-ligne"
                        aria-expanded={estOuvert}
                        onClick={() => basculerEndpoint(ep)}
                      >
                        <span className={`api-methode api-methode-${ep.method.toLowerCase()}`}>
                          {ep.method}
                        </span>
                        <span className="endpoint-chemin">{ep.path}</span>
                        <span className="endpoint-resume">{ep.summary}</span>
                        {ep.protegee && <span className="endpoint-auth" title="Nécessite un jeton d'authentification">🔒</span>}
                        <span className="famille-chevron">{estOuvert ? "▾" : "▸"}</span>
                      </button>

                      {estOuvert && (
                        <div className="endpoint-corps">
                          {ep.description && <p className="endpoint-description">{ep.description}</p>}

                          {ep.parametres.length > 0 && (
                            <div className="endpoint-champs">
                              {ep.parametres.map((param) => (
                                <div className="champ-groupe champ-court" key={param.name}>
                                  <label className="champ-libelle" htmlFor={`${ep.id}-${param.name}`}>
                                    {param.name} ({param.in}){param.required ? " *" : ""}
                                  </label>
                                  <input
                                    id={`${ep.id}-${param.name}`}
                                    className="champ-console"
                                    value={valeursParams[ep.id]?.[param.name] ?? ""}
                                    placeholder={param.schema?.type ?? "texte"}
                                    onChange={(evenement) => changerParam(ep.id, param.name, evenement.target.value)}
                                  />
                                  {param.description && (
                                    <span className="stat-tile-hint">{param.description}</span>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}

                          {ep.schemaCorps && (
                            <div className="champ-groupe">
                              <label className="champ-libelle" htmlFor={`${ep.id}-corps`}>
                                Corps JSON{ep.corpsRequis ? " *" : ""}
                              </label>
                              <textarea
                                id={`${ep.id}-corps`}
                                className="champ-console"
                                value={corpsTexte[ep.id] ?? ""}
                                onChange={(evenement) =>
                                  setCorpsTexte((etat) => ({ ...etat, [ep.id]: evenement.target.value }))
                                }
                              />
                              {erreursCorps[ep.id] && <p className="screen-error">{erreursCorps[ep.id]}</p>}
                            </div>
                          )}

                          <div className="endpoint-actions">
                            <button
                              className="btn btn-outline"
                              disabled={occupe}
                              onClick={() => void tester(ep)}
                            >
                              {occupe ? "Envoi…" : "Envoyer"}
                            </button>
                            {!token && ep.protegee && (
                              <span className="stat-tile-hint">
                                Aucune session active : cette route protégée répondra 401.
                              </span>
                            )}
                          </div>

                          {reponse && "statut" in reponse && (
                            <div
                              className={`endpoint-reponse ${reponse.ok ? "endpoint-reponse--ok" : "endpoint-reponse--erreur"}`}
                            >
                              <div className="endpoint-reponse-tete">
                                HTTP {reponse.statut} · {reponse.duree} ms
                              </div>
                              <div>{reponse.corps}</div>
                            </div>
                          )}
                          {reponse && "message" in reponse && (
                            <div className="endpoint-reponse endpoint-reponse--erreur">
                              <div className="endpoint-reponse-tete">Requête échouée</div>
                              <div>{reponse.message}</div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
