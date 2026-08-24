"""Configuration et injecteurs d'anomalies.

Les anomalies douces sont des données incohérentes qui respectent les
contraintes SQL mais révèlent les bugs métier : montants négatifs, dates
antidatées, quantités servies supérieures aux quantités prescrites. Les
anomalies dures, elles, sont invalides au premier regard.

Chaque type se règle séparément dans le catalogue (activé ou non, à son
propre taux) ; l'interrupteur global reste au-dessus et coupe tout.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, NamedTuple
from uuid import UUID

from anomalies.catalogue import (
    CODES, DATE_ANTIDATEE, DATE_HORS_DROITS, DATE_NAISSANCE_ABERRANTE,
    DATE_SOINS_FUTURE, DECLENCHEMENT_CONTINU, DECLENCHEMENT_DEMARRAGE,
    DECLENCHEMENT_DIFFERE, DECLENCHEMENT_MANUEL, DELAI_PAR_DEFAUT,
    EMAIL_INVALIDE, MONTANT_ABERRANT, MONTANT_HORS_BAREME,
    NUMERO_SECU_INVALIDE, PRESTATION_ORPHELINE, QUANTITE_EXCESSIVE,
    QUANTITE_NULLE, REPARTITION_FAUSSEE, TYPE_CENTRE_INCONNU,
)


class Tirage(NamedTuple):
    """Résultat d'un tirage : la valeur retenue, et si elle est faussée."""

    valeur: Any
    injectee: bool


@dataclass
class Injection:
    """Une anomalie posée, en attente d'écriture dans le journal."""

    anomalie_code: str
    valeur_origine: str
    valeur_injectee: str
    cible_cle: str | None = None
    passage_id: str | None = None
    simulation_id: UUID | None = None


@dataclass
class Reglage:
    """Ce que le catalogue dit d'un type : quand il agit, et à quel taux.

    Un taux nul signifie « pas encore réglé » : le type retombe alors sur le
    taux global, ce qui préserve le comportement d'avant le catalogue.
    """

    active: bool = True
    taux: float | None = None
    declenchement: str = DECLENCHEMENT_CONTINU
    delai_secondes: int | None = None
    # Vrai quand l'opérateur a armé un type « manuel » en cours d'exécution.
    arme: bool = False

    def en_scene(self, secondes_ecoulees: float) -> bool:
        """Dit si le type doit agir, au vu du temps écoulé depuis le départ."""

        delai = DELAI_PAR_DEFAUT if self.delai_secondes is None else self.delai_secondes

        if self.declenchement == DECLENCHEMENT_DEMARRAGE:
            # Une salve initiale, puis le silence.
            return secondes_ecoulees <= delai
        if self.declenchement == DECLENCHEMENT_DIFFERE:
            # Le silence, puis jusqu'à la fin.
            return secondes_ecoulees >= delai
        if self.declenchement == DECLENCHEMENT_MANUEL:
            return self.arme
        return True


class AnomaliesConfig:
    """Réglage global et catalogue, partagés par le seed, le moteur et l'API."""

    def __init__(
        self,
        enabled: bool = False,
        rate: float = 0.0,
        seed: int = 42,
        severity: str = "soft",
    ) -> None:
        self.enabled = enabled
        self.rate = max(0.0, min(1.0, rate))
        self.random = random.Random(seed)
        self.severity = severity
        self.injected_count = 0
        # Tous les types sont ouverts tant que le catalogue n'a pas été lu :
        # sans cela, une base neuve n'injecterait jamais rien.
        self.reglages: dict[str, Reglage] = {code: Reglage() for code in CODES}
        # Départ de l'exécution en cours, d'où se compte le moment d'injection.
        # Nul hors exécution : le seed injecte alors sans horloge.
        self.debut_execution: datetime | None = None

    # ── Décision ─────────────────────────────────────────────────────────

    def reglage(self, code: str) -> Reglage:
        """Retourne le réglage d'un type, ouvert par défaut s'il est inconnu."""

        return self.reglages.setdefault(code, Reglage())

    def taux_effectif(self, code: str) -> float:
        """Retourne le taux du type, ou le taux global s'il n'en a pas."""

        taux = self.reglage(code).taux
        return self.rate if taux is None else taux

    def secondes_ecoulees(self) -> float:
        """Temps réel écoulé depuis le début de l'exécution en cours.

        Hors exécution, on répond zéro : un type différé se tait, un type de
        démarrage agit — ce qui est le comportement attendu du seed.
        """

        if self.debut_execution is None:
            return 0.0
        return (datetime.now(timezone.utc) - self.debut_execution).total_seconds()

    def demarrer_execution(self) -> None:
        """Remet l'horloge des moments à zéro et désarme les types manuels."""

        self.debut_execution = datetime.now(timezone.utc)
        for reglage in self.reglages.values():
            reglage.arme = False

    def armer(self, code: str, arme: bool = True) -> None:
        """Arme ou désarme un type manuel, pendant que le moteur tourne."""

        self.reglage(code).arme = arme

    def should_inject(self, code: str | None = None) -> bool:
        """Décide s'il faut injecter : interrupteur global, type, puis moment."""

        if not self.enabled:
            return False
        if code is None:
            return self.random.random() < self.rate
        reglage = self.reglage(code)
        if not reglage.active:
            return False
        if not reglage.en_scene(self.secondes_ecoulees()):
            return False
        return self.random.random() < self.taux_effectif(code)

    def record_injection(self) -> None:
        """Incrémente le compteur affiché par le dashboard."""
        self.injected_count += 1

    # ── Tirages : la valeur, et si elle a été faussée ────────────────────

    def tirer_montant(self, montant: Decimal) -> Tirage:
        """Tire un montant négatif ou démesuré, ou laisse la valeur d'origine."""
        if not self.should_inject(MONTANT_ABERRANT):
            return Tirage(montant, False)
        self.record_injection()
        if self.random.random() < 0.5:
            return Tirage(Decimal("-1000.00"), True)
        return Tirage(Decimal("999999999.99"), True)

    def tirer_date(self, valeur: date) -> Tirage:
        """Tire une date antidatée jusqu'à un an, ou laisse la valeur."""
        if not self.should_inject(DATE_ANTIDATEE):
            return Tirage(valeur, False)
        self.record_injection()
        return Tirage(valeur - timedelta(days=self.random.randint(1, 365)), True)

    def tirer_quantite(self, prescrite: int, servie: int) -> Tirage:
        """Tire une quantité servie supérieure à la quantité prescrite."""
        if not self.should_inject(QUANTITE_EXCESSIVE):
            return Tirage(servie, False)
        self.record_injection()
        return Tirage(prescrite + self.random.randint(1, 20), True)

    def tirer_numero_secu(self, numero: str) -> Tirage:
        """Tire un numéro de sécurité sociale manifestement invalide."""
        if not self.should_inject(NUMERO_SECU_INVALIDE):
            return Tirage(numero, False)
        self.record_injection()
        return Tirage("00000000000000", True)

    def tirer_email(self, email: str) -> Tirage:
        """Tire une adresse électronique invalide."""
        if not self.should_inject(EMAIL_INVALIDE):
            return Tirage(email, False)
        self.record_injection()
        return Tirage("pas_un_email_valide", True)

    def tirer_taux(self, taux: Decimal, regime_code: str | None) -> Tirage:
        """Tire un taux étranger au régime : 100 % sur du RGB, 70 % sur du RAM.

        Le taux reste plausible pris isolément — c'est tout l'intérêt : seule
        la confrontation au régime de l'assuré révèle l'incohérence.
        """
        if not self.should_inject(MONTANT_HORS_BAREME):
            return Tirage(taux, False)
        self.record_injection()
        return Tirage(Decimal("70") if regime_code == "RAM" else Decimal("100"), True)

    def tirer_part_assure(self, part: Decimal) -> Tirage:
        """Tire une part assuré qui ne recompose plus la base remboursable."""
        if not self.should_inject(REPARTITION_FAUSSEE):
            return Tirage(part, False)
        self.record_injection()
        ecart = Decimal(self.random.randrange(500, 5000))
        return Tirage(part + ecart, True)

    def tirer_date_future(self, valeur: date) -> Tirage:
        """Tire une date de soins postérieure au jour de la facture."""
        if not self.should_inject(DATE_SOINS_FUTURE):
            return Tirage(valeur, False)
        self.record_injection()
        return Tirage(valeur + timedelta(days=self.random.randint(8, 180)), True)

    def tirer_date_hors_droits(self, valeur: date) -> Tirage:
        """Tire une date de soins hors de la période de droits couverte.

        Le décalage reste dans l'année, mais change de mois : les droits sont
        ouverts mois par mois, un mois de plus suffit à sortir de la période.
        """
        if not self.should_inject(DATE_HORS_DROITS):
            return Tirage(valeur, False)
        self.record_injection()
        return Tirage(valeur - timedelta(days=self.random.randint(40, 300)), True)

    def tirer_quantite_nulle(self, servie: int) -> Tirage:
        """Tire une quantité servie nulle malgré une prescription."""
        if not self.should_inject(QUANTITE_NULLE):
            return Tirage(servie, False)
        self.record_injection()
        return Tirage(0, True)

    def tirer_date_naissance(self, valeur):
        """Tire une date de naissance impossible : à venir, ou plus que centenaire."""
        if not self.should_inject(DATE_NAISSANCE_ABERRANTE):
            return Tirage(valeur, False)
        self.record_injection()
        if valeur is None:
            return Tirage(valeur, False)
        if self.random.random() < 0.5:
            return Tirage(valeur + timedelta(days=self.random.randint(400, 3000)), True)
        return Tirage(valeur - timedelta(days=self.random.randint(45000, 55000)), True)

    def tirer_type_centre(self, code: str | None) -> Tirage:
        """Tire un code de type d'établissement qui n'existe nulle part."""
        if not self.should_inject(TYPE_CENTRE_INCONNU):
            return Tirage(code, False)
        self.record_injection()
        return Tirage(f"ZZ{self.random.randrange(10, 99)}", True)

    def tirer_code_prestation(self, code: str) -> Tirage:
        """Tire un code de prestation absent du référentiel des actes."""
        if not self.should_inject(PRESTATION_ORPHELINE):
            return Tirage(code, False)
        self.record_injection()
        return Tirage(f"INCONNU-{self.random.randrange(1000, 9999)}", True)

    # ── Injecteurs sans contexte, pour les appelants qui ne journalisent pas ──

    def injecter_montant(self, montant: Decimal) -> Decimal:
        """Retourne un montant faussé ou la valeur d'origine, sans journal."""
        return self.tirer_montant(montant).valeur

    def injecter_date(self, valeur: date) -> date:
        """Retourne une date faussée ou la valeur d'origine, sans journal."""
        return self.tirer_date(valeur).valeur

    def injecter_quantite(self, prescrite: int, servie: int) -> int:
        """Retourne une quantité faussée ou la valeur d'origine, sans journal."""
        return self.tirer_quantite(prescrite, servie).valeur

    def injecter_numero_secu(self, numero: str) -> str:
        """Retourne un numéro faussé ou la valeur d'origine, sans journal."""
        return self.tirer_numero_secu(numero).valeur

    def injecter_email(self, email: str) -> str:
        """Retourne une adresse faussée ou la valeur d'origine, sans journal."""
        return self.tirer_email(email).valeur

    def contexte(self, simulation_id: UUID | None = None,
                 passage_id: str | None = None) -> ContexteInjection:
        """Ouvre un carnet d'injections rattaché à une exécution."""

        return ContexteInjection(self, simulation_id, passage_id)


@dataclass
class ContexteInjection:
    """Injecte comme la configuration, et retient ce qui a été posé.

    Chaque passage ouvre le sien : deux passages simultanés ne peuvent donc
    pas mélanger leurs injections avant que le journal ne soit écrit.
    """

    config: AnomaliesConfig
    simulation_id: UUID | None = None
    passage_id: str | None = None
    injections: list[Injection] = field(default_factory=list)

    def _retenir(self, code: str, origine: Any, tirage: Tirage,
                 cible_cle: str | None) -> Any:
        """Consigne l'injection si elle a eu lieu, puis rend la valeur."""

        if tirage.injectee:
            self.injections.append(Injection(
                anomalie_code=code,
                valeur_origine=str(origine),
                valeur_injectee=str(tirage.valeur),
                cible_cle=cible_cle,
                passage_id=self.passage_id,
                simulation_id=self.simulation_id,
            ))
        return tirage.valeur

    def injecter_montant(self, montant: Decimal, cible_cle: str | None = None) -> Decimal:
        """Fausse un montant et le consigne."""
        return self._retenir(MONTANT_ABERRANT, montant,
                             self.config.tirer_montant(montant), cible_cle)

    def injecter_date(self, valeur: date, cible_cle: str | None = None) -> date:
        """Fausse une date de soins et la consigne."""
        return self._retenir(DATE_ANTIDATEE, valeur,
                             self.config.tirer_date(valeur), cible_cle)

    def injecter_quantite(self, prescrite: int, servie: int,
                          cible_cle: str | None = None) -> int:
        """Fausse une quantité servie et la consigne."""
        return self._retenir(QUANTITE_EXCESSIVE, servie,
                             self.config.tirer_quantite(prescrite, servie), cible_cle)

    def injecter_numero_secu(self, numero: str, cible_cle: str | None = None) -> str:
        """Fausse un numéro de sécurité sociale et le consigne."""
        return self._retenir(NUMERO_SECU_INVALIDE, numero,
                             self.config.tirer_numero_secu(numero), cible_cle)

    def injecter_email(self, email: str, cible_cle: str | None = None) -> str:
        """Fausse une adresse électronique et la consigne."""
        return self._retenir(EMAIL_INVALIDE, email,
                             self.config.tirer_email(email), cible_cle)

    def injecter_taux(self, taux: Decimal, regime_code: str | None,
                      cible_cle: str | None = None) -> Decimal:
        """Fausse un taux de remboursement et le consigne."""
        return self._retenir(MONTANT_HORS_BAREME, taux,
                             self.config.tirer_taux(taux, regime_code), cible_cle)

    def injecter_part_assure(self, part: Decimal, cible_cle: str | None = None) -> Decimal:
        """Fausse la part restant à l'assuré et la consigne."""
        return self._retenir(REPARTITION_FAUSSEE, part,
                             self.config.tirer_part_assure(part), cible_cle)

    def injecter_date_future(self, valeur: date, cible_cle: str | None = None) -> date:
        """Repousse la date de soins dans l'avenir et la consigne."""
        return self._retenir(DATE_SOINS_FUTURE, valeur,
                             self.config.tirer_date_future(valeur), cible_cle)

    def injecter_date_hors_droits(self, valeur: date, cible_cle: str | None = None) -> date:
        """Sort la date de soins de la période de droits et la consigne."""
        return self._retenir(DATE_HORS_DROITS, valeur,
                             self.config.tirer_date_hors_droits(valeur), cible_cle)

    def injecter_quantite_nulle(self, servie: int, cible_cle: str | None = None) -> int:
        """Annule la quantité servie et la consigne."""
        return self._retenir(QUANTITE_NULLE, servie,
                             self.config.tirer_quantite_nulle(servie), cible_cle)

    def injecter_date_naissance(self, valeur, cible_cle: str | None = None):
        """Fausse une date de naissance et la consigne."""
        return self._retenir(DATE_NAISSANCE_ABERRANTE, valeur,
                             self.config.tirer_date_naissance(valeur), cible_cle)

    def injecter_type_centre(self, code: str | None, cible_cle: str | None = None) -> str | None:
        """Remplace le type d'établissement par un code inconnu, et le consigne."""
        return self._retenir(TYPE_CENTRE_INCONNU, code,
                             self.config.tirer_type_centre(code), cible_cle)

    def injecter_code_prestation(self, code: str, cible_cle: str | None = None) -> str:
        """Remplace le code de prestation par un code orphelin, et le consigne."""
        return self._retenir(PRESTATION_ORPHELINE, code,
                             self.config.tirer_code_prestation(code), cible_cle)

    def vider(self) -> list[Injection]:
        """Rend les injections accumulées et repart d'un carnet vide."""

        posees, self.injections = self.injections, []
        return posees


# Instance unique partagée par tout le processus (seed, moteur, API).
anomalies_config = AnomaliesConfig()


def apply_anomalies_to_row(
    row: dict[str, Any], config: AnomaliesConfig | ContexteInjection, row_type: str
) -> dict[str, Any]:
    """Applique les anomalies à une ligne du seed selon son type.

    Accepte aussi bien la configuration nue qu'un contexte : le seed passe le
    second pour que ses injections soient consignées.
    """
    reglage = config.config if isinstance(config, ContexteInjection) else config
    if not reglage.enabled:
        return row

    # La clé métier n'est transmise qu'au contexte : la configuration nue ne
    # journalise pas et n'en a pas l'usage.
    journalise = isinstance(config, ContexteInjection)

    if row_type == "agent" and "agent_email" in row:
        cle = {"cible_cle": row.get("agent_code")} if journalise else {}
        row["agent_email"] = config.injecter_email(row["agent_email"], **cle)
    elif row_type == "insured" and "numero_secu" in row:
        cle = {"cible_cle": str(row.get("personne_uuid"))} if journalise else {}
        row["numero_secu"] = config.injecter_numero_secu(row["numero_secu"], **cle)
        if journalise and "assure_date_naissance" in row:
            row["assure_date_naissance"] = config.injecter_date_naissance(
                row["assure_date_naissance"], **cle
            )

    return row
