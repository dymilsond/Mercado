from __future__ import annotations

import pandas as pd

from domain.enums import Priority, RecommendationType
from domain.models import Recommendation

_PRIORITY_ORDER = {Priority.alta: 0, Priority.media: 1, Priority.baixa: 2}

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
_PIX_THRESHOLD_PCT        = 10.0
_CONCENTRACAO_PROD_PCT    = 50.0
_CLIENTE_FRACO_FATOR      = 0.30
_MADRUGADA_THRESHOLD_PCT  = 10.0
_MAX_VENDAS_BAIXA_SAIDA   = 1
_CATEGORIAS_VOLUME_BAIXO  = {"vinhos", "vinho"}


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------
def _base_dias(df: pd.DataFrame) -> int:
    return df["data"].nunique()


def _base_label(df: pd.DataFrame) -> str:
    return f"Base analisada: {_base_dias(df)} dia(s)."


# ---------------------------------------------------------------------------
# Regras individuais
# ---------------------------------------------------------------------------
def _rec_custo_zerado(df: pd.DataFrame) -> Recommendation | None:
    pct = df["custo_zerado"].mean() * 100
    if pct < 100:
        return None
    return Recommendation(
        tipo=RecommendationType.custo,
        prioridade=Priority.alta,
        titulo="Cadastro de custos ausente",
        descricao=(
            "100% das transações têm custo = R$ 0,00. "
            "Análises de margem, lucratividade e ROI estão bloqueadas. "
            f"{_base_label(df)}"
        ),
        impacto_estimado=(
            "Sem custo preenchido é impossível saber se o negócio é lucrativo. "
            "Risco de decisão baseada apenas em faturamento."
        ),
    )


def _rec_pix_baixo(df: pd.DataFrame) -> Recommendation | None:
    grp = df["metodo_pagamento"].value_counts(normalize=True) * 100
    pix_pct = grp.get("PIX", 0.0)
    if pix_pct >= _PIX_THRESHOLD_PCT:
        return None
    total_fat = df["valor_total"].sum()
    economia_estimada = total_fat * 0.025
    return Recommendation(
        tipo=RecommendationType.pagamento,
        prioridade=Priority.alta,
        titulo=f"PIX subutilizado ({pix_pct:.1f}% das transações)",
        descricao=(
            f"PIX representa apenas {pix_pct:.1f}% das transações. "
            "Cartão de crédito/débito gera taxas de 1,5% a 3,5% por venda. "
            "Ação: oferecer desconto de 2% a 3% para pagamentos via PIX. "
            f"{_base_label(df)}"
        ),
        impacto_estimado=(
            f"Potencial economia estimada de R$ {economia_estimada:,.2f} "
            "se 20% das transações migrarem para PIX."
        ),
    )


_ALTA_MARGEM_EXCLUIR_PCT = 30.0  # produtos com margem >= 30% nao sao candidatos a remocao


def _rec_produtos_baixa_saida(df: pd.DataFrame) -> Recommendation | None:
    grp = (
        df.groupby(["produto", "categoria"])
        .agg(itens=("quantidade", "sum"), fat=("valor_total", "sum"))
        .reset_index()
    )
    baixos = grp[
        (grp["itens"] <= _MAX_VENDAS_BAIXA_SAIDA) &
        (~grp["categoria"].str.lower().isin(_CATEGORIAS_VOLUME_BAIXO))
    ]
    # Nao recomendar remocao de produtos com alta margem real
    if "margem_percentual" in df.columns and df["margem_percentual"].notna().any():
        margem_media_prod = (
            df.dropna(subset=["margem_percentual"])
            .groupby("produto")["margem_percentual"]
            .mean()
        )
        alta_margem = set(margem_media_prod[margem_media_prod >= _ALTA_MARGEM_EXCLUIR_PCT].index)
        baixos = baixos[~baixos["produto"].isin(alta_margem)]

    n = len(baixos)
    if n == 0:
        return None
    fat_bloqueado = baixos["fat"].sum()
    return Recommendation(
        tipo=RecommendationType.mix,
        prioridade=Priority.media,
        titulo=f"{n} produto(s) com venda minima (exceto vinhos e alta margem)",
        descricao=(
            f"{n} produtos (fora de categorias de baixo giro natural e sem alta margem) "
            f"foram vendidos apenas {_MAX_VENDAS_BAIXA_SAIDA} vez(es). "
            "Acao: revisar mix — reposicionar, substituir ou remover. "
            "Vinhos e produtos com margem >= 30% foram excluidos desta analise. "
            f"{_base_label(df)}"
        ),
        impacto_estimado=(
            f"Esses {n} produtos geraram R$ {fat_bloqueado:,.2f}. "
            "Substitui-los por variacoes dos top-3 pode ampliar faturamento."
        ),
    )


def _rec_clientes_fracos(df: pd.DataFrame) -> list[Recommendation]:
    grp = df.groupby("cliente")["valor_total"].sum()
    if len(grp) < 2:
        return []
    media = grp.mean()
    threshold = media * _CLIENTE_FRACO_FATOR
    recs = []
    for cliente, fat in grp.items():
        if fat < threshold:
            recs.append(
                Recommendation(
                    tipo=RecommendationType.cliente,
                    prioridade=Priority.alta,
                    titulo=f"Cliente crítico: {cliente}",
                    descricao=(
                        f"{cliente} gerou R$ {fat:,.2f}, "
                        f"equivalente a {fat/grp.sum()*100:.1f}% do faturamento. "
                        f"A média do grupo é R$ {media:,.2f}. "
                        "Ação: investigar fluxo de pessoas, operação da máquina, "
                        "mix de produtos e visibilidade no local. "
                        f"{_base_label(df)}"
                    ),
                    impacto_estimado=(
                        f"Elevar {cliente} à média do grupo representaria "
                        f"R$ {media - fat:,.2f} adicionais no período."
                    ),
                )
            )
    return recs


def _rec_concentracao_produto_categoria(df: pd.DataFrame) -> list[Recommendation]:
    total_cat = df.groupby("categoria")["valor_total"].sum()
    prod_cat  = df.groupby(["categoria", "produto"])["valor_total"].sum().reset_index()
    recs = []
    for _, row in prod_cat.iterrows():
        cat_total = total_cat.get(row["categoria"], 0)
        if cat_total == 0:
            continue
        pct = row["valor_total"] / cat_total * 100
        if pct >= _CONCENTRACAO_PROD_PCT:
            recs.append(
                Recommendation(
                    tipo=RecommendationType.concentracao,
                    prioridade=Priority.alta,
                    titulo=f"Concentração: '{row['produto']}' ({pct:.0f}% de {row['categoria']})",
                    descricao=(
                        f"'{row['produto']}' representa {pct:.1f}% de todo o faturamento "
                        f"da categoria '{row['categoria']}'. "
                        "Alta dependência de um único SKU expõe a risco de ruptura. "
                        "Ação: ampliar portfólio com 2 a 3 produtos complementares. "
                        f"{_base_label(df)}"
                    ),
                    impacto_estimado=(
                        "Uma ruptura de estoque desse produto pode eliminar "
                        f"até {pct:.0f}% do faturamento da categoria temporariamente."
                    ),
                )
            )
    return recs


def _rec_madrugada(df: pd.DataFrame) -> Recommendation | None:
    madr = df[df["periodo"] == "madrugada"]
    if madr.empty:
        return None
    fat_total = df["valor_total"].sum()
    fat_madr  = madr["valor_total"].sum()
    pct       = fat_madr / fat_total * 100 if fat_total > 0 else 0
    if pct < _MADRUGADA_THRESHOLD_PCT:
        return None
    top_produto = madr.groupby("produto")["valor_total"].sum().idxmax()
    return Recommendation(
        tipo=RecommendationType.operacional,
        prioridade=Priority.media,
        titulo=f"Madrugada representa {pct:.1f}% do faturamento",
        descricao=(
            f"Vendas entre 0h e 6h geraram R$ {fat_madr:,.2f} ({pct:.1f}% do total). "
            f"Produto mais vendido na madrugada: '{top_produto}'. "
            "Ação: garantir abastecimento noturno e funcionamento das máquinas 24h. "
            f"{_base_label(df)}"
        ),
        impacto_estimado=(
            f"Falha operacional na madrugada pode causar perda de "
            f"R$ {fat_madr:,.2f} por período similar."
        ),
    )


def _rec_alta_venda_baixa_margem(df: pd.DataFrame) -> list[Recommendation]:
    """Produtos no top 30% de faturamento com margem < 10% — revisar preco."""
    from services.finance import get_high_sale_low_margin
    criticos = get_high_sale_low_margin(df)
    if criticos.empty:
        return []
    recs = []
    for _, row in criticos.iterrows():
        recs.append(Recommendation(
            tipo=RecommendationType.ticket,
            prioridade=Priority.alta,
            titulo=f"Revisar preco: '{row['produto']}' (alta venda, margem {row['margem_pct']:.1f}%)",
            descricao=(
                f"'{row['produto']}' e um dos mais vendidos "
                f"(fat. R$ {row['faturamento']:,.2f}) mas tem margem de {row['margem_pct']:.1f}%. "
                "Acao: revisar preco de venda ou renegociar custo com fornecedor. "
                f"{_base_label(df)}"
            ),
            impacto_estimado=(
                f"Elevar margem de '{row['produto']}' para 20% geraria "
                f"R$ {row['faturamento'] * 0.10:,.2f} adicionais de lucro no periodo."
            ),
        ))
    return recs


def _rec_alta_margem_baixo_volume(df: pd.DataFrame) -> list[Recommendation]:
    """Produtos com alta margem e baixo volume — candidatos a promocao."""
    from services.finance import get_high_margin_low_volume
    candidatos = get_high_margin_low_volume(df)
    if candidatos.empty:
        return []
    recs = []
    for _, row in candidatos.iterrows():
        recs.append(Recommendation(
            tipo=RecommendationType.mix,
            prioridade=Priority.media,
            titulo=f"Promover: '{row['produto']}' (margem {row['margem_pct']:.1f}%, volume baixo)",
            descricao=(
                f"'{row['produto']}' tem margem excelente de {row['margem_pct']:.1f}% "
                f"mas faturamento baixo (R$ {row['faturamento']:,.2f}). "
                "Acao: destacar no ponto de venda e incluir em combos. "
                f"{_base_label(df)}"
            ),
            impacto_estimado=(
                f"Dobrar o volume de '{row['produto']}' adicionaria "
                f"R$ {max(row['lucro'], 0.0):,.2f} de lucro adicional no periodo."
            ),
        ))
    return recs


def _rec_ticket_medio_baixo(df: pd.DataFrame) -> Recommendation | None:
    n = len(df)
    if n == 0:
        return None
    ticket = df["valor_total"].sum() / n
    if ticket >= 10.0:
        return None
    return Recommendation(
        tipo=RecommendationType.ticket,
        prioridade=Priority.media,
        titulo=f"Ticket médio baixo (R$ {ticket:.2f})",
        descricao=(
            f"O ticket médio por transação é R$ {ticket:.2f}. "
            "Isso indica vendas de itens unitários sem complementar a cesta. "
            "Ação: criar combos ou reposicionar produtos premium. "
            f"{_base_label(df)}"
        ),
        impacto_estimado=(
            "Aumentar o ticket médio em R$ 2,00 por transação geraria "
            f"R$ {n * 2:,.2f} adicionais no período."
        ),
    )


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------
def generate_recommendations(
    df: pd.DataFrame,
    metrics: dict,
    alerts: list,
) -> list[Recommendation]:
    recs: list[Recommendation] = []

    r = _rec_custo_zerado(df)
    if r:
        recs.append(r)

    r = _rec_pix_baixo(df)
    if r:
        recs.append(r)

    recs.extend(_rec_clientes_fracos(df))
    recs.extend(_rec_concentracao_produto_categoria(df))

    r = _rec_produtos_baixa_saida(df)
    if r:
        recs.append(r)

    r = _rec_madrugada(df)
    if r:
        recs.append(r)

    r = _rec_ticket_medio_baixo(df)
    if r:
        recs.append(r)

    # Recomendacoes baseadas em custo real (so aparecem se houver dados financeiros)
    recs.extend(_rec_alta_venda_baixa_margem(df))
    recs.extend(_rec_alta_margem_baixo_volume(df))

    recs.sort(key=lambda x: _PRIORITY_ORDER.get(x.prioridade, 9))
    return recs
