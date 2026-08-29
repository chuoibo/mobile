#!/usr/bin/env bash
# Does the gate on `confirm_bill_assignments` actually go red, and in the right
# layer?
#
# Red-green on the new tests already happened once, by hand, before the fix
# existed. This script is the part that survives: it re-runs on demand, so the
# claim "the bill path is gated" stays checkable after somebody edits the
# service six weeks from now.
#
# Two rows carry the argument.
#
#   `state filter ignored at this call site` must leave the fake layer GREEN
#   and turn the live layer RED. The fake's roster answers `state="active"` for
#   every row it holds, so an invited person is indistinguishable from a member
#   there -- that row is the reason `tests/postgres` is not decoration here.
#
#   `ids sorted before the check` must leave BOTH layers GREEN. A table where
#   every mutation is red cannot tell "the gate works" from "the gate is
#   welded to an incidental detail". This row changes the call without changing
#   the property, and a red here would mean the tests are pinned to list order
#   rather than to who is in the group.
#
# Run from anywhere. Restores the tree after every mutant -- the commit has to
# exist first, or `git checkout --` throws the fix away with the mutation.
set -uo pipefail

cd "$(dirname "$0")/../../../services/api" || exit 1
TARGET=app/api/service.py
FAKE="tests/api/test_bill_participants_must_be_members.py"
LIVE="tests/postgres/test_expense_participant_membership_postgres.py"

if ! git diff --quiet -- "$TARGET"; then
  echo "REFUSING: $TARGET has uncommitted changes; commit first." >&2
  exit 1
fi

# A database of this lane's own. The shared one carries other lanes' alembic
# revisions, and stamping it is how a worktree ends up unable to migrate.
: "${MOBILE_TEST_DATABASE_URL:=postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/rdbe24}"
PG_ENV=(
  "MOBILE_TEST_DATABASE_URL=$MOBILE_TEST_DATABASE_URL"
  "MOBILE_REQUIRE_POSTGRES_TESTS=1"
)

restore() { git checkout -- "$TARGET"; }
trap restore EXIT

run_layer() { # <label> <paths...>
  local label=$1; shift
  local out rc
  out=$(env "${PG_ENV[@]}" python3 -m pytest "$@" -q 2>&1)
  rc=$?
  # Only the final summary line. Grepping the whole body reads a docstring
  # that happens to contain "passed" as a result.
  printf '    %-6s rc=%d  %s\n' "$label" "$rc" "$(printf '%s' "$out" | tail -n 1)"
  return $rc
}

FAILURES=0

mutant() { # <name> <python-patcher> <expect_fake:red|green> <expect_live:red|green>
  local name=$1 patcher=$2 want_fake=$3 want_live=$4
  echo "== $name"
  python3 - "$TARGET" <<PY || { echo "    PATCH FAILED"; restore; FAILURES=$((FAILURES+1)); return 1; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text()
$patcher
p.write_text(s)
PY
  if git diff --quiet -- "$TARGET"; then
    # A patch that matched nothing reports the clean tree's numbers. That reads
    # exactly like a gate that caught the mutation.
    echo "    PATCH WAS A NO-OP -- the mutation never applied, so rc below means nothing"
    restore; FAILURES=$((FAILURES+1)); return 1
  fi

  local fake_state live_state
  run_layer fake "$FAKE" && fake_state=green || fake_state=red
  run_layer live "$LIVE" && live_state=green || live_state=red
  restore

  if [[ $fake_state == "$want_fake" && $live_state == "$want_live" ]]; then
    echo "    OK   fake=$fake_state live=$live_state (wanted fake=$want_fake live=$want_live)"
  else
    echo "    MISS fake=$fake_state live=$live_state (wanted fake=$want_fake live=$want_live)"
    FAILURES=$((FAILURES+1))
  fi
}

echo "# baseline -- unmutated tree must be green on both layers"
run_layer fake "$FAKE" || FAILURES=$((FAILURES+1))
run_layer live "$LIVE" || FAILURES=$((FAILURES+1))
echo

# The anchor every mutation below shares. Kept in one place because
# `_require_participants_are_members(` appears twice in this file, and a
# `.replace(..., 1)` that lands on `confirm_expense` instead would report green
# while the guard under test sat untouched.
GUARD='        self._require_participants_are_members(
            record.context_id,
            [
                participant_id
                for assignment in request.assignments
                for participant_id in assignment.participant_ids
            ],
        )
'

# 1. The gate deleted outright. Both layers must notice; if either stays green
#    it is not testing this call site at all.
mutant "guard removed from confirm_bill_assignments" '
old = """'"$GUARD"'"""
assert old in s, "call site not found"
assert s.count(old) == 1, "anchor is not unique"
s = s.replace(old, "", 1)
' red red

# 2. The call kept, the argument emptied. This is the shape a refactor produces:
#    the line still reads like a membership check in review.
mutant "guard called with no ids" '
old = """'"$GUARD"'"""
new = """        self._require_participants_are_members(record.context_id, [])
"""
assert old in s, "call site not found"
s = s.replace(old, new, 1)
' red red

# 3. Only the last assignment checked. A plausible loop bug, and the reason the
#    fake layer bothers with two items: the live case sends one item, so the
#    fake is the only layer that can see this.
mutant "only the last assignment is checked" '
old = """'"$GUARD"'"""
new = """        self._require_participants_are_members(
            record.context_id, list(request.assignments[-1].participant_ids)
        )
"""
assert old in s, "call site not found"
s = s.replace(old, new, 1)
' red green

# 4. THE ROW THAT PAYS FOR THE LIVE TIER. The roster is still read and strangers
#    are still refused -- but `state` is ignored, so a person who was invited
#    and never accepted is treated as a member. The fake cannot fail this: every
#    row it returns already reads active.
mutant "state filter ignored at this call site" '
old = """'"$GUARD"'"""
new = """        _roster = {
            m.person_id for m in self.repository.list_members(record.context_id)
        }
        _named = [
            participant_id
            for assignment in request.assignments
            for participant_id in assignment.participant_ids
        ]
        _strangers = sorted(
            {p for p in _named if p not in _roster}, key=lambda value: value.bytes
        )
        if _strangers:
            raise ApiProblem(
                422,
                "participant_not_in_context",
                "Not members of this group: "
                + ", ".join(str(stranger) for stranger in _strangers),
            )
"""
assert old in s, "call site not found"
s = s.replace(old, new, 1)
' green red

# 5. PROPERTY PRESERVED, CALL CHANGED. Sorting the ids before the check cannot
#    alter who is in the group. Both layers must stay GREEN. A red here would
#    mean these tests are pinned to the order the client happened to send, not
#    to membership -- which is the failure mode a table of all-red rows hides.
mutant "ids sorted before the check (property unchanged)" '
old = """'"$GUARD"'"""
new = """        self._require_participants_are_members(
            record.context_id,
            sorted(
                (
                    participant_id
                    for assignment in request.assignments
                    for participant_id in assignment.participant_ids
                ),
                key=lambda value: value.bytes,
            ),
        )
"""
assert old in s, "call site not found"
s = s.replace(old, new, 1)
' green green

echo
if [[ $FAILURES -eq 0 ]]; then
  echo "ALL ROWS AS EXPECTED"
else
  echo "$FAILURES ROW(S) NOT AS EXPECTED"
fi
exit $FAILURES
