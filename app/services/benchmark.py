from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# Thresholds de alerta comparativo
# ---------------------------------------------------------------------------
_ABAIXO_MEDIA_FATOR     = 0.50   # < 50% da média → unidade crítica
_PIX_ABAIXO_GRUPO_DELTA = 10.0   # mais de 10pp abaixo da média do grupo
_CONCENTRACAO_ACIMA     = 1.30   # 30% mais concentrado que a média do grupo
_MADRUGADA_ACIMA_DELTA  = 5.0    # mais de 5pp acima da média do grupo


# ---------------------------------------------------------------------------
# 1. Ranking geral
# ---------------------------------------------------------------------------
def get_unit_ranking(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ranking completo de unidades por faturamento, com KPIs principais.
    """
    agg_spec: dict = {
        "faturamento": ("valor_total", "sum"),
        "transacoes":  ("valor_total", "count"),
    }
    if "quantidade" in df.columns:
        agg_spec["itens"] = ("quantidade", "sum")
    if "produto" in df.columns:
        agg_spec["n_produtos"] = ("produto", "nunique")
    if "categoria" in df.columns:
        agg_spec["n_categorias"] = ("categoria", "nunique")

    grp = (
        df.groupby("cliente")
        .agg(**agg_spec)
        .reset_index()
        .sort_values("faturamento", ascending=False)
        .reset_index(drop=True)
    )
    if "itens" not in grp.columns:
        grp["itens"] = 0
    if "n_produtos" not in grp.columns:
        grp["n_produtos"] = 0
    if "n_categorias" not in grp.columns:
        grp["n_categorias"] = 0
    grp["ranking"]          = grp.index + 1
    total                   = grp["faturamento"].sum()
    grp["participacao_pct"] = (grp["faturamento"] / total * 100).round(1)
    grp["ticket_medio"]     = (grp["faturamento"] / grp["transacoes"]).round(2)
    grp["itens_por_trans"]  = (grp["itens"] / grp["transacoes"]).round(2)
    return grp


# ---------------------------------------------------------------------------
# 2. Benchmark vs média do grupo
# ---------------------------------------------------------------------------
def get_unit_benchmark(df: pd.DataFrame) -> pd.DataFrame:
    """
    Para cada unidade: valor absoluto e desvio percentual contra a média do grupo.
    """
    rank = get_unit_ranking(df)
    metricas = ["faturamento", "ticket_medio", "transacoes", "itens", "itens_por_trans"]

    for m in metricas:
        media = rank[m].mean()
        rank[f"{m}_vs_media_pct"] = ((rank[m] - media) / media * 100).round(1) if media != 0 else 0.0
        rank[f"{m}_media"] = round(media, 2)

    return rank


# ---------------------------------------------------------------------------
# 3. Gap vs média — resumo por unidade
# ---------------------------------------------------------------------------
def get_unit_vs_average(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame com gap absoluto e relativo de cada unidade contra a média.
    Positivo = acima da média, negativo = abaixo.
    """
    bench = get_unit_benchmark(df)
    media_fat    = bench["faturamento_media"].iloc[0]
    media_ticket = bench["ticket_medio_media"].iloc[0]

    resultado = bench[["cliente", "ranking", "faturamento", "ticket_medio",
                        "transacoes", "participacao_pct"]].copy()
    resultado["gap_fat_abs"]     = (bench["faturamento"] - media_fat).round(2)
    resultado["gap_fat_pct"]     = bench["faturamento_vs_media_pct"]
    resultado["gap_ticket_abs"]  = (bench["ticket_medio"] - media_ticket).round(2)
    resultado["gap_ticket_pct"]  = bench["ticket_medio_vs_media_pct"]
    resultado["status"] = resultado["gap_fat_pct"].apply(
        lambda x: "acima" if x >= 10 else ("abaixo" if x <= -10 else "na_media")
    )
    return resultado


# ---------------------------------------------------------------------------
# 4. Perfil por unidade
# ---------------------------------------------------------------------------
def get_unit_profile(df: pd.DataFrame, unit_name: str) -> dict:
    """
    Perfil completo de uma unidade: KPIs, top produtos, categorias,
    horários de pico e método de pagamento.
    """
    df_u = df[df["cliente"] == unit_name]
    if df_u.empty:
        return {}

    n = len(df_u)
    fat = df_u["valor_total"].sum()

    # Top produtos
    top_produtos = (
        df_u.groupby("produto")["valor_total"].sum()
        .sort_values(ascending=False)
        .head(5)
        .reset_index()
    )
    top_produtos.columns = ["produto", "faturamento"]
    top_produtos["pct"] = (top_produtos["faturamento"] / fat * 100).round(1)

    # Categorias
    categorias = (
        df_u.groupby("categoria")["valor_total"].sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    categorias.columns = ["categoria", "faturamento"]
    categorias["pct"] = (categorias["faturamento"] / fat * 100).round(1)

    # Períodos
    periodos = (
        df_u.groupby("periodo")["valor_total"].sum()
        .reset_index()
    )
    periodos["pct"] = (periodos["valor_total"] / fat * 100).round(1)

    # Hora de pico
    hora_pico_row = df_u.groupby("hora")["valor_total"].sum()
    hora_pico = int(hora_pico_row.idxmax()) if not hora_pico_row.empty else None

    # Pagamento
    pgto = df_u["metodo_pagamento"].value_counts(normalize=True) * 100

    # Produto com maior concentração
    prod_conc = top_produtos.iloc[0]["pct"] if not top_produtos.empty else 0.0

    return {
        "unidade":          unit_name,
        "faturamento":      round(fat, 2),
        "n_transacoes":     n,
        "ticket_medio":     round(fat / n, 2) if n > 0 else 0.0,
        "n_produtos":       df_u["produto"].nunique(),
        "n_categorias":     df_u["categoria"].nunique(),
        "hora_pico":        hora_pico,
        "top_produtos":     top_produtos,
        "categorias":       categorias,
        "periodos":         periodos,
        "pix_pct":          round(pgto.get("PIX", 0.0), 1),
        "pagamentos":       pgto.round(1).reset_index().rename(
                                columns={"index": "metodo", "metodo_pagamento": "metodo",
                                         "proportion": "pct"}
                            ),
        "concentracao_top1_pct": round(prod_conc, 1),
    }


# ---------------------------------------------------------------------------
# 5. Comparação de pagamentos entre unidades
# ---------------------------------------------------------------------------
def get_unit_payment_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tabela: unidade × método de pagamento, com % de transações.
    """
    total_u = df.groupby("cliente").size().rename("total")
    pgto_u  = df.groupby(["cliente", "metodo_pagamento"]).size().rename("n")
    result  = (pgto_u / total_u * 100).round(1).reset_index()
    result.columns = ["unidade", "metodo_pagamento", "pct_transacoes"]

    pivot = result.pivot(
        index="unidade", columns="metodo_pagamento", values="pct_transacoes"
    ).fillna(0).reset_index()
    pivot.columns.name = None
    return pivot


# ---------------------------------------------------------------------------
# 6. Comparação de horários entre unidades
# ---------------------------------------------------------------------------
def get_unit_time_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tabela: unidade × período do dia, com % do faturamento.
    """
    fat_u   = df.groupby("cliente")["valor_total"].sum().rename("fat_total")
    fat_per = df.groupby(["cliente", "periodo"])["valor_total"].sum().rename("fat")
    result  = (fat_per / fat_u * 100).round(1).reset_index()
    result.columns = ["unidade", "periodo", "pct_faturamento"]

    pivot = result.pivot(
        index="unidade", columns="periodo", values="pct_faturamento"
    ).fillna(0).reset_index()
    pivot.columns.name = None
    return pivot


# ---------------------------------------------------------------------------
# 7. Alertas comparativos
# ---------------------------------------------------------------------------
def get_comparative_alerts(df: pd.DataFrame) -> list[dict]:
    """
    Gera alertas de benchmark entre unidades.
    Retorna lista de dicts: {unidade, tipo, mensagem, severidade}
    """
    alertas = []
    bench   = get_unit_benchmark(df)
    pgto    = get_unit_payment_comparison(df)
    tempo   = get_unit_time_comparison(df)

    media_fat    = bench["faturamento_media"].iloc[0]
    media_ticket = bench["ticket_medio_media"].iloc[0]

    # PIX médio do grupo
    pix_medio_grupo = 0.0
    if "PIX" in pgto.columns:
        pix_medio_grupo = pgto["PIX"].mean()

    # Madrugada médio do grupo
    madr_medio_grupo = 0.0
    if "madrugada" in tempo.columns:
        madr_medio_grupo = tempo["madrugada"].mean()

    for _, row in bench.iterrows():
        unidade = row["cliente"]

        # 1. Unidade abaixo de 50% da média
        if row["faturamento"] < media_fat * _ABAIXO_MEDIA_FATOR:
            gap = row["faturamento"] - media_fat
            alertas.append({
                "unidade":    unidade,
                "tipo":       "performance",
                "severidade": "error",
                "mensagem": (
                    f"{unidade} está {abs(row['faturamento_vs_media_pct']):.0f}% abaixo da média do grupo "
                    f"(R$ {row['faturamento']:,.2f} vs média R$ {media_fat:,.2f}). "
                    f"Gap: R$ {abs(gap):,.2f}."
                ),
            })

        # 2. PIX muito abaixo do grupo
        if "PIX" in pgto.columns:
            pix_row = pgto[pgto["unidade"] == unidade]
            if not pix_row.empty:
                pix_u = pix_row["PIX"].iloc[0]
                if pix_medio_grupo > 0 and (pix_medio_grupo - pix_u) > _PIX_ABAIXO_GRUPO_DELTA:
                    alertas.append({
                        "unidade":    unidade,
                        "tipo":       "pagamento",
                        "severidade": "warning",
                        "mensagem": (
                            f"{unidade}: PIX em {pix_u:.1f}% vs média do grupo {pix_medio_grupo:.1f}%. "
                            f"Diferença de {pix_medio_grupo - pix_u:.1f}pp."
                        ),
                    })

        # 3. Madrugada acima da média
        if "madrugada" in tempo.columns:
            madr_row = tempo[tempo["unidade"] == unidade]
            if not madr_row.empty:
                madr_u = madr_row["madrugada"].iloc[0]
                if (madr_u - madr_medio_grupo) > _MADRUGADA_ACIMA_DELTA:
                    alertas.append({
                        "unidade":    unidade,
                        "tipo":       "operacional",
                        "severidade": "info",
                        "mensagem": (
                            f"{unidade}: {madr_u:.1f}% do faturamento na madrugada "
                            f"vs média do grupo {madr_medio_grupo:.1f}%. "
                            "Verificar abastecimento noturno."
                        ),
                    })

    # Ordenar: error > warning > info
    _ord = {"error": 0, "warning": 1, "info": 2}
    alertas.sort(key=lambda x: _ord.get(x["severidade"], 9))
    return alertas
