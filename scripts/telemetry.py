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
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SITE = "https://pranjulgupta.com"
HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "assets" / "telemetry.svg"
CONTRIBUTIONS = HERE.parent / "assets" / "contributions.svg"
USER = "Pranjulcr7"
LEVELS = ("#2a2c2e", "#5c3d36", "#a85a42", "#da5d3e", "#f6d2c6")

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


def render(data: dict | None, host: str, fonts: str = "", now: datetime | None = None, note: str | None = None) -> str:
    """The card; `data` is the /api/metrics?range=7d response, or None when unavailable.
    `note` replaces the empty-state message (the first card, before any refresh)."""
    now = now or datetime.now(timezone.utc)
    totals = (data or {}).get("totals") or {}
    requests = int(totals.get("requests") or 0)
    width, height = 1200, 270
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
        for i, (value, label) in enumerate(cells):
            x = 40 + i * cell
            parts.append(f'<text class="d" x="{x:.0f}" y="150" font-size="76" fill="{TEXT}">{esc(value)}</text>')
            parts.append(f'<text class="t" x="{x:.0f}" y="188" font-size="19" fill="{MUTED}">{esc(label)}</text>')
        series = [int(b.get("requests") or 0) for b in data.get("series") or []]
        if series and max(series) > 0:
            peak = max(series)
            bar = (width - 80) / len(series)
            for i, value in enumerate(series):
                h = 24 * value / peak
                parts.append(f'<rect x="{40 + i * bar:.1f}" y="{246 - h:.1f}" width="{max(1.0, bar - 2):.1f}" height="{max(1.0, h):.1f}" rx="1" fill="{ACCENT_TEXT}" opacity=".7"/>')
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


def fetch_contributions(user: str = USER) -> dict | None:
    """GitHub's public contribution calendar, in the same rows, columns, and levels.

    Returns None when GitHub cannot be reached. `total` is the count in GitHub's
    heading. Each cell is one day from the table: row 0 is Sunday, `level` is
    GitHub's 0-4 color, `count` is the number in that day's tooltip.
    """
    request = urllib.request.Request(
        f"https://github.com/users/{user}/contributions",
        headers={"User-Agent": "github-profile-telemetry", "Accept": "text/html"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 (fixed https URL)
            page = response.read().decode()
    except Exception as exc:
        print(f"warning: contributions: {exc}", file=sys.stderr)
        return None
    heading = re.search(r"([\d,]+)\s+contributions?\s+in the last year", page)
    months = re.findall(
        r'class="ContributionCalendar-label"[^>]*colspan="(\d+)"[\s\S]*?aria-hidden="true"[^>]*>([^<]+)',
        page,
    )
    cells = []
    for date, row, col, level in re.findall(
        r'data-date="(\d{4}-\d{2}-\d{2})" id="contribution-day-component-(\d+)-(\d+)" data-level="(\d)"',
        page,
    ):
        cells.append({"date": date, "row": int(row), "col": int(col), "level": int(level), "count": 0})
    for cell_id, tip in re.findall(r'for="(contribution-day-component-\d+-\d+)"[^>]*>(.*?)</tool-tip>', page, re.S):
        row_s, col_s = cell_id.rsplit("-", 2)[-2:]
        count = re.search(r"([\d,]+)\s+contributions?", tip)
        found = int(count.group(1).replace(",", "")) if count else 0
        for cell in cells:
            if cell["row"] == int(row_s) and cell["col"] == int(col_s):
                cell["count"] = found
                break
    if not cells:
        return None
    total = int(heading.group(1).replace(",", "")) if heading else sum(cell["count"] for cell in cells)
    return {"total": total, "months": [(label.strip(), int(span)) for span, label in months], "cells": cells}


def render_contributions(calendar: dict | list | None, fonts: str = "", note: str | None = None) -> str:
    """The same week grid GitHub shows, in the site's colors.

    The cells are sized from the number of weeks so the grid spans the card; the total, the
    month labels, and the legend line up with its edges. A month label shows only where its
    weeks leave room for it (a partial first or last month often does not). Cells fade in,
    and they keep their fill if the animation is removed.
    """
    width = 1200
    left, right = 72, 40
    cells = calendar.get("cells") if isinstance(calendar, dict) else None
    parts: list[str] = []
    if not cells:
        height = 292
        message = note or "GitHub could not be reached for this refresh."
        parts.append(f'<text class="d" x="40" y="160" font-size="72" fill="{MUTED}">No data</text>')
        parts.append(f'<text class="t" x="40" y="208" font-size="21" fill="{MUTED}">{esc(message)}</text>')
        total = 0
    else:
        total = int(calendar.get("total") if calendar.get("total") is not None else sum(cell["count"] for cell in cells))
        cols = max(int(cell["col"]) for cell in cells) + 1
        step = max(8, min(22, (width - left - right + 4) // cols))
        cell_size = step - 4
        grid_top = 124
        grid_right = left + cols * step - 4
        grid_bottom = grid_top + 7 * step - 4
        height = grid_bottom + 52
        parts.append(f'<text class="d" x="{grid_right}" y="58" font-size="48" text-anchor="end" fill="{TEXT}">{total}</text>')
        parts.append(f'<text class="m" x="{grid_right}" y="80" font-size="13" letter-spacing="1.1" text-anchor="end" fill="{FAINT}">CONTRIBUTIONS</text>')
        column = 0
        for label, span in calendar.get("months") or []:
            if span * step >= 36:
                parts.append(f'<text class="m" x="{left + column * step}" y="{grid_top - 12}" font-size="12" fill="{FAINT}">{esc(label)}</text>')
            column += span
        for name, row in (("Mon", 1), ("Wed", 3), ("Fri", 5)):
            parts.append(f'<text class="m" x="{right}" y="{grid_top + row * step + cell_size - 3}" font-size="11" fill="{FAINT}">{name}</text>')
        for cell in cells:
            level = min(4, max(0, int(cell["level"])))
            x = left + int(cell["col"]) * step
            y = grid_top + int(cell["row"]) * step
            delay = int(cell["col"]) * 0.028 + int(cell["row"]) * 0.012
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" rx="3" fill="{LEVELS[level]}" opacity="1">'
                f'<title>{cell["count"]} on {cell["date"]}</title>'
                f'<animate attributeName="opacity" values="0;1" dur="0.4s" begin="{delay:.2f}s" fill="freeze"/>'
                f"</rect>"
            )
        # Legend under the grid's right edge, as on GitHub: LESS, five swatches, MORE.
        legend_y = grid_bottom + 30
        more_x = grid_right - 34
        swatches_x = more_x - 12 - len(LEVELS) * 18
        parts.append(f'<text class="m" x="{swatches_x - 10}" y="{legend_y}" font-size="12" text-anchor="end" fill="{FAINT}">LESS</text>')
        for i, color in enumerate(LEVELS):
            parts.append(f'<rect x="{swatches_x + i * 18}" y="{legend_y - 11}" width="12" height="12" rx="2" fill="{color}"/>')
        parts.append(f'<text class="m" x="{more_x}" y="{legend_y}" font-size="12" fill="{FAINT}">MORE</text>')
    frame = [
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="14" fill="{BG}" stroke="{RULE}"/>',
        f'<rect x="40" y="38" width="22" height="2" fill="{ACCENT}"/>',
        f'<text class="m" x="72" y="45" font-size="16" letter-spacing="1.8" fill="{MUTED}">GITHUB CONTRIBUTIONS, LAST YEAR</text>',
    ]
    title = f"{total} contributions in the last year" if cells else "GitHub contributions: no data"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="{esc(title)}">'
        f"<title>{esc(title)}</title><style>{fonts}"
        ".d{font-family:'Barlow Condensed','Arial Narrow',sans-serif;font-weight:600}"
        ".m{font-family:'JetBrains Mono',ui-monospace,monospace}"
        ".t{font-family:'IBM Plex Sans',system-ui,sans-serif}</style>"
        f"{''.join(frame + parts)}</svg>\n"
    )


def main() -> int:
    fonts_file = HERE / "fonts.css"
    fonts = fonts_file.read_text() if fonts_file.exists() else ""
    data = fetch(f"{SITE}/api/metrics?range=7d")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(data, SITE.removeprefix("https://"), fonts), encoding="utf-8")
    days = fetch_contributions()
    CONTRIBUTIONS.write_text(
        render_contributions(days, fonts, note=None if days else "Waiting for the first daily refresh."),
        encoding="utf-8",
    )
    print(f"wrote {OUT}")
    print(f"wrote {CONTRIBUTIONS} ({0 if not days else len(days.get('cells', []))} days, {0 if not days else days.get('total')} contributions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
