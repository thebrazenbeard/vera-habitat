"""Normal local model reasoning remains available; only proven budget exhaustion retries."""
import io
import json

import pytest
from vera_habitat import local_room

PROMPT = [{"role": "user", "content": "A fictional visitor asks for one sentence."}]


def use_responses(monkeypatch, responses):
    requests = []

    class ControlledLoopback:
        def open(self, request, timeout):
            payload = json.loads(request.data)
            requests.append((request.full_url, payload, timeout))
            item = responses[len(requests) - 1]
            return io.BytesIO(json.dumps(item).encode("utf-8"))

    monkeypatch.setattr(local_room, "build_opener", lambda _proxy: ControlledLoopback())
    return requests


def test_reasoning_capable_model_visible_reply_is_not_force_disabled(monkeypatch):
    requests = use_responses(monkeypatch, [
        {"message": {"thinking": "synthetic intermediate", "content": "synthetic reasoned reply"},
         "done": True, "done_reason": "stop"}
    ])
    assert local_room.local_ollama("some-local-model:dev", PROMPT) == "synthetic reasoned reply"
    assert len(requests) == 1
    url, payload, timeout = requests[0]
    assert url == "http://127.0.0.1:11434/api/chat"
    assert "think" not in payload  # Provider/model default remains available.
    assert payload["messages"] == PROMPT
    assert payload["stream"] is False


def test_hidden_reasoning_budget_exhaustion_retries_once_without_thinking(monkeypatch):
    requests = use_responses(monkeypatch, [
        {"message": {"thinking": "synthetic reasoning ran out", "content": ""},
         "done": True, "done_reason": "length"},
        {"message": {"content": "visible fallback reply"}, "done": True, "done_reason": "stop"},
    ])
    assert local_room.local_ollama("qwen3.5:0.8b", PROMPT) == "visible fallback reply"
    assert len(requests) == 2
    assert "think" not in requests[0][1]
    assert requests[1][1]["think"] is False
    assert requests[1][1]["messages"] == requests[0][1]["messages"] == PROMPT
    assert requests[1][1]["model"] == requests[0][1]["model"]


@pytest.mark.parametrize("first", [
    {"message": {"thinking": "", "content": ""}, "done": True, "done_reason": "length"},
    {"message": {"thinking": "silent synthetic thought", "content": ""},
     "done": True, "done_reason": "stop"},
    {"message": {"thinking": "synthetic reasoning", "content": ""}, "done": False,
     "done_reason": "length"},
    {"message": {"content": ""}, "done": True, "done_reason": "length"},
])
def test_empty_nonqualifying_response_does_not_retry(monkeypatch, first):
    requests = use_responses(monkeypatch, [first])
    with pytest.raises(ValueError, match="no visible response"):
        local_room.local_ollama("synthetic:dev", PROMPT)
    assert len(requests) == 1


def test_repeated_empty_reply_is_not_unbounded_retry(monkeypatch):
    requests = use_responses(monkeypatch, [
        {"message": {"thinking": "synthetic", "content": ""}, "done": True,
         "done_reason": "length"},
        {"message": {"content": "  "}, "done": True, "done_reason": "stop"},
    ])
    with pytest.raises(ValueError, match="no visible response"):
        local_room.local_ollama("synthetic:dev", PROMPT)
    assert len(requests) == 2
