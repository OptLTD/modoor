from __future__ import annotations

import json

import pytest

from modoor.core.db import init_db
from modoor.core.settings import get_settings
from modoor.platform.bootstrap import bootstrap
from modules.base.tools import (
    assign_role,
    create_app,
    create_role,
    create_user,
    delete_app,
    list_user_roles,
)


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'base.db'}")
    monkeypatch.setenv("MODOOR_API_KEY", "test-key")
    monkeypatch.setenv("MODOOR_TENANT", "t1")
    monkeypatch.setenv("MODOOR_CONFIRM_SECRET", "secret")
    get_settings.cache_clear()
    init_db(get_settings())
    bootstrap(get_settings())
    yield
    get_settings.cache_clear()


def test_app_user_role_assign():
    app = json.loads(create_app(code="crm", name="CRM"))
    assert app["status"] == "ok"
    app_id = app["result"]["id"]

    user = json.loads(create_user(username="Alice", realname="Alice Chen"))
    assert user["result"]["username"] == "alice"
    user_id = user["result"]["id"]

    role = json.loads(
        create_role(code="admin", name="Admin", app_id=app_id)
    )
    assert role["status"] == "ok"
    role_id = role["result"]["id"]

    assigned = json.loads(assign_role(user_id=user_id, role_id=role_id))
    assert assigned["status"] == "ok"

    roles = json.loads(list_user_roles(user_id=user_id))
    assert roles["result"]["count"] == 1
    assert roles["result"]["roles"][0]["code"] == "admin"

    # cannot delete app with roles
    blocked = json.loads(delete_app(app_id=app_id, confirmation_token=None))
    # first call is needs_confirmation
    assert blocked["status"] == "needs_confirmation"
    token = blocked["confirmation_token"]
    failed = json.loads(delete_app(app_id=app_id, confirmation_token=token))
    assert failed["status"] == "error"
    assert failed["error"]["code"] == "conflict"
