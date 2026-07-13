# Deploy JARVIS live (with Claude turned on)

Goal: JARVIS running 24/7 at a public URL, powered by your real Anthropic key,
password-protected. Budget: ~R$25–50/month hosting + your Claude API usage.

There are two ways. **Path A (GitHub + Railway clicks)** is the most reliable for
keeping it updated. **Path B (Railway CLI)** skips GitHub. Pick one.

Your two secrets go into the **host's environment variables** — never into code,
never into chat:
- `ANTHROPIC_API_KEY` — turns the agents into real Claude.
- `JARVIS_PASSWORD` — the dashboard login (so nobody else spends your API budget).

---

## Path A — GitHub + Railway (recommended)

1. **Put the code on GitHub**
   - Create a free GitHub account if needed → New repository → name it `jarvis` → Private.
   - Upload this folder's contents (drag-and-drop the files in GitHub's "uploading an
     existing file" screen, or use GitHub Desktop). Commit.

2. **Deploy on Railway**
   - Go to railway.com → sign in with GitHub → **New Project → Deploy from GitHub repo** → pick `jarvis`.
   - Railway auto-detects Python + the `Procfile` and builds it.

3. **Add your variables** (Railway → your service → **Variables** tab → New Variable):
   - `ANTHROPIC_API_KEY` = your key (starts with `sk-ant-`)
   - `JARVIS_PASSWORD` = a strong password you choose
   - (optional) add a **Volume** mounted at `/data`, then set `JARVIS_DB_PATH=/data/jarvis.db`
     so projects/tasks survive restarts.

4. **Go live**
   - Railway → **Settings → Networking → Generate Domain**. You get a public URL.
   - Open it, log in (user `admin`, your password). The footer should say **"Claude live"**.

---

## Path B — Railway CLI (no GitHub)

On any computer with Node installed:

```bash
npm i -g @railway/cli
railway login                 # opens the browser to sign in
cd jarvis                     # this folder
railway init                  # create a new project
railway up                    # uploads & deploys this folder
railway variables --set ANTHROPIC_API_KEY=sk-ant-...  --set JARVIS_PASSWORD=your-password
railway domain                # get your public URL
```

---

## Verify it's really on Claude
- Dashboard footer shows **"Claude live"** (green), not "demo mode".
- Ask the Manager to build a site. With the key on, the Dev writes a fully custom
  Portuguese site (real imagery, layout tailored to the business) instead of the
  built-in template.
- `https://your-url/health` returns `{"ok":true,"ai":true}`.

## Costs to expect
- Railway Hobby: ~US$5/mo base + usage (fits the budget).
- Claude API: Manager/Dev on `claude-sonnet-5`; Design/Marketing/Email on
  `claude-haiku-4-5` (cheap). A built site is roughly a few US cents of tokens.
- Set a spend limit in the Anthropic console so there are no surprises.

## Updating later (Path A)
Push changes to GitHub → Railway redeploys automatically. (Path B: re-run `railway up`.)
