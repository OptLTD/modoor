"""Platform modules package (base / doc / wiki / skill).

The directory name matches the product layer ("platform"), which collides with the
stdlib ``platform`` module. Re-export stdlib public names so
``import platform; platform.system()`` keeps working for dependencies.
"""

from __future__ import annotations

import importlib.util
import sys
import sysconfig
from pathlib import Path
from types import ModuleType

__all__ = []  # extended below with stdlib exports


def _load_stdlib_platform() -> ModuleType:
    stdlib = Path(sysconfig.get_path("stdlib"))
    path = stdlib / "platform.py"
    spec = importlib.util.spec_from_file_location("_modoor_stdlib_platform", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load stdlib platform from {path}")
    mod = importlib.util.module_from_spec(spec)
    # Avoid putting it in sys.modules as "platform"
    spec.loader.exec_module(mod)
    return mod


_stdlib = _load_stdlib_platform()
for _name in dir(_stdlib):
    if _name.startswith("_") and _name not in {"__version__", "__doc__"}:
        continue
    globals()[_name] = getattr(_stdlib, _name)
    if not _name.startswith("_"):
        __all__.append(_name)

# Subpackages (base/doc/…) are loaded via normal package import machinery.
