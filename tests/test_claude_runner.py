"""Tests for the Claude CLI runner: fence-strip, verdict parse, subprocess outcomes."""

from __future__ import annotations

import asyncio

import pytest

from goldsilver.reports import claude_runner
from goldsilver.reports.claude_runner import (
    extract_document,
    parse_verdict,
    run_claude,
    strip_fences,
)
from goldsilver.reports.models import ReportStatus

_VALID_HTML = (
    '<!-- VERDICT: {"intraday":"BUY","swing":"HOLD","confidence":72,'
    '"swedish_phase":"US_INFLUENCE","us_state":"OPENING","usd_impact":"Neutral",'
    '"gold_impact":"Positive","news_impact":"Neutral","geopolitical_impact":"Neutral",'
    '"top_reasons":["a","b","c"],"what_would_change":["x"]} -->\n'
    "<!doctype html><html><body><h1>Gold</h1></body></html>"
)


class _FakeProc:
    def __init__(self, out: bytes, err: bytes, code: int, delay: float) -> None:
        self._out, self._err, self.returncode, self._delay = out, err, code, delay
        self.killed = False

    async def communicate(self, data: bytes | None = None) -> tuple[bytes, bytes]:
        if self._delay:
            await asyncio.sleep(self._delay)
        return self._out, self._err

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        return self.returncode


def _patch_exec(monkeypatch, *, out=b"", err=b"", code=0, delay=0.0) -> None:
    async def fake_exec(*args, **kwargs):
        return _FakeProc(out, err, code, delay)

    monkeypatch.setattr(claude_runner.asyncio, "create_subprocess_exec", fake_exec)


def test_strip_fences_html_fence() -> None:
    assert strip_fences("```html\n<html></html>\n```") == "<html></html>"


def test_strip_fences_bare_fence() -> None:
    assert strip_fences("```\n<html></html>\n```") == "<html></html>"


def test_strip_fences_none() -> None:
    assert strip_fences("<html></html>") == "<html></html>"


def test_extract_document_drops_leading_prose() -> None:
    raw = (
        "The file write wasn't permitted, so I'll output the document directly.\n\n"
        "<!-- VERDICT: {} -->\n<!doctype html><html></html>"
    )
    doc = extract_document(raw)
    assert doc.startswith("<!-- VERDICT")


def test_extract_document_finds_doctype_after_prose() -> None:
    raw = "Here is the report:\n<!doctype html><html>x</html>"
    assert extract_document(raw).startswith("<!doctype html>")


def test_extract_document_no_marker_returns_text() -> None:
    assert extract_document("just an apology, no document") == (
        "just an apology, no document"
    )


def test_parse_verdict_valid() -> None:
    verdict = parse_verdict(_VALID_HTML)
    assert verdict is not None
    assert verdict.intraday == "BUY"
    assert verdict.confidence == 72


def test_parse_verdict_missing() -> None:
    assert parse_verdict("<html>no verdict</html>") is None


def test_parse_verdict_malformed_json() -> None:
    assert parse_verdict("<!-- VERDICT: {not json} -->") is None


def test_parse_verdict_survives_brace_arrow_inside_string() -> None:
    html = _VALID_HTML.replace(
        '"top_reasons":["a","b","c"]', '"top_reasons":["a} -->b"]'
    )

    verdict = parse_verdict(html)

    assert verdict is not None
    assert verdict.top_reasons == ["a} -->b"]


async def test_run_claude_success(monkeypatch) -> None:
    _patch_exec(monkeypatch, out=_VALID_HTML.encode())
    result = await run_claude(
        "prompt", allowed_tools=["WebSearch"], timeout_seconds=30, claude_path="claude"
    )
    assert result.status is ReportStatus.SUCCESS
    assert result.verdict is not None and result.verdict.intraday == "BUY"
    assert result.html is not None and result.html.lstrip().startswith("<!-- VERDICT")


async def test_run_claude_cli_missing(monkeypatch) -> None:
    monkeypatch.setattr(claude_runner, "find_claude", lambda: None)
    result = await run_claude(
        "prompt", allowed_tools=["WebSearch"], timeout_seconds=30, claude_path=None
    )
    assert result.status is ReportStatus.CLI_MISSING


async def test_run_claude_timeout(monkeypatch) -> None:
    _patch_exec(monkeypatch, out=b"late", delay=5.0)
    result = await run_claude(
        "prompt",
        allowed_tools=["WebSearch"],
        timeout_seconds=0.05,
        claude_path="claude",
    )
    assert result.status is ReportStatus.TIMEOUT


async def test_run_claude_nonzero_exit(monkeypatch) -> None:
    _patch_exec(monkeypatch, out=b"", err=b"boom", code=1)
    result = await run_claude(
        "prompt", allowed_tools=["WebSearch"], timeout_seconds=30, claude_path="claude"
    )
    assert result.status is ReportStatus.ERROR
    assert result.error is not None and "boom" in result.error
