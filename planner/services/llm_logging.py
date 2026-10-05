"""logged_invoke — the single choke point for observable LLM calls.

Replaces bare `llm.invoke(messages)` so every Gemini call leaves a
GenerationLog row: tokens, latency, success/failure, prompt version.
The call behaves identically to invoke() — same return value, exceptions
re-raised — so adopting it is a one-line change per call site, and a
logging problem can never break generation (log failures are swallowed).

Usage:
    from .llm_logging import logged_invoke
    response, log = logged_invoke(self.llm, messages, 'grocery', profile)
    ...
    if fell_back and log:
        log.fallback_used = True
        log.save(update_fields=['fallback_used'])
"""

import logging
import time

logger = logging.getLogger(__name__)

_PROMPT_VERSION = None


def _prompt_version():
    """Cached per process — hashing module sources on every call is waste."""
    global _PROMPT_VERSION
    if _PROMPT_VERSION is None:
        try:
            from ..evals.report import prompt_version
            _PROMPT_VERSION = prompt_version()
        except Exception:
            _PROMPT_VERSION = ''
    return _PROMPT_VERSION


def logged_invoke(llm, messages, service, profile=None):
    """Invoke the LLM and record the call. Returns (response, log_row).

    log_row is None when even logging failed — callers must not depend on
    it existing. On LLM failure the exception is re-raised AFTER the failed
    call is recorded, so error rates are visible in the stats.
    """
    from ..models import GenerationLog

    started = time.monotonic()
    error = ''
    response = None
    try:
        response = llm.invoke(messages)
        return response, _write_log(llm, service, profile, started, response, error)
    except Exception as e:
        error = str(e)[:300]
        _write_log(llm, service, profile, started, response, error)
        raise


def _write_log(llm, service, profile, started, response, error):
    from ..models import GenerationLog

    try:
        usage = getattr(response, 'usage_metadata', None) or {}
        return GenerationLog.objects.create(
            profile=profile,
            service=service,
            model_name=getattr(llm, 'model', '') or '',
            prompt_version=_prompt_version(),
            input_tokens=usage.get('input_tokens') or 0,
            output_tokens=usage.get('output_tokens') or 0,
            latency_ms=int((time.monotonic() - started) * 1000),
            ok=not error,
            error=error,
        )
    except Exception:
        # Observability must never take generation down with it.
        logger.exception('GenerationLog write failed')
        return None
