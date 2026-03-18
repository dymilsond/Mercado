from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from domain.enums import AlertSeverity, Priority, RecommendationType


@dataclass(frozen=True, slots=True)
class Recommendation:
    tipo:              RecommendationType
    prioridade:        Priority
    titulo:            str
    descricao:         str
    impacto_estimado:  str


@dataclass(frozen=True, slots=True)
class Alert:
    titulo:    str
    mensagem:  str
    severity:  AlertSeverity
    acao:      str = ""


@dataclass
class ActionLog:
    id:                 int
    data:               str
    tipo:               str
    titulo:             str
    descricao:          str
    usuario:            str
    resultado:          str          = "pendente"
    resolvido:          bool         = False
    data_atualizacao:   Optional[str] = None
