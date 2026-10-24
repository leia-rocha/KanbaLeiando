"""Configuracao tipada por ambiente.

Todos os parametros operacionais do KanbaLeiando sao lidos aqui, a partir de
variaveis de ambiente (ver .env.example na raiz). A aplicacao falha na
inicializacao quando falta configuracao critica de producao, em vez de assumir
valores padrao inseguros (RF07, secao 16.3 da especificacao).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["development", "test", "staging", "production"]


class Settings(BaseSettings):
    """Configuracao global da aplicacao."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Ambiente e rede ---
    app_env: AppEnv = Field(default="development")
    app_base_url: str = Field(default="http://localhost:8080")
    app_timezone: str = Field(default="America/Sao_Paulo")
    port: int = Field(default=8080)

    # --- Projeto Google / Firebase ---
    google_cloud_project: str = Field(default="")
    firebase_project_id: str = Field(default="")
    firebase_service_account_id: str = Field(default="")
    # Valores PUBLICOS do Firebase web (podem chegar ao cliente via /config).
    firebase_web_api_key: str = Field(default="")
    firebase_auth_domain: str = Field(default="")
    firebase_web_app_id: str = Field(default="")

    # --- Storage de anexos ---
    gcs_bucket_name: str = Field(default="")

    # --- Admin (secretos) ---
    admin_user: str = Field(default="")
    admin_password: str = Field(default="")
    admin_session_secret: str = Field(default="")
    admin_session_ttl_seconds: int = Field(default=3600)

    # --- Link publico ---
    public_link_secret: str = Field(default="")

    # --- SMTP (secretos) ---
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from: str = Field(default="")
    smtp_use_tls: bool = Field(default=True)

    # --- Cloud Tasks ---
    cloud_tasks_location: str = Field(default="")
    cloud_tasks_queue: str = Field(default="")
    tasks_service_account_email: str = Field(default="")
    tasks_audience: str = Field(default="")

    # --- Limites ---
    max_upload_bytes: int = Field(default=20_000_000)
    preview_timeout_seconds: int = Field(default=45)
    signed_url_ttl_seconds: int = Field(default=300)

    # --- Emuladores (apenas dev/test) ---
    firestore_emulator_host: str = Field(default="")
    firebase_auth_emulator_host: str = Field(default="")
    storage_emulator_host: str = Field(default="")

    # --- CORS (origens permitidas em desenvolvimento) ---
    cors_allow_origins: str = Field(default="http://localhost:5173,http://localhost:8080")

    @field_validator("app_env", mode="before")
    @classmethod
    def _normalize_env(cls, value: str) -> str:
        return (value or "development").strip().lower()

    @property
    def is_production(self) -> bool:
        return self.app_env in ("staging", "production")

    @property
    def using_emulators(self) -> bool:
        return bool(self.firestore_emulator_host or self.firebase_auth_emulator_host)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    def critical_missing(self) -> list[str]:
        """Lista de variaveis criticas ausentes para o ambiente de producao."""
        required = {
            "google_cloud_project": self.google_cloud_project,
            "firebase_project_id": self.firebase_project_id,
            "firebase_web_api_key": self.firebase_web_api_key,
            "firebase_auth_domain": self.firebase_auth_domain,
            "gcs_bucket_name": self.gcs_bucket_name,
            "admin_user": self.admin_user,
            "admin_password": self.admin_password,
            "admin_session_secret": self.admin_session_secret,
            "public_link_secret": self.public_link_secret,
        }
        return [name for name, value in required.items() if not value]

    def validate_for_runtime(self) -> None:
        """Garante que producao nao sobe sem segredos e nao usa emulador."""
        if self.is_production:
            missing = self.critical_missing()
            if missing:
                raise RuntimeError(
                    "Configuracao critica ausente em producao: " + ", ".join(sorted(missing))
                )
            if self.using_emulators:
                raise RuntimeError(
                    "Emuladores Firebase nao podem ser usados em producao. "
                    "Remova FIRESTORE_EMULATOR_HOST e FIREBASE_AUTH_EMULATOR_HOST."
                )
            if self.admin_session_secret == self.public_link_secret:
                raise RuntimeError(
                    "ADMIN_SESSION_SECRET e PUBLIC_LINK_SECRET devem ser distintos."
                )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_for_runtime()
    return settings
