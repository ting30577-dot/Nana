"""Copy, verify and recoverably archive legacy runtime roots from a checkout.

The command is dry-run by default.  ``--apply`` copies each known runtime tree
to the canonical Nana user-data layout, verifies a content inventory, commits
the destination, and finally moves the source tree into the repository's
ignored ``backups`` directory.  It never merges with a non-empty destination.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nana_sidecar.storage.workspace_lock import WorkspaceLock, WorkspaceLockError
from nana_sidecar.user_data import prepare_user_data_layout


_KNOWN_ROOTS = ("workspaces", "usability_sessions", "exports", "logs", "crash")


@dataclass(frozen=True, slots=True)
class TreeInventory:
    files: int
    bytes: int
    digest: str


@dataclass(frozen=True, slots=True)
class MigrationRecord:
    source_label: str
    destination_class: str
    backup_label: str
    files: int
    bytes: int
    digest: str
    disposition: str


def inventory_tree(root: Path) -> TreeInventory:
    entries: list[tuple[str, int, str]] = []
    total = 0
    for current_text, directories, files in os.walk(root, topdown=True, followlinks=False):
        current = Path(current_text)
        directories.sort(key=str.casefold)
        files.sort(key=str.casefold)
        for name in directories:
            path = current / name
            metadata = path.lstat()
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            if (
                path.is_symlink()
                or bool(
                    reparse_flag
                    and int(getattr(metadata, "st_file_attributes", 0)) & reparse_flag
                )
                or getattr(os.path, "isjunction", lambda _candidate: False)(path)
            ):
                raise RuntimeError(f"runtime migration refuses reparse directory: {name}")
        for name in files:
            path = current / name
            if path.is_symlink():
                raise RuntimeError(f"runtime migration refuses symlink: {name}")
            relative = path.relative_to(root).as_posix()
            file_digest = hashlib.sha256()
            size = 0
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    file_digest.update(chunk)
                    size += len(chunk)
            total += size
            entries.append((relative, size, file_digest.hexdigest()))
    normalized = "\n".join(
        f"{relative}\t{size}\t{digest}" for relative, size, digest in entries
    ).encode("utf-8")
    return TreeInventory(
        files=len(entries),
        bytes=total,
        digest=hashlib.sha256(normalized).hexdigest(),
    )


def _prove_workspace_idle(root: Path) -> None:
    locks: list[tuple[WorkspaceLock, bool]] = []
    try:
        for database in root.rglob("nana.db"):
            lock_path = database.with_name("workspace.owner.lock")
            existed = lock_path.exists()
            lock = WorkspaceLock(lock_path)
            lock.acquire()
            locks.append((lock, existed))
    except WorkspaceLockError as exc:
        raise RuntimeError("runtime migration refused an active Workspace") from exc
    finally:
        for lock, existed in reversed(locks):
            lock.release()
            if not existed:
                lock.path.unlink(missing_ok=True)


def migrate_runtime_roots(
    *,
    repository_root: Path,
    data_root: Path,
    backup_root: Path,
) -> tuple[MigrationRecord, ...]:
    sources = [
        (name, repository_root / name, data_root / name)
        for name in _KNOWN_ROOTS
        if (repository_root / name).exists()
    ]
    for name, source, destination in sources:
        if (
            not source.is_dir()
            or source.is_symlink()
            or getattr(os.path, "isjunction", lambda _candidate: False)(source)
        ):
            raise RuntimeError(f"legacy runtime root is not a real directory: {name}")
        if destination.exists() and any(destination.iterdir()):
            raise RuntimeError(
                f"destination for {name} is not empty; migration will not merge"
            )
        inventory_tree(source)
        _prove_workspace_idle(source)

    backup_root.mkdir(parents=True, exist_ok=False)
    records: list[MigrationRecord] = []
    for name, source, destination in sources:
        before = inventory_tree(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = destination.parent / f".{name}.migration-{uuid.uuid4().hex}"
        shutil.copytree(source, staging, copy_function=shutil.copy2)
        copied = inventory_tree(staging)
        if copied != before:
            shutil.rmtree(staging)
            raise RuntimeError(f"content verification failed while copying {name}")
        if destination.exists():
            destination.rmdir()
        os.replace(staging, destination)
        committed = inventory_tree(destination)
        if committed != before:
            raise RuntimeError(f"destination verification failed for {name}")
        backup = backup_root / name
        os.replace(source, backup)
        archived = inventory_tree(backup)
        if archived != before:
            raise RuntimeError(f"recoverable archive verification failed for {name}")
        records.append(
            MigrationRecord(
                source_label=name,
                destination_class=f"Nana user-data/{name}",
                backup_label=f"backups/{backup_root.name}/{name}",
                files=before.files,
                bytes=before.bytes,
                digest=before.digest,
                disposition="copied_verified_destination_committed_source_archived",
            )
        )
    return tuple(records)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    candidates = [name for name in _KNOWN_ROOTS if (ROOT / name).exists()]
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "legacy_roots": candidates}, sort_keys=True))
        return 0

    layout = prepare_user_data_layout(application_root=ROOT)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = ROOT / "backups" / f"runtime-migration-{timestamp}"
    records = migrate_runtime_roots(
        repository_root=ROOT,
        data_root=layout.root,
        backup_root=backup_root,
    )
    receipt = {
        "schema": "nana.runtime_data_migration.v1",
        "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "destination_class": "OS Nana user-data root",
        "records": [asdict(record) for record in records],
    }
    serialized = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.receipt:
        receipt_path = args.receipt
        if not receipt_path.is_absolute():
            receipt_path = ROOT / receipt_path
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(serialized, encoding="utf-8", newline="\n")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
