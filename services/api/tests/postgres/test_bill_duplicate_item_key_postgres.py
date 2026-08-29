"""Two lines with the same item_key must be refused, not crash the route.

Written by the devops lane while gating PR #83 and proved RED on 0013db7,
where `IntegrityError` escaped `create_bill` instead of `RepositoryConflict`
and the route answered 500. Kept verbatim in intent: this is the case that
lives in PostgreSQL, so the fake in `tests/api/conftest.py` cannot stand in
for it -- a fake cannot be made to violate a unique constraint it does not
have.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.api.repository import RepositoryConflict, SqlAlchemyApiRepository

pytestmark = pytest.mark.postgres

NOW = datetime(2030, 8, 29, 9, 0, tzinfo=UTC)


def _line(item_key: str, name: str, amount: int, position: int) -> dict:
    return {
        "item_key": item_key,
        "name": name,
        "quantity": 1,
        "unit_price_vnd": amount,
        "line_total_vnd": amount,
        "position": position,
        "suggested_participant_ids": [],
    }


def test_a_repeated_item_key_is_refused_not_crashed(postgres_session):
    """The same dish twice must come back as a conflict, never as a 500."""

    repository = SqlAlchemyApiRepository(postgres_session)

    with pytest.raises(RepositoryConflict) as caught:
        repository.create_bill(
            context_id=uuid.uuid4(),
            created_by_id=uuid.uuid4(),
            printed_total_vnd=60000,
            items_total_vnd=60000,
            confidence=90,
            needs_review=False,
            items=[
                _line("bia-sai-gon", "Bia Sài Gòn", 30000, 0),
                _line("bia-sai-gon", "Bia Sài Gòn", 30000, 1),
            ],
            surcharges=[],
            discounts=[],
            now=NOW,
        )

    assert caught.value.code == "DUPLICATE_BILL_ITEM_KEY"


def test_a_repeated_surcharge_key_is_refused_not_crashed(postgres_session):
    """The VAT line twice is the same defect one table over.

    Translating only `uq_bill_items_bill_item_key` fixes the case that was
    reported and leaves the two constraints added alongside it escaping as raw
    IntegrityError, which is the 500 that started this.
    """

    repository = SqlAlchemyApiRepository(postgres_session)

    with pytest.raises(RepositoryConflict) as caught:
        repository.create_bill(
            context_id=uuid.uuid4(),
            created_by_id=uuid.uuid4(),
            printed_total_vnd=90000,
            items_total_vnd=60000,
            confidence=90,
            needs_review=False,
            items=[_line("com-tam", "Cơm tấm", 60000, 0)],
            surcharges=[
                {
                    "surcharge_key": "vat",
                    "kind": "vat",
                    "amount_vnd": 15000,
                    "mode": "proportional",
                },
                {
                    "surcharge_key": "vat",
                    "kind": "vat",
                    "amount_vnd": 15000,
                    "mode": "proportional",
                },
            ],
            discounts=[],
            now=NOW,
        )

    assert caught.value.code == "DUPLICATE_BILL_SURCHARGE_KEY"


def test_a_repeated_discount_key_is_refused_not_crashed(postgres_session):
    repository = SqlAlchemyApiRepository(postgres_session)

    with pytest.raises(RepositoryConflict) as caught:
        repository.create_bill(
            context_id=uuid.uuid4(),
            created_by_id=uuid.uuid4(),
            printed_total_vnd=40000,
            items_total_vnd=60000,
            confidence=90,
            needs_review=False,
            items=[_line("com-tam", "Cơm tấm", 60000, 0)],
            surcharges=[],
            discounts=[
                {
                    "discount_key": "voucher",
                    "amount_vnd": 10000,
                    "scope": "global_proportional",
                    "target_item_key": None,
                },
                {
                    "discount_key": "voucher",
                    "amount_vnd": 10000,
                    "scope": "global_proportional",
                    "target_item_key": None,
                },
            ],
            now=NOW,
        )

    assert caught.value.code == "DUPLICATE_BILL_DISCOUNT_KEY"


def test_no_integrity_violation_escapes_as_a_raw_database_error(postgres_session):
    """Fail closed on constraints nobody has enumerated yet.

    `routes/bills.py` declares 403, 404, 409 and 422. Mapping each constraint
    by name is right, but a list of names is a list somebody has to remember to
    extend: the next check constraint added to these tables would go back to
    answering 500 in the same way this one did. The default has to be a
    conflict, not a crash.
    """

    repository = SqlAlchemyApiRepository(postgres_session)

    with pytest.raises(RepositoryConflict):
        repository.create_bill(
            context_id=uuid.uuid4(),
            created_by_id=uuid.uuid4(),
            printed_total_vnd=50000,
            items_total_vnd=60000,
            confidence=90,
            needs_review=False,
            items=[_line("com-tam", "Cơm tấm", 60000, 0)],
            surcharges=[],
            discounts=[
                # ck_bill_discounts_scope_target_match: a global discount must
                # not carry a target. The wire refuses this first, so reaching
                # it here means going around the schema on purpose.
                {
                    "discount_key": "voucher",
                    "amount_vnd": 10000,
                    "scope": "global_proportional",
                    "target_item_key": "com-tam",
                }
            ],
            now=NOW,
        )
