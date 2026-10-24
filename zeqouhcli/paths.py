from __future__ import annotations

import hashlib
import os
import platform
from pathlib import Path

APP_NAME = "Zeqou Harness CLI"


def data_dir() -> Path:
    """Return a per-user application data directory without external dependencies."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        result = base / "Zeqou" / "HarnessCLI"
    elif platform.system() == "Darwin":
        result = Path.home() / "Library" / "Application Support" / "Zeqou" / "HarnessCLI"
    else:
        result = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "zeqou-harness-cli"
    result.mkdir(parents=True, exist_ok=True)
    try:
        if os.name != "nt":
            result.chmod(0o700)
    except OSError:
        pass
    return result


def project_key(cwd: Path) -> str:
    canonical = str(cwd.resolve()).casefold() if os.name == "nt" else str(cwd.resolve())
    return hashlib.sha256(canonical.encode("utf-8", errors="replace")).hexdigest()[:20]


def project_sessions_dir(cwd: Path) -> Path:
    result = data_dir() / "projects" / project_key(cwd) / "sessions"
    result.mkdir(parents=True, exist_ok=True)
    try:
        if os.name != "nt":
            result.chmod(0o700)
    except OSError:
        pass
    return result


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError, RuntimeError):
        return False
