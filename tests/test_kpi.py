"""Vérifie la fenêtre glissante des KPI et le découpage des requêtes.

Les deux défauts corrigés au chantier 6 se masquaient l'un l'autre : la
fenêtre ancrée sur l'horloge simulée ne ramenait presque rien, donc la limite
de paramètres d'asyncpg n'était jamais atteinte.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database import async_session_factory
from app.models import Invoice
from events.models import EventJournal
from kpi.service import TAILLE_LOT, KpiService, _lignes_par_lots

# Au-delà de la limite d'asyncpg : la requête doit malgré tout aboutir.
AU_DELA_DE_LA_LIMITE = 40_000


async def _journaliser(type_evenement: str, simulated_at: datetime, **payload) -> None:
    """Écrit un événement dont l'horloge simulée est choisie par le test."""

    async with async_session_factory() as session:
        session.add(EventJournal(
            evenement_id=uuid.uuid4(), type_evenement=type_evenement,
            passage_id="passage-de-test", simulated_at=simulated_at,
            payload=payload, utilisateur_id_creation="tests",
        ))
        await session.commit()


async def test_la_fenetre_voit_l_activite_dont_l_horloge_simulee_est_en_avance(base_vierge):
    """Le cœur du défaut : simulated_at devance le réel de plusieurs jours."""

    del base_vierge
    futur = datetime.now(timezone.utc) + timedelta(days=3)
    await _journaliser("facture.creee", futur, facture_numero="FAC-TEST-0001")

    snapshot = await KpiService().calculate_snapshot()

    # Avant correction, la fenêtre s'ancrait sur le plus grand simulated_at
    # et n'aurait rien compté du tout.
    assert snapshot["passages"]["total"] == 1


async def test_la_fenetre_exclut_ce_qui_est_trop_ancien(base_vierge):
    del base_vierge
    maintenant = datetime.now(timezone.utc)
    await _journaliser("facture.creee", maintenant, facture_numero="FAC-TEST-0002")

    # On vieillit artificiellement l'enregistrement au-delà de la fenêtre.
    async with async_session_factory() as session:
        evenement = (await session.execute(select(EventJournal))).scalar_one()
        evenement.date_creation = maintenant - timedelta(hours=48)
        await session.commit()

    snapshot = await KpiService().calculate_snapshot()
    assert snapshot["passages"]["total"] == 0


async def test_la_fenetre_se_termine_a_l_instant_present(base_vierge):
    del base_vierge
    snapshot = await KpiService().calculate_snapshot()

    debut = datetime.fromisoformat(snapshot["window"]["from"])
    fin = datetime.fromisoformat(snapshot["window"]["to"])
    assert snapshot["window"]["hours"] == 24
    assert round((fin - debut).total_seconds() / 3600) == 24
    assert abs((datetime.now(timezone.utc) - fin).total_seconds()) < 60


async def test_les_passages_clotures_sont_distingues_des_passages_en_cours(base_vierge):
    del base_vierge
    maintenant = datetime.now(timezone.utc)
    await _journaliser("facture.creee", maintenant, facture_numero="FAC-A")
    await _journaliser("facture.creee", maintenant, facture_numero="FAC-B")
    await _journaliser("facture.statut", maintenant, facture_numero="FAC-A", statut="cloturee")

    snapshot = await KpiService().calculate_snapshot()
    assert snapshot["passages"] == {"en_cours": 1, "clotures": 1, "total": 2}


async def test_le_decoupage_encaisse_plus_de_parametres_que_la_limite(base_vierge):
    """Sans découpage, asyncpg refuse la requête au-delà de 32 767 valeurs."""

    del base_vierge
    identifiants = [f"FAC-TEST-{index:08d}" for index in range(AU_DELA_DE_LA_LIMITE)]
    assert len(identifiants) > 32_767

    async with async_session_factory() as session:
        lignes = await _lignes_par_lots(
            session,
            lambda lot: select(Invoice.facture_numero).where(Invoice.facture_numero.in_(lot)),
            identifiants,
        )
    assert lignes == []


async def test_le_decoupage_retrouve_bien_toutes_les_lignes(base_vierge):
    """Le découpage ne doit rien perdre au passage d'un lot à l'autre."""

    del base_vierge
    valeurs = list(range(TAILLE_LOT * 3 + 17))

    async with async_session_factory() as session:
        appels = []

        def construire(lot):
            appels.append(len(lot))
            return select(Invoice.facture_numero).where(Invoice.facture_numero.in_([]))

        await _lignes_par_lots(session, construire, valeurs)

    assert sum(appels) == len(valeurs)
    assert max(appels) <= TAILLE_LOT


async def test_une_liste_vide_ne_declenche_aucune_requete(base_vierge):
    del base_vierge
    appels = []

    async with async_session_factory() as session:
        def construire(lot):
            appels.append(lot)
            return select(Invoice.facture_numero)

        resultat = await _lignes_par_lots(session, construire, [])

    assert resultat == []
    assert appels == []
