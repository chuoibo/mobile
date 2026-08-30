"""F37 leak probe with an explicit response-record denominator.

The probe scans every outcome the reel route can serve in Stage 1.  It also
narrows the AI-authored surface to ``title`` and ``note``: captions, place
names, counts and timestamps are server-authored facts, so mixing them into
that sub-probe would make it impossible to say whether a model wrote a leaked
string or the server attached one.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import replace

from .test_trip_reel import (
    CHECKIN_ID,
    CONTEXT_ID,
    FOREIGN_CONTEXT_ID,
    FOREIGN_OUTING_ID,
    HEADERS,
    LOW_HEART_ID,
    MEMBER_ID,
    OUTING_ID,
    STRANGER_ID,
    RecordingReeler,
    StubReelRepository,
    _memory,
    actor_headers,
    build_reel_client,
    read_reel,
)

FOREIGN_TRIP_SECRET = "FOREIGN TRIP TITLE MUST STAY PRIVATE"
FOREIGN_CAPTION_SECRET = "FOREIGN CAPTION MUST STAY PRIVATE"
NON_MEMBER_PLACE_SECRET = "NON-MEMBER PRIVATE PLACE MUST STAY PRIVATE"
FORBIDDEN = (
    FOREIGN_TRIP_SECRET,
    FOREIGN_CAPTION_SECRET,
    NON_MEMBER_PLACE_SECRET,
)
EXPECTED_RESPONSE_RECORDS = 7
EXPECTED_MODEL_TEXT_RECORDS = 3

SAFE_RAW = {
    "title": "Ba khoảnh khắc còn ở lại",
    "picks": [
        {
            "memory_id": str(LOW_HEART_ID),
            "note": "Buổi sáng mà cả nhóm vẫn nhắc lại",
        },
        {
            "memory_id": str(CHECKIN_ID),
            "note": "Quãng nghỉ nhỏ thành chuyện vui nhất chuyến",
        },
    ],
}


def _seed_foreign_and_non_member_strings(repository: StubReelRepository) -> None:
    foreign_photo = repository.memories[FOREIGN_OUTING_ID][0]
    foreign_checkin = replace(
        _memory(
            uuid.UUID("37a00000-fee1-4fee-8fee-0000fee00098"),
            FOREIGN_CONTEXT_ID,
            kind="checkin",
            caption="A foreign group's stop",
            place_name=NON_MEMBER_PLACE_SECRET,
            reaction_count=7,
            comment_count=5,
            created_at=foreign_photo.created_at,
        ),
        author_id=STRANGER_ID,
    )
    repository.memories[FOREIGN_OUTING_ID] = (foreign_photo, foreign_checkin)


def _model_text_records(body: dict) -> list[str]:
    """Only fields the model is allowed to author, never server facts."""

    if body.get("source") != "ai":
        return []
    records = [body["title"]]
    records.extend(pick["note"] for pick in body.get("picks", []))
    return [record for record in records if isinstance(record, str)]


def test_every_reel_outcome_is_scanned_for_foreign_and_non_member_strings(
    monkeypatch,
):
    response_records: list[tuple[str, object]] = []
    model_text_records: list[str] = []
    prompt_records: list[tuple[dict, list[dict]]] = []

    def capture(label, repository, backend, *, headers=HEADERS, **ids):
        _seed_foreign_and_non_member_strings(repository)
        client = build_reel_client(monkeypatch, repository, backend)
        response = read_reel(client, headers=headers, **ids)
        body = response.json()
        response_records.append((label, body))
        model_text_records.extend(_model_text_records(body))
        prompt_records.extend(backend.calls)
        return response

    success_backend = RecordingReeler(SAFE_RAW)
    success = capture("ok", StubReelRepository(), success_backend)

    no_memories_repo = StubReelRepository()
    no_memories_repo.memories[OUTING_ID] = ()
    no_memories = capture("no_memories", no_memories_repo, RecordingReeler(SAFE_RAW))

    unavailable = capture("unavailable", StubReelRepository(), RecordingReeler(None))
    ungrounded = capture(
        "ungrounded",
        StubReelRepository(),
        RecordingReeler(
            {
                "title": "Safe but refused",
                "picks": [{"memory_id": str(uuid.uuid4()), "note": "Unknown memory"}],
            }
        ),
    )

    stranger_headers = actor_headers(STRANGER_ID, claimed_context=CONTEXT_ID)
    stranger_real = capture(
        "stranger_real",
        StubReelRepository(),
        RecordingReeler(SAFE_RAW),
        headers=stranger_headers,
    )
    stranger_missing = capture(
        "stranger_missing",
        StubReelRepository(),
        RecordingReeler(SAFE_RAW),
        headers=stranger_headers,
        outing_id=uuid.uuid4(),
    )
    foreign_outing = capture(
        "foreign_outing",
        StubReelRepository(),
        RecordingReeler(SAFE_RAW),
        outing_id=FOREIGN_OUTING_ID,
    )

    assert success.status_code == 200 and success.json()["reason"] == "ok"
    assert no_memories.status_code == 200
    assert no_memories.json()["reason"] == "no_memories"
    assert unavailable.status_code == 200
    assert unavailable.json()["reason"] == "unavailable"
    assert ungrounded.status_code == 200
    assert ungrounded.json()["reason"] == "ungrounded"
    assert stranger_real.status_code == stranger_missing.status_code == 403
    assert stranger_real.json() == stranger_missing.json()
    assert foreign_outing.status_code == 404

    # The denominator is part of the assertion.  Deleting the captures above
    # cannot turn a scan of zero bodies into a green "zero leaks" report.
    assert len(response_records) == EXPECTED_RESPONSE_RECORDS
    assert len(response_records) >= EXPECTED_RESPONSE_RECORDS
    assert len(model_text_records) == EXPECTED_MODEL_TEXT_RECORDS
    assert len(prompt_records) == 3

    # These strings live only in foreign server rows.  No backend fixture wrote
    # them, so absence from the AI-authored sub-surface is meaningful rather
    # than a model stub agreeing not to echo its own text.
    assert all(secret not in json.dumps(SAFE_RAW) for secret in FORBIDDEN)
    for label, body in response_records:
        rendered = json.dumps(body, ensure_ascii=False)
        for secret in FORBIDDEN:
            assert secret not in rendered, f"{label} leaked {secret!r}"
    for record in model_text_records:
        for secret in FORBIDDEN:
            assert secret not in record

    # The model-facing inputs are checked separately from the response: a
    # silent backend must not be handed a foreign row merely because its output
    # happened not to echo it.
    for trip, memories in prompt_records:
        prompt = json.dumps([trip, memories], ensure_ascii=False)
        for secret in FORBIDDEN:
            assert secret not in prompt
        assert str(FOREIGN_OUTING_ID) not in prompt
        assert str(FOREIGN_CONTEXT_ID) not in prompt
        assert str(MEMBER_ID) not in prompt
