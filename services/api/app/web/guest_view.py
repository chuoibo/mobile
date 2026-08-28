"""Build the view model for the guest page.

The guest page is the one surface a stranger reaches without installing
anything, so it is also the easiest place to leak a whole group's finances by
accident. Spec section 8.6 and 10.4 draw the line:

    A guest sees their own envelope. Never a group balance, never group
    history, never the invocation thread, never anybody else's allocation.

This module is the boundary. The template renders what it returns and nothing
else, so the leak test lives here rather than in a Jinja file where nobody
would think to look.

Pure functions over plain dicts. No I/O, no ORM, no framework.
"""

from __future__ import annotations

from app.web.banks import bank_display_name

__all__ = ["GuestViewError", "build_guest_view", "ALLOWED_TOP_LEVEL", "ALLOWED_BLOCK"]

# Whitelists, not blacklists. A blacklist grows a hole the first time somebody
# adds a field upstream and forgets to exclude it -- and on this page the
# forgotten field is somebody else's money.
ALLOWED_TOP_LEVEL = frozenset({
    "recorded_by_display_name",
    "claimed_person_display_name",
    "blocks",
    "link_state",
    "can_report_payment",
    "can_object",
})

ALLOWED_BLOCK = frozenset({
    "obligation_id",
    "occasion_label",
    "amount_vnd",
    "amount_display",
    "recipient_display_name",
    "bank_name",
    "bank_bin",
    "account_number",
    "account_holder_name",
    "transfer_note",
    "qr_payload",
    "qr_image_data_uri",
    "already_reported",
    "receiver_confirmed",
})

# Anything on this list appearing in the input is a programming error upstream,
# not something to quietly drop.
FORBIDDEN_INPUT_KEYS = frozenset({
    "group_balance",
    "group_history",
    "other_allocations",
    "invocation_thread",
    "original_bill_url",
    "member_list",
})


class GuestViewError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def format_vnd(amount_vnd: int) -> str:
    """82000 -> '82.000'. Vietnamese grouping, no currency symbol.

    The symbol is set separately in the template so it can be sized down; a
    string with the symbol baked in would force the template to slice it back
    out.
    """
    if isinstance(amount_vnd, bool) or not isinstance(amount_vnd, int):
        raise GuestViewError("AMOUNT_NOT_INTEGER")
    if amount_vnd < 0:
        raise GuestViewError("NEGATIVE_AMOUNT")
    return f"{amount_vnd:,}".replace(",", ".")


def build_guest_view(envelope: dict) -> dict:
    """Project one envelope down to exactly what the guest page may render.

    An envelope covers one sender's obligations inside one batch version, and
    may point at several recipients (spec section 8.2). Each block is
    independent: a dispute with Ha does not block the transfer to Nam.
    """
    leaked = FORBIDDEN_INPUT_KEYS & set(envelope)
    if leaked:
        raise GuestViewError("FORBIDDEN_FIELD_IN_INPUT")

    state = envelope.get("link_state")
    if state not in {"active", "revoked", "expired", "rotated"}:
        raise GuestViewError("UNKNOWN_LINK_STATE")

    if state != "active":
        # An expired link does not make the obligation disappear (section 8.2),
        # but it stops showing account numbers.
        return {
            "recorded_by_display_name": envelope["recorded_by_display_name"],
            "claimed_person_display_name": envelope["claimed_person_display_name"],
            "blocks": [],
            "link_state": state,
            "can_report_payment": False,
            "can_object": False,
        }

    blocks = []
    for obligation in envelope["obligations"]:
        blocks.append({
            "obligation_id": obligation["obligation_id"],
            "occasion_label": obligation["occasion_label"],
            "amount_vnd": obligation["amount_vnd"],
            "amount_display": format_vnd(obligation["amount_vnd"]),
            "recipient_display_name": obligation["recipient_display_name"],
            # A BIN is a routing code, not something a person can act on.
            "bank_name": obligation.get("bank_name")
            or bank_display_name(obligation["bank_bin"]),
            "bank_bin": obligation["bank_bin"],
            "account_number": obligation["account_number"],
            "account_holder_name": obligation["account_holder_name"],
            "transfer_note": obligation["transfer_note"],
            "qr_payload": obligation["qr_payload"],
            # Rendered server-side. Guests read this on the phone they will
            # pay from, so there is no second device to scan with -- the QR
            # is the fallback and copy is the primary path (spec 8.6).
            "qr_image_data_uri": obligation.get("qr_image_data_uri"),
            "already_reported": bool(obligation.get("already_reported")),
            # Only the recipient can set this, and even then it is a person
            # pressing a button -- not bank evidence (spec section 15).
            "receiver_confirmed": bool(obligation.get("receiver_confirmed")),
        })
        extra = set(blocks[-1]) - ALLOWED_BLOCK
        if extra:
            raise GuestViewError("BLOCK_FIELD_NOT_ALLOWED")

    view = {
        "recorded_by_display_name": envelope["recorded_by_display_name"],
        "claimed_person_display_name": envelope["claimed_person_display_name"],
        "blocks": blocks,
        "link_state": state,
        # Section 8.6 caps how often a guest may report or object, so a leaked
        # link cannot be used to spam the recipient.
        "can_report_payment": envelope.get("reports_used", 0) < envelope.get("reports_allowed", 3),
        "can_object": envelope["objections_used"] < envelope["objections_allowed"],
    }
    extra = set(view) - ALLOWED_TOP_LEVEL
    if extra:
        raise GuestViewError("TOP_LEVEL_FIELD_NOT_ALLOWED")
    return view


# Section 8.6: link previews must not carry a name or an amount. Whoever sees
# the preview in a group chat is not necessarily the intended reader.
NEUTRAL_PREVIEW = {
    "title": "Chi tiết khoản cần gửi",
    "description": "Mở để xem phần của bạn và cách chuyển.",
}
