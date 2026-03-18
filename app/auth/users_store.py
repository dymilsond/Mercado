from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path
from typing import Optional

_USERS_FILE = Path(__file__).resolve().parent.parent / "users.json"

# ---------------------------------------------------------------------------
# Estrutura de um usuário
# {
#   "username": str,
#   "password_hash": str,
#   "perfil": "admin" | "user",
#   "ativo": bool,
#   "nome": str,
#   "email": str
# }
# ---------------------------------------------------------------------------


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _load() -> dict[str, dict]:
    if not _USERS_FILE.exists():
        return {}
    with _USERS_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save(users: dict[str, dict]) -> None:
    _USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _USERS_FILE.open("w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Inicialização — garante que o admin padrão exista
# ---------------------------------------------------------------------------
def init_default_admin() -> None:
    users = _load()
    if "admin" not in users:
        users["admin"] = {
            "username": "admin",
            "password_hash": _hash_password("admin123"),
            "perfil": "admin",
            "ativo": True,
            "nome": "Administrador",
            "email": "admin@mercado.local",
        }
        _save(users)


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------
def get_user(username: str) -> Optional[dict]:
    return _load().get(username)


def get_all_users() -> list[dict]:
    users = _load()
    return [
        {k: v for k, v in u.items() if k != "password_hash"}
        for u in users.values()
    ]


def user_exists(username: str) -> bool:
    return username in _load()


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------
def verify_password(username: str, password: str) -> bool:
    user = get_user(username)
    if user is None:
        return False
    if not user.get("ativo", False):
        return False
    return user["password_hash"] == _hash_password(password)


# ---------------------------------------------------------------------------
# Mutações
# ---------------------------------------------------------------------------
def create_user(
    username: str,
    password: str,
    perfil: str,
    nome: str,
    email: str,
) -> None:
    users = _load()
    if username in users:
        raise ValueError(f"Usuário '{username}' já existe.")
    if perfil not in ("admin", "user"):
        raise ValueError("Perfil deve ser 'admin' ou 'user'.")
    users[username] = {
        "username": username,
        "password_hash": _hash_password(password),
        "perfil": perfil,
        "ativo": True,
        "nome": nome.strip(),
        "email": email.strip(),
    }
    _save(users)


def update_user(
    username: str,
    nome: Optional[str] = None,
    email: Optional[str] = None,
    perfil: Optional[str] = None,
) -> None:
    users = _load()
    if username not in users:
        raise ValueError(f"Usuário '{username}' não encontrado.")
    if nome is not None:
        users[username]["nome"] = nome.strip()
    if email is not None:
        users[username]["email"] = email.strip()
    if perfil is not None:
        if perfil not in ("admin", "user"):
            raise ValueError("Perfil deve ser 'admin' ou 'user'.")
        users[username]["perfil"] = perfil
    _save(users)


def set_active(username: str, ativo: bool) -> None:
    users = _load()
    if username not in users:
        raise ValueError(f"Usuário '{username}' não encontrado.")
    users[username]["ativo"] = ativo
    _save(users)


def reset_password(username: str, new_password: str) -> None:
    users = _load()
    if username not in users:
        raise ValueError(f"Usuário '{username}' não encontrado.")
    users[username]["password_hash"] = _hash_password(new_password)
    _save(users)


def generate_temp_password() -> str:
    return secrets.token_urlsafe(10)


def delete_user(username: str) -> None:
    users = _load()
    if username not in users:
        raise ValueError(f"Usuário '{username}' não encontrado.")
    if username == "admin":
        raise ValueError("Não é permitido excluir o usuário 'admin'.")
    del users[username]
    _save(users)
