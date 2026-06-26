from __future__ import annotations

import re
from pathlib import Path

_APP_IMPORT = re.compile(r"^\s*(from|import)\s+(goldsilver|quantum)\b", re.MULTILINE)


def test_marketcore_never_imports_an_app() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "marketcore"
    offenders = [
        str(py.relative_to(root))
        for py in root.rglob("*.py")
        if _APP_IMPORT.search(py.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"marketcore must not import an app package: {offenders}"
