"""L'outil témoin, exposé derrière le contrat que le vrai outil devra tenir.

Ce n'est pas un raccourci de M6 : c'est un participant à part entière du
canal. Brancher un vrai outil un jour ne changera rien côté canal
(`campagnes/echange.py`) tant qu'il répond à ce même contrat — reçoit un
fichier, rend `{"outil": ..., "constats": [{"ligne", "champ", "type"}, ...]}`.

Ces deux routes n'exigent pas de jeton ÉCHO : un outil externe réel ne les
connaîtra jamais, et le canal doit fonctionner sans eux — c'est justement ce
qu'il éprouve. Elles ne sont pas anonymes pour autant dès que
`ECHO_CLE_OUTIL_TESTE` est définie : l'appelant présente alors cette clé dans
l'en-tête `X-Echo-Cle`, comme le fait `campagnes/echange.py`.
"""

from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile, status

from api.schema import ConstatTemoinResponse, RapportTemoinResponse
from temoin.service import FichierRefuse, FichierTropVolumineux, analyser_televersement

VARIABLE_CLE = "ECHO_CLE_OUTIL_TESTE"
ENTETE_CLE = "X-Echo-Cle"


async def verifier_cle_partagee(
    cle: str | None = Header(default=None, alias=ENTETE_CLE),
) -> None:
    """Exige la clé du canal M6 quand elle est configurée.

    Sans clé définie, la garde s'efface : le développement local et la recette
    du canal restent utilisables tels quels. En production, la définir ferme
    ces deux routes — les seules de l'API sans jeton — à qui ne la connaît pas.
    """

    attendue = os.getenv(VARIABLE_CLE)
    if not attendue:
        return
    if cle is None or not hmac.compare_digest(cle.encode(), attendue.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé du canal M6 absente ou invalide.",
        )


def _analyser_ou_refuser(fichier: UploadFile):
    """Analyse l'envoi, et traduit un fichier inexploitable en refus lisible."""

    try:
        return analyser_televersement(fichier)
    except FichierTropVolumineux as trop_gros:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(trop_gros)
        ) from trop_gros
    except FichierRefuse as refus:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(refus)
        ) from refus


router = APIRouter(
    prefix="/temoin",
    tags=["Témoin"],
    dependencies=[Depends(verifier_cle_partagee)],
)


@router.post("/analyser", response_model=RapportTemoinResponse)
async def analyser_campagne(fichier: UploadFile) -> RapportTemoinResponse:
    """Analyse un jeu de campagne et rend le rapport, au contrat du canal M6."""

    outil, constats = _analyser_ou_refuser(fichier)
    return RapportTemoinResponse(
        outil=outil,
        constats=[
            ConstatTemoinResponse(ligne=constat.ligne, champ=constat.champ,
                                   type=constat.type)
            for constat in constats
        ],
    )


@router.post("/analyser-resume")
async def analyser_campagne_en_resume(fichier: UploadFile) -> dict:
    """Un outil imaginaire qui ne rend qu'un résumé, sans détail ligne à ligne.

    Sert uniquement à la recette du canal M6 : transmettre une campagne vers
    cette adresse plutôt que `/temoin/analyser` reproduit à volonté la panne
    « rapport sans détail », sans rien avoir à éteindre. Voir
    docs/guides/M6_canal_api.md.
    """

    _outil, constats = _analyser_ou_refuser(fichier)
    return {"resume": {"detectees": len(constats)}}
