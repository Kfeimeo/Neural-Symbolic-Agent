"""Terminal progress for Explore–Compress runs: one line per phase, with ETA.

``Progress`` is driven by :class:`~faithful.lib.ec.ExploreCompress` through five
calls (``run_started``, ``round_started``, ``phase_started``, ``advance``,
``phase_finished``, ``round_finished``) and never affects results. On a terminal
the open phase is redrawn in place (``\\r``) and a ticker keeps the elapsed time
moving during long single calls such as compression; elsewhere only the finished
lines are written, so logs stay readable. ``NullProgress`` is the silent default.
"""
from __future__ import annotations
import sys
import threading
import time
from typing import Optional, TextIO


def _duration(seconds: float) -> str:
    seconds = max(0., seconds)
    if seconds < 60: return f"{seconds:.1f}s"
    m, s = divmod(int(seconds + .5), 60)
    if m < 60: return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


class NullProgress:
    """Does nothing; the default so library code can call progress unconditionally."""
    def run_started(self, rounds: int, tasks: int) -> None: pass
    def round_started(self, index: int, total: int) -> None: pass
    def phase_started(self, name: str, total: Optional[int] = None, unit: str = "") -> None: pass
    def advance(self, n: int = 1) -> None: pass
    def phase_finished(self, note: str = "") -> None: pass
    def round_finished(self, index: int, note: str = "") -> None: pass
    def close(self) -> None: pass


class Progress(NullProgress):
    """Progress on ``stream`` (stderr by default).

    ``enabled=None`` reports only when the stream is a terminal; ``True`` also
    writes the finished lines to a file or pipe (without in-place redraws).
    """
    def __init__(self, stream: Optional[TextIO] = None, enabled: Optional[bool] = None,
                 width: int = 24, min_interval: float = 0.1):
        self.stream = stream or sys.stderr
        isatty = bool(getattr(self.stream, "isatty", lambda: False)())
        self.enabled = isatty if enabled is None else enabled
        self.animate = self.enabled and isatty
        self.width, self.min_interval = width, min_interval
        self._lock = threading.RLock()
        self._rounds = self._round = 0; self._in_round = False
        self._round_seconds: list[float] = []
        self._t_run = self._t_round = self._t_phase = self._t_draw = 0.
        self._phase: Optional[str] = None; self._total: Optional[int] = None; self._done = 0; self._unit = ""
        self._line_len = 0
        self._ticker: Optional[threading.Thread] = None; self._stop = threading.Event()

    # -- events ---------------------------------------------------------------------------------
    def run_started(self, rounds, tasks):
        with self._lock:
            self._rounds, self._round_seconds, self._t_run = rounds, [], time.perf_counter()
            self._write(f"explore-compress: {rounds} round(s), {tasks} task(s)\n")

    def round_started(self, index, total):
        with self._lock:
            self._round, self._rounds, self._t_round, self._in_round = index, total, time.perf_counter(), True

    def phase_started(self, name, total=None, unit=""):
        with self._lock:
            self._end_open_phase()
            self._phase, self._total, self._done, self._unit = name, total, 0, unit
            self._t_phase = self._t_draw = time.perf_counter()
            self._render(force=True)
            if self.animate and self._ticker is None:
                self._stop.clear()
                self._ticker = threading.Thread(target=self._tick, name="faithful-progress", daemon=True); self._ticker.start()

    def advance(self, n=1):
        with self._lock:
            if self._phase is None: return
            self._done += n
            self._render()

    def phase_finished(self, note=""):
        with self._lock:
            if self._phase is None: return
            elapsed = time.perf_counter() - self._t_phase
            count = f"{self._done}/{self._total}" + (f" {self._unit}" if self._unit else "") if self._total is not None else ""
            self._clear()
            self._write(f"{self._prefix()}{self._phase:<12}{count:>16}  {_duration(elapsed):>8}" + (f"  {note}" if note else "") + "\n")
            self._phase = None

    def round_finished(self, index, note=""):
        with self._lock:
            self._end_open_phase(); self._in_round = False
            seconds = time.perf_counter() - self._t_round; self._round_seconds.append(seconds)
            remaining = self._rounds - index - 1
            mean = sum(self._round_seconds) / len(self._round_seconds)
            eta = f"  est. remaining {_duration(mean * remaining)}" if remaining > 0 else ""
            self._write(f"round {index + 1}/{self._rounds} done in {_duration(seconds)}" + (f": {note}" if note else "") + eta + "\n")

    def close(self):
        with self._lock:
            self._end_open_phase()
            self._stop.set()
            if self._t_run:
                self._write(f"total {_duration(time.perf_counter() - self._t_run)}\n"); self._t_run = 0.

    # -- rendering ------------------------------------------------------------------------------
    def _prefix(self) -> str:
        return f"[round {self._round + 1}/{self._rounds}] " if self._in_round else ""

    def _end_open_phase(self):
        if self._phase is not None: self.phase_finished()

    def _tick(self):
        while not self._stop.wait(0.5):
            with self._lock:
                if self._phase is not None: self._render(force=True)

    def _render(self, force=False):
        if not self.animate or self._phase is None: return
        now = time.perf_counter()
        if not force and now - self._t_draw < self.min_interval: return
        self._t_draw = now
        elapsed = now - self._t_phase
        if self._total:
            frac = min(1., self._done / self._total)
            bar = "█" * int(frac * self.width) + "░" * (self.width - int(frac * self.width))
            eta = f"  eta {_duration(elapsed / self._done * (self._total - self._done))}" if self._done else ""
            line = f"{self._prefix()}{self._phase:<12}|{bar}| {self._done}/{self._total}{' ' + self._unit if self._unit else ''}  {_duration(elapsed)}{eta}"
        else:
            spin = "|/-\\"[int(elapsed * 2) % 4]
            line = f"{self._prefix()}{self._phase:<12} {spin}  {_duration(elapsed)}"
        pad = " " * max(0, self._line_len - len(line))
        self.stream.write("\r" + line + pad); self.stream.flush()
        self._line_len = len(line)

    def _clear(self):
        if self.animate and self._line_len:
            self.stream.write("\r" + " " * self._line_len + "\r"); self._line_len = 0

    def _write(self, text: str):
        if not self.enabled: return
        self._clear()
        self.stream.write(text); self.stream.flush()
