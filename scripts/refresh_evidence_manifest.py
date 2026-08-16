"""Recompute a repository evidence manifest and its detached SHA-256."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def recompute_manifest(manifest_path: Path) -> tuple[str, str]:
    manifest_path = manifest_path.resolve(strict=True)
    if not manifest_path.is_relative_to(ROOT):
        raise ValueError("manifest must be inside the repository")
    relative_paths: list[str] = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        relative, separator, _old_digest = line.partition("\t")
        if not separator or not relative or relative in relative_paths:
            raise ValueError("manifest entries must be unique path<TAB>digest lines")
        target = (ROOT / relative).resolve(strict=True)
        if not target.is_relative_to(ROOT) or not target.is_file():
            raise ValueError(f"manifest target escapes the repository: {relative}")
        relative_paths.append(relative)
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
    args = parser.parse_args()
    manifest = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    normalized, digest = recompute_manifest(manifest)
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
