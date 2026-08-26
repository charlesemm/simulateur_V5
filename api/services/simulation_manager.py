"""Gère l'unique instance du moteur utilisée par les endpoints FastAPI."""

from __future__ import annotations
import asyncio
from dataclasses import replace
from uuid import UUID
from anomalies.repository import appliquer_profil
from events import publish_simulation_event
from simulation import SimulationEngine
from simulation.aleas import ScenarioAleas
from simulation.commandes import Commande
from simulation.models import STATUT_ARRETEE, STATUT_ECHOUEE
from simulation.profils import QUALITE, profil
from simulation.runs import cloturer_execution, ouvrir_execution
from simulation_config import DEFAULT_CONFIG

class SimulationManager:
    """Sérialise les commandes start/stop et conserve la tâche principale."""

    def __init__(self) -> None:
        self._engine: SimulationEngine | None = None
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._maximum = DEFAULT_CONFIG.max_concurrent_passages
        self._simulation_id: UUID | None = None
        self._type = QUALITE

    async def start(self, speed: float | None = None, maximum: int | None = None,
                    utilisateur_uuid: UUID | None = None,
                    type_simulation: str | None = None,
                    libelle: str | None = None,
                    anomalies: dict[str, dict] | None = None,
                    aleas: dict[str, dict] | None = None,
                    duree_visee_minutes: int | None = None) -> None:
        """Applique un profil, ouvre une exécution et démarre un flux continu.

        Tout ce qui est passé explicitement l'emporte sur le profil : celui-ci
        propose un point de départ que l'écran de lancement peut retoucher
        entièrement. Les réglages d'anomalies valent **pour cette exécution** —
        le catalogue en base n'est pas réécrit, sans quoi lancer une simulation
        modifierait sournoisement les réglages de la suivante.

        Refuse un double démarrage : une seule exécution est ouverte à la fois,
        sans quoi deux moteurs se disputeraient les mêmes assurés.
        """

        async with self._lock:
            if self._task and not self._task.done():
                raise RuntimeError("Le simulateur est déjà démarré.")

            profil_retenu = profil(type_simulation)
            vitesse = profil_retenu.vitesse if speed is None else speed
            limite = (profil_retenu.passages_simultanes_max if maximum is None else maximum)
            reglages_anomalies = (
                profil_retenu.anomalies if anomalies is None else anomalies
            )
            reglages_aleas = profil_retenu.aleas if aleas is None else aleas

            config = replace(DEFAULT_CONFIG, default_speed=vitesse,
                             max_concurrent_passages=limite)
            scenario = ScenarioAleas.depuis_parametres(reglages_aleas)
            appliquer_profil(reglages_anomalies)

            self._simulation_id = await ouvrir_execution(
                {
                    "vitesse": vitesse,
                    "passages_simultanes_max": limite,
                    "graine": config.random_seed,
                    "anomalies": reglages_anomalies,
                    "aleas": scenario.en_parametres(),
                    # Rangée avec l'exécution : le poste de pilotage la relit
                    # au retour, ce qu'il ne pourrait pas faire d'un état
                    # gardé dans le navigateur.
                    "duree_visee_minutes": duree_visee_minutes,
                },
                utilisateur_uuid,
                profil_retenu.code,
                libelle,
            )
            await self._preparer(profil_retenu, self._simulation_id)

            self._engine = SimulationEngine(
                config, publish_simulation_event, self._simulation_id, scenario
            )
            self._engine.set_speed(vitesse)
            self._maximum = limite
            self._type = profil_retenu.code
            self._task = asyncio.create_task(self._engine.start())

    async def _preparer(self, profil_retenu, simulation_id: UUID) -> None:
        """Produit ce que le type demande avant que le moteur ne démarre.

        Désactivé en attendant le cahier des charges des moteurs T1-T4. Le
        champ `preparation` du profil est lu mais ignoré — quand les moteurs
        spécialisés seront implémentés, cette méthode reprendra du service.
        """

    def commander(self, commande: Commande) -> None:
        """Dépose un ordre pour le moteur en cours, ou refuse s'il est arrêté."""

        if self._engine is None or not self._engine._running:
            raise RuntimeError("Le simulateur est arrêté.")
        if not self._engine.canal.deposer(commande):
            raise RuntimeError("Le canal de commande est saturé, réessayez.")

    async def stop(self) -> None:
        """Arrête le moteur, attend sa tâche puis clôture l'exécution."""

        async with self._lock:
            if self._engine:
                await self._engine.stop()
            resultats = []
            if self._task:
                resultats = await asyncio.gather(self._task, return_exceptions=True)
            if self._simulation_id and self._engine:
                # Une exception remontée par la tâche principale signe une
                # exécution interrompue, pas un arrêt demandé : l'annulation
                # provoquée par stop() n'en est pas une.
                echec = any(
                    isinstance(resultat, BaseException)
                    and not isinstance(resultat, asyncio.CancelledError)
                    for resultat in resultats
                )
                await cloturer_execution(
                    self._simulation_id, STATUT_ECHOUEE if echec else STATUT_ARRETEE,
                    self._engine.passages_reussis, self._engine.passages_echoues,
                )
            self._simulation_id = None
            self._task = None
            self._engine = None

    def set_speed(self, speed: float) -> None:
        """Ajuste la vitesse ou signale que le moteur est arrêté."""

        if self._engine is None or not self._engine._running:
            raise RuntimeError("Le simulateur est arrêté.")
        self._engine.set_speed(speed)

    def status(self) -> dict:
        """Construit l'état courant consommé par le schéma Pydantic."""

        running = bool(self._engine and self._engine._running)
        return {
            "etat": "en_cours" if running else "arrete",
            "simulation_id": self._simulation_id,
            "type_simulation": self._type,
            "vitesse": self._engine._speed if self._engine else DEFAULT_CONFIG.default_speed,
            "passages_actifs": len(self._engine._insured_in_progress) if self._engine else 0,
            "passages_simultanes_max": self._maximum,
            "passages_interrompus": self._engine.passages_interrompus if self._engine else 0,
        }
simulation_manager = SimulationManager()
