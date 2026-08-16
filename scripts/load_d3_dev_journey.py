"""Load the frozen D3 dev journey through the canonical typed writer."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nana_sidecar.dev_journey_fixture import (
    DEFAULT_FIXTURE,
    frozen_resource_descriptor,
    load_dev_journey,
    local_fixture_actor,
    read_dev_journey_definition,
    workspace_bootstrap_spec,
)
from nana_sidecar.storage.journey_commands import (
    JourneyCommandService,
    WorkspaceBootstrapService,
)
from nana_sidecar.storage.workspace_lock import WorkspaceRuntime


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    args = parser.parse_args()

    definition = read_dev_journey_definition(args.fixture)
    runtime = WorkspaceRuntime(args.database)
    try:
        connection = runtime.start()
        WorkspaceBootstrapService(connection).ensure(
            workspace_bootstrap_spec(definition)
        )
        service = JourneyCommandService(
            connection,
            actor=local_fixture_actor(),
            resources=(frozen_resource_descriptor(definition),),
            now=_now,
        )
        loaded = load_dev_journey(service, definition)
        print(json.dumps({
            "ids": {name: str(value) for name, value in sorted(loaded.ids.items())},
            "statuses": [result.status.value for result in loaded.command_results],
        }, ensure_ascii=False, sort_keys=True))
    finally:
        if runtime.state == "ready":
            runtime.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
