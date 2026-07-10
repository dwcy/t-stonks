# Contract: Click-Region Interactions (news, indicators, calendar)

Stories 2, 3, and 4 all add click-driven behavior to widgets that currently render a
single `rich.text.Text` block rather than discrete per-item widgets. Rather than three
independent implementations, they share one interaction convention already
established in this codebase by `calendar_panel.py::_CalendarBody.on_click`.

## Existing precedent (unchanged, reused)

```python
# calendar_panel.py (existing, not modified by this feature)
class _CalendarBody(Static):
    def on_click(self, event: events.Click) -> None:
        style = self.get_style_at(event.x, event.y)
        cal_event = style.meta.get("cal_event")
        if cal_event is not None:
            self.post_message(self.EventSelected(cal_event))
```

Spans carry a `meta={"cal_event": event}` dict via `Text.assemble` / `Text.append`,
and `get_style_at(x, y)` recovers the meta dict for whatever character the click
landed on. This is the pattern all three stories below extend.

## Story 2 — news "read more"

`news_panel.py`'s render function attaches `meta={"news_url": item.url}` to each
item's title span (only when `item.url` is truthy — FR-008). New `on_click` handler
on the panel:

```python
def on_click(self, event: events.Click) -> None:
    style = self.get_style_at(event.x, event.y)
    url = style.meta.get("news_url")
    if url:
        webbrowser.open(url)
```

## Story 3 — indicator description toggle

`metal_panel.py::_render_indicators()` attaches `meta={"indicator": key}` to each
badge span. New `on_click` handler toggles `self._expanded_indicator` between `None`
and the clicked key (clicking the already-expanded badge, or clicking empty space,
collapses it — FR-011). `watch__expanded_indicator` triggers a re-render that inserts
the `IndicatorInfo.description` + `.rationale` text beneath the badge row when set.
This click must **not** re-trigger any strategy computation — it only toggles local
render state (FR-011).

## Story 4 — calendar spinner (state, not click)

Not a click contract — included here because it reuses the *rendering* half of the
same convention (per-row meta-driven state) without user interaction. `calendar_panel.py`
tracks `_fetching_event_ids: set[str]` (populated by `ActualsFetcher` callbacks, see
`research.md` R5) and checks membership when rendering each event row's span to decide
whether to show the animated spinner frame instead of the (not-yet-available) actual
value.

## Shared helper

`webbrowser.open(url)` (Story 2) is called directly — no wrapper needed, this is a
one-line stdlib call already safe to use from a Textual event handler (non-blocking,
hands off to the OS).

## Why one contract, not three

All three add "meta-tagged clickable/stateful spans on a `Static`-rendered `Text`
block" to widgets that were built before this pattern existed anywhere except the
calendar panel. Documenting them together keeps the technique consistent (same method
name shape, same `get_style_at` idiom) across the three new call sites instead of each
one reinventing slightly different plumbing.
