"""Bound request bodies before parsing or dispatching PDF work."""

import asyncio
from collections import deque
from dataclasses import dataclass
from math import ceil, isfinite
from time import monotonic

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


@dataclass(frozen=True)
class RequestLimits:
    single_body_bytes: int = 16 * 1024
    bulk_body_bytes: int = 5 * 1024 * 1024 + 65536
    body_timeout_seconds: float = 10
    requests_per_window: int = 30
    rate_window_seconds: float = 60
    max_rate_clients: int = 1024

    def __post_init__(self) -> None:
        counts = (self.single_body_bytes, self.bulk_body_bytes, self.requests_per_window, self.max_rate_clients)
        durations = (self.body_timeout_seconds, self.rate_window_seconds)
        if any(type(value) is not int or value < 1 for value in counts):
            raise ValueError("Request limits must be positive integers.")
        if any(not isfinite(value) or value <= 0 for value in durations):
            raise ValueError("Request durations must be positive and finite.")


class SecurityMiddleware:
    paths = {
        "/api/invitations/single",
        "/api/invitations/preview",
        "/api/invitations/bulk/validate",
        "/api/invitations/bulk/generate",
    }

    def __init__(self, app: ASGIApp, limits: RequestLimits) -> None:
        self.app = app
        self.limits = limits
        self.clients: dict[str, deque[float]] = {}
        self.active = False

    async def reject(
        self, scope: Scope, receive: Receive, send: Send, code: int, detail: str,
        retry_after: int | None = None,
    ) -> None:
        headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)
        response = JSONResponse(
            {"detail": detail}, status_code=code,
            headers=headers,
        )
        await response(scope, receive, send)

    def rate_retry_after(self, client: str) -> int | None:
        now = monotonic()
        expired_before = now - self.limits.rate_window_seconds
        for address in tuple(self.clients):
            events = self.clients[address]
            while events and events[0] <= expired_before:
                events.popleft()
            if not events:
                del self.clients[address]
        if client not in self.clients:
            if len(self.clients) >= self.limits.max_rate_clients:
                return max(1, ceil(self.limits.rate_window_seconds))
            self.clients[client] = deque()
        events = self.clients[client]
        if len(events) >= self.limits.requests_per_window:
            return max(1, ceil(events[0] + self.limits.rate_window_seconds - now))
        events.append(now)
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "").rstrip("/")
        protected = scope["method"] == "POST" and path in self.paths
        started = False

        async def secure_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "no-referrer"
                headers["X-Frame-Options"] = "DENY"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                if protected:
                    headers["Cache-Control"] = "no-store"
                if scope["path"] == "/":
                    headers["Content-Security-Policy"] = (
                        "default-src 'self'; script-src 'self'; style-src 'self'; "
                        "img-src 'self' blob: data:; font-src 'self'; connect-src 'self'; "
                        "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
                    )
            await send(message)

        if not protected:
            await self.app(scope, receive, secure_send)
            return

        client = scope.get("client")
        retry = self.rate_retry_after(client[0] if client else "unknown")
        if retry is not None:
            await self.reject(scope, receive, secure_send, 429,
                              "Too many invitation requests. Please wait and try again.", retry)
            return
        if self.active:
            await self.reject(scope, receive, secure_send, 503,
                              "Invitation generation is busy. Please try again shortly.", 1)
            return
        self.active = True
        try:
            await self.bounded_request(scope, receive, secure_send)
        except Exception:
            if started:
                raise
            await self.reject(scope, receive, secure_send, 500,
                              "Unable to process the invitation request. Please try again.")
        finally:
            self.active = False

    async def bounded_request(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope["path"].rstrip("/")
        limit = self.limits.bulk_body_bytes if "/bulk/" in path else self.limits.single_body_bytes
        lengths = [value for key, value in scope["headers"] if key.lower() == b"content-length"]
        if len(lengths) > 1 or (lengths and (not lengths[0].isdigit() or len(lengths[0]) > 20)):
            await self.reject(scope, receive, send, 400, "Invalid Content-Length header.")
            return
        if lengths and any(key.lower() == b"transfer-encoding" for key, value in scope["headers"]):
            await self.reject(scope, receive, send, 400, "Ambiguous request framing is not accepted.")
            return
        encodings = [value.lower() for key, value in scope["headers"] if key.lower() == b"content-encoding"]
        if encodings and encodings != [b"identity"]:
            await self.reject(scope, receive, send, 415, "Encoded request bodies are not supported.")
            return
        declared = int(lengths[0]) if lengths else None
        if declared is not None and declared > limit:
            await self.reject(scope, receive, send, 413, "Request body exceeds the permitted size.")
            return

        body = bytearray()
        deadline = asyncio.get_running_loop().time() + self.limits.body_timeout_seconds
        while True:
            try:
                async with asyncio.timeout_at(deadline):
                    message = await receive()
            except TimeoutError:
                await self.reject(scope, receive, send, 408, "Request body timed out. Please try again.")
                return
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > limit:
                await self.reject(scope, receive, send, 413, "Request body exceeds the permitted size.")
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        if declared is not None and declared != len(body):
            await self.reject(scope, receive, send, 400, "Request body length does not match Content-Length.")
            return

        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)