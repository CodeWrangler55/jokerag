from __future__ import annotations

import os
from pathlib import Path


def load_repo_env(env_path: Path | None = None) -> None:
    """Load key=value pairs from the repo root .env if present."""

    path = env_path or Path(__file__).resolve().parents[2] / ".env"
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")

