"""Expose les campagnes de test du module Qualité des données."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from anomalies.catalogue import CATALOGUE_INITIAL, DIMENSIONS, DIMENSION_PAR_CODE
from api.schema import (
    CampagneCreateRequest, CampagneResponse, CorrigeResponse, DimensionResponse,
    EchangeCampagneResponse, FormatExportResponse, LigneCorrigeResponse,
    PalierResponse, ProchaineReferenceResponse, ProgressionResponse,
    TransmissionRequest, TypeAnomalieCampagneResponse,
)
from auth.dependencies import require_role
from auth.models import User
from campagnes import (
    PALIERS, compter_corrige, creer, historique, lancer, lire, lire_corrige,
    lister, previsualiser_reference, progression, transmettre,
)
from campagnes.export import exporter, formats_disponibles
from campagnes.models import LIBELLES_MOTIFS_ECHEC, LIBELLES_STATUTS

router = APIRouter(prefix="/campagnes", tags=["Campagnes"])


@router.get("/paliers", response_model=list[PalierResponse],
            dependencies=[Depends(require_role("observateur"))])
async def list_paliers() -> list[PalierResponse]:
    """Retourne les quatre paliers de charge et leur volume proposé."""

    return [PalierResponse.model_validate(palier) for palier in PALIERS.values()]


@router.get("/formats", response_model=list[FormatExportResponse],
            dependencies=[Depends(require_role("observateur"))])
async def list_formats() -> list[FormatExportResponse]:
    """Retourne les formats dans lesquels un jeu peut être téléchargé.

    Déclarés par le serveur, comme les paliers et les statuts : ajouter un
    format ne doit pas demander de retoucher l'écran.

    Cette route est **déclarée avant `/{campagne_id}`** à dessein — FastAPI
    retient la première qui correspond, et lirait sinon « formats » comme un
    identifiant de campagne.
    """

    return [
        FormatExportResponse.model_validate(format_export)
        for format_export in formats_disponibles()
    ]


@router.get("/statuts", dependencies=[Depends(require_role("observateur"))])
async def list_statuts() -> dict[str, str]:
    """Retourne les statuts d'une campagne et leur libellé en français.

    L'écran ne les recopie pas : un statut ajouté côté serveur doit apparaître
    sans qu'on retouche le navigateur.
    """

    return LIBELLES_STATUTS


@router.get("/motifs-echec", dependencies=[Depends(require_role("observateur"))])
async def list_motifs_echec() -> dict[str, str]:
    """Les trois pannes du canal M6, et leur libellé en français.

    Déclarée avant `/{campagne_id}` pour la même raison que `/statuts`.
    """

    return LIBELLES_MOTIFS_ECHEC


@router.get("/dimensions", response_model=list[DimensionResponse],
            dependencies=[Depends(require_role("observateur"))])
async def list_dimensions() -> list[DimensionResponse]:
    """Retourne les huit dimensions de qualité et ce que chacune éprouve.

    Le compte de types disponibles est servi avec elles : une dimension que
    rien ne sait encore injecter doit se voir, sinon on croirait l'avoir
    testée alors qu'aucune anomalie ne la vise.
    """

    comptes: dict[str, int] = {code: 0 for code in DIMENSIONS}
    for dimension in DIMENSION_PAR_CODE.values():
        comptes[dimension] = comptes.get(dimension, 0) + 1

    return [
        DimensionResponse(
            code=code,
            libelle=libelle,
            description=description,
            types_disponibles=comptes.get(code, 0),
        )
        for code, (libelle, description) in DIMENSIONS.items()
    ]


@router.get("/anomalies", response_model=list[TypeAnomalieCampagneResponse],
            dependencies=[Depends(require_role("observateur"))])
async def list_types_anomalies() -> list[TypeAnomalieCampagneResponse]:
    """Retourne les types d'anomalies qu'une campagne peut poser.

    Servis depuis le catalogue en code : une campagne porte ses propres taux,
    et le réglage de la console d'injection — qui vaut pour le moteur temps
    réel — ne doit pas déteindre sur elle.
    """

    return [
        TypeAnomalieCampagneResponse(
            code=type_anomalie.code,
            libelle=type_anomalie.libelle,
            famille=type_anomalie.famille,
            couleur=type_anomalie.couleur,
            dimension=type_anomalie.dimension,
            dimension_libelle=type_anomalie.dimension_libelle,
            table_cible=type_anomalie.table_cible,
            colonne_cible=type_anomalie.colonne_cible,
            severite=type_anomalie.severite,
        )
        for type_anomalie in CATALOGUE_INITIAL
    ]


@router.get("/prochaine-reference", response_model=ProchaineReferenceResponse,
            dependencies=[Depends(require_role("observateur"))])
async def prochaine_reference() -> ProchaineReferenceResponse:
    """La référence que porterait la prochaine campagne, sans la réserver.

    L'écran de création l'affiche dès sa première étape, avant même que
    l'opérateur ait choisi un palier. **Purement prévisionnel** : si une
    autre campagne se crée entre-temps, celle-ci en héritera et la présente
    campagne prendra le rang suivant à la création réelle.

    Déclarée avant `/{campagne_id}` pour la même raison que `/formats` et
    `/statuts` : FastAPI retiendrait sinon « prochaine-reference » comme un
    identifiant de campagne.
    """

    return ProchaineReferenceResponse(reference=await previsualiser_reference())


@router.post("", response_model=CampagneResponse,
             status_code=status.HTTP_201_CREATED)
async def creer_campagne(
    requete: CampagneCreateRequest,
    utilisateur: User = Depends(require_role("operateur")),
) -> CampagneResponse:
    """Ouvre une campagne. Rien n'est encore généré à ce stade."""

    try:
        campagne = await creer(
            requete.palier, requete.volume_cible,
            requete.graine, utilisateur.utilisateur_uuid,
            {
                code: reglage.model_dump()
                for code, reglage in (requete.anomalies or {}).items()
            },
        )
    except RuntimeError as erreur:
        raise HTTPException(status_code=409, detail=str(erreur)) from erreur
    return CampagneResponse.model_validate(campagne)


@router.get("", response_model=list[CampagneResponse],
            dependencies=[Depends(require_role("observateur"))])
async def list_campagnes(limite: int = 50) -> list[CampagneResponse]:
    """Retourne les campagnes, de la plus récente à la plus ancienne."""

    campagnes = await lister(max(1, min(limite, 200)))
    return [CampagneResponse.model_validate(campagne) for campagne in campagnes]


@router.get("/{campagne_id}", response_model=CampagneResponse,
            dependencies=[Depends(require_role("observateur"))])
async def lire_campagne(campagne_id: UUID) -> CampagneResponse:
    """Retourne une campagne précise."""

    try:
        campagne = await lire(campagne_id)
    except LookupError as absente:
        raise HTTPException(status_code=404, detail=str(absente)) from absente
    return CampagneResponse.model_validate(campagne)


@router.post("/{campagne_id}/generer", response_model=ProgressionResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def generer_campagne(
    campagne_id: UUID,
    _utilisateur: User = Depends(require_role("operateur")),
) -> ProgressionResponse:
    """Lance la production du jeu piégé et de son corrigé.

    Retourne aussitôt : la génération continue en arrière-plan, et l'écran
    suit son avancement par `/progression`. Un gros palier se compte en
    minutes, et une requête qui attendrait la fin expirerait bien avant.
    """

    try:
        suivi = await lancer(campagne_id)
    except LookupError as absente:
        raise HTTPException(status_code=404, detail=str(absente)) from absente
    except RuntimeError as occupee:
        raise HTTPException(status_code=409, detail=str(occupee)) from occupee

    return ProgressionResponse(
        statut="generation",
        volume_cible=suivi.volume_cible,
        lignes_generees=suivi.lignes_generees,
        anomalies_posees=suivi.anomalies_posees,
        pourcentage=suivi.pourcentage,
        terminee=suivi.terminee,
        erreur=suivi.erreur,
    )


@router.get("/{campagne_id}/progression", response_model=ProgressionResponse,
            dependencies=[Depends(require_role("observateur"))])
async def lire_progression(campagne_id: UUID) -> ProgressionResponse:
    """Où en est la génération. Consultable pendant qu'elle tourne."""

    try:
        campagne = await lire(campagne_id)
    except LookupError as absente:
        raise HTTPException(status_code=404, detail=str(absente)) from absente

    suivi = progression(campagne_id)
    if suivi is None:
        # Aucune génération en mémoire : soit elle n'a jamais eu lieu, soit
        # l'API a redémarré depuis. On répond alors avec ce que la campagne
        # porte en base, qui reste la vérité durable.
        return ProgressionResponse(
            statut=campagne.campagne_statut,
            volume_cible=campagne.campagne_volume_cible,
            lignes_generees=campagne.campagne_lignes_generees,
            anomalies_posees=campagne.campagne_anomalies_posees,
            pourcentage=100.0 if campagne.campagne_empreinte else 0.0,
            terminee=campagne.campagne_empreinte is not None,
        )

    return ProgressionResponse(
        statut=campagne.campagne_statut,
        volume_cible=suivi.volume_cible,
        lignes_generees=suivi.lignes_generees,
        anomalies_posees=suivi.anomalies_posees,
        pourcentage=suivi.pourcentage,
        terminee=suivi.terminee,
        erreur=suivi.erreur,
    )


@router.get("/{campagne_id}/corrige", response_model=CorrigeResponse,
            dependencies=[Depends(require_role("observateur"))])
async def lire_corrige_campagne(
    campagne_id: UUID, limite: int = 50, decalage: int = 0,
    anomalie_code: str | None = None,
) -> CorrigeResponse:
    """Le corrigé : ligne, champ, type, valeur d'origine et valeur posée.

    Paginé, car un palier élevé en produit des dizaines de milliers. Le compte
    par type, lui, porte toujours sur la totalité — c'est la moitié gauche du
    futur tableau de score.
    """

    try:
        await lire(campagne_id)
    except LookupError as absente:
        raise HTTPException(status_code=404, detail=str(absente)) from absente

    par_anomalie = await compter_corrige(campagne_id)
    lignes = await lire_corrige(
        campagne_id, max(1, min(limite, 500)), max(0, decalage), anomalie_code
    )
    return CorrigeResponse(
        campagne_id=campagne_id,
        total=sum(par_anomalie.values()),
        par_anomalie=par_anomalie,
        lignes=[LigneCorrigeResponse.model_validate(ligne) for ligne in lignes],
    )


@router.get("/{campagne_id}/export",
            dependencies=[Depends(require_role("observateur"))])
async def exporter_campagne(campagne_id: UUID, format: str = "csv") -> Response:
    """Remet le jeu de la campagne dans le format demandé.

    Le paramètre s'appelle « format » parce que c'est le mot que lit celui qui
    consulte l'API ; il masque la fonction interne du même nom, dont on n'a pas
    l'usage ici.

    Le fichier est renvoyé en un bloc et non en flux : les formats dérivés sont
    de toute façon construits en mémoire, et le CSV est borné par le volume de
    la campagne. Un flux ne se justifiera qu'avec les paliers de M8.
    """

    try:
        campagne = await lire(campagne_id)
    except LookupError as absente:
        raise HTTPException(status_code=404, detail=str(absente)) from absente

    if not campagne.campagne_fichier:
        # 409 et non 404 : la campagne existe, c'est son jeu qui n'a pas encore
        # été produit. Les deux cas appellent des gestes différents de la part
        # de celui qui les lit, ils ne doivent pas porter le même code.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette campagne n'a pas encore été générée : rien à exporter.",
        )

    try:
        export = exporter(
            Path(campagne.campagne_fichier), format, campagne.campagne_reference
        )
    except FileNotFoundError as absent:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=str(absent)) from absent
    except ValueError as refus:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=str(refus)) from refus

    return Response(
        content=export.contenu,
        media_type=export.type_mime,
        headers={
            # « attachment » déclenche l'enregistrement au lieu de l'affichage,
            # et impose le nom du fichier — sans quoi le navigateur le
            # baptiserait « export », du dernier segment de l'adresse.
            "Content-Disposition": f'attachment; filename="{export.nom_fichier}"',
        },
    )


@router.post("/{campagne_id}/transmettre", response_model=EchangeCampagneResponse,
             status_code=status.HTTP_201_CREATED)
async def transmettre_campagne(
    campagne_id: UUID, requete: TransmissionRequest | None = None,
    _utilisateur: User = Depends(require_role("operateur")),
) -> EchangeCampagneResponse:
    """Transmet le jeu d'une campagne à l'outil testé (M6).

    Répond une fois l'échange terminé — succès ou échec, les trois pannes
    distinguées : ce n'est jamais long, un jeu de campagne se transmet en un
    seul appel HTTP synchrone. Sans adresse, la campagne part vers le témoin.
    """

    adresse = requete.adresse if requete is not None else None
    try:
        echange = await transmettre(campagne_id, adresse)
    except LookupError as absente:
        raise HTTPException(status_code=404, detail=str(absente)) from absente
    except RuntimeError as pas_prete:
        raise HTTPException(status_code=409, detail=str(pas_prete)) from pas_prete
    return EchangeCampagneResponse.model_validate(echange)


@router.get("/{campagne_id}/echanges", response_model=list[EchangeCampagneResponse],
            dependencies=[Depends(require_role("observateur"))])
async def lire_echanges_campagne(campagne_id: UUID) -> list[EchangeCampagneResponse]:
    """L'historique des transmissions d'une campagne, la plus récente d'abord."""

    try:
        await lire(campagne_id)
    except LookupError as absente:
        raise HTTPException(status_code=404, detail=str(absente)) from absente

    return [
        EchangeCampagneResponse.model_validate(echange)
        for echange in await historique(campagne_id)
    ]
