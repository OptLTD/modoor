from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modoor.core.settings import get_settings
from modoor.platform.bootstrap import bootstrap
from modoor.web.app import app
from modoor.web.nav import clear_ui_cache
from modoor.engine.registry import clear_bundle_cache
from modoor.engine.service import reload_engine_caches
from tests.conftest import configure_test_db


@pytest.fixture()
def client(monkeypatch):
    configure_test_db(
        monkeypatch,
        MODOOR_API_KEY="test-key",
        MODOOR_TENANT="demo",
        MODOOR_CONFIRM_SECRET="secret",
        MODOOR_ADMIN_USERNAME="admin",
        MODOOR_ADMIN_PASSWORD="admin123",
    )
    get_settings.cache_clear()
    clear_ui_cache()
    clear_bundle_cache()
    reload_engine_caches()
    bootstrap()
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def test_vue_shell_apis(client: TestClient):
    assert client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).status_code == 200

    users = client.get("/api/base/users")
    assert users.status_code == 200
    assert users.json()["items"]

    roles = client.get("/api/base/roles")
    assert roles.status_code == 200
    assert "roles" in roles.json()

    mods = client.get("/api/base/modules")
    assert mods.status_code == 200
    assert any(m["id"] == "base" for m in mods.json()["modules"])

    wiki = client.get("/api/wiki/pages")
    assert wiki.status_code == 200

    shell = client.get("/api/shell/modules")
    assert shell.status_code == 200
    ids = {m["id"] for m in shell.json()["modules"]}
    assert "base" in ids and "sale" in ids
