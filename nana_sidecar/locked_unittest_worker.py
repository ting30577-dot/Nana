"""Restricted worker for the trusted ``python.unittest.locked`` capability.

This is a deterministic guard for Nana's frozen test, not an OS sandbox for
hostile Python or native extensions.  It narrows Python-level file, network,
and child-process effects before importing the selected test module.
"""

from __future__ import annotations

import os
import json
import socket
import subprocess
import sys
import sysconfig
import time
import unittest
from pathlib import Path

from nana_sidecar.contracts.builtin_capabilities import (
    PYTHON_UNITTEST_LOCKED_TEST_IDS,
)


_WRITE_FLAGS = (
    os.O_APPEND
    | os.O_CREAT
    | os.O_EXCL
    | os.O_TRUNC
    | os.O_WRONLY
    | os.O_RDWR
)
_MUTATING_EVENTS = frozenset(
    {
        "os.chdir",
        "os.chmod",
        "os.chown",
        "os.link",
        "os.mkdir",
        "os.remove",
        "os.rename",
        "os.replace",
        "os.rmdir",
        "os.symlink",
        "os.truncate",
        "os.unlink",
        "os.utime",
    }
)
_EFFECT_REPORT_PREFIX = "NANA_LOCKED_EFFECTS:"


def _is_within(path: Path, roots: tuple[Path, ...]) -> bool:
    try:
        candidate = path.resolve(strict=False)
    except OSError:
        return False
    return any(candidate == root or root in candidate.parents for root in roots)


class _RuntimeGuard:
    def __init__(self, workspace_root: Path) -> None:
        workspace_root = workspace_root.resolve(strict=True)
        self.project_read_roots = (
            (
                "project:source",
                tuple(
                    (workspace_root / name).resolve(strict=True)
                    for name in ("algorithms", "nana_core", "nana_sidecar")
                ),
            ),
            (
                "project:tests",
                ((workspace_root / "tests").resolve(strict=True),),
            ),
        )
        self.observed_reads: set[str] = set()
        runtime_roots: list[Path] = []
        runtime_paths = sysconfig.get_paths()
        for raw in {
            runtime_paths[key]
            for key in ("stdlib", "platstdlib", "purelib", "platlib")
            if key in runtime_paths
        }:
            try:
                path = Path(raw).resolve(strict=False)
            except (OSError, TypeError):
                continue
            if path.exists():
                runtime_roots.append(path)
        self.runtime_read_roots = tuple(runtime_roots)

    def __call__(self, event: str, args: tuple[object, ...]) -> None:
        if event == "open":
            self._check_open(args)
            return
        if event.startswith("socket."):
            raise PermissionError("locked runtime denied network access")
        if event in _MUTATING_EVENTS:
            raise PermissionError("locked runtime denied filesystem mutation")
        if event == "subprocess.Popen" or event == "os.system" or event.startswith(
            ("os.exec", "os.spawn")
        ):
            raise PermissionError("locked runtime denied child process creation")

    def _check_open(self, args: tuple[object, ...]) -> None:
        if not args:
            raise PermissionError("locked runtime denied ambiguous file access")
        target = args[0]
        if isinstance(target, int):
            return
        try:
            path = Path(os.fsdecode(target))
        except (TypeError, ValueError):
            raise PermissionError("locked runtime denied ambiguous file access") from None
        mode = args[1] if len(args) > 1 else "r"
        flags = args[2] if len(args) > 2 else 0
        mutating = (
            isinstance(mode, str) and any(marker in mode for marker in "wax+")
        ) or (isinstance(flags, int) and bool(flags & _WRITE_FLAGS))
        if mutating:
            raise PermissionError("locked runtime denied file write")
        for logical_root, physical_roots in self.project_read_roots:
            if _is_within(path, physical_roots):
                self.observed_reads.add(logical_root)
                return
        if _is_within(path, self.runtime_read_roots):
            return
        raise PermissionError("locked runtime denied file read outside declared roots")

    def report(self) -> dict[str, object]:
        return {
            "reads": sorted(self.observed_reads),
            "writes": [],
            "network": [],
            "processes": [],
        }


def _run_test(test_id: str) -> int:
    if test_id not in PYTHON_UNITTEST_LOCKED_TEST_IDS:
        raise SystemExit("locked runtime rejected unknown test id")
    sys.dont_write_bytecode = True
    guard = _RuntimeGuard(Path.cwd())
    sys.addaudithook(guard)
    try:
        suite = unittest.defaultTestLoader.loadTestsFromName(test_id)
        result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
        return 0 if result.wasSuccessful() else 1
    finally:
        sys.stderr.write(
            _EFFECT_REPORT_PREFIX
            + json.dumps(guard.report(), separators=(",", ":"), sort_keys=True)
            + "\n"
        )
        sys.stderr.flush()


def _run_probe(name: str) -> int:
    sys.dont_write_bytecode = True
    sys.addaudithook(_RuntimeGuard(Path.cwd()))
    try:
        if name == "network":
            socket.socket().connect(("127.0.0.1", 9))
        elif name == "outside-read":
            Path.cwd().joinpath("README.md").read_bytes()
        elif name == "child-process":
            os.system("echo blocked")
        elif name == "write":
            Path.cwd().joinpath("locked-runtime-write-probe.tmp").write_bytes(b"blocked")
        elif name == "sleep":
            time.sleep(5)
            return 2
        elif name == "output":
            sys.stdout.buffer.write(b"x" * 8192)
            sys.stdout.buffer.flush()
            sys.stderr.buffer.write(b"y" * 8192)
            sys.stderr.buffer.flush()
            return 2
        elif name == "env-canary":
            return 0 if os.environ.get("NANA_D2_SYNTHETIC_CANARY") is None else 2
        elif name == "bytecode-disabled":
            return 0 if sys.dont_write_bytecode else 2
        else:
            raise SystemExit("unknown locked runtime probe")
    except PermissionError:
        return 0
    return 2


def _run_job_probe(marker_path: str, sentinel_path: str) -> int:
    """Spawn a descendant immediately for the Job Object adversarial fixture.

    This private test-only path intentionally runs before the audit guard.  It
    is not reachable through the frozen capability args schema.
    """

    child = subprocess.Popen(
        [
            sys.executable,
            "-B",
            "-c",
            (
                "import pathlib,sys,time;"
                "time.sleep(10);"
                "pathlib.Path(sys.argv[1]).write_text('escaped',encoding='utf-8')"
            ),
            sentinel_path,
        ],
        env={},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
    )
    marker = Path(marker_path)
    pending_marker = marker.with_suffix(marker.suffix + ".partial")
    pending_marker.write_text(str(child.pid), encoding="ascii")
    os.replace(pending_marker, marker)
    time.sleep(30)
    return 2


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    if len(values) == 4 and values[:2] == ["--job-probe", "spawn-child"]:
        return _run_job_probe(values[2], values[3])
    if len(values) == 2 and values[0] == "--probe":
        return _run_probe(values[1])
    if len(values) != 1:
        raise SystemExit("usage: locked_unittest_worker TEST_ID")
    return _run_test(values[0])


if __name__ == "__main__":
    raise SystemExit(main())
