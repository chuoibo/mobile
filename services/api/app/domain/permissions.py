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
    # Reading is narrower than writing, not wider. A bank destination is the one
    # field an attacker most wants to read before replacing it, and there is no
    # group-visibility case for it: the collection board shows what is owed, and
    # a published envelope carries the frozen account to exactly the one sender
    # who has to pay it.
    "view_bank_recipient": {"roles": {"member"}, "requires": ("is_own_account",)},
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
    # Naming somebody who has no row yet is how a name enters this product at
    # all: nobody signs up before a friend adds them to a dinner, so the
    # organiser types "Quyên" on their own phone. Section 7.2 calls the result
    # a PersonStub -- a name a member asserted, never proof of who that is.
    "register_person_identity": {"roles": {"group_admin", "member"}, "requires": ()},
    # Changing a name that already exists is a different act, and only the
    # person themselves may do it. A display name is what a stranger reads on
    # a guest page while deciding whether to send money; letting any member
    # rewrite it lets one member change who the page appears to be from.
    "rename_person_identity": {
        "roles": {"group_admin", "member"},
        "requires": ("is_self",),
    },
    # A guessed person id never makes a face public. Reading an avatar requires
    # an ACTIVE group shared with its subject; the self-case is trivially shared.
    "set_own_avatar": {
        "roles": {"group_admin", "member"},
        "requires": ("is_self",),
    },
    "view_person_avatar": {
        "roles": {"group_admin", "member"},
        "requires": ("shares_a_group_with_subject",),
    },
    "invite_person_stub_claim": {"roles": {"member"}, "requires": ()},
    "challenge_person_stub_claim": {"roles": {"member"}, "requires": ()},
    # Section 9.2: an admin does not adjudicate identity. Only the platform
    # does -- because in a group dispute the attacker is a group member.
    "adjudicate_person_stub_claim": {"roles": {"platform_moderator"}, "requires": ()},
    # --- friend graph (F03, F04) ----------------------------------------
    # Asking is not adding. `send_friend_request` creates a PENDING edge that
    # grants nothing, which is why its only predicate is that the actor is not
    # asking themselves; anyone with an account may ask anyone.
    #
    # `is_not_self` rather than a new predicate: the fact is identical to the
    # one `approve_link_join_request` already proves, and the note there is the
    # reason to reuse rather than mint. A second name for the same fact is a
    # second place to get it wrong.
    "send_friend_request": {"roles": {"member"}, "requires": ("is_not_self",)},
    # The consent gate. `is_invitee` is reused deliberately and exactly:
    # `accept_context_membership` already means "the person this was addressed
    # to may consent to it", and a friend request is the same shape -- an offer
    # aimed at one named person. Inventing `is_addressee` would have created
    # two predicates that must agree forever, which is what #128 cost us.
    #
    # Blocking is answered by this action too, and blocking is the one answer
    # either party may give. The extra latitude is proven in the service from
    # the row, not widened here: a permission table that says "either party"
    # would also let a requester accept.
    "respond_to_friend_request": {"roles": {"member"}, "requires": ("is_invitee",)},
    # Reading your own graph. `is_self` keeps one member from listing another
    # member's friends -- the social graph is the person's, not the group's.
    "view_own_friends": {"roles": {"member"}, "requires": ("is_self",)},
    # Resolving a telephone number the caller already holds to a person id.
    # No predicate beyond membership of the product, because the caller is
    # asking about a number they typed. What keeps this from being a directory
    # is that it answers with an id and a display name and never with a
    # telephone number -- see `routes/friends.py`, which is where that is
    # enforced and tested.
    "find_person_by_phone": {"roles": {"member"}, "requires": ()},
    # --- group logistics ------------------------------------------------
    # These four actions require group membership, not outing ownership: the
    # trip belongs to the group, so any member may adjust its plan.
    "create_outing": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    "view_outings": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    "edit_outing_timeline": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    "invite_to_outing": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    # F46. Arriving somewhere with the group is a group fact, so the gate is
    # the same ACTIVE membership the rest of this block uses: `is_group_member`
    # is satisfied only by an ACTIVE row, which is why an INVITED link holder
    # can neither record an arrival nor read who else has arrived.
    "check_in_to_stop": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    "view_stop_checkins": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    # Revocation is a group decision, so ACTIVE membership is the gate; an
    # INVITED link holder fails is_group_member.
    "revoke_outing_invite": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    "create_context": {"roles": {"group_admin", "member"}, "requires": ()},
    "invite_context_member": {
        "roles": {"group_admin"},
        "requires": ("is_group_member",),
    },
    "accept_context_membership": {
        "roles": {"group_admin", "member"},
        "requires": ("is_invitee",),
    },
    # Approval must come from somebody who is currently ACTIVE in the group and
    # who is not the requester. `is_group_member` is what actually refuses the
    # escalation today: a link redeemer holds an INVITED row, and INVITED is not
    # ACTIVE, so they fail the first predicate before the second is consulted.
    #
    # `is_not_self` is therefore redundant right now, and honestly so: deleting
    # it from this tuple breaks no test, because the partial unique index
    # `uq_memberships_open_per_person` makes the state it guards unreachable --
    # one person cannot hold both an ACTIVE row and an open INVITED row in the
    # same group. It is kept as the predicate that would still stand if that
    # index were ever relaxed, which is exactly the assumption rd-be-08 made
    # about `is_invitee` and got wrong. Do not read it as tested.
    "approve_link_join_request": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member", "is_not_self"),
    },
    "leave_context": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member", "is_self"),
    },
    "view_context_members": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    "post_group_message": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    "view_group_messages": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    "invoke_group_companion": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    # F32. A proactive suggestion is built from this group's own history --
    # where they went, what it cost, what kind of place they keep choosing --
    # so reading one is reading the group's past. Same ACTIVE gate as the
    # memory wall it is derived from: `is_group_member` is satisfied only by an
    # ACTIVE row, so an INVITED link holder cannot pull a group's history out
    # through a card that was never addressed to them.
    "view_group_suggestion": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    # F31. The implicit profile is the most concentrated thing the product
    # knows about a group: what they eat, what they do, and what they spend,
    # in one screen. It is derived from exactly the rows `view_group_memories`
    # guards, so it reuses that predicate rather than minting a softer one --
    # a profile is not "less private than the check-ins it was computed from"
    # merely because it arrives as scores instead of rows.
    "view_group_preference_profile": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    # F33. Reading this card means the server read the group's last few
    # messages. The gate is therefore the message gate, not a weaker one:
    # anyone who may not read the conversation may not read a card built out
    # of it either.
    "view_contextual_suggestion": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    # F36. An album is a way of reading photographs that already exist, so its
    # gate is deliberately the identical predicate the photo route uses. A
    # looser one here would make the album a way around that route -- which is
    # the whole failure mode a "collection" feature invites.
    "view_trip_album": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    # F43, F44, F45. All three read or answer about where the group goes, and
    # all three reuse `is_group_member` rather than minting a predicate: the
    # fact needed is identical to the one `view_group_memories` proves, because
    # the map and the heatmap are aggregations of exactly those rows. #128 was
    # the cost of two predicate names for one fact, and a "may_see_locations"
    # here would be that mistake with a location attached.
    #
    # Three actions rather than one, though, because they have different
    # subjects: two read the group's own history, and the third reads none of
    # it. Keeping them separate is what lets the map be withdrawn later without
    # also withdrawing a feature that never touched history.
    "view_social_map": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    "view_group_heatmap": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    # Meet-in-the-middle reads no stored location at all -- the caller supplies
    # unlabelled areas; see `app/places/meeting.py`. The gate is still ACTIVE
    # membership, because the answer is scored against the group's profile and a
    # former member should not keep a working group-planning endpoint.
    "view_meeting_point": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    # F34 carries the group's historical and current ledger totals. A context
    # id from a link is not authority to read them; only an ACTIVE row is.
    "view_group_budget": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    "post_group_memory": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    "view_group_memories": {
        "roles": {"group_admin", "member"},
        "requires": ("is_group_member",),
    },
    # Administration is scoped to one group, so `is_group_admin` must come
    # from that group's active membership row. X-Actor-Roles cannot prove
    # which group its broad `group_admin` claim applies to.
    "set_member_role": {
        "roles": {"group_admin"},
        "requires": ("is_group_admin",),
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
