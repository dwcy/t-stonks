"""Async wrapper around the Claude CLI: run one analysis, strip fences, parse the verdict."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from dataclasses import dataclass

from pydantic import ValidationError

from goldsilver.reports.models import ReportStatus, Verdict

OUTPUT_FORMAT = "text"
ALLOWED_TOOLS_FLAG = "--allowed-tools"

_VERDICT_RE = re.compile(r"<!--\s*VERDICT:\s*(\{.*?\})\s*-->", re.DOTALL)
_DOC_START_RE = re.compile(r"<!--\s*VERDICT:|<!doctype html|<html", re.IGNORECASE)


@dataclass(slots=True)
class ClaudeResult:
    status: ReportStatus
    html: str | None = None
    verdict: Verdict | None = None
    error: str | None = None


def find_claude() -> str | None:
    return shutil.which("claude")


def strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        newline = t.find("\n")
        if newline != -1:
            t = t[newline + 1 :]
        stripped = t.rstrip()
        if stripped.endswith("```"):
            t = stripped[:-3]
    return t.strip()


def extract_document(text: str) -> str:
    """Strip fences and slice from the first doc marker, dropping any leading prose."""
    t = strip_fences(text)
    match = _DOC_START_RE.search(t)
    if match:
        return t[match.start() :].strip()
    return t


def parse_verdict(html: str) -> Verdict | None:
    match = _VERDICT_RE.search(html)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
        return Verdict.model_validate(data)
    except (json.JSONDecodeError, ValidationError, TypeError):
        return None


async def run_claude(
    prompt: str,
    *,
    allowed_tools: list[str],
    timeout_seconds: int,
    claude_path: str | None = None,
) -> ClaudeResult:
    path = claude_path or find_claude()
    if path is None:
        return ClaudeResult(
            status=ReportStatus.CLI_MISSING,
            error="`claude` CLI not found on PATH",
        )

    args = [
        "-p",
        "--output-format",
        OUTPUT_FORMAT,
        ALLOWED_TOOLS_FLAG,
        *allowed_tools,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            path,
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        return ClaudeResult(status=ReportStatus.ERROR, error=str(exc))

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(prompt.encode("utf-8")),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        proc.kill()
        try:
            await proc.wait()
        except ProcessLookupError:
            pass
        return ClaudeResult(
            status=ReportStatus.TIMEOUT,
            error=f"timed out after {timeout_seconds}s",
        )

    if proc.returncode != 0:
        tail = stderr.decode("utf-8", "replace").strip()[-500:]
        return ClaudeResult(
            status=ReportStatus.ERROR,
            error=f"claude exited {proc.returncode}: {tail}",
        )

    html = extract_document(stdout.decode("utf-8", "replace"))
    return ClaudeResult(
        status=ReportStatus.SUCCESS,
        html=html,
        verdict=parse_verdict(html),
    )
