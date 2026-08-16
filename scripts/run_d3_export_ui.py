"""Run the explicit disposable D3 Approval/export browser harness."""

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
import nana_sidecar.storage.journey_commands as journey_commands_module

from nana_sidecar.dev_journey_fixture import (
    frozen_resource_descriptor,
    local_fixture_actor,
    read_dev_journey_definition,
    workspace_bootstrap_spec,
)
from nana_sidecar.export_selection import ExportSelectionRegistry
from nana_sidecar.runtime_app import JourneyRuntimeConfig, create_runtime_app
from nana_sidecar.sse import LocalSession
from nana_sidecar.storage.draft_export import DraftExportService as RealDraftExportService
from nana_sidecar.storage.workspace_lock import WorkspaceRuntime


E2E_TOKEN = "d3-export-session-" + ("c" * 40)


class _FenceCrashDraftExportService(RealDraftExportService):
    """Inject uncertainty only after the real durable first-write fence."""

    def __init__(self, *args, **kwargs):
        kwargs["checkpoint"] = self._crash_after_fence
        super().__init__(*args, **kwargs)

    @staticmethod
    def _crash_after_fence(name: str) -> None:
        if name == "first_write_fence_committed":
            raise RuntimeError("explicit E2E crash after durable first-write fence")


class _ExpiredDecisionDraftExportService(RealDraftExportService):
    """Advance only the decision clock after a real Approval was prepared."""

    def decide(self, request):
        self._now = lambda: "2099-01-01T00:00:00Z"
        return super().decide(request)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=43125)
    parser.add_argument("--mode", choices=("success", "uncertain", "expired"), default="success")
    parser.add_argument("--build-root", type=Path, default=ROOT / "nana_web" / "dist")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")

    if args.mode == "uncertain":
        runtime_module.DraftExportService = _FenceCrashDraftExportService
    if args.mode == "expired":
        journey_commands_module.DraftExportService = _ExpiredDecisionDraftExportService

    definition = read_dev_journey_definition()
    actor = local_fixture_actor()
    with tempfile.TemporaryDirectory(prefix=f"nana-d3-export-{args.mode}-") as directory:
        root = Path(directory)
        workspace = root / "workspace"
        target = root / "dedicated-export"
        workspace.mkdir()
        target.mkdir()
        session = LocalSession(
            token=E2E_TOKEN,
            origin=f"http://127.0.0.1:{args.port}",
        )
        selections = ExportSelectionRegistry(
            session=session,
            workspace_root=workspace,
            actor_id=str(actor.id),
            allow_test_harness=True,
        )
        selections.register_test_harness_target(str(target))
        app = create_runtime_app(
            workspace_runtime=WorkspaceRuntime(workspace / "nana.db"),
            local_session=session,
            web_build_root=args.build_root,
            journey_runtime=JourneyRuntimeConfig(
                bootstrap=workspace_bootstrap_spec(definition),
                actor=actor,
                resources=(frozen_resource_descriptor(definition),),
                export_selections=selections,
            ),
        )
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
