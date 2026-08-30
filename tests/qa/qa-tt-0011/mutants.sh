#!/usr/bin/env bash
# Does this directory's gate go red, in the right tier, for the right reason?
#
# Rewritten with the fix. The original table was written while the hole was
# open, so its rows APPLIED the fix and demanded the `xfail(strict=True)`
# stakes flip. The stakes are gone now -- removing them was the second half of
# the fix -- so the rows below REMOVE the fix instead and demand the plain
# assertions go red.
#
# Two things changed underneath it, and both are why this file could not simply
# be left alone:
#
#   * Row 2's anchor quoted `create_bill`'s permission check as
#     `request.context_id in actor.context_ids`. `#253` replaced that with
#     `self.repository.is_member(...)` AFTER this table was written, so the
#     anchor matched nothing. The script's own no-op guard would have caught it
#     -- but only for somebody who ran it; anchored mutations rot silently.
#
#   * A third layer had to be added. `split_bill`'s fallback is no longer
#     reachable through any route: `_bill_for_actor` requires `is_member`
#     (ACTIVE, not left), and a context with such a member has a non-empty
#     roster. That was also `#253`, and it closed the route by accident from a
#     different door. Restoring the fallback therefore leaves BOTH tiers of
#     this directory green, which would read as "nothing guards this" -- the
#     honest answer is that what guards it is the service-level case in
#     `services/api/tests/api/test_split_does_not_invent_participants.py`,
#     so that file is a layer here.
#
# Four rows, and each answers a different question:
#
#   1 `guard removed from confirm_bill_assignments` -- fake RED, live GREEN,
#     unit GREEN. The positive control must actually depend on the guard
#     existing, or the contrast this directory rests on is unmeasured.
#
#   2 `guard removed from create_bill` -- fake RED, live GREEN, unit GREEN.
#     Half the fix, undone: the storage half. `POST /bills` stores a stranger's
#     share again and the fake tier must say so. The live tier does NOT, and
#     that is not a gap -- its stranger never gets past `create_bill`'s actor
#     check in the first place, so it has nothing left to observe.
#
#   3 `fallback restored in split_bill` -- fake GREEN, live GREEN, unit RED.
#     The other half, undone: the money half. Only the third layer sees it.
#     This row is the whole reason that layer exists, and it is the row that
#     proves the layers measure different things rather than being one
#     assertion written three times.
#
#   4 `suggested ids sorted (property unchanged)` -- ALL THREE GREEN. Sorting
#     the ids cannot change who is in the group. A table whose every row is red
#     cannot distinguish "the gate measures the property" from "the gate
#     notices that somebody touched the file".
#
# Run from anywhere. Restores the tree after every mutant -- which is why the
# commit has to exist first: `git checkout --` throws away an uncommitted fix
# along with the mutation.
set -uo pipefail

cd "$(dirname "$0")/../../.." || exit 1
TARGET=services/api/app/api/service.py
GATE=tests/qa/qa-tt-0011
FAKE="$GATE/test_bill_moi_ghi_nguoi_la_vao_mon.py"
LIVE="$GATE/test_split_tra_tien_cho_nguoi_la_postgres.py"
UNIT=services/api/tests/api/test_split_does_not_invent_participants.py

if ! git diff --quiet -- "$TARGET"; then
  echo "REFUSING: $TARGET has uncommitted changes; commit first." >&2
  exit 1
fi

# A database of this lane's own. The shared one carries other lanes' alembic
# revisions, and stamping it is how a worktree ends up unable to migrate.
: "${MOBILE_TEST_DATABASE_URL:=postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/qatt0011}"
PG_ENV=(
  "MOBILE_TEST_DATABASE_URL=$MOBILE_TEST_DATABASE_URL"
  "MOBILE_REQUIRE_POSTGRES_TESTS=1"
)

restore() { git checkout -- "$TARGET"; }
trap restore EXIT

run_layer() { # <label> <path>
  local label=$1 path=$2 out rc
  out=$(env "${PG_ENV[@]}" python3 -m pytest "$path" -q 2>&1)
  rc=$?
  # Only the final summary line. Grepping the whole body reads a docstring that
  # happens to contain the word "passed" as if it were a result.
  printf '    %-6s rc=%d  %s\n' "$label" "$rc" "$(printf '%s' "$out" | tail -n 1)"
  return $rc
}

FAILURES=0

mutant() { # <name> <python-patcher> <expect_fake> <expect_live> <expect_unit>
  local name=$1 patcher=$2 want_fake=$3 want_live=$4 want_unit=$5
  echo "== $name"
  python3 - "$TARGET" <<PY || { echo "    PATCH FAILED"; restore; FAILURES=$((FAILURES+1)); return 1; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text()
$patcher
p.write_text(s)
PY
  if git diff --quiet -- "$TARGET"; then
    # A patch that matched nothing reports the clean tree's numbers, which
    # reads exactly like a gate that caught the mutation.
    echo "    PATCH WAS A NO-OP -- rc below says nothing about the gate"
    restore; FAILURES=$((FAILURES+1)); return 1
  fi

  local fake_state live_state unit_state
  run_layer fake "$FAKE" && fake_state=green || fake_state=red
  run_layer live "$LIVE" && live_state=green || live_state=red
  run_layer unit "$UNIT" && unit_state=green || unit_state=red
  restore

  if [[ $fake_state == "$want_fake" && $live_state == "$want_live" \
        && $unit_state == "$want_unit" ]]; then
    echo "    OK   fake=$fake_state live=$live_state unit=$unit_state"
  else
    echo "    MISS fake=$fake_state live=$live_state unit=$unit_state" \
         "(wanted fake=$want_fake live=$want_live unit=$want_unit)"
    FAILURES=$((FAILURES+1))
  fi
}

echo "# baseline -- unmutated tree: all three layers green"
run_layer fake "$FAKE" || FAILURES=$((FAILURES+1))
run_layer live "$LIVE" || FAILURES=$((FAILURES+1))
run_layer unit "$UNIT" || FAILURES=$((FAILURES+1))
echo

# 1. The guard the positive control depends on, deleted. The fake tier must
#    notice; the other two never touch that door and must not.
mutant "guard removed from confirm_bill_assignments" '
old = """        self._require_participants_are_members(
            record.context_id,
            [
                participant_id
                for assignment in request.assignments
                for participant_id in assignment.participant_ids
            ],
        )
"""
assert old in s, "call site not found"
assert s.count(old) == 1, "anchor is not unique"
s = s.replace(old, "", 1)
' red green green

# 2. HALF THE FIX, UNDONE: the storage half. `POST /bills` accepts a stranger
#    again. Anchored on the guard itself rather than on the permission check
#    above it, so `#253`-style edits to that check cannot rot this row.
#
#    The live column went from green to red here when the tier gained a case
#    that actually reaches this guard. While it was green, this row said the
#    guard could be deleted and the PostgreSQL tier would not notice.
mutant "guard removed from create_bill (storage half)" '
old = """        self._require_participants_are_members(
            request.context_id,
            [
                participant_id
                for item in request.items
                for participant_id in item.suggested_participant_ids
            ],
        )
"""
assert old in s, "create_bill guard not found"
assert s.count(old) == 1, "anchor is not unique"
s = s.replace(old, "", 1)
' red red green

# 3. THE OTHER HALF, UNDONE: the money half. Only the service-level layer can
#    see this, because no route reaches the branch any more.
mutant "fallback restored in split_bill (money half)" '
old = """        participant_ids = {
            membership.person_id
            for membership in self.repository.list_members(record.context_id)
            if membership.state == "active"
        }
"""
new = old + """        if not participant_ids:
            participant_ids = {
                share.participant_id for item in record.items for share in item.shares
            }
"""
assert old in s, "roster block not found"
assert s.count(old) == 1, "anchor is not unique"
s = s.replace(old, new, 1)
' green green red

# 4. PROPERTY PRESERVED, CALL CHANGED. Sorting the suggested ids cannot alter
#    who belongs to the group, so all three layers must stay GREEN. A red here
#    would mean these cases are pinned to the order the client happened to send.
mutant "suggested ids sorted (property unchanged)" '
old = """                        "suggested_participant_ids": list(
                            item.suggested_participant_ids
                        ),
"""
new = """                        "suggested_participant_ids": sorted(
                            item.suggested_participant_ids,
                            key=lambda value: value.bytes,
                        ),
"""
assert old in s, "mapping not found"
assert s.count(old) == 1, "anchor is not unique"
s = s.replace(old, new, 1)
' green green green

# 5. THE ACTOR CHECK `#253` PUT ON `create_bill`, REMOVED. The two empty-roster
#    cases are pinned to this door: without it the payer gets in, and the
#    refusal they name stops happening. Before those cases asserted a door this
#    row was GREEN on the live tier -- which is what made the tier inert.
#
#    The anchor carries the whole `def` line. `is_member(request.context_id,
#    actor.id)` alone appears twice in this file, and a `.replace(..., 1)` on it
#    lands on whichever came first rather than on the door being tested.
mutant "actor check removed from create_bill" '
old = """    def create_bill(self, request: BillCreateRequest, actor: Actor) -> BillResponse:
        _require_permission(
            \"confirm_expense_proposal\",
            actor,
            {
                \"is_group_member\": self.repository.is_member(
                    request.context_id, actor.id
                )
            },
        )"""
assert old in s, "create_bill head not found"
assert s.count(old) == 1, "anchor is not unique"
s = s.replace(old, old.replace("""self.repository.is_member(
                    request.context_id, actor.id
                )""", "True"), 1)
' green red green

# 6. THE ACTOR CHECK ON THE READ PATH `split_bill` GOES THROUGH. This is what
#    makes an emptied roster a refusal instead of a trip into the allocator, so
#    it is the door the emptied-roster case names. Same anchoring rule as row 5.
mutant "actor check removed from _bill_for_actor" '
old = """    def _bill_for_actor(self, bill_id: uuid.UUID, actor: Actor) -> BillRecord:
        record = self.repository.get_bill(bill_id)
        if record is None:
            raise ApiProblem(404, \"bill_not_found\", \"Bill does not exist\")
        _require_permission(
            \"confirm_expense_proposal\",
            actor,
            {\"is_group_member\": self.repository.is_member(record.context_id, actor.id)},
        )"""
assert old in s, "_bill_for_actor not found"
assert s.count(old) == 1, "anchor is not unique"
s = s.replace(old, old.replace(
    "self.repository.is_member(record.context_id, actor.id)", "True"), 1)
' green red green

echo
if [[ $FAILURES -eq 0 ]]; then
  echo "ALL ROWS AS EXPECTED"
else
  echo "$FAILURES ROW(S) NOT AS EXPECTED"
fi
exit $FAILURES
