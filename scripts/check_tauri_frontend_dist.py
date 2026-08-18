"""Audit the exact Vite output that Tauri packages as its frontendDist."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "nana_web" / "dist"
ASSET_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.(?:css|gif|ico|jpe?g|js|png|svg|webp|woff2?)$")
FORBIDDEN_NAMES = {".env", ".env.local", "credentials.json", "session.json", "startup-secret.txt"}
FORBIDDEN_SUFFIXES = (".db", ".db-wal", ".db-shm", ".sqlite3", ".pem", ".key")
CANARIES = (
    b"NANA_RELEASE_CREDENTIAL_CANARY_DO_NOT_PACKAGE",
    b"NANA_RELEASE_BOOTSTRAP_SECRET_DO_NOT_PACKAGE",
)


class FrontendDistError(RuntimeError):
    """The Tauri frontendDist crossed the static-shell content boundary."""


def _is_reparse(path: Path) -> bool:
    metadata = path.lstat()
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    return (
        path.is_symlink()
        or bool(flag and attributes & flag)
        or getattr(os.path, "isjunction", lambda _candidate: False)(path)
    )


def _files(dist: Path) -> list[Path]:
    if _is_reparse(dist):
        raise FrontendDistError("frontendDist must not be a reparse point")
    if not dist.is_dir():
        raise FrontendDistError("frontendDist is missing")
    result: list[Path] = []
    for current_text, directories, files in os.walk(dist, topdown=True, followlinks=False):
        current = Path(current_text)
        directories.sort()
        files.sort()
        for name in directories:
            path = current / name
            if _is_reparse(path):
                raise FrontendDistError(f"frontendDist contains a reparse directory: {path}")
        for name in files:
            path = current / name
            if _is_reparse(path):
                raise FrontendDistError(f"frontendDist contains a reparse file: {path}")
            result.append(path)
    return result


def _hash_and_scan(path: Path) -> str:
    digest = hashlib.sha256()
    carry = b""
    carry_size = max(len(canary) for canary in CANARIES) - 1
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            window = carry + chunk
            if any(canary in window for canary in CANARIES):
                raise FrontendDistError(f"frontendDist contains a credential canary: {path.name}")
            carry = window[-carry_size:]
    return digest.hexdigest()


def _secure_dist_path(dist: Path) -> Path:
    supplied = Path(os.path.abspath(os.fspath(dist)))
    root = ROOT.absolute()
    if not supplied.is_relative_to(root):
        raise FrontendDistError("frontendDist must remain inside the repository")
    current = root
    for part in supplied.relative_to(root).parts:
        current /= part
        if _is_reparse(current):
            raise FrontendDistError(f"frontendDist path contains a reparse point: {current}")
    resolved = supplied.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise FrontendDistError("frontendDist resolves outside the repository")
    return resolved


def audit_frontend_dist(dist: Path = DIST) -> dict[str, object]:
    dist = _secure_dist_path(dist)
    paths = _files(dist)
    relative_paths = [path.relative_to(dist).as_posix() for path in paths]
    if "index.html" not in relative_paths or ".vite/manifest.json" not in relative_paths:
        raise FrontendDistError("frontendDist must contain index.html and .vite/manifest.json")

    entries: list[dict[str, str]] = []
    for path, relative in zip(paths, relative_paths, strict=True):
        parts = relative.split("/")
        name = path.name.casefold()
        if name in FORBIDDEN_NAMES or name.endswith(FORBIDDEN_SUFFIXES):
            raise FrontendDistError(f"frontendDist contains a sensitive file: {relative}")
        if relative not in {"index.html", ".vite/manifest.json"} and not (
            len(parts) == 2 and parts[0] == "assets" and ASSET_NAME.fullmatch(path.name)
        ):
            raise FrontendDistError(f"frontendDist contains an unexpected file: {relative}")
        entries.append({"path": relative, "sha256": _hash_and_scan(path)})

    try:
        manifest = json.loads((dist / ".vite" / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FrontendDistError("Vite manifest is not valid UTF-8 JSON") from exc
    referenced = {str(item["file"]) for item in manifest.values() if isinstance(item, dict) and "file" in item}
    for item in manifest.values():
        if not isinstance(item, dict):
            continue
        for css in item.get("css", []):
            if isinstance(css, str):
                referenced.add(css)
    actual = set(relative_paths) - {"index.html", ".vite/manifest.json"}
    if not referenced or not referenced.issubset(actual):
        raise FrontendDistError("Vite manifest references missing frontend assets")
    html = (dist / "index.html").read_text(encoding="utf-8")
    html_assets = set(re.findall(r"(?:src|href)=\"(assets/[^\"]+)\"", html))
    if not html_assets.issubset(actual):
        raise FrontendDistError("index.html references missing frontend assets")
    return {"schema": "nana.tauri.frontend_dist_audit.v1", "entries": entries}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=DIST)
    args = parser.parse_args()
    result = audit_frontend_dist(args.dist)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
