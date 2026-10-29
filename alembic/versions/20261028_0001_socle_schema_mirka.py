"""Socle du simulateur : l'ossature de l'application, et le schéma de Mirka.

Le simulateur portait un schéma métier écrit à la main : une trentaine de
tables qui approchaient celles de Mirka sans les égaler. Produire des données
qu'un autre système doit savoir lire exige de produire la vraie structure, pas
une ressemblance. Cette révision crée donc les 317 tables transposées du
dictionnaire Oracle de Mirka, préfixées `TB_SIM_` pour qu'on ne les confonde
jamais avec l'ossature de l'application.

Elle remplace la chaîne 0001 → 0029, déplacée dans `alembic/versions_archive/`.
Cette table rase n'efface rien : elle s'applique à une base neuve
(`echo_db_v2`), et l'ancienne `echo_db` reste intacte à la révision
`20260918_0029`. C'est précisément ce qui la rend légitime — réécrire
l'historique d'une base déjà déployée ne l'aurait pas été.

Deux provenances, deux traitements :

- L'ossature (11 tables) vient de `schema_mirka/ossature.sql`, extrait par
  `pg_dump` de la base que produisait l'ancienne chaîne. Son DDL est donc
  celui des 29 révisions, au caractère près, et non une reconstitution.
- Les tables `TB_SIM_*` viennent de `simulation/schema_sim/`, généré depuis
  les classeurs de `schema_mirka/`. Les régénérer après un changement de
  Mirka ne demande pas de toucher à cette révision.

Le schéma de Mirka ignore `SIMULATION_ID` — c'est un ajout du simulateur, qui
cloisonne les lignes par exécution et rend possibles la volumétrie par run et
la purge sélective. Les tables de faits le portent, les référentiels non. La
contrainte vers `TB_SIMULATIONS` est posée ici et non dans le module de
tables : les deux schémas vivent sur des MetaData séparés, que SQLAlchemy ne
sait pas lier entre eux, alors qu'en base ils cohabitent sans difficulté.

Revision ID: 20261028_0001
Revises: None
Create Date: 2026-10-28
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from alembic import op

from echo.moteur.simulation.schema_sim import metadonnees_sim

revision = "20261028_0001"
down_revision = None
branch_labels = None
depends_on = None

OSSATURE_SQL = Path(__file__).resolve().parents[2] / "schema_mirka" / "ossature.sql"

# Le registre des refus à l'accueil est une sortie du moteur, pas une table de
# Mirka : il appartient à l'ossature, mais sa clé étrangère pointe vers les
# assurés, qui sont désormais une table TB_SIM_. Elle ne peut donc être posée
# qu'après la création du schéma Mirka.
CONTRAINTE_REFUS_ASSURE = "fk_refus_accueil_assure"


def _nom_contraint(nom: str) -> str:
    """Tronque un identifiant trop long sans le rendre ambigu.

    PostgreSQL coupe au-delà de 63 octets, et deux noms longs qui ne diffèrent
    qu'à la fin se retrouveraient confondus. On garde donc un condensé du nom
    complet. Même règle que `tools/generer_tables_sim.py`.
    """
    if len(nom) <= 63:
        return nom
    return nom[:56] + "_" + hashlib.sha1(nom.encode()).hexdigest()[:6]


def _instructions_ossature() -> list[str]:
    """Découpe le DDL de l'ossature : asyncpg refuse les appels multi-instructions."""
    brut = OSSATURE_SQL.read_text(encoding="utf-8")
    sans_commentaires = "\n".join(l for l in brut.splitlines() if not l.strip().startswith("--"))
    return [i.strip() for i in sans_commentaires.split(";") if i.strip()]


def _tables_de_faits() -> list[str]:
    """Les tables TB_SIM_* cloisonnées par exécution, dans l'ordre de création."""
    return [t.name for t in metadonnees_sim.sorted_tables if "SIMULATION_ID" in t.columns]


def upgrade() -> None:
    for instruction in _instructions_ossature():
        op.execute(instruction)

    metadonnees_sim.create_all(bind=op.get_bind())

    for table in _tables_de_faits():
        op.create_foreign_key(
            _nom_contraint(f"FK_{table}_SIMULATION_ID"),
            table,
            "TB_SIMULATIONS",
            ["SIMULATION_ID"],
            ["SIMULATION_ID"],
            ondelete="CASCADE",
        )

    # Mirka stocke ses identifiants de personne en VARCHAR2, pas dans le type
    # uuid de PostgreSQL. Le registre des refus les référence : sa colonne doit
    # suivre, sinon la clé étrangère est impossible. On altère ici plutôt que
    # dans `ossature.sql`, qui reste le reflet fidèle de l'ancienne chaîne.
    op.execute(
        'ALTER TABLE "TB_REFUS_ACCUEIL" '
        'ALTER COLUMN "PERSONNE_UUID" TYPE VARCHAR(100) USING "PERSONNE_UUID"::text'
    )

    op.create_foreign_key(
        CONTRAINTE_REFUS_ASSURE,
        "TB_REFUS_ACCUEIL",
        "TB_SIM_ASSURES",
        ["PERSONNE_UUID"],
        ["PERSONNE_UUID"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Vide le schéma : cette révision est le socle, il n'y a rien avant elle."""
    op.execute(f'ALTER TABLE IF EXISTS "TB_REFUS_ACCUEIL" DROP CONSTRAINT IF EXISTS "{CONTRAINTE_REFUS_ASSURE}"')

    for table in reversed(metadonnees_sim.sorted_tables):
        op.execute(f'DROP TABLE IF EXISTS "{table.name}" CASCADE')

    # L'ossature n'a pas de DDL de suppression : on reprend la liste des tables
    # créées plus haut, en sens inverse.
    for instruction in reversed(_instructions_ossature()):
        if instruction.upper().startswith("CREATE TABLE"):
            nom = instruction.split('"')[1]
            op.execute(f'DROP TABLE IF EXISTS "{nom}" CASCADE')
    op.execute('DROP SEQUENCE IF EXISTS "SEQ_FACTURE_NUMERO"')
    op.execute('DROP SEQUENCE IF EXISTS "TB_CONFIG_ANOMALIES_CONFIG_ID_seq"')
    # La publication de réplication logique sert la capture de changements
    # (Debezium). Sans ce DROP, un downgrade suivi d'un upgrade échouait : la
    # publication survivait, et sa recréation était refusée.
    op.execute("DROP PUBLICATION IF EXISTS dbz_publication_json")
