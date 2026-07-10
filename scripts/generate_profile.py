#!/usr/bin/env python3
"""Generate assets/terminal-profile.svg — BYTEJAY's neofetch-style profile card.

Inputs:
    profile.config.json      static personal content (edit this)
    assets/ascii-art.json    pre-rendered ASCII artwork (scripts/ascii_from_photo.py)
    GitHub REST API          verified public stats (repos/stars/forks/followers)

Stdlib only — no pip installs needed in CI.

GitHub data handling:
    * paginated, owner repos only; forks and archived repos excluded from
      star/fork/language aggregation
    * on API success the numbers are cached in assets/stats-cache.json
    * on API failure the cache is used; if there is no cache either, the
      existing SVG is left untouched and the script exits 0 so a temporary
      outage can never blank the profile
    * nothing is ever invented: every number shown comes from the API or
      from a previous API success
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "profile.config.json"
ART = ROOT / "assets" / "ascii-art.json"
CACHE = ROOT / "assets" / "stats-cache.json"
OUT = ROOT / "assets" / "terminal-profile.svg"

# ---------------------------------------------------------------- palette --
BG = "#0d1117"        # terminal background
BG_BAR = "#161b22"    # title bar
BORDER = "#30363d"
TEXT = "#e6edf3"
MUTED = "#8b949e"
FAINT = "#3d444d"
GREEN = "#3fb950"
CYAN = "#58a6ff"
ORANGE = "#d29922"
RED = "#f85149"
PURPLE = "#b083f0"
STRIP = ["#484f58", "#f85149", "#d29922", "#3fb950",
         "#58a6ff", "#b083f0", "#5cb8c4", "#e6edf3"]

# ----------------------------------------------------------------- layout --
W = 1000
PAD = 28
FS = 13               # font size
LH = 18               # line height
CW = 7.83             # monospace advance at FS (0.602em, Menlo-class fonts)
BAR_H = 36
ART_X = PAD
COL_X = 428           # right column start
VAL_X = 566           # value column start
VAL_CHARS = int((W - PAD - VAL_X) / CW)   # chars available for values
FONT = ("ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "
        "'Liberation Mono', 'Courier New', monospace")

# -------------------------------------------------------------- animation --
# The card "replays" a terminal session on every load: the command is typed
# char-by-char, then the output prints top-to-bottom. Pure CSS inside the
# SVG (opacity + transform only) so it animates in GitHub's <img> embeds.
TYPE_DELAY = 0.40     # s before typing starts
TYPE_STEP = 0.09      # s per typed character
PRINT_PAUSE = 0.15    # s between command finishing and output printing
PRINT_RATE = 0.0022   # s of print delay per px of output height


def text_el(x: float, y: float, runs, size=FS, cw=CW, weight=None,
            cls=None, style=None) -> str:
    """One <text> line from [(str, color), ...] runs, explicit x per run."""
    spans, col = [], 0
    for t, c in runs:
        if t:
            spans.append(
                f'<tspan x="{x + col * cw:.1f}" fill="{c}">{escape(t)}</tspan>'
            )
        col += len(t)
    w = f' font-weight="{weight}"' if weight else ""
    k = f' class="{cls}"' if cls else ""
    s = f' style="{style}"' if style else ""
    return (f'<text xml:space="preserve" y="{y:.1f}" font-family="{FONT}" '
            f'font-size="{size:.2f}"{w}{k}{s}>{"".join(spans)}</text>')


def wrap_value(runs, limit):
    """Split [(t, c)] runs into lines of <= limit chars, breaking on ', '."""
    flat = "".join(t for t, _ in runs)
    if len(flat) <= limit:
        return [runs]
    # Only plain single-color values ever get long enough to wrap.
    color = runs[0][1]
    words, lines, cur = flat.split(", "), [], ""
    for wd in words:
        cand = f"{cur}, {wd}" if cur else wd
        if len(cand) > limit and cur:
            lines.append(cur + ",")
            cur = wd
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return [[(ln, color)] for ln in lines]


# ------------------------------------------------------------ github data --
def ssl_context():
    """Default certs; fall back to certifi (fixes macOS framework Python)."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


_CTX = ssl_context()


def api(url: str, token: str | None):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "bytejay-profile-generator",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    })
    with urllib.request.urlopen(req, timeout=30, context=_CTX) as r:
        return json.loads(r.read())


def fetch_stats(username: str) -> dict | None:
    import os
    token = os.environ.get("GITHUB_TOKEN") or None
    try:
        user = api(f"https://api.github.com/users/{username}", token)
        repos, page = [], 1
        while True:
            batch = api(
                f"https://api.github.com/users/{username}/repos"
                f"?per_page=100&type=owner&page={page}", token)
            repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        own = [r for r in repos if not r["fork"] and not r["archived"]]
        langs: dict[str, int] = {}
        for r in own:
            if r.get("language"):
                langs[r["language"]] = langs.get(r["language"], 0) + 1
        top = [k for k, _ in sorted(langs.items(), key=lambda kv: -kv[1])[:3]]
        return {
            "public_repos": user["public_repos"],
            "followers": user["followers"],
            "following": user["following"],
            "stars": sum(r["stargazers_count"] for r in own),
            "forks": sum(r["forks_count"] for r in own),
            "top_languages": top,
        }
    except (urllib.error.URLError, KeyError, json.JSONDecodeError, OSError) as e:
        print(f"warning: GitHub API unavailable ({e})", file=sys.stderr)
        return None


def uptime(birth: str) -> str:
    b = date.fromisoformat(birth)
    t = date.today()
    years = t.year - b.year - ((t.month, t.day) < (b.month, b.day))
    anniv_year = b.year + years
    anniv = date(anniv_year, b.month, b.day)
    months = (t.year - anniv.year) * 12 + t.month - anniv.month
    if t.day < anniv.day:
        months -= 1
    # months granularity keeps CI commits monthly instead of daily
    return f"{years} years, {months} months"


# ------------------------------------------------------------------ build --
def build() -> str:
    cfg = json.loads(CONFIG.read_text())
    art = json.loads(ART.read_text()) if ART.exists() else {
        "cols": 30, "rows": 1, "lines": [[{"t": "[ ascii art pending ]",
                                           "c": MUTED}]]}

    stats = fetch_stats(cfg["github_username"])
    if stats:
        CACHE.write_text(json.dumps(stats, indent=2) + "\n")
    elif CACHE.exists():
        stats = json.loads(CACHE.read_text())
        print("info: using cached stats", file=sys.stderr)

    j = ", ".join
    c = cfg["contact"]

    # right-column rows: (label, [(text, color)...]) | "blank" | "header"
    rows: list = ["header"]
    rows += [
        ("OS", [(cfg["os"], TEXT)]),
        ("Host", [(cfg["host"], CYAN)]),
        ("Role", [(cfg["role"], GREEN)]),
        ("Focus", [(cfg["focus"], TEXT)]),
        ("Location", [(cfg["location"], TEXT)]),
        ("Uptime", [(uptime(cfg["birthdate"]), TEXT)]),
        "blank",
        ("Languages", [(j(cfg["languages"]), TEXT)]),
        ("Backend", [(j(cfg["backend"]), TEXT)]),
        ("Databases", [(j(cfg["databases"]), TEXT)]),
        ("Infra", [(j(cfg["infrastructure"]), TEXT)]),
        ("AI / ML", [(j(cfg["ai_ml"]), TEXT)]),
        ("Frontend", [(j(cfg["frontend"]), TEXT)]),
        ("Learning", [(j(cfg["learning"]), ORANGE)]),
        "blank",
    ]
    if stats:
        rows += [
            ("Repos", [(str(stats["public_repos"]), GREEN),
                       (" public", MUTED)]),
            ("Stars", [(str(stats["stars"]), ORANGE),
                       ("  ·  Forks ", MUTED),
                       (str(stats["forks"]), ORANGE)]),
            ("Followers", [(str(stats["followers"]), CYAN),
                           ("  ·  Following ", MUTED),
                           (str(stats["following"]), CYAN)]),
            "blank",
        ]
    rows += [
        ("Email", [(c["email"], CYAN)]),
        ("LinkedIn", [(c["linkedin"], CYAN)]),
    ]

    # ---- expand rows into positioned lines -------------------------------
    body: list[str] = []
    top = BAR_H + 24          # prompt baseline
    y = top + LH + 10         # first content baseline

    # measure right column height first (wrapping may add lines)
    expanded: list = []
    for row in rows:
        if row in ("blank", "header"):
            expanded.append(row)
            continue
        label, val = row
        for i, line in enumerate(wrap_value(val, VAL_CHARS)):
            expanded.append((label if i == 0 else None, line, i == 0))

    # art gets its own font size so any column count fits the left panel;
    # line height = 2x advance preserves the converter's 2:1 cell aspect
    art_avail = COL_X - PAD - 26
    acw = min(CW, art_avail / max(art["cols"], 1))
    afs = acw / 0.602
    alh = 2 * acw
    # center narrow artwork horizontally in the left panel
    art_x = PAD + max(0.0, (art_avail - art["cols"] * acw) / 2)

    right_lines = len(expanded)
    art_lines = art["rows"]
    right_h = right_lines * LH
    art_h = art_lines * alh
    n_lines = max(right_lines, art_lines)

    # ---- prompt line: static prefix, command typed char-by-char -----------
    prefix = [(cfg["user_at_host"], GREEN), (":", MUTED), ("~", CYAN),
              ("$ ", MUTED)]
    body.append(text_el(PAD, top, prefix))
    cmd = cfg["command"]
    cmd_x = PAD + sum(len(t) for t, _ in prefix) * CW
    for i, ch in enumerate(cmd):
        body.append(text_el(
            cmd_x + i * CW, top, [(ch, TEXT)], cls="o",
            style=f"animation-delay:{TYPE_DELAY + (i + .5) * TYPE_STEP:.2f}s"))
    type_end = TYPE_DELAY + len(cmd) * TYPE_STEP
    out_base = type_end + PRINT_PAUSE
    # block cursor that rides along while the command is typed
    body.append(f'<rect id="cur" x="{cmd_x:.1f}" y="{top - 11:.1f}" '
                f'width="{CW:.1f}" height="15" fill="{GREEN}"/>')

    def d(yy: float) -> str:
        """Print delay for an output line at baseline yy (top-to-bottom)."""
        return f"animation-delay:{out_base + max(0.0, yy - y) * PRINT_RATE:.2f}s"

    # ---- ascii art (vertically centered against the taller column) -------
    art_y0 = y + max(0.0, (right_h - art_h) / 2)
    for i, line in enumerate(art["lines"]):
        runs = [(r["t"], r["c"] or FAINT) for r in line]
        if runs:
            body.append(text_el(art_x, art_y0 + i * alh, runs,
                                size=afs, cw=acw, cls="o",
                                style=d(art_y0 + i * alh)))

    # ---- right column -----------------------------------------------------
    ry = y + max(0.0, (art_h - right_h) / 2)
    for row in expanded:
        if row == "blank":
            ry += LH * 0.75
            continue
        if row == "header":
            body.append(text_el(COL_X, ry, [
                (cfg["display_name"].lower(), GREEN),
                ("@", MUTED),
                (cfg["github_username"], GREEN),
            ], weight="bold", cls="o", style=d(ry)))
            ry += LH * 0.55
            body.append(
                f'<line x1="{COL_X}" y1="{ry:.1f}" x2="{W - PAD}" '
                f'y2="{ry:.1f}" stroke="{BORDER}" stroke-width="1" '
                f'class="o" style="{d(ry)}"/>')
            ry += LH
            continue
        label, val_runs, is_first = row
        if label:
            body.append(text_el(COL_X, ry, [(label, MUTED)],
                                cls="o", style=d(ry)))
            dots_x0 = COL_X + (len(label) + 1) * CW
            body.append(
                f'<line x1="{dots_x0:.1f}" y1="{ry - 4:.1f}" '
                f'x2="{VAL_X - 10}" y2="{ry - 4:.1f}" stroke="{FAINT}" '
                f'stroke-width="1.5" stroke-dasharray="1.5 4" '
                f'stroke-linecap="round" class="o" style="{d(ry)}"/>')
        body.append(text_el(VAL_X, ry, val_runs, cls="o", style=d(ry)))
        ry += LH

    content_bottom = max(art_y0 + art_h, ry)

    # ---- terminal color strip (bottom of right column) --------------------
    strip_y = content_bottom + 6
    for i, col in enumerate(STRIP):
        body.append(f'<rect x="{COL_X + i * 26}" y="{strip_y:.1f}" '
                    f'width="22" height="11" rx="2" fill="{col}" '
                    f'class="o" style="{d(strip_y)}"/>')
    # closing prompt; its block cursor blinks once the output has printed
    body.append(text_el(PAD, strip_y + 11, prefix,
                        cls="o", style=d(strip_y + 11)))
    body.append(text_el(cmd_x, strip_y + 11, [("▊", GREEN)], cls="c2"))
    blink_start = out_base + (strip_y + 11 - y) * PRINT_RATE

    h = int(strip_y + 11 + PAD - 4)

    # ---- window chrome -----------------------------------------------------
    title = cfg["terminal_title"]
    chrome = [
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="10" '
        f'fill="{BG}" stroke="{BORDER}"/>',
        f'<path d="M0.5 {BAR_H} h{W - 1}" stroke="{BORDER}"/>',
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{BAR_H - 0.5}" '
        f'rx="10" fill="{BG_BAR}"/>',
        f'<rect x="0.5" y="{BAR_H / 2}" width="{W - 1}" '
        f'height="{BAR_H / 2}" fill="{BG_BAR}"/>',
        f'<line x1="0.5" y1="{BAR_H}" x2="{W - 0.5}" y2="{BAR_H}" '
        f'stroke="{BORDER}"/>',
        f'<circle cx="24" cy="{BAR_H / 2}" r="6" fill="{RED}"/>',
        f'<circle cx="44" cy="{BAR_H / 2}" r="6" fill="{ORANGE}"/>',
        f'<circle cx="64" cy="{BAR_H / 2}" r="6" fill="{GREEN}"/>',
        f'<text x="{W / 2}" y="{BAR_H / 2 + 4.5}" text-anchor="middle" '
        f'font-family="{FONT}" font-size="12" fill="{MUTED}">'
        f'{escape(title)}</text>',
    ]

    # ---- animation CSS -----------------------------------------------------
    # .o lines start hidden and "print"; #cur rides the typed command then
    # hides; .c2 blinks forever. All delays derive from layout, so output
    # stays deterministic.
    css = (
        "<style>"
        ".o{opacity:0;animation:o .01s steps(1) both}"
        "@keyframes o{to{opacity:1}}"
        f"#cur{{animation:"
        f"r {len(cmd) * TYPE_STEP:.2f}s steps({len(cmd)}) {TYPE_DELAY:.2f}s both,"
        f"h .01s steps(1) {out_base:.2f}s forwards}}"
        f"@keyframes r{{to{{transform:translateX({len(cmd) * CW:.1f}px)}}}}"
        "@keyframes h{to{opacity:0}}"
        f".c2{{opacity:0;animation:b 1.06s step-end {blink_start:.2f}s infinite}}"
        "@keyframes b{0%,49%{opacity:1}50%,100%{opacity:0}}"
        "@media (prefers-reduced-motion:reduce)"
        "{.o,.c2{animation:none;opacity:1}#cur{display:none}}"
        "</style>"
    )

    # Deterministic output: no timestamps, so CI only commits real changes.
    meta = ("<!-- generated by scripts/generate_profile.py — "
            "edit profile.config.json, not this file -->")

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" '
        f'viewBox="0 0 {W} {h}" role="img" '
        f'aria-label="{escape(cfg["brand_name"])} — terminal-style developer '
        f'profile card">\n{meta}\n{css}\n'
        + "\n".join(chrome) + "\n"
        + "\n".join(body) + "\n</svg>\n"
    )


def main() -> None:
    if not ART.exists():
        print("warning: assets/ascii-art.json missing — using placeholder",
              file=sys.stderr)
    if not CONFIG.exists():
        sys.exit("profile.config.json not found")
    try:
        svg = build()
    except Exception as e:
        if OUT.exists():
            # never blank the profile over a transient failure
            print(f"error: generation failed, keeping existing SVG ({e})",
                  file=sys.stderr)
            return
        raise
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg)
    print(f"wrote {OUT} ({len(svg):,} bytes)")


if __name__ == "__main__":
    main()
