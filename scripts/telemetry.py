#!/usr/bin/env python3
"""Draw assets/telemetry.svg for the GitHub profile from the portfolio's live logs.

Runs daily in the profile repository (see .github/workflows/telemetry.yml) with
only the standard library. It reads the public /api/metrics endpoint (the same
numbers the website's "site telemetry" panel shows, from Cloudflare D1) and
never invents a number: if the site cannot be reached or has no events, the card
says so. scripts/build_github_profile.py copies this file into the profile repo
as scripts/telemetry.py, with the site's fonts in scripts/fonts.css.
"""
from __future__ import annotations

import html
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SITE = "https://pranjulgupta.com"
HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "assets" / "telemetry.svg"

BG = "#101112"
TEXT = "#f2f0ea"
MUTED = "#a9a69f"
FAINT = "#88857d"
ACCENT = "#da5d3e"
ACCENT_TEXT = "#ef8a6d"
RULE = "rgba(242,240,234,0.14)"


def fetch(url: str) -> dict | None:
    request = urllib.request.Request(url, headers={"User-Agent": "github-profile-telemetry", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 (fixed https URL)
            return json.loads(response.read().decode())
    except Exception as exc:  # network, HTTP, or JSON: draw the "unavailable" card instead
        print(f"warning: {url}: {exc}", file=sys.stderr)
        return None


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def seconds(ms: float | None) -> str:
    if ms is None:
        return "n/a"
    return f"{ms / 1000:.2f} s" if ms >= 1000 else f"{round(ms)} ms"


def wrap_words(text: str, limit: int) -> list[str]:
    """Greedy word wrap at `limit` characters."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        if current and len(current) + 1 + len(word) > limit:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines


def render(data: dict | None, host: str, fonts: str = "", now: datetime | None = None, note: str | None = None) -> str:
    """The card; `data` is the /api/metrics?range=7d response, or None when unavailable.
    `note` replaces the empty-state message (the first card, before any refresh)."""
    now = now or datetime.now(timezone.utc)
    totals = (data or {}).get("totals") or {}
    requests = int(totals.get("requests") or 0)
    width, height = 1200, 292
    parts = [
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="14" fill="{BG}" stroke="{RULE}"/>',
        f'<rect x="40" y="38" width="22" height="2" fill="{ACCENT}"/>',
        f'<text class="m" x="72" y="45" font-size="16" letter-spacing="1.8" fill="{MUTED}">LIVE FROM {esc(host.upper())}, LAST 7 DAYS</text>',
    ]
    if data is None or requests == 0:
        message = note or ("The site could not be reached for this refresh." if data is None else "No questions in the last 7 days yet.")
        parts.append(f'<text class="d" x="40" y="150" font-size="72" fill="{MUTED}">No data</text>')
        parts.append(f'<text class="t" x="40" y="198" font-size="21" fill="{MUTED}">{esc(message)} Ask the assistant something and it shows up here.</text>')
    else:
        latency = data.get("latency") or {}
        providers = data.get("providers") or {}
        static = int(totals.get("static_requests") or 0)
        llm = int(providers.get("groq") or 0) + int(providers.get("gemini") or 0)
        groq_share = f"{round(100 * int(providers.get('groq') or 0) / llm)}%" if llm else "n/a"
        cells = [
            (str(requests), "questions answered"),
            (seconds(latency.get("ttft_p50")), "median first token"),
            (f"{round(100 * static / requests)}%", "answered from the profile, no model"),
            (groq_share, "of model answers on Groq"),
        ]
        cell = (width - 80) / len(cells)
        # About 9.5px per character at 19px: wrap so a label never runs into the next column.
        fit = max(8, int((cell - 28) / 9.5))
        for i, (value, label) in enumerate(cells):
            x = 40 + i * cell
            parts.append(f'<text class="d" x="{x:.0f}" y="150" font-size="76" fill="{TEXT}">{esc(value)}</text>')
            for n, line in enumerate(wrap_words(label, fit)[:2]):
                parts.append(f'<text class="t" x="{x:.0f}" y="{188 + n * 24}" font-size="19" fill="{MUTED}">{esc(line)}</text>')
        series = [int(b.get("requests") or 0) for b in data.get("series") or []]
        if series and max(series) > 0:
            peak = max(series)
            bar = (width - 80) / len(series)
            for i, value in enumerate(series):
                h = 24 * value / peak
                parts.append(f'<rect x="{40 + i * bar:.1f}" y="{268 - h:.1f}" width="{max(1.0, bar - 2):.1f}" height="{max(1.0, h):.1f}" rx="1" fill="{ACCENT_TEXT}" opacity=".7"/>')
    parts.append(f'<text class="m" x="{width - 40}" y="45" font-size="15" text-anchor="end" fill="{FAINT}">UPDATED {now:%Y-%m-%d %H:%M} UTC</text>')
    title = f"Live assistant telemetry from {host}, last 7 days: {requests} questions" if requests else f"Live assistant telemetry from {host}: no data"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="{esc(title)}">'
        f"<title>{esc(title)}</title><style>{fonts}"
        ".d{font-family:'Barlow Condensed','Arial Narrow',sans-serif;font-weight:600}"
        ".m{font-family:'JetBrains Mono',ui-monospace,monospace}"
        ".t{font-family:'IBM Plex Sans',system-ui,sans-serif}</style>"
        f"{''.join(parts)}</svg>\n"
    )


def main() -> int:
    fonts_file = HERE / "fonts.css"
    fonts = fonts_file.read_text() if fonts_file.exists() else ""
    data = fetch(f"{SITE}/api/metrics?range=7d")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(data, SITE.removeprefix("https://"), fonts), encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
