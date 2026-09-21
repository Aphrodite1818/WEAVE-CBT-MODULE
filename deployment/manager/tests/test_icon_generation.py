from __future__ import annotations

import importlib.util
from pathlib import Path


def test_windows_icon_builder_produces_multiresolution_ico(tmp_path, monkeypatch):
    manager_root = Path(__file__).resolve().parents[1]
    script_path = manager_root / "build" / "create_icon.py"
    assert script_path.is_file()

    spec = importlib.util.spec_from_file_location("weave_create_icon", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    destination = manager_root / "resources" / "weave.ico"
    destination.unlink(missing_ok=True)
    try:
        assert module.main() == 0
        payload = destination.read_bytes()
        # ICONDIR: reserved=0, type=1, then the image count.
        assert payload[:4] == b"\x00\x00\x01\x00"
        assert int.from_bytes(payload[4:6], "little") == len(module.SIZES)
        assert len(payload) > 1024
    finally:
        destination.unlink(missing_ok=True)
