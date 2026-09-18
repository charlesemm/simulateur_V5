"""Géocode les localités de la liste CNAM vers `localites_coordonnees.csv`.

Comme `extraire_cnam.py`, ce script est ponctuel : le seed ne va jamais sur
Internet, il relit un CSV committé. À relancer seulement si la liste CNAM
change (nouvelles localités dans `etablissements_cnam.csv` /
`pharmacies_cnam.csv`).

Source : Nominatim (OpenStreetMap), service public gratuit qui impose au
plus une requête par seconde et un en-tête `User-Agent` identifiable — d'où
la pause entre deux appels. La précision n'est pas garantie sur les petits
villages ; les lignes non trouvées restent vides et sont à vérifier à la
main (colonne `trouve`).

    python -m seed.donnees.geocoder_localites             # géocode le manquant
    python -m seed.donnees.geocoder_localites --recommencer  # ignore le CSV existant
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from seed.donnees import DOSSIER, ETABLISSEMENTS, PHARMACIES, lire

SORTIE = DOSSIER / "localites_coordonnees.csv"
URL_RECHERCHE = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "simulateur-cmu-echo/1.0 (usage interne, geocodage ponctuel)"
PAYS = "Côte d'Ivoire"
PAUSE_SECONDES = 1.1  # Nominatim : au plus 1 requête/seconde.


def localites_a_geocoder() -> list[str]:
    """Mêmes localités que `build_collectivites` dans seed/runner.py."""

    etablissements = lire(ETABLISSEMENTS)
    pharmacies = lire(PHARMACIES)
    noms = {ligne["localite"] for ligne in etablissements} | {
        ligne["localite"] for ligne in pharmacies
    }
    return sorted(noms)


def _requete(localite: str) -> tuple[str, str] | None:
    """Une localité -> (latitude, longitude), ou None si rien trouvé."""

    parametres = urllib.parse.urlencode({
        "q": f"{localite}, {PAYS}",
        "format": "json",
        "limit": 1,
        "countrycodes": "ci",
    })
    requete = urllib.request.Request(
        f"{URL_RECHERCHE}?{parametres}", headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(requete, timeout=30) as reponse:
        resultats = json.loads(reponse.read().decode("utf-8"))
    if not resultats:
        return None
    return (resultats[0]["lat"], resultats[0]["lon"])


def _lire_existant() -> dict[str, dict[str, str]]:
    if not SORTIE.exists():
        return {}
    with SORTIE.open(encoding="utf-8", newline="") as fichier:
        return {ligne["localite"]: ligne for ligne in csv.DictReader(fichier, delimiter=";")}


def geocoder(recommencer: bool) -> None:
    localites = localites_a_geocoder()
    deja = {} if recommencer else _lire_existant()

    lignes: list[dict[str, str]] = []
    a_faire = [nom for nom in localites if nom not in deja or not deja[nom].get("latitude")]
    print(f"{len(localites)} localités, {len(a_faire)} à géocoder "
          f"({len(localites) - len(a_faire)} déjà connues).")

    for nom in localites:
        if nom in deja and deja[nom].get("latitude"):
            lignes.append(deja[nom])
            continue
        try:
            trouve = _requete(nom)
        except urllib.error.URLError as erreur:
            print(f"  ! {nom} : {erreur}")
            trouve = None
        if trouve:
            latitude, longitude = trouve
            lignes.append({"localite": nom, "latitude": latitude,
                           "longitude": longitude, "trouve": "oui"})
        else:
            lignes.append({"localite": nom, "latitude": "", "longitude": "", "trouve": "non"})
            print(f"  ? {nom} : aucun résultat")
        time.sleep(PAUSE_SECONDES)

    lignes.sort(key=lambda ligne: ligne["localite"])
    with SORTIE.open("w", encoding="utf-8", newline="") as fichier:
        ecrivain = csv.DictWriter(
            fichier, fieldnames=["localite", "latitude", "longitude", "trouve"], delimiter=";"
        )
        ecrivain.writeheader()
        ecrivain.writerows(lignes)

    manquants = sum(1 for ligne in lignes if ligne["trouve"] == "non")
    print(f"{SORTIE.name} : {len(lignes)} lignes, {manquants} sans coordonnées.")


def main() -> None:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--recommencer", action="store_true",
                         help="ignore le CSV existant, regéocode tout")
    arguments = parseur.parse_args()
    geocoder(arguments.recommencer)


if __name__ == "__main__":
    main()
