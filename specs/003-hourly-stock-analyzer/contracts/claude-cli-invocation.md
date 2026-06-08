# Contract: Claude CLI Invocation

How `claude_runner.py` shells out to the Claude CLI for one report. Implements research
D1. One process per ticker per run.

## Command

```
<claude> -p <PROMPT> --output-format text --allowed-tools WebSearch WebFetch Read
```

- `<claude>` is resolved via `shutil.which("claude")`; on Windows this yields
  `claude.cmd` (the `cli-llm-app` `.cmd` gotcha). If `None` → `ReportStatus.CLI_MISSING`,
  no process spawned.
- `<PROMPT>` is the fully-substituted `analysis_prompt.md` (analysis-prompt contract).
  Passed as a single argument (or via stdin if length is a concern on Windows; the runner
  prefers stdin: `claude -p - <prompt-on-stdin>` form if supported, else arg).
- `--allowed-tools` is taken from `ReportSettings.allowed_tools`; default grants only web
  read + `Read`. **No** `Write`, `Bash`, or `Edit` — the job must not touch the repo or
  shell. (Least privilege; the wrapper owns file writes.)

## Execution

- `asyncio.create_subprocess_exec(<claude>, *args, stdout=PIPE, stderr=PIPE)` — never
  blocking; runs inside the app event loop or the headless `asyncio.run`.
- Enforce `timeout_seconds` via `asyncio.wait_for`; on expiry, terminate the process tree
  and record `ReportStatus.TIMEOUT`.
- Capture stdout (the HTML) and stderr (diagnostics). Non-zero exit → `ReportStatus.ERROR`
  with stderr tail in `error`.

## Output post-processing (the fence-strip guard, D5)

1. Strip a leading line matching ```` ```html ```` / ```` ``` ```` and a trailing
   ```` ``` ````.
2. `lstrip()` whitespace.
3. The HTML guard (report-file contract) decides `SUCCESS` vs `MALFORMED`.

## Prompt-side requirements (asserted, not enforced by flags)

The prompt instructs the model to:
- Use the granted web tools to fetch **today's** data; never fabricate quotes.
- State explicitly any datum it could not retrieve.
- Emit **only** a complete HTML document, first line a `<!-- VERDICT: {json} -->`
  comment (data-model `Verdict`).

## Auth & environment

- Relies on the user's existing `claude` login (subscription auth). **No** `ANTHROPIC_API_KEY`
  is set or required (repo CLAUDE.md: no credentials).
- Inherits the ambient environment; the runner does not inject secrets.
- Model selection: omit `--model` to use the CLI default, or set it from a future
  `ReportSettings.model` (not in v1). Document the chosen default in quickstart.

## Failure mapping

| Situation | `ReportStatus` | File written |
|---|---|---|
| `claude` not on PATH | `CLI_MISSING` | none |
| Exceeded timeout | `TIMEOUT` | error shell |
| Non-zero exit | `ERROR` | error shell |
| Output not HTML after strip | `MALFORMED` | error shell wrapping raw text |
| Valid HTML | `SUCCESS` | report HTML + sidecar |
