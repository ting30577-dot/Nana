"""Export the sidecar OpenAPI document used to generate TypeScript types."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nana_sidecar.app import create_app
from nana_sidecar.dev_journey_fixture import (
    frozen_resource_descriptor,
    local_fixture_actor,
    read_dev_journey_definition,
    workspace_bootstrap_spec,
)
from nana_sidecar.runtime_app import JourneyRuntimeConfig, create_runtime_app
from nana_sidecar.sse import LocalSession
from nana_sidecar.storage.workspace_lock import WorkspaceRuntime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "nana_web" / "openapi.json",
    )
    parser.add_argument(
        "--source",
        choices=("d0-fixture", "runtime"),
        default="runtime",
        help="D0 fixture is archival only; runtime is the web-client authority.",
    )
    args = parser.parse_args()
    if args.source == "d0-fixture":
        schema = create_app().openapi()
    else:
        fixture = read_dev_journey_definition()
        schema = create_runtime_app(
            workspace_runtime=WorkspaceRuntime(
                ROOT / "fixtures" / "schema-only-runtime.db"
            ),
            local_session=LocalSession(
                token="schema-only-" + ("a" * 40),
                origin="http://127.0.0.1:43123",
            ),
            journey_runtime=JourneyRuntimeConfig(
                bootstrap=workspace_bootstrap_spec(fixture),
                actor=local_fixture_actor(),
                resources=(frozen_resource_descriptor(fixture),),
            ),
        ).openapi()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            schema,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
