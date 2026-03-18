from __future__ import annotations

import datetime

import pandas as pd
import pytest

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from services.data_loader import (
    _COLUNAS_OBRIGATORIAS,
    _transformar,
    _validar_colunas,
    get_clientes,
    get_date_range,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _raw_df_completo() -> pd.DataFrame:
    """DataFrame com todas as colunas originais do Excel."""
    return pd.DataFrame(
        {
            "Código Produto":   ["P001", "P002"],
            "Descrição Produto":["Produto A", "Produto B"],
            "Categoria Produto":["Cat1", "Cat2"],
            "Cliente":          ["CLI-1", "CLI-2"],
            "Método Pagamento": ["Cartão", "PIX"],
            "Bandeira Cartão":  ["Visa", None],
            "Data":             ["2025-12-01", "2025-12-02"],
            "Mês":              ["dezembro", "dezembro"],
            "Dia da Semana":    ["Segunda-feira", "Terça-feira"],
            "Hora":             ["10:00 - 10:59", "14:00 - 14:59"],
            "Quantidade":       [5, 2],
            "Valor Total":      [50.0, 30.0],
            "Valor Médio":      [10.0, 15.0],   # deve ser ignorado
            "Custo total":      [0.0, 0.0],
            "Custo médio":      [0.0, 0.0],     # deve ser ignorado
            "Margem média":     [0.0, 0.0],     # deve ser ignorado
        }
    )


# ---------------------------------------------------------------------------
# Validação de colunas
# ---------------------------------------------------------------------------
class TestValidarColunas:
    def test_aceita_df_completo(self):
        df = _raw_df_completo()
        _validar_colunas(df)  # não deve lançar

    def test_levanta_erro_coluna_faltando(self):
        df = _raw_df_completo().drop(columns=["Valor Total"])
        with pytest.raises(ValueError, match="Valor Total"):
            _validar_colunas(df)

    def test_todas_colunas_obrigatorias_testadas(self):
        for col in _COLUNAS_OBRIGATORIAS:
            df = _raw_df_completo().drop(columns=[col])
            with pytest.raises(ValueError):
                _validar_colunas(df)


# ---------------------------------------------------------------------------
# Transformações
# ---------------------------------------------------------------------------
class TestTransformar:
    def setup_method(self):
        self.raw = _raw_df_completo()
        self.df  = _transformar(self.raw)

    def test_colunas_snake_case_presentes(self):
        obrigatorias = ["produto", "categoria", "cliente", "metodo_pagamento",
                        "quantidade", "valor_total", "hora", "data", "datetime",
                        "periodo", "valor_unitario", "tem_custo", "custo_zerado"]
        for col in obrigatorias:
            assert col in self.df.columns, f"Coluna ausente: {col}"

    def test_colunas_ignoradas_ausentes(self):
        for col in ["Valor Médio", "Margem média", "Custo médio",
                    "valor_medio", "margem_media", "custo_medio"]:
            assert col not in self.df.columns

    def test_datetime_criado(self):
        assert pd.api.types.is_datetime64_any_dtype(self.df["datetime"])

    def test_data_como_date(self):
        assert isinstance(self.df["data"].iloc[0], datetime.date)

    def test_hora_como_int(self):
        assert self.df["hora"].dtype in (int, "int64", "int32")
        assert self.df["hora"].iloc[0] == 10

    def test_quantidade_como_int(self):
        assert self.df["quantidade"].dtype in (int, "int64", "int32")

    def test_periodo_criado_corretamente(self):
        # hora 10 → manha, hora 14 → tarde
        assert self.df.loc[self.df["hora"] == 10, "periodo"].iloc[0] == "manha"
        assert self.df.loc[self.df["hora"] == 14, "periodo"].iloc[0] == "tarde"

    def test_periodo_madrugada(self):
        raw = _raw_df_completo()
        raw.loc[0, "Hora"] = "03:00 - 03:59"
        df = _transformar(raw)
        assert df.loc[0, "periodo"] == "madrugada"

    def test_periodo_noite(self):
        raw = _raw_df_completo()
        raw.loc[0, "Hora"] = "20:00 - 20:59"
        df = _transformar(raw)
        assert df.loc[0, "periodo"] == "noite"

    def test_valor_unitario_recalculado(self):
        # 50.0 / 5 = 10.0
        assert self.df.loc[0, "valor_unitario"] == pytest.approx(10.0)

    def test_custo_zerado_flag(self):
        assert self.df["custo_zerado"].all()
        assert not self.df["tem_custo"].any()

    def test_custo_nao_zerado_flag(self):
        raw = _raw_df_completo()
        raw.loc[0, "Custo total"] = 5.0
        df = _transformar(raw)
        assert df.loc[0, "tem_custo"] is True or df.loc[0, "tem_custo"] == True
        assert df.loc[0, "custo_zerado"] is False or df.loc[0, "custo_zerado"] == False

    def test_valor_unitario_divisao_por_zero(self):
        raw = _raw_df_completo()
        raw.loc[0, "Quantidade"] = 0
        df = _transformar(raw)
        assert df.loc[0, "valor_unitario"] == 0.0

    def test_remove_linhas_sem_data(self):
        raw = _raw_df_completo()
        raw.loc[0, "Data"] = "data-invalida"
        df = _transformar(raw)
        assert len(df) == 1  # apenas a linha 2 sobrevive


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------
class TestUtilitarios:
    def setup_method(self):
        self.raw = _raw_df_completo()
        self.df  = _transformar(self.raw)

    def test_get_clientes(self):
        clientes = get_clientes(self.df)
        assert "CLI-1" in clientes
        assert "CLI-2" in clientes
        assert clientes == sorted(clientes)

    def test_get_date_range(self):
        dmin, dmax = get_date_range(self.df)
        assert dmin <= dmax
