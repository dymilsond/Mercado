from __future__ import annotations

import datetime
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest
from tests.conftest import *  # noqa: F401,F403

from domain.enums import AlertSeverity
from services.alerts import gerar_alertas, _alerta_custo_zerado, _alerta_pix_baixo, _alerta_madrugada


class TestAlertaCustoZerado:
    def test_dispara_quando_100_pct_zerado(self, df_base):
        a = _alerta_custo_zerado(df_base)
        assert a is not None
        assert a.severity == AlertSeverity.error

    def test_nao_dispara_quando_ha_custo(self, df_sem_custo_zerado):
        a = _alerta_custo_zerado(df_sem_custo_zerado)
        assert a is None


class TestAlertaPix:
    def test_dispara_pix_baixo(self, df_base):
        # df_base tem apenas 1 transação PIX de 6 (~16.7% > threshold de 15%)
        # Mas exatamente na fronteira. Vamos garantir um df sem PIX
        df = df_base.copy()
        df["metodo_pagamento"] = "Cartão"
        a = _alerta_pix_baixo(df)
        assert a is not None
        assert a.severity == AlertSeverity.warning

    def test_nao_dispara_com_pix_suficiente(self, df_com_pix):
        a = _alerta_pix_baixo(df_com_pix)
        # df_com_pix tem 3 de 6 transações em PIX = 50% → não dispara
        assert a is None


class TestAlertaMadrugada:
    def test_dispara_madrugada_relevante(self, df_base):
        # df_base tem Skol vendido às 2h (madrugada) com valor 20 de 280 = ~7%
        # Abaixo do threshold de 10%. Vamos criar um df com madrugada > 10%
        import datetime
        df = df_base.copy()
        # Forçar valores altos na madrugada
        df.loc[df["periodo"] == "madrugada", "valor_total"] = 100.0
        a = _alerta_madrugada(df)
        assert a is not None

    def test_nao_dispara_madrugada_irrelevante(self):
        df = pd.DataFrame({
            "periodo":     ["manha", "tarde"],
            "valor_total": [200.0, 100.0],
            "cliente":     ["A", "B"],
            "produto":     ["X", "Y"],
        })
        a = _alerta_madrugada(df)
        assert a is None


class TestGerarAlertas:
    def test_retorna_lista(self, df_base):
        alertas = gerar_alertas(df_base)
        assert isinstance(alertas, list)

    def test_ordenacao_error_antes_warning(self, df_base):
        alertas = gerar_alertas(df_base)
        severidades = [a.severity for a in alertas]
        # error deve vir antes de warning e info
        if AlertSeverity.error in severidades and AlertSeverity.warning in severidades:
            idx_err  = severidades.index(AlertSeverity.error)
            idx_warn = severidades.index(AlertSeverity.warning)
            assert idx_err < idx_warn

    def test_todos_alertas_tem_titulo_e_mensagem(self, df_base):
        for a in gerar_alertas(df_base):
            assert a.titulo
            assert a.mensagem

    def test_sem_dados_nao_quebra(self):
        df_empty = pd.DataFrame(columns=[
            "custo_zerado", "metodo_pagamento", "cliente", "valor_total",
            "produto", "quantidade", "periodo",
        ])
        try:
            gerar_alertas(df_empty)
        except Exception as e:
            pytest.fail(f"gerar_alertas quebrou com df vazio: {e}")
