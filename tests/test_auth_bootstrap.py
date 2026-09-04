from __future__ import annotations

import pytest

from modoor.platform.bootstrap import bootstrap
from modoor.core.ctx import Ctx
from modoor.core.db import init_db, session_scope
from modoor.core.errors import AppError
from modoor.platform.module_state import list_modules, set_module_enabled, sync_discovered_modules
from modoor.core.settings import get_settings
from modules.base import domain as base_domain
from modules.wiki import domain as wiki_domain


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'auth.db'}")
    monkeypatch.setenv("MODOOR_API_KEY", "test-key")
    monkeypatch.setenv("MODOOR_TENANT", "demo")
    monkeypatch.delenv("MODOOR_USER_ID", raising=False)
    monkeypatch.delenv("MODOOR_TEAM_ID", raising=False)
    monkeypatch.setenv("MODOOR_CONFIRM_SECRET", "secret")
    monkeypatch.setenv("MODOOR_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("MODOOR_ADMIN_PASSWORD", "admin123")
    get_settings.cache_clear()
    init_db(get_settings())
    yield
    get_settings.cache_clear()


def test_bootstrap_login_and_module_toggle():
    result = bootstrap(get_settings())
    assert result["admin_username"] == "admin"
    assert result["tenant_id"]
    assert result["team_id"]

    with session_scope() as session:
        tenant_id = result["tenant_id"]
        user = base_domain.authenticate_user(
            session, tenant=tenant_id, username="admin", password="admin123"
        )
        assert user.username == "admin"
        assert user.team_id == result["team_id"]

        with pytest.raises(AppError):
            base_domain.authenticate_user(
                session, tenant=tenant_id, username="admin", password="wrong"
            )

        sync_discovered_modules(session, tenant_id)
        modules = {m["id"]: m for m in list_modules(session, tenant_id)}
        assert modules["base"]["enabled"] is True
        assert modules["base"]["always_on"] is True

        set_module_enabled(session, tenant_id, "wiki", False)
        modules = {m["id"]: m for m in list_modules(session, tenant_id)}
        assert modules["wiki"]["enabled"] is False

        with pytest.raises(AppError):
            set_module_enabled(session, tenant_id, "base", False)

        ctx = Ctx(tenant=tenant_id, user_id=user.id, team_id=user.team_id)
        projects = wiki_domain.list_projects(session, ctx)
        assert projects["count"] >= 1
        home_id = projects["items"][0]["home_page_id"]
        assert home_id
        welcome = wiki_domain.get_page(session, ctx, page_id=home_id)
        assert welcome["title"]
