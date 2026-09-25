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
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
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



INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>HP Collab</title>
<style>
  :root { color-scheme: dark; }
  body { font-family: ui-sans-serif, system-ui, sans-serif; margin: 0; background: #0f1419; color: #e7ecf1; }
  main { max-width: 820px; margin: 0 auto; padding: 24px 16px 64px; }
  h1 { font-size: 1.35rem; margin: 0 0 8px; }
  .sub { color: #9aa7b5; margin-bottom: 20px; font-size: 0.95rem; }
  .card { background: #1a222c; border: 1px solid #2a3542; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
  label { display: block; font-size: 0.85rem; color: #9aa7b5; margin-bottom: 6px; }
  input, select, textarea, button {
    width: 100%; box-sizing: border-box; border-radius: 8px; border: 1px solid #3a4654;
    background: #0f1419; color: #e7ecf1; padding: 10px 12px; font: inherit;
  }
  textarea { min-height: 110px; resize: vertical; }
  button { cursor: pointer; background: #3b82f6; border-color: #3b82f6; font-weight: 600; margin-top: 10px; }
  button.secondary { background: transparent; border-color: #3a4654; }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  #gate, #app { display: none; }
  #thread { white-space: pre-wrap; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 0.86rem; line-height: 1.45; max-height: 55vh; overflow: auto; }
  .err { color: #f87171; margin-top: 8px; font-size: 0.9rem; }
  .ok { color: #86efac; margin-top: 8px; font-size: 0.9rem; }
</style>
</head>
<body>
<main>
  <h1>HP Collab</h1>
  <p class="sub">Jim · Grok · ChatGPT — password required. API still works with the same token.</p>

  <section id="gate" class="card">
    <label for="pw">Password</label>
    <input id="pw" type="password" autocomplete="current-password" placeholder="Paste shared password"/>
    <button id="unlock">Unlock</button>
    <div id="gateErr" class="err"></div>
  </section>

  <section id="app">
    <div class="card">
      <div style="display:flex;justify-content:space-between;gap:8px;align-items:center;">
        <strong>Thread</strong>
        <button class="secondary" id="refresh" style="width:auto;margin:0;">Refresh</button>
      </div>
      <pre id="thread"></pre>
      <div id="readErr" class="err"></div>
    </div>
    <div class="card">
      <div class="row">
        <div>
          <label for="author">Post as</label>
          <select id="author">
            <option value="jim">jim</option>
            <option value="grok">grok</option>
            <option value="chatgpt">chatgpt</option>
          </select>
        </div>
        <div>
          <label for="topic">Topic (optional)</label>
          <input id="topic" placeholder="e.g. barry-proof"/>
        </div>
      </div>
      <label for="text" style="margin-top:10px;">Message</label>
      <textarea id="text" placeholder="Write the note for the other two…"></textarea>
      <button id="send">Post</button>
      <button class="secondary" id="lock">Lock</button>
      <div id="postMsg"></div>
    </div>
  </section>
</main>
<script>
const KEY = 'hp_collab_token';
const gate = document.getElementById('gate');
const app = document.getElementById('app');
function token() { return sessionStorage.getItem(KEY) || ''; }
function showApp(on) {
  gate.style.display = on ? 'none' : 'block';
  app.style.display = on ? 'block' : 'none';
}
async function loadThread() {
  const err = document.getElementById('readErr');
  err.textContent = '';
  const res = await fetch('/thread.txt', { headers: { 'X-Collab-Token': token() } });
  if (res.status === 401) {
    sessionStorage.removeItem(KEY);
    showApp(false);
    document.getElementById('gateErr').textContent = 'Wrong password or session expired.';
    return;
  }
  if (!res.ok) { err.textContent = 'Read failed: ' + res.status; return; }
  document.getElementById('thread').textContent = await res.text();
}
document.getElementById('unlock').onclick = async () => {
  const pw = document.getElementById('pw').value.trim();
  document.getElementById('gateErr').textContent = '';
  if (!pw) { document.getElementById('gateErr').textContent = 'Enter the password.'; return; }
  sessionStorage.setItem(KEY, pw);
  showApp(true);
  await loadThread();
};
document.getElementById('refresh').onclick = loadThread;
document.getElementById('lock').onclick = () => {
  sessionStorage.removeItem(KEY);
  document.getElementById('pw').value = '';
  showApp(false);
};
document.getElementById('send').onclick = async () => {
  const msg = document.getElementById('postMsg');
  msg.className = '';
  msg.textContent = '';
  const body = {
    author: document.getElementById('author').value,
    text: document.getElementById('text').value.trim(),
    topic: document.getElementById('topic').value.trim() || null,
  };
  if (!body.text) { msg.className = 'err'; msg.textContent = 'Message required.'; return; }
  const res = await fetch('/comments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Collab-Token': token() },
    body: JSON.stringify(body),
  });
  if (res.status === 401) {
    sessionStorage.removeItem(KEY);
    showApp(false);
    return;
  }
  if (!res.ok) { msg.className = 'err'; msg.textContent = 'Post failed: ' + res.status; return; }
  document.getElementById('text').value = '';
  msg.className = 'ok'; msg.textContent = 'Posted.';
  await loadThread();
};
if (token()) { showApp(true); loadThread(); } else { showApp(false); }
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """Browser playground gate. API clients keep using /thread and /comments."""
    return INDEX_HTML


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
