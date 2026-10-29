"""Motion timings copied from Coucou windows/src/core/anim.ts and mochi/engine.ts.

The blue bot stays Kai's. These are only the springs, the squash, the dizzy roll
and the greet bob from that code.
"""

from __future__ import annotations

import math
import time


def ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_in_out(t: float) -> float:
    if t < 0.5:
        return 4 * t * t * t
    return 1 - ((-2 * t + 2) ** 3) / 2


def ease_back(t: float) -> float:
    c1 = 1.7
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def close_curve(x: float) -> float:
    """cubic-bezier(.45, 0, .2, 1), the 340 ms close from anim.ts."""
    x1, y1, x2, y2 = 0.45, 0.0, 0.2, 1.0

    def cx(t: float) -> float:
        return ((1 - t) ** 2 * 3 * t * x1) + (3 * (1 - t) * t * t * x2) + t ** 3

    def cy(t: float) -> float:
        return ((1 - t) ** 2 * 3 * t * y1) + (3 * (1 - t) * t * t * y2) + t ** 3

    lo, hi, t = 0.0, 1.0, x
    for _ in range(12):
        if cx(t) < x:
            lo = t
        else:
            hi = t
        t = (lo + hi) / 2
    return cy(t)


class Spring:
    """SwiftUI-style spring. ω₀ = 2π / response, ζ = dampingFraction."""

    def __init__(self, value: float, response: float = 0.5, damping: float = 0.72) -> None:
        self.value = value
        self.target = value
        self.velocity = 0.0
        self.omega = (2 * math.pi) / response
        self.zeta = damping

    def configure(self, response: float, damping: float) -> None:
        self.omega = (2 * math.pi) / response
        self.zeta = damping

    def set(self, value: float) -> None:
        self.value = value
        self.target = value
        self.velocity = 0.0

    @property
    def settled(self) -> bool:
        return abs(self.target - self.value) < 0.01 and abs(self.velocity) < 0.05

    def step(self, dt: float) -> None:
        steps = max(1, math.ceil(dt / (1 / 240)))
        h = dt / steps
        for _ in range(steps):
            acc = self.omega * self.omega * (self.target - self.value) - 2 * self.zeta * self.omega * self.velocity
            self.velocity += acc * h
            self.value += self.velocity * h


class Tracked:
    """Open grows on a spring. Close shrinks on the 340 ms curve."""

    def __init__(self, value: float) -> None:
        self.spring = Spring(value)
        self._from = 0.0
        self._to = 0.0
        self._start = 0.0
        self._dur = 0.0
        self.mode = "idle"

    @property
    def value(self) -> float:
        return self.spring.value

    @property
    def animating(self) -> bool:
        return self.mode != "idle"

    def spring_to(self, value: float, response: float = 0.5, damping: float = 0.72) -> None:
        if self.mode == "spring" and abs(self.spring.target - value) < 0.001:
            return
        self.spring.configure(response, damping)
        self.spring.target = value
        self.mode = "spring"

    def curve_towards(self, value: float, duration_ms: float = 340) -> None:
        if self.mode == "curve" and abs(self._to - value) < 0.001:
            return
        self._from = self.spring.value
        self._to = value
        self._start = time.monotonic()
        self._dur = duration_ms / 1000.0
        self.spring.target = value
        self.spring.velocity = 0.0
        self.mode = "curve"

    def step(self, dt: float) -> None:
        if self.mode == "spring":
            self.spring.step(dt)
            if self.spring.settled:
                self.spring.value = self.spring.target
                self.spring.velocity = 0.0
                self.mode = "idle"
        elif self.mode == "curve":
            p = _clamp((time.monotonic() - self._start) / max(0.001, self._dur), 0, 1)
            self.spring.value = _lerp(self._from, self._to, close_curve(p))
            if p >= 1:
                self.spring.velocity = 0.0
                self.mode = "idle"


class BotMotion:
    """squash / dizzy / greet from mochi/engine.ts, without drawing that bot."""

    def __init__(self) -> None:
        self.sx = 1.0
        self.sy = 1.0
        self.oy = 0.0
        self.roll = 0.0
        self.open = 1.0
        self._tweens: dict[str, dict] = {}

    @property
    def busy(self) -> bool:
        return bool(self._tweens)

    def anim(self, prop: str, keys: list[tuple[float, float, object]]) -> None:
        self._tweens[prop] = {
            "keys": keys,
            "index": 0,
            "from": getattr(self, prop),
            "start": time.monotonic(),
        }

    def squash(self) -> None:
        self.anim("sy", [(0.78, 70, ease_out), (1.1, 130, ease_out), (1, 170, ease_in_out)])
        self.anim("sx", [(1.16, 70, ease_out), (0.95, 130, ease_out), (1, 170, ease_in_out)])

    def dizzy(self) -> None:
        self.roll = 0.0
        self.anim("roll", [(math.pi * 2 * 2, 1300, ease_in_out)])

    def greet(self) -> None:
        self.anim("oy", [(-0.06, 220, ease_out), (0.0, 220, ease_back)])
        self.anim("sy", [(0.95, 100, ease_out), (1.0, 260, ease_back)])
        self.anim("sx", [(1.04, 100, ease_out), (1.0, 260, ease_back)])

    def update(self, _dt: float) -> None:
        now = time.monotonic()
        done = []
        for prop, tw in self._tweens.items():
            key = tw["keys"][tw["index"]]
            p = _clamp((now - tw["start"]) / (key[1] / 1000.0), 0, 1)
            setattr(self, prop, tw["from"] + (key[0] - tw["from"]) * key[2](p))
            if p >= 1:
                tw["from"] = key[0]
                tw["index"] += 1
                tw["start"] = now
                if tw["index"] >= len(tw["keys"]):
                    done.append(prop)
        for prop in done:
            self._tweens.pop(prop, None)
