from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from metrics.registry import registry as metrics_registry
from app.database import async_session_factory
from app.models import InsuredPerson, InsuredRight
from anomalies import anomalies_config
from simulation.aleas import RAFALE, PassageInterrompu, ScenarioAleas
from simulation.commandes import (
    ARMER_ANOMALIE, DECLENCHER_ALEA, DESARMER_ANOMALIE, CanalDeCommande,
)
from simulation.events import EventCallback, default_event_callback
from simulation.inscription import code_identite_a_inscrire, inscrire_assure
from simulation.passage import PassageSimulation
from simulation_config import DEFAULT_CONFIG, SimulationConfig

logger = logging.getLogger(__name__)

class SimulationEngine:
    """Pilote les tâches et interdit deux passages simultanés par assuré."""

    def __init__(self, config: SimulationConfig = DEFAULT_CONFIG,
                 event_callback: EventCallback = default_event_callback,
                 simulation_id: UUID | None = None,
                 scenario: ScenarioAleas | None = None) -> None:
        self.config = config
        self.event_callback = event_callback
        # Scénario d'aléa de l'exécution, partagé par tous ses passages.
        self.scenario = scenario or ScenarioAleas()
        # Canal par lequel l'API arme une anomalie ou déclenche un aléa
        # pendant que le moteur tourne.
        self.canal = CanalDeCommande()
        # Passages coupés volontairement par un aléa : ce ne sont pas des
        # pannes du simulateur, ils sont comptés à part.
        self.passages_interrompus = 0
        # Identifiant de l'exécution ouverte par l'appelant. Il descend jusqu'à
        # chaque ligne écrite ; nul, le moteur produit des lignes orphelines,
        # ce qui reste permis pour un lancement hors API.
        self.simulation_id = simulation_id
        # Compteurs propres à cette exécution : le registre des métriques est
        # global au processus et ne peut pas les distinguer.
        self.passages_reussis = 0
        self.passages_echoues = 0
        self._speed = config.default_speed
        self._running = False
        self._tasks: set[asyncio.Task] = set()
        self._insured_in_progress: set[UUID] = set()
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(config.max_concurrent_passages)
        self._random = random.Random(config.random_seed)
        self._pause_task: asyncio.Task | None = None

    def set_speed(self, speed: float) -> None:
        """Change immédiatement le rapport temps simulé / temps réel."""
        if speed <= 0:
            raise ValueError("La vitesse doit être strictly positive.")
        self._speed = speed

    async def _reserve_insured(self) -> UUID:
        """Réserve atomiquement un assuré qui n'est pas déjà en parcours.

        Seuls les assurés dont les droits sont ouverts pour le mois en cours
        sont éligibles : dans le système réel, les autres ne franchissent pas
        l'accueil et aucune facture ne s'ouvre pour eux. Le passage revérifie
        ensuite à la date exacte des soins, qui peut basculer sur le mois
        suivant pendant le parcours.
        """
        aujourdhui = datetime.now(timezone.utc)
        async with self._lock:
            async with async_session_factory() as session:
                ids = list((await session.execute(
                    select(InsuredPerson.personne_uuid)
                    .join(InsuredRight,
                          InsuredRight.personne_uuid == InsuredPerson.personne_uuid)
                    .where(
                        InsuredRight.droits_annee == aujourdhui.year,
                        InsuredRight.droits_mois == aujourdhui.month,
                        InsuredRight.droits_statut == 1,
                    )
                )).scalars())
            available = [insured_id for insured_id in ids if insured_id not in self._insured_in_progress]
            if not available:
                raise RuntimeError("Aucun assuré disponible pour un nouveau passage.")
            insured_id = self._random.choice(available)
            self._insured_in_progress.add(insured_id)
            metrics_registry.enregistrer_pic(len(self._insured_in_progress))
            return insured_id

    async def _reserve_or_inscrire(self) -> UUID:
        """Choisit entre reprendre un assuré existant et en inscrire un nouveau.

        Cinq types du catalogue visent l'identité de l'assuré lui-même ; comme
        le moteur ne crée normalement aucune fiche, ils n'auraient sinon jamais
        de ligne à corrompre. Le tirage se fait avant la réservation habituelle,
        aux mêmes taux et moments que tout autre type — réglables depuis la
        même console d'injection.
        """
        code = code_identite_a_inscrire(anomalies_config)
        if code is not None:
            return await inscrire_assure(code, self._random, self.simulation_id, anomalies_config)
        return await self._reserve_insured()

    async def _run_one(self, insured_id: UUID, sequence: int) -> None:
        """Exécute un passage sous limite de concurrence puis libère l'assuré."""
        try:
            async with self._semaphore:
                await PassageSimulation(
                    insured_id, self.config, lambda: self._speed,
                    self.event_callback, self.config.random_seed + sequence,
                    self.simulation_id, self.scenario,
                ).run()
        except PassageInterrompu as coupure:
            # Coupure demandée : la trace incohérente qu'elle laisse en base
            # est le résultat attendu, pas un échec du simulateur.
            logger.info("Le passage %s a été coupé par l'aléa %s.", sequence, coupure.alea)
            self.passages_interrompus += 1
        except Exception:
            logger.exception("Le passage %s a échoué.", sequence)
            self.passages_echoues += 1
            metrics_registry.enregistrer_passage(succes=False)
        else:
            self.passages_reussis += 1
            metrics_registry.enregistrer_passage(succes=True)
        finally:
            async with self._lock:
                self._insured_in_progress.discard(insured_id)

    def _traiter_commandes(self) -> None:
        """Applique les ordres déposés depuis le dernier passage créé.

        Le moteur est le seul à toucher l'état armé : l'API se contente de
        déposer, ce qui évite de modifier la configuration depuis le fil d'une
        requête HTTP pendant qu'un passage la lit.
        """

        for commande in self.canal.vider():
            if commande.ordre == ARMER_ANOMALIE:
                anomalies_config.armer(commande.cible, True)
            elif commande.ordre == DESARMER_ANOMALIE:
                anomalies_config.armer(commande.cible, False)
            elif commande.ordre == DECLENCHER_ALEA:
                self.scenario.armer(commande.cible)
            logger.info("Commande appliquée : %s sur %s.", commande.ordre, commande.cible)

    async def _lancer_rafale(self, sequence: int) -> int:
        """Lance d'un coup une salve de passages, et retourne le nouveau rang.

        La rafale ne demande pas la permission au rythme d'arrivée : c'est tout
        son intérêt, saturer d'un seul coup.
        """

        taille = int(self.scenario.reglage(RAFALE, "taille", 25))
        for _ in range(taille):
            try:
                insured_id = await self._reserve_or_inscrire()
            except RuntimeError:
                # Plus d'assuré libre : la rafale s'arrête là où elle peut.
                break
            sequence += 1
            task = asyncio.create_task(self._run_one(insured_id, sequence))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        logger.info("Rafale lancée jusqu'au passage %s.", sequence)
        return sequence

    async def _attendre_prochaine_arrivee(self) -> bool:
        """Laisse passer le délai avant le prochain assuré.

        Retourne False quand l'attente a été interrompue par `stop()` : la
        boucle d'arrivées doit alors sortir.
        """

        delay = self._random.expovariate(1 / self.config.passage_arrival_mean_seconds)
        self._pause_task = asyncio.create_task(asyncio.sleep(delay / self._speed))
        try:
            # asyncio.wait, et non « await self._pause_task » : attendre la
            # tâche directement ferait remonter ici le CancelledError de notre
            # propre stop(), impossible à distinguer d'une annulation venue
            # d'au-dessus (extinction de l'API, timeout). On aurait le choix
            # entre les avaler toutes les deux — et l'appelant attend un arrêt
            # qui ne se signale jamais — ou les relancer toutes les deux, et
            # stop() ne s'arrête plus proprement.
            #
            # wait() ne lève rien quand la tâche attendue est annulée : il ne
            # laisse passer que l'annulation de CETTE coroutine, la seule qui
            # doive poursuivre sa route. L'ambiguïté disparaît au lieu d'être
            # arbitrée.
            await asyncio.wait({self._pause_task})
            interrompue = self._pause_task.cancelled()
        finally:
            pause = self._pause_task
            self._pause_task = None
            if not pause.done():
                # Annulation venue d'au-dessus : la pause survivrait à la
                # boucle, wait() ne l'annule pas pour nous.
                pause.cancel()
        return not interrompue

    async def start(self, number_of_passages: int | None = None) -> None:
        """Crée un flux fini ou continu de tâches de passage."""
        self._running = True
        sequence = 0
        # L'horloge des moments d'injection part avec le moteur : c'est d'elle
        # que se comptent les déclenchements différés et de démarrage.
        anomalies_config.demarrer_execution()
        while self._running and (number_of_passages is None or sequence < number_of_passages):
            self._traiter_commandes()
            if self.scenario.frappe(RAFALE, self._random):
                # La salve remplace le passage unique de ce tour, mais le
                # rythme d'arrivée reprend ensuite : sans cela, une rafale à
                # forte probabilité tournerait sans jamais souffler.
                sequence = await self._lancer_rafale(sequence)
            else:
                insured_id = await self._reserve_or_inscrire()
                sequence += 1
                task = asyncio.create_task(self._run_one(insured_id, sequence))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
            # Pas de pause après le dernier passage d'un flux fini : elle ne
            # ferait qu'ajouter un délai avant de rendre la main.
            reste_des_passages = number_of_passages is None or sequence < number_of_passages
            if reste_des_passages and not await self._attendre_prochaine_arrivee():
                break
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks))
        self._running = False

    async def stop(self) -> None:
        """Arrête la création et annule proprement les tâches restantes."""
        self._running = False
        if self._pause_task and not self._pause_task.done():
            self._pause_task.cancel()
        for task in tuple(self._tasks):
            task.cancel()
        if self._pause_task:
            await asyncio.gather(self._pause_task, return_exceptions=True)
        await asyncio.gather(*tuple(self._tasks), return_exceptions=True)