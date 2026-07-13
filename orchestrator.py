"""The delegation loop: you -> Manager -> specialist agents -> result.

Runs in a background thread so the board updates live (UI polls /api/state).
All owner-facing text is English; client website content stays Portuguese.
"""
from __future__ import annotations
import threading

import db, agents


def _build_context(conn, limit: int = 14) -> str:
    """Recent conversation, oldest→newest, for the Manager's memory.
    Excludes the most recent 'you' message (passed separately as the new turn)."""
    rows = conn.execute(
        "SELECT author, text FROM messages ORDER BY id DESC LIMIT ?", (limit + 1,)
    ).fetchall()
    rows = list(reversed(rows))[:-1]  # drop the current (latest) message
    lines = []
    for r in rows:
        who = "You" if r["author"] == "you" else agents.NAMES.get(r["author"], r["author"].title())
        lines.append(f"{who}: {r['text']}")
    return "\n".join(lines)


def handle_user_message(text: str):
    conn = db.connect()
    try:
        db.add_message(conn, "you", text)
    finally:
        conn.close()
    threading.Thread(target=_run, args=(text,), daemon=True).start()


def _run(text: str):
    conn = db.connect()
    try:
        context = _build_context(conn)
        plan = agents.manager_plan(text, context=context)
        db.add_message(conn, "manager", plan.get("reply", "On it."))
        tasks = plan.get("tasks", [])
        if not tasks:
            return

        project_id = None
        pname = plan.get("project_name")
        if pname:
            project_id = db.create_project(conn, pname, brief=text)

        design_notes = ""
        for t in tasks:
            agent = t.get("agent")
            instruction = t.get("instruction", text)
            needs_approval = bool(t.get("needs_approval"))
            task_id = db.add_task(conn, project_id, agent, instruction)
            db.set_task(conn, task_id, "em_andamento")
            slug = _slug(conn, project_id)
            try:
                if agent == "design":
                    design_notes = agents.design_brief(instruction)
                    db.set_task(conn, task_id, "concluida", design_notes)
                    db.add_message(conn, "design", f"Visual direction set: {design_notes[:150]}")

                elif agent == "dev":
                    html, summary = agents.dev_build(instruction, design_notes)
                    if project_id:
                        db.set_project_html(conn, project_id, html, status="pronto")
                        slug = _slug(conn, project_id)
                    db.set_task(conn, task_id, "concluida", summary)
                    db.add_message(conn, "dev", f"{summary} Preview at /s/{slug}.")

                elif agent == "marketing":
                    copy = agents.marketing_copy(instruction)
                    db.set_task(conn, task_id, "concluida", copy)
                    db.add_message(conn, "marketing", copy)

                elif agent == "email":
                    site_url = f"/s/{slug}" if slug else ""
                    draft = agents.email_draft(instruction, site_url)
                    # ALWAYS wait for your approval before "sending"
                    db.set_task(conn, task_id, "aguardando_aprovacao", draft)
                    db.add_message(conn, "email",
                                   f"Drafted a note to the client — waiting for your approval:\n\n\"{draft}\"")

                elif agent == "security":
                    st = db.state(conn)
                    rep = agents.security_check(len(st["projects"]), len(st["tasks"]))
                    db.set_task(conn, task_id, "concluida", rep)
                    db.add_message(conn, "security", rep)

                else:
                    db.set_task(conn, task_id, "aguardando_aprovacao",
                                f"Agent '{agent}' not wired yet.")
            except Exception as e:
                db.set_task(conn, task_id, "erro", str(e)[:200])
                db.add_message(conn, agent or "manager", f"Hit a problem: {e}")

        if project_id:
            slug = _slug(conn, project_id)
            db.add_message(conn, "manager",
                           f"{pname}'s first version is live. Take a look on the right and tell me "
                           f"what to tweak — just say it (e.g. 'make the site blue'). The client "
                           f"email is drafted and waiting on your approval.")
    finally:
        conn.close()


def approve_task(task_id: int):
    """Approve a gated task (e.g. the client email)."""
    conn = db.connect()
    try:
        t = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not t or t["status"] != "aguardando_aprovacao":
            return
        db.set_task(conn, task_id, "concluida", (t["result"] or "") + "  [approved]")
        if t["agent"] == "email":
            db.add_message(conn, "email", "Approved — email sent to the client. ✅")
        else:
            db.add_message(conn, t["agent"] or "manager", "Approved and executed. ✅")
    finally:
        conn.close()


def apply_edit(project_slug: str, instruction: str):
    conn = db.connect()
    try:
        db.add_message(conn, "you", f"[{project_slug}] {instruction}")
    finally:
        conn.close()
    threading.Thread(target=_run_edit, args=(project_slug, instruction), daemon=True).start()


def _run_edit(project_slug: str, instruction: str):
    conn = db.connect()
    try:
        proj = conn.execute("SELECT * FROM projects WHERE slug=?", (project_slug,)).fetchone()
        if not proj or not proj["html"]:
            db.add_message(conn, "manager", "I couldn't find that project with a finished site.")
            return
        task_id = db.add_task(conn, proj["id"], "dev", instruction)
        db.set_task(conn, task_id, "em_andamento")
        html, summary = agents.dev_edit(proj["html"], instruction)
        db.set_project_html(conn, proj["id"], html, status="pronto")
        db.set_task(conn, task_id, "concluida", summary)
        db.add_message(conn, "dev", f"Updated {proj['name']}'s site: {summary}")
    except Exception as e:
        db.add_message(conn, "dev", f"Couldn't apply that edit: {e}")
    finally:
        conn.close()


def _slug(conn, project_id):
    if not project_id:
        return ""
    row = conn.execute("SELECT slug FROM projects WHERE id=?", (project_id,)).fetchone()
    return row["slug"] if row else ""
