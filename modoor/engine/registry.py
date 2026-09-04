"""Load model bundles: modules/<id>/models/<name>/{config,tables,inputs}.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from modoor.core.settings import Settings, get_settings


@dataclass
class ModelBundle:
    uukey: str
    module_id: str
    path: Path
    config: dict[str, Any]
    tables: dict[str, Any] = field(default_factory=dict)
    inputs: dict[str, Any] = field(default_factory=dict)

    @property
    def model(self) -> dict[str, Any]:
        return dict(self.config.get("model") or {})

    @property
    def groups(self) -> dict[str, Any]:
        return dict(self.config.get("groups") or {})

    @property
    def fields(self) -> dict[str, Any]:
        return dict(self.config.get("fields") or {})

    @property
    def clicks(self) -> dict[str, Any]:
        return dict(self.config.get("clicks") or {})


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def discover_bundles(settings: Settings | None = None) -> dict[str, ModelBundle]:
    settings = settings or get_settings()
    root = Path(settings.modoor_modules_root)
    out: dict[str, ModelBundle] = {}
    if not root.is_dir():
        return out
    for module_dir in sorted(root.iterdir()):
        if not module_dir.is_dir():
            continue
        models_dir = module_dir / "models"
        if not models_dir.is_dir():
            continue
        for model_dir in sorted(models_dir.iterdir()):
            if not model_dir.is_dir():
                continue
            config_path = model_dir / "config.json"
            if not config_path.is_file():
                continue
            config = _read_json(config_path)
            model_meta = config.get("model") or {}
            uukey = str(model_meta.get("uukey") or "").strip()
            if not uukey:
                continue
            out[uukey] = ModelBundle(
                uukey=uukey,
                module_id=module_dir.name,
                path=model_dir,
                config=config,
                tables=_read_json(model_dir / "tables.json"),
                inputs=_read_json(model_dir / "inputs.json"),
            )
    return out


@lru_cache
def bundled_models() -> dict[str, ModelBundle]:
    return discover_bundles()


def clear_bundle_cache() -> None:
    bundled_models.cache_clear()


def get_bundle(model: str) -> ModelBundle:
    bundles = bundled_models()
    if model not in bundles:
        # allow cache stale after new files in tests
        clear_bundle_cache()
        bundles = bundled_models()
    if model not in bundles:
        raise KeyError(f"unknown model: {model}")
    return bundles[model]
