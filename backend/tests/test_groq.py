import asyncio
import json

import httpx
import pytest

from app.extract import groq


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def transport(monkeypatch):
    """Routes Groq calls to a list of canned responses and records the models asked."""
    replies: list[httpx.Response] = []
    asked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(json.loads(request.content)["model"])
        return replies.pop(0)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(groq, "_http", lambda: client)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    return replies, asked


def ok(content: dict) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}, "finish_reason": "stop"}]})


def test_short_rate_limit_is_waited_out(transport):
    replies, asked = transport
    replies += [httpx.Response(429, headers={"retry-after": "0"}), ok({"total": 1})]
    data, model = run(groq.chat_json(groq.VISION_MODELS, [], {"name": "x", "schema": {}}, "u"))
    assert data == {"total": 1}
    assert asked == ["qwen/qwen3.8-27b", "qwen/qwen3.8-27b"]


def test_long_rate_limit_moves_to_next_model(transport):
    replies, asked = transport
    replies += [httpx.Response(429, headers={"retry-after": "300"}), ok({"total": 2})]
    data, model = run(groq.chat_json(groq.TEXT_MODELS, [], {"name": "x", "schema": {}}, "u"))
    assert model == "qwen/qwen3.8-27b"
    assert asked == ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]


def test_all_models_busy_raises_busy(transport):
    replies, _ = transport
    replies += [httpx.Response(429), httpx.Response(429)]
    with pytest.raises(groq.AIUnavailable) as error:
        run(groq.chat_json(groq.TEXT_MODELS, [], {"name": "x", "schema": {}}, "u"))
    assert error.value.busy


def test_cut_off_reply_falls_back(transport):
    replies, asked = transport
    cut = httpx.Response(200, json={"choices": [{"message": {"content": '{"tot'}, "finish_reason": "length"}]})
    replies += [cut, ok({"total": 3})]
    data, _ = run(groq.chat_json(groq.TEXT_MODELS, [], {"name": "x", "schema": {}}, "u"))
    assert data == {"total": 3}


def test_bad_key_stops_immediately(transport):
    replies, asked = transport
    replies += [httpx.Response(401)]
    with pytest.raises(groq.AIUnavailable):
        run(groq.chat_json(groq.TEXT_MODELS, [], {"name": "x", "schema": {}}, "u"))
    assert asked == ["openai/gpt-oss-120b"]
