"""L'outil témoin, exposé derrière le contrat que le vrai outil devra tenir.

Ce n'est pas un raccourci de M6 : c'est un participant à part entière du
canal. Brancher un vrai outil un jour ne changera rien côté canal
(`campagnes/echange.py`) tant qu'il répond à ce même contrat — reçoit un
fichier, rend `{"outil": ..., "constats": [{"ligne", "champ", "type"}, ...]}`.

Aucune authentification sur ces deux routes : un outil externe réel ne
connaîtra jamais les jetons d'ÉCHO, et le canal doit fonctionner sans eux —
c'est justement ce qu'il éprouve.
"""

from __future__ import annotations

from fastapi import APIRouter, UploadFile

from api.schema import ConstatTemoinResponse, RapportTemoinResponse
from temoin.service import analyser_fichier

router = APIRouter(prefix="/temoin", tags=["Témoin"])


@router.post("/analyser", response_model=RapportTemoinResponse)
async def analyser_campagne(fichier: UploadFile) -> RapportTemoinResponse:
    """Analyse un jeu de campagne et rend le rapport, au contrat du canal M6."""

    contenu = await fichier.read()
    outil, constats = analyser_fichier(contenu)
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

    contenu = await fichier.read()
    _outil, constats = analyser_fichier(contenu)
    return {"resume": {"detectees": len(constats)}}
