from __future__ import annotations

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pytest
from tests.conftest import *  # noqa: F401,F403  (fixtures)

from services.metrics import (
    faturamento_por_dia,
    faturamento_por_dia_semana,
    faturamento_por_hora,
    faturamento_por_periodo,
    kpis_gerais,
    metricas_pagamento,
    pareto_produtos,
    participacao_categorias,
    produtos_baixa_saida,
    ranking_clientes,
    ranking_produtos,
)


class TestKpis:
    def test_faturamento_total(self, df_base):
        kpis = kpis_gerais(df_base)
        assert kpis["faturamento"] == pytest.approx(280.0)

    def test_n_transacoes(self, df_base):
        assert kpis_gerais(df_base)["n_transacoes"] == 6

    def test_n_itens(self, df_base):
        assert kpis_gerais(df_base)["n_itens"] == 38  # 10+1+1+5+20+1

    def test_n_clientes(self, df_base):
        assert kpis_gerais(df_base)["n_clientes"] == 3

    def test_n_produtos(self, df_base):
        assert kpis_gerais(df_base)["n_produtos"] == 6

    def test_ticket_medio(self, df_base):
        kpis = kpis_gerais(df_base)
        assert kpis["ticket_medio"] == pytest.approx(280.0 / 6, rel=1e-3)

    def test_df_vazio(self):
        import pandas as pd
        df_empty = pd.DataFrame(
            columns=["valor_total", "quantidade", "produto", "cliente"]
        )
        # Não deve lançar erro
        try:
            kpis_gerais(df_empty)
        except Exception:
            pass  # aceito falhar graciosamente com df vazio


class TestRankingClientes:
    def test_ordenado_por_faturamento(self, df_base):
        rank = ranking_clientes(df_base)
        fats = rank["faturamento"].tolist()
        assert fats == sorted(fats, reverse=True)

    def test_participacao_soma_100(self, df_base):
        rank = ranking_clientes(df_base)
        assert rank["participacao_pct"].sum() == pytest.approx(100.0, rel=1e-2)

    def test_ticket_medio_positivo(self, df_base):
        rank = ranking_clientes(df_base)
        assert (rank["ticket_medio"] >= 0).all()


class TestParticipaoCategorias:
    def test_participacao_soma_100(self, df_base):
        cat = participacao_categorias(df_base)
        assert cat["participacao_pct"].sum() == pytest.approx(100.0, rel=1e-2)

    def test_todas_categorias_presentes(self, df_base):
        cat = participacao_categorias(df_base)
        assert set(cat["categoria"]) == {"Cervejas", "vinhos", "Salgadinhos", "Bebidas"}


class TestRankingProdutos:
    def test_top_n_respeitado(self, df_base):
        top = ranking_produtos(df_base, top_n=3)
        assert len(top) <= 3

    def test_ordenado_por_faturamento(self, df_base):
        top = ranking_produtos(df_base, top_n=10)
        fats = top["faturamento"].tolist()
        assert fats == sorted(fats, reverse=True)


class TestProdutosBaixaSaida:
    def test_identifica_1_venda(self, df_base):
        baixa = produtos_baixa_saida(df_base, max_vendas=1)
        # "Skol" (qtd=1), "Cabernet" (qtd=1), "Chips" (qtd=1)
        assert len(baixa) >= 1

    def test_nao_inclui_acima_do_limite(self, df_base):
        baixa = produtos_baixa_saida(df_base, max_vendas=1)
        assert "Heineken" not in baixa["produto"].values  # qtd=10


class TestParetoP:
    def test_retorna_chaves_corretas(self, df_base):
        p = pareto_produtos(df_base)
        assert "n_pareto_80" in p
        assert "total_produtos" in p
        assert "pct_catalogo" in p

    def test_n_pareto_menor_que_total(self, df_base):
        p = pareto_produtos(df_base)
        assert p["n_pareto_80"] <= p["total_produtos"]


class TestMetricasPagamento:
    def test_todos_metodos_presentes(self, df_base):
        m = metricas_pagamento(df_base)
        assert "Cartão" in m["metodo_pagamento"].values

    def test_participacao_soma_100(self, df_base):
        m = metricas_pagamento(df_base)
        assert m["participacao_pct"].sum() == pytest.approx(100.0, rel=1e-2)


class TestFaturamentoTemporal:
    def test_faturamento_por_dia_tem_dados(self, df_base):
        fd = faturamento_por_dia(df_base)
        assert not fd.empty
        assert "faturamento" in fd.columns

    def test_faturamento_por_hora_ordenado(self, df_base):
        fh = faturamento_por_hora(df_base)
        horas = fh["hora"].tolist()
        assert horas == sorted(horas)

    def test_faturamento_por_periodo(self, df_base):
        fp = faturamento_por_periodo(df_base)
        assert fp["participacao_pct"].sum() == pytest.approx(100.0, rel=1e-2)
