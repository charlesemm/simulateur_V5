from fastapi import APIRouter, Depends
from sqlalchemy import select
from app.database import async_session_factory
from app.models import HealthCenter
from api.schema import HealthCenterListResponse, HealthCenterSchema
from auth.dependencies import require_role

router = APIRouter(
    tags=["Centres de santé"],
    dependencies=[Depends(require_role("observateur"))],
)

@router.get("/centres-sante", response_model=HealthCenterListResponse)
async def list_health_centers() -> HealthCenterListResponse:
    """Retourne les centres triés par dénomination."""

    async with async_session_factory() as session:
        rows = list((await session.execute(
            select(HealthCenter).order_by(HealthCenter.centre_sante_denomination)
        )).scalars())
    centres = [HealthCenterSchema(
        centre_sante_code=row.centre_sante_code,
        denomination=row.centre_sante_denomination,
        type_code=row.type_etablissement_sanitaire_code,
        numero_immatriculation=row.centre_sante_numero_immatriculation,
    ) for row in rows]
    return HealthCenterListResponse(total=len(centres), centres=centres)