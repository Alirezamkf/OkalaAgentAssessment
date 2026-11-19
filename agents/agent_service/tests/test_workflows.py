import json
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_provider
from app.config import Settings
from app.provider import OpenAICompatibleProvider, ProviderUnavailable
from okala_ai.contract import EventRequest, Event, EventType, ReportRequest, Category, approved_phrasings, UNAVAILABLE, NO_EVENTS


class MockProvider:
    def __init__(self, outcome=0):
        self.outcome = outcome
        self.calls = []

    async def choose(self, choices):
        self.calls.append(choices)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AGENT_INTERNAL_SECRET", "test-internal-secret")
    provider = MockProvider()
    app.dependency_overrides[get_provider] = lambda: provider
    with TestClient(app) as client:
        yield client, provider
    app.dependency_overrides.clear()


def event_payload():
    return {"events": [{"event_type": "TabHidden", "timestamp": "2026-11-19T10:00:00Z"}]}


@pytest.mark.parametrize("endpoint,payload", [("event-summary", event_payload()), ("report-explanation", {"category": "incomplete_recordings", "matching_attempts": 2})])
def test_internal_auth(client, endpoint, payload):
    http, provider = client
    assert http.post(f"/internal/{endpoint}", json=payload).status_code == 401
    assert http.post(f"/internal/{endpoint}", headers={"X-Agent-Secret": "wrong"}, json=payload).status_code == 401
    assert not provider.calls


@pytest.mark.parametrize("event_type", list(EventType))
def test_all_events_grounded(client, event_type):
    http, provider = client
    request = EventRequest(events=[Event(event_type=event_type, timestamp=datetime(2026, 11, 19, tzinfo=timezone.utc))])
    response = http.post("/internal/event-summary", json=request.model_dump(mode="json"), headers={"X-Agent-Secret": "test-internal-secret"})
    assert response.json() == {"status": "available", "text": approved_phrasings(request)[0]}
    assert len(provider.calls) == 1


def test_empty_no_provider(client):
    http, provider = client
    response = http.post("/internal/event-summary", json={"events": []}, headers={"X-Agent-Secret": "test-internal-secret"})
    assert response.json() == {"status": "empty", "text": NO_EVENTS}
    assert not provider.calls


@pytest.mark.parametrize("outcome", [ProviderUnavailable(), TimeoutError(), 500, -1, "invented", True])
def test_bad_provider_is_unavailable(client, outcome):
    http, _ = client
    app.dependency_overrides[get_provider] = lambda: MockProvider(outcome)
    response = http.post("/internal/event-summary", json=event_payload(), headers={"X-Agent-Secret": "test-internal-secret"})
    assert response.json() == {"status": "unavailable", "text": UNAVAILABLE}


@pytest.mark.parametrize("field", ["question_text", "candidate_answers", "video", "image", "invitation_token", "password"])
def test_forbidden_payload(client, field):
    http, provider = client
    response = http.post("/internal/event-summary", json={**event_payload(), field: "private"}, headers={"X-Agent-Secret": "test-internal-secret"})
    assert response.status_code == 422
    assert not provider.calls


def test_reject_unsorted_and_naive(client):
    http, provider = client
    payload = event_payload()
    payload["events"].append({"event_type": "Idle", "timestamp": "2026-11-19T09:00:00Z"})
    assert http.post("/internal/event-summary", json=payload, headers={"X-Agent-Secret": "test-internal-secret"}).status_code == 422
    payload = event_payload()
    payload["events"][0]["timestamp"] = "2026-11-19T10:00:00"
    assert http.post("/internal/event-summary", json=payload, headers={"X-Agent-Secret": "test-internal-secret"}).status_code == 422
    assert not provider.calls


def test_reject_event_list_over_limit(client):
    http, provider = client
    event = event_payload()["events"][0]
    response = http.post("/internal/event-summary", json={"events": [event] * 101},
        headers={"X-Agent-Secret": "test-internal-secret"})
    assert response.status_code == 422
    assert not provider.calls


def test_exact_utf8_provider_input_limit_fails_safely(client):
    http, provider = client
    request = EventRequest(events=[Event(event_type="TabHidden",
        timestamp=datetime(2026, 11, 19, tzinfo=timezone.utc)) for _ in range(0)])
    # Build 100 ordered unique timestamps whose Persian approved text exceeds
    # the exact JSON-serialized UTF-8 input bound.
    request.events = [Event(event_type="TabHidden",
        timestamp=datetime(2026, 11, 19, tzinfo=timezone.utc).replace(microsecond=i * 1000))
        for i in range(100)]
    response = http.post("/internal/event-summary", json=request.model_dump(mode="json"),
        headers={"X-Agent-Secret": "test-internal-secret"})
    assert response.json() == {"status": "unavailable", "text": UNAVAILABLE}
    assert not provider.calls


@pytest.mark.parametrize("report_request", [
    ReportRequest(category=Category.STATUS, counts={s: 1 for s in ["Not Started", "In Progress", "Submitted", "Timed Out", "Interrupted", "Cancelled"]}),
    ReportRequest(category=Category.SCORES, scored_attempts=2, average=5, minimum=0, maximum=10),
    ReportRequest(category=Category.EVENTS, highest_count=3, matching_attempts=2),
    ReportRequest(category=Category.RECORDINGS, matching_attempts=2),
])
def test_reports_exact_numbers(client, report_request):
    http, _ = client
    response = http.post("/internal/report-explanation", json=report_request.model_dump(mode="json", exclude_none=True), headers={"X-Agent-Secret": "test-internal-secret"})
    assert response.json()["text"] == approved_phrasings(report_request)[0]


def test_missing_credentials_health_and_unavailable(monkeypatch):
    monkeypatch.setenv("AGENT_INTERNAL_SECRET", "test-internal-secret")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    with TestClient(app) as http:
        assert http.get("/health").json()["status"] == "healthy"
        assert http.post("/internal/event-summary", json=event_payload(), headers={"X-Agent-Secret": "test-internal-secret"}).json()["status"] == "unavailable"


@pytest.mark.parametrize("body", [{}, {"choices": []}, {"choices": [{"message": {"content": '{"choice":99}'}}]}, {"choices": [{"message": {"content": '{"choice":0,"secret":"leak"}'}}]}])
def test_provider_rejects_malformed(monkeypatch, body):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=transport, **kwargs))
    import asyncio
    provider = OpenAICompatibleProvider(Settings(api_key="private-test-key", model="configured-model"))
    with pytest.raises(ProviderUnavailable) as error:
        asyncio.run(provider.choose(["نتیجه گزارش"]))
    assert "private-test-key" not in str(error.value)


def test_provider_contract(monkeypatch):
    captured = []
    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"choice":1}'}}]})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    import asyncio
    assert asyncio.run(OpenAICompatibleProvider(Settings(api_key="test-key", model="configured-model")).choose(["اول", "دوم"])) == 1
    assert captured[0]["messages"][1]["content"] == '["اول", "دوم"]'


def test_invalid_input_is_not_echoed(client):
    http, _ = client
    response = http.post("/internal/event-summary", json={"events": [], "secret": "private-key"}, headers={"X-Agent-Secret": "test-internal-secret"})
    assert response.status_code == 422
    assert "private-key" not in response.text


def test_provider_timeout_is_sanitized(monkeypatch):
    def handler(request): raise httpx.ReadTimeout("private-key")
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    import asyncio
    with pytest.raises(ProviderUnavailable) as error:
        asyncio.run(OpenAICompatibleProvider(Settings(api_key="private-key", model="configured-model")).choose(["اول"]))
    assert "private-key" not in str(error.value)
