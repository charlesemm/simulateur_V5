# Référentiels CNAM et identifiants sans ordre

> Changements demandés les 10 et 11/09/2026. Ce guide dit ce qui a changé,
> comment l'appliquer à la base du conteneur, et comment le vérifier à l'écran.

---

## Ce qui a changé

**Les numéros d'identification ne se suivent plus et n'ont plus de préfixe.**
Deux fiches créées l'une après l'autre n'ont jamais des numéros voisins, et
l'écart entre deux numéros n'est pas constant non plus. Les longueurs sont
définies à un seul endroit, `seed/identifiants.py` :

| Identifiant | Avant | Maintenant |
|---|---|---|
| Facture | `FAC-20260911-5a55f00188` | 8 chiffres |
| Dossier | `DOS-5a55f0018891` | 8 caractères alphanumériques |
| Entente préalable | `EP-5a55f0018891` | 8 caractères alphanumériques |
| N° de sécurité sociale | `384…` | `394` + 10 chiffres |
| Centre / immatriculation | `CS007` / `CI-CMU-00007` | 7 / 8 chiffres |
| Agent d'accueil | `AG001` | 5 chiffres |
| Médecin conseil | `AG051` | **4 chiffres** (20 médecins au lieu de 10) |
| Professionnel / n° d'ordre | `PS0001` / `OMCI-000001` | 6 / 6 chiffres |
| Identifiant assuré / récépissé | `CMU0000000001` / `REC-2026-000001` | 10 / 10 chiffres |
| Droits | `DRT-202609-00000001` | 12 chiffres |
| Médicament / pathologie | `MED0001` / `A01` | 6 / 3 chiffres |

Les codes **mnémoniques** ne changent pas (`CONS-GEN`, `BIO-NFS`, `AMB`,
`RAM`, `RGB`, types d'établissement) : le moteur s'appuie dessus.

**Les référentiels viennent de la liste publique de la CNAM** (ipscnam.ci) :

- **1 510 établissements** au lieu de 30, avec leur vrai nom et leur localité.
  Leur type est lu dans le nom : CSR, CSU, dispensaire, HG, CHR, CHU…
- **1 011 localités**, dans la nouvelle table `TB_REF_COLLECTIVITES`.
- **809 pharmacies**, dans la nouvelle table `TB_REF_PHARMACIES`.
- **918 médicaments** de la liste CMU au lieu de 200 inventés. 177 ont leur
  prix réel (diabète, hypertension), les autres un tarif indicatif.
  **149 DCI** dans la nouvelle table `TB_REF_DCI`.
- Par centre : 1 agent d'accueil, 1 médecin, 1 infirmier.

**Entente préalable** : les dates portent l'heure, et `DATE_FIN` est remplie
au moment de la décision (acceptée, refusée ou validée d'office).

**Non touché** : le générateur de campagnes garde son format (384, `CSxxx`),
par décision du 10/09.

---

## Appliquer à la base du conteneur

Les codes changés sont des clés primaires : relancer le seed ajouterait les
nouvelles lignes à côté des anciennes. Il faut donc vider avant de recharger.
**Les comptes utilisateurs, les campagnes et le catalogue d'anomalies sont
gardés.**

```bash
podman compose build api migrations
podman compose up -d
podman compose exec api python -m seed.reinitialiser
podman compose exec api python -m seed.reinitialiser --confirmer
podman compose exec api python -m seed
```

La troisième commande ne touche à rien : elle liste ce qui sera vidé. Le seed
prend quelques minutes.

---

## Vérifier

**Dans DBeaver ou psql** :

```sql
SELECT COUNT(*) FROM "TB_REF_CENTRES_SANTE";      -- 1510
SELECT COUNT(*) FROM "TB_REF_PHARMACIES";         -- 809
SELECT COUNT(*) FROM "TB_REF_MEDICAMENTS";        -- 918
SELECT "AGENT_TYPE_CODE", COUNT(*), MIN(LENGTH("AGENT_CODE")), MAX(LENGTH("AGENT_CODE"))
  FROM "TB_REF_AGENTS" GROUP BY 1;                -- accueil 1510 (5), medecin_conseil 20 (4)
```

**À l'écran** :

1. Lance une simulation libre de quelques minutes, puis exporte-la en Excel.
2. Onglet Factures : numéro à 8 chiffres, n° de sécu en `394…`, centre à
   7 chiffres, dossier à 8 caractères sans `DOS-`. Deux lignes successives
   n'ont pas des numéros qui se suivent.
3. Onglet Ententes préalables : numéro à 8 caractères sans `EP-`, date de
   début avec l'heure, date de fin renseignée.
