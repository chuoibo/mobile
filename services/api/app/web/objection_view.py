"""View models for the two ways a guest can say "this is wrong".

Spec section 8.6 makes both first-class outcomes, not escape hatches:

    [Đúng, xem cách chuyển] · [Số tiền không đúng] · [Tôi không phải Hà]

They were links to routes that did not exist, so a guest who pressed either
one got a 404. That is worse than not offering them: the page invites a person
to object and then behaves as though the objection broke something.

Both surfaces are built around what the product genuinely cannot know:

  * It cannot tell who is holding a link. So "I am not Ha" never asks the
    reader to identify themselves, and never says "we will verify".
  * It cannot force the person who recorded the expense to share evidence. So
    section 10.5 is explicit that missing evidence must NOT be read as the
    charged party being wrong.

Pure functions over plain dicts. No I/O, no ORM, no framework.
"""

from __future__ import annotations

from app.web.guest_view import format_vnd

__all__ = [
    "ObjectionError",
    "ALLOWED_NOT_ME",
    "ALLOWED_WRONG_AMOUNT",
    "build_not_me_view",
    "build_wrong_amount_view",
    "OBJECTION_REASONS",
]

ALLOWED_NOT_ME = frozenset({
    "claimed_person_display_name",
    "recorded_by_display_name",
    "already_reported",
    "can_object",
})

ALLOWED_WRONG_AMOUNT = frozenset({
    "claimed_person_display_name",
    "recorded_by_display_name",
    "occasion_label",
    "amount_display",
    "obligation_id",
    "can_object",
    "can_request_evidence",
    "evidence_requested",
    "reasons",
})

# A closed list, because free text is where a stranger accidentally writes
# something the group should not see, and where the recorded_by person reads a
# tone that turns a bookkeeping question into a fight.
OBJECTION_REASONS = (
    ("amount_too_high", "Số tiền cao hơn phần của tôi"),
    ("did_not_join", "Tôi không tham gia khoản này"),
    ("already_paid", "Tôi đã chuyển rồi"),
    ("split_wrong", "Chia sai người"),
    ("other", "Lý do khác"),
)


class ObjectionError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _guard(envelope: dict) -> None:
    forbidden = {"group_balance", "group_history", "other_allocations",
                 "invocation_thread", "original_bill_url", "member_list"}
    if forbidden & set(envelope):
        raise ObjectionError("FORBIDDEN_FIELD_IN_INPUT")
    if envelope.get("link_state") != "active":
        raise ObjectionError("LINK_NOT_ACTIVE")


def build_not_me_view(envelope: dict) -> dict:
    """The reader says the link is not for them.

    Shows less than the main page, not more. Somebody who is not the intended
    reader should end this flow knowing strictly less about the group than when
    they arrived, so no amount and no account details appear here.
    """
    _guard(envelope)
    view = {
        "claimed_person_display_name": envelope["claimed_person_display_name"],
        "recorded_by_display_name": envelope["recorded_by_display_name"],
        "already_reported": bool(envelope.get("not_me_reported")),
        "can_object": envelope["objections_used"] < envelope["objections_allowed"],
    }
    extra = set(view) - ALLOWED_NOT_ME
    if extra:
        raise ObjectionError("FIELD_NOT_ALLOWED")
    return view


def build_wrong_amount_view(envelope: dict, obligation_id: str) -> dict:
    """The reader agrees they are the right person but disputes the number."""
    _guard(envelope)
    matches = [o for o in envelope["obligations"] if o["obligation_id"] == obligation_id]
    if not matches:
        raise ObjectionError("UNKNOWN_OBLIGATION")
    obligation = matches[0]

    view = {
        "claimed_person_display_name": envelope["claimed_person_display_name"],
        "recorded_by_display_name": envelope["recorded_by_display_name"],
        "occasion_label": obligation["occasion_label"],
        # Only the amount they were already shown. A dispute page is not a
        # reason to widen what a guest can see, so this is formatted from the
        # same integer the main page rendered rather than read from a wider
        # projection.
        "amount_display": obligation.get("amount_display")
        or format_vnd(obligation["amount_vnd"]),
        "obligation_id": obligation_id,
        # Per obligation, matching the home page. This still read the link-wide
        # count after the quota moved onto each debt, so the two pages
        # disagreed: the card offered the button and the page it led to locked
        # the form, telling a guest they had used up a quota they had not
        # touched. Inviting somebody to object and then refusing is worse than
        # never offering.
        "can_object": obligation.get("objections_used", envelope["objections_used"])
        < obligation.get("objections_allowed", envelope["objections_allowed"]),
        "can_request_evidence": not bool(obligation.get("evidence_requested")),
        "evidence_requested": bool(obligation.get("evidence_requested")),
        "reasons": list(OBJECTION_REASONS),
    }
    extra = set(view) - ALLOWED_WRONG_AMOUNT
    if extra:
        raise ObjectionError("FIELD_NOT_ALLOWED")
    return view
