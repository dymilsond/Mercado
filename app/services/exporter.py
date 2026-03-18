from __future__ import annotations

import io
from datetime import datetime

import pandas as pd


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------
def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M")


def _colunas_exportaveis(df: pd.DataFrame) -> pd.DataFrame:
    """Seleciona e renomeia colunas para exportação amigável."""
    mapa = {
        "codigo_produto":   "Código",
        "produto":          "Produto",
        "categoria":        "Categoria",
        "cliente":          "Cliente",
        "metodo_pagamento": "Método Pagamento",
        "bandeira":         "Bandeira",
        "data":             "Data",
        "dia_semana":       "Dia Semana",
        "hora":             "Hora",
        "periodo":          "Período",
        "quantidade":       "Quantidade",
        "valor_total":      "Valor Total (R$)",
        "valor_unitario":   "Valor Unitário (R$)",
    }
    colunas_presentes = [c for c in mapa if c in df.columns]
    return df[colunas_presentes].rename(columns=mapa)


# ---------------------------------------------------------------------------
# Exportação CSV
# ---------------------------------------------------------------------------
def export_filtered_csv(df: pd.DataFrame) -> bytes:
    """Retorna CSV em bytes dos dados filtrados."""
    df_exp = _colunas_exportaveis(df)
    return df_exp.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")


def csv_filename(prefix: str = "mercadinhos_dados") -> str:
    return f"{prefix}_{_timestamp()}.csv"


# ---------------------------------------------------------------------------
# Exportação Excel
# ---------------------------------------------------------------------------
def export_filtered_excel(df: pd.DataFrame) -> bytes:
    """Retorna Excel (xlsx) em memória dos dados filtrados."""
    df_exp = _colunas_exportaveis(df)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_exp.to_excel(writer, index=False, sheet_name="Dados Filtrados")

        # Formatação básica
        ws = writer.sheets["Dados Filtrados"]
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)

    return buffer.getvalue()


def excel_filename(prefix: str = "mercadinhos_dados") -> str:
    return f"{prefix}_{_timestamp()}.xlsx"


# ---------------------------------------------------------------------------
# Exportação Resumo Executivo TXT
# ---------------------------------------------------------------------------
def export_executive_summary_text(summary_data: dict) -> bytes:
    """
    Gera relatório textual do resumo executivo.

    summary_data esperado:
    {
        "periodo": str,
        "n_dias": int,
        "faturamento": float,
        "ticket_medio": float,
        "n_clientes": int,
        "n_transacoes": int,
        "n_produtos": int,
        "alertas": list[str],
        "recomendacoes": list[str],
        "projecao_mensal": float,
        "economia_pix": float,
    }
    """
    linhas = [
        "=" * 60,
        "  RESUMO EXECUTIVO - MERCADINHOS ANALYTICS",
        f"  Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "=" * 60,
        "",
        ">> PERIODO ANALISADO",
        f"  {summary_data.get('periodo', 'N/A')}",
        f"  Base: {summary_data.get('n_dias', 0)} dia(s)",
        "",
        ">> KPIs DO PERIODO",
        f"  Faturamento Total : R$ {summary_data.get('faturamento', 0):>12,.2f}",
        f"  Ticket Medio      : R$ {summary_data.get('ticket_medio', 0):>12,.2f}",
        f"  Num Clientes      : {summary_data.get('n_clientes', 0):>14}",
        f"  Num Transacoes    : {summary_data.get('n_transacoes', 0):>14,}",
        f"  Num Produtos      : {summary_data.get('n_produtos', 0):>14}",
        "",
    ]

    alertas = summary_data.get("alertas", [])
    if alertas:
        linhas += [">> ALERTAS ATIVOS", ""]
        for i, a in enumerate(alertas, 1):
            linhas.append(f"  {i}. {a}")
        linhas.append("")

    recs = summary_data.get("recomendacoes", [])
    if recs:
        linhas += [">> RECOMENDACOES PRIORITARIAS", ""]
        for i, r in enumerate(recs, 1):
            linhas.append(f"  {i}. {r}")
        linhas.append("")

    proj = summary_data.get("projecao_mensal", 0)
    eco  = summary_data.get("economia_pix", 0)
    linhas += [
        ">> IMPACTO POTENCIAL",
        f"  Projecao mensal (30 dias) : R$ {proj:>10,.2f}",
        f"  Economia estimada PIX     : R$ {eco:>10,.2f}",
        "",
        "=" * 60,
        "  Sistema DSS - Mercadinhos Analytics",
        "=" * 60,
    ]

    texto = "\n".join(linhas)
    return texto.encode("utf-8")


def summary_txt_filename() -> str:
    return f"resumo_executivo_{_timestamp()}.txt"
