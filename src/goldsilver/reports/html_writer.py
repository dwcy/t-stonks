"""Write report HTML + sidecar JSON to the dated tree, and regenerate index.html."""

from __future__ import annotations

import html as _html
import os
from pathlib import Path

from goldsilver.reports.constants import safe_name
from goldsilver.reports.models import ReportRun, ReportStatus

_VERDICT_COLORS = {"BUY": "#1f9d55", "HOLD": "#d9a400", "SELL": "#d23b3b"}
_DOC_PREFIXES = ("<!doctype html", "<html")


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def is_valid_html(payload: str | None) -> bool:
    if not payload:
        return False
    head = payload.lstrip()
    # Skip leading HTML comments (the report leads with the VERDICT comment).
    while head.startswith("<!--"):
        end = head.find("-->")
        if end == -1:
            return False
        head = head[end + 3 :].lstrip()
    return head.lower().startswith(_DOC_PREFIXES)


def _rel_paths(run: ReportRun) -> tuple[str, str]:
    local = run.started_at
    date_dir = local.strftime("%Y-%m-%d")
    stem = f"{local.strftime('%H-%M')}-{safe_name(run.ticker)}"
    return f"{date_dir}/{stem}.html", f"{date_dir}/{stem}.json"


def _error_shell(run: ReportRun, raw: str | None) -> str:
    when = run.started_at.strftime("%Y-%m-%d %H:%M")
    detail = _html.escape(raw or run.error or "no output")
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Report error — {_html.escape(run.ticker)}</title></head><body>"
        f"<h1>Report problem for {_html.escape(run.label)} ({_html.escape(run.ticker)})</h1>"
        f"<p>Time: {when} · Status: <strong>{run.status.value}</strong></p>"
        f"<pre style='white-space:pre-wrap'>{detail}</pre></body></html>"
    )


def write_report(out_root: Path, run: ReportRun, html: str | None) -> ReportRun:
    """Resolve status against the HTML guard, write the report + sidecar, fill paths."""
    rel_html, rel_json = _rel_paths(run)
    target = out_root / rel_html
    target.parent.mkdir(parents=True, exist_ok=True)

    if run.status is ReportStatus.SUCCESS:
        if is_valid_html(html):
            body = html or ""
        else:
            run.status = ReportStatus.MALFORMED
            run.error = run.error or "output was not a valid HTML document"
            body = _error_shell(run, html)
    else:
        body = _error_shell(run, None)

    run.html_path = rel_html
    _atomic_write_text(target, body)
    _atomic_write_text(out_root / rel_json, run.model_dump_json(indent=2))
    return run


def _remove_pair(html_file: Path) -> None:
    html_file.unlink(missing_ok=True)
    html_file.with_suffix(".json").unlink(missing_ok=True)
    parent = html_file.parent
    try:
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
    except OSError:
        pass


def prune_ticker(out_root: Path, ticker: str, keep_rel: str | None) -> None:
    """Delete every report for this ticker except keep_rel (one report per ticker)."""
    safe = safe_name(ticker)
    keep = (out_root / keep_rel).resolve() if keep_rel else None
    for html_file in out_root.glob(f"*/*-{safe}.html"):
        if keep is not None and html_file.resolve() == keep:
            continue
        _remove_pair(html_file)


def delete_report(out_root: Path, rel_html: str | None) -> None:
    if rel_html:
        _remove_pair(out_root / rel_html)


def _load_runs(out_root: Path) -> list[ReportRun]:
    runs: list[ReportRun] = []
    for sidecar in out_root.glob("*/*.json"):
        try:
            runs.append(ReportRun.model_validate_json(sidecar.read_text("utf-8")))
        except (OSError, ValueError):
            continue
    return runs


def load_recent_runs(out_root: Path, limit: int = 50) -> list[ReportRun]:
    """Read persisted sidecars newest-first so the UI survives restarts."""
    if not out_root.is_dir():
        return []
    runs = sorted(_load_runs(out_root), key=lambda r: r.started_at, reverse=True)
    return runs[:limit]


def _badge(run: ReportRun) -> str:
    if run.status not in (ReportStatus.SUCCESS, ReportStatus.MALFORMED):
        return f"<span class='badge fail'>{run.status.value}</span>"
    if run.verdict is None:
        return "<span class='badge none'>—</span>"
    call = run.verdict.intraday
    color = _VERDICT_COLORS.get(call, "#666")
    return (
        f"<span class='badge' style='background:{color}'>{call}"
        f" {run.verdict.confidence}%</span>"
    )


def write_index(out_root: Path) -> Path:
    """Regenerate out_root/index.html grouping all reports by date, newest first."""
    runs = _load_runs(out_root)
    by_date: dict[str, list[ReportRun]] = {}
    for run in runs:
        by_date.setdefault(run.started_at.strftime("%Y-%m-%d"), []).append(run)

    sections: list[str] = []
    for date in sorted(by_date, reverse=True):
        rows = sorted(by_date[date], key=lambda r: r.started_at, reverse=True)
        items = []
        for run in rows:
            href = _html.escape(run.html_path or "")
            time = run.started_at.strftime("%H:%M")
            label = _html.escape(f"{run.label} ({run.ticker})")
            items.append(
                f"<li><span class='t'>{time}</span> {_badge(run)} "
                f"<a href='{href}'>{label}</a></li>"
            )
        sections.append(f"<h2>{date}</h2><ul>{''.join(items)}</ul>")

    body = (
        "".join(sections)
        if sections
        else "<p class='empty'>No reports generated yet.</p>"
    )
    doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Gold &amp; Silver — Analysis Reports</title><style>"
        "body{font-family:system-ui,sans-serif;max-width:820px;margin:2rem auto;"
        "padding:0 1rem;background:#14141b;color:#e6e6ee}"
        "h1{font-size:1.4rem}h2{margin-top:1.6rem;border-bottom:1px solid #333;"
        "padding-bottom:.3rem;font-size:1.05rem;color:#bbb}"
        "ul{list-style:none;padding:0}li{padding:.35rem 0}"
        "a{color:#8ab4ff;text-decoration:none}a:hover{text-decoration:underline}"
        ".t{display:inline-block;width:3.5rem;color:#888}"
        ".badge{display:inline-block;min-width:4.5rem;text-align:center;"
        "padding:.05rem .4rem;border-radius:.3rem;color:#fff;font-size:.8rem;margin:0 .4rem}"
        ".badge.none{background:#444}.badge.fail{background:#7a2b2b}"
        ".empty{color:#888}</style></head><body>"
        "<h1>Gold &amp; Silver — Analysis Reports</h1>" + body + "</body></html>"
    )
    index = out_root / "index.html"
    out_root.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(index, doc)
    return index
