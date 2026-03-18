from __future__ import annotations

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pytest
from tests.conftest import *  # noqa: F401,F403

from domain.enums import Priority
from services.recommendations import (
    _base_label,
    _rec_pix_baixo,
    _rec_produtos_baixa_saida,
    generate_recommendations,
)


class TestBaseDias:
    def test_base_label_contem_dias(self, df_base):
        label = _base_label(df_base)
        assert "Base analisada:" in label
        assert "dia" in label

    def test_base_label_numero_correto(self, df_base):
        n = df_base["data"].nunique()
        assert str(n) in _base_label(df_base)


class TestVinhosExcluidos:
    def test_vinho_nao_entra_em_baixa_saida(self, df_base):
        rec = _rec_produtos_baixa_saida(df_base)
        # "Cabernet" é da categoria "vinhos" com qtd=1 — NÃO deve aparecer
        if rec is not None:
            # Título pode dizer "exceto vinhos" — isso é correto; Cabernet não deve aparecer como produto
            assert "Cabernet" not in rec.titulo

    def test_produto_nao_vinho_com_1_venda_entra(self, df_base):
        # "Skol" categoria "Cervejas" com qtd=1 — DEVE entrar
        rec = _rec_produtos_baixa_saida(df_base)
        assert rec is not None

    def test_descricao_menciona_exclusao_vinhos(self, df_base):
        rec = _rec_produtos_baixa_saida(df_base)
        if rec is not None:
            assert "vinho" in rec.descricao.lower() or "Vinho" in rec.descricao


class TestPrioridades:
    def test_custo_zerado_e_alta_prioridade(self, df_base):
        recs = generate_recommendations(df_base, {}, [])
        custo_recs = [r for r in recs if r.tipo.value == "custo"]
        assert all(r.prioridade == Priority.alta for r in custo_recs)

    def test_pix_e_alta_prioridade(self, df_base):
        df = df_base.copy()
        df["metodo_pagamento"] = "Cartão"
        rec = _rec_pix_baixo(df)
        assert rec is not None
        assert rec.prioridade == Priority.alta

    def test_baixa_saida_e_media_prioridade(self, df_base):
        rec = _rec_produtos_baixa_saida(df_base)
        if rec:
            assert rec.prioridade == Priority.media


class TestOrdenacao:
    def test_alta_antes_de_media(self, df_base):
        recs = generate_recommendations(df_base, {}, [])
        prioridades = [r.prioridade for r in recs]
        _order = {Priority.alta: 0, Priority.media: 1, Priority.baixa: 2}
        numeros = [_order[p] for p in prioridades]
        assert numeros == sorted(numeros)

    def test_todas_recomendacoes_tem_base_analisada(self, df_base):
        recs = generate_recommendations(df_base, {}, [])
        for r in recs:
            assert "Base analisada:" in r.descricao, (
                f"Recomendação '{r.titulo}' não tem 'Base analisada' na descrição"
            )

    def test_todas_recomendacoes_tem_impacto(self, df_base):
        recs = generate_recommendations(df_base, {}, [])
        for r in recs:
            assert r.impacto_estimado, f"'{r.titulo}' sem impacto_estimado"
