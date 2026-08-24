"""Construit les rapports PDF professionnels d'ÉCHO.

Deux formats :
- Le rapport technique quotidien (métriques SRE, sans donnée métier).
- La fiche d'exécution (paramètres, volumétrie, qualité, analyses détaillées).

Chaque PDF porte les logos ÉCHO et CNAM, une mise en page colorée et aérée,
et des analyses de répartition que le rapport textuel ne proposait pas.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from fpdf import FPDF
from fpdf.enums import Align, XPos, YPos
from sqlalchemy import func, select

from anomalies.models import AnomalyInjection, AnomalyType
from app.database import async_session_factory
from app.models import Invoice, InvoiceProvision, PriorAuthorization
from events.models import EventJournal
from metrics.registry import registry
from qualite import analyser
from reports.paths import OUTPUT_DIR
from simulation.models import SimulationRun

# ── Chemins des logos ────────────────────────────────────────────────────

_REPORTS_DIR = Path(__file__).resolve().parent
_LOGO_CNAM = _REPORTS_DIR / "logo_cnam.png"

# ── Palette ──────────────────────────────────────────────────────────────

VERT_ECHO = (22, 163, 74)        # #16a34a
BLEU_CNAM = (0, 91, 170)         # #005baa
GRIS_FONCE = (45, 55, 65)        # texte principal
GRIS_MOYEN = (120, 130, 140)     # texte secondaire
GRIS_CLAIR = (235, 238, 241)     # fond alternance
BLANC = (255, 255, 255)
ROUGE = (229, 72, 77)            # alertes
ORANGE = (234, 156, 45)          # avertissements
VERT_CLAIR = (200, 235, 210)     # fond succès


class EchoPDF(FPDF):
    """PDF avec en-tête et pied de page ÉCHO / CNAM."""

    def __init__(self, titre_rapport: str = "", sous_titre: str = ""):
        super().__init__()
        self.titre_rapport = titre_rapport
        self.sous_titre = sous_titre
        self.set_auto_page_break(auto=True, margin=25)

    # ── En-tête ──────────────────────────────────────────────────────

    def header(self):
        # Barre colorée en haut
        self.set_fill_color(*VERT_ECHO)
        self.rect(0, 0, 210, 4, style="F")
        self.set_fill_color(*BLEU_CNAM)
        self.rect(0, 4, 210, 1.5, style="F")

        # Logo CNAM à gauche
        if _LOGO_CNAM.exists():
            self.image(str(_LOGO_CNAM), x=12, y=8, h=14)

        # Titre ÉCHO à droite
        self.set_xy(50, 8)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*VERT_ECHO)
        self.cell(0, 6, "ECHO", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_xy(50, 14)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*GRIS_MOYEN)
        self.cell(0, 4, "Simulateur de donnees CNAM-CI", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Titre du rapport
        if self.titre_rapport:
            self.set_xy(10, 26)
            self.set_font("Helvetica", "B", 11)
            self.set_text_color(*GRIS_FONCE)
            self.cell(0, 6, _lat(self.titre_rapport), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if self.sous_titre:
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*GRIS_MOYEN)
            self.cell(0, 4, _lat(self.sous_titre), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Filet de séparation
        self.set_draw_color(*GRIS_CLAIR)
        self.line(10, 36, 200, 36)
        self.set_y(39)

    # ── Pied de page ─────────────────────────────────────────────────

    def footer(self):
        self.set_y(-20)
        self.set_draw_color(*GRIS_CLAIR)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*GRIS_MOYEN)
        self.cell(0, 4, (
            f"ECHO - Caisse Nationale d'Assurance Maladie de Cote d'Ivoire  |  "
            f"Page {self.page_no()}/{{nb}}  |  "
            f"Genere le {datetime.now(timezone.utc).strftime('%d/%m/%Y a %H:%M UTC')}"
        ), align=Align.C)

    # ── Composants de mise en page ───────────────────────────────────

    def titre_section(self, texte: str, couleur: tuple = VERT_ECHO):
        """Barre colorée avec titre blanc."""
        self.ln(4)
        self.set_fill_color(*couleur)
        self.set_text_color(*BLANC)
        self.set_font("Helvetica", "B", 9)
        self.cell(0, 7, f"  {_lat(texte)}", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(*GRIS_FONCE)
        self.ln(2)

    def sous_section(self, texte: str):
        """Titre de sous-section avec filet."""
        self.ln(2)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*BLEU_CNAM)
        self.cell(0, 6, _lat(texte), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*BLEU_CNAM)
        self.line(self.get_x(), self.get_y(), self.get_x() + 60, self.get_y())
        self.set_draw_color(*GRIS_CLAIR)
        self.set_text_color(*GRIS_FONCE)
        self.ln(2)

    def paire(self, libelle: str, valeur: object, largeur_libelle: float = 70):
        """Libellé : valeur sur une ligne."""
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GRIS_MOYEN)
        self.cell(largeur_libelle, 5.5, _lat(libelle), new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*GRIS_FONCE)
        self.cell(0, 5.5, _lat(str(valeur)), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def tableau(self, colonnes: list[str], lignes: list[list[str]],
                largeurs: list[float] | None = None,
                couleur_entete: tuple = BLEU_CNAM):
        """Tableau avec en-tête coloré et lignes alternées."""
        nb = len(colonnes)
        if largeurs is None:
            dispo = 190
            largeurs = [dispo / nb] * nb

        # En-tête
        self.set_fill_color(*couleur_entete)
        self.set_text_color(*BLANC)
        self.set_font("Helvetica", "B", 7.5)
        for i, col in enumerate(colonnes):
            self.cell(largeurs[i], 6, _lat(col), border=0, fill=True,
                      new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.ln()

        # Lignes
        self.set_text_color(*GRIS_FONCE)
        self.set_font("Helvetica", "", 7.5)
        for rang, ligne in enumerate(lignes):
            if rang % 2 == 0:
                self.set_fill_color(*GRIS_CLAIR)
            else:
                self.set_fill_color(*BLANC)
            for i, cellule in enumerate(ligne):
                self.cell(largeurs[i], 5.5, _lat(cellule), border=0, fill=True,
                          new_x=XPos.RIGHT, new_y=YPos.TOP)
            self.ln()
        self.ln(2)

    def barre_progression(self, libelle: str, valeur: float, maximum: float,
                          couleur: tuple = VERT_ECHO, largeur_barre: float = 80):
        """Barre horizontale avec libellé et pourcentage."""
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*GRIS_FONCE)
        self.cell(55, 5, _lat(libelle), new_x=XPos.RIGHT, new_y=YPos.TOP)

        x0 = self.get_x()
        y0 = self.get_y() + 0.5
        # Fond gris
        self.set_fill_color(*GRIS_CLAIR)
        self.rect(x0, y0, largeur_barre, 4, style="F")
        # Barre colorée
        ratio = min(valeur / maximum, 1.0) if maximum > 0 else 0
        if ratio > 0:
            self.set_fill_color(*couleur)
            self.rect(x0, y0, largeur_barre * ratio, 4, style="F")

        pct = f"{ratio * 100:.1f} %"
        self.set_xy(x0 + largeur_barre + 2, y0 - 0.5)
        self.set_font("Helvetica", "B", 7)
        self.cell(25, 5, pct, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def encart(self, texte: str, couleur_fond: tuple = VERT_CLAIR,
               couleur_texte: tuple = GRIS_FONCE):
        """Bloc de texte dans un rectangle arrondi."""
        self.set_fill_color(*couleur_fond)
        self.set_text_color(*couleur_texte)
        self.set_font("Helvetica", "I", 7.5)
        y = self.get_y()
        self.rect(10, y, 190, 10, style="F")
        self.set_xy(13, y + 2)
        self.multi_cell(184, 3.5, _lat(texte))
        self.set_y(y + 12)
        self.set_text_color(*GRIS_FONCE)


def _lat(valeur: str) -> str:
    """FPDF en mode standard ecrit en latin-1 : les caracteres hors jeu
    sont replaces par un substitut plutot que de casser la sortie."""
    return str(valeur).encode("latin-1", "replace").decode("latin-1")


def _fmt_nombre(n: int | float | Decimal) -> str:
    """Formate un nombre avec separateur de milliers."""
    if isinstance(n, float):
        return f"{n:,.2f}".replace(",", " ").replace(".", ",")
    return f"{int(n):,}".replace(",", " ")


def _fmt_duree(debut, fin) -> str:
    """Duree lisible entre deux datetimes."""
    if not debut or not fin:
        return "en cours"
    delta = fin - debut
    secondes = int(delta.total_seconds())
    heures = secondes // 3600
    minutes = (secondes % 3600) // 60
    if heures > 0:
        return f"{heures} h {minutes:02d} min"
    if minutes > 0:
        return f"{minutes} min {secondes % 60:02d} s"
    return f"{secondes} s"


# ═══════════════════════════════════════════════════════════════════════
#  Rapport technique quotidien
# ═══════════════════════════════════════════════════════════════════════

def build_daily_pdf_report(jour: date) -> Path:
    """Genere un PDF recapitulant les metriques techniques du registre."""

    donnees = registry.snapshot()

    pdf = EchoPDF(
        titre_rapport="Rapport technique quotidien",
        sous_titre=f"Date : {jour.strftime('%d/%m/%Y')}",
    )
    pdf.alias_nb_pages()
    pdf.add_page()

    # ── Disponibilite de l'API ───────────────────────────────────────
    pdf.titre_section("Disponibilite de l'API")
    pdf.paire("Serveur demarre depuis", donnees["demarre_depuis"])
    pdf.paire("Uptime", f'{int(donnees["uptime_secondes"]):,} secondes'.replace(",", " "))
    pdf.paire("Requetes API traitees", _fmt_nombre(donnees["requetes_api_total"]))
    pdf.paire("Temps de reponse moyen", f'{donnees["temps_moyen_reponse_api_ms"]} ms')

    # ── Moteur de simulation ─────────────────────────────────────────
    pdf.titre_section("Moteur de simulation")
    reussis = donnees["passages_reussis"]
    echoues = donnees["passages_echoues"]
    total_passages = reussis + echoues
    pdf.tableau(
        ["Indicateur", "Valeur"],
        [
            ["Passages reussis", _fmt_nombre(reussis)],
            ["Passages echoues", _fmt_nombre(echoues)],
            ["Taux d'echec", f'{donnees["taux_echec_pourcent"]} %'],
            ["Pic simultane atteint", _fmt_nombre(donnees["pic_passages_simultanes"])],
        ],
        largeurs=[120, 70],
    )
    if total_passages > 0:
        pdf.barre_progression("Taux de reussite", reussis, total_passages, VERT_ECHO)
        pdf.ln(2)

    # ── Pipeline KPI ─────────────────────────────────────────────────
    pdf.titre_section("Pipeline KPI (temps reel)")
    pdf.paire("Recalculs declenches", _fmt_nombre(donnees["recalculs_kpi"]))
    pdf.paire("Temps moyen par recalcul", f'{donnees["temps_moyen_recalcul_kpi_ms"]} ms')

    # ── Connexions Socket.IO ─────────────────────────────────────────
    pdf.titre_section("Connexions temps reel (Socket.IO)")
    pdf.paire("Connexions totales", _fmt_nombre(donnees["connexions_socketio_total"]))
    pdf.paire("Deconnexions totales", _fmt_nombre(donnees["deconnexions_socketio_total"]))
    pdf.paire("Clients connectes", _fmt_nombre(donnees["clients_socketio_actifs"]))

    # ── Note de bas ──────────────────────────────────────────────────
    pdf.ln(4)
    pdf.encart(
        "Ce rapport ne contient volontairement aucune metrique metier CMU "
        "(montants, pathologies, ententes) -- uniquement des indicateurs sur "
        "le fonctionnement technique du simulateur ECHO.",
    )

    chemin = OUTPUT_DIR / f"rapport_technique_{jour.isoformat()}.pdf"
    pdf.output(str(chemin))
    return chemin


# ═══════════════════════════════════════════════════════════════════════
#  Fiche d'execution
# ═══════════════════════════════════════════════════════════════════════

async def build_execution_pdf_report(simulation_id: UUID) -> Path:
    """Genere la fiche complete d'une execution avec analyses etendues."""

    async with async_session_factory() as session:
        execution = await session.get(SimulationRun, simulation_id)
        if execution is None:
            raise LookupError(f"Execution inconnue : {simulation_id}.")

        # ── Volumetrie ───────────────────────────────────────────────
        async def compter(modele) -> int:
            return (await session.execute(
                select(func.count()).select_from(modele)
                .where(modele.simulation_id == simulation_id)
            )).scalar_one()

        nb_factures = await compter(Invoice)
        nb_prestations = await compter(InvoiceProvision)
        nb_ententes = await compter(PriorAuthorization)
        nb_evenements = await compter(EventJournal)
        nb_anomalies = await compter(AnomalyInjection)

        # ── Repartition par regime ───────────────────────────────────
        repartition_regime = dict((await session.execute(
            select(Invoice.regime_code, func.count())
            .where(Invoice.simulation_id == simulation_id)
            .group_by(Invoice.regime_code)
        )).all())

        # ── Repartition par type de centre ───────────────────────────
        repartition_centre = dict((await session.execute(
            select(
                func.coalesce(Invoice.centre_sante_type_libelle, Invoice.centre_sante_type_code, "Non renseigne"),
                func.count(),
            )
            .where(Invoice.simulation_id == simulation_id)
            .group_by(Invoice.centre_sante_type_libelle, Invoice.centre_sante_type_code)
        )).all())

        # ── Montants agreges ─────────────────────────────────────────
        montants = (await session.execute(
            select(
                func.sum(InvoiceProvision.prestation_montant_depense),
                func.sum(InvoiceProvision.prestation_montant_rq),
                func.sum(InvoiceProvision.prestation_montant_assure),
                func.avg(InvoiceProvision.prestation_montant_depense),
            )
            .where(InvoiceProvision.simulation_id == simulation_id)
        )).one()
        total_depense = montants[0] or Decimal(0)
        total_rq = montants[1] or Decimal(0)
        total_assure = montants[2] or Decimal(0)
        moyenne_depense = montants[3] or Decimal(0)

        # ── Repartition des anomalies par famille ────────────────────
        anomalies_par_type = dict((await session.execute(
            select(AnomalyInjection.anomalie_code, func.count())
            .where(AnomalyInjection.simulation_id == simulation_id)
            .group_by(AnomalyInjection.anomalie_code)
        )).all())

        # Familles depuis le catalogue
        familles_map = dict((await session.execute(
            select(AnomalyType.anomalie_code, AnomalyType.anomalie_famille)
        )).all())

    # ── Qualite ──────────────────────────────────────────────────────
    qualite = await analyser(simulation_id, inclure_referentiel=False)

    # ── Construction du PDF ──────────────────────────────────────────
    libelle = execution.simulation_libelle or f"Execution {simulation_id}"
    pdf = EchoPDF(
        titre_rapport=f"Fiche d'execution",
        sous_titre=libelle,
    )
    pdf.alias_nb_pages()
    pdf.add_page()

    # ── 1. Identite de l'execution ───────────────────────────────────
    pdf.titre_section("Identite de l'execution", BLEU_CNAM)
    pdf.paire("Identifiant", str(simulation_id))
    pdf.paire("Libelle", libelle)
    pdf.paire("Type de simulation", execution.simulation_type or "non precise")
    pdf.paire("Statut", execution.simulation_statut)
    pdf.paire("Debut", execution.simulation_date_debut.strftime("%d/%m/%Y %H:%M:%S"))
    pdf.paire("Fin", (
        execution.simulation_date_fin.strftime("%d/%m/%Y %H:%M:%S")
        if execution.simulation_date_fin else "en cours"
    ))
    pdf.paire("Duree", _fmt_duree(execution.simulation_date_debut, execution.simulation_date_fin))

    # Parametres
    params = execution.simulation_parametres or {}
    if params.get("vitesse"):
        pdf.paire("Vitesse", f"x{params['vitesse']}")
    if params.get("passages_simultanes_max"):
        pdf.paire("Passages max en parallele", _fmt_nombre(params["passages_simultanes_max"]))

    # ── 2. Passages ──────────────────────────────────────────────────
    pdf.titre_section("Bilan des passages")
    total_p = execution.passages_reussis + execution.passages_echoues
    pdf.tableau(
        ["", "Nombre", "Proportion"],
        [
            ["Passages reussis", _fmt_nombre(execution.passages_reussis),
             f"{100 * execution.passages_reussis / total_p:.1f} %" if total_p else "—"],
            ["Passages echoues", _fmt_nombre(execution.passages_echoues),
             f"{100 * execution.passages_echoues / total_p:.1f} %" if total_p else "—"],
            ["Total", _fmt_nombre(total_p), "100 %" if total_p else "—"],
        ],
        largeurs=[90, 50, 50],
    )
    if total_p > 0:
        pdf.barre_progression(
            "Taux de reussite", execution.passages_reussis, total_p, VERT_ECHO)
        pdf.ln(2)

    # ── 3. Volumetrie produite ───────────────────────────────────────
    pdf.titre_section("Volumetrie produite")
    pdf.tableau(
        ["Objet", "Nombre"],
        [
            ["Factures", _fmt_nombre(nb_factures)],
            ["Prestations de soins", _fmt_nombre(nb_prestations)],
            ["Ententes prealables", _fmt_nombre(nb_ententes)],
            ["Evenements journalises", _fmt_nombre(nb_evenements)],
            ["Anomalies injectees", _fmt_nombre(nb_anomalies)],
        ],
        largeurs=[120, 70],
        couleur_entete=VERT_ECHO,
    )

    # ── 4. Analyse financiere ────────────────────────────────────────
    pdf.titre_section("Analyse financiere des prestations", BLEU_CNAM)
    pdf.paire("Montant total des depenses", f"{_fmt_nombre(total_depense)} FCFA")
    pdf.paire("Montant total rembourse (RQ)", f"{_fmt_nombre(total_rq)} FCFA")
    pdf.paire("Reste a charge assures", f"{_fmt_nombre(total_assure)} FCFA")
    pdf.paire("Depense moyenne par prestation", f"{_fmt_nombre(moyenne_depense)} FCFA")
    if total_depense > 0:
        taux_couv = float(total_rq) / float(total_depense) * 100
        pdf.ln(2)
        pdf.barre_progression("Taux de couverture RQ/depense", float(total_rq),
                              float(total_depense), BLEU_CNAM)

    # ── 5. Repartition par regime ────────────────────────────────────
    if repartition_regime:
        pdf.titre_section("Repartition par regime")
        total_regime = sum(repartition_regime.values())
        lignes_regime = []
        for code, nombre in sorted(repartition_regime.items(), key=lambda x: -x[1]):
            pct = f"{100 * nombre / total_regime:.1f} %" if total_regime else "—"
            lignes_regime.append([code or "Non renseigne", _fmt_nombre(nombre), pct])
        pdf.tableau(
            ["Regime", "Factures", "Part"],
            lignes_regime,
            largeurs=[80, 60, 50],
        )
        # Barres
        for code, nombre in sorted(repartition_regime.items(), key=lambda x: -x[1]):
            pdf.barre_progression(
                code or "Non renseigne", nombre, total_regime, BLEU_CNAM)
        pdf.ln(2)

    # ── 6. Repartition par type de centre ────────────────────────────
    if repartition_centre:
        pdf.titre_section("Repartition par type de centre de sante")
        total_centre = sum(repartition_centre.values())
        lignes_centre = []
        for libelle_c, nombre in sorted(repartition_centre.items(), key=lambda x: -x[1]):
            pct = f"{100 * nombre / total_centre:.1f} %" if total_centre else "—"
            lignes_centre.append([libelle_c, _fmt_nombre(nombre), pct])
        pdf.tableau(
            ["Type de centre", "Factures", "Part"],
            lignes_centre,
            largeurs=[100, 50, 40],
        )

    # ── 7. Qualite des donnees par dimension ─────────────────────────
    pdf.add_page()
    pdf.titre_section("Qualite des donnees", VERT_ECHO)

    pdf.sous_section("Constats par dimension")
    total_constats = qualite["total_constats"]
    lignes_dim = []
    for dim, nb in qualite["par_dimension"].items():
        pct = f"{100 * nb / total_constats:.1f} %" if total_constats else "—"
        lignes_dim.append([dim, _fmt_nombre(nb), pct])
    pdf.tableau(
        ["Dimension", "Constats", "Part"],
        lignes_dim,
        largeurs=[80, 55, 55],
        couleur_entete=VERT_ECHO,
    )
    # Barres de repartition
    if total_constats > 0:
        for dim, nb in qualite["par_dimension"].items():
            pdf.barre_progression(dim, nb, total_constats, VERT_ECHO)
        pdf.ln(4)

    # ── 8. Detail des regles ─────────────────────────────────────────
    pdf.sous_section("Detail des regles appliquees")
    lignes_regles = []
    for r in sorted(qualite["regles"], key=lambda x: -x["constats"]):
        lignes_regles.append([
            r["code"],
            r["libelle"][:50],
            r["dimension"],
            _fmt_nombre(r["constats"]),
        ])
    if lignes_regles:
        pdf.tableau(
            ["Code", "Regle", "Dimension", "Constats"],
            lignes_regles,
            largeurs=[35, 85, 35, 35],
        )

    # ── 9. Anomalies injectees vs detectees ──────────────────────────
    if qualite["confrontation"]:
        pdf.titre_section("Confrontation : injectees vs detectees", ROUGE)
        pdf.encart(
            "Le taux de detection compare ce que les regles de qualite relevent a "
            "ce que le journal d'injection dit avoir pose. C'est la seule mesure "
            "qu'aucun outil branche sur des donnees reelles ne peut produire.",
            couleur_fond=(255, 230, 230),
            couleur_texte=GRIS_FONCE,
        )
        pdf.ln(2)

        lignes_conf = []
        for ligne in qualite["confrontation"]:
            taux = ligne["taux_detection_pourcent"]
            taux_str = f"{taux} %" if taux is not None else "N/A"
            lignes_conf.append([
                ligne["anomalie_code"],
                _fmt_nombre(ligne["injectees"]),
                _fmt_nombre(ligne["detectees"]),
                taux_str,
            ])
        pdf.tableau(
            ["Type d'anomalie", "Injectees", "Detectees", "Taux detection"],
            lignes_conf,
            largeurs=[60, 40, 40, 50],
            couleur_entete=ROUGE,
        )

        # Barres de détection
        for ligne in qualite["confrontation"]:
            if ligne["injectees"] > 0:
                couleur_barre = VERT_ECHO if (ligne["taux_detection_pourcent"] or 0) >= 80 else ORANGE
                pdf.barre_progression(
                    ligne["anomalie_code"],
                    ligne["detectees"],
                    ligne["injectees"],
                    couleur_barre,
                )
        pdf.ln(4)

    # ── 10. Repartition des anomalies par famille ────────────────────
    if anomalies_par_type:
        pdf.titre_section("Repartition des anomalies par famille")
        par_famille: dict[str, int] = {}
        for code, nb in anomalies_par_type.items():
            famille = familles_map.get(code, "AUTRE")
            par_famille[famille] = par_famille.get(famille, 0) + nb

        total_anom = sum(par_famille.values())
        lignes_fam = []
        for fam, nb in sorted(par_famille.items(), key=lambda x: -x[1]):
            pct = f"{100 * nb / total_anom:.1f} %" if total_anom else "—"
            lignes_fam.append([fam, _fmt_nombre(nb), pct])
        pdf.tableau(
            ["Famille", "Anomalies", "Part"],
            lignes_fam,
            largeurs=[80, 55, 55],
        )
        if total_anom > 0:
            for fam, nb in sorted(par_famille.items(), key=lambda x: -x[1]):
                pdf.barre_progression(fam, nb, total_anom, ORANGE)
            pdf.ln(2)

    # ── 11. Synthese ─────────────────────────────────────────────────
    pdf.titre_section("Synthese et recommandations", BLEU_CNAM)

    observations: list[str] = []

    if total_p > 0:
        taux_reussite = 100 * execution.passages_reussis / total_p
        if taux_reussite >= 99:
            observations.append(
                f"Taux de reussite excellent ({taux_reussite:.1f} %) : "
                f"le moteur a produit {_fmt_nombre(total_p)} passages sans incident notable."
            )
        elif taux_reussite >= 90:
            observations.append(
                f"Taux de reussite correct ({taux_reussite:.1f} %) : "
                f"{_fmt_nombre(execution.passages_echoues)} passage(s) en echec a investiguer."
            )
        else:
            observations.append(
                f"Taux de reussite faible ({taux_reussite:.1f} %) : "
                f"{_fmt_nombre(execution.passages_echoues)} echec(s) sur {_fmt_nombre(total_p)} passages."
            )

    if total_constats > 0:
        dim_max = max(qualite["par_dimension"], key=qualite["par_dimension"].get)
        observations.append(
            f"La dimension la plus touchee est {dim_max} avec "
            f"{_fmt_nombre(qualite['par_dimension'][dim_max])} constat(s)."
        )

    for ligne in qualite.get("confrontation", []):
        taux = ligne.get("taux_detection_pourcent")
        if taux is not None and taux < 50 and ligne["injectees"] >= 5:
            observations.append(
                f"Alerte : le type {ligne['anomalie_code']} n'est detecte "
                f"qu'a {taux} % ({ligne['detectees']}/{ligne['injectees']}). "
                f"La regle merite un reglage plus sensible."
            )

    if nb_factures > 0 and total_depense > 0:
        depense_par_facture = float(total_depense) / nb_factures
        observations.append(
            f"Depense moyenne par facture : {_fmt_nombre(depense_par_facture)} FCFA "
            f"({_fmt_nombre(nb_factures)} facture(s) pour {_fmt_nombre(total_depense)} FCFA)."
        )

    if not observations:
        observations.append("Aucune observation particuliere sur cette execution.")

    pdf.set_font("Helvetica", "", 8)
    for i, obs in enumerate(observations, 1):
        pdf.multi_cell(0, 4.5, _lat(f"  {i}. {obs}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)

    # ── Pied ─────────────────────────────────────────────────────────
    pdf.ln(4)
    pdf.encart(
        "Document genere automatiquement par ECHO, le simulateur de donnees "
        "de la Caisse Nationale d'Assurance Maladie de Cote d'Ivoire. "
        "Les donnees presentees sont synthetiques et ne representent aucun "
        "assure ni aucun centre de sante reel.",
    )

    chemin = OUTPUT_DIR / f"execution_{simulation_id}.pdf"
    pdf.output(str(chemin))
    return chemin
