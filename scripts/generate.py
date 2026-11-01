"""Generate live SVG assets for the HUAYUE1024 profile README.

Outputs (into ./dist by default):
  dashboard.svg        stats + streak + languages + 52-week activity
  card-<repo>.svg      featured project cards with live stars / forks

Standard library only, so the GitHub Action needs no dependencies.
Token: $GITHUB_TOKEN, falling back to `gh auth token` for local runs.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

LOGIN = os.environ.get("PROFILE_LOGIN", "HUAYUE1024")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
EXCLUDE_LANG_REPOS = {LOGIN}

# Featured projects: repo -> (tagline, stack label)
FEATURED = {
    "mi-fitness-mcp-cn": ("小米运动健康 · 本地 MCP Server + REST + 仪表盘", "Python · MCP"),
    "windows-dynamic-island": ("Dynamic Island for Windows · Liquid Glass", "Electron · C#"),
    "codex-controller": ("用手柄操控 Codex · 本地语音 · 空间导航", "JavaScript"),
    "codechat": ("Local RAG CLI · 终端里直接对话你的代码", "Python · RAG"),
}

# chips for repos that have no GitHub topics set
FALLBACK_TOPICS = {
    "codechat": ["rag", "cli", "local-first", "developer-tools"],
}

# palette
BG, PANEL, LINE = "#0a0e14", "#0d131c", "#1b2430"
CYAN, BLUE, PURPLE = "#00F5D4", "#00BBF9", "#9B5DE5"
TEXT, MUTED, DIM = "#c9d1d9", "#8b949e", "#5c6773"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      totalCount
      nodes {
        name description stargazerCount forkCount pushedAt
        primaryLanguage { name color }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
        repositoryTopics(first: 4) { nodes { topic { name } } }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def token() -> str:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()


def fetch() -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token()}", "User-Agent": LOGIN},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if payload.get("errors"):
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]


# ---------------------------------------------------------------- helpers
def fmt(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def ago(iso: str) -> str:
    d = (datetime.now(timezone.utc) - datetime.fromisoformat(iso.replace("Z", "+00:00"))).days
    if d < 1:
        return "today"
    if d < 30:
        return f"{d}d ago"
    if d < 365:
        return f"{d // 30}mo ago"
    return f"{d // 365}y ago"


def text_w(s: str, size: float) -> float:
    """Rough monospace width; CJK glyphs are ~2 cells."""
    return sum(size * (1.0 if ord(c) > 0x2E80 else 0.6) for c in s)


def streaks(days: list[dict]) -> tuple[int, int]:
    counts = [d["contributionCount"] for d in days if date.fromisoformat(d["date"]) <= date.today()]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current = 0
    tail = counts[:-1] if counts and counts[-1] == 0 else counts  # today may still be empty
    for c in reversed(tail):
        if not c:
            break
        current += 1
    return current, longest


STAR = "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z"
FORK = "M5 5.372v.878c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75v-.878a2.25 2.25 0 1 1 1.5 0v.878a2.25 2.25 0 0 1-2.25 2.25h-1.5v2.128a2.251 2.251 0 1 1-1.5 0V8.5h-1.5A2.25 2.25 0 0 1 3.5 6.25v-.878a2.25 2.25 0 1 1 1.5 0ZM5 3.25a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Zm6.75.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm-3 8.75a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Z"


# ---------------------------------------------------------------- card
def card(repo: dict, tagline: str, stack: str) -> str:
    w, h = 480, 168
    name = escape(repo["name"])
    lang_color = (repo.get("primaryLanguage") or {}).get("color") or CYAN
    topics = [n["topic"]["name"] for n in repo["repositoryTopics"]["nodes"]][:4]
    topics = topics or FALLBACK_TOPICS.get(repo["name"], [])

    chips, x = [], 24
    for t in topics:
        cw = text_w(t, 11) + 16
        if x + cw > w - 24:
            break
        chips.append(
            f'<rect x="{x}" y="104" width="{cw:.0f}" height="20" rx="10" fill="{CYAN}" fill-opacity=".08" stroke="{CYAN}" stroke-opacity=".3"/>'
            f'<text x="{x + cw / 2:.0f}" y="118" class="chip" text-anchor="middle">{escape(t)}</text>'
        )
        x += cw + 6

    stars, forks = fmt(repo["stargazerCount"]), fmt(repo["forkCount"])
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<style>
text{{font-family:{MONO}}}
.p{{fill:{DIM};font-size:13px}} .n{{fill:{CYAN};font-size:21px;font-weight:700}}
.d{{fill:{TEXT};font-size:13px}} .m{{fill:{MUTED};font-size:12.5px}} .chip{{fill:{CYAN};font-size:11px}}
.in{{opacity:0;animation:in .6s ease-out forwards}}
@keyframes in{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}
@keyframes sweep{{0%{{transform:translateX(-160px)}}60%,100%{{transform:translateX({w + 160}px)}}}}
</style>
<defs>
<linearGradient id="bar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{CYAN}"/><stop offset="1" stop-color="{BLUE}"/></linearGradient>
<linearGradient id="sh" x1="0" x2="1"><stop offset="0" stop-color="{CYAN}" stop-opacity="0"/><stop offset=".5" stop-color="{CYAN}" stop-opacity=".07"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></linearGradient>
<clipPath id="r"><rect width="{w}" height="{h}" rx="12"/></clipPath>
</defs>
<g clip-path="url(#r)">
<rect width="{w}" height="{h}" fill="{BG}"/>
<rect width="140" height="{h}" fill="url(#sh)" style="animation:sweep 6s ease-in-out infinite"/>
<rect width="4" height="{h}" fill="url(#bar)"/>
</g>
<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="12" fill="none" stroke="{CYAN}" stroke-opacity=".35"/>
<g class="in"><text x="24" y="34" class="p">~/repos/</text>
<text x="{w - 24}" y="34" class="p" text-anchor="end">{escape(stack)}</text></g>
<g class="in" style="animation-delay:.1s"><text x="24" y="62" class="n">{name}</text></g>
<g class="in" style="animation-delay:.2s"><text x="24" y="88" class="d">{escape(tagline)}</text></g>
<g class="in" style="animation-delay:.3s">{''.join(chips)}</g>
<g class="in" style="animation-delay:.4s">
<line x1="24" y1="138" x2="{w - 24}" y2="138" stroke="{LINE}"/>
<circle cx="30" cy="153" r="5.5" fill="{lang_color}"/>
<text x="42" y="157" class="m">{escape((repo.get('primaryLanguage') or {}).get('name') or '—')}</text>
<g transform="translate(176 145)"><path d="{STAR}" fill="{MUTED}"/></g><text x="198" y="157" class="m">{stars}</text>
<g transform="translate(246 145)"><path d="{FORK}" fill="{MUTED}"/></g><text x="268" y="157" class="m">{forks}</text>
<text x="{w - 24}" y="157" class="m" text-anchor="end">updated {ago(repo['pushedAt'])}</text>
</g>
</svg>"""


# ---------------------------------------------------------------- dashboard
def dashboard(u: dict) -> str:
    repos = u["repositories"]["nodes"]
    cc = u["contributionsCollection"]
    cal = cc["contributionCalendar"]
    days = [d for wk in cal["weeks"] for d in wk["contributionDays"]]
    cur, longest = streaks(days)

    stats = [
        ("stars", sum(r["stargazerCount"] for r in repos)),
        ("forks", sum(r["forkCount"] for r in repos)),
        ("contribs/yr", cal["totalContributions"]),
        ("commits/yr", cc["totalCommitContributions"] + cc["restrictedContributionsCount"]),
        ("pull_requests", u["pullRequests"]["totalCount"]),
        ("issues", u["issues"]["totalCount"]),
        ("public_repos", u["repositories"]["totalCount"]),
        ("followers", u["followers"]["totalCount"]),
    ]

    langs: dict[str, list] = {}
    for r in repos:
        if r["name"] in EXCLUDE_LANG_REPOS:
            continue
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            langs.setdefault(n, [0, e["node"]["color"] or MUTED])[0] += e["size"]
    total = sum(v[0] for v in langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1][0])[:6]

    W, H = 1000, 330
    s = []
    # --- panel frames
    for x, wd, title in ((16, 316, "$ gh stats --me"), (344, 272, "$ streak"), (628, 356, "$ langs --top")):
        s.append(f'<rect x="{x}" y="16" width="{wd}" height="216" rx="10" fill="{PANEL}" stroke="{LINE}"/>')
        s.append(f'<text x="{x + 18}" y="42" class="t">{title}</text>')

    # --- stats rows
    for i, (k, v) in enumerate(stats):
        y = 72 + i * 20
        s.append(
            f'<g class="in" style="animation-delay:{.15 + i * .08:.2f}s">'
            f'<text x="34" y="{y}" class="k">{k}</text>'
            f'<line x1="{34 + text_w(k, 13) + 8:.0f}" y1="{y - 4}" x2="{306 - text_w(fmt(v), 13) - 8:.0f}" y2="{y - 4}" stroke="{LINE}" stroke-dasharray="2 4"/>'
            f'<text x="306" y="{y}" class="v" text-anchor="end">{fmt(v)}</text></g>'
        )

    # --- streak ring
    cx, cy, rr = 480, 122, 52
    circ = 2 * 3.14159 * rr
    frac = min(cur / max(longest, 1), 1) if longest else 0
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{rr}" fill="none" stroke="{LINE}" stroke-width="8"/>')
    s.append(
        f'<circle cx="{cx}" cy="{cy}" r="{rr}" fill="none" stroke="url(#g)" stroke-width="8" stroke-linecap="round" '
        f'transform="rotate(-90 {cx} {cy})" stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ:.1f}" class="ring" '
        f'style="--to:{circ * (1 - max(frac, .02)):.1f}"/>'
    )
    s.append(f'<text x="{cx}" y="{cy + 4}" class="big" text-anchor="middle">{cur}</text>')
    s.append(f'<text x="{cx}" y="{cy + 24}" class="k" text-anchor="middle">day streak</text>')
    s.append(f'<text x="{cx - 70}" y="210" class="k" text-anchor="middle">longest</text><text x="{cx - 70}" y="192" class="v" text-anchor="middle">{longest}d</text>')
    s.append(f'<text x="{cx + 70}" y="210" class="k" text-anchor="middle">this year</text><text x="{cx + 70}" y="192" class="v" text-anchor="middle">{fmt(cal["totalContributions"])}</text>')

    # --- languages
    bx, bw, acc = 646, 320, 0.0
    s.append(f'<clipPath id="lb"><rect x="{bx}" y="58" width="{bw}" height="10" rx="5"/></clipPath><g clip-path="url(#lb)"><rect x="{bx}" y="58" width="{bw}" height="10" fill="{LINE}"/>')
    for i, (n, (sz, col)) in enumerate(top):
        seg = bw * sz / total
        s.append(f'<rect x="{bx + acc:.1f}" y="58" width="{seg + .5:.1f}" height="10" fill="{col}" class="grow" style="animation-delay:{.3 + i * .1:.1f}s"/>')
        acc += seg
    s.append("</g>")
    for i, (n, (sz, col)) in enumerate(top):
        col_x = bx + (i % 2) * 170
        y = 98 + (i // 2) * 40
        pct = 100 * sz / total
        s.append(
            f'<g class="in" style="animation-delay:{.4 + i * .08:.2f}s">'
            f'<circle cx="{col_x + 6}" cy="{y - 4}" r="5.5" fill="{col}"/>'
            f'<text x="{col_x + 18}" y="{y}" class="v">{escape(n)}</text>'
            f'<text x="{col_x + 18}" y="{y + 17}" class="k">{pct:.1f}%</text></g>'
        )

    # --- 52-week activity sparkline
    weekly = [sum(d["contributionCount"] for d in wk["contributionDays"]) for wk in cal["weeks"]][-52:]
    mx = max(weekly) or 1
    x0, x1, y0, hh = 34, 966, 306, 44
    step = (x1 - x0) / max(len(weekly) - 1, 1)
    pts = [(x0 + i * step, y0 - hh * c / mx) for i, c in enumerate(weekly)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    s.append(f'<rect x="16" y="244" width="968" height="76" rx="10" fill="{PANEL}" stroke="{LINE}"/>')
    s.append(f'<text x="34" y="266" class="t">$ activity --weeks 52</text>')
    s.append(f'<text x="966" y="266" class="k" text-anchor="end">peak {mx}/wk</text>')
    s.append(f'<polygon points="{x0},{y0} {line} {x1},{y0}" fill="url(#area)"/>')
    s.append(f'<polyline points="{line}" fill="none" stroke="{CYAN}" stroke-width="2" stroke-linejoin="round" class="draw"/>')
    lx, ly = pts[-1]
    s.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.5" fill="{CYAN}"><animate attributeName="r" values="3.5;6;3.5" dur="1.6s" repeatCount="indefinite"/></circle>')

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<style>
text{{font-family:{MONO}}}
.t{{fill:{CYAN};font-size:13px;font-weight:700}} .k{{fill:{MUTED};font-size:12.5px}}
.v{{fill:{TEXT};font-size:14px;font-weight:700}} .big{{fill:{TEXT};font-size:34px;font-weight:800}}
.dots{{fill:none}}
.in{{opacity:0;animation:in .5s ease-out forwards}}
@keyframes in{{from{{opacity:0;transform:translateX(-6px)}}to{{opacity:1;transform:none}}}}
.ring{{animation:ring 1.6s cubic-bezier(.2,.8,.2,1) .3s forwards}}
@keyframes ring{{to{{stroke-dashoffset:var(--to)}}}}
.grow{{transform-box:fill-box;transform-origin:left;transform:scaleX(0);animation:grow .7s ease-out forwards}}
@keyframes grow{{to{{transform:scaleX(1)}}}}
.draw{{stroke-dasharray:3000;stroke-dashoffset:3000;animation:draw 2.4s ease-out .2s forwards}}
@keyframes draw{{to{{stroke-dashoffset:0}}}}
</style>
<defs>
<linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="{CYAN}"/><stop offset="1" stop-color="{BLUE}"/></linearGradient>
<linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{CYAN}" stop-opacity=".35"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></linearGradient>
</defs>
<rect width="{W}" height="{H}" rx="14" fill="{BG}"/>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="{CYAN}" stroke-opacity=".35"/>
{chr(10).join(s)}
</svg>"""


def main() -> None:
    u = fetch()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "dashboard.svg").write_text(dashboard(u), encoding="utf-8")
    by_name = {r["name"]: r for r in u["repositories"]["nodes"]}
    for name, (tag, stack) in FEATURED.items():
        if name in by_name:
            (OUT / f"card-{name}.svg").write_text(card(by_name[name], tag, stack), encoding="utf-8")
    print(f"wrote {len(list(OUT.glob('*.svg')))} svg files to {OUT}/")


if __name__ == "__main__":
    main()
