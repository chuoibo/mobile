#!/usr/bin/env bash
# Does this directory's gate go red, in the right tier, for the right reason?
#
# The gate here is unusual: four of its cases are `xfail(strict=True)` stakes
# for a hole that is still open. A stake that can never flip is decoration, so
# the load-bearing rows below are the ones that CLOSE the hole and demand the
# stakes turn red -- a strict XPASS is a failure, which is how "remove the
# marker" becomes part of the fix rather than a note somebody forgets.
#
# Four rows, and each answers a different question:
#
#   1 `guard removed from confirm_bill_assignments` -- fake RED, live GREEN.
#     The positive control must actually depend on the guard existing. If this
#     stayed green, the contrast this whole directory rests on ("that door
#     refuses, this one does not") would be unmeasured.
#
#   2 `create_bill gated` -- BOTH tiers RED. This is the fix, applied. Both
#     stakes on each tier must flip. A row that stays green here means the
#     stake is inert and would sit in the tree forever reading like coverage.
#
#   3 `fallback removed from split_bill` -- fake GREEN, live RED. Half the fix.
#     The money half closes, the storage half stays open, and the two tiers
#     must disagree. This is the row that proves the tiers measure different
#     things rather than being one assertion written twice.
#
#   4 `suggested ids sorted (property unchanged)` -- BOTH tiers GREEN. Sorting
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

mutant() { # <name> <python-patcher> <expect_fake> <expect_live>
  local name=$1 patcher=$2 want_fake=$3 want_live=$4
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

  local fake_state live_state
  run_layer fake "$FAKE" && fake_state=green || fake_state=red
  run_layer live "$LIVE" && live_state=green || live_state=red
  restore

  if [[ $fake_state == "$want_fake" && $live_state == "$want_live" ]]; then
    echo "    OK   fake=$fake_state live=$live_state"
  else
    echo "    MISS fake=$fake_state live=$live_state (wanted fake=$want_fake live=$want_live)"
    FAILURES=$((FAILURES+1))
  fi
}

echo "# baseline -- unmutated tree: 3 passed 2 xfailed (fake), 3 passed 2 xfailed (live)"
run_layer fake "$FAKE" || FAILURES=$((FAILURES+1))
run_layer live "$LIVE" || FAILURES=$((FAILURES+1))
echo

# The anchor rows 2 and 4 share. `create_bill`'s permission check is quoted in
# full because `_require_permission("confirm_expense_proposal", ...)` also
# appears in `_bill_for_actor`, and a `.replace(..., 1)` landing there would
# report a colour for a call site nobody is testing.
CREATE_HEAD='    def create_bill(self, request: BillCreateRequest, actor: Actor) -> BillResponse:
        _require_permission(
            "confirm_expense_proposal",
            actor,
            {"is_group_member": request.context_id in actor.context_ids},
        )
'

# 1. The guard the positive control depends on, deleted. The fake tier must
#    notice; the live tier never touches that door and must not.
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
' red green

# 2. THE FIX, APPLIED. Every stake in this directory must flip to a strict
#    XPASS, i.e. red, on both tiers. This row is why the stakes are not inert.
mutant "create_bill gated (the fix)" '
old = """'"$CREATE_HEAD"'"""
new = old + """        self._require_participants_are_members(
            request.context_id,
            [
                participant_id
                for item in request.items
                for participant_id in item.suggested_participant_ids
            ],
        )
"""
assert old in s, "create_bill head not found"
assert s.count(old) == 1, "anchor is not unique"
s = s.replace(old, new, 1)
' red red

# 3. HALF THE FIX, and the row that pays for two tiers. Removing the fallback
#    stops the allocator from paying a stranger, so the live stakes flip -- but
#    `POST /bills` still stores the share, so the fake stakes stay xfail and
#    that tier stays green. One assertion written twice could not do this.
mutant "fallback removed from split_bill (money half only)" '
old = """        if not participant_ids:
            participant_ids = {
                share.participant_id for item in record.items for share in item.shares
            }
"""
assert old in s, "fallback not found"
assert s.count(old) == 1, "anchor is not unique"
s = s.replace(old, "", 1)
' green red

# 4. PROPERTY PRESERVED, CALL CHANGED. Sorting the suggested ids cannot alter
#    who belongs to the group, so both tiers must stay GREEN. A red here would
#    mean these cases are pinned to the order the client happened to send.
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
' green green

echo
if [[ $FAILURES -eq 0 ]]; then
  echo "ALL ROWS AS EXPECTED"
else
  echo "$FAILURES ROW(S) NOT AS EXPECTED"
fi
exit $FAILURES
