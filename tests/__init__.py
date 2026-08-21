"""Paquet de tests.

Ce fichier est nécessaire : `test_api` et `test_parcours_moteur` importent des
constantes via `from tests.conftest import ...`. Sans lui, pytest charge le
conftest sous le nom racine `conftest` et cet import le rejoue une seconde fois
sous le nom `tests.conftest` — le module s'exécute deux fois et dérive l'URL de
test à partir d'une URL déjà suffixée.
"""
