# Contract: Report File & Index

Path scheme, HTML guard, sidecar, and index generation. Implements research D5/D6.

## Per-report paths

Relative to **repo root**, in `Europe/Stockholm` local time:

```
reports/<YYYY-MM-DD>/<HH-MM>-<SAFE_TICKER>.html      # the report
reports/<YYYY-MM-DD>/<HH-MM>-<SAFE_TICKER>.json      # ReportRun sidecar
reports/index.html                                   # regenerated each run
```

- `<YYYY-MM-DD>` and `<HH-MM>` from the run's `started_at` in Stockholm time.
- `SAFE_TICKER` = `symbol.upper()` with each of `/ . space :` → `-`. Examples:
  `XAU`→`XAU`, `LUG.ST`→`LUG-ST`, `BRK.B`→`BRK-B`.
- Directories created with `parents=True, exist_ok=True`.
- Per-minute + per-ticker naming guarantees no collisions within a run.

## HTML validity guard (decides SUCCESS vs MALFORMED)

After fence-stripping (claude-cli-invocation contract), the payload is `SUCCESS` iff,
after `lstrip()`, it begins case-insensitively with `<!doctype html` or `<html`. Otherwise
`MALFORMED`: write an error shell —

```html
<!doctype html><html><head><meta charset="utf-8"><title>Report error</title></head>
<body><h1>Malformed report for {TICKER} at {STOCKHOLM_TIME}</h1>
<p>Status: {STATUS}</p><pre>{escaped raw output / error}</pre></body></html>
```

— so a file always exists and the index never has dead links.

## Sidecar JSON

The serialized `ReportRun` (data-model.md), including the parsed `Verdict` (or `null`).
Authoritative source for the index and the TUI recent-list — neither parses the HTML
body. The line-1 `<!-- VERDICT: {json} -->` comment is the parse source; if absent/invalid
→ `verdict: null`, status stays `SUCCESS`.

## index.html

Regenerated after every run (unless `--no-index`) by scanning `reports/*/*.json`:

- Self-contained HTML (inline CSS), title "Gold & Silver — Analysis Reports".
- One `<h2>` per date, **newest date first**; within a date, **newest time first**.
- Each entry: time · ticker · color-coded intraday verdict · confidence · `<a href>`
  (relative path) opening the report.
- Entries with `verdict: null` show "—"; failed runs show their status badge.
- Empty state (no reports yet): a short "No reports generated yet" placeholder.

## Git

`reports/` is artifacts, not source → add `reports/` to `.gitignore`. The directory is
created on first run; it need not exist in a clean checkout.

## Linking from the TUI

The TUI opens a report via `webbrowser.open(html_path.resolve().as_uri())`. The shown
link uses an OSC-8 hyperlink where the terminal supports it (Windows Terminal does),
falling back to an Enter-to-open action on the selected row.
