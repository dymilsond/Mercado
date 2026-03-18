from __future__ import annotations

import datetime

import pandas as pd


def apply_filters(
    df: pd.DataFrame,
    data_inicio: datetime.date | None = None,
    data_fim: datetime.date | None = None,
    clientes: list[str] | None = None,
    categorias: list[str] | None = None,
    produtos: list[str] | None = None,
    metodos_pagamento: list[str] | None = None,
    periodos: list[str] | None = None,
    dias_semana: list[str] | None = None,
) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)

    if data_inicio:
        mask &= df["data"] >= data_inicio
    if data_fim:
        mask &= df["data"] <= data_fim
    if clientes:
        mask &= df["cliente"].isin(clientes)
    if categorias:
        mask &= df["categoria"].isin(categorias)
    if produtos:
        mask &= df["produto"].isin(produtos)
    if metodos_pagamento:
        mask &= df["metodo_pagamento"].isin(metodos_pagamento)
    if periodos:
        mask &= df["periodo"].isin(periodos)
    if dias_semana:
        mask &= df["dia_semana"].isin(dias_semana)

    return df[mask].copy()
