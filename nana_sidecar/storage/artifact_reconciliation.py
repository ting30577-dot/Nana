"""Deterministic startup reconciliation for D1 Artifact crash windows."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, Mapping

from nana_sidecar.contracts.domain import ArtifactReconciledPayload
from nana_sidecar.storage.artifacts import (
    ArtifactIntegrityError,
    ArtifactStore,
    StagedArtifact,
)


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
class ReconciliationAction:
    kind: str
    artifact_id: str | None = None
    path: Path | None = None


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    actions: tuple[ReconciliationAction, ...]


class ArtifactReconciler:
    """Converge the six Artifact states defined by architecture section 8.3."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        store: ArtifactStore,
        *,
        now: Callable[[], float] = time.time,
        grace_seconds: float = 300,
        checkpoint: Callable[[str], None] | None = None,
    ) -> None:
        if grace_seconds < 0:
            raise ValueError("grace_seconds must be non-negative")
        self.connection = connection
        self.store = store
        self._now = now
        self.grace_seconds = grace_seconds
        self._checkpoint = checkpoint or _no_checkpoint
        self._actor_json = _json(
            {"kind": "system", "id": "artifact-reconciler", "version": "d1"}
        )

    def scan(self) -> ReconciliationReport:
        if self.connection.in_transaction:
            raise RuntimeError(
                "Artifact reconciliation requires an idle SQLite connection"
            )
        rows = tuple(
            self.connection.execute(
                """
                SELECT id, media_type, blob_hash, size, state, temp_ref
                FROM artifacts
                ORDER BY id
                """
            )
        )
        referenced_temp_refs = {
            str(row["temp_ref"])
            for row in rows
            if row["temp_ref"] is not None
        }
        referenced_blob_hashes = {str(row["blob_hash"]) for row in rows}
        actions: list[ReconciliationAction] = []

        actions.extend(self._quarantine_old_partials(referenced_temp_refs))
        staged_rows = tuple(row for row in rows if row["state"] == "staged")
        available_rows = tuple(
            row for row in rows if row["state"] == "available"
        )
        promoted_artifact_ids: set[str] = set()
        for row in staged_rows:
            promoted, preparation_actions = self._prepare_staged_blob(row)
            actions.extend(preparation_actions)
            if promoted:
                promoted_artifact_ids.add(str(row["id"]))
        for row in staged_rows:
            actions.extend(
                self._reconcile_staged(
                    row,
                    partial_was_promoted=(
                        str(row["id"]) in promoted_artifact_ids
                    ),
                )
            )
        for row in available_rows:
            action = self._reconcile_available(row)
            if action is not None:
                actions.append(action)
        actions.extend(self._quarantine_orphan_blobs(referenced_blob_hashes))
        return ReconciliationReport(actions=tuple(actions))

    def _quarantine_old_partials(
        self,
        referenced_temp_refs: set[str],
    ) -> list[ReconciliationAction]:
        if not self.store.staging_root.exists():
            return []
        cutoff = self._now() - self.grace_seconds
        actions: list[ReconciliationAction] = []
        for partial_path in sorted(self.store.staging_root.glob("*.partial")):
            temp_ref = partial_path.relative_to(
                self.store.workspace_root
            ).as_posix()
            if temp_ref in referenced_temp_refs:
                continue
            try:
                modified_at = partial_path.lstat().st_mtime
            except FileNotFoundError:
                continue
            if modified_at > cutoff:
                continue
            quarantined = self.store.quarantine_partial(partial_path)
            self._checkpoint("partial_quarantined")
            actions.append(
                ReconciliationAction(
                    kind="partial_quarantined",
                    path=quarantined,
                )
            )
        return actions

    def _prepare_staged_blob(
        self,
        row: sqlite3.Row,
    ) -> tuple[bool, list[ReconciliationAction]]:
        artifact_id = str(row["id"])
        staged = self._staged_from_row(row)
        if self._final_is_valid(staged) or not self._partial_is_valid(staged):
            return False, []
        actions: list[ReconciliationAction] = []
        final_path = self.store.blob_path(staged.blob_hash)
        if final_path.exists() or final_path.is_symlink():
            quarantined = self.store.quarantine_orphan_blob(
                staged.blob_hash,
                corrupt=True,
            )
            actions.append(
                ReconciliationAction(
                    kind="corrupt_final_quarantined",
                    artifact_id=artifact_id,
                    path=quarantined,
                )
            )
        final_path = self.store.promote(staged)
        self._checkpoint("staged_partial_promoted")
        actions.append(
            ReconciliationAction(
                kind="staged_partial_promoted",
                artifact_id=artifact_id,
                path=final_path,
            )
        )
        return True, actions

    def _reconcile_staged(
        self,
        row: sqlite3.Row,
        *,
        partial_was_promoted: bool,
    ) -> list[ReconciliationAction]:
        artifact_id = str(row["id"])
        staged = self._staged_from_row(row)
        final_valid = self._final_is_valid(staged)
        actions: list[ReconciliationAction] = []

        if final_valid:
            partial_entry = self._partial_entry_from_row(row)
            if partial_entry is not None and (
                partial_entry.exists() or partial_entry.is_symlink()
            ):
                quarantined = self.store.quarantine_partial(
                    partial_entry
                )
                actions.append(
                    ReconciliationAction(
                        kind="duplicate_partial_quarantined",
                        artifact_id=artifact_id,
                        path=quarantined,
                    )
                )
            self._transition(
                artifact_id,
                previous_state="staged",
                state="available",
                reason_code=(
                    "staged_partial_promoted"
                    if partial_was_promoted
                    else "staged_final_verified"
                ),
                clear_temp_ref=True,
                checkpoint=(
                    "staged_partial_ready"
                    if partial_was_promoted
                    else "staged_final_ready"
                ),
            )
            actions.append(
                ReconciliationAction(
                    kind=(
                        "staged_partial_available"
                        if partial_was_promoted
                        else "staged_final_available"
                    ),
                    artifact_id=artifact_id,
                    path=self.store.blob_path(staged.blob_hash),
                )
            )
            return actions

        self._transition(
            artifact_id,
            previous_state="staged",
            state="failed",
            reason_code="staged_content_missing_or_corrupt",
            clear_temp_ref=False,
            checkpoint="staged_failed_ready",
        )
        actions.append(
            ReconciliationAction(
                kind="staged_failed",
                artifact_id=artifact_id,
            )
        )
        return actions

    def _reconcile_available(
        self,
        row: sqlite3.Row,
    ) -> ReconciliationAction | None:
        staged = self._staged_from_row(row)
        if self._final_is_valid(staged):
            return None
        artifact_id = str(row["id"])
        self._transition(
            artifact_id,
            previous_state="available",
            state="corrupt",
            reason_code="available_blob_missing_or_corrupt",
            clear_temp_ref=False,
            checkpoint="available_corrupt_ready",
        )
        return ReconciliationAction(
            kind="available_corrupt",
            artifact_id=artifact_id,
        )

    def _quarantine_orphan_blobs(
        self,
        referenced_blob_hashes: set[str],
    ) -> list[ReconciliationAction]:
        content_root = self.store.artifacts_root / "sha256"
        if not content_root.exists():
            return []
        actions: list[ReconciliationAction] = []
        for final_path in sorted(content_root.glob("*/*/*")):
            digest = final_path.name
            blob_hash = f"sha256:{digest}"
            try:
                expected = self.store.blob_path(blob_hash)
            except ValueError:
                continue
            if final_path != expected:
                continue
            if blob_hash in referenced_blob_hashes:
                continue
            if not final_path.exists() and not final_path.is_symlink():
                continue
            quarantined = self.store.quarantine_orphan_blob(blob_hash)
            self._checkpoint("orphan_blob_quarantined")
            actions.append(
                ReconciliationAction(
                    kind="orphan_blob_quarantined",
                    path=quarantined,
                )
            )
        return actions

    def _staged_from_row(self, row: sqlite3.Row) -> StagedArtifact:
        temp_ref = row["temp_ref"]
        logical_ref = (
            str(temp_ref)
            if temp_ref is not None
            else "artifacts/.staging/__missing__.partial"
        )
        partial_path = self._partial_entry_from_row(row)
        if partial_path is None:
            partial_path = (
                self.store.staging_root
                / ".invalid-temp-ref"
                / "invalid.partial"
            )
        return StagedArtifact(
            partial_path=partial_path,
            temp_ref=logical_ref,
            blob_hash=str(row["blob_hash"]),
            size=int(row["size"]),
            media_type=str(row["media_type"]),
        )

    def _partial_entry_from_row(
        self,
        row: sqlite3.Row,
    ) -> Path | None:
        temp_ref = row["temp_ref"]
        if temp_ref is None:
            return None
        try:
            return self.store.partial_path_from_temp_ref(str(temp_ref))
        except ValueError:
            return None

    def _partial_is_valid(self, staged: StagedArtifact) -> bool:
        try:
            self.store.verify_staged(
                staged,
                expected_hash=staged.blob_hash,
                expected_size=staged.size,
                expected_media_type=staged.media_type,
            )
        except (ArtifactIntegrityError, FileNotFoundError, ValueError):
            return False
        return True

    def _final_is_valid(self, staged: StagedArtifact) -> bool:
        try:
            self.store.verify_final(staged)
        except (ArtifactIntegrityError, FileNotFoundError, ValueError):
            return False
        return True

    def _transition(
        self,
        artifact_id: str,
        *,
        previous_state: str,
        state: str,
        reason_code: str,
        clear_temp_ref: bool,
        checkpoint: str,
    ) -> None:
        payload = ArtifactReconciledPayload(
            artifact_id=artifact_id,
            previous_state=previous_state,
            state=state,
            reason_code=reason_code,
        )
        occurred_at = datetime.fromtimestamp(
            self._now(),
            tz=timezone.utc,
        ).isoformat().replace("+00:00", "Z")
        with self._transaction():
            updated = self.connection.execute(
                """
                UPDATE artifacts
                SET state = ?, temp_ref = CASE WHEN ? THEN NULL ELSE temp_ref END
                WHERE id = ? AND state = ?
                """,
                (state, clear_temp_ref, artifact_id, previous_state),
            )
            if updated.rowcount != 1:
                raise RuntimeError(
                    f"Artifact {artifact_id} changed during reconciliation"
                )
            aggregate_version = int(
                self.connection.execute(
                    """
                    SELECT COALESCE(MAX(aggregate_version), 0) + 1
                    FROM events
                    WHERE aggregate_type = 'artifact' AND aggregate_id = ?
                    """,
                    (artifact_id,),
                ).fetchone()[0]
            )
            cursor = self.connection.execute(
                """
                INSERT INTO events (
                    aggregate_type, aggregate_id, aggregate_version, actor_json,
                    type, payload_json, occurred_at
                ) VALUES ('artifact', ?, ?, ?, 'artifact.reconciled', ?, ?)
                """,
                (
                    artifact_id,
                    aggregate_version,
                    self._actor_json,
                    _json(payload.model_dump(mode="json")),
                    occurred_at,
                ),
            )
            self.connection.execute(
                "INSERT INTO outbox_events(event_id) VALUES (?)",
                (int(cursor.lastrowid),),
            )
            self._checkpoint(checkpoint)

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.connection.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise
