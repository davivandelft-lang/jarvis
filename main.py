"""JARVIS — agency control dashboard."""
import os
import secrets
import base64
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

import db, orchestrator
from agents import AGENTS, HAS_KEY

app = FastAPI(title="JARVIS")
templates = Jinja2Templates(directory=str(Path(__file__).parent))

# --- Optional password gate (protects your API budget once deployed) ---------
# Set JARVIS_PASSWORD (and optionally JARVIS_USER) in the host env to require a
# login. The published client sites at /s/{slug} stay public.
_USER = os.environ.get("JARVIS_USER", "admin")
_PASS = os.environ.get("JARVIS_PASSWORD")


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    if _PASS and not request.url.path.startswith("/s/") and request.url.path != "/health":
        header = request.headers.get("authorization", "")
        ok = False
        if header.startswith("Basic "):
            try:
                user, _, pw = base64.b64decode(header[6:]).decode().partition(":")
                ok = secrets.compare_digest(user, _USER) and secrets.compare_digest(pw, _PASS)
            except Exception:
                ok = False
        if not ok:
            return Response("Auth required", status_code=401,
                            headers={"WWW-Authenticate": 'Basic realm="JARVIS"'})
    return await call_next(request)


@app.get("/health")
def health():
    return {"ok": True, "ai": HAS_KEY}


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(
        request, "dashboard.html",
        {"agents": AGENTS, "ai_enabled": HAS_KEY},
    )


@app.get("/api/state")
def api_state():
    conn = db.connect()
    try:
        return JSONResponse(db.state(conn))
    finally:
        conn.close()


@app.post("/api/say")
def api_say(text: str = Form(...)):
    if text.strip():
        orchestrator.handle_user_message(text.strip())
    return JSONResponse({"ok": True})


@app.post("/api/edit")
def api_edit(slug: str = Form(...), instruction: str = Form(...)):
    if instruction.strip():
        orchestrator.apply_edit(slug, instruction.strip())
    return JSONResponse({"ok": True})


@app.post("/api/approve")
def api_approve(task_id: int = Form(...)):
    orchestrator.approve_task(task_id)
    return JSONResponse({"ok": True})


@app.get("/api/project/{slug}")
def api_project(slug: str):
    conn = db.connect()
    try:
        p = conn.execute(
            "SELECT id,name,slug,brief,status,created_at,updated_at,"
            "(html IS NOT NULL) AS has_site FROM projects WHERE slug=?", (slug,)).fetchone()
        if not p:
            return JSONResponse({"error": "not found"}, status_code=404)
        tasks = [dict(r) for r in conn.execute(
            "SELECT agent,instruction,status,result,updated_at FROM tasks "
            "WHERE project_id=? ORDER BY id ASC", (p["id"],)).fetchall()]
        return JSONResponse({"project": dict(p), "tasks": tasks})
    finally:
        conn.close()


@app.get("/s/{slug}", response_class=HTMLResponse)
def serve_site(slug: str):
    conn = db.connect()
    try:
        row = conn.execute("SELECT html FROM projects WHERE slug=?", (slug,)).fetchone()
    finally:
        conn.close()
    if not row or not row["html"]:
        return HTMLResponse("<h1>Site em produção…</h1>", status_code=404)
    return HTMLResponse(row["html"])
