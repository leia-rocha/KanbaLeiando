"""Configuracao publica e saude (GET /config, GET /healthz)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.deps import get_current_user
from app.schemas.auth import MeResponse, PublicConfig

router = APIRouter()


@router.get("/config", response_model=PublicConfig)
def get_config(settings: Settings = Depends(get_settings)) -> PublicConfig:
    """Somente configuracao publica Firebase e parametros de UI (secao 15.3)."""
    return PublicConfig(
        firebaseApiKey=settings.firebase_web_api_key,
        firebaseAuthDomain=settings.firebase_auth_domain,
        firebaseProjectId=settings.firebase_project_id,
        firebaseAppId=settings.firebase_web_app_id,
        appTimezone=settings.app_timezone,
        maxUploadBytes=settings.max_upload_bytes,
        appEnv=settings.app_env,
        usingEmulators=settings.using_emulators,
        firestoreEmulatorHost=settings.firestore_emulator_host or None,
        authEmulatorHost=settings.firebase_auth_emulator_host or None,
    )


@router.get("/healthz")
def healthz() -> dict:
    """Verifica o processo sem consultar todos os servicos (secao 14.1)."""
    return {"status": "ok"}


@router.get("/me", response_model=MeResponse)
def me(user=Depends(get_current_user)) -> MeResponse:
    return MeResponse(uid=user.uid, email=user.email, name=user.name, status=user.status)
