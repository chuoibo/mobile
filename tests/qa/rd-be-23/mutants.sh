#!/usr/bin/env bash
# Is the scan ceiling gated as a RATE, and by which case?
#
# `tests/qa/qa-tt-0005` bounds the two numbers separately -- the limit lands in
# (20, 60] and the window in [60, 300] -- and never their ratio. Every pair
# inside both bands is therefore unguarded, however far the real ceiling moves.
# The two pairs below sit inside both bands and tighten the ceiling fivefold.
#
# A gate is only worth the last time somebody watched it go red. This script is
# that time, kept: it moves the shipped constants one mutation at a time, re-runs
# both gates, and restores the tree.
#
# The two columns matter more than either alone. `30 -> 3000` must leave the new
# case GREEN and qa-tt-0005 RED: the new case guards the floor, not the ceiling,
# and a script reporting red everywhere would be hiding that it is redundant.
#
# Run from the repo root:
#
#     bash tests/qa/rd-be-23/mutants.sh
set -u

SRC=services/api/app/api/search_rate_limit.py
MINE='test_the_human_burst_gets_through_in_every_minute_not_just_the_first'
QA='test_nguoi_chup_lai_bill_may_lan_khong_bi_tu_choi or test_mot_vong_lap_van_bi_chan_o_muc_hai_con_so or test_cua_so_dai_bang_phut_dung_nhu_cau_tu_choi_da_hua'

restore() { git checkout -- "$SRC"; }
trap restore EXIT

run_one() {  # $1 = -k selector
  local out rc n
  out=$(timeout 600 python3 -m pytest services/api/tests tests -q -k "$1" 2>&1)
  rc=$?
  # Only the final summary line. Earlier output echoes the failing case's own
  # docstring, which quotes a pass count that would be read back as a result.
  n=$(printf '%s' "$out" | tail -n 1 | sed -E 's/[= ]*$//; s/^[= ]*//; s/ in [0-9.]+s$//')
  if [ "$rc" -eq 0 ]; then echo "xanh  ($n)"; else echo "ĐỎ    ($n)"; fi
}

set_const() {  # $1 = exact current line, $2 = replacement
  grep -qxF "$1" "$SRC" || { echo "ANCHOR MISSING: $1" >&2; exit 9; }
  sed -i "s/^$1\$/$2/" "$SRC"
  # A mutation that never landed reads exactly like a gate that is blind.
  grep -qxF "$2" "$SRC" || { echo "MUTATION DID NOT LAND: $2" >&2; exit 9; }
}

W60='RECEIPT_SCAN_WINDOW_SECONDS = 60'
L30='RECEIPT_SCAN_LIMIT_PER_WINDOW = 30'

row() {  # $1 = label, rest = pairs of (anchor, replacement)
  local label=$1; shift
  restore
  while [ "$#" -ge 2 ]; do set_const "$1" "$2"; shift 2; done
  if [ -n "${label##đối chứng*}" ] && git diff --quiet -- "$SRC"; then
    echo "NO DIFF AFTER MUTATION: $label" >&2; exit 9
  fi
  printf '%-33s | %-34s | %s\n' "$label" "$(run_one "$MINE")" "$(run_one "$QA")"
}

printf '%-33s | %-34s | %s\n' 'đột biến' 'ca rd-be-23' 'qa-tt-0005'
printf '%.0s-' {1..96}; echo

row 'đối chứng (30 / 60, cây sạch)'
row 'cặp 30/300 (window 60 -> 300)' "$W60" 'RECEIPT_SCAN_WINDOW_SECONDS = 300'
row 'cặp 21/300 (mép trong của band)' "$W60" 'RECEIPT_SCAN_WINDOW_SECONDS = 300' \
                                      "$L30" 'RECEIPT_SCAN_LIMIT_PER_WINDOW = 21'
row 'limit 30 -> 3   (siết thô)' "$L30" 'RECEIPT_SCAN_LIMIT_PER_WINDOW = 3'
row 'limit 30 -> 3000 (trần biến mất)' "$L30" 'RECEIPT_SCAN_LIMIT_PER_WINDOW = 3000'

restore
echo
echo 'cây sau khi chạy (rỗng = đã khôi phục):'
git status --porcelain -- "$SRC" | sed 's/^/  /'
