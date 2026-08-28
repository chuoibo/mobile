"""One permission table. Every API and every ActionItem asks this module.

Spec section 9 opens with the reason: scattered permission checks are exactly
how the confused deputy comes back. If three call sites each decide who may
publish a batch, they will disagree eventually, and the disagreement will be
discovered by someone collecting money they had no right to collect.

So the rules live here as data, and `can()` is the only way to read them.

Pure functions over plain dicts. No I/O, no ORM, no framework.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "ACTIONS",
    "ROLES",
    "AuthorizationFacts",
    "can",
    "denial_reason",
    "PermissionError_",
]

ROLES = (
    "group_admin",
    "batch_owner",
    "advancer",
    "recipient",
    "sender",
    "creditor",
    "member",
    "former_member",
    "guest",
    "platform_moderator",
)

# Each entry is (roles that may act, extra predicates the context must satisfy).
# A role listed here is necessary, never sufficient on its own -- the predicates
# are what stop a batch_owner from acting outside their own batch.
_TABLE: dict[str, dict] = {
    # --- invocation ----------------------------------------------------
    "create_private_invocation": {"roles": {"member"}, "requires": ()},
    "create_shared_invocation": {"roles": {"member"}, "requires": ()},
    "view_invocation_input": {"roles": {"member"}, "requires": ("is_invoker",)},
    "view_invocation_proposal": {"roles": {"member"}, "requires": ("is_invoker",)},
    # --- expense -------------------------------------------------------
    "confirm_expense_proposal": {"roles": {"member"}, "requires": ("is_group_member",)},
    # Gate 2 of section 8.3. Only the person who actually fronted the money may
    # acknowledge that they fronted it; otherwise a member could raise
    # collections in someone else's name.
    "acknowledge_advancer_role": {
        "roles": {"advancer"},
        "requires": ("is_named_advancer",),
    },
    # --- collection board ----------------------------------------------
    # Reading who owes what, to whom, how much, and why somebody objected. The
    # endpoint shipped without this entry and without the check that uses it:
    # the service accepted an `actor` argument and never read it, so any valid
    # actor header plus a batch id returned every sender, every amount, and the
    # private reason a guest gave for disputing. Section 10 says visibility is
    # fail-closed; an unused parameter is the most convincing way to look like
    # it is while it is not.
    "view_collection_board": {"roles": {"member"}, "requires": ("is_group_member",)},
    # --- bank recipient ------------------------------------------------
    # Section 9.2: an admin may not add or change someone else's bank account,
    # and an AdvancerApprovalCapability explicitly may not be used for this.
    "set_bank_recipient": {
        "roles": {"member"},
        "requires": ("is_own_account", "is_authenticated_account"),
    },
    # Reading is narrower than writing, not wider. The screen that asks "where
    # does my money land?" needs an answer, but an account number is the one
    # field a group member has no business reading off a peer, so the same
    # is_own_account predicate gates the read.
    "view_bank_recipient": {
        "roles": {"member"},
        "requires": ("is_own_account", "is_authenticated_account"),
    },
    # --- batch ---------------------------------------------------------
    "create_batch": {"roles": {"member"}, "requires": ("is_group_member",)},
    "freeze_batch": {"roles": {"batch_owner"}, "requires": ("owns_batch",)},
    "publish_batch": {
        "roles": {"batch_owner"},
        "requires": ("owns_batch", "all_recipients_eligible"),
    },
    # Section 9.1: whoever has data or risk inside a capability may pull it
    # back. Three different subjects, three different scopes.
    "revoke_capability_whole_batch": {
        "roles": {"batch_owner"},
        "requires": ("owns_batch",),
    },
    "revoke_capability_own_recipient_account": {
        "roles": {"recipient"},
        "requires": ("envelope_contains_own_account",),
    },
    "revoke_capability_own_envelope": {
        "roles": {"sender"},
        "requires": ("is_own_capability",),
    },
    # --- guest settlement ----------------------------------------------
    # A bearer token is a capability, not proof of identity. The repository
    # first resolves it to one immutable envelope; these predicates ensure the
    # API never widens that scope while deciding what the holder may do.
    "view_guest_envelope": {"roles": {"guest"}, "requires": ("is_own_capability",)},
    "report_payment": {
        "roles": {"guest"},
        "requires": (
            "is_own_capability",
            "active_capability",
            "report_budget_available",
        ),
    },
    # Receipt confirmation is a financial event. Only the creditor of this
    # exact directed edge may create it; being a batch owner is irrelevant.
    "confirm_receipt": {
        "roles": {"recipient"},
        "requires": ("is_recipient_of_this_obligation",),
    },
    # --- things the batch owner may NOT do alone ------------------------
    "cancel_obligation": {
        "roles": {"batch_owner"},
        "requires": ("all_affected_parties_consented",),
    },
    "amend_obligation_after_publish": {
        "roles": {"batch_owner"},
        "requires": ("all_affected_parties_consented",),
    },
    "delete_payment_report": {"roles": set(), "requires": ()},
    "delete_receipt_confirmation": {"roles": set(), "requires": ()},
    "delete_audit_history": {"roles": set(), "requires": ()},
    "close_dispute": {"roles": {"platform_moderator"}, "requires": ()},
    # --- debt forgiveness ----------------------------------------------
    # Spec section 4: only the creditor of that exact receivable. The organiser
    # does not get to forgive on Ha's behalf.
    "waive_obligation": {
        "roles": {"creditor"},
        "requires": ("is_creditor_of_this_obligation",),
    },
    # --- evidence ------------------------------------------------------
    "request_redacted_evidence": {
        "roles": {"member", "guest"},
        "requires": ("is_charged_party",),
    },
    "share_evidence": {"roles": {"member"}, "requires": ("is_uploader",)},
    # --- identity ------------------------------------------------------
    "invite_person_stub_claim": {"roles": {"member"}, "requires": ()},
    "challenge_person_stub_claim": {"roles": {"member"}, "requires": ()},
    # Section 9.2: an admin does not adjudicate identity. Only the platform
    # does -- because in a group dispute the attacker is a group member.
    "adjudicate_person_stub_claim": {"roles": {"platform_moderator"}, "requires": ()},
    # --- group logistics ------------------------------------------------
    "create_context": {"roles": {"group_admin", "member"}, "requires": ()},
    "invite_context_member": {
        "roles": {"group_admin"},
        "requires": ("is_group_member",),
    },
    "accept_context_membership": {
        "roles": {"group_admin", "member"},
        "requires": ("is_invitee",),
    },
    "leave_context": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member", "is_self"),
    },
    "view_context_members": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    "manage_members_and_invites": {"roles": {"group_admin"}, "requires": ()},
    "remove_member_from_group": {"roles": {"group_admin"}, "requires": ()},
    "transfer_group_admin": {"roles": {"group_admin"}, "requires": ()},
    "remove_own_uploaded_content": {
        "roles": {"group_admin", "member"},
        "requires": ("is_uploader",),
    },
    "remove_others_content": {"roles": {"platform_moderator"}, "requires": ()},
    "attach_workspace_to_group": {
        "roles": {"member"},
        "requires": ("is_workspace_owner",),
    },
}

ACTIONS = tuple(sorted(_TABLE))


class PermissionError_(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class AuthorizationFacts:
    """What an authoritative source proved, not what a request claimed.

    The first version took a plain dict of booleans, so one adapter setting one
    flag wrongly bypassed the whole table -- exactly the confused deputy this
    module exists to prevent. A dict from an HTTP body and a dict from the
    database look identical to a function signature.

    So the type is the boundary. Only an adapter that read authoritative data
    can build this, `provenance` records which one did, and `can()` refuses
    anything else. Nothing here validates the facts; it makes the caller state
    where they came from, which is what an audit needs.
    """

    actor_id: str
    roles: frozenset[str]
    resource_id: str | None
    proven: frozenset[str] = field(default_factory=frozenset)
    provenance: str = ""

    def __post_init__(self):
        if not self.actor_id:
            raise PermissionError_("ANONYMOUS_ACTOR")
        if not self.provenance:
            # An unattributed fact cannot be audited later, and the point of
            # one permission table is that every decision can be explained.
            raise PermissionError_("FACTS_WITHOUT_PROVENANCE")
        unknown = set(self.roles) - set(ROLES)
        if unknown:
            raise PermissionError_("UNKNOWN_ROLE")


def can(action: str, facts: AuthorizationFacts) -> bool:
    """True when `facts` permit `action`."""
    return denial_reason(action, facts) is None


def denial_reason(action: str, facts: AuthorizationFacts) -> str | None:
    """None when allowed, otherwise the name of what is missing.

    Returning the reason rather than a bare False is deliberate: the interface
    has to tell somebody what is missing. "The advancer has not acknowledged
    yet" is actionable; "forbidden" is not.
    """
    if action not in _TABLE:
        raise PermissionError_("UNKNOWN_ACTION")
    if not isinstance(facts, AuthorizationFacts):
        # A plain dict is how a request body sneaks in wearing the costume of
        # a database read.
        raise PermissionError_("UNTYPED_FACTS")

    rule = _TABLE[action]
    if not rule["roles"]:
        # Nobody, ever. Deleting a receipt confirmation would let the ledger be
        # rewritten to suit whoever holds the button.
        return "action_permitted_to_nobody"
    if not (set(facts.roles) & rule["roles"]):
        return "role_not_permitted"
    for predicate in rule["requires"]:
        if predicate not in facts.proven:
            return predicate
    return None
