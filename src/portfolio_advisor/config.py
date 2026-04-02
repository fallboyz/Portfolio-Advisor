from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


def _find_config(start: Path | None = None) -> Path:
    """Walk up from start directory looking for config.toml."""
    current = start or Path.cwd()
    for directory in [current, *current.parents]:
        candidate = directory / "config.toml"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("config.toml not found in any parent directory")


def _find_dotenv(start: Path | None = None) -> Path | None:
    """Walk up from start directory looking for .env."""
    current = start or Path.cwd()
    for directory in [current, *current.parents]:
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


@lru_cache(maxsize=1)
def load_config(path: str | Path | None = None) -> dict:
    """Load config.toml + .env 환경 변수 오버라이드."""
    config_path = Path(path) if path else _find_config()

    env_path = _find_dotenv(config_path.parent)
    if env_path:
        load_dotenv(env_path)
    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    # .env 환경 변수가 있으면 config.toml 값을 오버라이드
    fred_key = os.environ.get("FRED_API_KEY")
    if fred_key:
        config.setdefault("api_keys", {})["fred"] = fred_key

    finnhub_key = os.environ.get("FINNHUB_API_KEY")
    if finnhub_key:
        config.setdefault("api_keys", {})["finnhub"] = finnhub_key

    return config
