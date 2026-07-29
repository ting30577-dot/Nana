"""Two-transaction Artifact commit protocol for D1."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, Mapping

from nana_sidecar.contracts.domain import (
    ArtifactCommittedPayload,
    ArtifactStagedPayload,
)
from nana_sidecar.storage.artifacts import (
    ArtifactIntegrityError,
    ArtifactNotAvailableError,
    ArtifactStore,
    StagedArtifact,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _no_checkpoint(name: str) -> None:
    return None


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


@dataclass(frozen=True, slots=True)
class ArtifactCommitResult:
    staged_event_id: int
    committed_event_id: int
    final_path: Path


@dataclass(frozen=True, slots=True)
class ArtifactPublishResult:
    committed_event_id: int
    final_path: Path


class ArtifactCommitService:
    """Persist Artifact metadata around a same-volume filesystem promotion."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        store: ArtifactStore,
        *,
        now: Callable[[], str] = _now,
        checkpoint: Callable[[str], None] | None = None,
    ) -> None:
        self.connection = connection
        self.store = store
        self._now = now
        self._checkpoint = checkpoint or _no_checkpoint
        self._actor_json = _json(
            {"kind": "system", "id": "artifact-store", "version": "d1"}
        )

    def record_staged(
        self,
        artifact_id: str,
        staged: StagedArtifact,
        *,
        producer_run_id: str | None = None,
        license: str | None = None,
        retention: Mapping[str, object] | None = None,
    ) -> int:
        """Atomically write staged metadata, lifecycle Event, and outbox row."""

        self.store.verify_staged(
            staged,
            expected_hash=staged.blob_hash,
            expected_size=staged.size,
            expected_media_type=staged.media_type,
        )
        payload = ArtifactStagedPayload(
            artifact_id=artifact_id,
            temp_ref=staged.temp_ref,
            blob_hash=staged.blob_hash,
            size=staged.size,
            media_type=staged.media_type,
        )
        occurred_at = self._now()
        with self._transaction():
            self.connection.execute(
                """
                INSERT INTO artifacts (
                    id, media_type, blob_hash, size, state, temp_ref,
                    producer_run_id, license, retention_json, created_at
                ) VALUES (?, ?, ?, ?, 'staged', ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    staged.media_type,
                    staged.blob_hash,
                    staged.size,
                    staged.temp_ref,
                    producer_run_id,
                    license,
                    _json(dict(retention or {})),
                    occurred_at,
                ),
            )
            event_id = self._insert_event(
                artifact_id=artifact_id,
                aggregate_version=1,
                event_type="artifact.staged",
                payload=payload.model_dump(mode="json"),
                occurred_at=occurred_at,
            )
            self.connection.execute(
                "INSERT INTO outbox_events(event_id) VALUES (?)",
                (event_id,),
            )
        self._checkpoint("staged_committed")
        return event_id

    def promote_and_publish(
        self,
        artifact_id: str,
        staged: StagedArtifact,
    ) -> ArtifactPublishResult:
        """Promote the blob, then atomically publish canonical availability."""

        self._require_matching_staged_row(artifact_id, staged)
        final_path = self.store.promote(staged)
        self._checkpoint("blob_promoted")
        payload = ArtifactCommittedPayload(
            artifact_id=artifact_id,
            blob_hash=staged.blob_hash,
            size=staged.size,
            media_type=staged.media_type,
        )
        occurred_at = self._now()
        with self._transaction():
            self._require_matching_staged_row(artifact_id, staged)
            self.store.verify_final(staged)
            updated = self.connection.execute(
                """
                UPDATE artifacts
                SET state = 'available', temp_ref = NULL
                WHERE id = ? AND state = 'staged'
                """,
                (artifact_id,),
            )
            if updated.rowcount != 1:
                raise ArtifactNotAvailableError(
                    f"Artifact {artifact_id} is not staged"
                )
            event_id = self._insert_event(
                artifact_id=artifact_id,
                aggregate_version=2,
                event_type="artifact.committed",
                payload=payload.model_dump(mode="json"),
                occurred_at=occurred_at,
            )
            self.connection.execute(
                "INSERT INTO outbox_events(event_id) VALUES (?)",
                (event_id,),
            )
        return ArtifactPublishResult(
            committed_event_id=event_id,
            final_path=final_path,
        )

    def commit(
        self,
        artifact_id: str,
        staged: StagedArtifact,
        *,
        producer_run_id: str | None = None,
        license: str | None = None,
        retention: Mapping[str, object] | None = None,
    ) -> ArtifactCommitResult:
        staged_event_id = self.record_staged(
            artifact_id,
            staged,
            producer_run_id=producer_run_id,
            license=license,
            retention=retention,
        )
        published = self.promote_and_publish(artifact_id, staged)
        return ArtifactCommitResult(
            staged_event_id=staged_event_id,
            committed_event_id=published.committed_event_id,
            final_path=published.final_path,
        )

    def _insert_event(
        self,
        *,
        artifact_id: str,
        aggregate_version: int,
        event_type: str,
        payload: Mapping[str, object],
        occurred_at: str,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO events (
                aggregate_type, aggregate_id, aggregate_version, actor_json,
                type, payload_json, occurred_at
            ) VALUES ('artifact', ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                aggregate_version,
                self._actor_json,
                event_type,
                _json(dict(payload)),
                occurred_at,
            ),
        )
        return int(cursor.lastrowid)

    def _require_matching_staged_row(
        self,
        artifact_id: str,
        staged: StagedArtifact,
    ) -> None:
        row = self.connection.execute(
            """
            SELECT state, temp_ref, blob_hash, size, media_type
            FROM artifacts
            WHERE id = ?
            """,
            (artifact_id,),
        ).fetchone()
        if row is None or row["state"] != "staged":
            raise ArtifactNotAvailableError(
                f"Artifact {artifact_id} is not staged"
            )
        expected = (
            staged.temp_ref,
            staged.blob_hash,
            staged.size,
            staged.media_type,
        )
        actual = (
            row["temp_ref"],
            row["blob_hash"],
            int(row["size"]),
            row["media_type"],
        )
        if actual != expected:
            raise ArtifactIntegrityError(
                f"canonical staged metadata mismatch for Artifact {artifact_id}"
            )

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        if self.connection.in_transaction:
            raise RuntimeError(
                "Artifact commit service requires an idle SQLite connection"
            )
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise


class ArtifactReader:
    """Read only blobs made available by canonical SQLite state."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        store: ArtifactStore,
    ) -> None:
        self.connection = connection
        self.store = store

    def read_bytes(self, artifact_id: str) -> bytes:
        row = self.connection.execute(
            """
            SELECT state, blob_hash, size
            FROM artifacts
            WHERE id = ?
            """,
            (artifact_id,),
        ).fetchone()
        if row is None or row["state"] != "available":
            raise ArtifactNotAvailableError(
                f"Artifact {artifact_id} is not available"
            )
        with self.store.open_for_read(
            str(row["blob_hash"]),
            state=str(row["state"]),
        ) as handle:
            content = handle.read()
        if len(content) != int(row["size"]):
            raise ArtifactIntegrityError(
                f"available Artifact size mismatch: {artifact_id}"
            )
        return content
