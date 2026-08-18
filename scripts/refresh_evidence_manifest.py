"""Recompute a repository evidence manifest and its detached SHA-256."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from collections.abc import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]


def _relative_path(path: Path) -> str:
    relative = path.relative_to(ROOT).as_posix()
    if relative in {"", "."} or relative.startswith("../"):
        raise ValueError(f"path must be inside the repository: {path}")
    return relative


def _resolve_scope(scope: Path, *, require_exists: bool = True) -> Path:
    candidate = scope if scope.is_absolute() else ROOT / scope
    resolved = candidate.resolve(strict=require_exists)
    if not resolved.is_relative_to(ROOT):
        raise ValueError(f"scope escapes the repository: {scope}")
    return resolved


def _discover_scope_files(scopes: Sequence[Path], excluded: Iterable[Path]) -> list[str]:
    excluded_resolved = [
        _resolve_scope(path, require_exists=False) for path in excluded
    ]
    discovered: set[str] = set()
    for scope in scopes:
        resolved = _resolve_scope(scope)
        candidates = [resolved] if resolved.is_file() else resolved.rglob("*")
        for candidate in candidates:
            if not candidate.is_file():
                continue
            candidate_resolved = candidate.resolve(strict=True)
            if any(
                candidate_resolved == ignored or ignored in candidate_resolved.parents
                for ignored in excluded_resolved
            ):
                continue
            discovered.add(_relative_path(candidate_resolved))
    return sorted(discovered)


def recompute_manifest(
    manifest_path: Path,
    *,
    scopes: Sequence[Path] | None = None,
    excluded: Sequence[Path] = (),
    strict_scope: bool = False,
) -> tuple[str, str]:
    manifest_path = manifest_path.resolve(strict=True)
    if not manifest_path.is_relative_to(ROOT):
        raise ValueError("manifest must be inside the repository")
    relative_paths: list[str] = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        relative, separator, _old_digest = line.partition("\t")
        if not separator or not relative or relative in relative_paths:
            raise ValueError("manifest entries must be unique path<TAB>digest lines")
        relative_paths.append(relative)
    if scopes is not None:
        expected_paths = _discover_scope_files(scopes, excluded)
        listed_paths = set(relative_paths)
        missing = sorted(set(expected_paths) - listed_paths)
        unexpected = sorted(listed_paths - set(expected_paths))
        if strict_scope and (missing or unexpected):
            details = []
            if missing:
                details.append(f"missing={','.join(missing)}")
            if unexpected:
                details.append(f"unexpected={','.join(unexpected)}")
            raise ValueError("manifest scope mismatch: " + "; ".join(details))
        relative_paths = expected_paths
    for relative in relative_paths:
        target = (ROOT / relative).resolve(strict=True)
        if not target.is_relative_to(ROOT) or not target.is_file():
            raise ValueError(f"manifest target escapes the repository: {relative}")
    normalized = "\n".join(
        f"{relative}\t{hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()}"
        for relative in relative_paths
    )
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return normalized, digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--scope",
        type=Path,
        action="append",
        default=None,
        help="file or directory whose complete file set must be represented",
    )
    parser.add_argument(
        "--exclude",
        type=Path,
        action="append",
        default=[],
        help="file or directory excluded from every scope",
    )
    args = parser.parse_args()
    manifest = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    normalized, digest = recompute_manifest(
        manifest,
        scopes=args.scope,
        excluded=args.exclude,
        strict_scope=args.check,
    )
    digest_path = manifest.with_suffix(".sha256")
    if args.check:
        if manifest.read_text(encoding="utf-8").rstrip("\r\n") != normalized:
            raise SystemExit("manifest entries are stale")
        if digest_path.read_text(encoding="ascii").strip() != digest:
            raise SystemExit("manifest digest is stale")
        return 0
    manifest.write_text(normalized + "\n", encoding="utf-8", newline="\n")
    digest_path.write_text(digest + "\n", encoding="ascii", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
