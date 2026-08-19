"""Deterministic Nana task bootstrap, authority checks, and cleanup planning."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_STATE = ROOT / "docs" / "ACTIVE_STATE.json"
KERNEL = ROOT / "docs" / "PROJECT_KERNEL.md"
ROUTES = ROOT / "config" / "context-routes.json"
RETENTION = ROOT / "config" / "document-retention.json"

HIGH_RISK_TERMS = {
    "auth",
    "authorization",
    "capability",
    "credential",
    "export",
    "external",
    "ipc",
    "migration",
    "path",
    "policy",
    "process",
    "receipt",
    "schema",
    "security",
    "selection",
    "sidecar",
    "workspace_lock",
}

PRIVACY_PATTERNS = {
    "windows_user_path": re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+"),
    "posix_user_path": re.compile(r"(?i)(?:^|\s)/(?:home|users)/[^/\s]+"),
    "api_key": re.compile(r"(?i)\b(?:sk-ant-|sk-proj-|sk-)[A-Za-z0-9_-]{12,}"),
    "authorization_header": re.compile(
        r"(?im)^\s*authorization\s*:\s*(?:bearer|basic)\s+"
        r"(?!<[^>\r\n]+>|none\b|null\b|redacted\b|masked\b|\*{3,})[^\s]+"
    ),
    "credential_field": re.compile(
        r"(?im)(?:^|[,{;\s])[\"']?"
        r"(?:(?:x[_-]?)?api[_-]?key|anthropic_api_key|openai_api_key|password|passwd|secret|"
        r"access[_-]?token|refresh[_-]?token|session[_-]?(?:cookie|token)|token|cookie)"
        r"[\"']?\s*[:=]\s*[\"']?"
        r"(?!<[^>\r\n]+>|none\b|null\b|redacted\b|masked\b|\*{3,})"
        r"[^\s,;}\"']+"
    ),
    "private_ipv4": re.compile(
        r"(?<!\d)(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
        r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?!\d)"
    ),
    "mac_address": re.compile(
        r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])"
    ),
    "sensitive_identity_field": re.compile(
        r"(?i)[\"']?(?:serial_number|license_key|machine_name|owner_name|user_name|username)"
        r"[\"']?\s*[:=]\s*[\"']?(?!<|none\b|null\b|redacted\b)[^\s,}\"']+"
    ),
}

RELEASE_BINARY_SUFFIXES = frozenset(
    {
        ".7z",
        ".bmp",
        ".class",
        ".db",
        ".dll",
        ".docx",
        ".dylib",
        ".exe",
        ".gif",
        ".gz",
        ".ico",
        ".jar",
        ".jpeg",
        ".jpg",
        ".mp3",
        ".mp4",
        ".otf",
        ".pdf",
        ".png",
        ".pptx",
        ".pyc",
        ".pyd",
        ".so",
        ".sqlite",
        ".sqlite3",
        ".tar",
        ".ttf",
        ".wav",
        ".wasm",
        ".webp",
        ".whl",
        ".woff",
        ".woff2",
        ".xlsx",
        ".zip",
    }
)

RELEASE_PLACEHOLDER_VALUES = frozenset(
    {
        "",
        "-",
        "...",
        "n/a",
        "na",
        "none",
        "null",
        "false",
        "masked",
        "placeholder",
        "redacted",
        "sample",
        "test",
        "unknown",
        "bytes",
        "bool",
        "dict",
        "field",
        "float",
        "int",
        "object",
        "str",
        "secretstr",
        "licensed",
        "never",
        "local",
        "captured",
        "candidate",
        "category",
        "match",
        "pattern",
        "result",
        "value",
        "groupindex",
        "<none>",
        "<null>",
        "<redacted>",
        "<masked>",
        "<placeholder>",
    }
)

RELEASE_FIELD_NAME_VALUE = re.compile(
    r"(?i)^(?:[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*)?[_-]?(?:field|name|value|token|key|secret|password|cookie)$"
)
RELEASE_TEST_CANARY = re.compile(
    r"(?i)(?:^|[_\-.])(?:canary|placeholder|redacted|masked|dummy|fake|fixture|example|sample|test|never|local)(?:$|[_\-.])"
)
RELEASE_SEQUENCE_CANARY = re.compile(
    r"(?i)(?:abcdefgh|12345678|01234567|deadbeef)(?:[a-z0-9_-]*)$"
)

RELEASE_TEXT_PATTERNS = {
    "windows_user_path": re.compile(rb"(?i)\b[A-Z]:\\Users\\[^\\\s]+"),
    "posix_user_path": re.compile(rb"(?i)(?:^|\s)/(?:home|users)/[^/\s]+"),
    "api_key": re.compile(rb"(?i)\b(?:sk-ant-|sk-proj-|sk-)[A-Za-z0-9_-]{12,}"),
    "authorization_header": re.compile(
        rb"(?im)^\s*authorization\s*:\s*(?:bearer|basic)\s+(?P<value>[^\s]+)"
    ),
    "credential_field": re.compile(
        rb"(?im)(?:^|[,{;\s])[\"']?(?:x[_-]?)?"
        rb"(?P<key>api[_-]?key|anthropic_api_key|openai_api_key|password|passwd|secret|"
        rb"access[_-]?token|refresh[_-]?token|session[_-]?(?:cookie|token)|token|cookie)"
        rb"[\"']?\s*[:=]\s*[\"']?(?P<value>[^\s,;}\"']+)"
    ),
    "private_ipv4": re.compile(
        rb"(?<!\d)(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
        rb"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?!\d)"
    ),
    "mac_address": re.compile(
        rb"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])"
    ),
    "sensitive_identity_field": re.compile(
        rb"(?i)[\"']?(?:serial_number|license_key|machine_name|owner_name|user_name|username)"
        rb"[\"']?\s*[:=]\s*[\"']?(?P<value>[^\s,}\"']+)"
    ),
}

RELEASE_FILENAME_PATTERNS = {
    "filename_user_path": re.compile(
        r"(?i)(?:^|/)(?:[a-z]:/)?(?:users|home)/[^/]+(?:/|$)"
    ),
    "filename_serial_number": re.compile(
        r"(?i)(?:^|/|[-_.])(?:serial(?:[-_.]?number)?|sn)[-_.][a-z0-9]{6,}(?:[-_.]|$)"
    ),
    "filename_authorization": re.compile(
        r"(?i)(?:^|/|[-_.])(?:api[-_]?key|auth(?:orization)?[-_]?(?:key|token)|"
        r"access[-_]?token|refresh[-_]?token|bearer|secret|password|cookie|license[-_]?key)"
        r"[-_.][a-z0-9][a-z0-9._-]{7,}(?:[-_.]|$)|"
        r"(?:^|/|[-_.])sk-(?:ant-|proj-)?[a-z0-9_-]{12,}(?:[-_.]|$)"
    ),
}


class GovernanceError(RuntimeError):
    """Raised when governance inputs are missing or contradictory."""


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        relative = path.relative_to(ROOT).as_posix()
        raise GovernanceError(f"cannot load {relative}: {exc}") from exc
    if not isinstance(value, dict):
        raise GovernanceError(f"{path.relative_to(ROOT).as_posix()} must contain an object")
    return value


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode:
        raise GovernanceError(completed.stderr.strip() or "git command failed")
    return completed.stdout


def _git_paths(*args: str) -> list[str]:
    """Return NUL-delimited Git path output without Windows code-page loss."""
    completed = subprocess.run(
        ["git", *args, "-z"],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if completed.returncode:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise GovernanceError(message or "git path command failed")
    return [
        value.decode("utf-8", errors="strict").replace("\\", "/")
        for value in completed.stdout.split(b"\0")
        if value
    ]


def _is_glob(value: str) -> bool:
    return any(character in value for character in "*?[")


def _relative_exists(value: str) -> bool:
    if _is_glob(value):
        return True
    return (ROOT / PurePosixPath(value.replace("\\", "/"))).exists()


def _validate_relative(value: str) -> None:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not value
        or normalized in {"", "."}
        or path.is_absolute()
        or ".." in path.parts
        or re.match(r"^[A-Za-z]:", normalized)
    ):
        raise GovernanceError(f"non-relative project path: {value}")


def _safe_cleanup_target(value: str) -> Path:
    """Validate the supplied path before resolution so reparse points stay visible."""
    _validate_relative(value)
    root = ROOT.resolve()
    supplied = Path(os.path.abspath(ROOT / PurePosixPath(value.replace("\\", "/"))))
    try:
        supplied.relative_to(root)
    except ValueError as exc:
        raise GovernanceError(f"cleanup target escapes repository: {value}") from exc
    if not supplied.exists() and not supplied.is_symlink():
        return supplied
    attributes = getattr(os.lstat(supplied), "st_file_attributes", 0)
    if supplied.is_symlink() or attributes & 0x400:
        raise GovernanceError(f"cleanup target is a reparse point: {value}")
    resolved = supplied.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise GovernanceError(f"cleanup target resolves outside repository: {value}") from exc
    return supplied


def _tree_size_without_reparse(directory: Path, label: str) -> int:
    """Measure a tree without following or accepting any nested reparse point."""
    total = 0
    pending = [directory]
    while pending:
        current = pending.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                attributes = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
                if entry.is_symlink() or attributes & 0x400:
                    relative = Path(entry.path).relative_to(ROOT).as_posix()
                    raise GovernanceError(
                        f"generated cleanup tree contains a reparse point: {label} -> {relative}"
                    )
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
    return total


def check() -> list[str]:
    state = _load_json(ACTIVE_STATE)
    routes = _load_json(ROUTES)
    retention = _load_json(RETENTION)
    errors: list[str] = []

    expected_schemas = {
        "nana.active_state.v1": state.get("schema"),
        "nana.context_routes.v1": routes.get("schema"),
        "nana.document_retention.v1": retention.get("schema"),
    }
    for expected, actual in expected_schemas.items():
        if expected != actual:
            errors.append(f"schema mismatch: expected {expected}, got {actual!r}")

    references: set[str] = set(routes.get("always_read", []))
    for route_name, route in routes.get("routes", {}).items():
        if not isinstance(route, dict):
            errors.append(f"route {route_name} must be an object")
            continue
        references.update(route.get("documents", []))
        references.update(route.get("source_roots", []))
        references.update(route.get("tests", []))
    references.update(state.get("authoritative_inputs", []))
    references.update(retention.get("keep_exact", []))

    for value in sorted(references):
        try:
            _validate_relative(value)
        except GovernanceError as exc:
            errors.append(str(exc))
            continue
        if not _relative_exists(value):
            errors.append(f"referenced project path is missing: {value}")

    for pattern in retention.get("delete_name_patterns", []):
        try:
            re.compile(pattern)
        except re.error as exc:
            errors.append(f"invalid retention pattern {pattern!r}: {exc}")

    baseline = state.get("stable_baseline", {})
    if baseline.get("status") != "acceptance_complete_release_baseline_frozen":
        errors.append("stable D3 baseline status changed without a kernel decision")
    stage = state.get("active_product_stage", {})
    if stage.get("product_migration_authorized") is not False:
        errors.append("active state must not authorize Tauri product migration at stage 1")
    if not KERNEL.is_file():
        errors.append("docs/PROJECT_KERNEL.md is missing")
    if errors:
        raise GovernanceError("\n".join(errors))
    return [
        "authority schemas are valid",
        f"{len(routes.get('routes', {}))} context routes are resolvable",
        "retention rules compile and explicit keep rules take precedence",
        "D3 baseline and Tauri stage-1 boundary agree",
    ]


def _status_paths() -> list[str]:
    records = _git_paths("-c", "core.quotepath=false", "status", "--short")
    paths: list[str] = []
    index = 0
    while index < len(records):
        record = records[index]
        if len(record) < 4 or record[2] != " ":
            raise GovernanceError("invalid NUL-delimited git status record")
        status = record[:2]
        paths.append(record[3:].replace("\\", "/"))
        # In porcelain v1 -z output, rename/copy entries are two records:
        # `XY destination\0source\0`. Only the destination is a current path.
        index += 2 if "R" in status or "C" in status else 1
    return paths


def bootstrap(route_name: str, external: bool = False) -> str:
    check()
    state = _load_json(ACTIVE_STATE)
    routes = _load_json(ROUTES)
    route = routes.get("routes", {}).get(route_name)
    if not isinstance(route, dict):
        choices = ", ".join(sorted(routes.get("routes", {})))
        raise GovernanceError(f"unknown route {route_name!r}; choose one of: {choices}")

    lines = [
        "# Nana task context capsule",
        "",
        f"- Route: `{route_name}` — {route['description']}",
        f"- Product: `{state['product_version']}`",
        f"- Stable baseline: `{state['stable_baseline']['stage']}` / `{state['stable_baseline']['status']}`",
        f"- Active product stage: `{state['active_product_stage']['id']}` / `{state['active_product_stage']['status']}`",
        f"- Product migration authorized: `{str(state['active_product_stage']['product_migration_authorized']).lower()}`",
        f"- Default review: `{route['default_review']}`",
        "",
        "## Read in this order",
    ]
    ordered = list(routes.get("always_read", [])) + list(route.get("documents", []))
    for value in dict.fromkeys(ordered):
        lines.append(f"- `{value}`")
    lines.extend(["", "## Relevant implementation roots"])
    lines.extend(f"- `{value}`" for value in route.get("source_roots", []))
    lines.extend(["", "## Relevant tests"])
    lines.extend(f"- `{value}`" for value in route.get("tests", []))

    dirty = _status_paths()
    retention = _load_json(RETENTION)
    historical_deletions = [
        value
        for value in dirty
        if not (ROOT / PurePosixPath(value)).exists()
        and should_delete(value, retention)
    ]
    relevant_dirty = [value for value in dirty if value not in historical_deletions]
    lines.extend(["", f"## Existing worktree changes ({len(relevant_dirty)})"])
    if historical_deletions:
        lines.append(
            f"- `{len(historical_deletions)}` policy-selected historical deletions are summarized and excluded from task context"
        )
    shown = relevant_dirty[:40]
    lines.extend(f"- `{value}`" for value in shown)
    if len(relevant_dirty) > len(shown):
        lines.append(f"- ... {len(relevant_dirty) - len(shown)} more; inspect only if they overlap this route")
    lines.extend(
        [
            "",
            "## Working rule",
            "Do not scan the full repository or Vault. Define outcome, allowed scope, forbidden scope, acceptance evidence, and review level before edits.",
        ]
    )
    if external:
        lines.extend(
            [
                "",
                "## External-model privacy boundary",
                "This capsule contains repository-relative paths only. Do not add credentials, license data, serial numbers, account/machine names, private IP/MAC addresses, or raw user content.",
            ]
        )
    result = "\n".join(lines) + "\n"
    if external and privacy_findings(result, "context-capsule"):
        raise GovernanceError("generated external context capsule failed privacy scan")
    return result


def review_level(paths: Iterable[str], milestone: bool = False) -> tuple[str, list[str]]:
    normalized = [str(path).replace("\\", "/").casefold() for path in paths]
    if milestone:
        return "R3", ["explicit milestone/release boundary"]
    matched = sorted(
        term for term in HIGH_RISK_TERMS if any(term in path for path in normalized)
    )
    if matched:
        return "R2", [f"high-risk surface: {term}" for term in matched]
    if normalized:
        return "R1", ["normal code or documentation change"]
    return "R0", ["no changed path supplied"]


def privacy_findings(text: str, label: str = "<memory>") -> list[dict[str, int | str]]:
    """Return locations and categories without echoing sensitive matched values."""
    findings: list[dict[str, int | str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for category, pattern in PRIVACY_PATTERNS.items():
            if pattern.search(line):
                findings.append(
                    {"file": label, "line": line_number, "category": category}
                )
    return findings


def scan_privacy_files(values: Iterable[str]) -> list[dict[str, int | str]]:
    findings: list[dict[str, int | str]] = []
    for value in values:
        _validate_relative(value)
        target = (ROOT / PurePosixPath(value)).resolve(strict=True)
        if not target.is_relative_to(ROOT) or not target.is_file():
            raise GovernanceError(f"privacy scan target must be a repository file: {value}")
        findings.extend(
            privacy_findings(target.read_text(encoding="utf-8"), value)
        )
    return findings


def _release_value_is_placeholder(value: str, *, allow_short: bool = False) -> bool:
    normalized = value.strip().strip("\"'").strip().casefold()
    if normalized in RELEASE_PLACEHOLDER_VALUES:
        return True
    if not allow_short and len(normalized) < 8:
        return True
    if any(character in normalized for character in "\\()[]{}|?*+="):
        return True
    if normalized.endswith(("-", "_", ".", ":")):
        return True
    if re.fullmatch(r"[A-Z][A-Z0-9_]*", value.strip().strip("\"'")):
        return True
    if normalized.startswith("<") and normalized.endswith(">"):
        return True
    if re.fullmatch(r"[*#xX_-]{3,}", normalized):
        return True
    if RELEASE_TEST_CANARY.search(normalized):
        return True
    if RELEASE_SEQUENCE_CANARY.search(normalized):
        return True
    return bool(RELEASE_FIELD_NAME_VALUE.fullmatch(normalized))


def _release_filename_findings(relative: str) -> list[dict[str, int | str]]:
    findings: list[dict[str, int | str]] = []
    normalized = relative.replace("\\", "/")
    for category, pattern in RELEASE_FILENAME_PATTERNS.items():
        match = pattern.search(normalized)
        if match:
            candidate = match.group(0).strip("/._-")
            if category == "filename_user_path":
                username = normalized.strip("/").split("/")[-2]
                if _release_value_is_placeholder(username, allow_short=True):
                    continue
            if category == "filename_authorization" and _release_value_is_placeholder(candidate):
                continue
            findings.append({"file": relative, "line": 0, "category": category})
    return findings


def _release_line_number(data: bytes, offset: int) -> int:
    return data.count(b"\n", 0, offset) + 1


def _release_candidate(match: re.Match[bytes], group: str | None = None) -> str:
    value = match.group(group) if group else match.group(0)
    return value.decode("ascii", errors="ignore")


def release_privacy_findings_for_bytes(relative: str, data: bytes) -> list[dict[str, int | str]]:
    """Scan one release-tree path without decoding its bytes as UTF-8."""
    _validate_relative(relative)
    findings = _release_filename_findings(relative)
    suffix = PurePosixPath(relative).suffix.casefold()
    is_binary = suffix in RELEASE_BINARY_SUFFIXES or b"\0" in data[:8192]

    # Both branches intentionally scan bytes. Binary files are never sent to a
    # UTF-8 decoder; ASCII credential material remains discoverable in them.
    payload = bytes(data) if is_binary else data
    for category, pattern in RELEASE_TEXT_PATTERNS.items():
        for match in pattern.finditer(payload):
            captured = None
            if "value" in pattern.groupindex:
                captured = _release_candidate(match, "value")
            elif category == "api_key":
                captured = _release_candidate(match)
            elif category in {"private_ipv4", "mac_address"}:
                if payload[match.end() : match.end() + 2] == b"\\n":
                    continue
                captured = _release_candidate(match)
            if captured is not None and _release_value_is_placeholder(captured):
                continue
            findings.append(
                {
                    "file": relative,
                    "line": _release_line_number(data, match.start()),
                    "category": category,
                }
            )
    return findings


def _validate_git_ref(value: str, label: str) -> None:
    if not value or value.startswith("-") or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._/@+~-]*", value
    ):
        raise GovernanceError(f"invalid Git {label} ref")


def release_changed_paths(base: str = "main", head: str = "HEAD") -> list[str]:
    """Return exactly the add/copy/modify/rename paths in base...head."""
    _validate_git_ref(base, "base")
    _validate_git_ref(head, "head")
    completed = subprocess.run(
        [
            "git",
            "-c",
            "core.quotepath=false",
            "diff",
            "--name-only",
            "--diff-filter=ACMR",
            "--no-ext-diff",
            "--relative",
            "-z",
            f"{base}...{head}",
            "--",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if completed.returncode:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise GovernanceError(message or "Git diff failed")
    try:
        return [
            value.decode("utf-8", errors="strict").replace("\\", "/")
            for value in completed.stdout.split(b"\0")
            if value
        ]
    except UnicodeDecodeError as exc:
        raise GovernanceError("Git diff returned a non-UTF-8 path") from exc


def scan_release_privacy(base: str = "main", head: str = "HEAD") -> list[dict[str, int | str]]:
    """Scan only the exact tracked file set changed by a PR relative to main."""
    findings: list[dict[str, int | str]] = []
    for relative in release_changed_paths(base, head):
        _validate_relative(relative)
        target = ROOT / PurePosixPath(relative)
        if target.is_symlink():
            raise GovernanceError(f"release privacy target is a reparse point: {relative}")
        resolved = target.resolve(strict=True)
        if not resolved.is_relative_to(ROOT) or not resolved.is_file():
            raise GovernanceError(f"release privacy target must be a repository file: {relative}")
        findings.extend(release_privacy_findings_for_bytes(relative, resolved.read_bytes()))
    return sorted(
        findings,
        key=lambda item: (str(item["file"]), int(item["line"]), str(item["category"])),
    )


def should_delete(path: str, retention: dict | None = None) -> bool:
    retention = retention or _load_json(RETENTION)
    keep_exact = set(retention.get("keep_exact", []))
    keep_prefixes = tuple(retention.get("keep_prefixes", []))
    patterns = [re.compile(value) for value in retention.get("delete_name_patterns", [])]
    return not (path in keep_exact or path.startswith(keep_prefixes)) and any(
        pattern.search(path) for pattern in patterns
    )


def cleanup_candidates() -> list[str]:
    retention = _load_json(RETENTION)
    candidates = []
    for path in _git_paths("-c", "core.quotepath=false", "ls-files"):
        target = ROOT / PurePosixPath(path)
        if not (target.exists() or target.is_symlink()):
            continue
        if should_delete(path, retention):
            candidates.append(path)
    return sorted(candidates)


def apply_cleanup(confirm: str) -> list[str]:
    """Delete clean tracked history candidates; Git retains recoverability."""
    if confirm != "DELETE_TRACKED_HISTORY":
        raise GovernanceError(
            "cleanup apply requires --confirm DELETE_TRACKED_HISTORY"
        )
    candidates = cleanup_candidates()
    dirty = set(_status_paths())
    overlaps = sorted(
        path
        for path in candidates
        if path in dirty and (ROOT / PurePosixPath(path)).exists()
    )
    if overlaps:
        raise GovernanceError(
            "refusing to delete candidates with existing worktree changes: "
            + ", ".join(overlaps)
        )
    deleted: list[str] = []
    for value in candidates:
        target = _safe_cleanup_target(value)
        if target.is_dir():
            raise GovernanceError(f"cleanup target unexpectedly became a directory: {value}")
        if target.exists() or target.is_symlink():
            target.unlink()
            deleted.append(value)
    return deleted


def generated_roots() -> list[dict[str, int | str]]:
    retention = _load_json(RETENTION)
    results: list[dict[str, int | str]] = []
    for value in retention.get("generated_cleanup_roots", []):
        target = _safe_cleanup_target(value)
        if not target.exists() and not target.is_symlink():
            continue
        size = (
            target.stat().st_size
            if target.is_file()
            else _tree_size_without_reparse(target, value)
        )
        results.append({"path": value, "bytes": size})
    return results


def apply_generated_cleanup(confirm: str) -> list[str]:
    if confirm != "DELETE_REGENERABLE_OUTPUTS":
        raise GovernanceError(
            "generated cleanup requires --confirm DELETE_REGENERABLE_OUTPUTS"
        )
    targets = generated_roots()
    deleted: list[str] = []
    for item in targets:
        value = str(item["path"])
        target = _safe_cleanup_target(value)
        if target.is_dir():
            _tree_size_without_reparse(target, value)
            shutil.rmtree(target)
        else:
            target.unlink()
        deleted.append(value)
    return deleted


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="validate authority, routes, and retention")
    bootstrap_parser = subparsers.add_parser("bootstrap", help="emit a minimal task context capsule")
    bootstrap_parser.add_argument("--route", required=True)
    bootstrap_parser.add_argument("--external", action="store_true")
    review_parser = subparsers.add_parser("review-level", help="classify proportional review")
    review_parser.add_argument("--paths", nargs="*", default=[])
    review_parser.add_argument("--milestone", action="store_true")
    privacy_parser = subparsers.add_parser(
        "privacy-scan", help="fail closed on forbidden external-context data"
    )
    privacy_parser.add_argument("--files", nargs="+", required=True)
    release_privacy_parser = subparsers.add_parser(
        "release-privacy-scan",
        help="scan the exact PR file set relative to a Git base ref",
    )
    release_privacy_parser.add_argument("--base", default="main")
    release_privacy_parser.add_argument("--head", default="HEAD")
    cleanup_parser = subparsers.add_parser(
        "cleanup-plan", help="list or apply tracked retention-policy candidates"
    )
    cleanup_parser.add_argument("--apply", action="store_true")
    cleanup_parser.add_argument("--confirm")
    generated_parser = subparsers.add_parser(
        "generated-cleanup", help="list or remove explicitly configured build outputs"
    )
    generated_parser.add_argument("--apply", action="store_true")
    generated_parser.add_argument("--confirm")
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        if args.command == "check":
            for result in check():
                print(f"PASS: {result}")
        elif args.command == "bootstrap":
            print(bootstrap(args.route, external=args.external), end="")
        elif args.command == "review-level":
            level, reasons = review_level(args.paths, milestone=args.milestone)
            print(json.dumps({"level": level, "reasons": reasons}, ensure_ascii=False, indent=2))
        elif args.command == "privacy-scan":
            findings = scan_privacy_files(args.files)
            print(
                json.dumps(
                    {"passed": not findings, "findings": findings},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            if findings:
                return 3
        elif args.command == "release-privacy-scan":
            findings = scan_release_privacy(args.base, args.head)
            print(json.dumps(findings, ensure_ascii=False, indent=2))
            if findings:
                return 3
        elif args.command == "cleanup-plan":
            if args.apply:
                deleted = apply_cleanup(args.confirm or "")
                print(
                    json.dumps(
                        {"deleted_count": len(deleted), "recoverable_from": "Git history"},
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                candidates = cleanup_candidates()
                print(json.dumps({"count": len(candidates), "candidates": candidates}, ensure_ascii=False, indent=2))
        elif args.command == "generated-cleanup":
            if args.apply:
                deleted = apply_generated_cleanup(args.confirm or "")
                print(
                    json.dumps(
                        {
                            "deleted_count": len(deleted),
                            "deleted": deleted,
                            "recovery": "regenerate from versioned source",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                roots = generated_roots()
                print(
                    json.dumps(
                        {
                            "count": len(roots),
                            "total_bytes": sum(int(item["bytes"]) for item in roots),
                            "roots": roots,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
        return 0
    except GovernanceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
