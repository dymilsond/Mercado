from __future__ import annotations

import datetime
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pytest
from tests.conftest import *  # noqa: F401,F403

from services.filters import apply_filters


class TestFiltros:
    def test_sem_filtros_retorna_tudo(self, df_base):
        df_f = apply_filters(df_base)
        assert len(df_f) == len(df_base)

    def test_filtro_cliente(self, df_base):
        df_f = apply_filters(df_base, clientes=["ClienteA"])
        assert set(df_f["cliente"].unique()) == {"ClienteA"}

    def test_filtro_categoria(self, df_base):
        df_f = apply_filters(df_base, categorias=["vinhos"])
        assert set(df_f["categoria"].unique()) == {"vinhos"}

    def test_filtro_metodo_pagamento(self, df_base):
        df_f = apply_filters(df_base, metodos_pagamento=["PIX"])
        assert set(df_f["metodo_pagamento"].unique()) == {"PIX"}

    def test_filtro_periodo(self, df_base):
        df_f = apply_filters(df_base, periodos=["manha"])
        assert set(df_f["periodo"].unique()) == {"manha"}

    def test_filtro_dia_semana(self, df_base):
        df_f = apply_filters(df_base, dias_semana=["segunda-feira"])
        assert set(df_f["dia_semana"].unique()) == {"segunda-feira"}

    def test_filtro_data_inicio(self, df_base):
        d = datetime.date(2025, 12, 2)
        df_f = apply_filters(df_base, data_inicio=d)
        assert all(row >= d for row in df_f["data"])

    def test_filtro_data_fim(self, df_base):
        d = datetime.date(2025, 12, 1)
        df_f = apply_filters(df_base, data_fim=d)
        assert all(row <= d for row in df_f["data"])

    def test_filtros_combinados(self, df_base):
        df_f = apply_filters(
            df_base,
            clientes=["ClienteA"],
            periodos=["manha"],
        )
        assert set(df_f["cliente"].unique()) == {"ClienteA"}
        assert set(df_f["periodo"].unique()) == {"manha"}

    def test_filtro_cliente_inexistente_retorna_vazio(self, df_base):
        df_f = apply_filters(df_base, clientes=["NaoExiste"])
        assert df_f.empty

    def test_filtro_produto(self, df_base):
        df_f = apply_filters(df_base, produtos=["Heineken"])
        assert list(df_f["produto"]) == ["Heineken"]

    def test_filtros_none_nao_quebram(self, df_base):
        df_f = apply_filters(
            df_base,
            data_inicio=None,
            data_fim=None,
            clientes=None,
            categorias=None,
            produtos=None,
            metodos_pagamento=None,
            periodos=None,
            dias_semana=None,
        )
        assert len(df_f) == len(df_base)
