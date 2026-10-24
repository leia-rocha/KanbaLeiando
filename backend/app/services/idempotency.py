"""Chaves de idempotencia para operacoes sensiveis (secao 11.3).

Guarda o resultado da operacao para que a repeticao da mesma chave retorne o
mesmo recurso sem criar duplicatas. Nao executar efeitos externos (e-mail, copia
de arquivos) dentro da transacao que pode ser reexecutada.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from google.cloud import firestore

from app.repositories import Repo


def _key_hash(scope: str, uid: str, key: str) -> str:
    return hashlib.sha256(f"{scope}:{uid}:{key}".encode()).hexdigest()


def get_cached(repo: Repo, scope: str, uid: str, key: str | None) -> dict[str, Any] | None:
    if not key:
        return None
    snap = repo.idempotency_ref(_key_hash(scope, uid, key)).get()
    if snap.exists:
        data = snap.to_dict() or {}
        return data.get("result")
    return None


def store(repo: Repo, scope: str, uid: str, key: str | None, result: dict[str, Any]) -> None:
    if not key:
        return
    repo.idempotency_ref(_key_hash(scope, uid, key)).set(
        {
            "scope": scope,
            "uid": uid,
            "result": json.loads(json.dumps(result, default=str)),
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
    )
