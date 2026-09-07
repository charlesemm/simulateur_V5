"""Registre en mémoire des métriques TECHNIQUES du simulateur.

Volontairement : aucune métrique métier CMU ici (montants remboursés,
répartition des pathologies, etc.) -- uniquement des indicateurs sur le
fonctionnement du simulateur lui-même (charge, fiabilité, latence, ressources).
"""
from __future__ import annotations

import ctypes

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

journal = logging.getLogger(__name__)


def _get_process_memory_mb() -> float:
    """Retourne la mémoire RSS du processus en Mo."""
    try:
        if sys.platform == "win32":
            import ctypes.wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.wintypes.DWORD),
                    ("PageFaultCount", ctypes.wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            psapi = ctypes.windll.psapi
            kernel = ctypes.windll.kernel32
            kernel.GetCurrentProcess.restype = ctypes.c_void_p
            psapi.GetProcessMemoryInfo.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                ctypes.wintypes.DWORD,
            ]
            psapi.GetProcessMemoryInfo.restype = ctypes.wintypes.BOOL

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                return round(counters.WorkingSetSize / (1024 * 1024), 2)
        else:
            import resource
            return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)
    except Exception:
        # La mémoire est un indicateur de confort : son absence ne doit jamais
        # faire échouer un appel. Mais elle doit se voir dans le journal, sinon
        # le « 0 Mo » renvoyé plus bas se lit comme une mesure au lieu d'un
        # échec, et on cherche une fuite dans un chiffre jamais mesuré.
        journal.debug("Mesure mémoire indisponible.", exc_info=True)
    return 0.0


@dataclass
class TechnicalMetricsRegistry:
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    passages_reussis: int = 0
    passages_echoues: int = 0
    pic_passages_simultanes: int = 0
    evenements_totaux: int = 0

    recalculs_kpi: int = 0
    duree_totale_recalculs_kpi_secondes: float = 0.0
    derniere_duree_recalcul_kpi_ms: float = 0.0

    connexions_socketio_total: int = 0
    deconnexions_socketio_total: int = 0
    clients_socketio_actifs: int = 0

    requetes_api_total: int = 0
    duree_totale_requetes_api_secondes: float = 0.0
    derniere_latence_api_ms: float = 0.0

    def enregistrer_passage(self, succes: bool) -> None:
        if succes:
            self.passages_reussis += 1
        else:
            self.passages_echoues += 1

    def enregistrer_evenement(self) -> None:
        self.evenements_totaux += 1

    def enregistrer_pic(self, valeur: int) -> None:
        self.pic_passages_simultanes = max(self.pic_passages_simultanes, valeur)

    def enregistrer_recalcul_kpi(self, duree_secondes: float) -> None:
        self.recalculs_kpi += 1
        self.duree_totale_recalculs_kpi_secondes += duree_secondes
        self.derniere_duree_recalcul_kpi_ms = round(duree_secondes * 1000, 2)

    def enregistrer_connexion_socketio(self) -> None:
        self.connexions_socketio_total += 1
        self.clients_socketio_actifs += 1

    def enregistrer_deconnexion_socketio(self) -> None:
        self.deconnexions_socketio_total += 1
        self.clients_socketio_actifs = max(0, self.clients_socketio_actifs - 1)

    def enregistrer_requete_api(self, duree_secondes: float) -> None:
        self.requetes_api_total += 1
        self.duree_totale_requetes_api_secondes += duree_secondes
        self.derniere_latence_api_ms = round(duree_secondes * 1000, 2)

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
        uptime = max(1.0, self.uptime_secondes())
        return {
            "demarre_depuis": self.started_at.isoformat(),
            "uptime_secondes": round(uptime, 1),
            "passages_reussis": self.passages_reussis,
            "passages_echoues": self.passages_echoues,
            "passages_total": total_passages,
            "taux_echec_pourcent": round(100 * self.passages_echoues / max(1, total_passages), 2),
            "taux_succes_pourcent": round(100 * self.passages_reussis / max(1, total_passages), 2),
            "debit_passages_par_sec": round(total_passages / uptime, 2),
            "pic_passages_simultanes": self.pic_passages_simultanes,
            "evenements_totaux": self.evenements_totaux,
            "debit_evenements_par_sec": round(self.evenements_totaux / uptime, 2),
            "recalculs_kpi": self.recalculs_kpi,
            "temps_moyen_recalcul_kpi_ms": round(self.temps_moyen_recalcul_kpi_ms(), 1),
            "derniere_duree_recalcul_kpi_ms": self.derniere_duree_recalcul_kpi_ms,
            "connexions_socketio_total": self.connexions_socketio_total,
            "deconnexions_socketio_total": self.deconnexions_socketio_total,
            "clients_socketio_actifs": self.clients_socketio_actifs,
            "requetes_api_total": self.requetes_api_total,
            "temps_moyen_reponse_api_ms": round(self.temps_moyen_reponse_api_ms(), 1),
            "derniere_latence_api_ms": self.derniere_latence_api_ms,
            "debit_requetes_par_sec": round(self.requetes_api_total / uptime, 2),
            "memoire_rss_mo": _get_process_memory_mb(),
        }


# Instance unique partagée par tout le processus (moteur, KPI, Socket.IO, API).
registry = TechnicalMetricsRegistry()
