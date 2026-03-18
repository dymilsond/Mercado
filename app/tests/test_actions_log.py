from __future__ import annotations

import json
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pytest

# Patch do caminho do log para usar arquivo temporário nos testes
import services.actions_log as _mod


@pytest.fixture(autouse=True)
def tmp_log(tmp_path, monkeypatch):
    """Redireciona o log para um arquivo temporário em cada teste."""
    log_file = tmp_path / "actions_log.json"
    monkeypatch.setattr(_mod, "_LOG_FILE", log_file)
    return log_file


from services.actions_log import (
    atualizar_resultado,
    get_all,
    get_pendentes,
    registrar_acao,
)


class TestRegistrarAcao:
    def test_cria_arquivo_se_nao_existir(self, tmp_log):
        assert not tmp_log.exists()
        registrar_acao("custo", "Teste", "Descricao", "admin")
        assert tmp_log.exists()

    def test_grava_acao_corretamente(self, tmp_log):
        registrar_acao("pix", "PIX baixo", "Ação A", "admin")
        acoes = get_all()
        assert len(acoes) == 1
        assert acoes[0]["tipo"] == "pix"
        assert acoes[0]["titulo"] == "PIX baixo"
        assert acoes[0]["usuario"] == "admin"

    def test_ids_incrementais(self, tmp_log):
        registrar_acao("a", "T1", "D1", "u1")
        registrar_acao("b", "T2", "D2", "u2")
        acoes = get_all()
        ids = [a["id"] for a in acoes]
        assert ids == [1, 2]

    def test_resultado_padrao_pendente(self, tmp_log):
        registrar_acao("mix", "T", "D", "u")
        assert get_all()[0]["resultado"] == "pendente"
        assert get_all()[0]["resolvido"] is False

    def test_multiplas_acoes_acumulam(self, tmp_log):
        for i in range(5):
            registrar_acao("tipo", f"Titulo {i}", "Desc", "admin")
        assert len(get_all()) == 5


class TestGetAll:
    def test_retorna_lista_vazia_sem_arquivo(self, tmp_log):
        assert get_all() == []

    def test_retorna_lista_com_dados(self, tmp_log):
        registrar_acao("custo", "T", "D", "u")
        assert len(get_all()) == 1


class TestGetPendentes:
    def test_retorna_apenas_pendentes(self, tmp_log):
        registrar_acao("custo", "T1", "D1", "u")
        registrar_acao("pix",   "T2", "D2", "u")
        atualizar_resultado(1, "feito", resolvido=True)
        pendentes = get_pendentes()
        assert len(pendentes) == 1
        assert pendentes[0]["titulo"] == "T2"


class TestAtualizarResultado:
    def test_atualiza_resultado(self, tmp_log):
        registrar_acao("custo", "T", "D", "u")
        atualizar_resultado(1, "implementado", resolvido=True)
        acoes = get_all()
        assert acoes[0]["resultado"] == "implementado"
        assert acoes[0]["resolvido"] is True

    def test_data_atualizacao_preenchida(self, tmp_log):
        registrar_acao("custo", "T", "D", "u")
        atualizar_resultado(1, "ok")
        assert "data_atualizacao" in get_all()[0]

    def test_id_inexistente_nao_quebra(self, tmp_log):
        registrar_acao("custo", "T", "D", "u")
        try:
            atualizar_resultado(999, "ok")
        except Exception as e:
            pytest.fail(f"Não deveria quebrar: {e}")


class TestJsonVazio:
    def test_nao_quebra_com_json_vazio(self, tmp_log):
        tmp_log.write_text("[]")
        assert get_all() == []

    def test_nao_quebra_com_json_corrompido(self, tmp_log):
        tmp_log.write_text("{invalid json")
        # deve retornar lista vazia graciosamente
        result = get_all()
        assert result == []
