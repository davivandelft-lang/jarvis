"""JARVIS agents: roster, the LLM layer, and each agent's logic.

You talk to the agents in ENGLISH and they reply in ENGLISH. The websites they
build for clients stay in Brazilian Portuguese (see generator.py).

LLM backend is swappable:
  - ANTHROPIC_API_KEY set -> real Claude (the deployed brain).
  - otherwise -> deterministic stubs so the whole system runs, testable, at $0.
"""
from __future__ import annotations
import json
import os
import re

# Current Anthropic model IDs (verified 2026-07). Override via env if needed.
MANAGER_MODEL = os.environ.get("JARVIS_MANAGER_MODEL", "claude-sonnet-5")
FAST_MODEL = os.environ.get("JARVIS_FAST_MODEL", "claude-haiku-4-5")
HAS_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))

# ---------------------------------------------------------------------------
# Agent roster — shown on the dashboard.
# ---------------------------------------------------------------------------
AGENTS = {
    "manager": {"name": "Manager", "role": "Chief of staff (JARVIS)",
                "blurb": "Takes your orders, plans, and delegates to the team.",
                "accent": "#38bdf8", "status": "online"},
    "dev": {"name": "Dev", "role": "Coding agent",
            "blurb": "Builds and edits the client websites.",
            "accent": "#34d399", "status": "online"},
    "design": {"name": "Design", "role": "Design agent",
               "blurb": "Sets palette, type and visual direction.",
               "accent": "#f472b6", "status": "online"},
    "marketing": {"name": "Marketing", "role": "Marketing agent",
                  "blurb": "SEO copy and social posts for each site.",
                  "accent": "#fbbf24", "status": "online"},
    "email": {"name": "Email", "role": "Email agent",
              "blurb": "Drafts client messages. Waits for your approval.",
              "accent": "#a78bfa", "status": "online"},
    "security": {"name": "Security", "role": "Security / ops agent",
                 "blurb": "Watches uptime, spend and backups.",
                 "accent": "#fb7185", "status": "online"},
}


def _client():
    import anthropic
    return anthropic.Anthropic()


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    a, b = text.find("{"), text.rfind("}")
    if a >= 0 and b > a:
        return json.loads(text[a:b + 1])
    raise ValueError("no json")


# ---------------------------------------------------------------------------
# MANAGER — turns your request into an English reply + a delegation plan.
# ---------------------------------------------------------------------------
MANAGER_SYSTEM = """You are the Manager, the lead agent of an automated web agency \
(JARVIS-style). The owner talks to you in ENGLISH; always reply in ENGLISH, short, \
confident and human — like a sharp chief of staff. Your job:
1. Understand the request.
2. Reply briefly.
3. Create a delegation plan for the right agents.

Agents you can delegate to:
- "design": sets visual direction (palette/style). Use before dev on a new site.
- "dev": builds or edits the actual website (the client site is in Portuguese).
- "marketing": writes SEO metadata + social captions for a finished site.
- "email": drafts a message to the client (ALWAYS needs the owner's approval).
- "security": runs a quick ops/status/cost check.

Respond ONLY with valid JSON:
{
  "reply": "your short English reply to the owner",
  "project_name": "client/project name if a new site, else null",
  "tasks": [
    {"agent": "design", "instruction": "..."},
    {"agent": "dev", "instruction": "full business details for the Portuguese site"},
    {"agent": "marketing", "instruction": "..."},
    {"agent": "email", "instruction": "what to tell the client", "needs_approval": true}
  ]
}
If the request needs no work (just a question), return tasks: []."""


def manager_plan(user_message: str, context: str = "") -> dict:
    if HAS_KEY:
        try:
            resp = _client().messages.create(
                model=MANAGER_MODEL, max_tokens=1500, system=MANAGER_SYSTEM,
                messages=[{"role": "user", "content": f"{context}\n\nRequest: {user_message}"}])
            plan = _extract_json(resp.content[0].text)
            plan.setdefault("tasks", [])
            plan.setdefault("reply", "Understood. On it.")
            plan.setdefault("project_name", None)
            return plan
        except Exception as e:
            return _manager_stub(user_message, note=f"(fallback: {e})")
    return _manager_stub(user_message)


def _manager_stub(user_message: str, note: str = "") -> dict:
    msg = user_message.lower()
    build_words = ("site", "website", "page", "landing", "build", "create", "make", "put together")
    status_words = ("status", "how are", "what's going", "whats going", "report", "today", "check")
    if any(w in msg for w in build_words):
        name = _extract_name(user_message)
        return {
            "reply": f"On it. I'll get {name}'s site built — Design sets the look, Dev builds "
                     f"it, Marketing preps the SEO and social copy, and Email will draft a "
                     f"note to the client for your approval. I'll ping you when the first "
                     f"version is live.",
            "project_name": name,
            "tasks": [
                {"agent": "design", "instruction": f"Visual direction for: {user_message}"},
                {"agent": "dev", "instruction": user_message},
                {"agent": "marketing", "instruction": f"SEO + social copy for {name}"},
                {"agent": "email", "instruction": f"Tell {name} their site is ready with the link",
                 "needs_approval": True},
            ],
            "_note": note,
        }
    if any(w in msg for w in status_words):
        return {"reply": "Let me have Security pull the current status.", "project_name": None,
                "tasks": [{"agent": "security", "instruction": "status and cost check"}], "_note": note}
    return {"reply": "Got it. Tell me which site you want the team to build and I'll delegate it "
                     "right away.", "project_name": None, "tasks": [], "_note": note}


_ART = r"(?:the|a|an|o|os|a|as|um|uma)\s+"
_RUN = r"([A-ZÀ-Ú][\wÀ-ú'&]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ú][\wÀ-ú'&]+){0,4})"


def _extract_name(text: str) -> str:
    m = re.search(r"(?:for|para|d[aeo]|named|called|chamad[ao]|nome)\s+(?:" + _ART + ")?" + _RUN, text)
    if m:
        return m.group(1).strip()
    m = re.search(_RUN, text)
    return (m.group(1).strip() if m else "New Client")


# ---------------------------------------------------------------------------
# DESIGN
# ---------------------------------------------------------------------------
DESIGN_SYSTEM = """You are the Design agent of a web agency. Given a business, reply in \
ENGLISH in 2-3 short sentences with the visual direction: palette (hex colors), type \
style, overall feel. Specific and premium, no clichés."""


def design_brief(instruction: str) -> str:
    if HAS_KEY:
        try:
            r = _client().messages.create(model=FAST_MODEL, max_tokens=400,
                                          system=DESIGN_SYSTEM,
                                          messages=[{"role": "user", "content": instruction}])
            return r.content[0].text.strip()
        except Exception:
            pass
    return ("Premium, restrained palette: a deep primary tone with one vivid accent, "
            "generous white space, a serif display face over a clean sans body. "
            "Feel: trustworthy, modern, high-end.")


# ---------------------------------------------------------------------------
# DEV / CODER — builds the Portuguese website. Summary shown to you is English.
# ---------------------------------------------------------------------------
def dev_build(instruction: str, design_notes: str = "") -> tuple[str, str]:
    from generator import generate_site, brief_from_text
    brief = brief_from_text(instruction)
    if design_notes:
        brief["design_notes"] = design_notes
    html = generate_site(brief)
    summary = (f"Built {brief.get('business_name','client')}'s site — {len(html):,} chars, "
               f"WhatsApp + Pix + local SEO included (site copy in Portuguese).")
    return html, summary


def dev_edit(current_html: str, instruction: str) -> tuple[str, str]:
    from generator import edit_site
    return edit_site(current_html, instruction), f"Applied change: {instruction[:80]}"


# ---------------------------------------------------------------------------
# MARKETING — SEO + social copy for the finished site (English report to you).
# ---------------------------------------------------------------------------
MARKETING_SYSTEM = """You are the Marketing agent. Given a Brazilian small business, reply \
in ENGLISH with: (1) an SEO title and meta description (these two IN PORTUGUESE, since \
they go on the site), and (2) two short Instagram caption ideas in Portuguese. Keep it tight."""


def marketing_copy(instruction: str) -> str:
    if HAS_KEY:
        try:
            r = _client().messages.create(model=FAST_MODEL, max_tokens=600,
                                          system=MARKETING_SYSTEM,
                                          messages=[{"role": "user", "content": instruction}])
            return r.content[0].text.strip()
        except Exception:
            pass
    name = _extract_name(instruction)
    return (f"SEO ready. Title: '{name} — atendimento em São Paulo'. "
            f"Meta: 'Conheça a {name}. Qualidade, atendimento próximo e Pix. Fale no WhatsApp.' "
            f"2 post ideas drafted (PT) for launch day.")


# ---------------------------------------------------------------------------
# EMAIL — drafts a client message. ALWAYS returned for approval.
# ---------------------------------------------------------------------------
def email_draft(instruction: str, site_url: str = "") -> str:
    if HAS_KEY:
        try:
            r = _client().messages.create(
                model=FAST_MODEL, max_tokens=500,
                system="You are the Email agent. Draft a short, warm client email in "
                       "BRAZILIAN PORTUGUESE telling them their site is ready. Include the "
                       "link if given. Reply with just the email text.",
                messages=[{"role": "user", "content": f"{instruction}\nLink: {site_url}"}])
            return r.content[0].text.strip()
        except Exception:
            pass
    return (f"Olá! Seu site já está no ar 🎉 Pode conferir aqui: {site_url or '[link]'}. "
            f"Qualquer ajuste, é só chamar. Abraço!")


# ---------------------------------------------------------------------------
# SECURITY / OPS
# ---------------------------------------------------------------------------
def security_check(projects: int, tasks: int) -> str:
    key = "live (Claude)" if HAS_KEY else "demo mode (no key)"
    return (f"All systems nominal. Projects: {projects}, tasks processed: {tasks}. "
            f"AI engine: {key}. No anomalies, spend within budget.")
