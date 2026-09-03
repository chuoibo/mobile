"""Every role a `prod` session cannot carry must be derived at its call site.

## Why this file exists

`publish_batch` asks for `batch_owner`. The service proved `owns_batch` from
the resource and then let the *role* arrive in `X-Actor-Roles`, which worked
for exactly as long as the client was believed. On a `prod` host nobody asserts
a role, so publishing answered 403 to the person who owns the batch: the hero
path of the whole product, dead.

Nothing in this repository caught it. Every case in `tests/api` and
`tests/postgres` sends the header, so all of them stayed green; it was found by
the prod-mode e2e slice, which is one expensive stage that runs late. This file
is the cheap structural version: it reads the permission table and the service
together and refuses a call site that depends on a role no session grants.

## What it checks

For each entry in `permissions._TABLE` whose roles are all outside
`SESSION_ROLES`, either

* no `_require_permission("<action>", ...)` call exists -- the action is
  declared but unreachable, and is listed in `UNREACHABLE` with a reason; or
* the call passes `extra_roles`, which is the codebase's one way of saying "the
  service derived this from the resource".

## What it does NOT check

That the derivation is *correct*. A call site passing
`extra_roles={"batch_owner"}` unconditionally would satisfy this file and would
hand the role to anybody; `owns_batch` is what stops that, and the tests for
each route are where it is proven. This gate is about a role having a source at
all, not about the source being right.

It also cannot see a role granted through a helper it does not recognise: it
matches the literal `extra_roles` in the call. That is deliberate -- a reader
looking for "where does this role come from" searches for the same string.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.domain import permissions

SERVICE = Path(__file__).resolve().parents[2] / "app" / "api" / "service.py"

#: What `SqlAlchemyApiRepository.actor_grants` puts on a session. Kept as a
#: literal rather than imported so that widening the grant is a decision made
#: in two places, one of which is a test that says why each role is there.
SESSION_ROLES = frozenset(
    {"member", "advancer", "recipient", "sender", "creditor", "former_member"}
)

#: Actions in the table that no route reaches. Declared and unimplemented is a
#: legitimate state -- the table is the spec -- but it must be stated, or an
#: action that becomes reachable later inherits this file's silence.
UNREACHABLE = {
    "close_dispute": "no route; no table says who moderates",
    "adjudicate_person_stub_claim": "no route; same",
    "remove_others_content": "no route; same",
    "manage_members_and_invites": "no route calls this action name",
    "remove_member_from_group": "no route; leaving is `leave_context`",
    "transfer_group_admin": "no route yet",
    "cancel_obligation": "no route; cancelling after publish is not built",
    "amend_obligation_after_publish": "no route; not built",
    "delete_payment_report": "declared to be refused, never called",
    "delete_receipt_confirmation": "declared to be refused, never called",
    "delete_audit_history": "declared to be refused, never called",
    "revoke_capability_whole_batch": "no route; only the two narrow revokes ship",
}


def _table() -> dict[str, dict]:
    return permissions._TABLE


def _actions_needing_derivation() -> list[str]:
    out = []
    for action, entry in _table().items():
        roles = frozenset(entry["roles"])
        if not roles:
            continue
        if roles & SESSION_ROLES:
            # Satisfiable by a session on its own; nothing to derive.
            continue
        if roles == {"guest"}:
            # A guest is a capability digest, built in `_guest_actor`, and is
            # never a person's session.
            continue
        out.append(action)
    return sorted(out)


def _call_sites(source: str) -> dict[str, str]:
    """Action -> the text of its `_require_permission` call."""

    sites: dict[str, str] = {}
    for match in re.finditer(r'_require_permission\(\s*\n?\s*"([a-z_0-9]+)"', source):
        action = match.group(1)
        # The call ends at the first line that closes it at the same depth.
        # Reading a fixed window is enough and avoids parsing Python here: no
        # call in this file is longer than this.
        sites[action] = source[match.start() : match.start() + 900]
    return sites


@pytest.fixture(scope="module")
def source() -> str:
    return SERVICE.read_text(encoding="utf-8")


def test_every_underivable_role_is_derived_or_declared_unreachable(source):
    sites = _call_sites(source)
    missing = []
    for action in _actions_needing_derivation():
        if action not in sites:
            assert action in UNREACHABLE, (
                f"`{action}` needs a role no session grants and no route calls it, "
                f"but it is not listed in UNREACHABLE. Add it with a reason, or "
                f"wire the route."
            )
            continue
        if "extra_roles" not in sites[action]:
            missing.append(action)

    assert not missing, (
        "these call sites depend on a role that `actor_grants` does not put on a "
        f"session, and do not derive it: {missing}. On a `prod` host they answer "
        "403 to the person entitled to act. Pass `extra_roles=` derived from the "
        "resource, the way `freeze_batch` and `publish_batch` do."
    )


def test_the_unreachable_list_does_not_go_stale(source):
    """An action that gains a route must leave the list, not sit in it.

    Without this the list is a place for a reachable action to hide: it would
    be excused by name forever, and the excuse says "no route".
    """

    sites = _call_sites(source)
    now_reachable = sorted(action for action in UNREACHABLE if action in sites)
    assert not now_reachable, (
        f"{now_reachable} are listed as unreachable but the service calls them. "
        "Remove them from UNREACHABLE and derive their roles at the call site."
    )


def test_the_unreachable_list_only_names_real_actions():
    unknown = sorted(action for action in UNREACHABLE if action not in _table())
    assert not unknown, (
        f"{unknown} are not in the permission table. A renamed action leaves its "
        "old name here excusing nothing, which is how this list rots."
    )
