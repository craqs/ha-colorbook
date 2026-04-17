"""SQLite-backed history of generated coloring pages.

Stores one row per generation. PNG files live under `images/` in the data
directory; rows reference them by filename.
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .config import SETTINGS


_DDL = """
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    full_prompt TEXT NOT NULL,
    refinement TEXT,
    parent_id TEXT,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL,
    printed_at TEXT,
    filename TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS items_created_at_idx ON items(created_at DESC);
"""


_lock = threading.Lock()


@dataclass
class Item:
    id: str
    topic: str
    full_prompt: str
    refinement: str | None
    parent_id: str | None
    model: str
    created_at: str
    printed_at: str | None
    filename: str

    def to_dict(self) -> dict:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    con = sqlite3.connect(SETTINGS.db_path, timeout=30)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init() -> None:
    with _lock, _conn() as con:
        con.executescript(_DDL)


def save_generation(
    *,
    topic: str,
    full_prompt: str,
    refinement: str | None,
    parent_id: str | None,
    model: str,
    png_bytes: bytes,
) -> Item:
    item_id = uuid.uuid4().hex
    filename = f"{item_id}.png"
    (SETTINGS.images_dir / filename).write_bytes(png_bytes)
    created_at = _now()
    item = Item(
        id=item_id,
        topic=topic,
        full_prompt=full_prompt,
        refinement=refinement,
        parent_id=parent_id,
        model=model,
        created_at=created_at,
        printed_at=None,
        filename=filename,
    )
    with _lock, _conn() as con:
        con.execute(
            "INSERT INTO items(id, topic, full_prompt, refinement, parent_id, "
            "model, created_at, printed_at, filename) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (item.id, item.topic, item.full_prompt, item.refinement, item.parent_id,
             item.model, item.created_at, item.printed_at, item.filename),
        )
    return item


def mark_printed(item_id: str) -> None:
    with _lock, _conn() as con:
        con.execute(
            "UPDATE items SET printed_at=? WHERE id=?",
            (_now(), item_id),
        )


def get(item_id: str) -> Item | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    return _row_to_item(row) if row else None


def list_items(limit: int = 50, offset: int = 0) -> list[Item]:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM items ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [_row_to_item(r) for r in rows]


def delete(item_id: str) -> bool:
    item = get(item_id)
    if item is None:
        return False
    path: Path = SETTINGS.images_dir / item.filename
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    with _lock, _conn() as con:
        con.execute("DELETE FROM items WHERE id=?", (item_id,))
    return True


def image_path(item: Item) -> Path:
    return SETTINGS.images_dir / item.filename


def _row_to_item(row: sqlite3.Row) -> Item:
    return Item(
        id=row["id"],
        topic=row["topic"],
        full_prompt=row["full_prompt"],
        refinement=row["refinement"],
        parent_id=row["parent_id"],
        model=row["model"],
        created_at=row["created_at"],
        printed_at=row["printed_at"],
        filename=row["filename"],
    )
