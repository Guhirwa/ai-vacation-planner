"""
observability.py

Request-level observability for the API, plus a shared way to log and trace
every LLM call consistently.

Adds a request ID to every request (propagated through log records and
returned in the X-Request-ID response header), logs latency and user ID for
every request, and gives every LLM call site (agent, fallback LLM service,
speech service) one helper to log latency, model, token usage, and
success/failure the same way, instead of each site doing its own thing.

Datadog tracing itself is enabled by running the app with ddtrace-run and
setting DD_TRACE_ENABLED=true; this module only adds the application-level
tags on top of whatever span ddtrace already started, and never fails a
request if tracing isn't active.
"""

import logging
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import settings
from app.utils.security import decode_user_id_for_logging

_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_user_id_var: ContextVar[str] = ContextVar("user_id", default="-")

request_logger = logging.getLogger("app.request")
llm_logger = logging.getLogger("app.llm")


class RequestContextFilter(logging.Filter):
    """Injects the current request's ID and user ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get()
        record.user_id = _user_id_var.get()
        return True


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generates a request ID for every request and logs its outcome and latency.

    The ID is available to every log record made while handling the
    request (via RequestContextFilter) and is returned in the
    X-Request-ID response header so a client or support ticket can
    reference the exact request.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request_id_token = _request_id_var.set(request_id)
        user_id_token = _user_id_var.set(_extract_user_id(request))

        start = time.monotonic()
        try:
            response = await call_next(request)
            elapsed_ms = (time.monotonic() - start) * 1000
            request_logger.info(
                "%s %s -> %d (%.1fms)",
                request.method, request.url.path, response.status_code, elapsed_ms,
            )
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            elapsed_ms = (time.monotonic() - start) * 1000
            request_logger.exception(
                "%s %s failed after %.1fms", request.method, request.url.path, elapsed_ms
            )
            raise
        finally:
            _request_id_var.reset(request_id_token)
            _user_id_var.reset(user_id_token)


def _extract_user_id(request: Request) -> str:
    """Best-effort user ID for logging, decoded straight from the bearer token."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return "-"
    decoded = decode_user_id_for_logging(auth_header[7:])
    return decoded if decoded is not None else "-"


@contextmanager
def log_llm_call(call_site: str, model: str):
    """Times an LLM call and logs its latency, model, and outcome consistently.

    Every LLM call site in the codebase (the agent, the fallback LLM
    service, the two speech service calls) wraps its call in this, so
    they all report the same shape of information instead of each one
    logging (or not logging) its own way. Also tags the active Datadog
    span with the same details, when tracing is enabled.

    Args:
        call_site: A short name identifying which code path made the call,
            e.g. "agent.call_llm" or "speech.extract_trip_details".
        model: The model name used for the call.

    Yields:
        A dict the caller should fill in with "input_tokens" and
        "output_tokens" once the call returns, before the block exits.
    """
    usage: dict = {}
    start = time.monotonic()
    try:
        yield usage
    except Exception as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        llm_logger.error(
            "LLM call failed site=%s model=%s latency_ms=%.1f error=%s",
            call_site, model, elapsed_ms, str(e),
        )
        _tag_current_span(call_site, model, elapsed_ms, usage, error=True)
        raise
    else:
        elapsed_ms = (time.monotonic() - start) * 1000
        llm_logger.info(
            "LLM call succeeded site=%s model=%s latency_ms=%.1f input_tokens=%s output_tokens=%s",
            call_site, model, elapsed_ms,
            usage.get("input_tokens", "-"), usage.get("output_tokens", "-"),
        )
        _tag_current_span(call_site, model, elapsed_ms, usage, error=False)


def _tag_current_span(call_site: str, model: str, elapsed_ms: float, usage: dict, error: bool) -> None:
    """Tags the active Datadog span, if tracing is enabled and a span exists.

    Never raises: a tagging failure should never break the actual request.
    """
    if not settings.dd_trace_enabled:
        return
    try:
        import ddtrace

        span = ddtrace.tracer.current_span()
        if span is None:
            return
        span.set_tag("llm.call_site", call_site)
        span.set_tag("llm.model", model)
        span.set_tag("llm.latency_ms", elapsed_ms)
        span.set_tag("llm.error", error)
        if "input_tokens" in usage:
            span.set_tag("llm.input_tokens", usage["input_tokens"])
        if "output_tokens" in usage:
            span.set_tag("llm.output_tokens", usage["output_tokens"])
    except Exception:
        pass
