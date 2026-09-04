from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_modules_root() -> Path:
    # modoor/core/settings.py → repo root
    return Path(__file__).resolve().parents[2] / "modules"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    modoor_api_key: str = Field(default="dev-key-change-me", alias="MODOOR_API_KEY")
    # Tenant display name; bootstrap resolves / creates int id + same-named root team.
    modoor_tenant: str = Field(default="demo", alias="MODOOR_TENANT")
    # Optional int overrides for API-key ctx (default: first admin / root team after bootstrap).
    modoor_user_id: int | None = Field(default=None, alias="MODOOR_USER_ID")
    modoor_team_id: int | None = Field(default=None, alias="MODOOR_TEAM_ID")
    modoor_confirm_secret: str = Field(
        default="dev-confirm-secret-change-me",
        alias="MODOOR_CONFIRM_SECRET",
    )
    modoor_confirm_ttl_seconds: int = Field(default=600, alias="MODOOR_CONFIRM_TTL_SECONDS")
    database_url: str = Field(
        default="postgresql+psycopg://modoor:modoor@127.0.0.1:5432/modoor",
        alias="DATABASE_URL",
    )
    modoor_modules_root: Path = Field(
        default_factory=_default_modules_root,
        alias="MODOOR_MODULES_ROOT",
    )
    modoor_web_host: str = Field(default="127.0.0.1", alias="MODOOR_WEB_HOST")
    modoor_web_port: int = Field(default=8765, alias="MODOOR_WEB_PORT")
    modoor_session_secret: str = Field(
        default="dev-session-secret-change-me",
        alias="MODOOR_SESSION_SECRET",
    )
    modoor_webui_url: str = Field(
        default="http://127.0.0.1:8765",
        alias="MODOOR_WEBUI_URL",
        description="Public console / login host (template shell on API).",
    )
    # moduleId=devUrl pairs
    modoor_webui_module_urls: str = Field(
        default=(
            "base=http://127.0.0.1:5175,wiki=http://127.0.0.1:5176,"
            "sale=http://127.0.0.1:5177,skill=http://127.0.0.1:5178,"
            "doc=http://127.0.0.1:5179"
        ),
        alias="MODOOR_WEBUI_MODULE_URLS",
    )
    # doc module blob storage: local | s3 | minio (v1 implements local only)
    modoor_doc_storage: str = Field(default="local", alias="MODOOR_DOC_STORAGE")
    modoor_doc_local_root: Path = Field(
        default=Path("./data/doc"),
        alias="MODOOR_DOC_LOCAL_ROOT",
    )
    modoor_doc_s3_endpoint: str = Field(default="", alias="MODOOR_DOC_S3_ENDPOINT")
    modoor_doc_s3_bucket: str = Field(default="", alias="MODOOR_DOC_S3_BUCKET")
    modoor_doc_s3_access_key: str = Field(default="", alias="MODOOR_DOC_S3_ACCESS_KEY")
    modoor_doc_s3_secret_key: str = Field(default="", alias="MODOOR_DOC_S3_SECRET_KEY")
    modoor_doc_s3_region: str = Field(default="", alias="MODOOR_DOC_S3_REGION")
    modoor_doc_s3_prefix: str = Field(default="doc/", alias="MODOOR_DOC_S3_PREFIX")
    # Dev/preview: reverse-proxy module frontends on the API port, e.g.
    # base=http://127.0.0.1:5175,wiki=http://127.0.0.1:5176
    modoor_webui_proxies: str = Field(
        default="",
        alias="MODOOR_WEBUI_PROXIES",
    )
    # Preview/prod: mount modules/*/webui/dist (comma ids; empty = all with dist)
    modoor_webui_static_modules: str = Field(
        default="",
        alias="MODOOR_WEBUI_STATIC_MODULES",
    )
    modoor_admin_username: str = Field(
        default="admin", alias="MODOOR_ADMIN_USERNAME"
    )
    modoor_admin_password: str = Field(
        default="admin123", alias="MODOOR_ADMIN_PASSWORD"
    )
    modoor_jobs_inprocess: bool = Field(default=True, alias="MODOOR_JOBS_INPROCESS")
    modoor_jobs_poll_seconds: float = Field(default=0.5, alias="MODOOR_JOBS_POLL_SECONDS")
    modoor_doc_ocr: bool = Field(default=True, alias="MODOOR_DOC_OCR")
    modoor_doc_ocr_max_pages: int = Field(default=20, alias="MODOOR_DOC_OCR_MAX_PAGES")

    @field_validator("database_url")
    @classmethod
    def _postgres_only(cls, v: str) -> str:
        url = (v or "").strip()
        if not url.startswith("postgresql"):
            raise ValueError(
                "DATABASE_URL must be PostgreSQL "
                "(e.g. postgresql+psycopg://modoor:modoor@127.0.0.1:5432/modoor). "
                "SQLite is not supported."
            )
        return url

    @field_validator("modoor_user_id", "modoor_team_id", mode="before")
    @classmethod
    def _empty_int_none(cls, v):
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
