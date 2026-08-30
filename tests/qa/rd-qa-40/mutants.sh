#!/usr/bin/env bash
# rd-qa-40 -- is each cell of the matrix what it claims to be?
#
# The audit table has three kinds of cell, and reading code cannot tell them
# apart. This script can:
#
#   GATED      -- a check exists in service.py. Deleting it must turn this
#                 directory RED. If it stays green the "gate" is decoration.
#   ELSEWHERE  -- service.py has no check because a layer below holds the
#                 property. Deleting the check *there* must turn this directory
#                 RED. That is what makes the blank cell an equivalent mutation
#                 rather than a hole -- the distinction #129 nearly got wrong,
#                 and the one this lane was told not to repeat.
#   UNCHANGED  -- a mutation that keeps the property while changing the code.
#                 Must stay GREEN. A table where every row is red cannot tell
#                 "the gate works" from "the tests are welded to an incidental
#                 detail", so these rows are what make the red ones mean
#                 something.
#
# All four holes this file opened are now closed, so none of them is carried
# as `xfail(strict=True)` any more and each has real rows below:
#
#   hole 3, suggested_participant_ids -> gated by #260 in `create_bill`
#   hole 1, paid_by_id                -> gated by rd-be-26 in `confirm_expense`
#   hole 2, recorded_by_id            -> gated by rd-be-26 in `confirm_expense`
#   hole 4, outing invite person_id   -> gated by rd-be-26 in
#                                        `create_outing_invite`, for
#                                        `source="group"` only
#
# Hole 4 is the one that needs a gate in BOTH directions. The other three have
# no legitimate caller naming an outsider, so "refuse harder" is always safer
# there. This one does: a `friend` invite exists precisely to name somebody the
# group does not contain, so a guard that over-refuses passes every red row
# below while deleting a feature. That is what the widened-condition row is
# for.
#
# Holes 1 and 2 were fixed at a single call site by widening the argument, not
# by adding a second check. That makes "delete the call" too coarse to mean
# much on its own -- it reds for the `participants` gate that was already there
# -- so the two rows that drop ONE argument each are the ones carrying the
# claim.
#
# Run from anywhere. Restores the tree after every mutant -- so the tree must be
# committed first, or `git checkout --` throws real work away with the mutation.
set -uo pipefail

cd "$(dirname "$0")/../../.." || exit 1
SERVICE=services/api/app/api/service.py
REPOSITORY=services/api/app/api/repository.py
ALLOCATOR=services/api/app/domain/allocator.py
SUITE=tests/qa/rd-qa-40
# The fourth hole's gate lives in the backend lane's own live tier, and it has
# to be mutated by the SAME table as the other three: one shape, one place that
# says whether each cell is real. It runs from `services/api` rather than the
# repo root because that is where the `pythonpath` in `pyproject.toml` comes
# from -- handing pytest both paths under one rootdir loses it and every case
# dies on `No module named 'app'`, which scores as a caught mutation.
LANE_SUITE=tests/postgres/test_outing_invite_source_must_match_roster.py

for target in "$SERVICE" "$REPOSITORY" "$ALLOCATOR"; do
  if ! git diff --quiet -- "$target"; then
    echo "REFUSING: $target has uncommitted changes; commit first." >&2
    exit 1
  fi
done

# A database of this lane's own. The shared one carries other lanes' alembic
# revisions, and stamping it is how a worktree ends up unable to migrate.
: "${MOBILE_TEST_DATABASE_URL:=postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/rdqa40}"
PG_ENV=(
  "MOBILE_TEST_DATABASE_URL=$MOBILE_TEST_DATABASE_URL"
  "MOBILE_REQUIRE_POSTGRES_TESTS=1"
)

restore() { git checkout -- "$SERVICE" "$REPOSITORY" "$ALLOCATOR"; }
trap restore EXIT

FAILURES=0

run_suite() {
  local out rc lane_out lane_rc
  out=$(env "${PG_ENV[@]}" python3 -m pytest "$SUITE" -q -p no:warnings 2>&1)
  rc=$?
  lane_out=$(cd services/api && env "${PG_ENV[@]}" \
    python3 -m pytest "$LANE_SUITE" -q -p no:warnings 2>&1)
  lane_rc=$?
  # Only the final summary line of each. Grepping the whole body reads a
  # docstring that happens to contain the word "passed" as if it were a result.
  printf '    rc=%d  %s   | lane rc=%d  %s\n' \
    "$rc" "$(printf '%s' "$out" | tail -n 1)" \
    "$lane_rc" "$(printf '%s' "$lane_out" | tail -n 1)"
  # A row is red if EITHER tier refuses. Returning only the first would let a
  # mutation that only the lane tier can see report green.
  if [[ $rc -ne 0 || $lane_rc -ne 0 ]]; then return 1; fi
  return 0
}

mutant() { # <kind> <name> <file> <python-patcher> <expect:red|green>
  local kind=$1 name=$2 file=$3 patcher=$4 want=$5
  echo "== [$kind] $name"
  python3 - "$file" <<PY || { echo "    PATCH FAILED"; restore; FAILURES=$((FAILURES+1)); return 1; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text()
$patcher
p.write_text(s)
PY
  if git diff --quiet -- "$file"; then
    # A patch that matched nothing reports the clean tree's numbers, which reads
    # exactly like a gate that caught the mutation.
    echo "    PATCH WAS A NO-OP -- rc below means nothing"
    restore; FAILURES=$((FAILURES+1)); return 1
  fi

  local state
  run_suite && state=green || state=red
  restore

  if [[ $state == "$want" ]]; then
    echo "    OK   $state (wanted $want)"
  else
    echo "    MISS $state (wanted $want)"
    FAILURES=$((FAILURES+1))
  fi
}

echo "# baseline -- unmutated tree, 18 passed"
run_suite || FAILURES=$((FAILURES+1))
echo

# --- GATED cells ------------------------------------------------------------

# `_require_participants_are_members(` is called from three places in
# service.py now (#235 confirm_expense, #247 confirm_bill_assignments, #260
# create_bill). Anchoring on the whole call, not the function name, so a
# `.replace(..., 1)` cannot land on the wrong one and report green while the
# guard under test sits untouched.
mutant GATED "confirm_expense: whole guard removed (#235 + rd-be-26)" "$SERVICE" '
old = """        self._require_participants_are_members(
            identity.context_id,
            [
                *request.proposal.participants,
                request.proposal.paid_by_id,
                request.proposal.recorded_by_id,
            ],
        )
"""
assert s.count(old) == 1, "confirm_expense call site is not unique"
s = s.replace(old, "", 1)
' red

# The two rows below are why the one above is not enough. Deleting the whole
# call proves the suite reacts to SOME change at this site; it cannot tell
# which of the three id sources is actually gated. Each row drops exactly one
# argument and leaves the other two in place, so a green here names the id
# nobody is checking.
mutant GATED "confirm_expense: paid_by_id dropped from the guard (rd-be-26 hole 1)" "$SERVICE" '
old = """                request.proposal.paid_by_id,
"""
assert s.count(old) == 1, "paid_by_id argument is not unique"
s = s.replace(old, "", 1)
' red

mutant GATED "confirm_expense: recorded_by_id dropped from the guard (rd-be-26 hole 2)" "$SERVICE" '
old = """                request.proposal.recorded_by_id,
"""
assert s.count(old) == 1, "recorded_by_id argument is not unique"
s = s.replace(old, "", 1)
' red

mutant GATED "confirm_bill_assignments: guard removed (#247)" "$SERVICE" '
old = """        self._require_participants_are_members(
            record.context_id,
            [
                participant_id
                for assignment in request.assignments
                for participant_id in assignment.participant_ids
            ],
        )
"""
assert s.count(old) == 1, "confirm_bill_assignments call site is not unique"
s = s.replace(old, "", 1)
' red

mutant GATED "set_bank_recipient: is_own_account dropped" "$SERVICE" '
old = """                \"is_own_account\": actor.id == request.recipient_id,"""
assert s.count(old) == 1, "predicate not found"
s = s.replace(old, """                \"is_own_account\": True,""", 1)
' red

mutant GATED "invite_context_member: registration check removed" "$SERVICE" '
old = """        self._require_registered_person(request.person_id)
"""
assert s.count(old) == 1, "call site not unique"
s = s.replace(old, "", 1)
' red

mutant GATED "send_friend_request: addressee existence check removed" "$SERVICE" '
old = """        if self.repository.get_person(addressee_id) is None:
            raise ApiProblem(404, \"person_not_found\", \"Chưa có ai mang danh tính này.\")
"""
assert s.count(old) == 1, "existence check not found"
s = s.replace(old, "", 1)
' red

mutant GATED "create_outing_invite: source=group roster check removed (rd-be-26 hole 4)" "$SERVICE" '
old = """            if request.source == \"group\":
                self._require_participants_are_members(
                    outing.context_id, [request.person_id]
                )
"""
assert s.count(old) == 1, "outing-invite roster check is not unique"
s = s.replace(old, "", 1)
' red

mutant GATED "create_outing_invite: registered-person check removed" "$SERVICE" '
old = """            self._require_registered_person(request.person_id)
"""
assert s.count(old) == 1, "outing-invite registration check is not unique"
s = s.replace(old, "", 1)
' red

# The row that keeps this gate HONEST in the other direction. Every row above
# asks "does it refuse?". A guard that refused EVERYTHING would pass all of
# them while deleting friend invites -- the feature whose entire purpose is
# naming somebody outside the group. Widening the condition to cover `friend`
# must therefore be RED, and it is red in the lane tier only, which is why
# `run_suite` reads both return codes.
mutant GATED "create_outing_invite: roster check widened to friend invites too" "$SERVICE" '
old = """            if request.source == \"group\":"""
assert s.count(old) == 1, "source condition is not unique"
s = s.replace(old, """            if request.source in (\"group\", \"friend\"):""", 1)
' red

# --- ELSEWHERE cells: blank in service.py, defended one layer down -----------

# shared_by. service.py copies it into the allocator input untouched. The reason
# that is safe is `_validate_shape`, which requires every sharer to be a
# participant -- and participants are roster-checked by the row above.
mutant ELSEWHERE "allocator: shared_by subset-of-participants check removed" "$ALLOCATOR" '
old = """            if participant not in participants:"""
assert s.count(old) == 1, "subset check not found"
s = s.replace(old, """            if False:""", 1)
' red

# expected_allocations. Its dict KEYS are person ids and they are stored
# verbatim, with no membership check anywhere. What refuses a smuggled key is
# the equality against the freshly recomputed proposal.
mutant ELSEWHERE "confirm_expense: recomputed-proposal comparison removed" "$SERVICE" '
old = """        if wire.allocations != request.expected_allocations:"""
assert s.count(old) == 1, "comparison not found"
s = s.replace(old, """        if False:""", 1)
' red

# set_context_member_role. The path person_id is never checked in service.py.
# The defence is the WHERE clause: no active membership, no row, and the service
# turns the None into 404. Only the live tier can see this -- the fake has no
# `membership_role` method at all, so the fake-tier cell is genuinely blind.
# The WHERE shape below appears five times in repository.py, so the anchor
# carries the `def` line with it. An anchor that matched a sibling method would
# report a colour belonging to a different guarantee -- red for the wrong
# reason reads exactly like red for the right one.
mutant ELSEWHERE "repository: set_membership_role stops filtering on ACTIVE" "$REPOSITORY" '
old = """    def set_membership_role(
        self, context_id: uuid.UUID, person_id: uuid.UUID, role: str
    ) -> MembershipRecord | None:
        membership = self.session.scalar(
            select(Membership)
            .where(
                Membership.context_id == context_id,
                Membership.person_id == person_id,
                Membership.state == MembershipState.ACTIVE,
                Membership.left_at.is_(None),
            )"""
assert s.count(old) == 1, "set_membership_role definition not unique"
s = s.replace(old, """    def set_membership_role(
        self, context_id: uuid.UUID, person_id: uuid.UUID, role: str
    ) -> MembershipRecord | None:
        membership = self.session.scalar(
            select(Membership)
            .where(
                Membership.context_id == context_id,
                Membership.person_id == person_id,
            )""", 1)
' red

# --- UNCHANGED cells: the property survives, so the suite must stay green ----

# Sorting the ids cannot change who is in the group. A red here would mean the
# cases are pinned to the order the client happened to send.
mutant UNCHANGED "confirm_expense: guard argument sorted and reordered" "$SERVICE" '
old = """            [
                *request.proposal.participants,
                request.proposal.paid_by_id,
                request.proposal.recorded_by_id,
            ],
"""
assert s.count(old) == 1, "call site is not unique"
s = s.replace(old, """            sorted(
                [
                    request.proposal.recorded_by_id,
                    request.proposal.paid_by_id,
                    *request.proposal.participants,
                ],
                key=lambda value: value.bytes,
            ),
""", 1)
' green

# The refusal message is rewritten while the refusal itself stands. If this goes
# red, the cases are asserting on prose rather than on behaviour.
mutant UNCHANGED "participant guard: refusal wording changed, code kept" "$SERVICE" '
old = """                \"Not members of this group: \""""
assert s.count(old) == 1, "message not found"
s = s.replace(old, """                \"Những người này không ở trong nhóm: \"""", 1)
' green

# Inside this branch `source` is `group` or `friend` -- `link` returned above --
# so testing for "not friend" selects exactly the same invites as testing for
# "is group". A red here would mean the cases are pinned to the spelling of the
# condition rather than to which invites get roster-checked.
mutant UNCHANGED "create_outing_invite: source condition spelled as not-friend" "$SERVICE" '
old = """            if request.source == \"group\":"""
assert s.count(old) == 1, "source condition is not unique"
s = s.replace(old, """            if request.source != \"friend\":""", 1)
' green

# The roster is read with a different but equivalent expression. Same set, same
# answer -- and unlike the ELSEWHERE row above, the `state` filter is KEPT.
mutant UNCHANGED "participant guard: roster built by loop instead of set-comp" "$SERVICE" '
old = """        roster = {
            membership.person_id
            for membership in self.repository.list_members(context_id)
            if membership.state == \"active\"
        }
"""
assert s.count(old) == 1, "roster comprehension not found"
s = s.replace(old, """        roster = set()
        for membership in self.repository.list_members(context_id):
            if membership.state == \"active\":
                roster.add(membership.person_id)
""", 1)
' green

echo
if [[ $FAILURES -eq 0 ]]; then
  echo "ALL ROWS AS EXPECTED"
else
  echo "$FAILURES ROW(S) NOT AS EXPECTED"
fi
exit $FAILURES
