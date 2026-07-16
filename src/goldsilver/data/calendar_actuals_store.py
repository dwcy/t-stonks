"""Disk store for fetched calendar actuals, keyed by stable event identity."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from goldsilver.data.models_macro import (
    CalendarEvent,
    CalendarSnapshot,
    EventAnalysis,
)
from goldsilver.data.settings import settings_path
from goldsilver.fsutil import atomic_write_text

RETENTION_DAYS = 30


def actuals_store_path() -> Path:
    return settings_path().parent / "calendar_actuals.json"


def event_key(event: CalendarEvent) -> str:
    scheduled = event.scheduled_time.astimezone(timezone.utc).isoformat()
    return f"{event.source}|{scheduled}|{event.title}"


class StoredActuals(BaseModel):
    model_config = ConfigDict(frozen=True)

    actual: str | None = None
    forecast: str | None = None
    previous: str | None = None
    actual_summary: str | None = None
    expected_summary: str | None = None
    analysis: EventAnalysis | None = None
    scheduled_time: datetime
    fetched_at: datetime

    @classmethod
    def from_event(cls, event: CalendarEvent) -> "StoredActuals":
        return cls(
            actual=event.actual,
            forecast=event.forecast,
            previous=event.previous,
            actual_summary=event.actual_summary,
            expected_summary=event.expected_summary,
            analysis=event.analysis,
            scheduled_time=event.scheduled_time,
            fetched_at=datetime.now(timezone.utc),
        )

    def apply_to(self, event: CalendarEvent) -> CalendarEvent:
        # A record with no `actual` is a forward-looking preview: fill forecast /
        # anticipated impact but leave `status` SCHEDULED so a later actuals fetch
        # can still release it.
        if self.actual is None:
            return event.model_copy(
                update={
                    "forecast": self.forecast or event.forecast,
                    "previous": self.previous or event.previous,
                    "expected_summary": self.expected_summary,
                    "analysis": self.analysis or event.analysis,
                }
            )
        return event.model_copy(
            update={
                "actual": self.actual,
                "forecast": self.forecast or event.forecast,
                "previous": self.previous or event.previous,
                "actual_summary": self.actual_summary,
                "analysis": self.analysis,
                "status": "RELEASED",
            }
        )


class CalendarActualsStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or actuals_store_path()
        self._records: dict[str, StoredActuals] = {}

    def load(self) -> None:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(raw, dict):
            return
        for key, value in raw.items():
            if not isinstance(key, str):
                continue
            try:
                self._records[key] = StoredActuals.model_validate(value)
            except ValidationError:
                continue

    def save(self) -> None:
        payload = {
            key: rec.model_dump(mode="json") for key, rec in self._records.items()
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(self._path, json.dumps(payload, indent=2))
        except OSError:
            pass

    def get(self, event: CalendarEvent) -> StoredActuals | None:
        return self._records.get(event_key(event))

    def put(self, event: CalendarEvent) -> None:
        self._records[event_key(event)] = StoredActuals.from_event(event)
        self.save()

    def apply(self, snapshot: CalendarSnapshot) -> CalendarSnapshot:
        if not self._records:
            return snapshot
        days = []
        changed = False
        for day in snapshot.days:
            events = []
            for event in day.events:
                record = self._records.get(event_key(event))
                if record is not None and event.status != "RELEASED":
                    events.append(record.apply_to(event))
                    changed = True
                else:
                    events.append(event)
            days.append(day.model_copy(update={"events": tuple(events)}))
        if not changed:
            return snapshot
        return snapshot.model_copy(update={"days": tuple(days)})

    def prune(self, now: datetime, retention_days: int = RETENTION_DAYS) -> int:
        cutoff = now - timedelta(days=retention_days)
        stale = [
            key for key, rec in self._records.items() if rec.scheduled_time < cutoff
        ]
        for key in stale:
            del self._records[key]
        if stale:
            self.save()
        return len(stale)
