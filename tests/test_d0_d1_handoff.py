"""D0 schema handoff simulation for the first D1 Artifact/Event slice.

This intentionally exercises metadata only.  Filesystem rename,
reconciliation services, HTTP SSE, and command handlers remain D1 work.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from nana_sidecar.storage import connect_database, initialize_database


NOW = "2026-07-29T00:00:00Z"
HASH = "sha256:" + "a" * 64


class D0D1HandoffSimulationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "workspace" / "nana.db"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_artifact_metadata_transaction_crash_and_replay_shape(self) -> None:
        connection = initialize_database(self.path)
        artifact_id = str(uuid4())

        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO artifacts (
                id, media_type, blob_hash, size, state, temp_ref,
                retention_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                "text/plain",
                HASH,
                7,
                "staged",
                "staging/handoff.partial",
                "{}",
                NOW,
            ),
        )
        staged = connection.execute(
            """
            INSERT INTO events (
                aggregate_type, aggregate_id, aggregate_version, actor_json,
                type, payload_json, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "artifact",
                artifact_id,
                1,
                '{"kind":"system","id":"artifact-store"}',
                "artifact.staged",
                json.dumps(
                    {
                        "artifact_id": artifact_id,
                        "state": "staged",
                        "temp_ref": "staging/handoff.partial",
                        "blob_hash": HASH,
                        "size": 7,
                        "media_type": "text/plain",
                    }
                ),
                NOW,
            ),
        )
        staged_event_id = int(staged.lastrowid)
        connection.execute(
            "INSERT INTO outbox_events(event_id) VALUES (?)",
            (staged_event_id,),
        )
        connection.commit()
        connection.close()

        connection = connect_database(self.path)
        staged_row = connection.execute(
            "SELECT state, temp_ref FROM artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()
        self.assertEqual(
            (staged_row["state"], staged_row["temp_ref"]),
            ("staged", "staging/handoff.partial"),
        )

        rolled_back_id = str(uuid4())
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO artifacts (
                id, media_type, blob_hash, size, state, temp_ref,
                retention_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rolled_back_id,
                "text/plain",
                HASH,
                7,
                "staged",
                "staging/rollback.partial",
                "{}",
                NOW,
            ),
        )
        rolled_back_event = connection.execute(
            """
            INSERT INTO events (
                aggregate_type, aggregate_id, aggregate_version, actor_json,
                type, payload_json, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "artifact",
                rolled_back_id,
                1,
                '{"kind":"system","id":"artifact-store"}',
                "artifact.staged",
                json.dumps(
                    {
                        "artifact_id": rolled_back_id,
                        "state": "staged",
                        "temp_ref": "staging/rollback.partial",
                        "blob_hash": HASH,
                        "size": 7,
                        "media_type": "text/plain",
                    }
                ),
                NOW,
            ),
        )
        connection.execute(
            "INSERT INTO outbox_events(event_id) VALUES (?)",
            (int(rolled_back_event.lastrowid),),
        )
        connection.rollback()
        self.assertEqual(
            connection.execute(
                "SELECT COUNT(*) FROM artifacts WHERE id = ?",
                (rolled_back_id,),
            ).fetchone()[0],
            0,
        )

        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "UPDATE artifacts SET state = 'available', temp_ref = NULL "
            "WHERE id = ?",
            (artifact_id,),
        )
        committed = connection.execute(
            """
            INSERT INTO events (
                aggregate_type, aggregate_id, aggregate_version, actor_json,
                type, payload_json, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "artifact",
                artifact_id,
                2,
                '{"kind":"system","id":"artifact-store"}',
                "artifact.committed",
                json.dumps(
                    {
                        "artifact_id": artifact_id,
                        "state": "available",
                        "blob_hash": HASH,
                        "size": 7,
                        "media_type": "text/plain",
                    }
                ),
                NOW,
            ),
        )
        committed_event_id = int(committed.lastrowid)
        connection.execute(
            "INSERT INTO outbox_events(event_id) VALUES (?)",
            (committed_event_id,),
        )
        connection.commit()

        replay = connection.execute(
            "SELECT id, type FROM events WHERE id > ? ORDER BY id",
            (staged_event_id,),
        ).fetchall()
        self.assertEqual(
            [(int(row["id"]), row["type"]) for row in replay],
            [(committed_event_id, "artifact.committed")],
        )
        visible = connection.execute(
            "SELECT COUNT(*) FROM artifacts "
            "WHERE id = ? AND state = 'available'",
            (artifact_id,),
        ).fetchone()[0]
        self.assertEqual(visible, 1)
        connection.close()

    def test_ten_thousand_event_cursor_shape_is_exact(self) -> None:
        connection = initialize_database(self.path)
        connection.execute("BEGIN IMMEDIATE")
        for version in range(1, 10_001):
            event = connection.execute(
                """
                INSERT INTO events (
                    aggregate_type, aggregate_id, aggregate_version,
                    actor_json, type, payload_json, occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "handoff_probe",
                    "aggregate-1",
                    version,
                    '{"kind":"system","id":"handoff-probe"}',
                    "budget.updated",
                    json.dumps({"sequence": version}),
                    NOW,
                ),
            )
            connection.execute(
                "INSERT INTO outbox_events(event_id) VALUES (?)",
                (int(event.lastrowid),),
            )
        connection.commit()
        connection.close()

        connection = connect_database(self.path)
        cursor = 0
        received: list[tuple[int, int]] = []
        while True:
            rows = connection.execute(
                "SELECT id, aggregate_version FROM events "
                "WHERE id > ? ORDER BY id LIMIT 257",
                (cursor,),
            ).fetchall()
            if not rows:
                break
            received.extend(
                (int(row["id"]), int(row["aggregate_version"]))
                for row in rows
            )
            cursor = int(rows[-1]["id"])

        self.assertEqual(
            [event_id for event_id, _ in received],
            list(range(1, 10_001)),
        )
        self.assertEqual(
            [version for _, version in received],
            list(range(1, 10_001)),
        )
        self.assertEqual(
            connection.execute(
                "SELECT COUNT(*) FROM outbox_events"
            ).fetchone()[0],
            10_000,
        )
        self.assertEqual(
            str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower(),
            "wal",
        )
        connection.close()


if __name__ == "__main__":
    unittest.main()
