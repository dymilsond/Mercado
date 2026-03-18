from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Optional

_LOG_FILE = Path(__file__).resolve().parent.parent / "data" / "actions_log.json"


def _load() -> list[dict]:
    if not _LOG_FILE.exists():
        return []
    with _LOG_FILE.open("r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _save(log: list[dict]) -> None:
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _LOG_FILE.open("w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2, default=str)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def registrar_acao(
    tipo: str,
    titulo: str,
    descricao: str,
    usuario: str,
    resultado: Optional[str] = None,
) -> None:
    log = _load()
    log.append(
        {
            "id": len(log) + 1,
            "data": datetime.now().isoformat(timespec="seconds"),
            "tipo": tipo,
            "titulo": titulo,
            "descricao": descricao,
            "usuario": usuario,
            "resultado": resultado or "pendente",
            "resolvido": False,
        }
    )
    _save(log)


def atualizar_resultado(action_id: int, resultado: str, resolvido: bool = True) -> None:
    log = _load()
    for entry in log:
        if entry["id"] == action_id:
            entry["resultado"] = resultado
            entry["resolvido"] = resolvido
            entry["data_atualizacao"] = datetime.now().isoformat(timespec="seconds")
            break
    _save(log)


def get_all() -> list[dict]:
    return _load()


def get_pendentes() -> list[dict]:
    return [e for e in _load() if not e.get("resolvido", False)]
