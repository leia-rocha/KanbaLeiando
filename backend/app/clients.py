"""Inicializacao dos clientes Firebase/Google Cloud.

Em producao usa Application Default Credentials (identidade do Cloud Run), sem
chave JSON embutida na imagem. Em desenvolvimento/testes pode apontar para os
emuladores via FIRESTORE_EMULATOR_HOST e FIREBASE_AUTH_EMULATOR_HOST.
"""

from __future__ import annotations

import os
from functools import lru_cache

import firebase_admin
from firebase_admin import auth as fb_auth
from firebase_admin import credentials, firestore
from google.cloud import storage

from app.config import Settings, get_settings


def _ensure_emulator_env(settings: Settings) -> None:
    """Exporta as variaveis dos emuladores para os SDKs, apenas fora de producao."""
    if settings.is_production:
        return
    if settings.firestore_emulator_host:
        os.environ.setdefault("FIRESTORE_EMULATOR_HOST", settings.firestore_emulator_host)
    if settings.firebase_auth_emulator_host:
        os.environ.setdefault(
            "FIREBASE_AUTH_EMULATOR_HOST", settings.firebase_auth_emulator_host
        )
    if settings.storage_emulator_host:
        os.environ.setdefault("STORAGE_EMULATOR_HOST", settings.storage_emulator_host)


@lru_cache
def get_firebase_app() -> firebase_admin.App:
    settings = get_settings()
    _ensure_emulator_env(settings)
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass

    project_id = settings.firebase_project_id or settings.google_cloud_project or None
    options: dict[str, str] = {}
    if project_id:
        options["projectId"] = project_id
    if settings.gcs_bucket_name:
        options["storageBucket"] = settings.gcs_bucket_name
    if settings.firebase_service_account_id:
        options["serviceAccountId"] = settings.firebase_service_account_id

    # ADC: sem chave embutida. Em emulador o Admin SDK aceita credencial anonima.
    cred = credentials.ApplicationDefault() if not settings.using_emulators else None
    return firebase_admin.initialize_app(cred, options or None)


@lru_cache
def get_firestore_client() -> firestore.Client:
    get_firebase_app()
    return firestore.client()


@lru_cache
def get_auth_client():
    get_firebase_app()
    return fb_auth


@lru_cache
def get_storage_client() -> storage.Client:
    settings = get_settings()
    _ensure_emulator_env(settings)
    project = settings.google_cloud_project or settings.firebase_project_id or None
    return storage.Client(project=project)


def get_bucket():
    settings = get_settings()
    client = get_storage_client()
    return client.bucket(settings.gcs_bucket_name)


def reset_clients_cache() -> None:
    """Util para testes: limpa caches de cliente."""
    get_firebase_app.cache_clear()
    get_firestore_client.cache_clear()
    get_auth_client.cache_clear()
    get_storage_client.cache_clear()
