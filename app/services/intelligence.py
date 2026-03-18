from __future__ import annotations

import datetime
import math

import pandas as pd

# ---------------------------------------------------------------------------
# Thresholds configuráveis
# ---------------------------------------------------------------------------
_MIN_DAYS_TREND    = 2     # mínimo de dias para calcular tendência
_MIN_DAYS_ANOMALY  = 3     # mínimo para detecção de anomalia
_MIN_DAYS_FORECAST = 2     # mínimo para projeção
_ANOMALY_Z_THRESH  = 2.0   # z-score >= 2 → anomalia
_TREND_SLOPE_PCT   = 0.05  # |slope| > 5% da média diária → subindo/caindo


# ---------------------------------------------------------------------------
# Helpers internos (sem dependência externa — apenas stdlib + pandas)
# ---------------------------------------------------------------------------
def _daily_series(df: pd.DataFrame) -> pd.Series:
    """Soma de valor_total por dia, ordenada cronologicamente."""
    if df.empty or "data" not in df.columns or "valor_total" not in df.columns:
        return pd.Series(dtype=float, name="valor_total")
    return df.groupby("data")["valor_total"].sum().sort_index()


def _ols(x: list[float], y: list[float]) -> tuple[float, float]:
    """
    Regressão linear simples OLS.
    Retorna (slope, intercept) usando apenas stdlib.
    """
    n = len(x)
    if n < 2:
        return 0.0, (y[0] if y else 0.0)
    x_mean = sum(x) / n
    y_mean = sum(y) / n
    num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
    den = sum((xi - x_mean) ** 2 for xi in x)
    slope = num / den if den != 0 else 0.0
    return slope, y_mean - slope * x_mean


def _rmse(y: list[float], y_fit: list[float]) -> float:
    """RMSE entre valores reais e ajustados."""
    n = len(y)
    if n < 2:
        return 0.0
    return math.sqrt(sum((yi - yf) ** 2 for yi, yf in zip(y, y_fit)) / n)


# ---------------------------------------------------------------------------
# 1. Tendência de faturamento
# ---------------------------------------------------------------------------
def get_revenue_trend(df: pd.DataFrame) -> dict:
    """
    Analisa a tendência de faturamento diário com regressão linear simples.

    Retorna:
        direction       : "subindo" | "caindo" | "estavel"
        slope_diario    : R$ por dia (positivo = crescendo)
        media_diaria    : média do período
        pct_variacao    : % entre primeiro e último dia
        dias_analisados : int
        serie           : DataFrame(data, faturamento, media_movel_3d)
    """
    daily = _daily_series(df)
    n = len(daily)

    _empty_serie = pd.DataFrame(columns=["data", "faturamento", "media_movel_3d"])

    if n < _MIN_DAYS_TREND:
        return {
            "direction":       "estavel",
            "slope_diario":    0.0,
            "media_diaria":    float(daily.mean()) if n == 1 else 0.0,
            "pct_variacao":    0.0,
            "dias_analisados": n,
            "serie":           _empty_serie,
        }

    x_vals = list(range(n))
    y_vals = [float(v) for v in daily.tolist()]
    slope, _ = _ols(x_vals, y_vals)
    media     = sum(y_vals) / n

    threshold = media * _TREND_SLOPE_PCT
    if slope > threshold:
        direction = "subindo"
    elif slope < -threshold:
        direction = "caindo"
    else:
        direction = "estavel"

    primeiro = y_vals[0]
    ultimo   = y_vals[-1]
    pct_var  = round((ultimo - primeiro) / primeiro * 100, 1) if primeiro > 0 else 0.0

    serie = pd.DataFrame({
        "data":        daily.index.tolist(),
        "faturamento": y_vals,
    })
    serie["media_movel_3d"] = (
        serie["faturamento"].rolling(window=3, min_periods=1).mean().round(2)
    )

    return {
        "direction":       direction,
        "slope_diario":    round(slope, 2),
        "media_diaria":    round(media, 2),
        "pct_variacao":    pct_var,
        "dias_analisados": n,
        "serie":           serie,
    }


# ---------------------------------------------------------------------------
# 2. Padrão por hora do dia
# ---------------------------------------------------------------------------
def get_hour_pattern(df: pd.DataFrame) -> pd.DataFrame:
    """
    Faturamento por hora do dia.
    Retorna DataFrame: hora, faturamento, participacao_pct, rank.
    """
    if df.empty or "hora" not in df.columns:
        return pd.DataFrame(columns=["hora", "faturamento", "participacao_pct", "rank"])

    grp = df.groupby("hora")["valor_total"].sum().reset_index()
    grp.columns = ["hora", "faturamento"]
    total = grp["faturamento"].sum()
    grp["participacao_pct"] = (
        (grp["faturamento"] / total * 100).round(1) if total > 0 else 0.0
    )
    grp_sorted = grp.sort_values("faturamento", ascending=False).reset_index(drop=True)
    rank_map   = {row["hora"]: i + 1 for i, row in grp_sorted.iterrows()}
    grp["rank"] = grp["hora"].map(rank_map)
    return grp.sort_values("hora").reset_index(drop=True)


# ---------------------------------------------------------------------------
# 3. Padrão por dia da semana
# ---------------------------------------------------------------------------
_ORDEM_SEMANA = [
    "segunda-feira", "terca-feira", "quarta-feira",
    "quinta-feira",  "sexta-feira", "sabado", "domingo",
]


def get_weekday_pattern(df: pd.DataFrame) -> pd.DataFrame:
    """
    Faturamento por dia da semana.
    Retorna DataFrame: dia_semana, faturamento, participacao_pct, rank.
    Ordenado por dia canônico (seg → dom).
    """
    if df.empty or "dia_semana" not in df.columns:
        return pd.DataFrame(columns=["dia_semana", "faturamento", "participacao_pct", "rank"])

    grp = df.groupby("dia_semana")["valor_total"].sum().reset_index()
    grp.columns = ["dia_semana", "faturamento"]
    total = grp["faturamento"].sum()
    grp["participacao_pct"] = (
        (grp["faturamento"] / total * 100).round(1) if total > 0 else 0.0
    )
    grp_sorted = grp.sort_values("faturamento", ascending=False).reset_index(drop=True)
    rank_map   = {row["dia_semana"]: i + 1 for i, row in grp_sorted.iterrows()}
    grp["rank"] = grp["dia_semana"].map(rank_map)

    _ordem = {d: i for i, d in enumerate(_ORDEM_SEMANA)}
    grp["_ord"] = grp["dia_semana"].map(lambda x: _ordem.get(x, 99))
    return grp.sort_values("_ord").drop(columns=["_ord"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 4. Detecção de anomalias
# ---------------------------------------------------------------------------
def detect_anomalies(
    df: pd.DataFrame,
    threshold: float = _ANOMALY_Z_THRESH,
) -> list[dict]:
    """
    Detecta dias com faturamento fora do padrão (|z-score| >= threshold).
    Usa estatísticas globais do período (análise retrospectiva — sem lookahead).

    Retorna lista de dicts:
        data, faturamento, esperado, zscore, tipo ("pico" / "queda")
    """
    daily = _daily_series(df)
    n = len(daily)
    if n < _MIN_DAYS_ANOMALY:
        return []

    mean = float(daily.mean())
    std  = float(daily.std())
    if std == 0:
        return []

    anomalies = []
    for date, fat in daily.items():
        z = (float(fat) - mean) / std
        if abs(z) >= threshold:
            anomalies.append({
                "data":       date,
                "faturamento": round(float(fat), 2),
                "esperado":   round(mean, 2),
                "zscore":     round(z, 2),
                "tipo":       "pico" if z > 0 else "queda",
            })
    return sorted(anomalies, key=lambda x: x["data"])


# ---------------------------------------------------------------------------
# 5. Previsão de faturamento (sem lookahead bias)
# ---------------------------------------------------------------------------
def forecast_next_days(df: pd.DataFrame, days: int = 7) -> dict:
    """
    Previsão de faturamento para os próximos N dias.
    Usa regressão linear OLS sobre série histórica diária.

    Sem lookahead bias: apenas o histórico disponível alimenta o modelo.

    Retorna:
        dias_base         : int
        media_diaria      : float
        slope_diario      : float (R$/dia)
        previsao          : DataFrame(data_prevista, faturamento_previsto,
                                      limite_inferior, limite_superior)
        metodo            : str
        aviso             : str
    """
    daily = _daily_series(df)
    n = len(daily)

    _vazio = {
        "dias_base":    n,
        "media_diaria": float(daily.mean()) if n > 0 else 0.0,
        "slope_diario": 0.0,
        "previsao":     pd.DataFrame(columns=[
            "data_prevista", "faturamento_previsto",
            "limite_inferior", "limite_superior",
        ]),
        "metodo": "sem_dados",
        "aviso":  f"Base insuficiente ({n} dia(s)). Minimo: {_MIN_DAYS_FORECAST} dias.",
    }
    if n < _MIN_DAYS_FORECAST:
        return _vazio

    x_vals   = list(range(n))
    y_vals   = [float(v) for v in daily.tolist()]
    slope, intercept = _ols(x_vals, y_vals)

    fitted   = [intercept + slope * x for x in x_vals]
    rmse     = _rmse(y_vals, fitted)
    ci_width = 1.5 * rmse  # ~87% CI (assume distribuição normal dos resíduos)

    last_date = daily.index[-1]
    rows = []
    for k in range(1, days + 1):
        pred_date = last_date + datetime.timedelta(days=k)
        x_pred    = n - 1 + k
        pred      = max(0.0, intercept + slope * x_pred)
        rows.append({
            "data_prevista":        pred_date,
            "faturamento_previsto": round(pred, 2),
            "limite_inferior":      round(max(0.0, pred - ci_width), 2),
            "limite_superior":      round(pred + ci_width, 2),
        })

    aviso = (
        f"Base curta ({n} dia(s)) — acuracia limitada. Previsao indicativa."
        if n < 14 else
        f"Previsao baseada em {n} dia(s) de historico."
    )

    return {
        "dias_base":    n,
        "media_diaria": round(sum(y_vals) / n, 2),
        "slope_diario": round(slope, 2),
        "previsao":     pd.DataFrame(rows),
        "metodo":       "regressao_linear",
        "aviso":        aviso,
    }
