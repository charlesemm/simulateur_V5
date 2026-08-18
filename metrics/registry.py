"""Registre en mémoire des métriques TECHNIQUES du simulateur.

Volontairement : aucune métrique métier CMU ici (montants remboursés,
répartition des pathologies, etc.) -- uniquement des indicateurs sur le
fonctionnement du simulateur lui-même (charge, fiabilité, latence).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class TechnicalMetricsRegistry:
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    passages_reussis: int = 0
    passages_echoues: int = 0
    pic_passages_simultanes: int = 0

    recalculs_kpi: int = 0
    duree_totale_recalculs_kpi_secondes: float = 0.0

    connexions_socketio_total: int = 0
    deconnexions_socketio_total: int = 0
    clients_socketio_actifs: int = 0

    requetes_api_total: int = 0
    duree_totale_requetes_api_secondes: float = 0.0

    def enregistrer_passage(self, succes: bool) -> None:
        if succes:
            self.passages_reussis += 1
        else:
            self.passages_echoues += 1

    def enregistrer_pic(self, valeur: int) -> None:
        self.pic_passages_simultanes = max(self.pic_passages_simultanes, valeur)

    def enregistrer_recalcul_kpi(self, duree_secondes: float) -> None:
        self.recalculs_kpi += 1
        self.duree_totale_recalculs_kpi_secondes += duree_secondes

    def enregistrer_connexion_socketio(self) -> None:
        self.connexions_socketio_total += 1
        self.clients_socketio_actifs += 1

    def enregistrer_deconnexion_socketio(self) -> None:
        self.deconnexions_socketio_total += 1
        self.clients_socketio_actifs = max(0, self.clients_socketio_actifs - 1)

    def enregistrer_requete_api(self, duree_secondes: float) -> None:
        self.requetes_api_total += 1
        self.duree_totale_requetes_api_secondes += duree_secondes

    def uptime_secondes(self) -> float:
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()

    def temps_moyen_recalcul_kpi_ms(self) -> float:
        if self.recalculs_kpi == 0:
            return 0.0
        return (self.duree_totale_recalculs_kpi_secondes / self.recalculs_kpi) * 1000

    def temps_moyen_reponse_api_ms(self) -> float:
        if self.requetes_api_total == 0:
            return 0.0
        return (self.duree_totale_requetes_api_secondes / self.requetes_api_total) * 1000

    def snapshot(self) -> dict:
        total_passages = self.passages_reussis + self.passages_echoues
        return {
            "demarre_depuis": self.started_at.isoformat(),
            "uptime_secondes": round(self.uptime_secondes(), 1),
            "passages_reussis": self.passages_reussis,
            "passages_echoues": self.passages_echoues,
            "taux_echec_pourcent": round(100 * self.passages_echoues / max(1, total_passages), 2),
            "pic_passages_simultanes": self.pic_passages_simultanes,
            "recalculs_kpi": self.recalculs_kpi,
            "temps_moyen_recalcul_kpi_ms": round(self.temps_moyen_recalcul_kpi_ms(), 1),
            "connexions_socketio_total": self.connexions_socketio_total,
            "deconnexions_socketio_total": self.deconnexions_socketio_total,
            "clients_socketio_actifs": self.clients_socketio_actifs,
            "requetes_api_total": self.requetes_api_total,
            "temps_moyen_reponse_api_ms": round(self.temps_moyen_reponse_api_ms(), 1),
        }


# Instance unique partagée par tout le processus (moteur, KPI, Socket.IO, API).
registry = TechnicalMetricsRegistry()