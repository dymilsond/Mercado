from __future__ import annotations

import datetime
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

from services.benchmark import (
    get_comparative_alerts,
    get_unit_benchmark,
    get_unit_payment_comparison,
    get_unit_profile,
    get_unit_ranking,
    get_unit_time_comparison,
    get_unit_vs_average,
)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def df_bench() -> pd.DataFrame:
    hoje   = datetime.date(2025, 12, 1)
    amanha = datetime.date(2025, 12, 2)
    return pd.DataFrame({
        "produto":          ["Heineken", "Skol", "Água", "Doritos", "Vinho", "Suco",
                             "Heineken", "Skol", "Água", "Doritos"],
        "categoria":        ["Cervejas","Cervejas","Bebidas","Salgadinhos","Vinhos","Bebidas",
                             "Cervejas","Cervejas","Bebidas","Salgadinhos"],
        "cliente":          ["Alpha","Alpha","Alpha","Beta","Beta","Beta",
                             "Gamma","Gamma","Delta","Delta"],
        "metodo_pagamento": ["Cartão","Cartão","PIX","Cartão","Cartão","PIX",
                             "PIX","PIX","Cartão","Cartão"],
        "bandeira":         ["Visa","Visa",None,"Master","Master",None,
                             None,None,"Visa","Visa"],
        "quantidade":       [10, 5, 20, 8, 2, 15, 12, 6, 4, 3],
        "valor_total":      [100.0, 50.0, 60.0, 40.0, 80.0, 30.0,
                             120.0, 60.0, 20.0, 15.0],
        "hora":             [10, 14, 10, 20, 20, 14, 10, 14, 2, 2],
        "data":             [hoje, hoje, amanha, hoje, amanha, amanha,
                             hoje, amanha, hoje, amanha],
        "datetime":         [
            datetime.datetime(2025,12,1,10), datetime.datetime(2025,12,1,14),
            datetime.datetime(2025,12,2,10), datetime.datetime(2025,12,1,20),
            datetime.datetime(2025,12,2,20), datetime.datetime(2025,12,2,14),
            datetime.datetime(2025,12,1,10), datetime.datetime(2025,12,2,14),
            datetime.datetime(2025,12,1,2),  datetime.datetime(2025,12,2,2),
        ],
        "dia_semana":       ["segunda-feira"]*10,
        "mes":              ["dezembro"]*10,
        "periodo":          ["manha","tarde","manha","noite","noite","tarde",
                             "manha","tarde","madrugada","madrugada"],
        "valor_unitario":   [10.0,10.0,3.0,5.0,40.0,2.0,10.0,10.0,5.0,5.0],
        "ticket_medio_item":[10.0,10.0,3.0,5.0,40.0,2.0,10.0,10.0,5.0,5.0],
        "tem_custo":        [False]*10,
        "custo_zerado":     [True]*10,
    })


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------
class TestUnitRanking:
    def test_retorna_todas_unidades(self, df_bench):
        rank = get_unit_ranking(df_bench)
        assert set(rank["cliente"]) == {"Alpha", "Beta", "Gamma", "Delta"}

    def test_ordenado_por_faturamento(self, df_bench):
        rank = get_unit_ranking(df_bench)
        fats = rank["faturamento"].tolist()
        assert fats == sorted(fats, reverse=True)

    def test_ranking_começa_em_1(self, df_bench):
        rank = get_unit_ranking(df_bench)
        assert rank["ranking"].min() == 1

    def test_participacao_soma_100(self, df_bench):
        rank = get_unit_ranking(df_bench)
        assert rank["participacao_pct"].sum() == pytest.approx(100.0, rel=1e-2)

    def test_ticket_medio_calculado(self, df_bench):
        rank = get_unit_ranking(df_bench)
        alpha = rank[rank["cliente"] == "Alpha"].iloc[0]
        expected = alpha["faturamento"] / alpha["transacoes"]
        assert alpha["ticket_medio"] == pytest.approx(expected, rel=1e-3)

    def test_colunas_obrigatorias(self, df_bench):
        rank = get_unit_ranking(df_bench)
        for col in ["cliente","ranking","faturamento","participacao_pct",
                    "transacoes","ticket_medio","n_produtos"]:
            assert col in rank.columns


# ---------------------------------------------------------------------------
# Benchmark vs média
# ---------------------------------------------------------------------------
class TestUnitBenchmark:
    def test_media_calculada(self, df_bench):
        bench = get_unit_benchmark(df_bench)
        media = df_bench.groupby("cliente")["valor_total"].sum().mean()
        assert bench["faturamento_media"].iloc[0] == pytest.approx(media, rel=1e-3)

    def test_desvio_maior_acima_tem_positivo(self, df_bench):
        bench = get_unit_benchmark(df_bench)
        # Gamma tem maior faturamento → desvio positivo
        gamma = bench[bench["cliente"] == "Gamma"].iloc[0]
        assert gamma["faturamento_vs_media_pct"] > 0

    def test_desvio_menor_abaixo_tem_negativo(self, df_bench):
        bench = get_unit_benchmark(df_bench)
        # Delta tem menor faturamento → desvio negativo
        delta = bench[bench["cliente"] == "Delta"].iloc[0]
        assert delta["faturamento_vs_media_pct"] < 0


# ---------------------------------------------------------------------------
# Gap vs média
# ---------------------------------------------------------------------------
class TestUnitVsAverage:
    def test_retorna_colunas_gap(self, df_bench):
        gap = get_unit_vs_average(df_bench)
        for col in ["gap_fat_abs","gap_fat_pct","status"]:
            assert col in gap.columns

    def test_status_acima_correto(self, df_bench):
        gap = get_unit_vs_average(df_bench)
        # Gamma (maior fat) → status acima
        gamma_status = gap[gap["cliente"] == "Gamma"]["status"].iloc[0]
        assert gamma_status == "acima"

    def test_status_abaixo_correto(self, df_bench):
        gap = get_unit_vs_average(df_bench)
        delta_status = gap[gap["cliente"] == "Delta"]["status"].iloc[0]
        assert delta_status == "abaixo"

    def test_gap_positivo_para_lider(self, df_bench):
        gap = get_unit_vs_average(df_bench)
        gamma_gap = gap[gap["cliente"] == "Gamma"]["gap_fat_abs"].iloc[0]
        assert gamma_gap > 0

    def test_gap_negativo_para_ultimo(self, df_bench):
        gap = get_unit_vs_average(df_bench)
        delta_gap = gap[gap["cliente"] == "Delta"]["gap_fat_abs"].iloc[0]
        assert delta_gap < 0


# ---------------------------------------------------------------------------
# Perfil por unidade
# ---------------------------------------------------------------------------
class TestUnitProfile:
    def test_retorna_dict_completo(self, df_bench):
        p = get_unit_profile(df_bench, "Alpha")
        for key in ["faturamento","n_transacoes","ticket_medio","n_produtos",
                    "top_produtos","categorias","periodos","pix_pct"]:
            assert key in p

    def test_faturamento_correto(self, df_bench):
        fat_esperado = df_bench[df_bench["cliente"] == "Alpha"]["valor_total"].sum()
        p = get_unit_profile(df_bench, "Alpha")
        assert p["faturamento"] == pytest.approx(fat_esperado)

    def test_pix_pct_correto(self, df_bench):
        p = get_unit_profile(df_bench, "Alpha")
        df_a = df_bench[df_bench["cliente"] == "Alpha"]
        n_pix = (df_a["metodo_pagamento"] == "PIX").sum()
        esperado = n_pix / len(df_a) * 100
        assert p["pix_pct"] == pytest.approx(esperado, rel=1e-2)

    def test_unidade_inexistente_retorna_vazio(self, df_bench):
        p = get_unit_profile(df_bench, "NaoExiste")
        assert p == {}

    def test_top_produtos_max_5(self, df_bench):
        p = get_unit_profile(df_bench, "Alpha")
        assert len(p["top_produtos"]) <= 5


# ---------------------------------------------------------------------------
# Comparação de pagamentos
# ---------------------------------------------------------------------------
class TestPaymentComparison:
    def test_todas_unidades_presentes(self, df_bench):
        pgto = get_unit_payment_comparison(df_bench)
        assert set(pgto["unidade"]) == {"Alpha", "Beta", "Gamma", "Delta"}

    def test_pix_coluna_presente(self, df_bench):
        pgto = get_unit_payment_comparison(df_bench)
        assert "PIX" in pgto.columns

    def test_gamma_tem_alto_pix(self, df_bench):
        pgto = get_unit_payment_comparison(df_bench)
        gamma_pix = pgto[pgto["unidade"] == "Gamma"]["PIX"].iloc[0]
        assert gamma_pix == pytest.approx(100.0)  # Gamma só usa PIX


# ---------------------------------------------------------------------------
# Comparação de horários
# ---------------------------------------------------------------------------
class TestTimeComparison:
    def test_todas_unidades_presentes(self, df_bench):
        tempo = get_unit_time_comparison(df_bench)
        assert set(tempo["unidade"]) == {"Alpha", "Beta", "Gamma", "Delta"}

    def test_madrugada_coluna_presente(self, df_bench):
        tempo = get_unit_time_comparison(df_bench)
        assert "madrugada" in tempo.columns

    def test_delta_tem_madrugada_100(self, df_bench):
        tempo = get_unit_time_comparison(df_bench)
        delta_madr = tempo[tempo["unidade"] == "Delta"]["madrugada"].iloc[0]
        assert delta_madr == pytest.approx(100.0)  # Delta só vende na madrugada


# ---------------------------------------------------------------------------
# Alertas comparativos
# ---------------------------------------------------------------------------
class TestComparativeAlerts:
    def test_retorna_lista(self, df_bench):
        alertas = get_comparative_alerts(df_bench)
        assert isinstance(alertas, list)

    def test_alerta_performance_para_delta(self, df_bench):
        alertas = get_comparative_alerts(df_bench)
        perf = [a for a in alertas if a["tipo"] == "performance"]
        unidades = [a["unidade"] for a in perf]
        assert "Delta" in unidades

    def test_ordenado_error_antes_warning(self, df_bench):
        alertas = get_comparative_alerts(df_bench)
        sevs = [a["severidade"] for a in alertas]
        _ord = {"error": 0, "warning": 1, "info": 2}
        nums = [_ord.get(s, 9) for s in sevs]
        assert nums == sorted(nums)

    def test_todos_alertas_tem_mensagem(self, df_bench):
        alertas = get_comparative_alerts(df_bench)
        for a in alertas:
            assert a["mensagem"]
            assert a["unidade"]

    def test_1_unidade_nao_quebra(self):
        df_single = pd.DataFrame({
            "cliente":          ["Alpha", "Alpha"],
            "valor_total":      [100.0, 50.0],
            "metodo_pagamento": ["PIX", "Cartão"],
            "periodo":          ["manha", "tarde"],
        })
        try:
            get_comparative_alerts(df_single)
        except Exception as e:
            pytest.fail(f"Não deveria quebrar com 1 unidade: {e}")

    def test_base_curta_nao_quebra(self):
        import datetime
        df_curto = pd.DataFrame({
            "produto":    ["A"],
            "categoria":  ["X"],
            "cliente":    ["Un1"],
            "metodo_pagamento": ["PIX"],
            "bandeira":   [None],
            "quantidade": [1],
            "valor_total":[10.0],
            "hora":       [10],
            "data":       [datetime.date(2025,12,1)],
            "datetime":   [datetime.datetime(2025,12,1,10)],
            "dia_semana": ["segunda-feira"],
            "mes":        ["dezembro"],
            "periodo":    ["manha"],
            "valor_unitario":   [10.0],
            "ticket_medio_item":[10.0],
            "tem_custo":  [False],
            "custo_zerado":[True],
        })
        try:
            get_unit_ranking(df_curto)
            get_unit_benchmark(df_curto)
        except Exception as e:
            pytest.fail(f"Base curta quebrou: {e}")
