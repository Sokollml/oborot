"""Загрузка scoring_config.yaml (один раз за процесс)."""

import os
from functools import cache
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "scoring_config.yaml"


@cache
def config() -> dict[str, Any]:
    path = Path(os.environ.get("SCORING_CONFIG_PATH", DEFAULT_PATH))
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)
