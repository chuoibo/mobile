#!/usr/bin/env bash
# Mutation battery for the `server-routes` gate of PR #333, lượt hai.
#
# WHY THIS RUNS A SECOND TIME. The first battery (qa-tt-0033) ran on a tree the
# QA lane merged and conflict-resolved by hand, so it proved the gate's teeth on
# an artifact nobody would ever ship. #333 then merged `main` itself. A merge can
# blunt a reader without touching a line anyone reads -- so the teeth get
# re-checked on what the author actually pushed.
#
# HOW TO READ THE TABLE. Every mutant is applied to a GREEN baseline and reverted
# with `git checkout --` before the next one, one variable at a time. Without a
# green baseline every row prints "red" and the table cannot distinguish a gate
# that catches things from a gate that is simply always red -- which is why M0
# pins the six live findings first and aborts if it does not reach exit 0.
#
# M3 is the row that carries the table: it declares the SAME route as M1 but adds
# a real caller, and must go green. A gate that never goes green catches nothing.
#
# Usage:  dot-bien-lan-hai.sh [đường-dẫn-cây-đo]      (mặc định: thư mục hiện tại)
# Cây đo phải là một cây git sạch chứa #333 đã gộp lên main.
set -u
TREE="${1:-$PWD}"
cd "$TREE" || { echo "không vào được cây đo: $TREE" >&2; exit 9; }
git rev-parse --git-dir >/dev/null 2>&1 || { echo "$TREE không phải cây git" >&2; exit 9; }

OUT="${TMPDIR:-/tmp}/qa34-mut"
GATE="python3 scripts/check_server_routes_called.py"
PLACES=services/api/app/api/routes/places.py
TWIN=scripts/check_api_contract.py
API=apps/mobile/src/api.ts
DEBT=.server-routes-uncalled.json

restore() { git checkout -- "$PLACES" "$TWIN" "$API" "$DEBT" 2>/dev/null; }

# The six findings live on main (from #133 and #303), not in the PR. Pinning them
# is what turns the tree green so the mutants below mean something; it is thrown
# away by `restore` and is NOT a suggested fix.
pin_six() {
python3 - <<'PY'
import json
p = ".server-routes-uncalled.json"
d = json.load(open(p, encoding="utf-8"))
six = ["/contexts/{context_id}/votes", "/votes/{vote_id}",
       "/votes/{vote_id}/ballots", "/votes/{vote_id}/close",
       "/contexts/{context_id}/photos/{photo_id}/face-boxes",
       "/bills/{bill_id}/my-items"]
for r in six:
    d["uncalled"].append({"route": r, "reason": "GHIM TAM CUA QA de co nen XANH truoc khi dot bien -- khong phai ban de merge"})
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
}

run() { local out; out=$($GATE 2>&1); local rc=$?; printf '%s\n' "$out" > "$OUT-$1.txt"; echo "$rc"; }

echo "=================== NEN (baseline) ==================="
restore; pin_six
RC=$(run BASE)
echo "M0 nen (6 route ghim tam)              exit=$RC   $(grep -c route_khong_ai_goi "$OUT-BASE.txt") route do"
if [ "$RC" != "0" ]; then
  echo "NEN KHONG XANH -- bang duoi khong phan biet duoc gi. Dung."; sed -n '1,15p' "$OUT-BASE.txt"; restore; exit 1
fi

echo
echo "=================== DOT BIEN ==================="

# --- M1: server declares a route no screen calls ----------------------------
restore; pin_six
cat >> "$PLACES" <<'EOF'


@router.get("/canary-m1-khong-ai-goi")
def _canary_m1_khong_ai_goi() -> dict:
    """QA mutant: a route no screen calls."""
    return {}
EOF
RC=$(run M1)
grep -q 'canary-m1-khong-ai-goi' "$OUT-M1.txt" && N=NEU_TEN || N=KHONG_NEU_TEN
echo "M1 route moi khong ai goi              exit=$RC   $N"

# --- M3: same route, with a real caller (POSITIVE CONTROL) ------------------
restore; pin_six
cat >> "$PLACES" <<'EOF'


@router.get("/canary-m1-khong-ai-goi")
def _canary_m1_khong_ai_goi() -> dict:
    """QA mutant: a route no screen calls."""
    return {}
EOF
cat >> "$API" <<'EOF'

// QA mutant M3: a real path literal, in code, not in a comment.
export const M3_PROBE_PATH = "/canary-m1-khong-ai-goi";
EOF
RC=$(run M3)
echo "M3 CUNG route nhung CO nguoi goi       exit=$RC   (doi chung duong: phai 0)"

# --- M4: break the client reader --------------------------------------------
restore; pin_six
python3 - <<'PY'
p = "scripts/check_api_contract.py"
s = open(p, encoding="utf-8").read()
old = "def tokenize(src: str) -> list[Token]:\n"
assert s.count(old) == 1, s.count(old)
open(p, "w", encoding="utf-8").write(s.replace(old, old + "    return []  # QA mutant M4\n"))
PY
RC=$(run M4)
grep -q 'không đọc được đường dẫn API' "$OUT-M4.txt" && N=TU_CHOI || N=IM_LANG
echo "M4 pha bo doc client (tokenize=[])     exit=$RC   $N"

# --- M5: break the server denominator ---------------------------------------
restore; pin_six
python3 - <<'PY'
p = "scripts/check_api_contract.py"
s = open(p, encoding="utf-8").read()
old = "def load_openapi() -> dict:\n"
assert s.count(old) == 1, s.count(old)
open(p, "w", encoding="utf-8").write(s.replace(old, old + '    return {"paths": {}}  # QA mutant M5\n'))
PY
RC=$(run M5)
grep -q 'không có route nào' "$OUT-M5.txt" && N=TU_CHOI || N=IM_LANG
echo "M5 pha mau so may chu (paths={})       exit=$RC   $N"

# --- M7: delete a REAL caller of a live hero route ---------------------------
# `replace` with no count: api.ts holds TWO copies of "/expenses". Patching one
# and reading the red as "caught" is how a blind gate reads as a sighted one.
restore; pin_six
python3 - <<'PY'
p = "apps/mobile/src/api.ts"
s = open(p, encoding="utf-8").read()
n = s.count('"/expenses"')
assert n >= 1, n
s = s.replace('"/expenses"', '"/khong-con-goi-nua-m7"')
s = s.replace("`/expenses/${proposal.expenseId}/confirm`", "`/khong-con-goi-nua-m7/${proposal.expenseId}/confirm`")
open(p, "w", encoding="utf-8").write(s)
print("da thay", n, 'ban sao cua "/expenses"')
PY
RC=$(run M7)
grep -q '^/expenses  \[route_khong_ai_goi\]' "$OUT-M7.txt" && N=NEU_TEN || N=KHONG_NEU_TEN
echo "M7 go nguoi goi that cua /expenses     exit=$RC   $N"

# --- M8: a debt line pointing at a route the server never declares -----------
# Non-fatal by design (deleting a dead route is the outcome this gate wants).
# The property under test is that it is NOT swallowed silently.
restore; pin_six
python3 - <<'PY'
import json
p = ".server-routes-uncalled.json"
d = json.load(open(p, encoding="utf-8"))
d["uncalled"].append({"route": "/route-may-chu-khong-he-khai-m8",
                      "reason": "QA mutant M8: mot dong no tro vao hu khong"})
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
RC=$(run M8)
grep -q 'route-may-chu-khong-he-khai-m8' "$OUT-M8.txt" && N=NEU_TEN || N=NUOT_IM_LANG
echo "M8 dong no tro vao route khong ton tai exit=$RC   $N"

restore
echo
echo "=== cay da khoi phuc (rong = sach) ==="
git status --short | head -5
