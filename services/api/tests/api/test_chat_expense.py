"""F24 HTTP orchestration with the model and repository kept deterministic."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.api.repository import MembershipRecord, MessageRecord

from .helpers import (
    ADVANCER_ID,
    CONTEXT_ID,
    OTHER_ID,
    SENDER_ID,
    actor_headers,
)

MESSAGE_ID = uuid.UUID("5ee00000-eeee-4eee-8eee-0000e0000001")
OTHER_CONTEXT_ID = uuid.UUID("6ff00000-ffff-4fff-8fff-0000f0000001")
NOW = datetime(2030, 8, 30, 8, 0, tzinfo=UTC)


class PinnedChatReader:
    def __init__(self, reading: dict):
        self.reading = reading
        self.calls: list[str] = []

    def read(self, text: str) -> dict:
        self.calls.append(text)
        return dict(self.reading)


def _seed_message(
    repository,
    *,
    message_id: uuid.UUID = MESSAGE_ID,
    context_id: uuid.UUID = CONTEXT_ID,
    author_id: uuid.UUID | None = SENDER_ID,
    kind: str = "text",
    body: str | None = "Tao trả Grab 180k rồi nhé.",
) -> MessageRecord:
    record = MessageRecord(
        id=message_id,
        context_id=context_id,
        author_id=author_id,
        kind=kind,
        body=body,
        image_url=None,
        card=None if kind != "ai_card" else {"type": "suggestion"},
        created_at=NOW,
    )
    repository.messages[record.id] = record
    return record


def _override_reader(client, reader) -> None:
    from app.api.deps import get_chat_expense_reader

    client.app.dependency_overrides[get_chat_expense_reader] = lambda: reader


def _post(client, message_id: uuid.UUID = MESSAGE_ID, **kwargs):
    headers = kwargs.pop("headers", actor_headers())
    return client.post(
        f"/contexts/{CONTEXT_ID}/messages/{message_id}/expense-draft",
        headers=headers,
        **kwargs,
    )


def test_chat_expense_route_declares_no_request_body(client) -> None:
    operation = client.app.openapi()["paths"][
        "/contexts/{context_id}/messages/{message_id}/expense-draft"
    ]["post"]

    assert "requestBody" not in operation


def test_chat_expense_uses_message_author_and_active_roster_not_request_json(
    client, repository
) -> None:
    message = _seed_message(repository)
    reader = PinnedChatReader(
        {"is_expense": True, "title": "  Grab  ", "amount_text": "180k"}
    )
    _override_reader(client, reader)

    response = _post(
        client,
        json={
            "paid_by_id": str(OTHER_ID),
            "shared_by": [str(OTHER_ID)],
            "amount_vnd": 1,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "context_id": str(CONTEXT_ID),
        "message_id": str(MESSAGE_ID),
        "detected": True,
        "draft": {
            "title": "Grab",
            "amount_vnd": 180_000,
            "paid_by_id": str(SENDER_ID),
            "shared_by": [str(ADVANCER_ID), str(SENDER_ID)],
            "needs_review": True,
        },
        "reason": None,
    }
    assert reader.calls == [message.body]
    assert repository.expenses == {}
    assert repository.confirmed == {}


def test_chat_expense_excludes_non_active_roster_rows(
    client, repository, monkeypatch
) -> None:
    _seed_message(repository)
    original = repository.list_members
    invited = MembershipRecord(
        id=uuid.uuid4(),
        context_id=CONTEXT_ID,
        person_id=OTHER_ID,
        display_name="Người được mời",
        state="invited",
        role="member",
        origin="named",
        invited_by_id=ADVANCER_ID,
        joined_at=None,
        left_at=None,
        created_at=NOW,
    )
    monkeypatch.setattr(
        repository,
        "list_members",
        lambda context_id: [*original(context_id), invited],
    )
    reader = PinnedChatReader(
        {"is_expense": True, "title": "Grab", "amount_text": "180k"}
    )
    _override_reader(client, reader)

    response = _post(client)

    assert response.status_code == 200
    assert str(OTHER_ID) not in response.json()["draft"]["shared_by"]


def test_chat_expense_requires_active_membership_before_reading_the_message(
    client, repository
) -> None:
    _seed_message(repository)
    reader = PinnedChatReader(
        {"is_expense": True, "title": "Grab", "amount_text": "180k"}
    )
    _override_reader(client, reader)

    response = _post(client, headers={"X-Actor-ID": str(OTHER_ID)})

    assert response.status_code == 403
    assert reader.calls == []


def test_chat_expense_hides_a_message_owned_by_another_context(
    client, repository
) -> None:
    secret = "Nhóm B đi nơi bí mật và trả 987k"
    _seed_message(repository, context_id=OTHER_CONTEXT_ID, body=secret)
    reader = PinnedChatReader(
        {"is_expense": True, "title": "Bí mật", "amount_text": "987k"}
    )
    _override_reader(client, reader)

    response = _post(client)

    assert response.status_code == 404
    assert secret not in response.text
    assert "987k" not in response.text
    assert reader.calls == []


def test_chat_expense_missing_message_is_the_same_404(client) -> None:
    reader = PinnedChatReader(
        {"is_expense": True, "title": "Grab", "amount_text": "180k"}
    )
    _override_reader(client, reader)

    response = _post(client)

    assert response.status_code == 404
    assert response.json()["code"] == "message_not_found"
    assert reader.calls == []


def test_chat_expense_ai_card_has_no_person_who_paid(client, repository) -> None:
    _seed_message(repository, author_id=None, kind="ai_card", body=None)
    reader = PinnedChatReader(
        {"is_expense": True, "title": "Grab", "amount_text": "180k"}
    )
    _override_reader(client, reader)

    response = _post(client)

    assert response.status_code == 422
    assert response.json()["code"] == "message_has_no_author"
    assert reader.calls == []


def test_chat_expense_message_without_text_is_refused_before_the_model(
    client, repository
) -> None:
    _seed_message(repository, kind="image", body=None)
    reader = PinnedChatReader(
        {"is_expense": True, "title": "Grab", "amount_text": "180k"}
    )
    _override_reader(client, reader)

    response = _post(client)

    assert response.status_code == 422
    assert response.json()["code"] == "message_has_no_text"
    assert reader.calls == []


def test_chat_expense_can_report_that_nothing_was_detected(client, repository) -> None:
    _seed_message(repository)
    reader = PinnedChatReader({"is_expense": False})
    _override_reader(client, reader)

    response = _post(client)

    assert response.status_code == 200
    body = response.json()
    assert body["detected"] is False
    assert body["draft"] is None
    assert isinstance(body["reason"], str) and body["reason"].strip()


def test_chat_expense_refuses_model_authored_identity(client, repository) -> None:
    _seed_message(repository)
    reader = PinnedChatReader(
        {
            "is_expense": True,
            "title": "Grab",
            "amount_text": "180k",
            "paid_by": "Nam",
        }
    )
    _override_reader(client, reader)

    response = _post(client)

    assert response.status_code == 422
    assert response.json()["code"] == "chat_expense_model_named_a_person"


def test_chat_expense_unreadable_model_money_is_a_422(client, repository) -> None:
    _seed_message(repository)
    reader = PinnedChatReader(
        {"is_expense": True, "title": "Grab", "amount_text": 180_000.0}
    )
    _override_reader(client, reader)

    response = _post(client)

    assert response.status_code == 422
    assert response.json()["code"] == "chat_expense_unreadable"


def test_chat_expense_missing_backend_key_is_a_server_configuration_error(
    client, repository
) -> None:
    from app.domain.chat_expense import ChatExpenseError

    class UnconfiguredReader:
        def read(self, text: str) -> dict:
            del text
            raise ChatExpenseError("CHAT_READER_NOT_CONFIGURED")

    _seed_message(repository)
    _override_reader(client, UnconfiguredReader())

    response = _post(client)

    assert response.status_code == 503
    assert response.json()["code"] == "chat_reader_not_configured"


def test_chat_expense_backend_failure_does_not_echo_or_log_private_text(
    client, repository, caplog
) -> None:
    private_output = "secret model output and api key"

    class BrokenReader:
        def read(self, text: str) -> dict:
            del text
            raise RuntimeError(private_output)

    _seed_message(repository)
    _override_reader(client, BrokenReader())

    response = _post(client)

    assert response.status_code == 502
    assert response.json()["code"] == "chat_reader_unavailable"
    assert private_output not in response.text
    assert private_output not in caplog.text
    assert "Tao trả Grab 180k rồi nhé." not in caplog.text


def test_chat_expense_rate_limit_is_per_actor(client, repository) -> None:
    from app.api.routes.messages import get_chat_expense_limiter
    from app.api.search_rate_limit import FixedWindowLimiter

    _seed_message(repository)
    reader = PinnedChatReader(
        {"is_expense": True, "title": "Grab", "amount_text": "180k"}
    )
    limiter = FixedWindowLimiter(
        limit=1,
        window_seconds=60,
        code="chat_expense_rate_limited",
        message="Quá nhiều lượt đọc tin nhắn.",
    )
    _override_reader(client, reader)
    client.app.dependency_overrides[get_chat_expense_limiter] = lambda: limiter

    first = _post(client)
    refused = _post(client)
    other_actor = _post(client, headers=actor_headers(SENDER_ID))

    assert first.status_code == 200
    assert refused.status_code == 429
    assert refused.json()["code"] == "chat_expense_rate_limited"
    assert other_actor.status_code == 200
    assert reader.calls == [
        "Tao trả Grab 180k rồi nhé.",
        "Tao trả Grab 180k rồi nhé.",
    ]


@pytest.mark.parametrize("bad_amount", [180_000.0, "180000", True, 0])
def test_chat_expense_response_money_is_strict_and_positive(bad_amount) -> None:
    from app.api.schemas import ChatExpenseDraft

    with pytest.raises(ValidationError):
        ChatExpenseDraft(
            title="Grab",
            amount_vnd=bad_amount,
            paid_by_id=SENDER_ID,
            shared_by=[SENDER_ID],
            needs_review=True,
        )


def test_chat_expense_response_state_cannot_be_half_present() -> None:
    from app.api.schemas import ChatExpenseDraft, ChatExpenseDraftResponse

    draft = ChatExpenseDraft(
        title="Grab",
        amount_vnd=180_000,
        paid_by_id=SENDER_ID,
        shared_by=[SENDER_ID],
        needs_review=True,
    )

    with pytest.raises(ValidationError):
        ChatExpenseDraftResponse(
            context_id=CONTEXT_ID,
            message_id=MESSAGE_ID,
            detected=True,
            draft=None,
            reason=None,
        )
    with pytest.raises(ValidationError):
        ChatExpenseDraftResponse(
            context_id=CONTEXT_ID,
            message_id=MESSAGE_ID,
            detected=False,
            draft=draft,
            reason="Không thấy khoản chi.",
        )
    with pytest.raises(ValidationError):
        ChatExpenseDraftResponse(
            context_id=CONTEXT_ID,
            message_id=MESSAGE_ID,
            detected=False,
            draft=None,
            reason="   ",
        )
