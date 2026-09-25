"""hp-collab: lightweight 3-way collab thread (Jim + Grok + ChatGPT)."""
from __future__ import annotations

import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

MT = ZoneInfo("America/Denver")
DB_PATH = Path(os.environ.get("COLLAB_DB_PATH", "/tmp/hp-collab.db"))
COLLAB_TOKEN = (os.environ.get("COLLAB_TOKEN") or "").strip()

app = FastAPI(title="hp-collab", version="1.0.0", docs_url=None, redoc_url=None, openapi_url=None)


def _init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                author TEXT NOT NULL,
                text TEXT NOT NULL,
                topic TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


@contextmanager
def db() -> Any:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


@app.on_event("startup")
def on_startup() -> None:
    if not COLLAB_TOKEN:
        # Fail closed: refuse to serve without a configured token.
        raise RuntimeError("COLLAB_TOKEN env var is required")
    _init_db()


def require_token(
    authorization: Optional[str] = Header(default=None),
    x_collab_token: Optional[str] = Header(default=None, alias="X-Collab-Token"),
) -> None:
    provided: Optional[str] = None
    if x_collab_token:
        provided = x_collab_token.strip()
    elif authorization:
        auth = authorization.strip()
        if auth.lower().startswith("bearer "):
            provided = auth[7:].strip()
        else:
            provided = auth
    if not provided or provided != COLLAB_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")


class CommentIn(BaseModel):
    author: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    topic: Optional[str] = None


def _row_to_dict(row: sqlite3.Row) -> dict:
    created = row["created_at"]
    try:
        dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        mt = dt.astimezone(MT)
        mt_str = mt.strftime("%Y-%m-%d %H:%M:%S MT")
    except Exception:
        mt_str = created
    return {
        "id": row["id"],
        "author": row["author"],
        "text": row["text"],
        "topic": row["topic"],
        "created_at": created,
        "created_at_mt": mt_str,
    }


@app.get("/health")
def health() -> dict:
    """Public liveness only — no secrets, no thread data."""
    return {"ok": True}


@app.get("/thread.txt", response_class=PlainTextResponse)
def thread_txt(_: None = Depends(require_token)) -> str:
    with db() as conn:
        rows = conn.execute(
            "SELECT id, author, text, topic, created_at FROM comments ORDER BY id ASC"
        ).fetchall()
    if not rows:
        return "# hp-collab thread (empty)\n"
    lines = ["# hp-collab thread (newest last)", ""]
    for row in rows:
        d = _row_to_dict(row)
        topic = f" [{d['topic']}]" if d.get("topic") else ""
        lines.append(f"#{d['id']} {d['author']} @ {d['created_at_mt']}{topic}")
        lines.append(d["text"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


@app.get("/thread")
def thread_json(_: None = Depends(require_token)) -> list:
    with db() as conn:
        rows = conn.execute(
            "SELECT id, author, text, topic, created_at FROM comments ORDER BY id ASC"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


@app.get("/comments")
def list_comments(
    limit: int = Query(default=100, ge=1, le=1000),
    _: None = Depends(require_token),
) -> list:
    with db() as conn:
        rows = conn.execute(
            "SELECT id, author, text, topic, created_at FROM comments ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    # Return newest-last for readability (reverse the DESC fetch)
    return [_row_to_dict(r) for r in reversed(rows)]


@app.post("/comments", status_code=201)
def post_comment(body: CommentIn, _: None = Depends(require_token)) -> dict:
    author = body.author.strip().lower()
    text = body.text.strip()
    topic = body.topic.strip() if body.topic else None
    if not author:
        raise HTTPException(status_code=422, detail="author required")
    if not text:
        raise HTTPException(status_code=422, detail="text required")
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO comments (author, text, topic, created_at) VALUES (?, ?, ?, ?)",
            (author, text, topic, created_at),
        )
        cid = cur.lastrowid
        row = conn.execute(
            "SELECT id, author, text, topic, created_at FROM comments WHERE id = ?",
            (cid,),
        ).fetchone()
    return _row_to_dict(row)
