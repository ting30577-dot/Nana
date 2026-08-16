"""The sole authenticated D3 HTTP runtime and OpenAPI authority."""

from __future__ import annotations

import asyncio
import contextlib
import json
import mimetypes
import os
import re
import hmac
import secrets
import stat
import threading
from concurrent.futures import ThreadPoolExecutor
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable
from uuid import UUID, uuid4

from fastapi import Body, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse

from nana_sidecar import SCHEMA_READ_CEILING, SCHEMA_VERSION
from nana_sidecar.api_models import (
    ContractCatalogInfo,
    ExportSelectionInfo,
    HandshakeResponse,
    HealthResponse,
    RuntimeHandshakeResponse,
)
from nana_sidecar.app import _catalog_schema, _install_contract_openapi, _schema_hash
from nana_sidecar.contracts.commands import CommandResult, DEV_COMMAND_NAMES
from nana_sidecar.contracts.commands import StartRun, CancelRun
from nana_sidecar.contracts.common import ActorRef, EffectScope
from nana_sidecar.contracts.domain import EventType, RelationType
from nana_sidecar.contracts.errors import (
    ErrorCategory,
    ErrorCode,
    ErrorResponse,
    StructuredError,
)
from nana_sidecar.contracts.journey import (
    DecideApprovalRequest,
    JOURNEY_COMMAND_NAMES,
    JourneyCommandRequest,
    WorkspaceBootstrapSpec,
    to_canonical_command,
)
from nana_sidecar.export_selection import ExportSelectionRegistry
from nana_sidecar.contracts.locators import LOCATOR_KINDS
from nana_sidecar.sse import LocalSession, SQLiteEventStream, parse_last_event_id
from nana_sidecar.read_models import (
    BootstrapReadModel,
    PageTooLargeError,
    SnapshotTooLargeError,
)
from nana_sidecar.storage.workspace_lock import WorkspaceRuntime
from nana_sidecar.storage.command_transactions import CommandExecutionError
from nana_sidecar.storage.journey_commands import (
    FrozenResourceDescriptor,
    JourneyCommandService,
    WorkspaceBootstrapService,
)
from nana_sidecar.storage.locked_unittest_executor import (
    LockedExecutorError,
    LockedProcessResult,
    default_locked_unittest_runner,
)
from nana_sidecar.storage.draft_export import DraftExportService


_PUBLIC_HEALTH_PATH = "/healthz"
_BOOTSTRAP_EXCHANGE_PATH = "/api/v1/session/exchange"
_SESSION_RESTORE_PATH = "/api/v1/session/restore"
_JOURNEY_COMMAND_PATH = "/api/v1/journey/commands"
_SESSION_RECOVERY_COOKIE = "nana_session_recovery"
_AUTHENTICATED_GET_PATHS = frozenset(
    {
        "/api/v1/handshake",
        "/api/v1/contracts",
        "/api/v1/events",
        "/api/v1/bootstrap",
        "/openapi.json",
    }
)
_FORWARDED_HEADERS = frozenset({"forwarded", "x-forwarded-host", "x-forwarded-proto"})
_PREFLIGHT_HEADERS = frozenset({"authorization", "last-event-id"})
_MUTATION_PREFLIGHT_HEADERS = frozenset({"authorization", "content-type"})
_MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_MAX_JOURNEY_BODY_BYTES = 64 * 1024


@dataclass(slots=True)
class _OneTimeBootstrap:
    secret: bytes = field(repr=False)
    consumed: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def from_value(cls, value: str) -> "_OneTimeBootstrap":
        try:
            encoded = value.encode("ascii")
        except UnicodeEncodeError as exc:
            raise RuntimeConfigurationError("bootstrap secret must be ASCII") from exc
        if len(encoded) < 32:
            raise RuntimeConfigurationError("bootstrap secret must be at least 256 bits")
        return cls(encoded)

    def consume(self, candidate: str) -> bool:
        try:
            encoded = candidate.encode("ascii")
        except UnicodeEncodeError:
            return False
        with self.lock:
            if self.consumed or not hmac.compare_digest(encoded, self.secret):
                return False
            self.consumed = True
            self.secret = b"\x00" * len(self.secret)
            return True


@dataclass(frozen=True, slots=True)
class _SessionRecovery:
    secret: bytes = field(repr=False)

    @classmethod
    def create(cls) -> "_SessionRecovery":
        return cls(secrets.token_urlsafe(32).encode("ascii"))

    def matches(self, candidate: str | None) -> bool:
        if candidate is None:
            return False
        try:
            encoded = candidate.encode("ascii")
        except UnicodeEncodeError:
            return False
        return secrets.compare_digest(encoded, self.secret)

    def value(self) -> str:
        return self.secret.decode("ascii")


class RuntimeConfigurationError(ValueError):
    """The D3 runtime was configured outside its narrow security contract."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class JourneyRuntimeConfig:
    bootstrap: WorkspaceBootstrapSpec
    actor: ActorRef
    resources: tuple[FrozenResourceDescriptor, ...]
    now: Callable[[], str] = _utc_now
    new_id: Callable[[], UUID] = uuid4
    export_selections: ExportSelectionRegistry | None = None


@dataclass(frozen=True, slots=True)
class _StaticAsset:
    content: bytes
    media_type: str


@dataclass(frozen=True, slots=True)
class _StaticBuild:
    index: _StaticAsset
    assets: tuple[tuple[str, _StaticAsset], ...]


_STATIC_ROUTE = re.compile(r"assets/[A-Za-z0-9._/-]+\Z")


def _path_is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    return (
        path.is_symlink()
        or bool(reparse_flag and attributes & reparse_flag)
        or getattr(os.path, "isjunction", lambda _candidate: False)(path)
    )


def _stable_regular_bytes(path: Path) -> bytes:
    before = path.lstat()
    if _path_is_link_or_reparse(path) or not stat.S_ISREG(before.st_mode):
        raise RuntimeConfigurationError("web build entry must be a regular file")
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise RuntimeConfigurationError("web build entry could not be read") from exc
    after = path.lstat()
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if identity_before != identity_after or _path_is_link_or_reparse(path):
        raise RuntimeConfigurationError("web build entry changed during validation")
    return content


def _validated_static_build(build_root: str | Path) -> _StaticBuild:
    supplied_root = Path(build_root).absolute()
    if _path_is_link_or_reparse(supplied_root):
        raise RuntimeConfigurationError("web build root must not be a link or reparse point")
    root = supplied_root.resolve(strict=True)
    if not root.is_dir() or _path_is_link_or_reparse(root):
        raise RuntimeConfigurationError("web build root must be a regular directory")
    manifest_path = root / ".vite" / "manifest.json"
    index_path = root / "index.html"
    if _path_is_link_or_reparse(root / ".vite"):
        raise RuntimeConfigurationError("web build metadata directory must not be a reparse point")
    if not manifest_path.is_file() or not index_path.is_file():
        raise RuntimeConfigurationError("web build requires regular index and Vite manifest files")
    try:
        manifest = json.loads(_stable_regular_bytes(manifest_path).decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeConfigurationError("web build manifest is invalid") from exc
    if not isinstance(manifest, dict) or not manifest:
        raise RuntimeConfigurationError("web build manifest must be a non-empty object")
    declared: list[str] = []
    for entry in manifest.values():
        if not isinstance(entry, dict):
            raise RuntimeConfigurationError("web build manifest entry is invalid")
        for field_name in ("file", "css", "assets"):
            raw = entry.get(field_name, [] if field_name != "file" else None)
            values = [raw] if isinstance(raw, str) else raw
            if raw is None and field_name == "file":
                raise RuntimeConfigurationError("web build manifest entry has no file")
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                raise RuntimeConfigurationError("web build manifest asset list is invalid")
            declared.extend(values)
    if len(declared) != len(set(declared)):
        raise RuntimeConfigurationError("web build manifest declares an asset more than once")
    assets: list[tuple[str, _StaticAsset]] = []
    for relative in declared:
        pure = PurePosixPath(relative)
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or "\\" in relative
            or pure.as_posix() != relative
            or not relative.startswith("assets/")
            or _STATIC_ROUTE.fullmatch(relative) is None
            or relative.endswith(".map")
        ):
            raise RuntimeConfigurationError("web build manifest contains a forbidden asset path")
        unresolved = root
        for part in pure.parts:
            unresolved /= part
            if _path_is_link_or_reparse(unresolved):
                raise RuntimeConfigurationError("web build asset path contains a reparse point")
        target = unresolved.resolve(strict=True)
        if not target.is_relative_to(root) or not target.is_file():
            raise RuntimeConfigurationError("web build asset is not a regular build-root child")
        media_type = mimetypes.guess_type(relative)[0] or "application/octet-stream"
        assets.append((relative, _StaticAsset(_stable_regular_bytes(target), media_type)))
    disk_assets: set[str] = set()
    for candidate in root.rglob("*"):
        if _path_is_link_or_reparse(candidate):
            raise RuntimeConfigurationError("web build may not contain linked or reparse entries")
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(root).as_posix()
        if relative in {"index.html", ".vite/manifest.json"}:
            continue
        if relative.endswith(".map"):
            raise RuntimeConfigurationError("web build may not contain source maps")
        disk_assets.add(relative)
    if disk_assets != set(declared):
        raise RuntimeConfigurationError("web build manifest and disk assets do not match")
    return _StaticBuild(
        index=_StaticAsset(_stable_regular_bytes(index_path), "text/html"),
        assets=tuple(sorted(assets)),
    )


def _static_headers(*, index: bool) -> dict[str, str]:
    headers = {
        "Cache-Control": "no-store" if index else "public, max-age=31536000, immutable",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
    }
    if index:
        headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'"
        )
    return headers


@dataclass(slots=True)
class _LockedRunSignals:
    cancel: threading.Event = field(default_factory=threading.Event)
    pause: threading.Event = field(default_factory=threading.Event)

    def __call__(self) -> bool:
        return self.cancel.is_set()

    def pause_requested(self) -> bool:
        return self.pause.is_set()


@dataclass(slots=True)
class _RuntimeControl:
    workspace: WorkspaceRuntime
    journey: JourneyRuntimeConfig | None = None
    state: str = "starting"
    drain_event: asyncio.Event = field(default_factory=asyncio.Event)
    streams: set[asyncio.Task[object]] = field(default_factory=set)
    streams_empty: asyncio.Event = field(default_factory=asyncio.Event)
    writers: set[asyncio.Task[object]] = field(default_factory=set)
    writers_empty: asyncio.Event = field(default_factory=asyncio.Event)
    locked_tasks: set[asyncio.Task[object]] = field(default_factory=set)
    locked_cancellations: dict[str, threading.Event] = field(default_factory=dict)
    locked_pauses: dict[str, threading.Event] = field(default_factory=dict)
    drain_timeout_seconds: float = 1.0
    writer_executor: ThreadPoolExecutor = field(init=False)
    locked_worker_executor: ThreadPoolExecutor = field(init=False)
    _prestarted: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        self.streams_empty.set()
        self.writers_empty.set()
        self.writer_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="nana-workspace-writer",
        )
        self.locked_worker_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="nana-locked-worker",
        )
        self._prestarted = self.workspace.state == "ready"
        if self.workspace.state == "ready":
            self.state = "ready"

    async def _run_on_writer(self, function: Callable[[], Any]) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.writer_executor, function)

    async def start(self) -> None:
        if self.workspace.state == "ready":
            if self.journey is not None:
                self.state = "failed"
                self.writer_executor.shutdown(wait=True)
                raise RuntimeConfigurationError(
                    "journey mutations require Workspace start on the owner lane"
                )
            self.state = "ready"
            return
        self.state = "starting"
        try:
            await self._run_on_writer(self.workspace.start)
            if self.journey is not None:
                def bootstrap() -> int:
                    connection = self.workspace.connection
                    if connection is None:
                        raise RuntimeError("Workspace connection is unavailable")
                    return WorkspaceBootstrapService(connection).ensure(
                        self.journey.bootstrap
                    )

                await self._run_on_writer(bootstrap)
                def reconcile_stale() -> int:
                    connection = self.workspace.connection
                    if connection is None or self.journey is None:
                        return 0
                    return JourneyCommandService(
                        connection,
                        actor=self.journey.actor,
                        resources=self.journey.resources,
                        now=self.journey.now,
                        new_id=self.journey.new_id,
                    ).reconcile_stale_locked_runs()

                await self._run_on_writer(reconcile_stale)
                if self.journey.export_selections is not None:
                    def reconcile_exports() -> int:
                        connection = self.workspace.connection
                        if connection is None or self.journey is None or self.journey.export_selections is None:
                            return 0
                        return DraftExportService(
                            connection,
                            actor=self.journey.actor,
                            selections=self.journey.export_selections,
                            now=self.journey.now,
                            new_id=self.journey.new_id,
                        ).reconcile_startup()

                    await self._run_on_writer(reconcile_exports)
        except Exception:
            self.state = "failed"
            try:
                if self.workspace.state == "ready":
                    await self._run_on_writer(self.workspace.close)
            finally:
                self.writer_executor.shutdown(wait=True)
                self.locked_worker_executor.shutdown(wait=True)
            raise
        self.state = "ready"

    async def execute_journey(
        self,
        request: JourneyCommandRequest,
    ) -> CommandResult:
        if self.state != "ready" or self.journey is None:
            raise RuntimeError("journey mutation runtime is not ready")
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("journey Command must run in an asyncio task")
        self.writers.add(task)
        self.writers_empty.clear()
        try:
            config = self.journey

            def execute() -> CommandResult:
                connection = self.workspace.connection
                if connection is None:
                    raise RuntimeError("Workspace connection is unavailable")
                pause_event = None
                if request.type in {"PauseRun", "ResumeRun"}:
                    pause_event = self.locked_pauses.get(str(request.run_id))
                    if pause_event is None:
                        raise RuntimeError("active Run control is unavailable")
                result = JourneyCommandService(
                    connection,
                    actor=config.actor,
                    resources=config.resources,
                    now=config.now,
                    new_id=config.new_id,
                    export_selections=config.export_selections,
                ).execute(
                    request,
                    defer_locked_execution=request.type == "StartRun",
                )
                if request.type == "CancelRun":
                    cancel_event = self.locked_cancellations.get(str(request.run_id))
                    if cancel_event is not None:
                        cancel_event.set()
                elif request.type in {"PauseRun", "ResumeRun"}:
                    assert pause_event is not None
                    if request.type == "PauseRun":
                        pause_event.set()
                    else:
                        pause_event.clear()
                return result

            result = await self._run_on_writer(execute)
            if request.type == "StartRun" and result.status.value == "accepted":
                deferred_task = asyncio.create_task(self._run_deferred_locked(request, result))
                self.locked_tasks.add(deferred_task)
                deferred_task.add_done_callback(self.locked_tasks.discard)
            if (
                isinstance(request, DecideApprovalRequest)
                and request.decision == "approved"
                and result.status.value in {"accepted", "replayed"}
            ):
                export_task = asyncio.create_task(
                    self._run_draft_export(str(request.approval_id))
                )
                self.locked_tasks.add(export_task)
                export_task.add_done_callback(self.locked_tasks.discard)
            return result
        finally:
            self.writers.discard(task)
            if not self.writers:
                self.writers_empty.set()

    async def _run_draft_export(self, approval_id: str) -> None:
        if self.journey is None or self.journey.export_selections is None:
            return

        def execute() -> None:
            connection = self.workspace.connection
            if connection is None or self.journey is None or self.journey.export_selections is None:
                return
            DraftExportService(
                connection,
                actor=self.journey.actor,
                selections=self.journey.export_selections,
                now=self.journey.now,
                new_id=self.journey.new_id,
            ).execute_authorized(approval_id)

        await self._run_on_writer(execute)

    async def _run_deferred_locked(
        self,
        request: JourneyCommandRequest,
        result: CommandResult,
    ) -> None:
        """Run the frozen process off-lane and commit facts back on-lane."""
        if self.journey is None:
            return
        command = to_canonical_command(request, actor=self.journey.actor)
        if not isinstance(command, StartRun):
            return
        run_id = next(key.split(":", 1)[1] for key in result.affected_revisions if key.startswith("run:"))
        signals = _LockedRunSignals()
        cancel_event = signals.cancel
        pause_event = signals.pause
        self.locked_cancellations[run_id] = cancel_event
        self.locked_pauses[run_id] = pause_event
        context: dict[str, object] | None = None
        watchdog: asyncio.Task[None] | None = None
        try:
            def prepare() -> dict[str, object]:
                connection = self.workspace.connection
                if connection is None:
                    raise RuntimeError("Workspace connection is unavailable")
                service = JourneyCommandService(
                    connection,
                    actor=self.journey.actor,
                    resources=self.journey.resources,
                    now=self.journey.now,
                    new_id=self.journey.new_id,
                )
                return service.prepare_locked_action(
                    command,
                    result,
                    cancel_requested=cancel_event.is_set,
                )

            context = await self._run_on_writer(prepare)

            async def timeout_watchdog() -> None:
                active_remaining = float(context["timeout_seconds"])
                tick = 0.05
                while active_remaining > 0:
                    if cancel_event.is_set():
                        return
                    await asyncio.sleep(min(tick, active_remaining))
                    if not pause_event.is_set():
                        active_remaining -= min(tick, active_remaining)

                def request_timeout() -> None:
                    connection = self.workspace.connection
                    if connection is None or self.journey is None:
                        return
                    JourneyCommandService(
                        connection,
                        actor=self.journey.actor,
                        resources=self.journey.resources,
                        now=self.journey.now,
                        new_id=self.journey.new_id,
                    ).request_locked_timeout(command, context)

                with contextlib.suppress(Exception):
                    await self._run_on_writer(request_timeout)

            watchdog = asyncio.create_task(timeout_watchdog())
            # The owner lane commits a durable spawn fence.  Cancellation that
            # wins this CAS is settled as pre-spawn cancellation and never
            # reaches the worker executor.
            def commit_fence() -> bool:
                connection = self.workspace.connection
                if connection is None or self.journey is None:
                    return False
                return JourneyCommandService(
                    connection,
                    actor=self.journey.actor,
                    resources=self.journey.resources,
                    now=self.journey.now,
                    new_id=self.journey.new_id,
                ).commit_spawn_fence(context)

            if not await self._run_on_writer(commit_fence):
                cancelled = LockedProcessResult(
                    exit_code=None,
                    stdout=b"",
                    stderr=b"",
                    wall_clock_ms=0,
                    pre_spawn_cancelled=True,
                    actual_effects=EffectScope(),
                )

                def complete_cancelled() -> None:
                    connection = self.workspace.connection
                    if connection is None or self.journey is None:
                        return
                    JourneyCommandService(
                        connection,
                        actor=self.journey.actor,
                        resources=self.journey.resources,
                        now=self.journey.now,
                        new_id=self.journey.new_id,
                    ).complete_locked_action(command, context, cancelled)

                await self._run_on_writer(complete_cancelled)
                return
            loop = asyncio.get_running_loop()
            process = await loop.run_in_executor(
                self.locked_worker_executor,
                lambda: default_locked_unittest_runner(
                    context["test_id"],
                    context["workspace_root"],
                    context["timeout_seconds"],
                    context["max_output_bytes"],
                    signals,
                ),
            )
            # A cooperative/fake runner may return at the pause boundary.  A
            # user-paused Run must remain non-terminal until Resume or Cancel.
            while pause_event.is_set() and not cancel_event.is_set():
                await asyncio.sleep(0.01)

            def complete() -> None:
                connection = self.workspace.connection
                if connection is None:
                    raise RuntimeError("Workspace connection is unavailable")
                JourneyCommandService(
                    connection,
                    actor=self.journey.actor,
                    resources=self.journey.resources,
                    now=self.journey.now,
                    new_id=self.journey.new_id,
                ).complete_locked_action(command, context, process)

            await self._run_on_writer(complete)
        except (LockedExecutorError, RuntimeError) as exc:
            # Reconcile on the owner lane; a failed bridge never synthesizes
            # success or leaves an unexplained proposed Action behind.
            def reconcile() -> None:
                connection = self.workspace.connection
                if connection is None or self.journey is None:
                    return
                service = JourneyCommandService(
                    connection,
                    actor=self.journey.actor,
                    resources=self.journey.resources,
                    now=self.journey.now,
                    new_id=self.journey.new_id,
                )
                service.reconcile_locked_failure(command, result, str(exc))

            with contextlib.suppress(Exception):
                await self._run_on_writer(reconcile)
        finally:
            if watchdog is not None:
                watchdog.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await watchdog
            self.locked_cancellations.pop(run_id, None)
            self.locked_pauses.pop(run_id, None)

    def register_stream(self) -> asyncio.Task[object]:
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("SSE stream must run in an asyncio task")
        self.streams.add(task)
        self.streams_empty.clear()
        return task

    def unregister_stream(self, task: asyncio.Task[object]) -> None:
        self.streams.discard(task)
        if not self.streams:
            self.streams_empty.set()

    async def close(self) -> None:
        self.state = "draining"
        self.drain_event.set()
        # Requests must leave the owner-lane writer set before waiting for a
        # deferred worker, because worker completion itself schedules a short
        # owner-lane transaction.  A writer drain timeout is a lifecycle
        # failure, not a reason to silently proceed with SQLite close.
        await asyncio.wait_for(self.writers_empty.wait(), timeout=self.drain_timeout_seconds)
        for cancel_event in self.locked_cancellations.values():
            cancel_event.set()
        if self.locked_tasks:
            await asyncio.gather(*tuple(self.locked_tasks), return_exceptions=True)
        if self.journey is not None and self.journey.export_selections is not None:
            self.journey.export_selections.close()
        try:
            await asyncio.wait_for(self.streams_empty.wait(), timeout=self.drain_timeout_seconds)
        except asyncio.TimeoutError:
            for task in tuple(self.streams):
                task.cancel()
            if self.streams:
                await asyncio.gather(*tuple(self.streams), return_exceptions=True)
        try:
            if self._prestarted and self.journey is None:
                self.workspace.close()
            else:
                await self._run_on_writer(self.workspace.close)
        except Exception:
            self.state = "close_failed"
            raise
        else:
            self.state = "closed"
            self.writer_executor.shutdown(wait=True)
            self.locked_worker_executor.shutdown(wait=True)


def _response(detail: str, status_code: int) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status_code)


def _one_header(scope: dict[str, Any], name: str) -> str | None:
    values = [
        value.decode("latin-1")
        for key, value in scope["headers"]
        if key.decode("latin-1").lower() == name
    ]
    return values[0] if len(values) == 1 else None


def _header_count(scope: dict[str, Any], name: str) -> int:
    return sum(
        1
        for key, _value in scope["headers"]
        if key.decode("latin-1").lower() == name
    )


def _requested_headers(scope: dict[str, Any]) -> frozenset[str] | None:
    raw = _one_header(scope, "access-control-request-headers")
    if raw is None:
        return frozenset()
    parts = tuple(part.strip().lower() for part in raw.split(","))
    if not all(parts) or len(set(parts)) != len(parts):
        return None
    return frozenset(parts)


class _RuntimeSecurityGate:
    """Apply readiness and exact local-session checks before routing."""

    def __init__(
        self,
        app: Any,
        *,
        session: LocalSession,
        control: _RuntimeControl,
        mutation_enabled: bool,
        bootstrap_enabled: bool,
    ) -> None:
        self.app = app
        self.session = session
        self.control = control
        self.mutation_enabled = mutation_enabled
        self.bootstrap_enabled = bootstrap_enabled

    def _preflight_contract(
        self,
        scope: dict[str, Any],
    ) -> tuple[str, frozenset[str]] | None:
        path = scope["path"]
        requested_method = _one_header(scope, "access-control-request-method")
        if path in _AUTHENTICATED_GET_PATHS and requested_method == "GET":
            return "GET", _PREFLIGHT_HEADERS
        if (
            self.mutation_enabled
            and path == _JOURNEY_COMMAND_PATH
            and requested_method == "POST"
        ):
            return "POST", _MUTATION_PREFLIGHT_HEADERS
        return None

    def _valid_preflight(
        self,
        scope: dict[str, Any],
    ) -> tuple[str, frozenset[str]] | None:
        contract = self._preflight_contract(scope)
        if contract is None:
            return None
        if _header_count(scope, "origin") != 1:
            return None
        if _one_header(scope, "origin") != self.session.origin:
            return None
        if _header_count(scope, "access-control-request-method") != 1:
            return None
        if _header_count(scope, "access-control-request-headers") > 1:
            return None
        requested = _requested_headers(scope)
        method, allowed_headers = contract
        if requested is None or not requested <= allowed_headers:
            return None
        return method, allowed_headers

    async def _bounded_mutation_receive(
        self,
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> Callable[[], Any] | None:
        if _header_count(scope, "content-type") != 1:
            await _response("exactly one Content-Type is required", 415)(scope, receive, send)
            return None
        if _one_header(scope, "content-type") != "application/json":
            await _response("Content-Type must be application/json", 415)(scope, receive, send)
            return None
        if _header_count(scope, "content-encoding"):
            await _response("Content-Encoding is not accepted", 415)(scope, receive, send)
            return None
        if _header_count(scope, "content-length") > 1:
            await _response("duplicate Content-Length is not accepted", 400)(scope, receive, send)
            return None
        declared: int | None = None
        raw_length = _one_header(scope, "content-length")
        if raw_length is not None:
            try:
                declared = int(raw_length)
            except ValueError:
                await _response("Content-Length is invalid", 400)(scope, receive, send)
                return None
            if declared < 0:
                await _response("Content-Length is invalid", 400)(scope, receive, send)
                return None
            if declared > _MAX_JOURNEY_BODY_BYTES:
                await _response("journey Command body is too large", 413)(scope, receive, send)
                return None
        messages: list[dict[str, Any]] = []
        total = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] == "http.disconnect":
                break
            if message["type"] != "http.request":
                continue
            total += len(message.get("body", b""))
            if total > _MAX_JOURNEY_BODY_BYTES:
                await _response("journey Command body is too large", 413)(scope, receive, send)
                return None
            if not message.get("more_body", False):
                break
        if declared is not None and declared != total:
            await _response("Content-Length does not match the body", 400)(scope, receive, send)
            return None

        async def replay() -> dict[str, Any]:
            if messages:
                return messages.pop(0)
            return {"type": "http.request", "body": b"", "more_body": False}

        return replay

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = scope["method"]
        path = scope["path"]
        preflight = self._valid_preflight(scope) if method == "OPTIONS" else None
        if method == "OPTIONS" and preflight is not None:
            allowed_method, allowed_headers = preflight
            response = Response(
                status_code=204,
                headers={
                    "Access-Control-Allow-Origin": self.session.origin,
                    "Access-Control-Allow-Methods": allowed_method,
                    "Access-Control-Allow-Headers": ", ".join(
                        sorted(header.title() for header in allowed_headers)
                    ),
                    "Vary": "Origin, Access-Control-Request-Method, Access-Control-Request-Headers",
                },
            )
            await response(scope, receive, send)
            return
        if path == _PUBLIC_HEALTH_PATH and method == "GET":
            await self.app(scope, receive, send)
            return
        if self.control.state != "ready":
            await _response("runtime not ready", 503)(scope, receive, send)
            return
        if any(_header_count(scope, header) for header in _FORWARDED_HEADERS):
            await _response("forwarded request headers are not accepted", 400)(scope, receive, send)
            return
        if _header_count(scope, "host") != 1 or _one_header(scope, "host") != self.session.authority:
            await _response("request Host is not the active local session authority", 403)(scope, receive, send)
            return
        if self.bootstrap_enabled and method == "GET" and (
            path == "/" or path.startswith("/assets/")
        ):
            await self.app(scope, receive, send)
            return
        if self.bootstrap_enabled and method == "POST" and path in {
            _BOOTSTRAP_EXCHANGE_PATH,
            _SESSION_RESTORE_PATH,
        }:
            csrf_header = (
                ("x-nana-bootstrap", "1")
                if path == _BOOTSTRAP_EXCHANGE_PATH
                else ("x-nana-session-restore", "1")
            )
            if (
                _header_count(scope, "origin") != 1
                or _one_header(scope, "origin") != self.session.origin
                or _header_count(scope, csrf_header[0]) != 1
                or _one_header(scope, csrf_header[0]) != csrf_header[1]
            ):
                await _response("session Origin or CSRF header is invalid", 403)(scope, receive, send)
                return
            bounded_receive = await self._bounded_mutation_receive(scope, receive, send)
            if bounded_receive is None:
                return
            await self.app(scope, bounded_receive, send)
            return
        request = Request(scope)
        try:
            self.session.authorize(
                request.headers,
                allow_same_origin_browser_fetch=(
                    method == "GET" and path in _AUTHENTICATED_GET_PATHS
                ),
            )
        except HTTPException as exc:
            response = _response(str(exc.detail), exc.status_code)
            response.headers.update(exc.headers or {})
            await response(scope, receive, send)
            return
        if (
            self.mutation_enabled
            and method == "POST"
            and path == _JOURNEY_COMMAND_PATH
        ):
            bounded_receive = await self._bounded_mutation_receive(
                scope,
                receive,
                send,
            )
            if bounded_receive is None:
                return
            receive = bounded_receive
        await self.app(scope, receive, send)


async def _stop_aware_events(
    source: AsyncIterator[str],
    stop_event: asyncio.Event,
) -> AsyncIterator[str]:
    """Stop an infinite poller promptly during bounded runtime drain."""

    try:
        async for frame in source:
            if stop_event.is_set():
                return
            yield frame
    finally:
        with contextlib.suppress(RuntimeError):
            await source.aclose()


def _runtime_openapi(app: FastAPI) -> None:
    _install_contract_openapi(app)
    original_openapi = app.openapi

    def openapi() -> dict[str, Any]:
        schema = original_openapi()
        components = schema.setdefault("components", {})
        schemes = components.setdefault("securitySchemes", {})
        schemes["LocalSessionBearer"] = {"type": "http", "scheme": "bearer"}
        components.setdefault("schemas", {})["HealthResponse"] = HealthResponse.model_json_schema()
        for path, item in schema.get("paths", {}).items():
            if path != _PUBLIC_HEALTH_PATH:
                for method, operation in item.items():
                    if method in {"get", "post", "options"}:
                        operation["security"] = [{"LocalSessionBearer": []}]
        return schema

    app.openapi = openapi


def validate_no_mutation_methods(app: FastAPI) -> None:
    methods = {
        method
        for route in app.routes
        for method in getattr(route, "methods", set())
        if method in _MUTATION_METHODS
    }
    if methods:
        raise RuntimeConfigurationError(
            f"D3-02 runtime forbids mutation methods: {sorted(methods)}"
        )


def validate_runtime_route_inventory(
    app: FastAPI,
    *,
    journey_enabled: bool,
    bootstrap_enabled: bool = False,
) -> None:
    actual = tuple(sorted(
        (str(getattr(route, "path", "")), method)
        for route in app.routes
        for method in getattr(route, "methods", set())
        if method in _MUTATION_METHODS
    ))
    expected = tuple(sorted(
        tuple(
            item
            for item in (
                (_JOURNEY_COMMAND_PATH, "POST") if journey_enabled else None,
                (_BOOTSTRAP_EXCHANGE_PATH, "POST") if bootstrap_enabled else None,
                (_SESSION_RESTORE_PATH, "POST") if bootstrap_enabled else None,
            )
            if item is not None
        )
    ))
    if actual != expected:
        raise RuntimeConfigurationError(
            f"runtime mutation route inventory mismatch: {sorted(actual)}"
        )


def create_runtime_app(
    *,
    workspace_runtime: WorkspaceRuntime,
    local_session: LocalSession,
    web_build_root: str | Path | None = None,
    journey_runtime: JourneyRuntimeConfig | None = None,
    bootstrap_secret: str | None = None,
) -> FastAPI:
    """Build the sole served D3 runtime from one D3-01 Workspace owner."""

    if journey_runtime is not None:
        if workspace_runtime.state != "closed":
            raise RuntimeConfigurationError(
                "journey mutations require a closed Workspace at app creation"
            )
        if (
            journey_runtime.actor.kind.value != "user"
            or journey_runtime.actor.id is None
        ):
            raise RuntimeConfigurationError(
                "journey runtime actor must be a stable user principal"
            )
    bootstrap_exchange = (
        _OneTimeBootstrap.from_value(bootstrap_secret)
        if bootstrap_secret is not None
        else None
    )
    session_recovery = (
        _SessionRecovery.create() if bootstrap_exchange is not None else None
    )
    if bootstrap_exchange is not None and web_build_root is None:
        raise RuntimeConfigurationError("browser bootstrap requires a validated web build")
    control = _RuntimeControl(workspace=workspace_runtime, journey=journey_runtime)
    event_stream = SQLiteEventStream(str(workspace_runtime.database_path))
    read_model = BootstrapReadModel(
        workspace_runtime.database_path,
        token_secret=local_session.token.get_secret_value(),
    )
    static_build = _validated_static_build(web_build_root) if web_build_root is not None else None

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await control.start()
        try:
            yield
        finally:
            await control.close()

    app = FastAPI(
        title="Nana Sidecar Runtime",
        version="0.3.0-dev",
        docs_url=None,
        redoc_url=None,
        redirect_slashes=False,
        lifespan=lifespan,
    )
    app.add_middleware(
        _RuntimeSecurityGate,
        session=local_session,
        control=control,
        mutation_enabled=journey_runtime is not None,
        bootstrap_enabled=bootstrap_exchange is not None,
    )
    app.state.runtime_control = control
    app.state.workspace_runtime = workspace_runtime
    app.state.static_build = static_build

    if static_build is not None:
        @app.get("/", include_in_schema=False)
        def web_index() -> Response:
            return Response(
                static_build.index.content,
                media_type=static_build.index.media_type,
                headers=_static_headers(index=True),
            )

        def asset_endpoint(asset: _StaticAsset) -> Any:
            def serve_asset() -> Response:
                return Response(
                    asset.content,
                    media_type=asset.media_type,
                    headers=_static_headers(index=False),
                )

            return serve_asset

        for relative, target in static_build.assets:
            app.add_api_route(
                "/" + relative,
                asset_endpoint(target),
                methods=["GET"],
                include_in_schema=False,
                name="web_asset_" + relative.replace("/", "_").replace(".", "_"),
            )

    if bootstrap_exchange is not None:
        @app.post(_BOOTSTRAP_EXCHANGE_PATH, include_in_schema=False)
        def exchange_session(payload: dict[str, str] = Body(...)) -> Response:
            if set(payload) != {"bootstrap_secret"}:
                return JSONResponse({"detail": "invalid bootstrap request"}, status_code=400)
            candidate = payload.get("bootstrap_secret")
            if not isinstance(candidate, str) or not bootstrap_exchange.consume(candidate):
                return JSONResponse({"detail": "bootstrap secret rejected"}, status_code=401)
            response = JSONResponse(
                {"authorization": "Bearer " + local_session.token.get_secret_value()},
                headers={"Cache-Control": "no-store"},
            )
            assert session_recovery is not None
            response.set_cookie(
                _SESSION_RECOVERY_COOKIE,
                session_recovery.value(),
                httponly=True,
                samesite="strict",
                secure=False,
                path="/",
            )
            return response

        @app.post(_SESSION_RESTORE_PATH, include_in_schema=False)
        def restore_session(
            request: Request,
            payload: dict[str, object] = Body(...),
        ) -> Response:
            if payload:
                return JSONResponse(
                    {"detail": "invalid restore request"}, status_code=400
                )
            assert session_recovery is not None
            if not session_recovery.matches(
                request.cookies.get(_SESSION_RECOVERY_COOKIE)
            ):
                return JSONResponse(
                    {"detail": "session recovery rejected"}, status_code=401
                )
            return JSONResponse(
                {"authorization": "Bearer " + local_session.token.get_secret_value()},
                headers={"Cache-Control": "no-store"},
            )

    @app.get(_PUBLIC_HEALTH_PATH, tags=["system"])
    def health() -> Response:
        return JSONResponse({"status": control.state}, status_code=200 if control.state == "ready" else 503)

    if journey_runtime is not None:
        @app.get(
            "/api/v1/handshake",
            response_model=RuntimeHandshakeResponse,
            tags=["system"],
        )
        def handshake() -> RuntimeHandshakeResponse:
            export_selections = (
                journey_runtime.export_selections.summaries()
                if journey_runtime.export_selections is not None
                else ()
            )
            return RuntimeHandshakeResponse(
                app_version="0.3.0-dev",
                api_version="1",
                schema_version=SCHEMA_VERSION,
                schema_read_ceiling=SCHEMA_READ_CEILING,
                enabled_mutations=tuple(sorted(
                    JOURNEY_COMMAND_NAMES
                    if journey_runtime.export_selections is not None
                    else JOURNEY_COMMAND_NAMES - {"RequestApproval", "DecideApproval"}
                )),
                execution_enabled=True,
                external_effects_enabled=bool(export_selections),
                export_selections=tuple(
                    ExportSelectionInfo(
                        selection_id=item.selection_id,
                        label=item.label,
                        expires_at=item.expires_at,
                        provenance=item.provenance,
                    )
                    for item in export_selections
                ),
            )
    else:
        @app.get(
            "/api/v1/handshake",
            response_model=HandshakeResponse,
            tags=["system"],
        )
        def handshake() -> HandshakeResponse:
            return HandshakeResponse(
                app_version="0.3.0-dev",
                api_version="1",
                schema_version=SCHEMA_VERSION,
                schema_read_ceiling=SCHEMA_READ_CEILING,
            )

    if journey_runtime is not None:
        @app.exception_handler(RequestValidationError)
        async def journey_validation_error(
            request: Request,
            exc: RequestValidationError,
        ) -> JSONResponse:
            if request.url.path != _JOURNEY_COMMAND_PATH:
                return JSONResponse({"detail": "request validation failed"}, status_code=422)
            issues = [
                {
                    "location": [str(part) for part in issue.get("loc", ())],
                    "type": str(issue.get("type", "validation_error")),
                }
                for issue in exc.errors()
            ]
            error = ErrorResponse(
                error=StructuredError(
                    code=ErrorCode.VALIDATION,
                    category=ErrorCategory.INPUT,
                    message="journey Command validation failed",
                    retryable=False,
                    details={"issues": issues},
                    data_safe=True,
                    suggested_actions=("Correct the typed request and use a new command_id.",),
                )
            )
            return JSONResponse(error.model_dump(mode="json"), status_code=422)

        @app.post(
            _JOURNEY_COMMAND_PATH,
            response_model=CommandResult,
            responses={
                409: {"model": ErrorResponse},
                422: {"model": ErrorResponse},
                500: {"model": ErrorResponse},
            },
            tags=["journey"],
        )
        async def journey_command(
            command: JourneyCommandRequest,
        ) -> CommandResult | JSONResponse:
            try:
                return await control.execute_journey(command)
            except CommandExecutionError as exc:
                status_code = (
                    409
                    if exc.error.category is ErrorCategory.CONFLICT
                    else 422
                )
                return JSONResponse(
                    ErrorResponse(error=exc.error).model_dump(mode="json"),
                    status_code=status_code,
                )
            except Exception:
                error = ErrorResponse(
                    error=StructuredError(
                        code=ErrorCode.INTERNAL,
                        category=ErrorCategory.INTERNAL,
                        message="journey Command failed closed",
                        retryable=False,
                        details={},
                        data_safe=True,
                        suggested_actions=("Inspect the local runtime evidence before retrying.",),
                    )
                )
                return JSONResponse(error.model_dump(mode="json"), status_code=500)

    @app.get("/api/v1/contracts", response_model=ContractCatalogInfo, tags=["system"])
    def contract_catalog() -> ContractCatalogInfo:
        schema = _catalog_schema()
        return ContractCatalogInfo(
            schema_hash=_schema_hash(schema),
            schema_names=tuple(sorted(schema.get("$defs", {}))),
            command_names=tuple(sorted(DEV_COMMAND_NAMES)),
            event_types=tuple(sorted(item.value for item in EventType)),
            locator_kinds=tuple(sorted(LOCATOR_KINDS)),
            relation_types=tuple(sorted(item.value for item in RelationType)),
        )

    @app.get("/api/v1/bootstrap", tags=["projection"])
    async def bootstrap(
        section: str | None = None,
        page_token: str | None = None,
        limit: int = 100,
    ) -> JSONResponse:
        if section is not None or page_token is not None:
            if section is None or page_token is None:
                raise HTTPException(status_code=400, detail={"code": "E_PAGE_TOKEN"})
            try:
                page = await asyncio.to_thread(
                    read_model.page, section=section, token=page_token, limit=limit
                )
            except PageTooLargeError as exc:
                raise HTTPException(
                    status_code=413,
                    detail={"code": "E_SECTION_PAGE_TOO_LARGE", "section": exc.section},
                ) from None
            except ValueError as exc:
                raise HTTPException(status_code=400, detail={"code": str(exc)}) from None
            return JSONResponse(page)
        try:
            snapshot = await asyncio.to_thread(read_model.snapshot)
        except SnapshotTooLargeError as exc:
            raise HTTPException(
                status_code=413,
                detail={
                    "code": "E_SNAPSHOT_TOO_LARGE",
                    "sections": exc.sections,
                    "page_tokens": exc.page_tokens,
                },
            ) from None
        return JSONResponse(snapshot)

    @app.get("/api/v1/events", response_class=StreamingResponse, tags=["events"])
    async def events(
        request: Request,
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ) -> StreamingResponse:
        if len(request.headers.getlist("last-event-id")) > 1:
            raise HTTPException(status_code=400, detail="Last-Event-ID must not be repeated")
        cursor = parse_last_event_id(last_event_id)

        async def stream() -> AsyncIterator[str]:
            task = control.register_stream()
            try:
                async for frame in _stop_aware_events(
                    event_stream.iter_sse(
                        after_id=cursor,
                        stop_event=control.drain_event,
                    ),
                    control.drain_event,
                ):
                    yield frame
            finally:
                control.unregister_stream(task)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
        )

    _runtime_openapi(app)
    validate_runtime_route_inventory(
        app,
        journey_enabled=journey_runtime is not None,
        bootstrap_enabled=bootstrap_exchange is not None,
    )
    return app
