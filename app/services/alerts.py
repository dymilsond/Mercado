from __future__ import annotations

import pandas as pd

from domain.enums import AlertSeverity
from domain.models import Alert

# ---------------------------------------------------------------------------
# Thresholds configuráveis
# ---------------------------------------------------------------------------
_THRESHOLD_CLIENTE_BAIXO_PCT  = 5.0    # % do faturamento total
_THRESHOLD_PIX_BAIXO_PCT      = 15.0   # % das transações
_THRESHOLD_CONCENTRACAO_PROD  = 12.0   # % de um único produto
_MAX_VENDAS_BAIXA_SAIDA       = 1


def _alerta_custo_zerado(df: pd.DataFrame) -> Alert | None:
    pct = df["custo_zerado"].mean() * 100
    if pct > 0:
        return Alert(
            titulo="Custo zerado nos dados",
            mensagem=(
                f"{pct:.0f}% das linhas têm custo = R$ 0,00. "
                "Margem real não pode ser calculada."
            ),
            severity=AlertSeverity.error,
            acao="Preencha os custos dos produtos no sistema de origem.",
        )
    return None


def _alerta_clientes_baixos(df: pd.DataFrame) -> list[Alert]:
    grp = df.groupby("cliente")["valor_total"].sum()
    total = grp.sum()
    if total == 0:
        return []
    alertas = []
    for cliente, fat in grp.items():
        pct = fat / total * 100
        if pct < _THRESHOLD_CLIENTE_BAIXO_PCT:
            alertas.append(
                Alert(
                    titulo=f"Cliente com baixo faturamento: {cliente}",
                    mensagem=f"{cliente} representa apenas {pct:.1f}% do faturamento (R$ {fat:,.2f}).",
                    severity=AlertSeverity.warning,
                    acao="Verificar operação do mercadinho, mix de produtos e disponibilidade.",
                )
            )
    return alertas


def _alerta_pix_baixo(df: pd.DataFrame) -> Alert | None:
    grp = df["metodo_pagamento"].value_counts(normalize=True) * 100
    pix_pct = grp.get("PIX", 0.0)
    if pix_pct < _THRESHOLD_PIX_BAIXO_PCT:
        return Alert(
            titulo="Baixa adesão ao PIX",
            mensagem=f"PIX representa apenas {pix_pct:.1f}% das transações.",
            severity=AlertSeverity.warning,
            acao="Considere oferecer desconto de 2-3% para pagamentos via PIX.",
        )
    return None


def _alerta_concentracao_produto(df: pd.DataFrame) -> list[Alert]:
    total = df["valor_total"].sum()
    if total == 0:
        return []
    grp = df.groupby("produto")["valor_total"].sum()
    alertas = []
    for produto, fat in grp.items():
        pct = fat / total * 100
        if pct >= _THRESHOLD_CONCENTRACAO_PROD:
            alertas.append(
                Alert(
                    titulo=f"Alta concentração: {produto}",
                    mensagem=(
                        f"'{produto}' representa {pct:.1f}% do faturamento total. "
                        "Risco de ruptura de estoque."
                    ),
                    severity=AlertSeverity.warning,
                    acao="Garantir estoque permanente e considerar diversificação.",
                )
            )
    return alertas


def _alerta_baixa_saida(df: pd.DataFrame) -> Alert | None:
    grp = df.groupby("produto")["quantidade"].sum()
    n = int((grp <= _MAX_VENDAS_BAIXA_SAIDA).sum())
    if n > 0:
        return Alert(
            titulo=f"{n} produto(s) com vendas mínimas",
            mensagem=(
                f"{n} produtos foram vendidos {_MAX_VENDAS_BAIXA_SAIDA} vez(es) no período. "
                "Ocupam espaço e capital de giro sem retorno adequado."
            ),
            severity=AlertSeverity.info,
            acao="Revisar mix: remover itens sem giro e substituir por variações de produtos campeões.",
        )
    return None


# ---------------------------------------------------------------------------
# Alertas financeiros (requerem custo_unitario_real)
# ---------------------------------------------------------------------------
_THRESHOLD_MARGEM_UNIDADE_PCT = 10.0   # margem < 10% na unidade → warning
_THRESHOLD_ALTA_VENDA_MARGEM  = 10.0   # margem < 10% em produto de alto giro → warning


def _alerta_produto_prejuizo(df: pd.DataFrame) -> list[Alert]:
    if "lucro" not in df.columns or df["lucro"].notna().sum() == 0:
        return []
    grp = (
        df.dropna(subset=["lucro"])
        .groupby("produto")
        .agg(lucro=("lucro", "sum"), faturamento=("valor_total", "sum"))
        .reset_index()
    )
    alertas = []
    for _, row in grp[grp["lucro"] < 0].iterrows():
        alertas.append(Alert(
            titulo=f"Produto em prejuizo: {row['produto']}",
            mensagem=(
                f"'{row['produto']}' gerou lucro negativo de R$ {row['lucro']:,.2f} "
                f"sobre faturamento de R$ {row['faturamento']:,.2f} no periodo."
            ),
            severity=AlertSeverity.error,
            acao="Revisar precificacao ou renegociar custo com fornecedor.",
        ))
    return alertas


def _alerta_margem_baixa_unidade(df: pd.DataFrame) -> list[Alert]:
    if "lucro" not in df.columns or df["lucro"].notna().sum() == 0:
        return []
    grp = (
        df.dropna(subset=["lucro"])
        .groupby("cliente")
        .agg(lucro=("lucro", "sum"), faturamento=("valor_total", "sum"))
        .reset_index()
    )
    grp["margem"] = grp.apply(
        lambda r: r["lucro"] / r["faturamento"] * 100 if r["faturamento"] > 0 else 0.0,
        axis=1,
    )
    alertas = []
    for _, row in grp[grp["margem"] < _THRESHOLD_MARGEM_UNIDADE_PCT].iterrows():
        alertas.append(Alert(
            titulo=f"Margem critica: {row['cliente']}",
            mensagem=(
                f"'{row['cliente']}' tem margem de {row['margem']:.1f}% "
                f"(lucro R$ {row['lucro']:,.2f} sobre fat. R$ {row['faturamento']:,.2f})."
            ),
            severity=AlertSeverity.warning,
            acao="Revisar mix de produtos e precificacao desta unidade.",
        ))
    return alertas


def _alerta_categoria_margem_negativa(df: pd.DataFrame) -> list[Alert]:
    if "lucro" not in df.columns or df["lucro"].notna().sum() == 0:
        return []
    grp = (
        df.dropna(subset=["lucro"])
        .groupby("categoria")
        .agg(lucro=("lucro", "sum"), faturamento=("valor_total", "sum"))
        .reset_index()
    )
    alertas = []
    for _, row in grp[grp["lucro"] < 0].iterrows():
        alertas.append(Alert(
            titulo=f"Categoria com margem negativa: {row['categoria']}",
            mensagem=(
                f"Categoria '{row['categoria']}' gerou prejuizo de "
                f"R$ {row['lucro']:,.2f} no periodo."
            ),
            severity=AlertSeverity.warning,
            acao="Avaliar se categoria compensa espaco e capital de giro.",
        ))
    return alertas


def _alerta_alta_venda_baixa_margem(df: pd.DataFrame) -> list[Alert]:
    if "lucro" not in df.columns or df["lucro"].notna().sum() == 0:
        return []
    grp = (
        df.dropna(subset=["lucro"])
        .groupby("produto")
        .agg(lucro=("lucro", "sum"), faturamento=("valor_total", "sum"))
        .reset_index()
    )
    if grp.empty:
        return []
    threshold = grp["faturamento"].quantile(0.70)
    grp["margem"] = grp.apply(
        lambda r: r["lucro"] / r["faturamento"] * 100 if r["faturamento"] > 0 else 0.0,
        axis=1,
    )
    alertas = []
    for _, row in grp[(grp["faturamento"] >= threshold) & (grp["margem"] < _THRESHOLD_ALTA_VENDA_MARGEM)].iterrows():
        alertas.append(Alert(
            titulo=f"Alto giro, baixa margem: {row['produto']}",
            mensagem=(
                f"'{row['produto']}' esta no top de faturamento "
                f"(R$ {row['faturamento']:,.2f}) mas com margem de {row['margem']:.1f}%."
            ),
            severity=AlertSeverity.warning,
            acao="Revisar preco de venda ou negociar custo para melhorar margem.",
        ))
    return alertas


# ---------------------------------------------------------------------------
# Alertas de inteligência (padrões e anomalias)
# ---------------------------------------------------------------------------
_QUEDA_SLOPE_PCT = 0.20   # slope < -20% da média diária → queda crítica


def _alerta_anomalia_recente(df: pd.DataFrame) -> Alert | None:
    """Alerta se o dia mais recente da série for anomalias."""
    from services.intelligence import detect_anomalies
    anomalias = detect_anomalies(df)
    if not anomalias:
        return None
    daily_max = df["data"].max()
    ultimas   = [a for a in anomalias if a["data"] == daily_max]
    if not ultimas:
        return None
    a = ultimas[0]
    if a["tipo"] == "queda":
        return Alert(
            titulo="Queda anomala no ultimo dia",
            mensagem=(
                f"Faturamento de {a['data']} foi R$ {a['faturamento']:,.2f} "
                f"(esperado ~R$ {a['esperado']:,.2f}, z={a['zscore']:+.1f}). "
                "Queda fora do padrao historico."
            ),
            severity=AlertSeverity.error,
            acao="Verificar operacao das maquinas e disponibilidade de produtos.",
        )
    return Alert(
        titulo="Pico anomalo no ultimo dia",
        mensagem=(
            f"Faturamento de {a['data']} foi R$ {a['faturamento']:,.2f} "
            f"(esperado ~R$ {a['esperado']:,.2f}, z={a['zscore']:+.1f}). "
            "Pico fora do padrao — verificar se ha evento ou dado incorreto."
        ),
        severity=AlertSeverity.warning,
        acao="Confirmar se o pico corresponde a evento real ou erro de dados.",
    )


def _alerta_queda_tendencia(df: pd.DataFrame) -> Alert | None:
    """Alerta se a tendência de faturamento for de queda significativa."""
    from services.intelligence import get_revenue_trend
    trend = get_revenue_trend(df)
    if trend["direction"] != "caindo":
        return None
    if trend["media_diaria"] == 0:
        return None
    slope_pct = abs(trend["slope_diario"]) / trend["media_diaria"]
    if slope_pct < _QUEDA_SLOPE_PCT:
        return None
    return Alert(
        titulo="Tendencia de queda no faturamento",
        mensagem=(
            f"Faturamento vem caindo ~R$ {abs(trend['slope_diario']):,.2f}/dia "
            f"({trend['pct_variacao']:+.1f}% no periodo de {trend['dias_analisados']} dia(s))."
        ),
        severity=AlertSeverity.warning,
        acao="Investigar causas: mix, disponibilidade de produtos, operacao das maquinas.",
    )


def _alerta_madrugada(df: pd.DataFrame) -> Alert | None:
    madr = df[df["periodo"] == "madrugada"]
    if madr.empty:
        return None
    fat = madr["valor_total"].sum()
    pct = fat / df["valor_total"].sum() * 100 if df["valor_total"].sum() > 0 else 0
    if pct >= 10:
        top_cliente = madr.groupby("cliente")["valor_total"].sum().idxmax()
        return Alert(
            titulo="Vendas relevantes na madrugada",
            mensagem=(
                f"Madrugada (0h-6h) representa {pct:.1f}% do faturamento (R$ {fat:,.2f}). "
                f"Maior cliente nesse horário: {top_cliente}."
            ),
            severity=AlertSeverity.info,
            acao="Garantir abastecimento e funcionamento das máquinas durante a madrugada.",
        )
    return None


# ---------------------------------------------------------------------------
# Agregador principal
# ---------------------------------------------------------------------------
def gerar_alertas(df: pd.DataFrame) -> list[Alert]:
    alertas: list[Alert] = []

    # Dados de origem (custo do Excel)
    a = _alerta_custo_zerado(df)
    if a:
        alertas.append(a)

    # Alertas financeiros (custo real do custos.xlsx)
    alertas.extend(_alerta_produto_prejuizo(df))
    alertas.extend(_alerta_categoria_margem_negativa(df))

    # Operacionais
    a = _alerta_pix_baixo(df)
    if a:
        alertas.append(a)

    alertas.extend(_alerta_clientes_baixos(df))
    alertas.extend(_alerta_concentracao_produto(df))
    alertas.extend(_alerta_margem_baixa_unidade(df))
    alertas.extend(_alerta_alta_venda_baixa_margem(df))

    a = _alerta_baixa_saida(df)
    if a:
        alertas.append(a)

    a = _alerta_madrugada(df)
    if a:
        alertas.append(a)

    # Alertas de inteligência
    a = _alerta_anomalia_recente(df)
    if a:
        alertas.append(a)

    a = _alerta_queda_tendencia(df)
    if a:
        alertas.append(a)

    _order = {AlertSeverity.error: 0, AlertSeverity.warning: 1, AlertSeverity.info: 2}
    alertas.sort(key=lambda x: _order.get(x.severity, 9))
    return alertas
