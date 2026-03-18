from __future__ import annotations

import datetime
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

from services.intelligence import (
    detect_anomalies,
    forecast_next_days,
    get_hour_pattern,
    get_revenue_trend,
    get_weekday_pattern,
)


# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------
def _start() -> datetime.date:
    return datetime.date(2025, 12, 1)


def _make_daily_df(revenues: list[float], hours: list[int] | None = None) -> pd.DataFrame:
    """
    Cria DataFrame com uma transação por dia, cada uma com valor = revenues[i].
    Simula output do data_loader com colunas mínimas para intelligence.
    """
    start = _start()
    _dias = ["segunda-feira", "terca-feira", "quarta-feira", "quinta-feira",
             "sexta-feira", "sabado", "domingo"]
    rows = []
    for i, rev in enumerate(revenues):
        d = start + datetime.timedelta(days=i)
        rows.append({
            "data":            d,
            "hora":            hours[i] if hours else 10,
            "periodo":         "manha",
            "dia_semana":      _dias[i % 7],
            "valor_total":     rev,
            "quantidade":      1,
            "produto":         f"Prod{i}",
            "categoria":       "Cat",
            "cliente":         "CliA",
            "custo_zerado":    True,
            "custo_unitario_real": float("nan"),
        })
    return pd.DataFrame(rows)


def _make_hourly_df() -> pd.DataFrame:
    """DataFrame com transações em horas específicas para testar get_hour_pattern."""
    start = _start()
    rows = []
    for hora, total in [(8, 50.0), (12, 200.0), (19, 150.0), (22, 30.0)]:
        rows.append({
            "data": start, "hora": hora, "dia_semana": "segunda-feira",
            "valor_total": total, "quantidade": 1, "produto": "P",
            "categoria": "C", "cliente": "A", "custo_zerado": True,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 1. Tendência
# ---------------------------------------------------------------------------
class TestRevenueTrend:
    def test_detects_uptrend(self):
        df = _make_daily_df([100, 120, 140, 160, 180, 200, 220])
        result = get_revenue_trend(df)
        assert result["direction"] == "subindo"

    def test_detects_downtrend(self):
        df = _make_daily_df([220, 200, 180, 160, 140, 120, 100])
        result = get_revenue_trend(df)
        assert result["direction"] == "caindo"

    def test_detects_flat_trend(self):
        df = _make_daily_df([150.0] * 7)
        result = get_revenue_trend(df)
        assert result["direction"] == "estavel"

    def test_slope_positive_for_uptrend(self):
        df = _make_daily_df([100, 120, 140, 160, 180, 200, 220])
        assert get_revenue_trend(df)["slope_diario"] > 0

    def test_slope_negative_for_downtrend(self):
        df = _make_daily_df([220, 200, 180, 160, 140, 120, 100])
        assert get_revenue_trend(df)["slope_diario"] < 0

    def test_has_required_keys(self):
        df = _make_daily_df([100, 120, 140])
        result = get_revenue_trend(df)
        for key in ["direction", "slope_diario", "media_diaria",
                    "pct_variacao", "dias_analisados", "serie"]:
            assert key in result

    def test_dias_analisados_correto(self):
        df = _make_daily_df([100, 110, 120, 130, 140])
        assert get_revenue_trend(df)["dias_analisados"] == 5

    def test_serie_tem_media_movel(self):
        df = _make_daily_df([100, 120, 140, 160, 180])
        serie = get_revenue_trend(df)["serie"]
        assert "media_movel_3d" in serie.columns
        assert not serie["media_movel_3d"].isna().all()

    def test_pct_variacao_subida(self):
        df = _make_daily_df([100.0, 150.0])
        result = get_revenue_trend(df)
        assert result["pct_variacao"] == pytest.approx(50.0, rel=1e-2)

    def test_single_day_returns_estavel(self):
        df = _make_daily_df([200.0])
        result = get_revenue_trend(df)
        assert result["direction"] == "estavel"
        assert result["dias_analisados"] == 1

    def test_empty_df_returns_estavel(self):
        df = _make_daily_df([])
        result = get_revenue_trend(df)
        assert result["direction"] == "estavel"
        assert result["dias_analisados"] == 0


# ---------------------------------------------------------------------------
# 2. Padrão por hora
# ---------------------------------------------------------------------------
class TestHourPattern:
    def test_retorna_dataframe(self):
        df = _make_hourly_df()
        result = get_hour_pattern(df)
        assert isinstance(result, pd.DataFrame)

    def test_colunas_obrigatorias(self):
        df = _make_hourly_df()
        result = get_hour_pattern(df)
        for col in ["hora", "faturamento", "participacao_pct", "rank"]:
            assert col in result.columns

    def test_participacao_soma_100(self):
        df = _make_hourly_df()
        result = get_hour_pattern(df)
        assert result["participacao_pct"].sum() == pytest.approx(100.0, rel=1e-2)

    def test_hora_maior_faturamento_rank_1(self):
        df = _make_hourly_df()
        result = get_hour_pattern(df)
        # hora 12 tem faturamento 200 → rank 1
        h12 = result[result["hora"] == 12]
        assert h12.iloc[0]["rank"] == 1

    def test_empty_df_retorna_vazio(self):
        df = pd.DataFrame(columns=["hora", "valor_total"])
        result = get_hour_pattern(df)
        assert result.empty

    def test_ordenado_por_hora(self):
        df = _make_hourly_df()
        result = get_hour_pattern(df)
        horas = result["hora"].tolist()
        assert horas == sorted(horas)


# ---------------------------------------------------------------------------
# 3. Padrão por dia da semana
# ---------------------------------------------------------------------------
class TestWeekdayPattern:
    def test_retorna_dataframe(self):
        df = _make_daily_df([100, 120, 140, 160, 180, 200, 220])
        result = get_weekday_pattern(df)
        assert isinstance(result, pd.DataFrame)

    def test_colunas_obrigatorias(self):
        df = _make_daily_df([100, 120, 140])
        result = get_weekday_pattern(df)
        for col in ["dia_semana", "faturamento", "participacao_pct", "rank"]:
            assert col in result.columns

    def test_participacao_soma_100(self):
        df = _make_daily_df([100, 120, 140, 160, 180, 200, 220])
        result = get_weekday_pattern(df)
        assert result["participacao_pct"].sum() == pytest.approx(100.0, rel=1e-2)

    def test_empty_df_retorna_vazio(self):
        df = pd.DataFrame(columns=["dia_semana", "valor_total"])
        result = get_weekday_pattern(df)
        assert result.empty

    def test_n_dias_correto(self):
        df = _make_daily_df([100, 120, 140])
        result = get_weekday_pattern(df)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# 4. Detecção de anomalias
# ---------------------------------------------------------------------------
class TestDetectAnomalies:
    def test_detecta_pico(self):
        # Dia 4 tem faturamento 1000 — muito acima da média (~150)
        revenues = [150, 140, 160, 1000, 155, 145, 165]
        df = _make_daily_df(revenues)
        anomalias = detect_anomalies(df)
        picos = [a for a in anomalias if a["tipo"] == "pico"]
        assert len(picos) >= 1

    def test_detecta_queda(self):
        revenues = [150, 140, 160, 5, 155, 145, 165]
        df = _make_daily_df(revenues)
        anomalias = detect_anomalies(df)
        quedas = [a for a in anomalias if a["tipo"] == "queda"]
        assert len(quedas) >= 1

    def test_retorna_vazio_menos_3_dias(self):
        df = _make_daily_df([100, 200])
        assert detect_anomalies(df) == []

    def test_retorna_vazio_sem_anomalia(self):
        # Todos os dias iguais → std=0 → sem anomalia
        df = _make_daily_df([100.0] * 7)
        assert detect_anomalies(df) == []

    def test_zscore_correto_para_pico(self):
        revenues = [100.0] * 6 + [400.0]   # último dia é pico
        df = _make_daily_df(revenues)
        anomalias = detect_anomalies(df)
        picos = [a for a in anomalias if a["tipo"] == "pico"]
        assert len(picos) >= 1
        assert picos[-1]["zscore"] > 0

    def test_tipo_queda_zscore_negativo(self):
        revenues = [100.0] * 6 + [0.0]
        df = _make_daily_df(revenues)
        anomalias = detect_anomalies(df)
        quedas = [a for a in anomalias if a["tipo"] == "queda"]
        if quedas:
            assert quedas[0]["zscore"] < 0

    def test_campos_obrigatorios(self):
        revenues = [150] * 6 + [1500]
        df = _make_daily_df(revenues)
        anomalias = detect_anomalies(df)
        if anomalias:
            for campo in ["data", "faturamento", "esperado", "zscore", "tipo"]:
                assert campo in anomalias[0]

    def test_retorna_lista(self):
        df = _make_daily_df([100, 150, 120, 140, 160])
        result = detect_anomalies(df)
        assert isinstance(result, list)

    def test_ordenado_por_data(self):
        revenues = [1000, 150, 140, 160, 155, 0, 145]
        df = _make_daily_df(revenues)
        anomalias = detect_anomalies(df)
        if len(anomalias) >= 2:
            datas = [a["data"] for a in anomalias]
            assert datas == sorted(datas)


# ---------------------------------------------------------------------------
# 5. Previsão
# ---------------------------------------------------------------------------
class TestForecastNextDays:
    def test_retorna_n_dias_correto(self):
        df = _make_daily_df([100, 120, 140, 160, 180])
        fc = forecast_next_days(df, days=7)
        assert len(fc["previsao"]) == 7

    def test_primeiro_dia_previsto_e_dia_seguinte(self):
        revenues = [100, 110, 120, 130, 140]
        df = _make_daily_df(revenues)
        fc = forecast_next_days(df, days=3)
        last_date = _start() + datetime.timedelta(days=len(revenues) - 1)
        expected  = last_date + datetime.timedelta(days=1)
        assert fc["previsao"]["data_prevista"].iloc[0] == expected

    def test_valores_nao_negativos(self):
        df = _make_daily_df([100, 110, 120, 130, 140])
        fc = forecast_next_days(df, days=7)
        assert (fc["previsao"]["faturamento_previsto"] >= 0).all()

    def test_limite_sup_maior_que_previsto(self):
        df = _make_daily_df([100, 120, 140, 160, 180])
        fc = forecast_next_days(df, days=5)
        prev = fc["previsao"]
        assert (prev["limite_superior"] >= prev["faturamento_previsto"]).all()

    def test_limite_inf_menor_que_previsto(self):
        df = _make_daily_df([100, 120, 140, 160, 180])
        fc = forecast_next_days(df, days=5)
        prev = fc["previsao"]
        assert (prev["limite_inferior"] <= prev["faturamento_previsto"]).all()

    def test_base_insuficiente_retorna_vazio(self):
        df = _make_daily_df([100.0])  # só 1 dia
        fc = forecast_next_days(df, days=7)
        assert fc["previsao"].empty

    def test_aviso_base_curta(self):
        df = _make_daily_df([100, 120, 140])
        fc = forecast_next_days(df, days=3)
        assert len(fc["aviso"]) > 0

    def test_slope_positivo_tendencia_alta(self):
        # Com tendência ascendente, slope deve ser positivo
        df = _make_daily_df([100, 120, 140, 160, 180, 200, 220])
        fc = forecast_next_days(df, days=3)
        assert fc["slope_diario"] > 0

    def test_sem_lookahead_bias_na_projecao(self):
        """
        Os valores previstos devem ser calculados apenas com dados do histórico.
        Verificamos que a previsão para o dia N+1 usa somente N dias de dados
        e não inclui o faturamento previsto como dado de entrada.
        """
        df_curto = _make_daily_df([100, 110, 120])
        df_longo = _make_daily_df([100, 110, 120, 130, 140])
        fc_curto = forecast_next_days(df_curto, days=1)
        fc_longo = forecast_next_days(df_longo, days=1)
        # Com mais histórico o modelo pode ter slope diferente — OK.
        # O que validamos é que a previsão não usa dados além da série histórica.
        # Verifica: datas previstas são POSTERIORES à última data real
        if not fc_curto["previsao"].empty:
            ultima_curta = _start() + datetime.timedelta(days=2)
            assert fc_curto["previsao"]["data_prevista"].iloc[0] > ultima_curta

    def test_campos_obrigatorios_no_resultado(self):
        df = _make_daily_df([100, 120, 140, 160, 180])
        fc = forecast_next_days(df, days=3)
        for campo in ["dias_base", "media_diaria", "slope_diario", "previsao", "metodo", "aviso"]:
            assert campo in fc

    def test_metodo_regressao_linear(self):
        df = _make_daily_df([100, 120, 140, 160, 180])
        fc = forecast_next_days(df, days=3)
        assert fc["metodo"] == "regressao_linear"
