from __future__ import annotations

import asyncio
import inspect
import logging
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from app.database import async_session_factory
from app.models import (
    Agent, HealthCenter, HealthProfessional, InsuredPerson, Invoice,
    InvoicePathology, InvoicePrescription, InvoiceProvision, InvoiceStatus,
    MedicalAct, Medication, Pathology, PriorAuthorization,
    PriorAuthorizationMedicalAct, PriorAuthorizationStatus,
)
from simulation.events import EventCallback, SimulationEvent
from simulation_config import SimulationConfig

logger = logging.getLogger(__name__)

class PassageSimulation:
    """Fait progresser un assuré réservé dans toutes les étapes du parcours."""

    def __init__(self, insured_id, config: SimulationConfig, speed_getter,
                 callback: EventCallback, seed: int) -> None:
        """Initialise un passage déterministe sans démarrer son exécution."""
        self.passage_id = uuid4().hex
        self.insured_id = insured_id
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
        result = self.callback(SimulationEvent(
            event_type, self.passage_id, self.simulated_at, payload
        ))
        if inspect.isawaitable(result):
            await result

    async def choose(self, model, *criteria):
        """Sélectionne aléatoirement une ligne active du référentiel."""
        async with async_session_factory() as session:
            statement = select(model).where(*criteria).order_by(func.random()).limit(1)
            value = (await session.execute(statement)).scalar_one_or_none()
            if value is None:
                raise RuntimeError(f"Référentiel vide pour {model.__name__}.")
            return value

    async def add_status(self, invoice_number: str, code: str) -> None:
        """Persiste et publie un nouveau statut de facture."""
        async with async_session_factory() as session:
            session.add(InvoiceStatus(
                facture_numero=invoice_number, statut_code=code,
                statut_date_debut=self.simulated_at.date(),
                statut_observations=f"Statut produit par le passage {self.passage_id}.",
                utilisateur_id_creation="simulation",
            ))
            await session.commit()
        await self.emit("facture.statut", facture_numero=invoice_number, statut=code)

    async def run(self) -> None:
        """Exécute la state machine jusqu'à la clôture de la facture."""
        center = await self.choose(HealthCenter)
        professional = await self.choose(HealthProfessional)
        invoice_number = f"FAC-{self.simulated_at:%Y%m%d}-{self.passage_id[:10]}"
        ambulatory = self.random.random() < self.config.ambulatory_probability
        invoice_type = "AMB" if ambulatory else "DEN"
        logger.info("[%s] Ouverture %s au centre %s.", self.passage_id, invoice_number, center.centre_sante_code)

        # 1. Création de la facture
        async with async_session_factory() as session:
            session.add(Invoice(
                facture_numero=invoice_number, produit_code="CMU", regime_code="CMU",
                regime_taux=Decimal("70"), organisme_code="CNAM-CI",
                assurance_code="CMU", personne_uuid=self.insured_id,
                type_facture_code=invoice_type, facture_date_soins=self.simulated_at.date(),
                dossier_numero=f"DOS-{self.passage_id[:12]}",
                centre_sante_code=center.centre_sante_code,
                centre_sante_type_code=center.type_etablissement_sanitaire_code,
                centre_sante_type_libelle=center.centre_sante_denomination,
                utilisateur_id_creation="simulation",
            ))
            await session.commit()
        await self.emit("facture.creee", facture_numero=invoice_number, type=invoice_type)
        await self.add_status(invoice_number, "ouverte")

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
                    utilisateur_id_creation="simulation",
                ))
            await session.commit()
        await self.emit("facture.pathologies", facture_numero=invoice_number, codes=pathologies)

        # 3. Consultation médicale
        await self.sleep(self.random.uniform(
            self.config.consultation_min_seconds, self.config.consultation_max_seconds
        ))
        base_code = "CONS-GEN" if ambulatory else self.random.choice(["DENT-DET", "DENT-EXT", "DENT-CAR"])
        async with async_session_factory() as session:
            session.add(InvoiceProvision(
                facture_numero=invoice_number, prestation_code=base_code,
                professionnel_sante_code=professional.professionnel_sante_code,
                statut_remboursement="couvert", prestation_base_remboursement=Decimal("10000"),
                prestation_taux_remboursement=Decimal("70"), prestation_quantite_prescrite=1,
                prestation_quantite_servie=1, prestation_prix_unitaire=Decimal("10000"),
                prestation_montant_depense=Decimal("10000"), prestation_montant_assure=Decimal("3000"),
                statut_code="servie", utilisateur_id_creation="simulation",
            ))
            await session.commit()
        await self.emit("prestation.servie", facture_numero=invoice_number, code=base_code)

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
                    prescription_duree=5, utilisateur_id_creation="simulation",
                ))
                await session.commit()
            await self.emit("medicament.prescrit", facture_numero=invoice_number, code=medicine.medicament_code)

        if needs_biology or needs_hospital:
            await self.process_prior_authorization(
                invoice_number, center.centre_sante_code,
                professional.professionnel_sante_code, needs_hospital,
            )

        if medications:
            await self.sleep(self.random.uniform(
                self.config.pharmacy_min_delay_seconds,
                self.config.pharmacy_max_delay_seconds,
            ))
            await self.emit("medicament.retire", facture_numero=invoice_number)

        # 5. Clôture de la facture
        await self.add_status(invoice_number, "cloturee")
        logger.info("[%s] Facture %s clôturée.", self.passage_id, invoice_number)

    async def process_prior_authorization(self, invoice_number: str, center_code: str,
                                          professional_code: str, hospital: bool) -> None:
        """Crée, attend et décide une entente préalable acte par acte."""
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
                entente_prealable_numero=f"EP-{self.passage_id[:12]}",
                centre_sante_code=center_code, personne_uuid=self.insured_id,
                dossier_numero=f"DOS-{self.passage_id[:12]}",
                entente_prealable_date_debut=self.simulated_at.date(),
                organisme_code="CNAM-CI", facture_numero=invoice_number,
                type_demande_code="hospitalisation" if hospital else "acte",
                type_hospitalisation_code="standard" if hospital else None,
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
        amount = Decimal("50000") if hospital else Decimal("15000")
        cmu_amount = amount * Decimal(str(self.config.cmu_reimbursement_rate)) if accepted else Decimal("0")

        async with async_session_factory() as session:
            session.add(PriorAuthorizationMedicalAct(
                entente_prealable_id=agreement_id, acte_medical_code=act.acte_medical_code,
                professionnel_sante_code=professional_code,
                acte_medical_motif="Prescription issue du parcours simulé.",
                acte_medical_base_remboursement=amount,
                acte_medical_taux_remboursement=Decimal("70") if accepted else Decimal("0"),
                acte_medical_montant_cmu=cmu_amount,
                acte_medical_montant_assure=amount - cmu_amount,
                acte_medical_statut=status,
                acte_medical_motif_rejet=None if accepted else "Refus simulé du médecin conseil.",
                utilisateur_id_creation="simulation",
            ))
            session.add(PriorAuthorizationStatus(
                entente_prealable_id=agreement_id, statut_code=status,
                statut_date_debut=self.simulated_at.date(),
                agent_code=None if advisor is None else advisor.agent_code,
                utilisateur_id_creation="simulation",
            ))
            await session.commit()
        await self.emit("entente.traitee", entente_id=agreement_id, statut=status,
                        delai_secondes=round(response_delay))