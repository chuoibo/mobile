"""F37 across HTTP: one authorised trip, one honest model provenance.

These are fake-repository orchestration tests.  They prove the permission and
grounding order seen by FastAPI; they make no claim about SQL.  The live case
belongs to Stage 2.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime, timedelta

import anyio
import pytest
from fastapi.routing import APIRoute

from app.api.deps import get_reeler, get_repository
from app.api.main import create_app
from app.api.reel_gemini import build_reel_prompt, gemini_reel
from app.api.repository import MemoryRecord, OutingRecord, RecapOutingRecord
from app.api.routes.albums import get_reel_limiter
from app.api.search_rate_limit import FixedWindowLimiter

from .conftest import ASGITestClient

NOW = datetime(2030, 8, 30, 12, 0, tzinfo=UTC)
CONTEXT_ID = uuid.UUID("37c00000-fee1-4fee-8fee-0000fee00037")
FOREIGN_CONTEXT_ID = uuid.UUID("37c00000-fee1-4fee-8fee-0000fee00099")
OUTING_ID = uuid.UUID("37d00000-fee1-4fee-8fee-0000fee00037")
FOREIGN_OUTING_ID = uuid.UUID("37d00000-fee1-4fee-8fee-0000fee00099")
MEMBER_ID = uuid.UUID("37e00000-fee1-4fee-8fee-0000fee00001")
SECOND_MEMBER_ID = uuid.UUID("37e00000-fee1-4fee-8fee-0000fee00002")
STRANGER_ID = uuid.UUID("37e00000-fee1-4fee-8fee-0000fee00099")
LOW_HEART_ID = uuid.UUID("37a00000-fee1-4fee-8fee-0000fee00001")
HIGH_HEART_ID = uuid.UUID("37a00000-fee1-4fee-8fee-0000fee00002")
CHECKIN_ID = uuid.UUID("37a00000-fee1-4fee-8fee-0000fee00003")

HEADERS = {"X-Actor-ID": str(MEMBER_ID), "X-Actor-Roles": "member"}


def actor_headers(actor_id: uuid.UUID, *, claimed_context: uuid.UUID | None = None):
    headers = {"X-Actor-ID": str(actor_id), "X-Actor-Roles": "member"}
    if claimed_context is not None:
        headers["X-Actor-Contexts"] = str(claimed_context)
    return headers


def _outing(
    outing_id: uuid.UUID,
    context_id: uuid.UUID,
    *,
    title: str,
) -> RecapOutingRecord:
    return RecapOutingRecord(
        outing=OutingRecord(
            id=outing_id,
            context_id=context_id,
            created_by_id=MEMBER_ID,
            title=title,
            starts_on=date(2030, 8, 27),
            ends_on=date(2030, 8, 29),
            headcount=4,
            budget_per_person_vnd=300_000,
            created_at=NOW - timedelta(days=7),
            stops=(),
        ),
        in_progress=False,
        split_total_vnd=1_200_000,
        expense_count=5,
        memory_count=3,
    )


def _memory(
    memory_id: uuid.UUID,
    context_id: uuid.UUID,
    *,
    kind: str,
    caption: str | None,
    place_name: str | None,
    reaction_count: int,
    comment_count: int,
    created_at: datetime,
) -> MemoryRecord:
    return MemoryRecord(
        id=memory_id,
        context_id=context_id,
        author_id=MEMBER_ID,
        kind=kind,
        image_url=(
            f"/contexts/{context_id}/photos/{memory_id}" if kind == "photo" else None
        ),
        caption=caption,
        place_id="place-by-the-lake" if kind == "checkin" else None,
        place_name=place_name,
        lat=11.9 if kind == "checkin" else None,
        lng=108.4 if kind == "checkin" else None,
        created_at=created_at,
        reaction_count=reaction_count,
        comment_count=comment_count,
    )


OWN_OUTING = _outing(OUTING_ID, CONTEXT_ID, title="Ba ngày trên cao nguyên")
FOREIGN_OUTING = _outing(
    FOREIGN_OUTING_ID,
    FOREIGN_CONTEXT_ID,
    title="FOREIGN TRIP TITLE MUST STAY PRIVATE",
)
OWN_MEMORIES = (
    _memory(
        LOW_HEART_ID,
        CONTEXT_ID,
        kind="photo",
        caption="Bình minh đầu tiên",
        place_name=None,
        reaction_count=1,
        comment_count=2,
        created_at=NOW - timedelta(days=1, hours=2),
    ),
    _memory(
        HIGH_HEART_ID,
        CONTEXT_ID,
        kind="photo",
        caption="Cả nhóm trên đỉnh đồi",
        place_name=None,
        reaction_count=9,
        comment_count=4,
        created_at=NOW - timedelta(days=1, hours=1),
    ),
    _memory(
        CHECKIN_ID,
        CONTEXT_ID,
        kind="checkin",
        caption="Dừng chân ăn trưa",
        place_name="Quán bên hồ",
        reaction_count=3,
        comment_count=1,
        created_at=NOW - timedelta(days=1),
    ),
)

DEFAULT_RAW = {
    "title": "Ba khoảnh khắc còn ở lại",
    "picks": [
        {
            "memory_id": str(LOW_HEART_ID),
            "note": "Buổi sáng mà cả nhóm vẫn nhắc lại",
            "image_url": "https://model.invalid/fabricated.jpg",
            "caption": "Caption invented by the model",
            "reaction_count": 999,
        },
        {
            "memory_id": str(CHECKIN_ID),
            "note": "Một quãng nghỉ nhỏ thành chuyện vui nhất chuyến",
        },
    ],
    "cta": "A field no client asked for",
}


class StubReelRepository:
    """Two groups in storage, with calls recorded to prove lookup order."""

    def __init__(self) -> None:
        self.members = {
            (CONTEXT_ID, MEMBER_ID),
            (CONTEXT_ID, SECOND_MEMBER_ID),
        }
        self.recaps = {
            CONTEXT_ID: [OWN_OUTING],
            FOREIGN_CONTEXT_ID: [FOREIGN_OUTING],
        }
        self.memories = {
            OUTING_ID: OWN_MEMORIES,
            FOREIGN_OUTING_ID: (
                _memory(
                    uuid.UUID("37a00000-fee1-4fee-8fee-0000fee00099"),
                    FOREIGN_CONTEXT_ID,
                    kind="photo",
                    caption="FOREIGN CAPTION MUST STAY PRIVATE",
                    place_name=None,
                    reaction_count=99,
                    comment_count=99,
                    created_at=NOW,
                ),
            ),
        }
        self.calls: list[tuple] = []

    def is_member(self, context_id, person_id):
        self.calls.append(("is_member", context_id, person_id))
        return (context_id, person_id) in self.members

    def group_recap(self, context_id, *, today):
        self.calls.append(("group_recap", context_id, today))
        return list(self.recaps.get(context_id, ()))

    def list_outing_memories(self, outing_id, *, limit, viewer_id):
        self.calls.append(("list_outing_memories", outing_id, limit, viewer_id))
        return tuple(self.memories.get(outing_id, ()))[:limit]


class RecordingReeler:
    """A raw backend whose inputs and call count remain visible to tests."""

    def __init__(self, raw=DEFAULT_RAW, *, error: Exception | None = None) -> None:
        self.raw = raw
        self.error = error
        self.calls: list[tuple[dict, list[dict]]] = []

    def __call__(self, trip, memories):
        self.calls.append((trip, memories))
        if self.error is not None:
            raise self.error
        return self.raw


@pytest.fixture
def reel_repository():
    return StubReelRepository()


@pytest.fixture
def reeler():
    return RecordingReeler()


def build_reel_client(monkeypatch, repository, backend) -> ASGITestClient:
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    app = create_app()
    # Rate-limit wiring is tested test-first in its own file.  Core route tests
    # install a local window so their first red is about the missing F37 route,
    # not about the later create_app change.
    limiter = FixedWindowLimiter(
        limit=100,
        window_seconds=60,
        code="reel_rate_limited",
        message="Quá nhiều lượt dựng thước phim.",
    )
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_reeler] = lambda: backend
    app.dependency_overrides[get_reel_limiter] = lambda: limiter
    return ASGITestClient(app)


@pytest.fixture
def reel_client(monkeypatch, reel_repository, reeler):
    return build_reel_client(monkeypatch, reel_repository, reeler)


def reel_path(
    *, context_id: uuid.UUID = CONTEXT_ID, outing_id: uuid.UUID = OUTING_ID
) -> str:
    return f"/contexts/{context_id}/albums/{outing_id}/reel"


def read_reel(client, *, headers=HEADERS, **ids):
    return client.get(reel_path(**ids), headers=headers)


def silent_body(reason: str, *, considered_count: int) -> dict:
    return {
        "context_id": str(CONTEXT_ID),
        "outing_id": str(OUTING_ID),
        "reeled": False,
        "reason": reason,
        "source": "none",
        "title": None,
        "picks": [],
        "considered_count": considered_count,
    }


def test_a_member_gets_grounded_picks_and_server_computed_considered_count(
    reel_client, reeler
):
    response = read_reel(reel_client)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["reeled"] is True
    assert body["reason"] == "ok"
    assert body["source"] == "ai"
    assert body["title"] == DEFAULT_RAW["title"]
    assert body["considered_count"] == len(OWN_MEMORIES)
    assert [pick["memory_id"] for pick in body["picks"]] == [
        str(LOW_HEART_ID),
        str(CHECKIN_ID),
    ]
    assert body["picks"][0] == {
        "memory_id": str(LOW_HEART_ID),
        "image_url": f"/contexts/{CONTEXT_ID}/photos/{LOW_HEART_ID}",
        "caption": "Bình minh đầu tiên",
        "place_name": None,
        "created_at": (NOW - timedelta(days=1, hours=2))
        .isoformat()
        .replace("+00:00", "Z"),
        "reaction_count": 1,
        "comment_count": 2,
        "note": "Buổi sáng mà cả nhóm vẫn nhắc lại",
    }
    assert body["picks"][1]["image_url"] is None


def test_the_backend_sees_only_the_contract_metadata_and_never_an_image_url(
    reel_client, reeler
):
    assert read_reel(reel_client).status_code == 200

    assert len(reeler.calls) == 1
    trip, memories = reeler.calls[0]
    assert trip == {
        "title": "Ba ngày trên cao nguyên",
        "starts_on": "2030-08-27",
        "ends_on": "2030-08-29",
        "headcount": 4,
    }
    assert len(memories) == len(OWN_MEMORIES)
    assert all(
        set(memory)
        == {
            "id",
            "kind",
            "caption",
            "place_name",
            "created_at",
            "reaction_count",
            "comment_count",
        }
        for memory in memories
    )
    assert all("image_url" not in memory for memory in memories)
    assert memories[0]["id"] == str(LOW_HEART_ID)
    assert memories[0]["created_at"] == (NOW - timedelta(days=1, hours=2)).isoformat()


def test_the_ai_reel_does_not_replace_the_groups_heart_highlights(reel_client):
    reel = read_reel(reel_client).json()
    album = reel_client.get(
        f"/contexts/{CONTEXT_ID}/albums/{OUTING_ID}", headers=HEADERS
    )

    assert album.status_code == 200, album.text
    assert reel["picks"][0]["memory_id"] == str(LOW_HEART_ID)
    assert album.json()["highlights"][0]["memory_id"] == str(HIGH_HEART_ID)


def test_a_trip_with_no_memories_has_the_tidy_empty_state(
    reel_client, reel_repository, reeler
):
    reel_repository.memories[OUTING_ID] = ()

    response = read_reel(reel_client)

    assert response.status_code == 200, response.text
    assert response.json() == silent_body("no_memories", considered_count=0)
    assert reeler.calls == []


@pytest.mark.parametrize("raw", [None, {"title": "x", "picks": []}])
def test_unavailable_and_ungrounded_are_distinct_honest_empty_answers(
    monkeypatch, reel_repository, raw
):
    backend = RecordingReeler(raw)
    client = build_reel_client(monkeypatch, reel_repository, backend)

    response = read_reel(client)

    expected = "unavailable" if raw is None else "ungrounded"
    assert response.status_code == 200, response.text
    assert response.json() == silent_body(expected, considered_count=len(OWN_MEMORIES))


def test_a_backend_exception_logs_only_its_type_and_returns_unavailable(
    monkeypatch, reel_repository, caplog
):
    class PrivateBackendFailure(RuntimeError):
        pass

    secret = "PRIVATE CAPTION AND MODEL OUTPUT MUST NOT REACH A LOG"
    backend = RecordingReeler(error=PrivateBackendFailure(secret))
    client = build_reel_client(monkeypatch, reel_repository, backend)

    with caplog.at_level(logging.WARNING, logger="app.api.service"):
        response = read_reel(client)

    assert response.status_code == 200, response.text
    assert response.json() == silent_body(
        "unavailable", considered_count=len(OWN_MEMORIES)
    )
    assert "PrivateBackendFailure" in caplog.text
    assert secret not in caplog.text
    assert "Bình minh đầu tiên" not in caplog.text
    assert "Quán bên hồ" not in caplog.text


def test_an_ungrounded_answer_never_falls_back_to_the_heart_list(
    monkeypatch, reel_repository
):
    backend = RecordingReeler(
        {
            "title": "Looks plausible",
            "picks": [{"memory_id": str(uuid.uuid4()), "note": "Invented"}],
        }
    )
    client = build_reel_client(monkeypatch, reel_repository, backend)

    body = read_reel(client).json()

    assert body == silent_body("ungrounded", considered_count=len(OWN_MEMORIES))
    assert str(HIGH_HEART_ID) not in str(body)


def test_a_stranger_gets_the_same_constant_403_before_any_outing_lookup(
    reel_client, reel_repository, reeler
):
    claimed = actor_headers(STRANGER_ID, claimed_context=CONTEXT_ID)

    real = read_reel(reel_client, headers=claimed)
    missing = read_reel(reel_client, headers=claimed, outing_id=uuid.uuid4())

    assert real.status_code == missing.status_code == 403
    assert real.json() == missing.json()
    assert real.json()["code"] == "permission_denied"
    assert [call[0] for call in reel_repository.calls] == [
        "is_member",
        "is_member",
    ]
    assert reeler.calls == []


def test_an_outing_from_another_context_is_404_before_memories_or_model(
    reel_client, reel_repository, reeler
):
    response = read_reel(reel_client, outing_id=FOREIGN_OUTING_ID)

    assert response.status_code == 404
    assert response.json() == {
        "code": "album_not_found",
        "detail": "Chuyến đi này không có ở đây.",
    }
    assert [call[0] for call in reel_repository.calls] == [
        "is_member",
        "group_recap",
    ]
    assert reeler.calls == []


def test_the_route_has_only_path_and_gateway_parameters_and_declares_refusals():
    app = create_app()
    path = "/contexts/{context_id}/albums/{outing_id}/reel"
    operation = app.openapi()["paths"][path]["get"]
    query_parameters = [
        parameter
        for parameter in operation.get("parameters", [])
        if parameter["in"] == "query"
    ]

    assert "requestBody" not in operation
    assert query_parameters == []
    assert {"403", "404", "422", "429"} <= set(operation["responses"])
    route = next(
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == path
    )
    assert route.methods == {"GET"}


def test_prompt_builder_drops_image_material_even_from_an_overwide_caller():
    image_url = "https://private.invalid/the-groups-photo.jpg"
    image_bytes = "PRIVATE_IMAGE_BYTES_37"
    prompt = build_reel_prompt(
        {
            "title": "Chuyến đi",
            "starts_on": "2030-08-27",
            "ends_on": "2030-08-29",
            "headcount": 4,
            "private": "trip field outside the contract",
        },
        [
            {
                "id": str(LOW_HEART_ID),
                "kind": "photo",
                "caption": "Bình minh đầu tiên",
                "place_name": None,
                "created_at": NOW.isoformat(),
                "reaction_count": 1,
                "comment_count": 2,
                "image_url": image_url,
                "image_bytes": image_bytes,
            }
        ],
    )

    assert "Bình minh đầu tiên" in prompt
    assert image_url not in prompt
    assert image_bytes not in prompt
    assert "trip field outside the contract" not in prompt


def test_unconfigured_gemini_returns_none_and_logs_a_closed_code(monkeypatch, caplog):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with caplog.at_level(logging.INFO, logger="app.api.reel_gemini"):
        result = gemini_reel({"title": "private trip"}, [{"caption": "private"}])

    assert result is None
    assert [record.getMessage() for record in caplog.records] == [
        "reel_gemini_unconfigured"
    ]
    assert "private trip" not in caplog.text
    assert "private" not in caplog.text


def test_gemini_transport_failure_logs_no_key_prompt_or_exception_text(
    monkeypatch, caplog
):
    api_key = "fake-api-key-that-must-stay-private"
    private_error = "upstream echoed a private caption"
    monkeypatch.setenv("GEMINI_API_KEY", api_key)

    def fail(*args, **kwargs):
        del args, kwargs
        raise RuntimeError(private_error)

    monkeypatch.setattr("app.api.reel_gemini.urllib.request.urlopen", fail)

    with caplog.at_level(logging.WARNING, logger="app.api.reel_gemini"):
        result = gemini_reel(
            {"title": "private trip"},
            [{"id": str(LOW_HEART_ID), "caption": "private caption"}],
        )

    assert result is None
    assert [record.getMessage() for record in caplog.records] == [
        "reel_gemini_call_failed"
    ]
    for secret in (api_key, private_error, "private trip", "private caption"):
        assert secret not in caplog.text
