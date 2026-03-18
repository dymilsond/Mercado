from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


# ---------------------------------------------------------------------------
# Resultado de simulação
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class SimResult:
    titulo: str
    cenario_atual: str
    cenario_simulado: str
    impacto_financeiro: float   # R$ positivo = ganho, negativo = perda
    impacto_descricao: str
    premissas: str


# ---------------------------------------------------------------------------
# Simulação 1 — Adesão ao PIX
# ---------------------------------------------------------------------------
def simular_pix(
    df: pd.DataFrame,
    meta_pix_pct: float = 20.0,
    taxa_cartao_pct: float = 2.5,
) -> SimResult:
    """
    Simula economia ao migrar transações de cartão para PIX.
    meta_pix_pct: % de transações que passariam a ser PIX
    taxa_cartao_pct: taxa média cobrada pelo cartão (%)
    """
    n_total    = len(df)
    fat_total  = df["valor_total"].sum()
    grp_pct    = df["metodo_pagamento"].value_counts(normalize=True) * 100
    pix_atual  = grp_pct.get("PIX", 0.0)

    # Transações atuais que NÃO são PIX
    fat_nao_pix = df[df["metodo_pagamento"] != "PIX"]["valor_total"].sum()

    # Faturamento que seria migrado para PIX
    incremento_pix_pct = max(0, meta_pix_pct - pix_atual) / 100
    fat_migrado = fat_nao_pix * incremento_pix_pct
    economia    = fat_migrado * (taxa_cartao_pct / 100)

    return SimResult(
        titulo="Simulação: Adesão ao PIX",
        cenario_atual=(
            f"PIX atual: {pix_atual:.1f}% das transações. "
            f"Taxa de cartão aplicada: {taxa_cartao_pct:.1f}%."
        ),
        cenario_simulado=(
            f"Se PIX atingir {meta_pix_pct:.0f}% das transações, "
            f"R$ {fat_migrado:,.2f} migrariam de cartão para PIX."
        ),
        impacto_financeiro=round(economia, 2),
        impacto_descricao=(
            f"Economia estimada em taxas de cartão: R$ {economia:,.2f} no período."
        ),
        premissas=(
            f"Taxa média de cartão: {taxa_cartao_pct:.1f}%. "
            f"Meta PIX: {meta_pix_pct:.0f}%. "
            f"Base: {df['data'].nunique()} dia(s)."
        ),
    )


# ---------------------------------------------------------------------------
# Simulação 2 — Remoção de produtos de baixa saída
# ---------------------------------------------------------------------------
def simular_remocao_baixa_saida(
    df: pd.DataFrame,
    max_vendas: int = 1,
    reposicao_fator: float = 0.5,
    categorias_excluir: set[str] | None = None,
) -> SimResult:
    """
    Simula o impacto de remover produtos de baixa saída e repor com outros.
    reposicao_fator: % do faturamento perdido que seria recuperado com produtos substitutos
    """
    if categorias_excluir is None:
        categorias_excluir = {"vinhos", "vinho"}

    grp = (
        df.groupby(["produto", "categoria"])
        .agg(itens=("quantidade", "sum"), fat=("valor_total", "sum"))
        .reset_index()
    )
    baixos = grp[
        (grp["itens"] <= max_vendas) &
        (~grp["categoria"].str.lower().isin(categorias_excluir))
    ]

    fat_perdido   = baixos["fat"].sum()
    fat_recuperado = fat_perdido * reposicao_fator
    impacto       = fat_recuperado - fat_perdido  # negativo = perda líquida esperada

    return SimResult(
        titulo="Simulação: Remoção de produtos de baixa saída",
        cenario_atual=(
            f"{len(baixos)} produtos com ≤ {max_vendas} venda(s). "
            f"Faturamento combinado: R$ {fat_perdido:,.2f}."
        ),
        cenario_simulado=(
            f"Remover esses {len(baixos)} produtos e substituir por variações "
            f"dos campeões de venda, capturando {reposicao_fator*100:.0f}% do valor."
        ),
        impacto_financeiro=round(impacto, 2),
        impacto_descricao=(
            f"Perda imediata estimada: R$ {fat_perdido:,.2f}. "
            f"Recuperação via substituição: R$ {fat_recuperado:,.2f}. "
            f"Impacto líquido: R$ {impacto:,.2f}."
        ),
        premissas=(
            f"Fator de reposição: {reposicao_fator*100:.0f}%. "
            f"Categorias excluídas da análise: {', '.join(categorias_excluir)}. "
            f"Base: {df['data'].nunique()} dia(s)."
        ),
    )


# ---------------------------------------------------------------------------
# Simulação 3 — Crescimento de cliente fraco
# ---------------------------------------------------------------------------
def simular_crescimento_cliente(
    df: pd.DataFrame,
    cliente: str,
    meta_pct_media: float = 80.0,
) -> SimResult:
    """
    Simula quanto um cliente fraco precisaria crescer para atingir X% da média.
    """
    grp = df.groupby("cliente")["valor_total"].sum()
    fat_cliente = grp.get(cliente, 0.0)
    media       = grp.mean()
    meta_valor  = media * (meta_pct_media / 100)
    gap         = max(0.0, meta_valor - fat_cliente)

    return SimResult(
        titulo=f"Simulação: Crescimento de {cliente}",
        cenario_atual=(
            f"{cliente}: R$ {fat_cliente:,.2f}. "
            f"Média do grupo: R$ {media:,.2f}."
        ),
        cenario_simulado=(
            f"Atingir {meta_pct_media:.0f}% da média do grupo "
            f"(R$ {meta_valor:,.2f})."
        ),
        impacto_financeiro=round(gap, 2),
        impacto_descricao=(
            f"Seriam necessários R$ {gap:,.2f} adicionais "
            f"para {cliente} atingir {meta_pct_media:.0f}% da média."
        ),
        premissas=(
            f"Meta: {meta_pct_media:.0f}% da média do grupo. "
            f"Base: {df['data'].nunique()} dia(s)."
        ),
    )


# ---------------------------------------------------------------------------
# Simulação 4 — Projeção mensal (extrapolar base parcial)
# ---------------------------------------------------------------------------
def simular_ajuste_preco(
    df: pd.DataFrame,
    produto: str,
    aumento_pct: float = 10.0,
) -> SimResult:
    """
    Simula o impacto de ajustar o preco de venda de um produto.
    aumento_pct: percentual de aumento no preco (pode ser negativo para reducao).
    """
    df_prod = df[df["produto"] == produto]
    if df_prod.empty:
        return SimResult(
            titulo=f"Simulacao: Ajuste de preco — {produto}",
            cenario_atual="Produto nao encontrado no periodo.",
            cenario_simulado="N/A",
            impacto_financeiro=0.0,
            impacto_descricao="Produto nao encontrado.",
            premissas=f"Produto: {produto}. Aumento: {aumento_pct:.1f}%.",
        )
    fat_atual = df_prod["valor_total"].sum()
    fat_novo  = fat_atual * (1 + aumento_pct / 100)
    impacto   = fat_novo - fat_atual

    lucro_desc = ""
    if "lucro" in df_prod.columns and df_prod["lucro"].notna().any():
        lucro_atual = float(df_prod["lucro"].sum())
        lucro_novo  = lucro_atual + impacto
        lucro_desc  = f" Lucro estimado: R$ {lucro_novo:,.2f} (atual: R$ {lucro_atual:,.2f})."

    preco_medio = df_prod["valor_unitario"].mean() if "valor_unitario" in df_prod.columns else 0.0

    return SimResult(
        titulo=f"Simulacao: Ajuste de preco — {produto}",
        cenario_atual=(
            f"Faturamento atual: R$ {fat_atual:,.2f}. "
            f"Preco medio: R$ {preco_medio:,.2f}."
        ),
        cenario_simulado=(
            f"Com {'aumento' if aumento_pct >= 0 else 'reducao'} de {abs(aumento_pct):.1f}% "
            f"no preco, faturamento passaria para R$ {fat_novo:,.2f}."
        ),
        impacto_financeiro=round(impacto, 2),
        impacto_descricao=(
            f"{'Ganho' if impacto >= 0 else 'Perda'} adicional estimado: "
            f"R$ {impacto:,.2f} no periodo.{lucro_desc}"
        ),
        premissas=(
            f"Variacao de preco: {aumento_pct:+.1f}%. "
            "Demanda elastica nao considerada. "
            f"Base: {df['data'].nunique()} dia(s)."
        ),
    )


def simular_reducao_custo(
    df: pd.DataFrame,
    produto: str,
    reducao_pct: float = 10.0,
) -> SimResult:
    """
    Simula o impacto de reduzir o custo unitario de um produto.
    Requer custo_unitario_real cadastrado em data/custos.xlsx.
    """
    df_prod = df[df["produto"] == produto]
    sem_custo = (
        df_prod.empty
        or "custo_total_real" not in df.columns
        or df_prod["custo_total_real"].isna().all()
    )
    if sem_custo:
        return SimResult(
            titulo=f"Simulacao: Reducao de custo — {produto}",
            cenario_atual="Custo real nao disponivel para este produto.",
            cenario_simulado="N/A",
            impacto_financeiro=0.0,
            impacto_descricao="Cadastre o custo do produto em app/data/custos.xlsx.",
            premissas=f"Produto: {produto}. Reducao: {reducao_pct:.1f}%.",
        )

    custo_atual = float(df_prod["custo_total_real"].sum())
    fat_atual   = float(df_prod["valor_total"].sum())
    lucro_atual = float(df_prod["lucro"].sum())
    custo_novo  = custo_atual * (1 - reducao_pct / 100)
    ganho       = custo_atual - custo_novo
    lucro_novo  = lucro_atual + ganho
    margem_nova = (lucro_novo / fat_atual * 100) if fat_atual > 0 else 0.0

    return SimResult(
        titulo=f"Simulacao: Reducao de custo — {produto}",
        cenario_atual=(
            f"Custo total: R$ {custo_atual:,.2f}. "
            f"Faturamento: R$ {fat_atual:,.2f}. "
            f"Lucro atual: R$ {lucro_atual:,.2f}."
        ),
        cenario_simulado=(
            f"Com reducao de {reducao_pct:.1f}% no custo, "
            f"custo passaria para R$ {custo_novo:,.2f}."
        ),
        impacto_financeiro=round(ganho, 2),
        impacto_descricao=(
            f"Economia de custo: R$ {ganho:,.2f}. "
            f"Novo lucro estimado: R$ {lucro_novo:,.2f} "
            f"(margem {margem_nova:.1f}%)."
        ),
        premissas=(
            f"Reducao de custo: {reducao_pct:.1f}%. "
            "Preco de venda mantido. "
            f"Base: {df['data'].nunique()} dia(s)."
        ),
    )


def simular_projecao_mensal(df: pd.DataFrame) -> SimResult:
    """
    Extrapola o faturamento observado para 30 dias.
    Útil quando a base tem poucos dias (ex: 8 dias).
    """
    n_dias    = df["data"].nunique()
    fat_atual = df["valor_total"].sum()
    fat_proj  = (fat_atual / n_dias * 30) if n_dias > 0 else 0.0
    delta     = fat_proj - fat_atual

    return SimResult(
        titulo="Simulação: Projeção mensal (30 dias)",
        cenario_atual=(
            f"Faturamento observado em {n_dias} dia(s): R$ {fat_atual:,.2f}. "
            f"Média diária: R$ {fat_atual/n_dias:,.2f}."
        ),
        cenario_simulado=(
            f"Extrapolando para 30 dias à mesma taxa diária."
        ),
        impacto_financeiro=round(fat_proj, 2),
        impacto_descricao=(
            f"Projeção mensal: R$ {fat_proj:,.2f}. "
            f"Isso representa R$ {delta:,.2f} além da base atual."
        ),
        premissas=(
            f"Sazonalidade não considerada. "
            f"Base: {n_dias} dia(s) reais. "
            "Use com cautela — 8 dias podem não representar o mês completo."
        ),
    )
