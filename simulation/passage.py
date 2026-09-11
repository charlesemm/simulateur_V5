from __future__ import annotations

import asyncio
import inspect
import logging
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import NamedTuple
from uuid import uuid4

from sqlalchemy import func, or_, select

from app.database import async_session_factory
from app.models import (
    Agent, HealthCenter, HealthProfessional, InsuredPerson, InsuredRight,
    Invoice, InvoicePathology, InvoicePrescription, InvoiceProvision,
    InvoiceStatus, MedicalAct, Medication, Pathology, PriorAuthorization,
    PriorAuthorizationMedicalAct, PriorAuthorizationStatus, Regime,
)
from anomalies import anomalies_config
from anomalies.repository import enregistrer_injections
from metrics.registry import registry as metrics_registry
from seed.constants import HEALTH_CENTER_TYPES
from simulation.aleas import (
    BASE_RALENTIE, COUPURE_BRUTALE, HORLOGE_DECALEE, PERTE_CONNEXION,
    SATURATION_MEMOIRE, PassageInterrompu, ScenarioAleas,
)
from simulation.events import EventCallback, SimulationEvent
from simulation.models import RefusAccueil
from simulation_config import SimulationConfig

logger = logging.getLogger(__name__)

# Motif publié quand l'assuré se présente sans droits ouverts : le passage
# s'arrête à l'accueil, aucune facture n'est ouverte.
MOTIF_DROITS_FERMES = "droits_fermes"

# La facture range le libellé du TYPE d'établissement, pas le nom du centre.
# Elle a longtemps reçu le second, ce qui rendait la colonne inexploitable
# pour tout regroupement par type.
LIBELLES_TYPE_CENTRE = dict(HEALTH_CENTER_TYPES)


class Coverage(NamedTuple):
    """Ce que le référentiel dit de l'assuré au jour des soins."""

    regime_code: str
    taux: Decimal
    droits_ouverts: bool


class PassageSimulation:
    """Fait progresser un assuré réservé dans toutes les étapes du parcours."""

    def __init__(self, insured_id, config: SimulationConfig, speed_getter,
                 callback: EventCallback, seed: int, simulation_id=None,
                 scenario: ScenarioAleas | None = None) -> None:
        """Initialise un passage déterministe sans démarrer son exécution."""
        self.passage_id = uuid4().hex
        self.insured_id = insured_id
        # Scénario d'aléa de l'exécution. À vide, aucun tirage n'est fait et le
        # passage se déroule exactement comme avant les crash tests.
        self.scenario = scenario or ScenarioAleas()
        self.memoire_retenue: bytearray | None = None
        # Exécution d'origine, reportée sur chaque ligne écrite par le passage.
        self.simulation_id = simulation_id
        # Carnet d'injections propre au passage : deux passages simultanés ne
        # peuvent donc pas mélanger leurs anomalies avant l'écriture.
        self.anomalies = anomalies_config.contexte(simulation_id, self.passage_id)
        self.config = config
        self.speed_getter = speed_getter
        self.callback = callback
        self.random = random.Random(seed)
        self.simulated_at = datetime.now(timezone.utc)

    async def sleep(self, simulated_seconds: float) -> None:
        """Avance l'horloge simulée en respectant la vitesse courante."""
        self.simulated_at += timedelta(seconds=simulated_seconds)
        await asyncio.sleep(simulated_seconds / self.speed_getter())

    async def emit(self, event_type: str, **payload) -> None:
        """Appelle le hook après validation de l'écriture correspondante."""
        metrics_registry.enregistrer_evenement()
        result = self.callback(SimulationEvent(
            event_type, self.passage_id, self.simulated_at, payload,
            self.simulation_id,
        ))
        if inspect.isawaitable(result):
            await result

    async def appliquer_aleas_initiaux(self) -> None:
        """Joue les aléas qui frappent avant la première écriture.

        L'horloge décalée et la saturation mémoire valent pour tout le passage :
        elles se décident une fois, au départ.
        """

        if self.scenario.frappe(HORLOGE_DECALEE, self.random):
            amplitude = self.scenario.reglage(HORLOGE_DECALEE, "amplitude_heures", 72)
            decalage = self.random.uniform(-amplitude, amplitude)
            self.simulated_at += timedelta(hours=decalage)
            await self.emit("alea.horloge_decalee", heures=round(decalage, 2))

        if self.scenario.frappe(SATURATION_MEMOIRE, self.random):
            megaoctets = int(self.scenario.reglage(SATURATION_MEMOIRE, "megaoctets", 50))
            # La mémoire est rendue à la fin du passage : l'aléa met le
            # processus sous tension, il ne cherche pas à le tuer.
            self.memoire_retenue = bytearray(megaoctets * 1024 * 1024)
            await self.emit("alea.saturation_memoire", megaoctets=megaoctets)

    async def ralentir(self) -> None:
        """Fait attendre le passage avant une écriture, base saturée.

        La latence n'est pas divisée par la vitesse : une base lente l'est en
        temps réel, quelle que soit l'accélération de l'horloge simulée.
        """

        if not self.scenario.frappe(BASE_RALENTIE, self.random):
            return
        latence = self.scenario.reglage(BASE_RALENTIE, "latence_secondes", 0.5)
        await asyncio.sleep(latence)
        await self.emit("alea.base_ralentie", latence_secondes=latence)

    async def verifier_interruption(self, etape: str) -> None:
        """Coupe le passage si un aléa d'arrêt frappe à cette étape.

        La coupure laisse volontairement la facture ouverte, sans prestation
        ni clôture : c'est exactement l'incohérence que les crash tests
        cherchent à produire.
        """

        for alea in (COUPURE_BRUTALE, PERTE_CONNEXION):
            if self.scenario.frappe(alea, self.random):
                await self.emit("alea.interruption", alea=alea, etape=etape)
                raise PassageInterrompu(alea)

    async def enregistrer_refus(self, coverage: Coverage) -> None:
        """Consigne une présentation refusée à l'accueil.

        Un refus ne produit aucune facture : sans ce registre, l'assuré qui
        s'est déplacé pour rien ne laisserait aucune trace, et la part de
        refus d'une exécution serait impossible à établir.
        """

        async with async_session_factory() as session:
            session.add(RefusAccueil(
                passage_id=self.passage_id,
                personne_uuid=self.insured_id,
                refus_date=self.simulated_at.date(),
                refus_motif=MOTIF_DROITS_FERMES,
                regime_code=coverage.regime_code,
                simulation_id=self.simulation_id,
                utilisateur_id_creation="simulation",
            ))
            await session.commit()

    async def journaliser_anomalies(self) -> None:
        """Écrit au journal les anomalies posées depuis le dernier appel.

        Appelée juste après la validation des lignes corrompues : le journal
        ne peut donc pas annoncer une anomalie que la base n'a pas reçue.
        """
        await enregistrer_injections(self.anomalies.vider())

    async def choose(self, model, *criteria):
        """Sélectionne aléatoirement une ligne active du référentiel."""
        async with async_session_factory() as session:
            statement = select(model).where(*criteria).order_by(func.random()).limit(1)
            value = (await session.execute(statement)).scalar_one_or_none()
            if value is None:
                raise RuntimeError(f"Référentiel vide pour {model.__name__}.")
            return value

    async def numero_facture(self) -> str:
        """Tire un numéro de facture : huit chiffres, unique pour toujours.

        `FACTURE_NUMERO` est la clé primaire de `TB_FACTURES`, sans remise à
        zéro par exécution : contrairement au dossier ou à l'entente, il ne
        peut pas être dérivé du hasard de `passage_id` sur seulement huit
        chiffres — l'espace (10^8) est trop petit pour une génération de
        données censée accumuler toutes les lignes de toutes les exécutions
        (paradoxe des anniversaires : la collision devient probable bien
        avant d'avoir épuisé l'espace). Une séquence Postgres (migration
        20260911_0023) garantit l'unicité même sous plusieurs passages
        concurrents, ce qu'un compteur Python en mémoire ne pourrait pas.
        """
        async with async_session_factory() as session:
            rang = (await session.execute(
                select(func.nextval("SEQ_FACTURE_NUMERO"))
            )).scalar_one()
        return f"{rang:08d}"

    @property
    def dossier_numero(self) -> str:
        """Numéro de dossier : huit caractères alphanumériques, sans préfixe.

        Dérivé du même `passage_id` que la facture et l'entente, pour qu'un
        même passage retrouve toujours le même dossier.
        """
        return self.passage_id[:8].upper()

    @property
    def entente_prealable_numero(self) -> str:
        """Numéro d'entente : huit caractères alphanumériques, sans préfixe.

        Autre tranche du même `passage_id` que `dossier_numero`, pour ne pas
        produire le même numéro sous deux noms différents.
        """
        return self.passage_id[8:16].upper()

    async def add_status(self, invoice_number: str, code: str) -> None:
        """Persiste et publie un nouveau statut de facture."""
        async with async_session_factory() as session:
            session.add(InvoiceStatus(
                facture_numero=invoice_number, statut_code=code,
                statut_date_debut=self.simulated_at.date(),
                statut_observations=f"Statut produit par le passage {self.passage_id}.",
                simulation_id=self.simulation_id,
                utilisateur_id_creation="simulation",
            ))
            await session.commit()
        await self.emit("facture.statut", facture_numero=invoice_number, statut=code)

    async def load_coverage(self) -> Coverage:
        """Lit le régime de l'assuré et l'état de ses droits au jour des soins.

        Plus rien n'est codé en dur : le taux vient de TB_TV_REGIMES, en
        vigueur à la date des soins, et l'ouverture des droits du mois
        correspondant vient de TB_ASSURES_DROITS.
        """
        soins = self.simulated_at.date()
        async with async_session_factory() as session:
            regime_code = (await session.execute(
                select(InsuredPerson.regime_code)
                .where(InsuredPerson.personne_uuid == self.insured_id)
            )).scalar_one()

            taux = (await session.execute(
                select(Regime.regime_taux).where(
                    Regime.regime_code == regime_code,
                    Regime.regime_date_debut <= self.simulated_at,
                    or_(Regime.regime_date_fin.is_(None),
                        Regime.regime_date_fin > self.simulated_at),
                ).order_by(Regime.regime_date_debut.desc()).limit(1)
            )).scalar_one_or_none()

            # Aucune ligne pour ce mois vaut droits fermés : l'assuré n'a
            # jamais été couvert, ce qui est le cas le plus fréquent.
            statut = (await session.execute(
                select(InsuredRight.droits_statut).where(
                    InsuredRight.personne_uuid == self.insured_id,
                    InsuredRight.droits_annee == soins.year,
                    InsuredRight.droits_mois == soins.month,
                )
            )).scalar_one_or_none()

        if taux is None:
            # Un régime sans ligne en vigueur ne peut rien rembourser : on
            # ferme les droits plutôt que d'inventer un taux de repli.
            logger.warning("[%s] Régime %s sans ligne en vigueur au %s.",
                           self.passage_id, regime_code, soins)
            return Coverage(regime_code or "INCONNU", Decimal("0"), False)
        return Coverage(regime_code, taux, statut == 1)

    async def run(self) -> None:
        """Exécute la state machine jusqu'à la clôture de la facture.

        La mémoire retenue par un aléa de saturation est rendue quoi qu'il
        arrive : un passage interrompu ne doit pas la garder.
        """
        try:
            await self._derouler()
        finally:
            self.memoire_retenue = None

    async def _derouler(self) -> None:
        """Enchaîne les étapes du parcours, aléas compris."""
        await self.appliquer_aleas_initiaux()
        coverage = await self.load_coverage()

        # Contrôle des droits à l'accueil. Dans le système réel, une facture
        # ne s'ouvre que sur des droits ouverts : sans eux, le passage
        # s'arrête ici et aucune facture n'est créée.
        if not coverage.droits_ouverts:
            logger.info("[%s] Passage refusé à l'accueil : droits fermés au %s.",
                        self.passage_id, self.simulated_at.date())
            await self.enregistrer_refus(coverage)
            await self.emit("passage.refuse", motif=MOTIF_DROITS_FERMES,
                            regime=coverage.regime_code)
            return

        center = await self.choose(HealthCenter)
        professional = await self.choose(HealthProfessional)
        invoice_number = await self.numero_facture()
        ambulatory = self.random.random() < self.config.ambulatory_probability
        invoice_type = "AMB" if ambulatory else "DEN"
        logger.info("[%s] Ouverture %s au centre %s (régime %s à %s %%).",
                    self.passage_id, invoice_number, center.centre_sante_code,
                    coverage.regime_code, coverage.taux)

        # 1. Création de la facture
        await self.ralentir()
        # Trois anomalies visent la même date, chacune à sa façon : antidatée,
        # projetée dans l'avenir, ou sortie de la période de droits. Elles
        # s'appliquent l'une après l'autre, la dernière l'emportant.
        date_soins = self.anomalies.injecter_date(self.simulated_at.date(), invoice_number)
        date_soins = self.anomalies.injecter_date_future(date_soins, invoice_number)
        date_soins = self.anomalies.injecter_date_hors_droits(date_soins, invoice_number)

        async with async_session_factory() as session:
            session.add(Invoice(
                facture_numero=invoice_number, produit_code="CMU",
                regime_code=coverage.regime_code,
                regime_taux=coverage.taux, organisme_code="CNAM-CI",
                assurance_code="CMU", personne_uuid=self.insured_id,
                type_facture_code=invoice_type,
                facture_date_soins=date_soins,
                dossier_numero=self.dossier_numero,
                centre_sante_code=center.centre_sante_code,
                centre_sante_type_code=self.anomalies.injecter_type_centre(
                    center.type_etablissement_sanitaire_code, invoice_number
                ),
                centre_sante_type_libelle=LIBELLES_TYPE_CENTRE.get(
                    center.type_etablissement_sanitaire_code
                ),
                simulation_id=self.simulation_id,
                utilisateur_id_creation="simulation",
            ))
            await session.commit()
        await self.journaliser_anomalies()
        await self.emit("facture.creee", facture_numero=invoice_number, type=invoice_type)
        await self.add_status(invoice_number, "ouverte")

        # La facture est ouverte mais rien n'est encore facturé : c'est ici
        # qu'une coupure laisse la trace la plus révélatrice.
        await self.verifier_interruption("facture_ouverte")

        # 2. Ajout des pathologies
        pathologies = []
        async with async_session_factory() as session:
            result = await session.execute(select(Pathology).order_by(func.random()).limit(self.random.randint(1, 3)))
            for pathology in result.scalars():
                pathologies.append(pathology.pathologie_code)
                session.add(InvoicePathology(
                    facture_numero=invoice_number,
                    pathologie_code=pathology.pathologie_code,
                    pathologie_date_debut=pathology.pathologie_date_debut,
                    pathologie_observations="Diagnostic synthétique du simulateur.",
                    simulation_id=self.simulation_id,
                    utilisateur_id_creation="simulation",
                ))
            await session.commit()
        await self.emit("facture.pathologies", facture_numero=invoice_number, codes=pathologies)

        # 3. Consultation médicale
        await self.sleep(self.random.uniform(
            self.config.consultation_min_seconds, self.config.consultation_max_seconds
        ))
        base_code = "CONS-GEN" if ambulatory else self.random.choice(["DENT-DET", "DENT-EXT", "DENT-CAR"])
        await self.ralentir()
        montant_depense = self.anomalies.injecter_montant(Decimal("10000"), invoice_number)
        quantite_servie = self.anomalies.injecter_quantite(1, 1, invoice_number)
        quantite_servie = self.anomalies.injecter_quantite_nulle(quantite_servie, invoice_number)
        code_prestation = self.anomalies.injecter_code_prestation(base_code, invoice_number)

        # Le taux vient du régime de l'assuré ; l'anomalie hors barème lui en
        # substitue un qui appartient à l'autre régime.
        taux = self.anomalies.injecter_taux(coverage.taux, coverage.regime_code, invoice_number)
        base = Decimal("10000")
        montant_rq = (base * taux / Decimal("100")).quantize(Decimal("0.01"))
        part_assure = self.anomalies.injecter_part_assure(base - montant_rq, invoice_number)

        async with async_session_factory() as session:
            session.add(InvoiceProvision(
                facture_numero=invoice_number, prestation_code=code_prestation,
                professionnel_sante_code=professional.professionnel_sante_code,
                statut_remboursement="couvert",
                prestation_base_remboursement=base,
                prestation_taux_remboursement=taux, prestation_quantite_prescrite=1,
                prestation_quantite_servie=quantite_servie, prestation_prix_unitaire=base,
                prestation_montant_depense=montant_depense,
                prestation_montant_rq=montant_rq,
                prestation_montant_assure=part_assure,
                statut_code="servie", simulation_id=self.simulation_id,
                utilisateur_id_creation="simulation",
            ))
            await session.commit()
        await self.journaliser_anomalies()
        await self.emit("prestation.servie", facture_numero=invoice_number,
                        code=code_prestation)

        # 4. Prescriptions et Ententes
        medications = self.random.random() < self.config.medication_probability
        needs_biology = ambulatory and self.random.random() < self.config.biology_imaging_probability
        needs_hospital = ambulatory and self.random.random() < self.config.hospitalization_probability

        if medications:
            medicine = await self.choose(Medication)
            async with async_session_factory() as session:
                session.add(InvoicePrescription(
                    facture_numero=invoice_number, prescription_code=medicine.medicament_code,
                    date_debut=self.simulated_at.date(), prescription_quantite=1,
                    prescription_posologie="Selon prescription médicale synthétique.",
                    prescription_duree=5, simulation_id=self.simulation_id,
                    utilisateur_id_creation="simulation",
                ))
                await session.commit()
            await self.emit("medicament.prescrit", facture_numero=invoice_number, code=medicine.medicament_code)

        if needs_biology or needs_hospital:
            await self.process_prior_authorization(
                invoice_number, center.centre_sante_code,
                professional.professionnel_sante_code, needs_hospital,
                coverage.taux,
            )

        if medications:
            await self.sleep(self.random.uniform(
                self.config.pharmacy_min_delay_seconds,
                self.config.pharmacy_max_delay_seconds,
            ))
            await self.emit("medicament.retire", facture_numero=invoice_number)

        # 5. Clôture de la facture
        await self.verifier_interruption("avant_cloture")
        await self.add_status(invoice_number, "cloturee")
        logger.info("[%s] Facture %s clôturée.", self.passage_id, invoice_number)

    async def process_prior_authorization(self, invoice_number: str, center_code: str,
                                          professional_code: str, hospital: bool,
                                          taux: Decimal) -> None:
        """Crée, attend et décide une entente préalable acte par acte.

        Le taux reçu est celui du régime de l'assuré : un bénéficiaire du
        régime d'assistance médicale voit son acte pris en charge à 100 %.
        """
        if hospital:
            criterion = MedicalAct.acte_medical_code.like("HOS-%")
        else:
            criterion = (
                    MedicalAct.acte_medical_code.like("BIO-%")
                    | MedicalAct.acte_medical_code.like("IMG-%")
            )
        act = await self.choose(MedicalAct, criterion)
        async with async_session_factory() as session:
            agreement = PriorAuthorization(
                entente_prealable_numero=self.entente_prealable_numero,
                centre_sante_code=center_code, personne_uuid=self.insured_id,
                dossier_numero=self.dossier_numero,
                entente_prealable_date_debut=self.simulated_at,
                organisme_code="CNAM-CI", facture_numero=invoice_number,
                type_demande_code="hospitalisation" if hospital else "acte",
                type_hospitalisation_code="standard" if hospital else None,
                simulation_id=self.simulation_id,
                utilisateur_id_creation="simulation",
            )
            session.add(agreement)
            await session.flush()
            agreement_id = agreement.entente_prealable_id
            invoice = await session.get(Invoice, invoice_number)
            invoice.entente_prealable_id = agreement_id
            await session.commit()
        await self.emit("entente.creee", facture_numero=invoice_number, entente_id=agreement_id)

        response_delay = self.random.expovariate(1 / self.config.advice_mean_delay_seconds)
        await self.sleep(response_delay)
        automatic = response_delay >= self.config.automatic_approval_limit_seconds
        accepted = automatic or self.random.random() < self.config.prior_authorization_acceptance_probability
        advisor = None if automatic else await self.choose(Agent, Agent.agent_type_code == "medecin_conseil")
        status = "validee_office" if automatic else ("acceptee" if accepted else "refusee")
        amount = self.anomalies.injecter_montant(
            Decimal("50000") if hospital else Decimal("15000"),
            self.entente_prealable_numero,
        )
        cmu_amount = ((amount * taux / Decimal("100")).quantize(Decimal("0.01"))
                      if accepted else Decimal("0"))
        # Date de fin de l'entente = moment de la décision, pas une échéance
        # de validité : le moteur ne modélise aucune durée de couverture.
        decision_at = self.simulated_at + timedelta(seconds=round(response_delay))

        async with async_session_factory() as session:
            agreement = await session.get(PriorAuthorization, agreement_id)
            agreement.entente_prealable_date_fin = decision_at
            session.add(PriorAuthorizationMedicalAct(
                entente_prealable_id=agreement_id, acte_medical_code=act.acte_medical_code,
                professionnel_sante_code=professional_code,
                acte_medical_motif="Prescription issue du parcours simulé.",
                acte_medical_base_remboursement=amount,
                acte_medical_taux_remboursement=taux if accepted else Decimal("0"),
                acte_medical_montant_cmu=cmu_amount,
                acte_medical_montant_assure=amount - cmu_amount,
                acte_medical_statut=status,
                acte_medical_motif_rejet=None if accepted else "Refus simulé du médecin conseil.",
                simulation_id=self.simulation_id,
                utilisateur_id_creation="simulation",
            ))
            session.add(PriorAuthorizationStatus(
                entente_prealable_id=agreement_id, statut_code=status,
                statut_date_debut=decision_at,
                agent_code=None if advisor is None else advisor.agent_code,
                simulation_id=self.simulation_id,
                utilisateur_id_creation="simulation",
            ))
            await session.commit()
        await self.journaliser_anomalies()
        await self.emit("entente.traitee", entente_id=agreement_id, statut=status,
                        delai_secondes=round(response_delay))