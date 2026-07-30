"""D1 HTTP runtime composition layered over the frozen D0 app factory."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from nana_sidecar.app import create_app
from nana_sidecar.sse import (
    LocalSession,
    SQLiteEventStream,
    parse_last_event_id,
)


class _LocalSessionMiddleware:
    """Authenticate the session-protected API and SSE with one policy."""

    def __init__(
        self,
        app: Any,
        *,
        local_session: LocalSession,
    ) -> None:
        self.app = app
        self.local_session = local_session

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        if (
            scope["type"] == "http"
            and scope["path"] in {"/api/v1/contracts", "/api/v1/events"}
        ):
            request = Request(scope)
            try:
                self.local_session.authorize(request.headers)
            except HTTPException as exc:
                response = JSONResponse(
                    {"detail": exc.detail},
                    status_code=exc.status_code,
                    headers=exc.headers,
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def create_runtime_app(
    *,
    event_stream: SQLiteEventStream | None = None,
    local_session: LocalSession | None = None,
) -> FastAPI:
    """Compose the authenticated D1 Event stream with the frozen D0 app."""

    if event_stream is None or local_session is None:
        raise ValueError(
            "event_stream and local_session must be configured together"
        )

    app = create_app()
    app.add_middleware(
        _LocalSessionMiddleware,
        local_session=local_session,
    )

    @app.get(
        "/api/v1/events",
        response_class=StreamingResponse,
        tags=["events"],
    )
    async def events(
        request: Request,
        last_event_id: Annotated[
            str | None,
            Header(alias="Last-Event-ID"),
        ] = None,
    ) -> StreamingResponse:
        if len(request.headers.getlist("last-event-id")) > 1:
            raise HTTPException(
                status_code=400,
                detail="Last-Event-ID must not be repeated",
            )
        cursor = parse_last_event_id(last_event_id)
        return StreamingResponse(
            event_stream.iter_sse(after_id=cursor),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    return app
