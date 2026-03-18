from __future__ import annotations

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

from tests.conftest import *  # noqa: F401,F403

from services.finance import (
    get_cobertura_custo,
    get_high_margin_low_volume,
    get_high_sale_low_margin,
    get_margin,
    get_products_with_loss,
    get_profit_by_product,
    get_profit_by_unit,
    get_top_profit_products,
    get_total_profit,
    get_worst_profit_products,
)


# ---------------------------------------------------------------------------
# Cobertura de custo
# ---------------------------------------------------------------------------
class TestCoberturaCusto:
    def test_sem_coluna_retorna_zero(self, df_base):
        df = df_base.drop(columns=["custo_unitario_real"])
        assert get_cobertura_custo(df) == 0.0

    def test_todos_nan_retorna_zero(self, df_base):
        assert get_cobertura_custo(df_base) == 0.0

    def test_parcial_retorna_pct_correta(self, df_com_custo_real):
        # 5 de 6 linhas com custo = 83.33...%
        cob = get_cobertura_custo(df_com_custo_real)
        assert pytest.approx(cob, rel=1e-2) == 5 / 6 * 100

    def test_completo_retorna_100(self, df_com_custo_real_completo):
        assert get_cobertura_custo(df_com_custo_real_completo) == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Lucro total
# ---------------------------------------------------------------------------
class TestTotalProfit:
    def test_none_quando_sem_custo(self, df_base):
        assert get_total_profit(df_base) is None

    def test_calculo_correto(self, df_com_custo_real):
        # lucros: 40 + 6 + (-10) + 25 + 3 = 64
        lucro = get_total_profit(df_com_custo_real)
        assert lucro == pytest.approx(64.0, rel=1e-3)

    def test_inclui_prejuizo(self, df_com_custo_real):
        # Cabernet tem lucro=-10, deve ser incluido no total
        lucro = get_total_profit(df_com_custo_real)
        assert lucro < 100.0   # menor que a soma sem o prejuizo

    def test_completo_soma_todo_lucro(self, df_com_custo_real_completo):
        # Agua: 1.5*20=30 custo, fat=60, lucro=30 → total = 64 + 30 = 94
        lucro = get_total_profit(df_com_custo_real_completo)
        assert lucro == pytest.approx(94.0, rel=1e-3)


# ---------------------------------------------------------------------------
# Margem
# ---------------------------------------------------------------------------
class TestMargin:
    def test_none_quando_sem_custo(self, df_base):
        assert get_margin(df_base) is None

    def test_margem_calculada_corretamente(self, df_com_custo_real):
        # fat com custo = 100+20+50+40+10=220, lucro=64
        margem = get_margin(df_com_custo_real)
        esperada = 64.0 / 220.0 * 100
        assert margem == pytest.approx(esperada, rel=1e-2)

    def test_margem_positiva_quando_lucrativo(self, df_com_custo_real_completo):
        assert get_margin(df_com_custo_real_completo) > 0

    def test_margem_zero_fat_retorna_none(self):
        import datetime
        df = pd.DataFrame({
            "custo_unitario_real": [5.0],
            "custo_total_real":    [5.0],
            "lucro":               [0.0],
            "valor_total":         [0.0],
            "quantidade":          [1],
        })
        assert get_margin(df) is None


# ---------------------------------------------------------------------------
# Lucro por produto
# ---------------------------------------------------------------------------
class TestProfitByProduct:
    def test_retorna_vazio_sem_custo(self, df_base):
        result = get_profit_by_product(df_base)
        assert result.empty

    def test_ordenado_por_lucro_desc(self, df_com_custo_real):
        prod = get_profit_by_product(df_com_custo_real)
        lucros = prod["lucro"].tolist()
        assert lucros == sorted(lucros, reverse=True)

    def test_colunas_obrigatorias(self, df_com_custo_real):
        prod = get_profit_by_product(df_com_custo_real)
        for col in ["produto", "categoria", "faturamento", "custo_total", "lucro", "margem_pct"]:
            assert col in prod.columns

    def test_produto_prejuizo_incluso(self, df_com_custo_real):
        prod = get_profit_by_product(df_com_custo_real)
        cabernet = prod[prod["produto"] == "Cabernet"]
        assert len(cabernet) == 1
        assert cabernet.iloc[0]["lucro"] < 0

    def test_margem_cabernet_negativa(self, df_com_custo_real):
        prod = get_profit_by_product(df_com_custo_real)
        cab_margem = prod[prod["produto"] == "Cabernet"]["margem_pct"].iloc[0]
        assert cab_margem < 0

    def test_margem_heineken_correta(self, df_com_custo_real):
        # Heineken: fat=100, custo=60, lucro=40, margem=40%
        prod = get_profit_by_product(df_com_custo_real)
        h = prod[prod["produto"] == "Heineken"].iloc[0]
        assert h["margem_pct"] == pytest.approx(40.0, rel=1e-2)

    def test_linhas_sem_custo_excluidas(self, df_com_custo_real):
        # Agua (P005) nao tem custo — nao deve aparecer
        prod = get_profit_by_product(df_com_custo_real)
        assert "Água" not in prod["produto"].values


# ---------------------------------------------------------------------------
# Top e Worst products
# ---------------------------------------------------------------------------
class TestTopWorstProducts:
    def test_top_tem_maior_lucro(self, df_com_custo_real):
        top = get_top_profit_products(df_com_custo_real, n=1)
        all_prod = get_profit_by_product(df_com_custo_real)
        assert top.iloc[0]["lucro"] == all_prod["lucro"].max()

    def test_worst_tem_menor_lucro(self, df_com_custo_real):
        worst = get_worst_profit_products(df_com_custo_real, n=1)
        all_prod = get_profit_by_product(df_com_custo_real)
        assert worst.iloc[0]["lucro"] == all_prod["lucro"].min()

    def test_top_n_respeita_limite(self, df_com_custo_real):
        top = get_top_profit_products(df_com_custo_real, n=3)
        assert len(top) <= 3

    def test_worst_sem_custo_retorna_vazio(self, df_base):
        assert get_worst_profit_products(df_base).empty


# ---------------------------------------------------------------------------
# Produtos com prejuizo
# ---------------------------------------------------------------------------
class TestProductsWithLoss:
    def test_sem_custo_retorna_vazio(self, df_base):
        assert get_products_with_loss(df_base).empty

    def test_encontra_cabernet(self, df_com_custo_real):
        loss = get_products_with_loss(df_com_custo_real)
        assert "Cabernet" in loss["produto"].values

    def test_nao_inclui_lucrativos(self, df_com_custo_real):
        loss = get_products_with_loss(df_com_custo_real)
        assert "Heineken" not in loss["produto"].values


# ---------------------------------------------------------------------------
# Lucro por unidade
# ---------------------------------------------------------------------------
class TestProfitByUnit:
    def test_sem_custo_retorna_vazio(self, df_base):
        assert get_profit_by_unit(df_base).empty

    def test_agrupa_por_cliente(self, df_com_custo_real):
        unit = get_profit_by_unit(df_com_custo_real)
        # ClienteA: Heineken(40) + Skol(6) = 46
        # ClienteB: Cabernet(-10) + Doritos(25) = 15
        # ClienteC: Chips(3)
        assert set(unit["cliente"]) == {"ClienteA", "ClienteB", "ClienteC"}

    def test_cliente_a_lucro_correto(self, df_com_custo_real):
        unit = get_profit_by_unit(df_com_custo_real)
        lucro_a = unit[unit["cliente"] == "ClienteA"]["lucro"].iloc[0]
        assert lucro_a == pytest.approx(46.0, rel=1e-3)

    def test_colunas_obrigatorias(self, df_com_custo_real):
        unit = get_profit_by_unit(df_com_custo_real)
        for col in ["cliente", "faturamento", "custo_total", "lucro", "margem_pct"]:
            assert col in unit.columns

    def test_ordenado_por_lucro_desc(self, df_com_custo_real):
        unit = get_profit_by_unit(df_com_custo_real)
        lucros = unit["lucro"].tolist()
        assert lucros == sorted(lucros, reverse=True)


# ---------------------------------------------------------------------------
# Alto giro / baixa margem
# ---------------------------------------------------------------------------
class TestHighSaleLowMargin:
    def test_sem_custo_retorna_vazio(self, df_base):
        assert get_high_sale_low_margin(df_base).empty

    def test_retorna_df(self, df_com_custo_real):
        result = get_high_sale_low_margin(df_com_custo_real)
        assert isinstance(result, pd.DataFrame)

    def test_apenas_alto_fat_baixa_margem(self, df_com_custo_real):
        result = get_high_sale_low_margin(df_com_custo_real)
        if not result.empty:
            assert (result["margem_pct"] < 10.0).all()


# ---------------------------------------------------------------------------
# Alta margem / baixo volume
# ---------------------------------------------------------------------------
class TestHighMarginLowVolume:
    def test_sem_custo_retorna_vazio(self, df_base):
        assert get_high_margin_low_volume(df_base).empty

    def test_apenas_alta_margem(self, df_com_custo_real):
        result = get_high_margin_low_volume(df_com_custo_real)
        if not result.empty:
            assert (result["margem_pct"] >= 30.0).all()
