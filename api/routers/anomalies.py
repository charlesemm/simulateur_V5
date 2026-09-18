"""Gestion de la configuration des anomalies du simulateur."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from anomalies import anomalies_config
from anomalies.catalogue import CODES_MOTEUR, DECLENCHEMENTS, FAMILLES
from anomalies.models import AnomalyInjection
from anomalies.repository import (
    lire_catalogue, modifier_type, sauvegarder_configuration,
)
from app.database import async_session_factory
from auth.dependencies import require_role

router = APIRouter(
    prefix="/anomalies",
    tags=["anomalies"],
    dependencies=[Depends(require_role("administrateur"))],
)


class AnomaliesConfigRequest(BaseModel):
    """Requête pour modifier la configuration."""
    enabled: bool | None = None
    rate: float | None = Field(None, ge=0.0, le=1.0)
    severity: str | None = None


class AnomaliesConfigResponse(BaseModel):
    """Réponse avec la configuration actuelle."""
    enabled: bool
    rate: float
    severity: str
    injected_count: int


@router.get("", response_model=AnomaliesConfigResponse)
async def get_anomalies_config() -> AnomaliesConfigResponse:
    """Retourne la configuration courante des anomalies."""
    return AnomaliesConfigResponse(
        enabled=anomalies_config.enabled,
        rate=anomalies_config.rate,
        severity=anomalies_config.severity,
        injected_count=anomalies_config.injected_count,
    )


@router.patch("", response_model=AnomaliesConfigResponse)
async def update_anomalies_config(payload: AnomaliesConfigRequest) -> AnomaliesConfigResponse:
    """Modifie la configuration à la volée (en mémoire uniquement pour v1)."""
    if payload.enabled is not None:
        anomalies_config.enabled = payload.enabled
    if payload.rate is not None:
        anomalies_config.rate = payload.rate
    if payload.severity is not None:
        anomalies_config.severity = payload.severity

    await sauvegarder_configuration()

    return AnomaliesConfigResponse(
        enabled=anomalies_config.enabled,
        rate=anomalies_config.rate,
        severity=anomalies_config.severity,
        injected_count=anomalies_config.injected_count,
    )


@router.post("/reset")
async def reset_anomalies_count() -> dict[str, str]:
    """Réinitialise le compteur d'anomalies injectées."""
    anomalies_config.injected_count = 0
    await sauvegarder_configuration()
    return {"message": "Compteur d'anomalies réinitialisé."}


class TypeAnomalieResponse(BaseModel):
    """Une entrée du catalogue, avec sa cible et son réglage."""

    model_config = ConfigDict(from_attributes=True)

    anomalie_code: str
    anomalie_libelle: str
    anomalie_famille: str
    anomalie_couleur: str
    anomalie_table_cible: str
    anomalie_colonne_cible: str
    anomalie_severite: str
    anomalie_active: bool
    anomalie_taux: float
    anomalie_declenchement: str
    anomalie_delai_secondes: int | None


class TypeAnomalieRequest(BaseModel):
    """Change le réglage d'un seul type : interrupteur, taux, moment."""

    active: bool | None = None
    taux: float | None = Field(None, ge=0.0, le=1.0)
    declenchement: str | None = None
    delai_secondes: int | None = Field(None, ge=0)


class InjectionResponse(BaseModel):
    """Une anomalie réellement posée, telle que le journal la conserve."""

    model_config = ConfigDict(from_attributes=True)

    injection_id: UUID
    anomalie_code: str
    simulation_id: UUID | None
    passage_id: str | None
    cible_cle: str | None
    valeur_origine: str | None
    valeur_injectee: str | None


@router.get("/catalogue", response_model=list[TypeAnomalieResponse])
async def get_catalogue() -> list:
    """Retourne les types d'anomalies et leur réglage.

    **Seuls ceux que le moteur temps réel sait poser.** Un seul type reste
    écarté : FORMAT_DATE_INCOHERENT, qui remplace une date par du texte et ne
    peut viser qu'un fichier, jamais une colonne `date` en base. Les cinq
    autres types d'identité (doublons, champ vide, encodage cassé, tentative
    d'injection) sont désormais posés en inscrivant un assuré neuf — voir
    simulation/inscription.py.
    """

    return [
        type_anomalie for type_anomalie in await lire_catalogue()
        if type_anomalie.anomalie_code in CODES_MOTEUR
    ]


@router.patch("/catalogue/{code}", response_model=TypeAnomalieResponse)
async def update_type(code: str, payload: TypeAnomalieRequest):
    """Règle un type séparément des autres : taux, interrupteur et moment."""

    if payload.declenchement is not None and payload.declenchement not in DECLENCHEMENTS:
        raise HTTPException(
            status_code=422,
            detail=(f"Déclenchement inconnu : {payload.declenchement}. "
                    f"Attendus : {', '.join(DECLENCHEMENTS)}."),
        )

    type_anomalie = await modifier_type(
        code, payload.active, payload.taux,
        payload.declenchement, payload.delai_secondes,
    )
    if type_anomalie is None:
        raise HTTPException(status_code=404, detail=f"Type d'anomalie inconnu : {code}.")
    return type_anomalie


@router.get("/familles")
async def get_familles() -> list[dict[str, str]]:
    """Retourne les six familles et leur couleur, pour la console d'injection."""

    return [{"famille": famille, "couleur": couleur}
            for famille, couleur in FAMILLES.items()]


@router.get("/journal", response_model=list[InjectionResponse])
async def get_journal(simulation_id: UUID | None = None, limite: int = 100) -> list:
    """Retourne les injections consignées, la plus récente en tête.

    Filtrées sur une exécution, elles donnent la vérité terrain à laquelle
    comparer ce que détectera le moteur de qualité des données.
    """

    async with async_session_factory() as session:
        requete = select(AnomalyInjection).order_by(AnomalyInjection.date_creation.desc())
        if simulation_id is not None:
            requete = requete.where(AnomalyInjection.simulation_id == simulation_id)
        return list((await session.execute(requete.limit(limite))).scalars())