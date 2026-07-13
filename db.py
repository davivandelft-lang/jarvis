"""SQLite persistence for JARVIS."""
import sqlite3
import re
import unicodedata
from pathlib import Path
from datetime import datetime, timezone

import os
# Configurable so a hosting volume (e.g. Railway mounted at /data) persists the DB.
DB_PATH = Path(os.environ.get(
    "JARVIS_DB_PATH",
    Path(__file__).resolve().parent / "data" / "jarvis.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    brief TEXT,
    html TEXT,
    status TEXT NOT NULL DEFAULT 'em_producao',  -- em_producao | pronto | publicado
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id),
    agent TEXT NOT NULL,
    instruction TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'recebida',  -- recebida | em_andamento | concluida | aguardando_aprovacao | erro
    result TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author TEXT NOT NULL,     -- 'voce' | agent key
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def slugify(base: str) -> str:
    s = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "site"


def unique_slug(conn, base: str) -> str:
    slug = slugify(base)
    cand, i = slug, 1
    while conn.execute("SELECT 1 FROM projects WHERE slug=?", (cand,)).fetchone():
        i += 1
        cand = f"{slug}-{i}"
    return cand


def add_message(conn, author: str, text: str):
    conn.execute("INSERT INTO messages (author, text, created_at) VALUES (?,?,?)",
                 (author, text, now()))
    conn.commit()


def create_project(conn, name: str, brief: str = "") -> int:
    slug = unique_slug(conn, name)
    cur = conn.execute(
        "INSERT INTO projects (name, slug, brief, status, created_at, updated_at)"
        " VALUES (?,?,?, 'em_producao', ?, ?)", (name, slug, brief, now(), now()))
    conn.commit()
    return cur.lastrowid


def add_task(conn, project_id, agent: str, instruction: str) -> int:
    cur = conn.execute(
        "INSERT INTO tasks (project_id, agent, instruction, status, created_at, updated_at)"
        " VALUES (?,?,?, 'recebida', ?, ?)", (project_id, agent, instruction, now(), now()))
    conn.commit()
    return cur.lastrowid


def set_task(conn, task_id: int, status: str, result: str = None):
    if result is None:
        conn.execute("UPDATE tasks SET status=?, updated_at=? WHERE id=?", (status, now(), task_id))
    else:
        conn.execute("UPDATE tasks SET status=?, result=?, updated_at=? WHERE id=?",
                     (status, result, now(), task_id))
    conn.commit()


def set_project_html(conn, project_id: int, html: str, status: str = "pronto"):
    conn.execute("UPDATE projects SET html=?, status=?, updated_at=? WHERE id=?",
                 (html, status, now(), project_id))
    conn.commit()


def state(conn) -> dict:
    projects = [dict(r) for r in conn.execute(
        "SELECT id,name,slug,status,updated_at FROM projects ORDER BY updated_at DESC").fetchall()]
    tasks = [dict(r) for r in conn.execute(
        "SELECT id,project_id,agent,instruction,status,result,updated_at FROM tasks"
        " ORDER BY id DESC LIMIT 40").fetchall()]
    messages = [dict(r) for r in conn.execute(
        "SELECT author,text,created_at FROM messages ORDER BY id ASC LIMIT 100").fetchall()]
    return {"projects": projects, "tasks": tasks, "messages": messages}
