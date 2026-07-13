"""Site generation used by the Dev agent.

- With ANTHROPIC_API_KEY: Claude builds a fully custom premium site.
- Without: a genuinely premium deterministic template (not the old cheap one).
brief_from_text() lets the manager pass a single free-text description and still
get structured fields.
"""
from __future__ import annotations
import json
import os
import re
from urllib.parse import quote

MODEL = os.environ.get("JARVIS_CODER_MODEL", "claude-sonnet-4-5")

SYSTEM_PROMPT = """Você é o Dev, agente de código de uma agência de sites premium para \
empresas brasileiras. Gere um site institucional de UMA PÁGINA, COMPLETO, em um único \
arquivo HTML autocontido, em português do Brasil. O padrão de qualidade é de agência \
cara (nível Awwwards), não de construtor genérico.

Exigências de qualidade:
- Tipografia real: importe fontes do Google Fonts (ex.: 'Fraunces' ou 'Playfair Display' \
para títulos + 'Inter' para o corpo). Hierarquia forte, títulos grandes.
- Layout sofisticado: hero de alto impacto, seções com respiro generoso, grid alinhado, \
detalhes (linhas finas, sombras suaves, cantos consistentes). NADA de emoji como ícone — \
use SVG inline para ícones.
- Fotografia: use imagens do Unsplash via CDN (https://images.unsplash.com/photo-...?...&w=1600&q=80) \
adequadas ao ramo, SEMPRE com um overlay/gradiente por cima para legibilidade e coesão.
- Paleta coesa (siga a direção do Design se fornecida), modo claro elegante ou escuro premium.
- Microinterações sutis em CSS (hover, transições). Mobile-first e responsivo de verdade.

Exigências de negócio (Brasil):
- CTA principal em todas as seções = "Falar no WhatsApp" -> https://wa.me/<numero> com texto pré-preenchido.
- Botão flutuante de WhatsApp fixo (SVG do ícone, não emoji).
- Seção de pagamento destacando Pix. Localização com link para Google Maps.
- SEO local: <title> e meta description com cidade/bairro, Open Graph, JSON-LD LocalBusiness.
- Rodapé com horário, Instagram e CNPJ se houver.

Responda APENAS com o HTML final, começando em <!DOCTYPE html>. Sem comentários fora do HTML."""

EDIT_SYSTEM = """Você é o Dev. Receberá o HTML atual de um site premium e uma instrução do \
dono da agência. Aplique exatamente a mudança pedida, preservando o padrão de qualidade e \
todo o resto. Responda APENAS com o HTML completo atualizado, começando em <!DOCTYPE html>."""


def _clean(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:html)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    i = text.find("<!DOCTYPE")
    return text[i:] if i > 0 else text


def generate_site(brief: dict) -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        prompt = "Construa o site para este negócio:\n" + json.dumps(brief, ensure_ascii=False, indent=2)
        resp = anthropic.Anthropic().messages.create(
            model=MODEL, max_tokens=20000, system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return _clean(resp.content[0].text)
    return _premium_template(brief)


def edit_site(current_html: str, instruction: str) -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        resp = anthropic.Anthropic().messages.create(
            model=MODEL, max_tokens=20000, system=EDIT_SYSTEM,
            messages=[{"role": "user", "content": f"HTML atual:\n{current_html}\n\nInstrução: {instruction}"}],
        )
        return _clean(resp.content[0].text)
    return _stub_edit(current_html, instruction)


# ---------------------------------------------------------------------------
# Free-text -> structured brief (the new one-prompt flow)
# ---------------------------------------------------------------------------
SEGMENT_IMAGES = {
    "padaria": "1509440159596-0249088772ff", "restaurante": "1517248135467-4c7edcad34c4",
    "cafe": "1495474472287-4d71bcdd2085", "café": "1495474472287-4d71bcdd2085",
    "estetica": "1560066984-138dadb4c035", "estética": "1560066984-138dadb4c035",
    "salao": "1560066984-138dadb4c035", "salão": "1560066984-138dadb4c035",
    "barbearia": "1585747860715-2ba37e788b70", "clinica": "1576091160399-112ba8d25d1d",
    "clínica": "1576091160399-112ba8d25d1d", "odonto": "1588776814546-1ffcf47267a5",
    "advocacia": "1589829545856-d10d557cf95f", "academia": "1534438327276-14e5300c3a48",
    "petshop": "1450778869180-41d0601e046e", "pet": "1450778869180-41d0601e046e",
    "loja": "1441986300917-64674bd600d8", "construtora": "1503387762-592deb58ef4e",
}


def _pick_image(segment: str, description: str) -> str:
    text = (segment + " " + description).lower()
    for key, pid in SEGMENT_IMAGES.items():
        if key in text:
            return f"https://images.unsplash.com/photo-{pid}?auto=format&fit=crop&w=1600&q=80"
    return "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1600&q=80"


def _looks_en(text: str) -> bool:
    return bool(re.search(r"\b(a|an|the|in|for|and|with|famous|our|we|your|best|bakery|"
                          r"shop|store|studio|beauty|salon|barber|restaurant|coffee|cafe|"
                          r"clinic|dental|gym|fitness|pet|law|make|build|create)\b",
                          text.lower()))


def _looks_pt(text: str) -> bool:
    t = text.lower()
    if _looks_en(t):  # English input can't be reused verbatim on a Portuguese site
        return False
    return bool(re.search(r"[ãõáéíóúâêôç]", t) or
                re.search(r"\b(da|de|do|na|no|em|anos|famosa|nossa|nosso|com)\b", t))


def _clean_desc(text: str, name: str) -> str:
    """Turn a raw command into a natural business description/tagline."""
    d = text.strip()
    # drop leading command in EN or PT: "build a site for <Name>," / "cria um site para a <Nome>,"
    d = re.sub(r"^\s*(?:build|create|make|put together|need|want|cri[ae]r?|faz(?:er)?|faça|"
               r"mont[ae]r?|quero|preciso de|gostaria de)\b.*?\b(?:site|website|page)\b[^,]*?,\s*",
               "", d, flags=re.I)
    # if the name still leads the sentence, drop it
    if name:
        d = re.sub(r"^\s*(?:para\s+)?(?:a|o|as|os)?\s*" + re.escape(name) + r"\s*[,\-–]?\s*",
                   "", d, flags=re.I)
    # strip whatsapp / phone clauses
    d = re.sub(r",?\s*whats?app.*$", "", d, flags=re.I)
    d = re.sub(r",?\s*\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}.*$", "", d)
    d = d.strip(" ,.-–")
    if d:
        d = d[0].upper() + d[1:]
    return d


def brief_from_text(text: str) -> dict:
    """Extract structured fields from a free-form description."""
    brief: dict = {"city": "São Paulo"}
    wa = re.search(r"(\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4})", text)
    if wa:
        brief["whatsapp"] = wa.group(1)
    _art = r"(?:the|a|an|o|as|os|um|uma)\s+"
    _run = r"([A-ZÀ-Ú][\wÀ-ú'&]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ú][\wÀ-ú'&]+){0,4})"
    name = re.search(r"(?:for|para|d[aeo]|named|called|chamad[ao]|nome)\s+(?:" + _art + ")?" + _run, text)
    if name:
        brief["business_name"] = name.group(1).strip()
    else:
        cap = re.search(_run, text)
        brief["business_name"] = cap.group(1).strip() if cap else "Novo Cliente"
    low = text.lower()
    segs = ["padaria", "restaurante", "café", "cafeteria", "estética", "salão", "barbearia",
            "clínica", "odonto", "dentista", "advocacia", "academia", "petshop", "pet shop",
            "loja", "construtora", "consultoria", "confeitaria", "pizzaria", "hamburgueria"]
    # English business type -> Portuguese segment label (client sites are Portuguese)
    en_seg = {"bakery": "padaria", "restaurant": "restaurante", "coffee": "cafeteria",
              "cafe": "cafeteria", "beauty": "estética", "aesthetic": "estética",
              "salon": "salão", "barber": "barbearia", "clinic": "clínica",
              "dental": "odontologia", "dentist": "odontologia", "gym": "academia",
              "fitness": "academia", "pet": "petshop", "law": "advocacia",
              "lawyer": "advocacia", "store": "loja", "shop": "loja",
              "bakeshop": "padaria", "pizzeria": "pizzaria", "burger": "hamburgueria",
              "consulting": "consultoria", "studio": "estúdio"}
    for s in segs:
        if s in low:
            brief["segment"] = s
            break
    else:
        for en, pt in en_seg.items():
            if re.search(r"\b" + en + r"\b", low):
                brief["segment"] = pt
                break
    bairros = re.search(r"(?:na|no|em|in|bairro|neighborhood)\s+([A-ZÀ-Ú][\wÀ-ú']+(?:\s+[A-ZÀ-Ú][\wÀ-ú']+)?)", text)
    if bairros:
        brief["address"] = bairros.group(1).strip()
    brief["description"] = _clean_desc(text, brief["business_name"])
    return brief


# ---------------------------------------------------------------------------
# Premium deterministic template (fallback / demo without API key)
# ---------------------------------------------------------------------------
def _wa(whatsapp: str, name: str) -> str:
    d = re.sub(r"\D", "", whatsapp or "")
    if d and not d.startswith("55"):
        d = "55" + d
    msg = f"Olá! Vi o site da {name} e gostaria de mais informações."
    return f"https://wa.me/{d}?text={quote(msg)}" if d else "#contato"


WA_SVG = ('<svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor"><path d="M17.5 14.4c-.3-.2-1.7-.9-2-1-.3-.1-.5-.2-.7.2-.2.3-.7 1-.9 1.1-.2.2-.3.2-.6.1-.3-.2-1.2-.5-2.3-1.5-.9-.8-1.4-1.7-1.6-2-.2-.3 0-.5.1-.6l.5-.5c.1-.2.2-.3.3-.5.1-.2 0-.4 0-.5 0-.2-.7-1.6-.9-2.2-.2-.6-.5-.5-.7-.5h-.6c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.5s1.1 2.9 1.2 3.1c.2.2 2.1 3.3 5.2 4.6.7.3 1.3.5 1.7.6.7.2 1.4.2 1.9.1.6-.1 1.7-.7 2-1.4.2-.7.2-1.2.2-1.4-.1-.1-.3-.2-.6-.3z"/><path d="M12 2C6.5 2 2 6.5 2 12c0 1.8.5 3.4 1.3 4.9L2 22l5.3-1.4c1.4.8 3 1.2 4.7 1.2 5.5 0 10-4.5 10-10S17.5 2 12 2zm0 18.2c-1.5 0-3-.4-4.2-1.2l-.3-.2-3.1.8.8-3-.2-.3C4 15 3.6 13.5 3.6 12 3.6 7.4 7.4 3.6 12 3.6s8.4 3.8 8.4 8.4-3.8 8.2-8.4 8.2z"/></svg>')


def _premium_template(brief: dict) -> str:
    name = brief.get("business_name", "Sua Empresa")
    segment = brief.get("segment", "")
    desc = brief.get("description", "")
    city = brief.get("city", "São Paulo")
    address = brief.get("address", "")
    hours = brief.get("hours", "Seg a Sáb, 9h às 19h")
    instagram = (brief.get("instagram") or "").lstrip("@")
    accent = brief.get("accent", "#0f766e")
    image = _pick_image(segment, desc)
    wa = _wa(brief.get("whatsapp", ""), name)
    # Client sites are Portuguese even if the owner ordered in English:
    pt_desc = desc if (desc and _looks_pt(desc)) else ""
    if pt_desc:
        tagline = pt_desc.split(".")[0].strip()
    elif segment:
        tagline = f"{segment.title()} em {address or city}"
    else:
        tagline = f"Bem-vindo à {name}"
    services = [s.strip() for s in re.split(r"[;,\n]", brief.get("services", "")) if s.strip()]
    if not services:
        services = ["Atendimento personalizado", "Qualidade premium", "Entrega no prazo"]
    maps_q = quote(f"{name} {address} {city}")

    icon = ('<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" '
            'stroke-width="1.6"><path d="M20 6L9 17l-5-5"/></svg>')
    service_cards = "".join(
        f'<article class="svc"><span class="tick">{icon}</span><h3>{s}</h3>'
        f'<a href="{wa}" class="svc-link">Saiba mais →</a></article>' for s in services[:6]
    )
    schema = json.dumps({
        "@context": "https://schema.org", "@type": "LocalBusiness", "name": name,
        "description": (desc or segment)[:200],
        "address": {"@type": "PostalAddress", "streetAddress": address,
                    "addressLocality": city, "addressCountry": "BR"},
        "openingHours": hours,
    }, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} — {segment.title() or 'Empresa'} em {city}</title>
<meta name="description" content="{tagline} — {city}. Fale conosco pelo WhatsApp.">
<meta property="og:title" content="{name}"><meta property="og:description" content="{tagline}">
<meta property="og:image" content="{image}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<script type="application/ld+json">{schema}</script>
<style>
:root{{--accent:{accent};--ink:#141210;--muted:#6b6560;--line:#e9e4de;--bg:#fbf9f6;}}
*{{margin:0;padding:0;box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{font-family:'Inter',system-ui,sans-serif;color:var(--ink);background:var(--bg);line-height:1.65;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1120px;margin:0 auto;padding:0 28px}}
h1,h2,h3{{font-family:'Fraunces',Georgia,serif;font-weight:600;line-height:1.08;letter-spacing:-.01em}}
.top{{position:absolute;top:0;left:0;right:0;z-index:10;display:flex;justify-content:space-between;align-items:center;padding:26px 32px;color:#fff}}
.brand{{font-family:'Fraunces',serif;font-size:1.4rem;font-weight:600}}
.top a.cta{{color:#fff;border:1px solid rgba(255,255,255,.55);padding:9px 18px;border-radius:999px;text-decoration:none;font-size:.9rem;font-weight:500;backdrop-filter:blur(4px)}}
.hero{{position:relative;min-height:88vh;display:flex;align-items:center;color:#fff;overflow:hidden}}
.hero::before{{content:"";position:absolute;inset:0;z-index:0;background-image:linear-gradient(115deg,rgba(20,18,16,.86),rgba(20,18,16,.42)),url('{image}'),linear-gradient(135deg,var(--accent),#141210);background-size:cover;background-position:center}}
.hero .wrap{{position:relative;z-index:1;padding-top:60px;padding-bottom:60px}}
.eyebrow{{text-transform:uppercase;letter-spacing:.18em;font-size:.72rem;font-weight:600;opacity:.85;margin-bottom:20px}}
.hero h1{{font-size:clamp(2.6rem,6vw,4.6rem);max-width:14ch;margin-bottom:22px}}
.hero p.lead{{font-size:1.2rem;max-width:46ch;opacity:.94;margin-bottom:34px}}
.btn{{display:inline-flex;align-items:center;gap:10px;background:var(--accent);color:#fff;font-weight:600;padding:15px 28px;border-radius:12px;text-decoration:none;font-size:1rem;transition:transform .15s ease,filter .15s ease;box-shadow:0 8px 30px rgba(0,0,0,.25)}}
.btn:hover{{transform:translateY(-2px);filter:brightness(1.06)}}
section{{padding:96px 0}}
.kicker{{text-transform:uppercase;letter-spacing:.16em;font-size:.72rem;font-weight:600;color:var(--accent);margin-bottom:14px}}
.sec-h{{font-size:clamp(1.9rem,4vw,2.8rem);max-width:20ch;margin-bottom:14px}}
.sec-sub{{color:var(--muted);max-width:52ch;font-size:1.05rem}}
.svc-grid{{display:grid;gap:1px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));background:var(--line);border:1px solid var(--line);border-radius:18px;overflow:hidden;margin-top:46px}}
.svc{{background:var(--bg);padding:34px 30px;display:flex;flex-direction:column;gap:14px;transition:background .2s}}
.svc:hover{{background:#fff}}
.tick{{width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;background:color-mix(in srgb,var(--accent) 12%,transparent);color:var(--accent)}}
.svc h3{{font-size:1.3rem}}
.svc-link{{margin-top:auto;color:var(--accent);text-decoration:none;font-weight:600;font-size:.95rem}}
.split{{display:grid;grid-template-columns:1.1fr .9fr;gap:64px;align-items:center}}
.pay{{background:var(--ink);color:#fff;border-radius:22px;padding:48px}}
.pay h2{{color:#fff;font-size:2rem;margin-bottom:14px}}
.pill{{display:inline-flex;align-items:center;gap:8px;background:color-mix(in srgb,var(--accent) 26%,transparent);color:#fff;padding:7px 16px;border-radius:999px;font-weight:600;font-size:.85rem;margin-bottom:22px}}
.loc a{{color:var(--accent);font-weight:600;text-decoration:none}}
footer{{border-top:1px solid var(--line);padding:56px 0;color:var(--muted);font-size:.92rem}}
footer .brand{{color:var(--ink);font-size:1.5rem;margin-bottom:8px}}
.wa-float{{position:fixed;right:22px;bottom:22px;width:60px;height:60px;border-radius:50%;background:#25d366;color:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 10px 30px rgba(37,211,102,.5);z-index:60;transition:transform .15s}}
.wa-float:hover{{transform:scale(1.07)}}
@media(max-width:760px){{.split{{grid-template-columns:1fr;gap:36px}}.pay{{padding:34px}}section{{padding:66px 0}}}}
</style></head>
<body>
<header class="top"><span class="brand">{name}</span><a class="cta" href="{wa}">Falar no WhatsApp</a></header>
<section class="hero"><div class="wrap">
  <p class="eyebrow">{segment.title() or 'Bem-vindo'} · {city}</p>
  <h1>{tagline}</h1>
  <p class="lead">{pt_desc[:160] if pt_desc else f'Atendimento de excelência em {city}. Conheça nosso trabalho e fale com a gente agora mesmo.'}</p>
  <a class="btn" href="{wa}">{WA_SVG} Falar no WhatsApp</a>
</div></section>

<section><div class="wrap">
  <p class="kicker">O que fazemos</p>
  <h2 class="sec-h">Serviços feitos com cuidado</h2>
  <p class="sec-sub">Qualidade, atendimento próximo e o resultado que seu momento pede.</p>
  <div class="svc-grid">{service_cards}</div>
</div></section>

<section><div class="wrap split">
  <div class="pay">
    <span class="pill">● Aceitamos Pix</span>
    <h2>Pague do jeito mais fácil</h2>
    <p style="opacity:.85">Pix na hora, cartões e dinheiro. Rápido, seguro e sem complicação — como deve ser.</p>
  </div>
  <div class="loc">
    <p class="kicker">Onde estamos</p>
    <h2 class="sec-h" style="font-size:1.8rem">{address + ' · ' if address else ''}{city}</h2>
    <p class="sec-sub" style="margin-bottom:18px">🕒 {hours}</p>
    <p><a href="https://www.google.com/maps/search/?api=1&query={maps_q}">Ver no Google Maps →</a></p>
    <p style="margin-top:26px"><a class="btn" href="{wa}">{WA_SVG} Falar agora</a></p>
  </div>
</div></section>

<footer><div class="wrap">
  <p class="brand">{name}</p>
  <p>{segment.title() + ' · ' if segment else ''}{city}{' · @' + instagram if instagram else ''}</p>
  {'<p>CNPJ: ' + brief.get('cnpj') + '</p>' if brief.get('cnpj') else ''}
  <p style="margin-top:16px;font-size:.82rem">Site criado por JARVIS · agência automatizada</p>
</div></footer>
<a class="wa-float" href="{wa}" aria-label="WhatsApp">{WA_SVG}</a>
</body></html>"""


def _stub_edit(html: str, instruction: str) -> str:
    """Best-effort edit without an API key: handle common color requests."""
    colors = {"azul": "#1d4ed8", "verde": "#0f766e", "vermelho": "#b91c1c", "roxo": "#6d28d9",
              "laranja": "#c2410c", "preto": "#141210", "rosa": "#be185d", "dourado": "#a16207"}
    for word, hexv in colors.items():
        if word in instruction.lower():
            html = re.sub(r"--accent:#[0-9a-fA-F]{6}", f"--accent:{hexv}", html)
            break
    return html
