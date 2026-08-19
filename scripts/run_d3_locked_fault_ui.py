"""Run disposable real-runtime locked-worker failure browser scenarios."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn
import nana_sidecar.runtime_app as runtime_module
import nana_sidecar.storage.journey_commands as journey_module

from nana_sidecar.dev_journey_fixture import (
    frozen_resource_descriptor,
    local_fixture_actor,
    read_dev_journey_definition,
    workspace_bootstrap_spec,
)
from nana_sidecar.runtime_app import JourneyRuntimeConfig, create_runtime_app
from nana_sidecar.sse import LocalSession
from nana_sidecar.storage.workspace_lock import WorkspaceRuntime


E2E_TOKEN = "d3-fault-session-" + ("d" * 40)
_REAL_PREPARE = journey_module.JourneyCommandService.prepare_locked_action


def _worker_crash(*_args, **_kwargs):
    raise RuntimeError("explicit D3 release-matrix worker crash")


def _prepare_then_lose_owner_context(self, *args, **kwargs):
    _REAL_PREPARE(self, *args, **kwargs)
    raise RuntimeError("explicit D3 release-matrix owner-context loss")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=43128)
    parser.add_argument("--mode", choices=("worker_crash", "owner_context_loss"), required=True)
    parser.add_argument("--build-root", type=Path, default=ROOT / "nana_web" / "dist")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    if args.mode == "worker_crash":
        runtime_module.default_locked_unittest_runner = _worker_crash
    else:
        journey_module.JourneyCommandService.prepare_locked_action = _prepare_then_lose_owner_context

    definition = read_dev_journey_definition()
    with tempfile.TemporaryDirectory(prefix=f"nana-d3-{args.mode}-") as directory:
        app = create_runtime_app(
            workspace_runtime=WorkspaceRuntime(Path(directory) / "nana.db"),
            local_session=LocalSession(token=E2E_TOKEN, origin=f"http://127.0.0.1:{args.port}"),
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
