"""Groq's OpenAI-compatible chat API, with a fallback model when one is busy, retired or unusable.

Model ids as listed by Groq's /models endpoint on 2026-11-25. qwen/qwen3.8-27b is a preview model
(it reads images); Groq may retire it at short notice, which then fails over like a 404.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger("facturelens.groq")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT_S = 45.0


@dataclass(frozen=True)
class Model:
    id: str
    max_tokens: int
    reasoning_effort: str | None = None
    hide_reasoning: bool = False


# Free-tier limits are per model and per minute (8,000 tokens a minute for the Qwen model as of
# 2026-11-25), so output caps stay close to what an invoice needs.
TEXT_MODELS = [
    Model("openai/gpt-oss-120b", 4000, reasoning_effort="low", hide_reasoning=True),
    Model("qwen/qwen3.8-27b", 2500, reasoning_effort="none"),
]
VISION_MODELS = [
    # Groq counts the output cap against the per-minute budget too; real answers use ~250 tokens.
    Model("qwen/qwen3.8-27b", 1500, reasoning_effort="none"),
]

# Wait for a rate limit to reset if Groq says it will within this many seconds. A visitor would
# rather wait half a minute than get an error.
MAX_WAIT_S = 45


class AIUnavailable(Exception):
    """No model gave a usable answer: no key, rate limited, or every model failed."""

    def __init__(self, reason: str, busy: bool = False):
        super().__init__(reason)
        self.busy = busy


_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        # Groq's firewall rejects some default client names, so send our own.
        _client = httpx.AsyncClient(timeout=TIMEOUT_S, headers={"User-Agent": "facturelens/0.1"})
    return _client


def _body(model: Model, messages: list[dict], schema: dict, user: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model.id,
        "messages": messages,
        "temperature": 0.1,
        "max_completion_tokens": model.max_tokens,
        "stream": False,
        "user": user,
        "response_format": {"type": "json_schema", "json_schema": {**schema, "strict": True}},
    }
    if model.reasoning_effort:
        body["reasoning_effort"] = model.reasoning_effort
    if model.hide_reasoning:
        body["include_reasoning"] = False
    return body


async def chat_json(models: list[Model], messages: list[dict], schema: dict, user: str) -> tuple[dict, str]:
    """Returns (parsed JSON, model id). Tries each model in turn; raises AIUnavailable."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise AIUnavailable("GROQ_API_KEY is not set")

    busy = False
    for model in models:
        try:
            response = await _post(key, model, messages, schema, user)
        except httpx.HTTPError as error:
            log.warning("groq %s: no response (%s)", model.id, type(error).__name__)
            continue

        if response.status_code == 200:
            choice = (response.json().get("choices") or [{}])[0]
            content = (choice.get("message") or {}).get("content")
            if choice.get("finish_reason") == "length" or not isinstance(content, str):
                log.warning("groq %s: reply cut off or empty", model.id)
                continue
            try:
                return json.loads(content), model.id
            except json.JSONDecodeError:
                log.warning("groq %s: reply is not valid JSON", model.id)
                continue

        log.warning("groq %s: HTTP %s %s", model.id, response.status_code, response.headers.get("x-request-id", ""))
        if response.status_code == 429:
            busy = True
            continue
        if response.status_code in (404, 410) or response.status_code >= 500:
            continue
        if response.status_code == 400 and _model_gone(response):
            continue
        # 401, 403, 413 and other 400s: the key or the request is wrong; another model won't help.
        raise AIUnavailable(f"Groq refused the request (HTTP {response.status_code})")

    raise AIUnavailable("every model is busy" if busy else "no model gave a usable answer", busy=busy)


async def _post(key: str, model: Model, messages: list[dict], schema: dict, user: str) -> httpx.Response:
    """One request; if rate limited and Groq says the limit resets soon, waits and tries once more."""
    for attempt in range(2):
        response = await _http().post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}"},
            json=_body(model, messages, schema, user),
        )
        if response.status_code != 429 or attempt:
            break
        wait = _retry_after(response)
        log.info("groq %s: rate limited (retry-after %s)", model.id, wait)
        if wait is None or wait > MAX_WAIT_S:
            break
        await asyncio.sleep(wait + 0.5)
    if response.status_code == 200:
        usage = response.json().get("usage") or {}
        log.info("groq %s: %s prompt + %s completion tokens", model.id, usage.get("prompt_tokens"), usage.get("completion_tokens"))
    return response


def _retry_after(response: httpx.Response) -> float | None:
    try:
        return float(response.headers.get("retry-after", ""))
    except ValueError:
        return None


def _model_gone(response: httpx.Response) -> bool:
    try:
        code = response.json().get("error", {}).get("code")
    except ValueError:
        return False
    return code in ("model_decommissioned", "model_not_found")
