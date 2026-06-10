from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from goldsilver.data.models_macro import Signal, SignalAction, SignalKind


WINDOW_30M = timedelta(minutes=30)
WINDOW_2M = timedelta(minutes=2)


@dataclass(slots=True)
class ParamSpec:
    key: str
    label: str
    default: float
    min: float
    max: float
    step: float


class SignalStrategy(Protocol):
    name: str
    kind: SignalKind

    def observe(self, symbol: str, price: float, at: datetime) -> Signal: ...
    def params(self) -> dict[str, float]: ...
    def set_param(self, key: str, value: float) -> None: ...
    def param_specs(self) -> tuple[ParamSpec, ...]: ...
    def reset(self, symbol: str | None = None) -> None: ...


def _none(
    *,
    symbol: str,
    strategy: str,
    kind: SignalKind,
    reason: str,
    at: datetime,
    intensity: float = 0.0,
) -> Signal:
    return Signal(
        symbol=symbol,
        strategy=strategy,
        kind=kind,
        action="NONE",
        intensity_sigma=intensity,
        reason=reason,
        at=at,
    )


def _make(
    *,
    symbol: str,
    strategy: str,
    kind: SignalKind,
    action: SignalAction,
    intensity: float,
    reason: str,
    at: datetime,
) -> Signal:
    return Signal(
        symbol=symbol,
        strategy=strategy,
        kind=kind,
        action=action,
        intensity_sigma=intensity,
        reason=reason,
        at=at,
    )


class _WindowState:
    __slots__ = ("ticks", "last_fire")

    def __init__(self) -> None:
        self.ticks: deque[tuple[datetime, float]] = deque()
        self.last_fire: tuple[datetime, Signal] | None = None


class _WindowBase:
    name: str
    kind: SignalKind
    _window: timedelta = WINDOW_30M
    _cooldown_seconds: float = 60.0

    def __init__(self) -> None:
        self._state: dict[str, _WindowState] = {}

    def reset(self, symbol: str | None = None) -> None:
        if symbol is None:
            self._state.clear()
        else:
            self._state.pop(symbol, None)

    def _push(self, symbol: str, price: float, at: datetime) -> _WindowState:
        st = self._state.setdefault(symbol, _WindowState())
        st.ticks.append((at, price))
        cutoff = at - self._window
        while st.ticks and st.ticks[0][0] < cutoff:
            st.ticks.popleft()
        return st

    def _hit_cooldown(self, st: _WindowState, at: datetime) -> Signal | None:
        if st.last_fire is None:
            return None
        if at - st.last_fire[0] < timedelta(seconds=self._cooldown_seconds):
            return st.last_fire[1]
        return None

    def _fired(self, st: _WindowState, at: datetime, sig: Signal) -> Signal:
        if sig.action != "NONE":
            st.last_fire = (at, sig)
        return sig


def _stats(prices: list[float]) -> tuple[float, float]:
    n = len(prices)
    if n == 0:
        return 0.0, 0.0
    mean = sum(prices) / n
    if n == 1:
        return mean, 0.0
    var = sum((p - mean) ** 2 for p in prices) / n
    return mean, math.sqrt(var)


class SlopeMomentum(_WindowBase):
    name = "Slope Momentum"
    kind: SignalKind = "momentum"
    MIN_SAMPLES = 8

    def __init__(self) -> None:
        super().__init__()
        self._slope_window_s = 120.0
        self._slope_pct_thr = 0.03
        self._z_align = 0.5
        self._cooldown_seconds = 45.0

    def params(self) -> dict[str, float]:
        return {
            "slope_window_s": self._slope_window_s,
            "slope_pct_thr": self._slope_pct_thr,
            "z_align": self._z_align,
            "cooldown_s": self._cooldown_seconds,
        }

    def set_param(self, key: str, value: float) -> None:
        if key == "slope_window_s":
            self._slope_window_s = max(15.0, value)
        elif key == "slope_pct_thr":
            self._slope_pct_thr = max(0.0, value)
        elif key == "z_align":
            self._z_align = max(0.0, value)
        elif key == "cooldown_s":
            self._cooldown_seconds = max(5.0, value)

    def param_specs(self) -> tuple[ParamSpec, ...]:
        return (
            ParamSpec("slope_window_s", "Slope window (s)", 120.0, 15.0, 600.0, 5.0),
            ParamSpec("slope_pct_thr", "Slope threshold (%)", 0.03, 0.0, 1.0, 0.01),
            ParamSpec("z_align", "Z alignment", 0.5, 0.0, 3.0, 0.1),
            ParamSpec("cooldown_s", "Cooldown (s)", 45.0, 5.0, 600.0, 5.0),
        )

    def observe(self, symbol: str, price: float, at: datetime) -> Signal:
        at = at.astimezone(timezone.utc)
        st = self._push(symbol, price, at)
        cooled = self._hit_cooldown(st, at)
        if cooled is not None:
            return cooled
        if len(st.ticks) < self.MIN_SAMPLES:
            return _none(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                reason="warming up",
                at=at,
            )
        slope_cutoff = at - timedelta(seconds=self._slope_window_s)
        slope_ticks = [p for t, p in st.ticks if t >= slope_cutoff]
        if len(slope_ticks) < 2:
            return _none(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                reason="no slope window",
                at=at,
            )
        prices = [p for _, p in st.ticks]
        mean, std = _stats(prices)
        if mean == 0.0 or std == 0.0:
            return _none(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                reason="flat",
                at=at,
            )
        slope = price - slope_ticks[0]
        slope_pct = slope / mean * 100.0
        z = (price - mean) / std
        reason = f"slope {slope_pct:+.2f}% · z {z:+.1f}"
        if slope_pct > self._slope_pct_thr and z > self._z_align:
            sig = _make(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                action="BUY",
                intensity=abs(z),
                reason=reason,
                at=at,
            )
            return self._fired(st, at, sig)
        if slope_pct < -self._slope_pct_thr and z < -self._z_align:
            sig = _make(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                action="SELL",
                intensity=abs(z),
                reason=reason,
                at=at,
            )
            return self._fired(st, at, sig)
        return _none(
            symbol=symbol,
            strategy=self.name,
            kind=self.kind,
            reason=reason,
            at=at,
            intensity=abs(z),
        )


class BollingerRecoil(_WindowBase):
    name = "Bollinger Recoil"
    kind: SignalKind = "recoil"
    MIN_SAMPLES = 12

    def __init__(self) -> None:
        super().__init__()
        self._band_sigma = 2.0
        self._slope_window_s = 120.0
        self._pct_b_high = 0.97
        self._pct_b_low = 0.03
        self._cooldown_seconds = 300.0

    def params(self) -> dict[str, float]:
        return {
            "band_sigma": self._band_sigma,
            "slope_window_s": self._slope_window_s,
            "pct_b_high": self._pct_b_high,
            "pct_b_low": self._pct_b_low,
            "cooldown_s": self._cooldown_seconds,
        }

    def set_param(self, key: str, value: float) -> None:
        if key == "band_sigma":
            self._band_sigma = max(0.1, value)
        elif key == "slope_window_s":
            self._slope_window_s = max(15.0, value)
        elif key == "pct_b_high":
            self._pct_b_high = min(1.5, max(0.5, value))
        elif key == "pct_b_low":
            self._pct_b_low = min(0.5, max(-0.5, value))
        elif key == "cooldown_s":
            self._cooldown_seconds = max(5.0, value)

    def param_specs(self) -> tuple[ParamSpec, ...]:
        return (
            ParamSpec("band_sigma", "Band σ", 2.0, 0.5, 4.0, 0.1),
            ParamSpec("slope_window_s", "Slope window (s)", 120.0, 15.0, 600.0, 5.0),
            ParamSpec("pct_b_high", "%B high", 0.97, 0.5, 1.5, 0.01),
            ParamSpec("pct_b_low", "%B low", 0.03, -0.5, 0.5, 0.01),
            ParamSpec("cooldown_s", "Cooldown (s)", 300.0, 5.0, 1800.0, 15.0),
        )

    def observe(self, symbol: str, price: float, at: datetime) -> Signal:
        at = at.astimezone(timezone.utc)
        st = self._push(symbol, price, at)
        cooled = self._hit_cooldown(st, at)
        if cooled is not None:
            return cooled
        if len(st.ticks) < self.MIN_SAMPLES:
            return _none(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                reason="warming up",
                at=at,
            )
        prices = [p for _, p in st.ticks]
        mean, std = _stats(prices)
        if std == 0.0:
            return _none(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                reason="flat",
                at=at,
            )
        upper = mean + self._band_sigma * std
        lower = mean - self._band_sigma * std
        span = max(upper - lower, 1e-9)
        pct_b = (price - lower) / span
        slope_cutoff = at - timedelta(seconds=self._slope_window_s)
        slope_ticks = [p for t, p in st.ticks if t >= slope_cutoff]
        if len(slope_ticks) < 2:
            slope_pct = 0.0
        else:
            slope_pct = (price - slope_ticks[0]) / mean * 100.0
        reason = f"%B {pct_b:.2f} · slope {slope_pct:+.2f}%"
        intensity = abs(pct_b - 0.5) * 2.0
        if pct_b >= self._pct_b_high and slope_pct <= 0.0:
            sig = _make(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                action="SELL",
                intensity=intensity,
                reason=reason,
                at=at,
            )
            return self._fired(st, at, sig)
        if pct_b <= self._pct_b_low and slope_pct >= 0.0:
            sig = _make(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                action="BUY",
                intensity=intensity,
                reason=reason,
                at=at,
            )
            return self._fired(st, at, sig)
        return _none(
            symbol=symbol,
            strategy=self.name,
            kind=self.kind,
            reason=reason,
            at=at,
            intensity=intensity,
        )


class RocMomentum(_WindowBase):
    name = "ROC Momentum"
    kind: SignalKind = "momentum"
    _window = WINDOW_2M
    MIN_SAMPLES = 4

    def __init__(self) -> None:
        super().__init__()
        self._roc_pct_thr = 0.05
        self._cooldown_seconds = 60.0

    def params(self) -> dict[str, float]:
        return {
            "roc_pct_thr": self._roc_pct_thr,
            "cooldown_s": self._cooldown_seconds,
        }

    def set_param(self, key: str, value: float) -> None:
        if key == "roc_pct_thr":
            self._roc_pct_thr = max(0.0, value)
        elif key == "cooldown_s":
            self._cooldown_seconds = max(5.0, value)

    def param_specs(self) -> tuple[ParamSpec, ...]:
        return (
            ParamSpec("roc_pct_thr", "ROC threshold (%)", 0.05, 0.0, 2.0, 0.01),
            ParamSpec("cooldown_s", "Cooldown (s)", 60.0, 5.0, 600.0, 5.0),
        )

    def observe(self, symbol: str, price: float, at: datetime) -> Signal:
        at = at.astimezone(timezone.utc)
        st = self._push(symbol, price, at)
        cooled = self._hit_cooldown(st, at)
        if cooled is not None:
            return cooled
        if len(st.ticks) < self.MIN_SAMPLES:
            return _none(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                reason="warming up",
                at=at,
            )
        first_price = st.ticks[0][1]
        if first_price == 0.0:
            return _none(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                reason="flat",
                at=at,
            )
        roc_pct = (price - first_price) / first_price * 100.0
        reason = f"2m ROC {roc_pct:+.2f}%"
        intensity = abs(roc_pct) / max(self._roc_pct_thr, 1e-9)
        if roc_pct > self._roc_pct_thr:
            sig = _make(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                action="BUY",
                intensity=intensity,
                reason=reason,
                at=at,
            )
            return self._fired(st, at, sig)
        if roc_pct < -self._roc_pct_thr:
            sig = _make(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                action="SELL",
                intensity=intensity,
                reason=reason,
                at=at,
            )
            return self._fired(st, at, sig)
        return _none(
            symbol=symbol,
            strategy=self.name,
            kind=self.kind,
            reason=reason,
            at=at,
            intensity=intensity,
        )


class _RsiState:
    __slots__ = ("ticks", "avg_gain", "avg_loss", "last_fire", "last_price")

    def __init__(self) -> None:
        self.ticks: deque[float] = deque(maxlen=64)
        self.avg_gain: float | None = None
        self.avg_loss: float | None = None
        self.last_fire: tuple[datetime, Signal] | None = None
        self.last_price: float | None = None


class RsiRecoil:
    name = "RSI Recoil"
    kind: SignalKind = "recoil"

    def __init__(self) -> None:
        self._state: dict[str, _RsiState] = {}
        self._period = 14
        self._rsi_high = 75.0
        self._rsi_low = 25.0
        self._cooldown_seconds = 90.0

    def reset(self, symbol: str | None = None) -> None:
        if symbol is None:
            self._state.clear()
        else:
            self._state.pop(symbol, None)

    def params(self) -> dict[str, float]:
        return {
            "period": float(self._period),
            "rsi_high": self._rsi_high,
            "rsi_low": self._rsi_low,
            "cooldown_s": self._cooldown_seconds,
        }

    def set_param(self, key: str, value: float) -> None:
        if key == "period":
            new_period = max(2, int(value))
            if new_period != self._period:
                self._period = new_period
                self._state.clear()
        elif key == "rsi_high":
            self._rsi_high = min(100.0, max(50.0, value))
        elif key == "rsi_low":
            self._rsi_low = min(50.0, max(0.0, value))
        elif key == "cooldown_s":
            self._cooldown_seconds = max(5.0, value)

    def param_specs(self) -> tuple[ParamSpec, ...]:
        return (
            ParamSpec("period", "Period", 14.0, 2.0, 60.0, 1.0),
            ParamSpec("rsi_high", "RSI overbought", 75.0, 50.0, 100.0, 1.0),
            ParamSpec("rsi_low", "RSI oversold", 25.0, 0.0, 50.0, 1.0),
            ParamSpec("cooldown_s", "Cooldown (s)", 90.0, 5.0, 600.0, 5.0),
        )

    def observe(self, symbol: str, price: float, at: datetime) -> Signal:
        at = at.astimezone(timezone.utc)
        st = self._state.setdefault(symbol, _RsiState())
        if st.last_fire is not None and at - st.last_fire[0] < timedelta(
            seconds=self._cooldown_seconds
        ):
            return st.last_fire[1]
        prev = st.last_price
        st.last_price = price
        if prev is None:
            return _none(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                reason=f"warming up 0/{self._period}",
                at=at,
            )
        change = price - prev
        gain = change if change > 0 else 0.0
        loss = -change if change < 0 else 0.0
        st.ticks.append(change)
        if len(st.ticks) < self._period:
            return _none(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                reason=f"warming up {len(st.ticks)}/{self._period}",
                at=at,
            )
        if st.avg_gain is None or st.avg_loss is None:
            recent = list(st.ticks)[-self._period :]
            gains = [c for c in recent if c > 0]
            losses = [-c for c in recent if c < 0]
            st.avg_gain = sum(gains) / self._period
            st.avg_loss = sum(losses) / self._period
        else:
            n = self._period
            st.avg_gain = (st.avg_gain * (n - 1) + gain) / n
            st.avg_loss = (st.avg_loss * (n - 1) + loss) / n
        if st.avg_loss == 0.0:
            rsi = 100.0 if st.avg_gain > 0 else 50.0
        else:
            rs = st.avg_gain / st.avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
        reason = f"RSI {rsi:.0f}"
        intensity = abs(rsi - 50.0) / 50.0 * 2.0
        if rsi >= self._rsi_high:
            sig = _make(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                action="SELL",
                intensity=intensity,
                reason=reason,
                at=at,
            )
            st.last_fire = (at, sig)
            return sig
        if rsi <= self._rsi_low:
            sig = _make(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                action="BUY",
                intensity=intensity,
                reason=reason,
                at=at,
            )
            st.last_fire = (at, sig)
            return sig
        return _none(
            symbol=symbol,
            strategy=self.name,
            kind=self.kind,
            reason=reason,
            at=at,
            intensity=intensity,
        )


class _MacdState:
    __slots__ = (
        "ema_fast",
        "ema_slow",
        "signal",
        "prev_hist",
        "last_fire",
        "ticks",
    )

    def __init__(self) -> None:
        self.ema_fast: float | None = None
        self.ema_slow: float | None = None
        self.signal: float | None = None
        self.prev_hist: float | None = None
        self.last_fire: tuple[datetime, Signal] | None = None
        self.ticks: deque[tuple[datetime, float]] = deque()


class _MacdCore:
    """Shared MACD compute used by both MacdMomentum and ZScoreRecoil."""

    def __init__(self, fast: int, slow: int, signal: int) -> None:
        self.fast = fast
        self.slow = slow
        self.signal_period = signal

    def step(self, st: _MacdState, price: float) -> tuple[float, float]:
        a_fast = 2.0 / (self.fast + 1)
        a_slow = 2.0 / (self.slow + 1)
        a_sig = 2.0 / (self.signal_period + 1)
        if st.ema_fast is None:
            st.ema_fast = price
            st.ema_slow = price
        else:
            st.ema_fast = a_fast * price + (1 - a_fast) * st.ema_fast
            st.ema_slow = a_slow * price + (1 - a_slow) * st.ema_slow
        macd = st.ema_fast - st.ema_slow
        if st.signal is None:
            st.signal = macd
        else:
            st.signal = a_sig * macd + (1 - a_sig) * st.signal
        hist = macd - st.signal
        return macd, hist


class MacdMomentum:
    name = "MACD Momentum"
    kind: SignalKind = "momentum"
    MIN_SAMPLES = 20

    def __init__(self) -> None:
        self._state: dict[str, _MacdState] = {}
        self._fast = 12
        self._slow = 60
        self._signal = 20
        self._eps_pct = 0.02
        self._cooldown_seconds = 45.0

    def reset(self, symbol: str | None = None) -> None:
        if symbol is None:
            self._state.clear()
        else:
            self._state.pop(symbol, None)

    def params(self) -> dict[str, float]:
        return {
            "fast": float(self._fast),
            "slow": float(self._slow),
            "signal": float(self._signal),
            "eps_pct": self._eps_pct,
            "cooldown_s": self._cooldown_seconds,
        }

    def set_param(self, key: str, value: float) -> None:
        if key == "fast":
            self._fast = max(2, int(value))
            self._state.clear()
        elif key == "slow":
            self._slow = max(self._fast + 1, int(value))
            self._state.clear()
        elif key == "signal":
            self._signal = max(2, int(value))
            self._state.clear()
        elif key == "eps_pct":
            self._eps_pct = max(0.0, value)
        elif key == "cooldown_s":
            self._cooldown_seconds = max(5.0, value)

    def param_specs(self) -> tuple[ParamSpec, ...]:
        return (
            ParamSpec("fast", "Fast EMA", 12.0, 2.0, 60.0, 1.0),
            ParamSpec("slow", "Slow EMA", 60.0, 5.0, 200.0, 1.0),
            ParamSpec("signal", "Signal EMA", 20.0, 2.0, 60.0, 1.0),
            ParamSpec("eps_pct", "Hist threshold (%)", 0.02, 0.0, 0.5, 0.01),
            ParamSpec("cooldown_s", "Cooldown (s)", 45.0, 5.0, 600.0, 5.0),
        )

    def observe(self, symbol: str, price: float, at: datetime) -> Signal:
        at = at.astimezone(timezone.utc)
        st = self._state.setdefault(symbol, _MacdState())
        if st.last_fire is not None and at - st.last_fire[0] < timedelta(
            seconds=self._cooldown_seconds
        ):
            return st.last_fire[1]
        st.ticks.append((at, price))
        cutoff = at - WINDOW_30M
        while st.ticks and st.ticks[0][0] < cutoff:
            st.ticks.popleft()
        core = _MacdCore(self._fast, self._slow, self._signal)
        _, hist = core.step(st, price)
        if len(st.ticks) < self.MIN_SAMPLES:
            st.prev_hist = hist
            return _none(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                reason=f"warming up {len(st.ticks)}/{self.MIN_SAMPLES}",
                at=at,
            )
        eps = self._eps_pct / 100.0 * price
        prev = st.prev_hist if st.prev_hist is not None else hist
        rising = hist > prev
        falling = hist < prev
        reason = f"hist {hist:+.3f}"
        intensity = min(abs(hist) / max(eps, 1e-9), 5.0)
        st.prev_hist = hist
        if hist > eps and rising:
            sig = _make(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                action="BUY",
                intensity=intensity,
                reason=reason,
                at=at,
            )
            st.last_fire = (at, sig)
            return sig
        if hist < -eps and falling:
            sig = _make(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                action="SELL",
                intensity=intensity,
                reason=reason,
                at=at,
            )
            st.last_fire = (at, sig)
            return sig
        return _none(
            symbol=symbol,
            strategy=self.name,
            kind=self.kind,
            reason=reason,
            at=at,
            intensity=intensity,
        )


class ZScoreRecoil(_WindowBase):
    name = "Z-Score Recoil"
    kind: SignalKind = "recoil"
    MIN_SAMPLES = 8

    def __init__(self) -> None:
        super().__init__()
        self._z_threshold = 2.0
        self._cooldown_seconds = 300.0
        self._macd = MacdMomentum()
        self._macd._cooldown_seconds = 0.0

    def reset(self, symbol: str | None = None) -> None:
        super().reset(symbol)
        self._macd.reset(symbol)

    def params(self) -> dict[str, float]:
        return {
            "z_threshold": self._z_threshold,
            "cooldown_s": self._cooldown_seconds,
        }

    def set_param(self, key: str, value: float) -> None:
        if key == "z_threshold":
            self._z_threshold = max(0.1, value)
        elif key == "cooldown_s":
            self._cooldown_seconds = max(5.0, value)

    def param_specs(self) -> tuple[ParamSpec, ...]:
        return (
            ParamSpec("z_threshold", "Z threshold", 2.0, 0.5, 4.0, 0.1),
            ParamSpec("cooldown_s", "Cooldown (s)", 300.0, 5.0, 1800.0, 15.0),
        )

    def observe(self, symbol: str, price: float, at: datetime) -> Signal:
        at = at.astimezone(timezone.utc)
        st = self._push(symbol, price, at)
        macd_state = self._macd._state.get(symbol)
        # observe() advances prev_hist to the current histogram, so the
        # previous value must be captured before the call.
        prev_hist = macd_state.prev_hist if macd_state is not None else None
        self._macd.observe(symbol, price, at)
        cooled = self._hit_cooldown(st, at)
        if cooled is not None:
            return cooled
        if len(st.ticks) < self.MIN_SAMPLES:
            return _none(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                reason="warming up",
                at=at,
            )
        prices = [p for _, p in st.ticks]
        mean, std = _stats(prices)
        if std == 0.0:
            return _none(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                reason="flat",
                at=at,
            )
        z = (price - mean) / std
        macd_state = self._macd._state.get(symbol)
        hist = macd_state.prev_hist if macd_state is not None else None
        reason = f"z {z:+.1f}"
        intensity = abs(z)
        if (
            z > self._z_threshold
            and prev_hist is not None
            and hist is not None
            and hist < prev_hist
        ):
            sig = _make(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                action="SELL",
                intensity=intensity,
                reason=reason,
                at=at,
            )
            return self._fired(st, at, sig)
        if (
            z < -self._z_threshold
            and prev_hist is not None
            and hist is not None
            and hist > prev_hist
        ):
            sig = _make(
                symbol=symbol,
                strategy=self.name,
                kind=self.kind,
                action="BUY",
                intensity=intensity,
                reason=reason,
                at=at,
            )
            return self._fired(st, at, sig)
        return _none(
            symbol=symbol,
            strategy=self.name,
            kind=self.kind,
            reason=reason,
            at=at,
            intensity=intensity,
        )


STRATEGY_REGISTRY: tuple[type[SignalStrategy], ...] = (
    SlopeMomentum,
    BollingerRecoil,
    RocMomentum,
    RsiRecoil,
    MacdMomentum,
    ZScoreRecoil,
)


STRATEGY_NAMES: tuple[str, ...] = tuple(cls.name for cls in STRATEGY_REGISTRY)

# Default visibility: only the recommended C pair on at startup.
DEFAULT_VISIBLE: tuple[str, ...] = ("MACD Momentum", "Z-Score Recoil")

# Default chart-marker pair (momentum + recoil that drives BUY/SELL dots).
DEFAULT_MARKER_MOMENTUM = "MACD Momentum"
DEFAULT_MARKER_RECOIL = "Z-Score Recoil"


def build_strategies() -> list[SignalStrategy]:
    return [cls() for cls in STRATEGY_REGISTRY]
