# Ancienne chaîne de migrations (0001 → 0029)

Ces 29 révisions construisaient le schéma du simulateur jusqu'au 18 septembre
2026 : l'ossature de l'application **et** une trentaine de tables métier
écrites à la main, qui approchaient celles de Mirka sans les égaler.

Elles ont été remplacées par une révision socle unique, qui crée l'ossature et
les 317 tables `TB_SIM_*` transposées du schéma Oracle de Mirka.

Pourquoi archivées et non supprimées :

- La base `echo_db` déployée est restée à la révision `20260918_0029`. Ces
  fichiers sont le seul document de ce qu'elle contient.
- Le DDL de l'ossature repris par la révision socle en est directement issu
  (voir l'en-tête de `schema_mirka/ossature.sql`).

Alembic ne lit que `alembic/versions/` : ce dossier est inerte. Ne pas le
remettre dans le chemin des révisions, les deux chaînes se marcheraient sur
les pieds.
