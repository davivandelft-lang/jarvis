# JARVIS — central da agência automatizada de sites

You talk to the **Gerente** (Manager). It plans, delegates to the **Dev** (coder)
and **Design** agents, and a real website comes out the other side — live on the
task board, previewed in the panel, editable by chat. This is the factory that
builds the sites you sell.

## What's real in this v1 (the "working brain")

- **Manager agent** — reads your order in plain Portuguese, replies, and creates a
  delegation plan (which agents do what).
- **Design agent** — sets the visual direction (palette/typography) that guides the Dev.
- **Dev agent** — actually builds the website: a complete, self-contained, premium
  HTML site with WhatsApp-first CTAs, Pix section, Google Maps, local SEO (JSON-LD).
- **Task board** — every delegated task shows its lifecycle live: recebida →
  em_andamento → concluída (or aguardando_aprovação / erro).
- **Live preview** — the built site "pulls up" in the panel; edit it by chat
  ("deixa azul e adiciona horário de domingo") and it re-renders.
- **Agent roster** — Manager/Dev/Design online; Marketing/Email/Segurança are
  registered and shown in standby (next slices).

### Two brains, one codebase
- **With `ANTHROPIC_API_KEY`:** every agent runs on real Claude. The Manager truly
  reasons about delegation; the Dev writes fully custom sites with real photography.
- **Without a key (current demo):** deterministic stubs run the exact same loop so
  you can see the whole system work at zero cost. The generated sites use a premium
  built-in template. (Note: the template pulls photos from Unsplash; in a locked-down
  sandbox those may not load, so the hero falls back to a designed gradient — on a
  real deploy with the key, the Dev generates real imagery.)

## Run locally

```bash
pip install fastapi uvicorn jinja2 python-multipart anthropic
export ANTHROPIC_API_KEY=sk-ant-...      # turns the stubs into real Claude agents
uvicorn app.main:app --port 8100
# open http://localhost:8100
```

Try: *"Cria um site para a Padaria Estrela da Mooca, padaria artesanal na Mooca,
WhatsApp 11 91234-5678"* → watch the board fill and the site appear.

## Deploy (Railway — ~R$25–50/mês)

1. Push this folder to a private GitHub repo.
2. Railway → New Project → Deploy from GitHub.
3. Environment variables: `ANTHROPIC_API_KEY` (yours).
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add a Volume mounted at `/app/data` so the SQLite DB (projects, tasks, chat)
   survives restarts — or swap to Railway Postgres later (same SQL).

Fly.io works the same way; either fits the sub-$200/mo budget easily.

## Architecture (the boring-on-purpose stack the research validated)

`FastAPI + SQLite + Jinja`, one process. The dashboard polls `/api/state` every
1.5s for live updates (simple and bulletproof; upgrade to WebSocket later for the
cinematic feel). Agents are plain Claude API calls with role system-prompts and a
task queue — **no LangGraph/CrewAI**, exactly what every shipped JARVIS build used.

```
app/
  main.py          FastAPI routes: dashboard, /api/say, /api/edit, /api/state, /s/{slug}
  agents.py        agent roster + LLM layer (real Claude or stub) + Manager/Design/Dev logic
  orchestrator.py  the delegation loop (background thread; updates the task board live)
  generator.py     the Dev's site builder (Claude prompt + premium fallback template)
  db.py            SQLite: projects, tasks, messages
  templates/dashboard.html   the control room UI
```

## Roadmap (next slices, in order)

1. **Approval gates** — flag outbound/sensitive tasks as "aguardando aprovação"
   with an Approve button (schema already supports the status).
2. **Publish + custom domains** — per-client .com.br, auto-TLS.
3. **More agents online** — Marketing (SEO/posts), Email (client intake via Resend),
   Segurança (uptime + spend caps).
4. **Voice** — Web Speech (STT) in, ElevenLabs Flash (TTS) out, one voice per agent,
   WebSocket streaming. (This is where the Iron-Man feel arrives.)
5. **HUD polish** — holographic panels, waveforms, the summon-a-panel canvas.

Revenue first: this brain can already produce sellable sites today. Voice and the
cinematics sit on top of a system that works.
