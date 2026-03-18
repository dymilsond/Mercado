from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Caminhos — busca o xlsx em múltiplos locais possíveis
# ---------------------------------------------------------------------------
_FILENAME   = "Resumo dinamico transacoes.xlsx"
SHEET_NAME  = "Resumo dinamico transacoes"

def _find_excel() -> Path:
    """Localiza o arquivo Excel independente de onde o app é executado."""
    candidates = [
        Path(__file__).resolve().parent.parent.parent / _FILENAME,  # raiz do repo
        Path(__file__).resolve().parent.parent / _FILENAME,          # dentro de app/
        Path.cwd() / _FILENAME,                                       # cwd
        Path.cwd().parent / _FILENAME,                                # um nível acima
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]   # retorna o caminho padrão (vai gerar erro descritivo)

EXCEL_PATH  = _find_excel()
_BASE_DIR   = EXCEL_PATH.parent
_CUSTOS_PATH = Path(__file__).resolve().parent.parent / "data" / "custos.xlsx"

# ---------------------------------------------------------------------------
# Mapeamento de nomes originais → snake_case
# ---------------------------------------------------------------------------
_COLUMN_MAP: dict[str, str] = {
    "Código Produto":      "codigo_produto",
    "Descrição Produto":   "produto",
    "Categoria Produto":   "categoria",
    "Cliente":             "cliente",
    "Método Pagamento":    "metodo_pagamento",
    "Bandeira Cartão":     "bandeira",
    "Data":                "data_raw",
    "Mês":                 "mes_raw",
    "Dia da Semana":       "dia_semana_raw",
    "Hora":                "hora_raw",
    "Quantidade":          "quantidade",
    "Valor Total":         "valor_total",
    # Colunas ignoradas intencionalmente:
    # "Valor Médio"    → descartada (inconsistente)
    # "Custo total"    → mantida apenas para flag
    # "Custo médio"    → descartada
    # "Margem média"   → descartada
    "Custo total":         "custo_total_raw",
}

_COLUNAS_OBRIGATORIAS: list[str] = [
    "Código Produto",
    "Descrição Produto",
    "Categoria Produto",
    "Cliente",
    "Método Pagamento",
    "Data",
    "Hora",
    "Quantidade",
    "Valor Total",
    "Custo total",
]

# ---------------------------------------------------------------------------
# Mapa de período do dia
# ---------------------------------------------------------------------------
def _periodo_do_dia(hora: int) -> str:
    if 0 <= hora <= 5:
        return "madrugada"
    if 6 <= hora <= 11:
        return "manha"
    if 12 <= hora <= 17:
        return "tarde"
    return "noite"


# ---------------------------------------------------------------------------
# Parser da coluna Hora  ("19:00 - 19:59"  →  19)
# ---------------------------------------------------------------------------
def _parse_hora(valor: object) -> int | None:
    if pd.isna(valor):
        return None
    s = str(valor).strip()
    match = re.match(r"^(\d{1,2})\s*:", s)
    if match:
        return int(match.group(1))
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Validação das colunas obrigatórias
# ---------------------------------------------------------------------------
def _validar_colunas(df: pd.DataFrame) -> None:
    faltando = [c for c in _COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltando:
        raise ValueError(
            f"Colunas obrigatórias ausentes no Excel: {faltando}\n"
            f"Colunas encontradas: {df.columns.tolist()}"
        )


# ---------------------------------------------------------------------------
# Transformações principais
# ---------------------------------------------------------------------------
def _transformar(df: pd.DataFrame) -> pd.DataFrame:
    # 1. Renomear apenas as colunas mapeadas; descartar as demais
    df = df.rename(columns=_COLUMN_MAP)
    colunas_uteis = list(_COLUMN_MAP.values())
    df = df[[c for c in colunas_uteis if c in df.columns]].copy()

    # 2. Tipagem básica
    df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce").fillna(0).astype(int)
    df["valor_total"] = pd.to_numeric(df["valor_total"], errors="coerce").fillna(0.0).astype(float)
    df["custo_total_raw"] = pd.to_numeric(df["custo_total_raw"], errors="coerce").fillna(0.0).astype(float)

    # 3. Hora como inteiro
    df["hora"] = df["hora_raw"].apply(_parse_hora)
    df["hora"] = df["hora"].fillna(0).astype(int)

    # 4. Data como datetime.date
    df["data"] = pd.to_datetime(df["data_raw"], errors="coerce").dt.date

    # 5. datetime unificado (Data + Hora)
    df["datetime"] = pd.to_datetime(df["data_raw"], errors="coerce") + pd.to_timedelta(df["hora"], unit="h")

    # 6. dia_semana e mes normalizados
    df["dia_semana"] = df["dia_semana_raw"].astype(str).str.strip().str.lower()
    df["mes"] = df["mes_raw"].astype(str).str.strip().str.lower()

    # 7. Período do dia
    df["periodo"] = df["hora"].apply(_periodo_do_dia)

    # 8. Valor unitário recalculado (evita divisão por zero)
    df["valor_unitario"] = df.apply(
        lambda r: r["valor_total"] / r["quantidade"] if r["quantidade"] > 0 else 0.0,
        axis=1,
    ).round(2)

    # 9. Ticket médio por item (alias semântico — mesmo cálculo)
    df["ticket_medio_item"] = df["valor_unitario"]

    # 10. Flags de custo
    df["tem_custo"] = df["custo_total_raw"] > 0
    df["custo_zerado"] = df["custo_total_raw"] == 0

    # 11. Limpeza de colunas auxiliares
    df = df.drop(columns=["hora_raw", "data_raw", "mes_raw", "dia_semana_raw", "custo_total_raw"])

    # 12. Garantir strings limpas
    for col in ["produto", "categoria", "cliente", "metodo_pagamento", "bandeira"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].replace("nan", "Não informado")

    # 13. Remover linhas sem data válida
    df = df.dropna(subset=["data"])

    # 14. Reset index
    df = df.reset_index(drop=True)

    return df


# ---------------------------------------------------------------------------
# Carregamento de custos (data/custos.xlsx)
# ---------------------------------------------------------------------------
def load_costs() -> pd.DataFrame:
    """
    Carrega arquivo de custos unitarios reais.
    Retorna DataFrame vazio se arquivo nao existir ou estiver invalido.
    Colunas esperadas: produto_id | custo_unitario
    """
    if not _CUSTOS_PATH.exists():
        return pd.DataFrame(columns=["produto_id", "custo_unitario"])
    try:
        df = pd.read_excel(_CUSTOS_PATH)
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        if "produto_id" not in df.columns or "custo_unitario" not in df.columns:
            return pd.DataFrame(columns=["produto_id", "custo_unitario"])
        df["produto_id"]     = df["produto_id"].astype(str).str.strip()
        df["custo_unitario"] = pd.to_numeric(df["custo_unitario"], errors="coerce")
        return df[["produto_id", "custo_unitario"]].dropna().reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["produto_id", "custo_unitario"])


# ---------------------------------------------------------------------------
# Merge de custos reais no DataFrame de vendas
# ---------------------------------------------------------------------------
def _merge_custos(df: pd.DataFrame, custos: pd.DataFrame) -> pd.DataFrame:
    """
    Faz LEFT JOIN do df de vendas com o df de custos via codigo_produto.
    Adiciona colunas: custo_unitario_real, custo_total_real, lucro, margem_percentual.
    Linhas sem correspondencia ficam com NaN nessas colunas.
    NÃO usa custo_zerado/tem_custo do Excel original — sao sinais diferentes.
    """
    # Inicializa colunas como NaN
    df["custo_unitario_real"] = float("nan")
    df["custo_total_real"]    = float("nan")
    df["lucro"]               = float("nan")
    df["margem_percentual"]   = float("nan")

    if custos.empty:
        return df

    # Chave de merge: codigo_produto (string normalizada)
    chave_vendas = df["codigo_produto"].astype(str).str.strip()
    custo_map    = custos.set_index("produto_id")["custo_unitario"]

    df["custo_unitario_real"] = chave_vendas.map(custo_map)

    mask = df["custo_unitario_real"].notna()
    if mask.any():
        df.loc[mask, "custo_total_real"] = (
            df.loc[mask, "custo_unitario_real"] * df.loc[mask, "quantidade"]
        )
        df.loc[mask, "lucro"] = (
            df.loc[mask, "valor_total"] - df.loc[mask, "custo_total_real"]
        )
        fat_mask = mask & (df["valor_total"] > 0)
        df.loc[fat_mask, "margem_percentual"] = (
            df.loc[fat_mask, "lucro"] / df.loc[fat_mask, "valor_total"] * 100
        ).round(1)

    return df


# ---------------------------------------------------------------------------
# Ponto de entrada principal — com cache do Streamlit
# ---------------------------------------------------------------------------
def _file_mtime() -> float:
    """Retorna o timestamp de modificação do Excel — usado como cache-buster."""
    try:
        return EXCEL_PATH.stat().st_mtime
    except OSError:
        return 0.0


@st.cache_data(ttl=60, show_spinner="Carregando dados...")
def load_data(_mtime: float = 0.0) -> pd.DataFrame:
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(
            f"Arquivo Excel não encontrado: {EXCEL_PATH}\n"
            "Verifique se o arquivo está na raiz do projeto."
        )

    raw = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME)
    _validar_colunas(raw)
    df  = _transformar(raw)
    df  = _merge_custos(df, load_costs())
    return df


def load_data_fresh() -> pd.DataFrame:
    """Chama load_data com o mtime atual — força reload quando arquivo mudar."""
    return load_data(_mtime=_file_mtime())


# ---------------------------------------------------------------------------
# Utilitários de acesso rápido (sem cache próprio — dependem do load_data)
# ---------------------------------------------------------------------------
def get_clientes(df: pd.DataFrame) -> list[str]:
    return sorted(df["cliente"].dropna().unique().tolist())


def get_categorias(df: pd.DataFrame) -> list[str]:
    return sorted(df["categoria"].dropna().unique().tolist())


def get_produtos(df: pd.DataFrame) -> list[str]:
    return sorted(df["produto"].dropna().unique().tolist())


def get_metodos_pagamento(df: pd.DataFrame) -> list[str]:
    return sorted(df["metodo_pagamento"].dropna().unique().tolist())


def get_periodos(df: pd.DataFrame) -> list[str]:
    ordem = ["madrugada", "manha", "tarde", "noite"]
    presentes = df["periodo"].unique().tolist()
    return [p for p in ordem if p in presentes]


def get_dias_semana(df: pd.DataFrame) -> list[str]:
    ordem = [
        "segunda-feira", "terca-feira", "quarta-feira",
        "quinta-feira", "sexta-feira", "sabado", "domingo",
    ]
    presentes = df["dia_semana"].unique().tolist()
    return [d for d in ordem if d in presentes] + [
        d for d in presentes if d not in ordem
    ]


def get_date_range(df: pd.DataFrame) -> tuple:
    return df["data"].min(), df["data"].max()


def schema_info(df: pd.DataFrame) -> dict:
    """Retorna metadados do DataFrame carregado — útil para debug/admin."""
    return {
        "total_linhas": len(df),
        "colunas": df.columns.tolist(),
        "data_inicio": str(df["data"].min()),
        "data_fim": str(df["data"].max()),
        "clientes": df["cliente"].nunique(),
        "produtos": df["produto"].nunique(),
        "categorias": df["categoria"].nunique(),
        "custo_zerado_pct": round(df["custo_zerado"].mean() * 100, 1),
    }
