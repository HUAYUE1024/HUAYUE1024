"""HUAYUE1024 profile — design system & asset generator.

    python scripts/generate.py static assets   # hero, headings, toolkit, archive, footer
    python scripts/generate.py live   dist     # project cards + stats (GitHub API)

Every asset is emitted in a dark and a light variant (`*-dark.svg` / `*-light.svg`)
and swapped by the README via <picture> + prefers-color-scheme.
All English + Chinese typography is shaped into pure SVG <path> outlines.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

from typeset import font, mixed_text, text

LOGIN = os.environ.get("PROFILE_LOGIN", "HUAYUE1024")

# ───────────────────────────────────────────────────────────── type
DISPLAY = font("Inter.ttf", wght=630, opsz=32)
MEDIUM = font("Inter.ttf", wght=520, opsz=18)
BODY = font("Inter.ttf", wght=420, opsz=18)
SERIF = font("InstrumentSerif-Regular.ttf")
SERIF_I = font("InstrumentSerif-Italic.ttf")
MONO = font("GeistMono.ttf", wght=500)
CJK_FONT = font("CJKSub.otf")

# ───────────────────────────────────────────────────────────── color
THEMES = {
    "dark": dict(
        bg="#07070A", surface="#0B0B10", ink="#F2F2F5", muted="#A0A0AE", faint="#666674",
        line="#FFFFFF", line_op=.085, rim_op=.22, g=("#2DD4BF", "#818CF8", "#C084FC"),
        aurora=.58, grain=.065, island_stroke=.16,
    ),
    "light": dict(
        bg="#F8F8F6", surface="#FFFFFF", ink="#101014", muted="#555562", faint="#90909E",
        line="#000000", line_op=.075, rim_op=.06, g=("#0D9488", "#4F46E5", "#9333EA"),
        aurora=.26, grain=.04, island_stroke=0,
    ),
}

# ───────────────────────────────────────────────────────────── content
FEATURED = [
    # repo, accent, english line, chinese line, fallback topics
    ("mi-fitness-mcp-cn", "#FF6A13", "Your Mi Fitness data, as a local MCP server.",
     "小米运动健康 · MCP + REST API + Web 仪表盘", []),
    ("windows-dynamic-island", "#8B5CF6", "The Dynamic Island, reimagined for Windows.",
     "真 · Liquid Glass 背景折射 · 九大模块", []),
    ("codex-controller", "#10B981", "Drive Codex with a gamepad and your voice.",
     "手柄操控 · 本地语音输入 · 空间导航", []),
    ("codechat", "#3B82F6", "Chat with your codebase — fully local RAG.",
     "终端里直接对话你的代码", ["rag", "cli", "local-first", "developer-tools"]),
]

ARCHIVE = [
    ("huaycode", "Python execution visualizer", "逐行追踪 · 内存分析 · 算法动画", "Python · Docker", "#F59E0B"),
    ("Snowcode", "Next-gen autonomous coding agent", "更好的智能体 · 本地工具链协同", "Python · Agent", "#2DD4BF"),
    ("MoCobe", "Multi-model AI agent platform", "多模型自进化智能体平台 · Web UI", "Python · Web", "#818CF8"),
    ("cloud-deploy", "Multi-cloud deployment toolkit", "多云部署平台 · 自动化脚本", "Shell · DevOps", "#EC4899"),
]

TOOLKIT = [
    ("Languages", ["Python", "JavaScript", "C#", "HTML · CSS", "Shell"], "#2DD4BF"),
    ("Runtime & UI", ["Electron", ".NET", "Flask", "Node.js", "REST APIs"], "#818CF8"),
    ("AI systems", ["MCP", "RAG", "Agents", "Voice input", "Local-first"], "#C084FC"),
    ("Tooling", ["Git", "GitHub Actions", "Docker", "Linux", "VS Code"], "#38BDF8"),
]
NOW_BUILDING = "windows-dynamic-island"


# ───────────────────────────────────────────────────────────── primitives
BASE_CSS = """
.f{opacity:0;animation:up .85s cubic-bezier(.2,.7,.2,1) forwards}
@keyframes up{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}.f,.c{opacity:1!important}}
"""


def svg(w: int, h: int, body: list[str], css: str = "") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" fill="none">\n'
            f"<style>{BASE_CSS}{css}</style>\n" + "\n".join(body) + "\n</svg>\n")


def defs(t: dict, blur: int = 60, extra: str = "") -> str:
    g1, g2, g3 = t["g"]
    return f"""<defs>
<linearGradient id="acc" x1="0" y1="0" x2="1" y2=".25"><stop offset="0" stop-color="{g1}"/><stop offset=".55" stop-color="{g2}"/><stop offset="1" stop-color="{g3}"/></linearGradient>
<linearGradient id="rim" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{t['line']}" stop-opacity="0"/><stop offset=".35" stop-color="{g1}" stop-opacity="{t['rim_op']}"/><stop offset=".65" stop-color="{g3}" stop-opacity="{t['rim_op']}"/><stop offset="1" stop-color="{t['line']}" stop-opacity="0"/></linearGradient>
<filter id="blur" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="{blur}"/></filter>
<filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/></filter>
{extra}</defs>"""


def aurora(blobs, opacity: float) -> str:
    """blobs: (cx, cy, r, color, seconds, dx, dy) — soft drifting light."""
    out = [f'<g opacity="{opacity}">']
    for cx, cy, r, c, dur, dx, dy in blobs:
        out.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c}" filter="url(#blur)">'
            f'<animateTransform attributeName="transform" type="translate" values="0 0;{dx} {dy};0 0" '
            f'dur="{dur}s" repeatCount="indefinite" calcMode="spline" keySplines=".45 0 .55 1;.45 0 .55 1"/></circle>')
    out.append("</g>")
    return "".join(out)


def grain(t: dict, w: int, h: int) -> str:
    return f'<rect width="{w}" height="{h}" filter="url(#grain)" opacity="{t["grain"]}"/>'


def hline(t, x1, x2, y):
    return f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{t["line"]}" stroke-opacity="{t["line_op"]}"/>'


def vline(t, x, y1, y2):
    return f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{t["line"]}" stroke-opacity="{t["line_op"]}"/>'


def label(s, x, y, t, anchor="start", size=12.5, fill=None):
    return text(MONO, s.upper(), size, x, y, anchor=anchor, tracking=.13, fill=fill or t["faint"])


def fade(inner: str, delay: float) -> str:
    return f'<g class="f" style="animation-delay:{delay:.2f}s">{inner}</g>'


def surface(t, w, h, rx=24):
    return (
        f'<rect width="{w}" height="{h}" rx="{rx}" fill="{t["surface"]}"/>',
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{rx - .5}" stroke="{t["line"]}" stroke-opacity="{t["line_op"] * 1.35:.3f}"/>'
        f'<line x1="{rx}" y1=".75" x2="{w - rx}" y2=".75" stroke="url(#rim)" stroke-width="1.5"/>',
    )


# ───────────────────────────────────────────────────────────── hero
def island(t, cx: float, cy: float) -> str:
    """A tiny Dynamic Island that wakes up, shows what I'm building, and sleeps."""
    cw, ch, ew, eh = 132, 36, 456, 50
    kt, ks = "0;.12;.22;.70;.80;1", ";".join([".5 0 .1 1"] * 5)
    vals = lambda a, b: f"{a};{a};{b};{b};{a};{a}"
    anim = lambda attr, a, b: (f'<animate attributeName="{attr}" values="{vals(a, b)}" keyTimes="{kt}" dur="9s" '
                               f'repeatCount="indefinite" calcMode="spline" keySplines="{ks}"/>')
    pill = (f'<rect x="{cx - cw / 2}" y="{cy - ch / 2}" width="{cw}" height="{ch}" rx="{ch / 2}" fill="#050508" '
            f'stroke="#fff" stroke-opacity="{t["island_stroke"]}">'
            + anim("x", cx - cw / 2, cx - ew / 2) + anim("y", cy - ch / 2, cy - eh / 2)
            + anim("width", cw, ew) + anim("height", ch, eh) + anim("rx", ch / 2, eh / 2) + "</rect>")
    show = ('<animate attributeName="opacity" values="0;0;0;1;1;0;0" keyTimes="0;.12;.2;.27;.66;.71;1" '
            'dur="9s" repeatCount="indefinite"/>')
    hide = ('<animate attributeName="opacity" values="1;1;0;0;1;1" keyTimes="0;.11;.14;.78;.82;1" '
            'dur="9s" repeatCount="indefinite"/>')
    x0 = cx - ew / 2 + 24
    lab, lw = text(MONO, "NOW BUILDING", 11, x0 + 16, cy + 4, tracking=.1, fill="#888896")
    name, _ = text(MEDIUM, NOW_BUILDING, 15, x0 + 16 + lw + 12, cy + 5.5, fill="#F4F4F6")
    bars = []
    for i, (lo, hi, d) in enumerate([(6, 16, .9), (10, 22, .7), (4, 14, 1.1), (8, 20, .8), (5, 12, 1.0)]):
        bx = cx + ew / 2 - 24 - (5 - i) * 6
        bars.append(f'<rect x="{bx}" width="3" rx="1.5" fill="{t["g"][0] if i % 2 else t["g"][2]}">'
                    f'<animate attributeName="height" values="{lo};{hi};{lo}" dur="{d}s" repeatCount="indefinite"/>'
                    f'<animate attributeName="y" values="{cy - lo / 2};{cy - hi / 2};{cy - lo / 2}" dur="{d}s" repeatCount="indefinite"/></rect>')
    content = (f'<g opacity="0">{show}<circle cx="{x0 + 4}" cy="{cy}" r="4" fill="#34D399">'
               f'<animate attributeName="opacity" values="1;.35;1" dur="1.6s" repeatCount="indefinite"/></circle>'
               f'{lab}{name}{"".join(bars)}</g>')
    lens = (f'<g>{hide}<circle cx="{cx + 42}" cy="{cy}" r="7" fill="#14141C"/>'
            f'<circle cx="{cx + 42}" cy="{cy}" r="3" fill="#1E2A4A"/><circle cx="{cx + 43.5}" cy="{cy - 1.5}" r="1" fill="#6A8CFF" opacity=".8"/></g>')
    return pill + lens + content


def hero_blueprint(t) -> str:
    """Subtle architectural orbital rings in the top-right quadrant of the hero."""
    op = t["line_op"] * 0.75
    col = t["line"]
    cx, cy = 1030, 260
    return (
        f'<g stroke="{col}" stroke-opacity="{op:.3f}" fill="none">'
        f'<circle cx="{cx}" cy="{cy}" r="140" stroke-dasharray="3 6"/>'
        f'<circle cx="{cx}" cy="{cy}" r="230"/>'
        f'<circle cx="{cx}" cy="{cy}" r="330" stroke-dasharray="1 8"/>'
        f'<line x1="{cx - 360}" y1="{cy}" x2="{cx + 160}" y2="{cy}" stroke-opacity="{op * .6:.3f}"/>'
        f'<line x1="{cx}" y1="{cy - 240}" x2="{cx}" y2="{cy + 240}" stroke-opacity="{op * .6:.3f}"/>'
        f'<circle cx="{cx - 230}" cy="{cy}" r="3.5" fill="{t["g"][0]}" stroke="none" opacity=".7"/>'
        f'<circle cx="{cx}" cy="{cy - 140}" r="3" fill="{t["g"][2]}" stroke="none" opacity=".7"/>'
        f'</g>'
    )


def hero(t: dict) -> str:
    W, H = 1200, 620
    g1, g2, g3 = t["g"]
    b = [
        defs(t, 70),
        f'<clipPath id="frame"><rect width="{W}" height="{H}" rx="28"/></clipPath>',
        '<g clip-path="url(#frame)">',
        f'<rect width="{W}" height="{H}" fill="{t["bg"]}"/>',
        aurora([(940, 150, 230, g1, 20, -70, 40), (760, 480, 260, g2, 24, 60, -40),
                (1140, 420, 210, g3, 18, -50, -60), (220, 720, 240, g2, 26, 80, -30)], t["aurora"]),
        hero_blueprint(t),
        grain(t, W, H),
        "</g>",
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="27.5" stroke="{t["line"]}" stroke-opacity="{t["line_op"] * 1.4:.3f}"/>',
        f'<line x1="28" y1=".75" x2="{W - 28}" y2=".75" stroke="url(#rim)" stroke-width="1.5"/>',
    ]

    brand, _ = text(MONO, "HUAYUE1024", 14, 100, 61, tracking=.14, fill=t["ink"])
    right, _ = label("LOCAL-FIRST AI STUDIO · 2026", 1128, 61, t, anchor="end", size=13)
    b.append(fade(f'<circle cx="82" cy="56" r="7" fill="url(#acc)"/>{brand}{right}', 0))
    b.append(island(t, 580, 56))

    l1, _ = text(DISPLAY, "I build AI that runs", 90, 70, 262, tracking=-.038, fill=t["ink"])
    on, w_on = text(DISPLAY, "on ", 90, 70, 366, tracking=-.038, fill=t["ink"])
    your, w_y = text(SERIF_I, "your", 114, 70 + w_on + 2, 366, tracking=-.01, fill="url(#acc)")
    mach, _ = text(DISPLAY, " machine.", 90, 70 + w_on + w_y + 8, 366, tracking=-.038, fill=t["ink"])
    b += [fade(l1, .12), fade(on + your + mach, .24)]

    sub, _ = text(BODY, "Student developer crafting MCP servers, RAG tools, agents & desktop UX.", 22, 72, 434, fill=t["muted"])
    cjk, _ = mixed_text(MEDIUM, CJK_FONT, "学生开发者 · 做在本地跑起来的 AI 工具 —— 你的数据，你的机器，你的模型。",
                        17.5, 72, 472, fill=t["muted"], opacity=".82")
    b += [fade(sub, .36), fade(cjk, .44)]

    meta = [hline(t, 72, 1128, 518)]
    for i, (k, v) in enumerate([("01 / FOCUS", "MCP · RAG · Agents"), ("02 / CRAFT", "Desktop UX · Liquid Glass"),
                                ("03 / STACK", "Python · JS · C#"), ("04 / STATUS", "Open to collabs")]):
        x = 72 + i * 268
        if i:
            meta.append(vline(t, x - 24, 536, 596))
        lab, _ = label(k, x, 554, t, size=12)
        vx = x + (16 if "STATUS" in k else 0)
        val, _ = text(MEDIUM, v, 18, vx, 586, fill=t["ink"])
        dot = (f'<circle cx="{x + 5}" cy="580" r="4.5" fill="#22C55E"><animate attributeName="r" values="4.5;6.2;4.5" '
               f'dur="2s" repeatCount="indefinite"/></circle>') if "STATUS" in k else ""
        meta.append(fade(lab + dot + val, .52 + i * .07))
    b += meta
    return svg(W, H, b)


# ───────────────────────────────────────────────────────────── headings / toolkit / archive / footer
def heading(t, num: str, a: str, em: str, zh_tag: str, right: str) -> str:
    W, H = 1200, 104
    pill = f'<rect x="0" y="42" width="38" height="24" rx="12" stroke="{t["line"]}" stroke-opacity="{t["line_op"] * 1.8:.3f}"/>'
    n, _ = text(MONO, num, 13, 19, 58.5, anchor="middle", tracking=.06, fill=t["muted"])
    ta, wa = text(DISPLAY, a, 46, 52, 68, tracking=-.03, fill=t["ink"])
    tb, wb = text(SERIF_I, em, 56, 52 + wa + 12, 68, fill="url(#acc)")
    zx = 52 + wa + 12 + wb + 18
    zt, zw = mixed_text(MONO, CJK_FONT, zh_tag, 14, zx, 62, fill=t["faint"])
    r, wr = label(right, W, 62, t, anchor="end")
    x1, x2 = zx + zw + 24, W - wr - 24
    return svg(W, H, [defs(t), fade(pill + n + ta + tb + zt, 0), fade(hline(t, x1, x2, 57) + r, .12)])


def toolkit(t) -> str:
    W, H = 1200, 344
    b = [defs(t), *surface(t, W, H)]
    for i, (cat, items, col) in enumerate(TOOLKIT):
        x = 48 + i * 280
        if i:
            b.append(vline(t, x - 28, 44, H - 44))
        dot = f'<circle cx="{x + 5}" cy="70" r="4" fill="{col}"/>'
        lab, _ = label(f"0{i + 1}  {cat}", x + 16, 75, t)
        b.append(fade(dot + lab, i * .07))
        for j, it in enumerate(items):
            y = 132 + j * 42
            p, _ = text(MEDIUM, it, 22, x, y, tracking=-.01, fill=t["ink"])
            # subtle proficiency indicator bar on the right of each column
            bw = 28 - j * 3
            bar = (f'<rect x="{x + 216 - bw}" y="{y - 8}" width="{bw}" height="3" rx="1.5" '
                   f'fill="{col}" fill-opacity="{0.75 - j * 0.1:.2f}"/>')
            b.append(fade(p + bar, .08 + i * .07 + j * .04))
    return svg(W, H, b)


def archive(t) -> str:
    """2x2 bento grid showcasing 4 more repositories in the same editorial style."""
    W, H = 1200, 240
    b = [defs(t), *surface(t, W, H), hline(t, 36, W - 36, H // 2), vline(t, W // 2, 28, H - 28)]
    for i, (name, en, zh, stack, col) in enumerate(ARCHIVE):
        cx = 44 if i % 2 == 0 else W // 2 + 40
        cy = 52 if i < 2 else H // 2 + 48
        dot = f'<circle cx="{cx + 5}" cy="{cy - 6}" r="4.5" fill="{col}"/>'
        nm, nw = text(DISPLAY, name, 24, cx + 18, cy, tracking=-.02, fill=t["ink"])
        st, sw = text(MONO, stack, 12.5, cx + 516, cy - 2, anchor="end", fill=t["muted"])
        en_p, ew = text(BODY, en + "  ·  ", 15.5, cx + 18, cy + 32, fill=t["muted"])
        zh_p, _ = mixed_text(BODY, CJK_FONT, zh, 15, cx + 18 + ew, cy + 32, fill=t["faint"])
        b.append(fade(dot + nm + st + en_p + zh_p, .06 * i))
    return svg(W, H, b)


def footer(t) -> str:
    W, H = 1200, 290
    g1, g2, g3 = t["g"]
    a, wa = text(SERIF, "Thanks for ", 68, 0, 0)
    c, wc = text(SERIF_I, "stopping by.", 68, 0, 0)
    x0 = (W - wa - wc) / 2
    a, _ = text(SERIF, "Thanks for ", 68, x0, 146, fill=t["ink"])
    c, _ = text(SERIF_I, "stopping by.", 68, x0 + wa, 146, fill="url(#acc)")
    m, _ = label("local-first, always   ·   github.com/HUAYUE1024", W / 2, 204, t, anchor="middle")
    return svg(W, H, [defs(t, 50),
                      aurora([(520, 130, 120, g1, 16, 60, 10), (700, 140, 120, g3, 20, -60, -10)], t["aurora"] * .45),
                      fade(a + c, 0), fade(m, .16),
                      fade(f'<rect x="{W / 2 - 24}" y="238" width="48" height="3" rx="1.5" fill="url(#acc)"/>', .24)])


# ───────────────────────────────────────────────────────────── live data
QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      totalCount
      nodes {
        name stargazerCount forkCount pushedAt
        primaryLanguage { name color }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } }
        repositoryTopics(first: 6) { nodes { topic { name } } }
      }
    }
    contributionsCollection {
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
    }
  }
}
"""


def fetch() -> dict:
    tok = os.environ.get("GITHUB_TOKEN") or subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    req = urllib.request.Request("https://api.github.com/graphql",
                                 data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
                                 headers={"Authorization": f"bearer {tok}", "User-Agent": LOGIN})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if data.get("errors"):
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]


def fmt(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def ago(iso: str) -> str:
    d = (datetime.now(timezone.utc) - datetime.fromisoformat(iso.replace("Z", "+00:00"))).days
    return "today" if d < 1 else f"{d}d ago" if d < 30 else f"{d // 30}mo ago" if d < 365 else f"{d // 365}y ago"


STAR = "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z"
FORK = "M5 5.372v.878c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75v-.878a2.25 2.25 0 1 1 1.5 0v.878a2.25 2.25 0 0 1-2.25 2.25h-1.5v2.128a2.251 2.251 0 1 1-1.5 0V8.5h-1.5A2.25 2.25 0 0 1 3.5 6.25v-.878a2.25 2.25 0 1 1 1.5 0ZM5 3.25a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Zm6.75.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm-3 8.75a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Z"


def card_glyph(name: str, accent: str, t: dict) -> str:
    """Bespoke geometric illustration in the top-right area of each project card."""
    op = t["line_op"] * 1.8
    if name == "mi-fitness-mcp-cn":
        # ECG pulse wave + MCP nodes
        return (
            f'<g transform="translate(380 28)">'
            f'<path d="M0 22 H28 L36 8 L46 38 L56 14 L64 26 L70 22 H112" stroke="{accent}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" opacity=".85"/>'
            f'<circle cx="14" cy="22" r="3" fill="{accent}" opacity=".6"/>'
            f'<circle cx="96" cy="22" r="3" fill="{accent}" opacity=".6"/>'
            f'</g>'
        )
    if name == "windows-dynamic-island":
        # Concentric liquid-glass pill capsules
        return (
            f'<g transform="translate(384 31)">'
            f'<rect x="0" y="0" width="106" height="34" rx="17" stroke="{accent}" stroke-opacity=".55" stroke-width="1.5"/>'
            f'<rect x="10" y="7" width="86" height="20" rx="10" fill="{accent}" fill-opacity=".14"/>'
            f'<circle cx="24" cy="17" r="3.5" fill="{accent}"/>'
            f'<line x1="72" y1="13" x2="72" y2="21" stroke="{accent}" stroke-width="2" stroke-linecap="round"/>'
            f'<line x1="78" y1="11" x2="78" y2="23" stroke="{accent}" stroke-width="2" stroke-linecap="round"/>'
            f'<line x1="84" y1="14" x2="84" y2="20" stroke="{accent}" stroke-width="2" stroke-linecap="round"/>'
            f'</g>'
        )
    if name == "codex-controller":
        # D-pad cross + spatial voice rings
        return (
            f'<g transform="translate(396 30)" stroke="{accent}" stroke-width="1.6">'
            f'<path d="M14 4 H24 V14 H34 V24 H24 V34 H14 V24 H4 V14 H14 Z" fill="{accent}" fill-opacity=".12" stroke-linejoin="round"/>'
            f'<circle cx="72" cy="19" r="14" stroke-dasharray="3 3" opacity=".75"/>'
            f'<circle cx="72" cy="19" r="5" fill="{accent}" stroke="none"/>'
            f'</g>'
        )
    # codechat: terminal prompt + RAG embedding nodes
    return (
        f'<g transform="translate(396 30)" stroke="{accent}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'
        f'<rect x="0" y="2" width="48" height="34" rx="8" fill="{accent}" fill-opacity=".12"/>'
        f'<path d="M12 13 L20 19 L12 25 M24 25 H34"/>'
        f'<circle cx="68" cy="10" r="3" fill="{accent}" stroke="none"/>'
        f'<circle cx="88" cy="10" r="3" fill="{accent}" stroke="none" opacity=".6"/>'
        f'<circle cx="78" cy="28" r="3" fill="{accent}" stroke="none" opacity=".8"/>'
        f'<path d="M68 10 L88 10 L78 28 Z" stroke-width="1.2" opacity=".5"/>'
        f'</g>'
    )


def card(t, idx: int, repo: dict, accent: str, en: str, zh: str, fallback: list[str]) -> str:
    W, H = 600, 340
    b = [defs(t, 55), f'<clipPath id="r"><rect width="{W}" height="{H}" rx="24"/></clipPath>']
    bg, border = surface(t, W, H)
    b += [bg, '<g clip-path="url(#r)">',
          aurora([(530, 35, 155, accent, 14, -40, 30), (380, -40, 115, t["g"][1], 18, 40, 20)], t["aurora"] * .78),
          grain(t, W, H), "</g>", border]

    n, _ = label(f"0{idx} / PROJECT", 40, 54, t, size=12.5)
    glyph = card_glyph(repo["name"], accent, t)
    arrow = (f'<circle cx="540" cy="48" r="20" stroke="{t["line"]}" stroke-opacity="{t["line_op"] * 2.2:.2f}"/>'
             f'<path d="M534 54 546 42M538 42h8v8" stroke="{t["ink"]}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>')
    b.append(fade(n + glyph + arrow, 0))

    title, _ = text(DISPLAY, repo["name"], 39, 40, 146, tracking=-.03, max_w=W - 80, fill=t["ink"])
    sub, _ = text(BODY, en, 18, 40, 186, max_w=W - 80, fill=t["muted"])
    cjk, _ = mixed_text(MEDIUM, CJK_FONT, zh, 15.5, 40, 218, fill=t["muted"], opacity=".82")
    b += [fade(title, .07), fade(sub + cjk, .14)]

    topics = [x["topic"]["name"] for x in repo["repositoryTopics"]["nodes"]] or fallback
    chips, x = [], 40
    for tp in topics:
        _, w = text(MONO, tp, 12.5, 0, 0)
        cw = w + 24
        if x + cw > W - 40:
            break
        p, _ = text(MONO, tp, 12.5, x + 12, 263, fill=t["muted"])
        chips.append(f'<rect x="{x}" y="243" width="{cw:.1f}" height="28" rx="14" fill="{t["line"]}" fill-opacity="{t["line_op"] * .45:.3f}" '
                     f'stroke="{t["line"]}" stroke-opacity="{t["line_op"] * 1.6:.2f}"/>{p}')
        x += cw + 8
    b.append(fade("".join(chips), .21))

    b.append(hline(t, 40, W - 40, 286))
    lang = repo.get("primaryLanguage") or {"name": "—", "color": t["faint"]}
    ln, lw = text(MEDIUM, lang["name"], 15, 58, 315, fill=t["ink"])
    sx = 58 + lw + 28
    st, sw = text(MEDIUM, fmt(repo["stargazerCount"]), 15, sx + 22, 315, fill=t["ink"])
    fx = sx + 22 + sw + 24
    fk, _ = text(MEDIUM, fmt(repo["forkCount"]), 15, fx + 22, 315, fill=t["ink"])
    up, _ = text(BODY, f"Updated {ago(repo['pushedAt'])}", 14.5, W - 40, 315, anchor="end", fill=t["muted"])
    b.append(fade(f'<circle cx="45" cy="310" r="5" fill="{lang["color"]}"/>{ln}'
                  f'<path d="{STAR}" fill="{accent}" transform="translate({sx} 302)"/>{st}'
                  f'<path d="{FORK}" fill="{t["muted"]}" transform="translate({fx} 302)"/>{fk}{up}', .28))
    return svg(W, H, b)


def streaks(days: list[dict]) -> tuple[int, int]:
    counts = [d["contributionCount"] for d in days if date.fromisoformat(d["date"]) <= date.today()]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    tail = counts[:-1] if counts and counts[-1] == 0 else counts
    cur = 0
    for c in reversed(tail):
        if not c:
            break
        cur += 1
    return cur, longest


def stats(t, u: dict) -> str:
    W, H = 1200, 650
    g1, g2, g3 = t["g"]
    repos = u["repositories"]["nodes"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"][-53:]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    cur, longest = streaks(days)

    extra_defs = (
        f'<linearGradient id="spark" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{g1}" stop-opacity=".38"/>'
        f'<stop offset="1" stop-color="{g2}" stop-opacity="0"/></linearGradient>'
    )
    b = [defs(t, 70, extra_defs), f'<clipPath id="r"><rect width="{W}" height="{H}" rx="24"/></clipPath>']
    bg, border = surface(t, W, H)
    b += [bg, '<g clip-path="url(#r)">',
          aurora([(1120, 20, 200, g3, 22, -60, 40), (80, 640, 200, g1, 26, 60, -30)], t["aurora"] * .6),
          grain(t, W, H), "</g>", border]

    # headline numbers
    nums = [("01 / STARS EARNED", sum(r["stargazerCount"] for r in repos)),
            ("02 / FORKS", sum(r["forkCount"] for r in repos)),
            ("03 / CONTRIBUTIONS (1Y)", cal["totalContributions"]),
            ("04 / PUBLIC REPOS", u["repositories"]["totalCount"])]
    for i, (k, v) in enumerate(nums):
        x = 48 + i * 280
        if i:
            b.append(vline(t, x - 28, 56, 182))
        n, _ = text(DISPLAY, fmt(v), 72, x - 3, 134, tracking=-.045, fill=t["ink"])
        lab, _ = label(k, x, 172, t, size=12)
        b.append(fade(n + lab, i * .07))
    b.append(hline(t, 48, W - 48, 214))

    # heatmap + legend
    lab, _ = label("CONTRIBUTION MATRIX · 53 WEEKS", 48, 256, t)
    nz = sorted(d["contributionCount"] for w in weeks for d in w["contributionDays"] if d["contributionCount"])
    q = [nz[int(len(nz) * p)] for p in (.25, .5, .75)] if nz else [1, 2, 3]
    levels = [(t["line"], t["line_op"] * .85), (g1, .35), (g1, .7), (g2, .9), (g3, 1)]

    leg = []
    less_t, _ = label("LESS", W - 188, 256, t, anchor="end", size=11)
    more_t, _ = label("MORE", W - 48, 256, t, anchor="end", size=11)
    leg.extend([less_t, more_t])
    for li, (col, op) in enumerate(levels):
        lx = W - 178 + li * 17
        leg.append(f'<rect x="{lx}" y="245" width="12" height="12" rx="3" fill="{col}" fill-opacity="{op:.2f}"/>')
    b.append(fade(lab + "".join(leg), .25))

    pitch, cell, top = (W - 96) / 53, 15.5, 304
    cells, months, last_m = [], [], -9
    for wi, w in enumerate(weeks):
        x = 48 + wi * pitch
        first = date.fromisoformat(w["contributionDays"][0]["date"])
        if first.day <= 7 and wi - last_m >= 3:
            m, _ = text(MONO, first.strftime("%b").upper(), 11, x, top - 12, tracking=.08, fill=t["faint"])
            months.append(m)
            last_m = wi
        for d in w["contributionDays"]:
            c = d["contributionCount"]
            lv = 0 if not c else 1 + sum(c > v for v in q)
            col, op = levels[lv]
            wd = date.fromisoformat(d["date"]).weekday()
            y = top + ((wd + 1) % 7) * pitch
            cells.append(f'<rect class="c" x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="4" fill="{col}" '
                         f'fill-opacity="{op:.2f}" style="animation-delay:{.3 + wi * .012 + wd * .025:.2f}s"/>')
    div_y = top + 7 * pitch + 26
    b += ["".join(months), "".join(cells), hline(t, 48, W - 48, div_y), vline(t, 680, div_y + 24, H - 32)]

    # bottom-left: languages
    langs: dict[str, list] = {}
    for r in repos:
        if r["name"] == LOGIN:
            continue
        for e in r["languages"]["edges"]:
            langs.setdefault(e["node"]["name"], [0, e["node"]["color"] or t["faint"]])[0] += e["size"]
    total = sum(v[0] for v in langs.values()) or 1
    top_l = sorted(langs.items(), key=lambda kv: -kv[1][0])[:5]
    y0 = div_y + 44
    lab, _ = label("LANGUAGE DISTRIBUTION", 48, y0, t)
    bw = 596
    bar = [f'<clipPath id="lb"><rect x="48" y="{y0 + 18}" width="{bw}" height="12" rx="6"/></clipPath><g clip-path="url(#lb)">',
           f'<rect x="48" y="{y0 + 18}" width="{bw}" height="12" fill="{t["line"]}" fill-opacity="{t["line_op"]}"/>']
    legend, lx, acc = [], 48, 0.0
    for name, (sz, col) in top_l:
        seg = bw * sz / total
        bar.append(f'<rect x="{48 + acc:.1f}" y="{y0 + 18}" width="{seg + .6:.1f}" height="12" fill="{col}"/>')
        acc += seg
        nm, nw = text(MEDIUM, name, 15, lx + 13, y0 + 64, fill=t["ink"])
        pc, pw = text(MONO, f"{100 * sz / total:.0f}%", 13, lx + 13 + nw + 6, y0 + 64, fill=t["faint"])
        legend.append(f'<circle cx="{lx + 4}" cy="{y0 + 59}" r="4" fill="{col}"/>{nm}{pc}')
        lx += 13 + nw + 6 + pw + 20
    bar.append("</g>")
    b.append(fade(lab + "".join(bar) + "".join(legend), .75))

    # bottom-right: 52-week activity sparkline + streaks
    weekly = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks[-26:]]
    mx = max(weekly) or 1
    sx0, sx1, sy0, sh = 716, W - 48, y0 + 68, 42
    step = (sx1 - sx0) / max(len(weekly) - 1, 1)
    pts = [(sx0 + i * step, sy0 - sh * (c / mx)) for i, c in enumerate(weekly)]
    poly = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
    spark_hdr, _ = label(f"PULSE · CUR {cur}D / BEST {longest}D STREAK", sx0, y0, t)
    peak_lbl, _ = label(f"PEAK {max(weekly)}/WK", sx1, y0, t, anchor="end", fill=g1)
    lx_pt, ly_pt = pts[-1]
    spark = (
        f'{spark_hdr}{peak_lbl}'
        f'<polygon points="{sx0},{sy0} {poly} {sx1},{sy0}" fill="url(#spark)"/>'
        f'<polyline points="{poly}" fill="none" stroke="url(#acc)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{lx_pt:.1f}" cy="{ly_pt:.1f}" r="4" fill="{g1}">'
        f'<animate attributeName="r" values="3.5;6;3.5" dur="1.8s" repeatCount="indefinite"/></circle>'
    )
    b.append(fade(spark, .85))

    css = (".c{opacity:0;animation:pop .55s ease-out forwards}"
           "@keyframes pop{from{opacity:0}to{opacity:1}}")
    return svg(W, H, b, css)


# ───────────────────────────────────────────────────────────── main
def write(out: Path, name: str, fn) -> None:
    for theme, t in THEMES.items():
        (out / f"{name}-{theme}.svg").write_text(fn(t), encoding="utf-8")


def main() -> None:
    mode, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    if mode == "static":
        write(out, "hero", hero)
        write(out, "h-work", lambda t: heading(t, "01", "Selected", "work", "精选作品", "Live · refreshed every 6h"))
        write(out, "h-toolkit", lambda t: heading(t, "02", "The", "toolkit", "技术栈", "Daily drivers"))
        write(out, "h-numbers", lambda t: heading(t, "03", "By the", "numbers", "数据洞察", "Last 365 days"))
        write(out, "toolkit", toolkit)
        write(out, "archive", archive)
        write(out, "footer", footer)
    elif mode == "live":
        u = fetch()
        by = {r["name"]: r for r in u["repositories"]["nodes"]}
        for i, (name, accent, en, zh, fb) in enumerate(FEATURED, 1):
            if name in by:
                write(out, f"card-{name}", lambda t, i=i, name=name, accent=accent, en=en, zh=zh, fb=fb: card(t, i, by[name], accent, en, zh, fb))
        write(out, "stats", lambda t: stats(t, u))
    else:
        raise SystemExit(__doc__)
    print(f"{mode}: {len(list(out.glob('*.svg')))} svg files in {out}/")


if __name__ == "__main__":
    main()
