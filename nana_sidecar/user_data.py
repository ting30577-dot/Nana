"""Canonical Nana user-data layout outside the source/application tree.

The product launcher uses this module instead of deriving writable paths from
the current working directory.  Environment overrides are supported for
tests and managed deployments, but they remain subject to the same absolute,
non-reparse and application-tree separation checks.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


APPLICATION_ROOT = Path(__file__).resolve().parents[1]
_OVERRIDE = "NANA_DATA_ROOT"


class UserDataBoundaryError(RuntimeError):
    """A writable Nana path could not be proven safe."""


@dataclass(frozen=True, slots=True)
class UserDataLayout:
    root: Path
    workspaces: Path
    usability_sessions: Path
    exports: Path
    logs: Path
    crash: Path
    temporary: Path

    @property
    def default_workspace_database(self) -> Path:
        return self.workspaces / "d3" / "nana.db"


def _related(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _is_reparse(path: Path) -> bool:
    metadata = path.lstat()
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    return (
        path.is_symlink()
        or bool(reparse and attributes & reparse)
        or getattr(os.path, "isjunction", lambda _candidate: False)(path)
    )


def _reject_existing_reparse_components(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if not current.exists():
            break
        try:
            if _is_reparse(current):
                raise UserDataBoundaryError(
                    "Nana user-data paths must not contain symlink, junction, "
                    "mount-point or other reparse components"
                )
        except OSError as exc:
            raise UserDataBoundaryError(
                "Nana user-data path identity could not be verified"
            ) from exc


def _absolute(path: Path) -> Path:
    if not path.is_absolute():
        raise UserDataBoundaryError("Nana user-data root must be absolute")
    return Path(os.path.abspath(path))


def resolve_user_data_root(
    *,
    environ: Mapping[str, str] | None = None,
    application_root: Path = APPLICATION_ROOT,
    platform: str | None = None,
    home: Path | None = None,
) -> Path:
    """Resolve the writable root without consulting the process CWD."""

    values = os.environ if environ is None else environ
    platform = os.name if platform is None else platform
    override = values.get(_OVERRIDE, "").strip()
    if override:
        candidate = _absolute(Path(override))
    elif platform == "nt":
        local_app_data = values.get("LOCALAPPDATA", "").strip()
        if not local_app_data:
            raise UserDataBoundaryError(
                "LOCALAPPDATA is required when NANA_DATA_ROOT is not configured"
            )
        candidate = _absolute(Path(local_app_data)) / "Nana"
    else:
        xdg_data_home = values.get("XDG_DATA_HOME", "").strip()
        if xdg_data_home:
            candidate = _absolute(Path(xdg_data_home)) / "Nana"
        else:
            candidate = _absolute(home or Path.home()) / ".local" / "share" / "Nana"

    app = application_root.resolve(strict=True)
    _reject_existing_reparse_components(candidate)
    normalized = candidate.resolve(strict=False)
    if _related(normalized, app):
        raise UserDataBoundaryError(
            "Nana user-data root must be outside the application/source tree"
        )
    _reject_existing_reparse_components(normalized)
    return normalized


def user_data_layout(root: Path) -> UserDataLayout:
    root = _absolute(root).resolve(strict=False)
    return UserDataLayout(
        root=root,
        workspaces=root / "workspaces",
        usability_sessions=root / "usability_sessions",
        exports=root / "exports",
        logs=root / "logs",
        crash=root / "crash",
        temporary=root / "temp",
    )


def prepare_user_data_layout(
    *,
    environ: Mapping[str, str] | None = None,
    application_root: Path = APPLICATION_ROOT,
) -> UserDataLayout:
    root = resolve_user_data_root(
        environ=environ,
        application_root=application_root,
    )
    layout = user_data_layout(root)
    for directory in (
        layout.root,
        layout.workspaces,
        layout.usability_sessions,
        layout.exports,
        layout.logs,
        layout.crash,
        layout.temporary,
    ):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    _reject_existing_reparse_components(layout.root)
    return layout


def validate_runtime_path(
    path: Path,
    *,
    application_root: Path = APPLICATION_ROOT,
) -> Path:
    """Validate an explicit writable product path before creating it."""

    supplied = _absolute(path)
    _reject_existing_reparse_components(supplied.parent)
    candidate = supplied.resolve(strict=False)
    app = application_root.resolve(strict=True)
    if _related(candidate, app):
        raise UserDataBoundaryError(
            "runtime and user data must not be written inside the application/source tree"
        )
    _reject_existing_reparse_components(candidate.parent)
    return candidate
