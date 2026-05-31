from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

from goldsilver.data.signal_strategies import (
    ParamSpec,
    SignalStrategy,
    STRATEGY_REGISTRY,
)


@dataclass(slots=True)
class StrategyEditData:
    name: str
    specs: tuple[ParamSpec, ...]
    values: dict[str, float]


OnEdit = Callable[[str, str, float], None]


class EditMathScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(
        self,
        current: list[StrategyEditData],
        *,
        on_edit: OnEdit,
        on_reset: Callable[[str], None],
    ) -> None:
        super().__init__()
        self._data = current
        self._on_edit = on_edit
        self._on_reset = on_reset
        self._defaults: dict[str, dict[str, float]] = {
            d.name: {s.key: s.default for s in d.specs} for d in self._data
        }

    def compose(self) -> ComposeResult:
        with Container(id="edit-math-dialog"):
            yield Label("Edit signal math", id="edit-math-title")
            with VerticalScroll(id="edit-math-body"):
                for entry in self._data:
                    with Vertical(classes="math-group"):
                        with Horizontal(classes="math-header"):
                            yield Label(entry.name, classes="math-group-label")
                            yield Button(
                                "Reset",
                                variant="default",
                                id=self._reset_id(entry.name),
                                classes="math-reset",
                            )
                        for spec in entry.specs:
                            with Horizontal(classes="math-field"):
                                yield Label(
                                    f"{spec.label}",
                                    classes="math-field-label",
                                )
                                yield Input(
                                    value=f"{entry.values.get(spec.key, spec.default):g}",
                                    placeholder=f"{spec.default:g}",
                                    id=self._input_id(entry.name, spec.key),
                                    classes="math-input",
                                )
            yield Button("Close", variant="primary", id="edit-math-close")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._maybe_emit(event.input.id, event.value)

    def on_input_changed(self, event: Input.Changed) -> None:
        # Apply on blur instead of every keystroke — handled via Submitted.
        return

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "edit-math-close":
            self.dismiss()
            return
        if bid.startswith("reset-"):
            name = self._strategy_name_from_reset(bid)
            if name is not None:
                self._on_reset(name)
                self._reset_inputs_for(name)

    def _maybe_emit(self, input_id: str | None, raw: str) -> None:
        if not input_id or not input_id.startswith("param-"):
            return
        try:
            _, name, key = self._decode_input_id(input_id)
        except ValueError:
            return
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return
        self._on_edit(name, key, value)

    def _reset_inputs_for(self, strategy_name: str) -> None:
        defaults = self._defaults.get(strategy_name, {})
        for key, value in defaults.items():
            wid = self._input_id(strategy_name, key)
            try:
                widget = self.query_one(f"#{wid}", Input)
            except Exception:
                continue
            widget.value = f"{value:g}"

    @staticmethod
    def _slug(name: str) -> str:
        return "".join(
            ch.lower() if ch.isalnum() else "-" for ch in name
        ).strip("-")

    @classmethod
    def _input_id(cls, strategy_name: str, key: str) -> str:
        return f"param-{cls._slug(strategy_name)}--{key}"

    @classmethod
    def _reset_id(cls, strategy_name: str) -> str:
        return f"reset-{cls._slug(strategy_name)}"

    def _decode_input_id(self, input_id: str) -> tuple[str, str, str]:
        # input_id = "param-{slug}--{key}"; map slug back to a known name.
        body = input_id[len("param-") :]
        slug, _, key = body.partition("--")
        for entry in self._data:
            if self._slug(entry.name) == slug:
                return "param", entry.name, key
        raise ValueError(input_id)

    def _strategy_name_from_reset(self, button_id: str) -> str | None:
        slug = button_id[len("reset-") :]
        for entry in self._data:
            if self._slug(entry.name) == slug:
                return entry.name
        return None


def build_edit_data(
    strategies: list[SignalStrategy],
) -> list[StrategyEditData]:
    out: list[StrategyEditData] = []
    for s in strategies:
        out.append(
            StrategyEditData(
                name=s.name,
                specs=s.param_specs(),
                values=s.params(),
            )
        )
    return out


__all__ = [
    "EditMathScreen",
    "StrategyEditData",
    "build_edit_data",
    "STRATEGY_REGISTRY",
]
