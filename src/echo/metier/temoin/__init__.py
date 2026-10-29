"""L'outil témoin du module Qualité des données.

En attendant que le vrai outil soit choisi (cahier des charges, chapitre M6),
ÉCHO se teste lui-même : ce paquet relit un jeu de campagne — le fichier, pas
la base — et applique les mêmes règles que `qualite/regles.py`, réécrites
pour lire du texte plutôt qu'interroger PostgreSQL. Il répond au même contrat
que devra tenir le vrai outil, exposé par `api/routers/temoin.py`.
"""
