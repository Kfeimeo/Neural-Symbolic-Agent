"""Haskell kernel: build targets, executable discovery and process management.

The symbolic core (type inference, enumeration, scoring, sampling, compression)
is a Haskell program speaking protocol v1 (newline-delimited JSON). This module
owns three concerns that the frozen ``faithful.python.kernel`` hard-codes:

* **Build** — every executable is described by a :class:`KernelTarget`; the
  ``versionspace`` target is a strict superset of the others and is the default.
* **Discovery** — an explicit path, then ``FAITHFUL_KERNEL_<TARGET>``, then
  ``FAITHFUL_BUILD_DIR``, then the package ``build/`` directory. Missing
  executables are compiled on demand when ``ghc`` is available.
* **Process** — :class:`Kernel` is a thread-safe, restartable, optionally
  timed client; a dead process raises :class:`KernelProcessError` instead of
  returning garbage. There is no Python fallback for any symbolic operation.
* **Pool** — :class:`KernelPool` runs several independent kernel processes
  behind the same interface. One ``Kernel`` serializes every call behind its
  lock; a pool lets independent calls (``map``) proceed concurrently.
"""
from __future__ import annotations
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence, TypeVar

T = TypeVar("T"); R = TypeVar("R")

PACKAGE_ROOT = Path(__file__).resolve().parents[1]  # .../faithful
REPO_ROOT = PACKAGE_ROOT.parent

class KernelError(RuntimeError):
    """The kernel answered ``ok: false``; ``message`` is the Haskell error."""
    def __init__(self, message: str, operation: Optional[str] = None):
        super().__init__(message); self.message = message; self.operation = operation

class KernelProcessError(KernelError):
    """The kernel process is gone (crashed, killed, or timed out)."""

class KernelBuildError(KernelError):
    """ghc is unavailable or compilation failed."""

@dataclass(frozen=True)
class KernelTarget:
    """One Haskell executable. ``main`` is ``None`` for a plain ``Main`` module."""
    name: str
    source: str                          # entry module path relative to the faithful package
    includes: tuple[str, ...]            # -i directories relative to the faithful package
    main: Optional[str] = None           # -main-is value
    operations: tuple[str, ...] = ()     # operations added on top of the parent target
    parent: Optional[str] = None

CORE_OPERATIONS = ("unify", "infer", "beta", "evaluate", "evaluate_batch", "sample", "versions",
                   "compression_candidates", "compress", "score", "enumerate", "enumerate_budget",
                   "search_tasks", "frontier", "update")
BRIDGE_OPERATIONS = ("compression_objective", "compression_trial")
VERSIONSPACE_OPERATIONS = ("vs_compress", "vs_candidates", "vs_versions")

TARGETS: dict[str, KernelTarget] = {
    "core": KernelTarget("kernel", "haskell/Main.hs", ("haskell",), None, CORE_OPERATIONS),
    "bridge": KernelTarget("compression_bridge", "compression/Bridge.hs", ("haskell", "compression"),
                           "Bridge.main", BRIDGE_OPERATIONS, "core"),
    "versionspace": KernelTarget("versionspace_kernel", "versionspace/VSMain.hs",
                                 ("haskell", "compression", "versionspace"), "VSMain.main",
                                 VERSIONSPACE_OPERATIONS, "bridge"),
    # Example of a domain whose primitive semantics live in Haskell (see domains/DomainMain.hs).
    "official_domain": KernelTarget("official_domain", "domains/DomainMain.hs",
                                    ("haskell", "compression"), "DomainMain.main", (), "bridge"),
}
DEFAULT_TARGET = "versionspace"

def operations(target: str = DEFAULT_TARGET) -> frozenset[str]:
    """All protocol operations served by ``target`` (its own plus inherited)."""
    t = TARGETS[target]
    return frozenset(t.operations) | (operations(t.parent) if t.parent else frozenset())

def register_target(key: str, target: KernelTarget) -> None:
    """Register a user-built executable (for example a Haskell-side domain)."""
    TARGETS[key] = target

# ---- discovery ---------------------------------------------------------------

def find_ghc(ghc: Optional[str] = None) -> str:
    path = ghc or os.environ.get("FAITHFUL_GHC") or shutil.which("ghc")
    if not path:
        raise KernelBuildError("ghc not found; install GHC (see LINUX_RUN.md) or set FAITHFUL_GHC")
    return path

def build_dir() -> Path:
    return Path(os.environ.get("FAITHFUL_BUILD_DIR") or PACKAGE_ROOT / "build")

def _candidates(target: str) -> list[Path]:
    name = TARGETS[target].name
    env = os.environ.get(f"FAITHFUL_KERNEL_{target.upper()}")
    if env: return [Path(env)]
    folder = build_dir()
    # Frozen scripts always name the file ``.exe`` even on Linux; accept both.
    return [folder / f"{name}.exe", folder / name]

def executable_path(target: str = DEFAULT_TARGET) -> Optional[Path]:
    """Existing executable for ``target`` or ``None``."""
    for candidate in _candidates(target):
        if candidate.is_file(): return candidate
    return None

def build(target: str = DEFAULT_TARGET, *, ghc: Optional[str] = None, optimisation: str = "-O1",
          output: Optional[Path] = None, quiet: bool = False) -> Path:
    """Compile ``target`` with ghc into the build directory and return the executable."""
    t = TARGETS[target]
    folder = build_dir()
    exe = Path(output) if output else folder / (t.name + (".exe" if sys.platform == "win32" else ""))
    objects = folder / (target if target != "core" else "")  # frozen layout: core objects live in build/
    exe.parent.mkdir(parents=True, exist_ok=True); objects.mkdir(parents=True, exist_ok=True)
    command = [find_ghc(ghc), optimisation] + [f"-i{PACKAGE_ROOT / d}" for d in t.includes]
    command += ["-outputdir", str(objects)]
    if t.main: command += ["-main-is", t.main]
    command += [str(PACKAGE_ROOT / t.source), "-o", str(exe)]
    result = subprocess.run(command, cwd=REPO_ROOT, capture_output=quiet, text=True)
    if result.returncode:
        raise KernelBuildError(f"ghc failed for target {target!r}:\n{result.stderr or ''}")
    return exe

def ensure_executable(target: str = DEFAULT_TARGET, auto_build: Optional[bool] = None) -> Path:
    """Locate ``target``, compiling it when missing and ``auto_build`` allows."""
    found = executable_path(target)
    if found: return found
    if auto_build is None:
        auto_build = os.environ.get("FAITHFUL_AUTO_BUILD", "1") not in ("0", "false", "no")
    if not auto_build:
        raise KernelBuildError(f"No executable for kernel target {target!r} in {build_dir()}; run "
                               f"`python -m faithful.lib build {target}` or set FAITHFUL_KERNEL_{target.upper()}")
    return build(target)

# ---- process -----------------------------------------------------------------

@dataclass
class KernelOptions:
    target: str = DEFAULT_TARGET
    executable: Optional[os.PathLike | str] = None
    auto_build: Optional[bool] = None
    timeout: Optional[float] = None       # seconds per call; the process is killed on expiry
    restart: bool = True                  # relaunch after a crash/timeout on the next call
    trace: Optional[os.PathLike | str] = None  # JSONL request/response log (default: $FAITHFUL_TRACE)
    env: Optional[Mapping[str, str]] = None
    extra_args: Sequence[str] = field(default_factory=tuple)

class _Protocol:
    """Convenience wrappers shared by :class:`Kernel` and :class:`KernelPool`."""
    def infer(self, grammar, program, environment=()):
        return self.call("infer", grammar=grammar, program=program, environment=list(environment))["type"]
    def beta(self, program):
        return self.call("beta", program=program)["program"]
    def score(self, grammar, request, program, environment=()):
        return self.call("score", grammar=grammar, request=request, program=program, environment=list(environment))
    def frontier(self, grammar, frontier):
        return self.call("frontier", grammar=grammar, frontier=frontier)
    def sample(self, grammar, request, uniforms):
        return self.call("sample", grammar=grammar, request=request, uniforms=list(uniforms))
    def enumerate_budget(self, grammar, request, search_grammar=None, **budget):
        return self.call("enumerate_budget", grammar=grammar, search_grammar=search_grammar or grammar, request=request, **budget)
    def evaluate_batch(self, program, input_sets):
        return self.call("evaluate_batch", program=program, input_sets=list(input_sets))["values"]

class Kernel(_Protocol):
    """Persistent protocol v1 client.

    >>> with Kernel() as k:
    ...     k.call("beta", program={"application": [{"abstraction": {"index": 0}}, {"primitive": "zero"}]})
    {'program': {'primitive': 'zero'}}
    """
    protocol_version = 1

    def __init__(self, executable: Optional[os.PathLike | str] = None, *, target: str = DEFAULT_TARGET,
                 auto_build: Optional[bool] = None, timeout: Optional[float] = None, restart: bool = True,
                 trace: Optional[os.PathLike | str] = None, env: Optional[Mapping[str, str]] = None,
                 extra_args: Sequence[str] = (), options: Optional[KernelOptions] = None):
        if options is not None:
            executable, target, auto_build = options.executable, options.target, options.auto_build
            timeout, restart, trace, env, extra_args = options.timeout, options.restart, options.trace, options.env, options.extra_args
        self.target = target
        self.executable = Path(executable) if executable else ensure_executable(target, auto_build)
        if not self.executable.is_file():
            raise KernelBuildError(f"Kernel executable not found: {self.executable}")
        self.timeout, self.restart = timeout, restart
        self.trace = Path(trace) if trace else (Path(os.environ["FAITHFUL_TRACE"]) if os.environ.get("FAITHFUL_TRACE") else None)
        self.env, self.extra_args = dict(env) if env else None, list(extra_args)
        self._lock = threading.RLock()
        self.process: Optional[subprocess.Popen] = None
        self.calls = 0
        self.last_failure: Optional[str] = None
        self.start()

    # -- lifecycle
    def start(self) -> None:
        with self._lock:
            if self.alive: return
            self.process = subprocess.Popen([str(self.executable), *self.extra_args], stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1,
                                            env=self.env, cwd=REPO_ROOT)

    @property
    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    @property
    def pid(self) -> Optional[int]:
        return self.process.pid if self.process else None

    def close(self, timeout: float = 10.) -> None:
        with self._lock:
            p, self.process = self.process, None
            if p is None: return
            try:
                if p.stdin and not p.stdin.closed: p.stdin.close()
                p.wait(timeout=timeout)
            except Exception:
                p.kill(); p.wait()
            finally:
                if p.stdout: p.stdout.close()

    def kill(self) -> None:
        with self._lock:
            if self.process is not None and self.alive: self.process.kill()
            self.close()

    def __enter__(self): return self
    def __exit__(self, *exc): self.close()
    def __del__(self):
        try: self.close(timeout=1.)
        except Exception: pass

    # -- protocol
    def supports(self, operation: str) -> bool:
        return operation in operations(self.target)

    def call(self, operation: str, **payload: Any) -> Any:
        request = dict(version=self.protocol_version, operation=operation, **payload)
        line = json.dumps(request) + "\n"
        with self._lock:
            if not self.alive:
                if self.last_failure and not self.restart:
                    raise KernelProcessError(f"Kernel process is down ({self.last_failure}); restart disabled", operation)
                self.start()
            timed_out = threading.Event()
            timer = None
            if self.timeout:
                def expire(p=self.process):
                    timed_out.set(); p.kill()
                timer = threading.Timer(self.timeout, expire); timer.daemon = True; timer.start()
            try:
                try:
                    self.process.stdin.write(line); self.process.stdin.flush()
                    raw = self.process.stdout.readline()
                except (BrokenPipeError, OSError, ValueError):
                    raw = ""
            finally:
                if timer: timer.cancel()
            self.calls += 1
            if not raw:
                code = self.process.poll()
                self.close(timeout=1.)
                self.last_failure = f"timed out after {self.timeout}s" if timed_out.is_set() else f"exited with code {code}"
                raise KernelProcessError(f"Kernel process {self.last_failure} during {operation!r}", operation)
        response = json.loads(raw)
        if self.trace:
            with open(self.trace, "a", encoding="utf8") as f:
                f.write(json.dumps({"implementation": "haskell", "target": self.target, "request": request, "response": response}) + "\n")
        if not response.get("ok"):
            raise KernelError(response.get("error", "unknown kernel error"), operation)
        return response["result"]

    def map(self, fn: Callable[["Kernel", T], R], items: Iterable[T]) -> list[R]:
        """``[fn(self, x) for x in items]``; :class:`KernelPool` overrides this to run the calls concurrently."""
        return [fn(self, x) for x in items]

# ---- pool --------------------------------------------------------------------

class KernelPool(_Protocol):
    """``size`` independent kernel processes behind the :class:`Kernel` interface.

    A single ``Kernel`` serializes every request behind its lock, so loops of
    independent calls in the parent (rescoring frontiers, scoring recognition
    summaries, MDL accounting) run one process at a time. A pool keeps ``size``
    processes and a thread per process; ``map(fn, items)`` evaluates
    ``fn(pool, item)`` for each item on those threads, in input order, with the
    first exception propagated. Python releases the GIL while a thread waits on
    its kernel pipe, so the processes genuinely run concurrently. Every call made
    inside ``fn`` goes to the kernel the thread borrowed for that item; a nested
    ``map`` runs on the calling thread instead of waiting for the pool.

    Calls made outside ``map`` borrow any idle process. Results are the same as
    with one ``Kernel``: nothing is shared between processes and no call order
    changes a response. ``size=1`` is a plain ``Kernel`` with a thread pool of one.

    >>> with KernelPool(2) as pool:
    ...     pool.map(lambda k, p: k.beta(p), [{"primitive": "zero"}, {"primitive": "one"}])
    [{'primitive': 'zero'}, {'primitive': 'one'}]
    """
    protocol_version = Kernel.protocol_version

    def __init__(self, size: int = 2, executable: Optional[os.PathLike | str] = None, *, target: str = DEFAULT_TARGET,
                 auto_build: Optional[bool] = None, timeout: Optional[float] = None, restart: bool = True,
                 trace: Optional[os.PathLike | str] = None, env: Optional[Mapping[str, str]] = None,
                 extra_args: Sequence[str] = (), options: Optional[KernelOptions] = None):
        if type(size) is not int or size < 1:
            raise ValueError("KernelPool size must be a positive integer")
        if options is None:
            options = KernelOptions(target=target, executable=executable, auto_build=auto_build, timeout=timeout,
                                    restart=restart, trace=trace, env=env, extra_args=tuple(extra_args))
        if options.executable is None:  # build once, not once per process
            options = replace(options, executable=ensure_executable(options.target, options.auto_build))
        base_trace = Path(options.trace) if options.trace else (Path(os.environ["FAITHFUL_TRACE"]) if os.environ.get("FAITHFUL_TRACE") else None)
        self.size = size
        self.kernels: list[Kernel] = []
        try:
            for i in range(size):
                o = replace(options, trace=str(base_trace.with_name(f"{base_trace.stem}.kernel-{i}{base_trace.suffix}"))) if base_trace else options
                self.kernels.append(Kernel(options=o))
        except Exception:
            for k in self.kernels: k.close(timeout=1.)
            raise
        primary = self.kernels[0]
        self.target, self.executable, self.timeout, self.restart = primary.target, primary.executable, primary.timeout, primary.restart
        self.trace, self.env, self.extra_args = base_trace, primary.env, primary.extra_args
        self._idle: queue.LifoQueue[Kernel] = queue.LifoQueue()
        for k in self.kernels: self._idle.put(k)
        self._local = threading.local()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._lock = threading.Lock()

    # -- Kernel-shaped attributes (the first process stands for the pool)
    @property
    def process(self): return self.kernels[0].process if self.kernels else None
    @property
    def pid(self) -> Optional[int]: return self.kernels[0].pid if self.kernels else None
    @property
    def alive(self) -> bool: return any(k.alive for k in self.kernels)
    @property
    def pids(self) -> list[Optional[int]]: return [k.pid for k in self.kernels]
    @property
    def calls(self) -> int: return sum(k.calls for k in self.kernels)
    @property
    def last_failure(self) -> Optional[str]:
        return next((k.last_failure for k in self.kernels if k.last_failure), None)

    def supports(self, operation: str) -> bool:
        return operation in operations(self.target)

    # -- lifecycle
    def close(self, timeout: float = 10.) -> None:
        with self._lock:
            ex, self._executor = self._executor, None
        if ex is not None: ex.shutdown(wait=True)
        for k in self.kernels: k.close(timeout=timeout)
    def kill(self) -> None:
        with self._lock:
            ex, self._executor = self._executor, None
        if ex is not None: ex.shutdown(wait=False, cancel_futures=True)
        for k in self.kernels: k.kill()
    def __enter__(self): return self
    def __exit__(self, *exc): self.close()
    def __del__(self):
        try: self.close(timeout=1.)
        except Exception: pass

    # -- protocol
    def call(self, operation: str, **payload: Any) -> Any:
        held = getattr(self._local, "kernel", None)
        if held is not None:                    # inside map: stay on the borrowed process
            return held.call(operation, **payload)
        k = self._idle.get()
        try: return k.call(operation, **payload)
        finally: self._idle.put(k)

    def map(self, fn: Callable[["KernelPool", T], R], items: Iterable[T]) -> list[R]:
        """``[fn(self, x) for x in items]`` evaluated on up to ``size`` processes at once.

        Order is preserved and every item runs even when an earlier one fails;
        the first failure is re-raised once all have finished."""
        items = list(items)
        if len(items) <= 1 or self.size == 1 or getattr(self._local, "kernel", None) is not None:
            return [fn(self, x) for x in items]
        with self._lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=self.size, thread_name_prefix="faithful-kernel")
            ex = self._executor
        return list(ex.map(self._run, ((fn, x) for x in items)))

    def _run(self, job):
        fn, item = job
        k = self._idle.get(); self._local.kernel = k
        try: return fn(self, item)
        finally:
            self._local.kernel = None; self._idle.put(k)

def trace_path() -> Optional[Path]:
    value = os.environ.get("FAITHFUL_TRACE")
    return Path(value) if value else None
