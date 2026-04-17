"""Runtime configuration loaded from environment variables.

`run.sh` populates these from `/data/options.json`. During local development
set them in your shell before starting Flask.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default) or default


def _bool(value: str, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_image_model: str
    openai_chat_model: str
    image_size: str
    image_quality: str
    printer_host: str
    printer_port: int
    printer_queue: str
    paper_size: str
    auto_accept_default: bool
    data_dir: Path

    @property
    def images_dir(self) -> Path:
        return self.data_dir / "images"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "history.db"


def load() -> Settings:
    # Resolve to an absolute path up-front: Flask's send_file treats relative
    # paths as relative to app.root_path (the "app/" package dir), which would
    # mismatch where history.py writes PNG files (relative to CWD).
    data_dir = Path(_env("DATA_DIR", "/data")).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "images").mkdir(parents=True, exist_ok=True)

    api_key = _env("OPENAI_API_KEY") or _env("OPENAI_TOKEN")

    return Settings(
        openai_api_key=api_key,
        openai_image_model=_env("OPENAI_IMAGE_MODEL", "gpt-image-1"),
        openai_chat_model=_env("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
        image_size=_env("IMAGE_SIZE", "1024x1536"),
        image_quality=_env("IMAGE_QUALITY", "medium"),
        printer_host=_env("PRINTER_HOST"),
        printer_port=int(_env("PRINTER_PORT", "631") or "631"),
        printer_queue=_env("PRINTER_QUEUE", "ipp/print").lstrip("/"),
        paper_size=_env("PAPER_SIZE", "A4"),
        auto_accept_default=_bool(_env("AUTO_ACCEPT_DEFAULT", "false")),
        data_dir=data_dir,
    )


SETTINGS = load()
