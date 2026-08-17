"""Audit a built Nana package and emit a deterministic content manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "release-input-allowlist.json"
MANIFEST_NAME = "PACKAGE_MANIFEST.sha256"


class ReleaseBoundaryError(RuntimeError):
    """A release input or output crossed the frozen package boundary."""


def load_policy(path: Path = POLICY_PATH) -> dict[str, object]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy.get("schema") != "nana.release_input_allowlist.v1":
        raise ReleaseBoundaryError("unknown release input policy schema")
    return policy


def _is_reparse(path: Path) -> bool:
    metadata = path.lstat()
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    return (
        path.is_symlink()
        or bool(flag and attributes & flag)
        or getattr(os.path, "isjunction", lambda _candidate: False)(path)
    )


def _package_paths(package_root: Path):
    for current_text, directories, files in os.walk(
        package_root, topdown=True, followlinks=False
    ):
        current = Path(current_text)
        directories.sort(key=str.casefold)
        files.sort(key=str.casefold)
        for name in directories:
            path = current / name
            if _is_reparse(path):
                raise ReleaseBoundaryError("package contains a reparse directory")
            yield path
        for name in files:
            path = current / name
            if _is_reparse(path):
                raise ReleaseBoundaryError("package contains a reparse file")
            yield path


def _hash_and_scan(path: Path, canaries: tuple[bytes, ...]) -> str:
    digest = hashlib.sha256()
    carry = b""
    carry_size = max((len(value) for value in canaries), default=1) - 1
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            window = carry + chunk
            if any(canary in window for canary in canaries):
                raise ReleaseBoundaryError("package contains a credential canary")
            carry = window[-carry_size:] if carry_size else b""
    return digest.hexdigest()


def _normalized_manifest(package_root: Path, policy: dict[str, object]) -> str:
    allowed_top = {str(item).casefold() for item in policy["allowed_package_top_level"]}
    forbidden_components = {
        str(item).casefold() for item in policy["forbidden_runtime_components"]
    }
    forbidden_names = {str(item).casefold() for item in policy["forbidden_exact_names"]}
    forbidden_suffixes = tuple(
        str(item).casefold() for item in policy["forbidden_suffixes"]
    )
    canaries = tuple(str(item).encode("utf-8") for item in policy["credential_canaries"])
    entries: list[str] = []
    for path in _package_paths(package_root):
        relative = path.relative_to(package_root)
        parts = tuple(part.casefold() for part in relative.parts)
        if parts and parts[0] not in allowed_top:
            raise ReleaseBoundaryError(
                f"package contains a non-allowlisted top-level entry: {relative.parts[0]}"
            )
        if any(part in forbidden_components for part in parts):
            raise ReleaseBoundaryError(
                f"package contains a forbidden runtime-data component: {relative.as_posix()}"
            )
        name = path.name.casefold()
        if name in forbidden_names or name.endswith(forbidden_suffixes):
            raise ReleaseBoundaryError(
                f"package contains a forbidden runtime/secret file: {relative.as_posix()}"
            )
        if not path.is_file() or relative.as_posix() == MANIFEST_NAME:
            continue
        try:
            file_digest = _hash_and_scan(path, canaries)
        except ReleaseBoundaryError as exc:
            raise ReleaseBoundaryError(
                f"package contains a credential canary: {relative.as_posix()}"
            ) from exc
        entries.append(f"{relative.as_posix()}\t{file_digest}")
    if not any(line.startswith("Nana.exe\t") for line in entries):
        raise ReleaseBoundaryError("package does not contain the Nana.exe entrypoint")
    return "\n".join(entries)


def audit_package(
    package_root: Path,
    *,
    write_manifest: bool = False,
    check_manifest: bool = False,
    policy_path: Path = POLICY_PATH,
) -> tuple[int, str]:
    supplied_root = package_root.absolute()
    if _is_reparse(supplied_root):
        raise ReleaseBoundaryError("package root must not be a reparse point")
    package_root = supplied_root.resolve(strict=True)
    if not package_root.is_dir():
        raise ReleaseBoundaryError("package root must be a directory")
    normalized = _normalized_manifest(package_root, load_policy(policy_path))
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    manifest = package_root / MANIFEST_NAME
    if write_manifest:
        manifest.write_text(normalized + "\n", encoding="ascii", newline="\n")
    if check_manifest:
        if not manifest.is_file():
            raise ReleaseBoundaryError("package manifest is missing")
        if manifest.read_text(encoding="ascii").rstrip("\r\n") != normalized:
            raise ReleaseBoundaryError("package manifest does not match package contents")
    return len(normalized.splitlines()) if normalized else 0, digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write-manifest", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    count, digest = audit_package(
        args.package_root,
        write_manifest=args.write_manifest,
        check_manifest=args.check,
    )
    print(json.dumps({"entries": count, "digest": digest}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
