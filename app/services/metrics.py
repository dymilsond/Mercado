from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# KPIs globais
# ---------------------------------------------------------------------------
def kpis_gerais(df: pd.DataFrame) -> dict:
    n_transacoes = len(df)
    faturamento  = df["valor_total"].sum()
    n_itens      = df["quantidade"].sum()
    n_produtos   = df["produto"].nunique()
    n_clientes   = df["cliente"].nunique()
    ticket_medio = faturamento / n_transacoes if n_transacoes > 0 else 0.0

    return {
        "faturamento":   round(faturamento, 2),
        "n_transacoes":  int(n_transacoes),
        "n_itens":       int(n_itens),
        "n_produtos":    int(n_produtos),
        "n_clientes":    int(n_clientes),
        "ticket_medio":  round(ticket_medio, 2),
    }


# ---------------------------------------------------------------------------
# Clientes
# ---------------------------------------------------------------------------
def ranking_clientes(df: pd.DataFrame) -> pd.DataFrame:
    grp = (
        df.groupby("cliente")
        .agg(
            faturamento=("valor_total", "sum"),
            transacoes=("valor_total", "count"),
            itens=("quantidade", "sum"),
        )
        .reset_index()
        .sort_values("faturamento", ascending=False)
    )
    total = grp["faturamento"].sum()
    grp["participacao_pct"] = (grp["faturamento"] / total * 100).round(1)
    grp["ticket_medio"] = (grp["faturamento"] / grp["transacoes"]).round(2)
    return grp


# ---------------------------------------------------------------------------
# Categorias
# ---------------------------------------------------------------------------
def participacao_categorias(df: pd.DataFrame) -> pd.DataFrame:
    grp = (
        df.groupby("categoria")
        .agg(
            faturamento=("valor_total", "sum"),
            itens=("quantidade", "sum"),
            transacoes=("valor_total", "count"),
            produtos=("produto", "nunique"),
        )
        .reset_index()
        .sort_values("faturamento", ascending=False)
    )
    total = grp["faturamento"].sum()
    grp["participacao_pct"] = (grp["faturamento"] / total * 100).round(1)
    return grp


# ---------------------------------------------------------------------------
# Produtos
# ---------------------------------------------------------------------------
def ranking_produtos(df: pd.DataFrame, top_n: int = 30) -> pd.DataFrame:
    grp = (
        df.groupby(["produto", "categoria"])
        .agg(
            faturamento=("valor_total", "sum"),
            itens=("quantidade", "sum"),
            transacoes=("valor_total", "count"),
            n_clientes=("cliente", "nunique"),
            preco_medio=("valor_unitario", "mean"),
        )
        .reset_index()
        .sort_values("faturamento", ascending=False)
        .head(top_n)
    )
    total = df["valor_total"].sum()
    grp["participacao_pct"] = (grp["faturamento"] / total * 100).round(2)
    grp["preco_medio"] = grp["preco_medio"].round(2)
    return grp


def produtos_baixa_saida(df: pd.DataFrame, max_vendas: int = 1) -> pd.DataFrame:
    grp = (
        df.groupby(["produto", "categoria"])
        .agg(
            itens=("quantidade", "sum"),
            faturamento=("valor_total", "sum"),
            transacoes=("valor_total", "count"),
        )
        .reset_index()
    )
    return grp[grp["itens"] <= max_vendas].sort_values("faturamento", ascending=False)


def pareto_produtos(df: pd.DataFrame) -> dict:
    """Retorna quantos produtos representam 80% do faturamento."""
    grp = (
        df.groupby("produto")["valor_total"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    total = grp["valor_total"].sum()
    grp["acumulado"] = grp["valor_total"].cumsum()
    grp["acumulado_pct"] = grp["acumulado"] / total
    n_pareto = int((grp["acumulado_pct"] <= 0.80).sum())
    total_produtos = len(grp)
    return {
        "n_pareto_80": n_pareto,
        "total_produtos": total_produtos,
        "pct_catalogo": round(n_pareto / total_produtos * 100, 1) if total_produtos else 0,
    }


# ---------------------------------------------------------------------------
# Temporal
# ---------------------------------------------------------------------------
def faturamento_por_dia(df: pd.DataFrame) -> pd.DataFrame:
    grp = (
        df.groupby(["data", "dia_semana"])
        .agg(
            faturamento=("valor_total", "sum"),
            itens=("quantidade", "sum"),
            transacoes=("valor_total", "count"),
        )
        .reset_index()
        .sort_values("data")
    )
    return grp


def faturamento_por_dia_semana(df: pd.DataFrame) -> pd.DataFrame:
    ordem = [
        "segunda-feira", "terca-feira", "quarta-feira",
        "quinta-feira", "sexta-feira", "sabado", "domingo",
    ]
    grp = (
        df.groupby("dia_semana")
        .agg(
            faturamento=("valor_total", "sum"),
            transacoes=("valor_total", "count"),
            itens=("quantidade", "sum"),
        )
        .reset_index()
    )
    grp["ordem"] = grp["dia_semana"].apply(
        lambda d: ordem.index(d) if d in ordem else 99
    )
    return grp.sort_values("ordem").drop(columns="ordem")


def faturamento_por_hora(df: pd.DataFrame) -> pd.DataFrame:
    grp = (
        df.groupby("hora")
        .agg(
            faturamento=("valor_total", "sum"),
            transacoes=("valor_total", "count"),
            itens=("quantidade", "sum"),
        )
        .reset_index()
        .sort_values("hora")
    )
    return grp


def heatmap_hora_dia(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot: index=hora, columns=dia_semana, values=faturamento."""
    grp = (
        df.groupby(["hora", "dia_semana"])["valor_total"]
        .sum()
        .reset_index()
    )
    pivot = grp.pivot(index="hora", columns="dia_semana", values="valor_total").fillna(0)
    return pivot


def faturamento_por_periodo(df: pd.DataFrame) -> pd.DataFrame:
    grp = (
        df.groupby("periodo")
        .agg(
            faturamento=("valor_total", "sum"),
            transacoes=("valor_total", "count"),
        )
        .reset_index()
        .sort_values("faturamento", ascending=False)
    )
    total = grp["faturamento"].sum()
    grp["participacao_pct"] = (grp["faturamento"] / total * 100).round(1)
    return grp


# ---------------------------------------------------------------------------
# Pagamentos
# ---------------------------------------------------------------------------
def metricas_pagamento(df: pd.DataFrame) -> pd.DataFrame:
    grp = (
        df.groupby("metodo_pagamento")
        .agg(
            faturamento=("valor_total", "sum"),
            transacoes=("valor_total", "count"),
            itens=("quantidade", "sum"),
        )
        .reset_index()
        .sort_values("faturamento", ascending=False)
    )
    total = grp["faturamento"].sum()
    grp["participacao_pct"] = (grp["faturamento"] / total * 100).round(1)
    grp["ticket_medio"] = (grp["faturamento"] / grp["transacoes"]).round(2)
    return grp


def metricas_bandeira(df: pd.DataFrame) -> pd.DataFrame:
    df_cards = df[df["bandeira"].notna() & (df["bandeira"] != "Não informado")]
    if df_cards.empty:
        return pd.DataFrame()
    grp = (
        df_cards.groupby("bandeira")
        .agg(
            faturamento=("valor_total", "sum"),
            transacoes=("valor_total", "count"),
        )
        .reset_index()
        .sort_values("faturamento", ascending=False)
    )
    total = grp["faturamento"].sum()
    grp["participacao_pct"] = (grp["faturamento"] / total * 100).round(1)
    return grp
