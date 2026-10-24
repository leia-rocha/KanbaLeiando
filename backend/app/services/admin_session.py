"""Sessao administrativa opaca e revogavel (RF07, secao 15.3).

Compara credenciais com tratamento seguro (comparacao em tempo constante),
emite sessao curta com cookie Secure/HttpOnly/SameSite, protege por CSRF e
vincula a versao das credenciais de ambiente. Rate limit e persistido no
Firestore para sobreviver a multiplas instancias e reinicios.
"""

from __future__ import annotations

import hashlib
import hmac

from google.cloud import firestore

from app.config import get_settings
from app.errors import RateLimitError, UnauthorizedError
from app.repositories import Repo
from app.utils.ids import new_id
from app.utils.timeutils import to_iso_utc, utc_now

COOKIE_NAME = "kanba_admin_session"
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 300


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def credentials_version() -> str:
    """Muda quando as credenciais/segredo mudam, invalidando sessoes antigas."""
    settings = get_settings()
    material = f"{settings.admin_user}:{settings.admin_password}:{settings.admin_session_secret}"
    return _hash(material)[:16]


def _constant_time_check(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def check_rate_limit(repo: Repo, ip_key: str) -> None:
    ref = repo.rate_limit_ref(_hash(f"admin_login:{ip_key}"))
    now = utc_now()

    @firestore.transactional
    def _txn(txn):
        snap = ref.get(transaction=txn)
        data = snap.to_dict() if snap.exists else {}
        window_start = data.get("windowStart")
        count = int(data.get("count", 0))
        if window_start is not None:
            elapsed = (now - window_start).total_seconds() if hasattr(window_start, "year") else 0
            if elapsed > _WINDOW_SECONDS:
                count = 0
        if count >= _MAX_ATTEMPTS:
            raise RateLimitError("Muitas tentativas de login. Aguarde alguns minutos.")
        txn.set(
            ref,
            {
                "count": count + 1,
                "windowStart": window_start or now,
                "updatedAt": firestore.SERVER_TIMESTAMP,
                "expiresAt": now,
            },
        )

    _txn(repo.db.transaction())


def authenticate(repo: Repo, username: str, password: str, ip_key: str) -> tuple[str, str, str]:
    """Valida credenciais e cria uma sessao. Retorna (token_sessao, csrf, expiresAt_iso)."""
    settings = get_settings()
    check_rate_limit(repo, ip_key)
    user_ok = _constant_time_check(username, settings.admin_user)
    pass_ok = _constant_time_check(password, settings.admin_password)
    if not (user_ok and pass_ok) or not settings.admin_user:
        raise UnauthorizedError("Credenciais administrativas invalidas.")

    session_token = new_id("adm_", 40)
    csrf_token = new_id("csrf_", 32)
    expires = utc_now()
    from datetime import timedelta

    expires_at = expires + timedelta(seconds=settings.admin_session_ttl_seconds)
    repo.admin_session_ref(_hash(session_token)).set(
        {
            "csrfHash": _hash(csrf_token),
            "credVersion": credentials_version(),
            "createdAt": firestore.SERVER_TIMESTAMP,
            "expiresAt": expires_at,
        }
    )
    return session_token, csrf_token, to_iso_utc(expires_at)


def validate_session(repo: Repo, session_token: str | None, csrf_header: str | None, *,
                     require_csrf: bool) -> None:
    if not session_token:
        raise UnauthorizedError("Sessao administrativa ausente.")
    ref = repo.admin_session_ref(_hash(session_token))
    snap = ref.get()
    if not snap.exists:
        raise UnauthorizedError("Sessao administrativa invalida.")
    data = snap.to_dict() or {}
    # Mudanca de credencial/segredo invalida sessoes antigas.
    if data.get("credVersion") != credentials_version():
        ref.delete()
        raise UnauthorizedError("Sessao expirada por mudanca de configuracao.")
    expires_at = data.get("expiresAt")
    if expires_at is not None and hasattr(expires_at, "year"):
        if utc_now() >= expires_at:
            ref.delete()
            raise UnauthorizedError("Sessao administrativa expirada.")
    if require_csrf:
        if not csrf_header or data.get("csrfHash") != _hash(csrf_header):
            raise UnauthorizedError("Token CSRF invalido.")


def revoke_session(repo: Repo, session_token: str | None) -> None:
    if not session_token:
        return
    repo.admin_session_ref(_hash(session_token)).delete()
