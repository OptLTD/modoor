from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_platform_root() -> Path:
    # modoor/core/settings.py → repo root
    return Path(__file__).resolve().parents[2] / "platform"


def _default_modules_root() -> Path:
    # modoor/core/settings.py → repo root
    return Path(__file__).resolve().parents[2] / "modules"


def _split_pipe(raw: str) -> tuple[str, str | None]:
    """Split `left|right`; returns (left, right_or_None)."""
    text = (raw or "").strip()
    if "|" not in text:
        return text, None
    left, right = text.split("|", 1)
    return left.strip(), right


def _expand_module_urls(raw: str, *, host: str) -> str:
    """Expand short `base=5175` entries to `base=http://{host}:5175`."""
    parts: list[str] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        mid, target = part.split("=", 1)
        mid = mid.strip()
        target = target.strip().rstrip("/")
        if not mid or not target:
            continue
        if target.isdigit():
            target = f"http://{host}:{target}"
        elif "://" not in target and target.startswith(":"):
            target = f"http://{host}{target}"
        parts.append(f"{mid}={target}")
    return ",".join(parts)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    modoor_api_key: str = Field(default="dev-key-change-me", alias="MODOOR_API_KEY")
    # `id|name` (preferred) or plain name. After load, modoor_tenant is always the name.
    # Example: MODOOR_TENANT=1000|TENANT_NAME → tenant_id=1000, tenant="TENANT_NAME"
    modoor_tenant: str = Field(default="demo", alias="MODOOR_TENANT")
    modoor_tenant_id: int | None = Field(default=None)
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
    modoor_platform_root: Path = Field(
        default_factory=_default_platform_root,
        alias="MODOOR_PLATFORM_ROOT",
        description="Builtin platform modules (base/doc/wiki/skill).",
    )
    modoor_modules_root: Path = Field(
        default_factory=_default_modules_root,
        alias="MODOOR_MODULES_ROOT",
        description="Business modules (sale/crm/…).",
    )
    # Derived from MODOOR_WEBUI_URL (no separate env needed).
    modoor_web_host: str = Field(default="127.0.0.1")
    modoor_web_port: int = Field(default=8765)
    modoor_session_secret: str = Field(
        default="dev-session-secret-change-me",
        alias="MODOOR_SESSION_SECRET",
    )
    modoor_webui_url: str = Field(
        default="http://127.0.0.1:8765",
        alias="MODOOR_WEBUI_URL",
        description="Public console / login host (template shell on API). Also sets listen host/port.",
    )
    # Short form: base=5175,wiki=5176 (host from WEBUI_URL). Full URLs still accepted.
    modoor_module_urls: str = Field(
        default="base=5175,wiki=5176,sale=5177,skill=5178,doc=5179,fleet=5180,transport=5181",
        alias="MODOOR_MODULE_URLS",
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
    # base=5175,wiki=5176 (same short form as MODULE_URLS)
    modoor_webui_proxies: str = Field(
        default="",
        alias="MODOOR_WEBUI_PROXIES",
    )
    # Preview/prod: mount modules/*/webui/dist (comma ids; empty = all with dist)
    modoor_webui_static_modules: str = Field(
        default="",
        alias="MODOOR_WEBUI_STATIC_MODULES",
    )
    # `username|password` (preferred). Falls back to USERNAME/PASSWORD fields.
    # Example: MODOOR_ADMIN=admin|ADMIN_PASSWORD
    modoor_admin: str | None = Field(default=None, alias="MODOOR_ADMIN")
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

    @model_validator(mode="after")
    def _normalize_tenant_admin_webui(self) -> Settings:
        raw_tenant = (self.modoor_tenant or "").strip() or "demo"
        left, right = _split_pipe(raw_tenant)
        tenant_id = self.modoor_tenant_id
        name = raw_tenant
        if right is not None:
            if left.isdigit() and right.strip():
                tenant_id = int(left)
                name = right.strip()
            elif right.strip():
                name = left or raw_tenant
            else:
                name = left or "demo"
        object.__setattr__(self, "modoor_tenant", name)
        object.__setattr__(self, "modoor_tenant_id", tenant_id)

        raw_admin = (self.modoor_admin or "").strip()
        if raw_admin:
            user, password = _split_pipe(raw_admin)
            if password is not None:
                if user:
                    object.__setattr__(self, "modoor_admin_username", user)
                object.__setattr__(self, "modoor_admin_password", password)
            elif user:
                object.__setattr__(self, "modoor_admin_username", user)

        parsed = urlparse((self.modoor_webui_url or "").strip() or "http://127.0.0.1:8765")
        host = parsed.hostname or "127.0.0.1"
        if parsed.port is not None:
            port = parsed.port
        else:
            port = 443 if parsed.scheme == "https" else 80
        object.__setattr__(self, "modoor_web_host", host)
        object.__setattr__(self, "modoor_web_port", port)

        expanded = _expand_module_urls(self.modoor_module_urls, host=host)
        object.__setattr__(self, "modoor_webui_module_urls", expanded)
        if self.modoor_webui_proxies:
            object.__setattr__(
                self,
                "modoor_webui_proxies",
                _expand_module_urls(self.modoor_webui_proxies, host=host),
            )
        return self

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

    @field_validator("modoor_user_id", "modoor_team_id", "modoor_tenant_id", mode="before")
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
