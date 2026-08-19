"""Run the explicit D3 browser-mutation test harness composition."""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn
import nana_sidecar.runtime_app as runtime_module

from nana_sidecar.dev_journey_fixture import (
    frozen_resource_descriptor,
    local_fixture_actor,
    read_dev_journey_definition,
    workspace_bootstrap_spec,
)
from nana_sidecar.runtime_app import JourneyRuntimeConfig, create_runtime_app
from nana_sidecar.sse import LocalSession
from nana_sidecar.storage.workspace_lock import WorkspaceRuntime


E2E_TOKEN = "d3-mutation-session-" + ("b" * 40)


_real_locked_runner = runtime_module.default_locked_unittest_runner
_run_attempts = 0


def _delayed_locked_runner(*args, **kwargs):
    """Keep the real locked worker cancellable long enough for browser E2E."""

    time.sleep(1.5)
    return _real_locked_runner(*args, **kwargs)


def _pausable_locked_runner(test_id, workspace_root, timeout_seconds, max_output_bytes, signals):
    """Deterministic browser fixture with observable pause/resume and one failure."""
    if getattr(signals, "pause_requested", lambda: False) is None:
        raise RuntimeError("pause control unavailable")
    active = 0.0
    while active < 0.8:
        if signals():
            return runtime_module.LockedProcessResult(
                exit_code=None, stdout=b"", stderr=b"", wall_clock_ms=10,
                cancelled=True, actual_effects=runtime_module.EffectScope(),
            )
        time.sleep(0.01)
        if not signals.pause_requested():
            active += 0.01
    global _run_attempts
    _run_attempts += 1
    if _run_attempts == 1:
        return runtime_module.LockedProcessResult(
            exit_code=1, stdout=b"", stderr=b"expected first failure", wall_clock_ms=800,
            actual_effects=runtime_module.EffectScope(),
        )
    return _real_locked_runner(
        test_id, workspace_root, timeout_seconds, max_output_bytes, signals
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=43124)
    parser.add_argument("--first-run-fails", action="store_true")
    parser.add_argument(
        "--build-root",
        type=Path,
        default=ROOT / "nana_web" / "dist",
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    definition = read_dev_journey_definition()
    runtime_module.default_locked_unittest_runner = (
        _pausable_locked_runner if args.first_run_fails else _delayed_locked_runner
    )
    with tempfile.TemporaryDirectory(prefix="nana-d3-mutation-") as directory:
        app = create_runtime_app(
            workspace_runtime=WorkspaceRuntime(Path(directory) / "nana.db"),
            local_session=LocalSession(
                token=E2E_TOKEN,
                origin=f"http://127.0.0.1:{args.port}",
            ),
            web_build_root=args.build_root,
            journey_runtime=JourneyRuntimeConfig(
                bootstrap=workspace_bootstrap_spec(definition),
                actor=local_fixture_actor(),
                resources=(frozen_resource_descriptor(definition),),
            ),
        )
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
