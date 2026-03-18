from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------------------
# Constantes internas
# ---------------------------------------------------------------------------
_COL_CUSTO_UNIT   = "custo_unitario_real"
_COL_LUCRO        = "lucro"
_COL_MARGEM       = "margem_percentual"

_MARGEM_BAIXA_PCT    = 10.0   # < 10% → atenção
_TOP_VENDA_PERCENTIL = 0.70   # top 30% por faturamento define "alto giro"
_ALTA_MARGEM_PCT     = 30.0   # >= 30% → produto de alta margem


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------
def _tem_custo_real(df: pd.DataFrame) -> bool:
    return _COL_CUSTO_UNIT in df.columns and df[_COL_CUSTO_UNIT].notna().any()


def _df_custo(df: pd.DataFrame) -> pd.DataFrame:
    """Retorna apenas linhas com custo real disponivel."""
    if not _tem_custo_real(df):
        return df.iloc[0:0].copy()
    return df.dropna(subset=[_COL_CUSTO_UNIT]).copy()


# ---------------------------------------------------------------------------
# Cobertura de custo
# ---------------------------------------------------------------------------
def get_cobertura_custo(df: pd.DataFrame) -> float:
    """Percentual de linhas com custo real cadastrado (0-100)."""
    if _COL_CUSTO_UNIT not in df.columns:
        return 0.0
    return float(df[_COL_CUSTO_UNIT].notna().mean() * 100)


# ---------------------------------------------------------------------------
# Métricas globais
# ---------------------------------------------------------------------------
def get_total_profit(df: pd.DataFrame) -> float | None:
    """Lucro total. None se nao houver custo real."""
    dfc = _df_custo(df)
    if dfc.empty:
        return None
    return float(dfc[_COL_LUCRO].sum())


def get_margin(df: pd.DataFrame) -> float | None:
    """Margem media ponderada (%). None se nao houver custo real."""
    dfc = _df_custo(df)
    if dfc.empty:
        return None
    fat = dfc["valor_total"].sum()
    if fat == 0:
        return None
    return float(dfc[_COL_LUCRO].sum() / fat * 100)


# ---------------------------------------------------------------------------
# Por produto
# ---------------------------------------------------------------------------
def get_profit_by_product(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame: produto, categoria, faturamento, custo_total, lucro,
               margem_pct, participacao_pct, itens.
    Ordenado por lucro DESC.
    """
    dfc = _df_custo(df)
    if dfc.empty:
        return pd.DataFrame(columns=[
            "produto", "categoria", "faturamento",
            "custo_total", "lucro", "margem_pct", "participacao_pct", "itens",
        ])
    grp = (
        dfc.groupby(["produto", "categoria"])
        .agg(
            faturamento=("valor_total",       "sum"),
            custo_total=("custo_total_real",  "sum"),
            lucro      =(_COL_LUCRO,          "sum"),
            itens      =("quantidade",         "sum"),
        )
        .reset_index()
    )
    total_fat = grp["faturamento"].sum()
    grp["margem_pct"] = grp.apply(
        lambda r: round(r["lucro"] / r["faturamento"] * 100, 1) if r["faturamento"] > 0 else 0.0,
        axis=1,
    )
    grp["participacao_pct"] = (
        (grp["faturamento"] / total_fat * 100).round(1) if total_fat > 0 else 0.0
    )
    return grp.sort_values("lucro", ascending=False).reset_index(drop=True)


def get_top_profit_products(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Top N produtos por lucro."""
    return get_profit_by_product(df).head(n)


def get_worst_profit_products(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """N produtos com menor lucro (prejuizo primeiro)."""
    return get_profit_by_product(df).sort_values("lucro").head(n).reset_index(drop=True)


def get_products_with_loss(df: pd.DataFrame) -> pd.DataFrame:
    """Produtos com lucro negativo (prejuizo)."""
    prod = get_profit_by_product(df)
    return prod[prod["lucro"] < 0].reset_index(drop=True)


def get_high_sale_low_margin(df: pd.DataFrame) -> pd.DataFrame:
    """Produtos no top 30% de faturamento mas com margem < 10%."""
    prod = get_profit_by_product(df)
    if prod.empty:
        return prod
    threshold = prod["faturamento"].quantile(_TOP_VENDA_PERCENTIL)
    return prod[
        (prod["faturamento"] >= threshold) & (prod["margem_pct"] < _MARGEM_BAIXA_PCT)
    ].reset_index(drop=True)


def get_high_margin_low_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Produtos com margem >= 30% mas faturamento no bottom 30% — candidatos a promocao."""
    prod = get_profit_by_product(df)
    if prod.empty:
        return prod
    threshold = prod["faturamento"].quantile(1.0 - _TOP_VENDA_PERCENTIL)
    return prod[
        (prod["faturamento"] <= threshold) & (prod["margem_pct"] >= _ALTA_MARGEM_PCT)
    ].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Por unidade operacional
# ---------------------------------------------------------------------------
def get_profit_by_unit(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame: cliente, faturamento, custo_total, lucro, margem_pct.
    Ordenado por lucro DESC.
    """
    dfc = _df_custo(df)
    if dfc.empty:
        return pd.DataFrame(columns=[
            "cliente", "faturamento", "custo_total", "lucro", "margem_pct",
        ])
    grp = (
        dfc.groupby("cliente")
        .agg(
            faturamento=("valor_total",      "sum"),
            custo_total=("custo_total_real", "sum"),
            lucro      =(_COL_LUCRO,         "sum"),
        )
        .reset_index()
    )
    grp["margem_pct"] = grp.apply(
        lambda r: round(r["lucro"] / r["faturamento"] * 100, 1) if r["faturamento"] > 0 else 0.0,
        axis=1,
    )
    return grp.sort_values("lucro", ascending=False).reset_index(drop=True)
