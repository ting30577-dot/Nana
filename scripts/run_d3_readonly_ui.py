"""Run the authenticated D3-04 read-only browser test composition."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn

from nana_sidecar.runtime_app import create_runtime_app
from nana_sidecar.sse import LocalSession
from nana_sidecar.storage.workspace_lock import WorkspaceRuntime


E2E_TOKEN = "d3-e2e-session-" + ("a" * 40)
E2E_BOOTSTRAP_SECRET = "d3-e2e-bootstrap-" + ("b" * 32)


def _seed_readonly_fixture(workspace: WorkspaceRuntime) -> None:
    connection = workspace.connection
    if connection is None:
        raise RuntimeError("Workspace must be ready before fixture seeding")
    if connection.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0]:
        return
    now = "2026-08-08T00:00:00Z"
    connection.execute(
        "INSERT INTO workspaces(id, schema_version, data_root, policy_json, status, revision, created_at) "
        "VALUES (?, 7, ?, ?, 'active', 1, ?)",
        ("workspace-d3-readonly", "fixture-root-not-projected", json.dumps({}), now),
    )
    connection.execute(
        "INSERT INTO projects(id, workspace_id, title, status, data_class, revision, created_at) VALUES (?, ?, ?, 'active', 'public', 1, ?)",
        ("project-readonly", "workspace-d3-readonly", "Sparse event projection", now),
    )
    connection.execute(
        "INSERT INTO inquiries(id, project_id, question, acceptance, status, revision, created_at) VALUES (?, ?, ?, ?, 'active', 1, ?)",
        ("inquiry-readonly", "project-readonly", "Can canonical facts survive browser reconnect?", "Projection and Receipt remain consistent.", now),
    )
    connection.execute(
        "INSERT INTO plans(id, inquiry_id, revision, status, steps_json, policy_json, budget_json, created_at) VALUES (?, ?, 1, 'completed', ?, ?, ?, ?)",
        (
            "plan-readonly",
            "inquiry-readonly",
            json.dumps([{"id": "step-locked-test", "title": "Run the frozen locked test", "approval_required": False}]),
            json.dumps({}),
            json.dumps({}),
            now,
        ),
    )
    connection.execute(
        "INSERT INTO resources(id, project_id, kind, logical_ref, content_hash, media_type, data_class, captured_at, status, revision) VALUES (?, ?, 'dataset', ?, ?, 'application/json', 'public', ?, 'available', 1)",
        ("resource-readonly", "project-readonly", "fixture:canonical-events", "sha256:" + "1" * 64, now),
    )
    connection.execute(
        "INSERT INTO locators(id, resource_id, locator_type, coordinates_json, quote_hash, status, revision) VALUES (?, ?, 'dataset', ?, ?, 'valid', 1)",
        ("locator-readonly", "resource-readonly", json.dumps({"kind": "dataset", "row": 1}), "sha256:" + "2" * 64),
    )
    connection.execute(
        "INSERT INTO claims(id, inquiry_id, statement, status, revision, created_by_json) VALUES (?, ?, ?, 'verified', 1, ?)",
        ("claim-readonly", "inquiry-readonly", "Sparse committed Event IDs remain replayable.", json.dumps({"kind": "system"})),
    )
    connection.execute(
        "INSERT INTO evidence(id, inquiry_id, locator_id, direction, excerpt_hash, status, created_by_json) VALUES (?, ?, ?, 'supports', ?, 'valid', ?)",
        ("evidence-readonly", "inquiry-readonly", "locator-readonly", "sha256:" + "3" * 64, json.dumps({"kind": "system"})),
    )
    connection.executemany(
        "INSERT INTO runs(id, project_id, inquiry_id, state, snapshot_json, result_json, created_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("run-succeeded", "project-readonly", "inquiry-readonly", "succeeded", json.dumps({}), json.dumps({"result": "succeeded"}), now, now),
            ("run-uncertain", "project-readonly", "inquiry-readonly", "orphaned", json.dumps({}), json.dumps({"result": "effect_unknown"}), now, now),
            ("run-waiting", "project-readonly", "inquiry-readonly", "paused", json.dumps({}), None, now, None),
        ],
    )
    connection.executemany(
        "INSERT INTO artifacts(id, media_type, blob_hash, size, state, producer_run_id, retention_json, created_at) VALUES (?, ?, ?, ?, 'available', ?, ?, ?)",
        [
            ("artifact-args-1", "application/json", "sha256:" + "4" * 64, 2, None, json.dumps({}), now),
            ("artifact-args-2", "application/json", "sha256:" + "5" * 64, 2, None, json.dumps({}), now),
            ("artifact-args-3", "application/json", "sha256:" + "c" * 64, 2, None, json.dumps({}), now),
            ("artifact-result", "text/plain", "sha256:" + "6" * 64, 12, "run-succeeded", json.dumps({}), now),
        ],
    )
    connection.executemany(
        "INSERT INTO actions(id, run_id, plan_step_id, capability_id, capability_version, executable_digest, args_artifact_id, args_hash, action_hash, risk_tier, requested_effects_json, policy_decision, authorization_ref, state, started_at, finished_at) VALUES (?, ?, ?, 'python.unittest.locked', '1', ?, ?, ?, ?, 'T2', ?, ?, ?, ?, ?, ?)",
        [
            ("action-succeeded", "run-succeeded", "step-locked-test", "sha256:" + "b" * 64, "artifact-args-1", "sha256:" + "7" * 64, "sha256:" + "8" * 64, json.dumps({"reads": [], "writes": [], "network": [], "processes": ["builtin:python.unittest.locked"]}), "grant", "policy_grant:fixture", "succeeded", now, now),
            ("action-uncertain", "run-uncertain", "step-locked-test", "sha256:" + "b" * 64, "artifact-args-2", "sha256:" + "9" * 64, "sha256:" + "a" * 64, json.dumps({"reads": [], "writes": [], "network": [], "processes": ["builtin:python.unittest.locked"]}), "grant", "policy_grant:fixture", "effect_unknown", now, now),
            ("action-waiting", "run-waiting", "step-locked-test", "sha256:" + "b" * 64, "artifact-args-3", "sha256:" + "d" * 64, "sha256:" + "e" * 64, json.dumps({"reads": [], "writes": [], "network": [], "processes": ["builtin:python.unittest.locked"]}), "approval_required", None, "waiting_approval", None, None),
        ],
    )
    receipt_sql = (
        "INSERT INTO action_receipts(id, action_id, action_hash, authorization_source, authorization_ref, actual_effects_json, result, before_artifact_ids_json, after_artifact_ids_json, resource_usage_json, created_at, authorized_effects_json, effect_violation) "
        "VALUES (?, ?, ?, 'policy_grant', 'policy_grant:fixture', ?, ?, '[]', ?, ?, ?, ?, 0)"
    )
    connection.executemany(
        receipt_sql,
        [
            ("receipt-succeeded", "action-succeeded", "sha256:" + "8" * 64, json.dumps({"reads": [], "writes": [], "network": [], "processes": ["builtin:python.unittest.locked"]}), "succeeded", json.dumps(["artifact-result"]), json.dumps({"wall_clock_ms": 24}), now, json.dumps({"reads": [], "writes": [], "network": [], "processes": ["builtin:python.unittest.locked"]})),
            ("receipt-uncertain", "action-uncertain", "sha256:" + "a" * 64, json.dumps({"reads": [], "writes": [], "network": [], "processes": ["builtin:python.unittest.locked"]}), "effect_unknown", "[]", json.dumps({"wall_clock_ms": 31}), now, json.dumps({"reads": [], "writes": [], "network": [], "processes": ["builtin:python.unittest.locked"]})),
        ],
    )
    connection.execute(
        "INSERT INTO findings(id, inquiry_id, statement, status, confidence_basis, evidence_ids_json, producer_run_id, revision) VALUES (?, ?, ?, 'draft', ?, ?, ?, 1)",
        ("finding-readonly", "inquiry-readonly", "The browser projection preserves causal status.", "Fixture evidence and terminal Receipt.", json.dumps(["evidence-readonly"]), "run-succeeded"),
    )
    actor = json.dumps({"kind": "system", "id": "d3-e2e"})
    events = [
        ("workspace", "workspace-d3-readonly", 1, None, None, None, "workspace.created", {"state": "active"}),
        ("run", "run-succeeded", 1, "run-succeeded", 1, None, "run.started", {"state": "running"}),
        ("action", "action-succeeded", 1, "run-succeeded", 2, "action-succeeded", "action.completed", {"state": "succeeded"}),
        (
            "artifact",
            "artifact-result",
            1,
            "run-succeeded",
            3,
            "action-succeeded",
            "artifact.committed",
            {
                "artifact_id": "artifact-result",
                "state": "available",
                "blob_hash": "sha256:" + "6" * 64,
                "size": 12,
                "media_type": "text/plain",
            },
        ),
        ("run", "run-succeeded", 2, "run-succeeded", 4, None, "run.succeeded", {"state": "succeeded"}),
        ("run", "run-uncertain", 1, "run-uncertain", 1, None, "run.orphaned", {"state": "orphaned"}),
        ("action", "action-uncertain", 1, "run-uncertain", 2, "action-uncertain", "action.effect_unknown", {"state": "effect_unknown"}),
        ("action", "action-waiting", 1, "run-waiting", 1, "action-waiting", "action.proposed", {"action_id": "action-waiting", "state": "waiting_approval"}),
    ]
    for aggregate_type, aggregate_id, version, run_id, run_seq, action_id, event_type, payload in events:
        event = connection.execute(
            "INSERT INTO events(aggregate_type, aggregate_id, aggregate_version, run_id, run_seq, action_id, actor_json, type, payload_json, occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (aggregate_type, aggregate_id, version, run_id, run_seq, action_id, actor, event_type, json.dumps(payload), now),
        )
        connection.execute("INSERT INTO outbox_events(event_id) VALUES (?)", (event.lastrowid,))
    connection.commit()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=43123)
    parser.add_argument(
        "--build-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "nana_web" / "dist",
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    with tempfile.TemporaryDirectory(prefix="nana-d3-readonly-") as directory:
        workspace = WorkspaceRuntime(Path(directory) / "nana.db")
        workspace.start()
        try:
            _seed_readonly_fixture(workspace)
            app = create_runtime_app(
                workspace_runtime=workspace,
                local_session=LocalSession(
                    token=E2E_TOKEN,
                    origin=f"http://127.0.0.1:{args.port}",
                ),
                web_build_root=args.build_root,
                bootstrap_secret=E2E_BOOTSTRAP_SECRET,
            )
            uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
        finally:
            if workspace.state == "ready":
                workspace.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
