from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

# Type aliases para consistência nos serviços
MetricsDict   = dict[str, float | int]
AlertList     = list  # list[Alert]
RecList       = list  # list[Recommendation]
ActionLogList = list  # list[dict]

# Constante global de aviso de base pequena
SMALL_BASE_THRESHOLD_DAYS = 15
