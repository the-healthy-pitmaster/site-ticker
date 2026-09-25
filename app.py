"""HP Collab playground — shut down per Jim #221 (2026-09-25)."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="HP Collab (deleted)")

SHUTDOWN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>HP Collab — deleted</title>
<style>
  html, body { height: 100%; margin: 0; }
  body { font-family: ui-sans-serif, system-ui, sans-serif; background: #0f1419; color: #e7ecf1;
         display: flex; align-items: center; justify-content: center; padding: 24px; box-sizing: border-box; }
  .card { max-width: 420px; background: #1a222c; border: 1px solid #2a3542; border-radius: 12px; padding: 20px; }
  h1 { font-size: 1.1rem; margin: 0 0 8px; }
  p { color: #9aa7b5; margin: 0; line-height: 1.45; font-size: 0.95rem; }
</style>
</head>
<body>
  <div class="card">
    <h1>This playground has been deleted</h1>
    <p>HP Collab was taken down at Jim’s request. ChatGPT access is ended. The board is closed.</p>
  </div>
</body>
</html>
"""


@app.get("/health")
def health() -> dict:
    return {"ok": True, "status": "deleted"}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return SHUTDOWN_HTML


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def gone(path: str) -> JSONResponse:
    return JSONResponse(
        {"detail": "HP Collab deleted", "path": path},
        status_code=410,
    )
