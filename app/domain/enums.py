from __future__ import annotations

from enum import Enum


class Priority(str, Enum):
    alta  = "alta"
    media = "media"
    baixa = "baixa"

    def __lt__(self, other: "Priority") -> bool:
        _order = {Priority.alta: 0, Priority.media: 1, Priority.baixa: 2}
        return _order[self] < _order[other]


class AlertSeverity(str, Enum):
    error   = "error"
    warning = "warning"
    info    = "info"


class RecommendationType(str, Enum):
    custo        = "custo"
    pagamento    = "pagamento"
    mix          = "mix"
    cliente      = "cliente"
    concentracao = "concentracao"
    operacional  = "operacional"
    ticket       = "ticket"
