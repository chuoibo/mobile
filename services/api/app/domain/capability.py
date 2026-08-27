"""Guest-capability scope invariant from product spec section 8.2."""

from __future__ import annotations

__all__ = ["CapabilityScopeError", "capability_scope"]


class CapabilityScopeError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def capability_scope(envelope: dict, obligations: list[dict]) -> dict:
    """Return a canonical scope only for one sender in one batch version.

    The database makes batch versions, obligations and envelopes append-only.
    This function closes the other half of invariant 6: a bearer capability is
    rejected if its queried obligation set crosses either the sender or version
    boundary. The canonical obligation-id tuple is the immutable set the link
    covers.
    """

    if not obligations:
        raise CapabilityScopeError("NO_OBLIGATIONS")

    batch_version_id = envelope["batch_version_id"]
    sender_id = envelope["sender_id"]
    obligation_ids = []
    for obligation in obligations:
        if obligation["batch_version_id"] != batch_version_id:
            raise CapabilityScopeError("CROSSES_BATCH_VERSION")
        if obligation["sender_id"] != sender_id:
            raise CapabilityScopeError("CROSSES_SENDER")
        obligation_ids.append(obligation["obligation_id"])

    if len(set(obligation_ids)) != len(obligation_ids):
        raise CapabilityScopeError("DUPLICATE_OBLIGATION")
    return {
        "batch_version_id": batch_version_id,
        "sender_id": sender_id,
        "obligation_ids": tuple(sorted(obligation_ids, key=lambda value: str(value))),
    }
