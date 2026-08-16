"""Launch the authenticated D3 journey with a real interactive export choice."""

from __future__ import annotations

import argparse
import json
import secrets
import socket
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Callable
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn

from nana_sidecar.dev_journey_fixture import (
    frozen_resource_descriptor,
    local_fixture_actor,
    read_dev_journey_definition,
    workspace_bootstrap_spec,
)
from nana_sidecar.export_selection import ExportSelectionRegistry
from nana_sidecar.runtime_app import JourneyRuntimeConfig, create_runtime_app
from nana_sidecar.sse import LocalSession
from nana_sidecar.storage.workspace_lock import WorkspaceRuntime


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Nana D3 with an interactive fixed-local draft target.",
    )
    parser.add_argument("database", type=Path)
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="loopback port; 0 (the default) asks the OS for an unused port",
    )
    parser.add_argument(
        "--build-root",
        type=Path,
        default=ROOT / "nana_web" / "dist",
    )
    return parser


def create_interactive_runtime(
    *,
    database: Path,
    port: int,
    build_root: Path,
    input_fn: Callable[[str], str] = input,
    bootstrap_secret: str | None = None,
):
    """Prompt over stdin; no export-target command-line argument exists."""

    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    database.parent.mkdir(parents=True, exist_ok=True)
    if not database.parent.is_dir():
        raise ValueError("the Workspace database parent is not a directory")
    token = "d3-local-" + secrets.token_urlsafe(32)
    origin = f"http://127.0.0.1:{port}"
    session = LocalSession(token=token, origin=origin)
    actor = local_fixture_actor()
    selections = ExportSelectionRegistry(
        session=session,
        workspace_root=database.parent,
        actor_id=str(actor.id),
    )
    raw_target = input_fn(
        "Select an existing dedicated empty fixed-local export folder: "
    )
    summary = selections.register_interactive_target(raw_target)
    definition = read_dev_journey_definition()
    app = create_runtime_app(
        workspace_runtime=WorkspaceRuntime(database),
        local_session=session,
        web_build_root=build_root,
        journey_runtime=JourneyRuntimeConfig(
            bootstrap=workspace_bootstrap_spec(definition),
            actor=actor,
            resources=(frozen_resource_descriptor(definition),),
            export_selections=selections,
        ),
        bootstrap_secret=bootstrap_secret,
    )
    return app, session, summary


def _listener(requested_port: int) -> tuple[socket.socket, int]:
    if not 0 <= requested_port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        listener.bind(("127.0.0.1", requested_port))
        listener.listen(128)
        return listener, int(listener.getsockname()[1])
    except Exception:
        listener.close()
        raise


def _open_browser_when_ready(
    origin: str,
    bootstrap_secret: str,
    stop_event: threading.Event | None = None,
    *,
    retry_interval: float = 0.05,
) -> bool:
    """Open after health is reachable, or report why startup stopped waiting."""

    stop_event = stop_event or threading.Event()
    health = origin + "/healthz"
    last_error: OSError | None = None
    while not stop_event.is_set():
        try:
            with urlopen(health, timeout=0.25) as response:
                if response.status == 200:
                    opened = webbrowser.open(
                        origin + "/#bootstrap=" + bootstrap_secret
                    )
                    if not opened:
                        print(
                            "Nana runtime is ready, but the default browser could "
                            f"not be opened automatically; open {origin} manually.",
                            file=sys.stderr,
                        )
                    return bool(opened)
        except OSError as exc:
            last_error = exc
        stop_event.wait(retry_interval)

    detail = f" Last health error: {last_error!r}." if last_error else ""
    print(
        "Nana stopped before the browser bootstrap could observe a ready runtime."
        + detail,
        file=sys.stderr,
    )
    return False


def main() -> int:
    args = _parser().parse_args()
    listener, port = _listener(args.port)
    bootstrap_secret = secrets.token_urlsafe(32)
    app, session, summary = create_interactive_runtime(
        database=args.database,
        port=port,
        build_root=args.build_root,
        bootstrap_secret=bootstrap_secret,
    )
    print(
        json.dumps(
            {
                "origin": session.origin,
                "session": "browser bootstrap pending; no credential is printed",
                "export_selection": {
                    "selection_id": summary.selection_id,
                    "label": summary.label,
                    "expires_at": summary.expires_at,
                    "provenance": summary.provenance,
                },
            },
            sort_keys=True,
        )
    )
    opener_stop = threading.Event()
    opener = threading.Thread(
        target=_open_browser_when_ready,
        args=(session.origin, bootstrap_secret, opener_stop),
        name="nana-browser-bootstrap",
        daemon=True,
    )
    opener.start()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    try:
        uvicorn.Server(config).run(sockets=[listener])
    finally:
        opener_stop.set()
        opener.join(timeout=1)
        listener.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
