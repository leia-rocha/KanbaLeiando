"""Testes de configuracao por ambiente (RF07, secao 16.3)."""

from __future__ import annotations

import pytest

from app.config import Settings


def test_producao_falha_sem_segredos():
    s = Settings(app_env="production")
    with pytest.raises(RuntimeError) as exc:
        s.validate_for_runtime()
    assert "critica" in str(exc.value).lower()


def test_producao_nao_aceita_emulador():
    s = Settings(
        app_env="production",
        google_cloud_project="p",
        firebase_project_id="p",
        firebase_web_api_key="k",
        firebase_auth_domain="d",
        gcs_bucket_name="b",
        admin_user="u",
        admin_password="pw",
        admin_session_secret="s1",
        public_link_secret="s2",
        firestore_emulator_host="localhost:8080",
    )
    with pytest.raises(RuntimeError) as exc:
        s.validate_for_runtime()
    assert "emulador" in str(exc.value).lower()


def test_segredos_devem_ser_distintos():
    s = Settings(
        app_env="production",
        google_cloud_project="p",
        firebase_project_id="p",
        firebase_web_api_key="k",
        firebase_auth_domain="d",
        gcs_bucket_name="b",
        admin_user="u",
        admin_password="pw",
        admin_session_secret="same",
        public_link_secret="same",
    )
    with pytest.raises(RuntimeError):
        s.validate_for_runtime()


def test_desenvolvimento_sobe_sem_segredos():
    s = Settings(app_env="development")
    s.validate_for_runtime()  # nao lanca
