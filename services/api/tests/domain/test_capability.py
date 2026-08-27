"""Guest capability scope, product-spec invariant 6."""

from __future__ import annotations

import pytest

from app.domain.capability import CapabilityScopeError, capability_scope


def test_scope_is_one_sender_and_one_immutable_batch_version():
    scope = capability_scope(
        {"batch_version_id": "v1", "sender_id": "ha"},
        [
            {"obligation_id": "o2", "batch_version_id": "v1", "sender_id": "ha"},
            {"obligation_id": "o1", "batch_version_id": "v1", "sender_id": "ha"},
        ],
    )
    assert scope == {
        "batch_version_id": "v1",
        "sender_id": "ha",
        "obligation_ids": ("o1", "o2"),
    }


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("sender_id", "someone-else", "CROSSES_SENDER"),
        ("batch_version_id", "v2", "CROSSES_BATCH_VERSION"),
    ],
)
def test_scope_rejects_crossing_sender_or_version(field, value, code):
    obligation = {"obligation_id": "o1", "batch_version_id": "v1", "sender_id": "ha"}
    obligation[field] = value
    with pytest.raises(CapabilityScopeError, match=code):
        capability_scope({"batch_version_id": "v1", "sender_id": "ha"}, [obligation])
