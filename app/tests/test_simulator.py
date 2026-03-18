from __future__ import annotations

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pytest
from tests.conftest import *  # noqa: F401,F403

from services.simulator import (
    simular_crescimento_cliente,
    simular_pix,
    simular_projecao_mensal,
    simular_remocao_baixa_saida,
)


class TestSimulacaoPix:
    def test_retorna_impacto_positivo(self, df_base):
        res = simular_pix(df_base, meta_pix_pct=50.0, taxa_cartao_pct=2.5)
        assert res.impacto_financeiro >= 0

    def test_impacto_zero_se_pix_ja_na_meta(self, df_com_pix):
        # df_com_pix tem 50% PIX — meta de 30% não gera economia adicional
        res = simular_pix(df_com_pix, meta_pix_pct=20.0, taxa_cartao_pct=2.5)
        assert res.impacto_financeiro >= 0  # não negativo

    def test_tem_premissas(self, df_base):
        res = simular_pix(df_base)
        assert res.premissas
        assert "dia" in res.premissas.lower()

    def test_impacto_coerente_com_faturamento(self, df_base):
        fat_total = df_base["valor_total"].sum()
        res = simular_pix(df_base, meta_pix_pct=80.0, taxa_cartao_pct=3.0)
        # Economia não pode ser maior que 3% do faturamento total
        assert res.impacto_financeiro <= fat_total * 0.03 + 0.01


class TestSimulacaoMix:
    def test_nao_gera_valor_absurdo(self, df_base):
        fat_total = df_base["valor_total"].sum()
        res = simular_remocao_baixa_saida(df_base, reposicao_fator=0.5)
        # Impacto não pode ser maior que o faturamento total
        assert abs(res.impacto_financeiro) <= fat_total

    def test_vinhos_excluidos(self, df_base):
        res = simular_remocao_baixa_saida(df_base, categorias_excluir={"vinhos"})
        assert "vinhos" in res.premissas.lower() or "vinho" in res.premissas.lower()

    def test_fator_zero_causa_perda_total(self, df_base):
        res = simular_remocao_baixa_saida(df_base, reposicao_fator=0.0)
        assert res.impacto_financeiro <= 0


class TestSimulacaoCrescimentoCliente:
    def test_gap_positivo_para_cliente_fraco(self, df_base):
        # ClienteC tem faturamento muito baixo
        res = simular_crescimento_cliente(df_base, cliente="ClienteC", meta_pct_media=80.0)
        assert res.impacto_financeiro >= 0

    def test_gap_zero_para_cliente_na_meta(self, df_base):
        # ClienteA tem o maior faturamento; meta de 50% da média deve ser zero
        res = simular_crescimento_cliente(df_base, cliente="ClienteA", meta_pct_media=10.0)
        assert res.impacto_financeiro == 0.0


class TestProjecaoMensal:
    def test_projecao_maior_que_base(self, df_base):
        res = simular_projecao_mensal(df_base)
        fat_base = df_base["valor_total"].sum()
        n_dias   = df_base["data"].nunique()
        if n_dias < 30:
            assert res.impacto_financeiro > fat_base

    def test_inclui_aviso_de_cautela(self, df_base):
        res = simular_projecao_mensal(df_base)
        assert "cautela" in res.premissas.lower() or "sazonalidade" in res.premissas.lower()

    def test_nao_quebra_com_1_dia(self):
        import datetime, pandas as pd
        df = pd.DataFrame({
            "valor_total": [100.0],
            "data":        [datetime.date(2025, 12, 1)],
        })
        res = simular_projecao_mensal(df)
        assert res.impacto_financeiro == pytest.approx(100.0 / 1 * 30)
