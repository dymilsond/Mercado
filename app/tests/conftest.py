from __future__ import annotations

import datetime

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# DataFrame base — simula o output do data_loader (sem custo real cadastrado)
# ---------------------------------------------------------------------------
@pytest.fixture
def df_base() -> pd.DataFrame:
    hoje   = datetime.date(2025, 12, 1)
    amanha = datetime.date(2025, 12, 2)
    return pd.DataFrame(
        {
            "codigo_produto":    ["P001", "P002", "P003", "P004", "P005", "P006"],
            "produto":           ["Heineken", "Skol", "Cabernet", "Doritos", "Água", "Chips"],
            "categoria":         ["Cervejas", "Cervejas", "vinhos", "Salgadinhos", "Bebidas", "Salgadinhos"],
            "cliente":           ["ClienteA", "ClienteA", "ClienteB", "ClienteB", "ClienteA", "ClienteC"],
            "metodo_pagamento":  ["Cartão", "Cartão", "PIX", "Cartão", "Cartão", "Cartão"],
            "bandeira":          ["Visa", "Visa", None, "Master", "Visa", "Master"],
            "quantidade":        [10, 1, 1, 5, 20, 1],
            "valor_total":       [100.0, 20.0, 50.0, 40.0, 60.0, 10.0],
            "hora":              [10, 2, 14, 20, 10, 15],
            "data":              [hoje, hoje, amanha, amanha, hoje, amanha],
            "datetime":          [
                datetime.datetime(2025, 12, 1, 10),
                datetime.datetime(2025, 12, 1, 2),
                datetime.datetime(2025, 12, 2, 14),
                datetime.datetime(2025, 12, 2, 20),
                datetime.datetime(2025, 12, 1, 10),
                datetime.datetime(2025, 12, 2, 15),
            ],
            "dia_semana":        ["segunda-feira", "segunda-feira", "terca-feira",
                                  "terca-feira", "segunda-feira", "terca-feira"],
            "mes":               ["dezembro"] * 6,
            "periodo":           ["manha", "madrugada", "tarde", "noite", "manha", "tarde"],
            "valor_unitario":    [10.0, 20.0, 50.0, 8.0, 3.0, 10.0],
            "ticket_medio_item": [10.0, 20.0, 50.0, 8.0, 3.0, 10.0],
            "tem_custo":         [False] * 6,
            "custo_zerado":      [True]  * 6,
            # Colunas financeiras — NaN porque custos.xlsx nao tem esses produtos
            "custo_unitario_real": [float("nan")] * 6,
            "custo_total_real":    [float("nan")] * 6,
            "lucro":               [float("nan")] * 6,
            "margem_percentual":   [float("nan")] * 6,
        }
    )


@pytest.fixture
def df_com_pix(df_base) -> pd.DataFrame:
    df = df_base.copy()
    df.loc[1, "metodo_pagamento"] = "PIX"
    df.loc[3, "metodo_pagamento"] = "PIX"
    df.loc[5, "metodo_pagamento"] = "PIX"
    return df


@pytest.fixture
def df_sem_custo_zerado(df_base) -> pd.DataFrame:
    df = df_base.copy()
    df["tem_custo"]    = True
    df["custo_zerado"] = False
    return df


# ---------------------------------------------------------------------------
# Fixtures financeiras — com custo real parcialmente preenchido
# ---------------------------------------------------------------------------
def _calcular_colunas_financeiras(df: pd.DataFrame) -> pd.DataFrame:
    """Recalcula custo_total_real, lucro e margem_percentual a partir de custo_unitario_real."""
    df = df.copy()
    df["custo_total_real"]  = float("nan")
    df["lucro"]             = float("nan")
    df["margem_percentual"] = float("nan")

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


@pytest.fixture
def df_com_custo_real(df_base) -> pd.DataFrame:
    """
    Cobertura parcial (5/6 = ~83%).
    Heineken  P001: custo=6.0  → 10un*6=60, fat=100, lucro=40, margem=40%
    Skol      P002: custo=14.0 → 1un*14=14, fat=20, lucro=6, margem=30%
    Cabernet  P003: custo=60.0 → 1un*60=60, fat=50, lucro=-10, margem=-20% (prejuizo)
    Doritos   P004: custo=3.0  → 5un*3=15,  fat=40, lucro=25, margem=62.5%
    Agua      P005: sem custo  → NaN
    Chips     P006: custo=7.0  → 1un*7=7,   fat=10, lucro=3, margem=30%
    """
    custos = {"P001": 6.0, "P002": 14.0, "P003": 60.0, "P004": 3.0, "P006": 7.0}
    df = df_base.copy()
    df["custo_unitario_real"] = df["codigo_produto"].map(custos)
    return _calcular_colunas_financeiras(df)


@pytest.fixture
def df_com_custo_real_completo(df_base) -> pd.DataFrame:
    """
    Cobertura total (6/6 = 100%).
    Adiciona custo para Agua (P005).
    """
    custos = {"P001": 6.0, "P002": 14.0, "P003": 60.0, "P004": 3.0, "P005": 1.5, "P006": 7.0}
    df = df_base.copy()
    df["custo_unitario_real"] = df["codigo_produto"].map(custos)
    return _calcular_colunas_financeiras(df)
