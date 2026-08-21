"""Centralise toutes les probabilités et durées du moteur de simulation."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    """Paramètres métier modifiables sans toucher à la state machine."""

    ambulatory_probability: float = 0.70
    medication_probability: float = 0.60
    biology_imaging_probability: float = 0.25
    hospitalization_probability: float = 0.05
    prior_authorization_acceptance_probability: float = 0.85
    automatic_approval_limit_seconds: float = 4 * 60 * 60
    advice_mean_delay_seconds: float = 90 * 60
    pharmacy_min_delay_seconds: float = 2 * 60 * 60
    pharmacy_max_delay_seconds: float = 3 * 24 * 60 * 60
    passage_arrival_mean_seconds: float = 10 * 60
    consultation_min_seconds: float = 15 * 60
    consultation_max_seconds: float = 60 * 60
    # Le taux de remboursement n'est plus un paramètre du moteur : il dépend
    # du régime de l'assuré et se lit dans TB_TV_REGIMES.
    default_speed: float = 60.0
    max_concurrent_passages: int = 20
    random_seed: int = 326


DEFAULT_CONFIG = SimulationConfig()