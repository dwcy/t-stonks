# 0001. Store fetched calendar actuals as a keyed overlay re-applied to every fresh snapshot

Date: 2026-06-11

## Status

Accepted

## Decision

We will persist only the fetched actuals — not calendar snapshots — in
`calendar_actuals.json` next to `settings.json`, written atomically and keyed by
the stable event identity `source|scheduled-time-utc|title`. Each record holds
the released figures (`actual`, `forecast`, `previous`, `actual_summary`,
`analysis`) plus `scheduled_time` and `fetched_at`.

`CalendarService` re-applies this overlay to every freshly built snapshot, so
released figures survive both the periodic rebuild and app restarts. Repeat
fetches for a stored event are served from the file without dispatching the
Claude CLI, and records older than 30 days are pruned at startup.

## Context

The macro calendar's released figures (actuals) are fetched on demand via the
Claude CLI — a slow, paid operation. The fetched figures were merged only into
`CalendarService._last_snapshot`, which is in-memory state. The calendar
refresh loop rebuilds the snapshot from the static + FRED sources every 600
seconds and knows nothing about previously fetched actuals, so they were wiped
on the next refresh and on every app restart, prompting redundant re-fetches.

The project deliberately has no database or backend; durable state follows the
existing convention of small JSON files in the config dir (`settings.json`,
`trades.json`, `history/`) written via `atomic_write_text`.

## Consequences

- Fetched figures survive calendar refreshes and app restarts; each release is
  fetched at most once, eliminating repeat Claude CLI spend for the same event.
- The 600s refresh loop keeps its single job — discovering newly scheduled
  events — and stays oblivious to actuals; the overlay is applied after each
  rebuild in one place (`CalendarService._refresh_once`).
- The store is bounded by 30-day retention pruning at startup.
- The event key includes the scheduled time, so a rescheduled event is treated
  as a new event and fetches fresh — correct, but it means stored figures are
  not carried across reschedules.
- One more JSON file in the config dir to be aware of when debugging state.

## Alternatives Considered

- **Persist whole calendar snapshots.** Rejected: the refresh loop would still
  overwrite them unless its rebuild logic also changed; snapshots are mostly
  re-derivable schedule data, and stale schedule state would need its own
  invalidation rules.
- **Make the refresh loop merge from the previous in-memory snapshot.** Fixes
  the 600s wipe but not restarts, and entangles the rebuild with merge
  semantics.
- **Skip refreshing once data is fetched.** Rejected: the loop is still needed
  to discover newly scheduled events; the overlay makes it harmless instead.
