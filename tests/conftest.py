"""Make `custom_components.bapp_auto.models` importable without Home Assistant.

The package __init__ imports Home Assistant, so the two package levels are
registered as bare namespace modules and only the pure modules get imported.
"""

import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG_DIR = ROOT / "custom_components" / "bapp_auto"

for name, path in (("custom_components", ROOT / "custom_components"), ("custom_components.bapp_auto", PKG_DIR)):
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.__path__ = [str(path)]  # type: ignore[attr-defined]
        sys.modules[name] = module
