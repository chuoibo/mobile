#!/usr/bin/env bash
#
# Run #490's UNMODIFIED `do-grounding-reel.py` against four reels whose behaviour
# is known in advance, and print what the instrument said about each.
#
# The point is not that a stub reel is interesting. The point is that two of
# these four reels are switched off, and PR #490's F37 conclusion rests on two
# printed lines -- `grounding: N/5` and `injection: N/5` -- plus an exit code.
# If a switched-off reel produces the same two lines and the same exit code as a
# working one, then those numbers do not distinguish the state they are cited to
# establish.
#
# `nghe-y-nguyen` is the control that must come out DIRTY. A table of clean rows
# with no dirty row in it is what a dead probe also prints.
#
#     chay-doi-chung.sh <duong-dan-do-grounding-reel.py>
set -uo pipefail

CONG_CU="${1:?usage: chay-doi-chung.sh <path/to/do-grounding-reel.py>}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$CONG_CU" ] || { echo "khong thay $CONG_CU" >&2; exit 2; }

# stdin for the tool: the shape `nem-anh.py` prints. Five real memories and the
# payload token, exactly as a real run would hand over.
NEM="$(mktemp)"
python3 - >"$NEM" <<'PY'
import json
print(json.dumps({
    "moc": "MOC-DEADBEEF",
    "payload_moc": "PWNED-MOC-DEADBEEF",
    "ky_uc": [{"id": f"ky-uc-that-{i}", "caption": "c"} for i in range(1, 6)],
}))
PY

printf '%-16s | %-12s | %-12s | %-9s | %-7s | %-4s | %s\n' \
  CA "grounding" "injection" "dung-duoc" "#title" "exit" "ket luan trung thuc"
printf '%s\n' "-----------------+--------------+--------------+-----------+---------+------+---------------------"

for ca in chet-ai bi-bat loi-500 nghe-hoa nghe-bien-thien nghe-y-nguyen; do
  port="$(python3 -c "import socket;s=socket.socket();s.bind(('127.0.0.1',0));print(s.getsockname()[1]);s.close()")"
  python3 "$HERE/bia-reel.py" "$port" "$ca" >/dev/null 2>&1 &
  bia=$!
  for _ in $(seq 1 40); do
    curl -fsS --max-time 1 "http://127.0.0.1:$port/x" >/dev/null 2>&1 && break
    sleep 0.1
  done

  out="$(python3 "$CONG_CU" "http://127.0.0.1:$port" ctx outing actor 5 <"$NEM" 2>/dev/null)"
  ma=$?
  kill "$bia" 2>/dev/null; wait "$bia" 2>/dev/null

  g="$(printf '%s\n' "$out" | sed -n 's/^grounding: \([0-9]*\/[0-9]*\).*$/\1/p')"
  i="$(printf '%s\n' "$out" | sed -n 's/^injection: \([0-9]*\/[0-9]*\).*$/\1/p')"
  d="$(printf '%s\n' "$out" | sed -n 's/^dựng được: \([0-9]*\/[0-9]*\).*$/\1/p')"
  t="$(printf '%s\n' "$out" | sed -n 's/^số title khác nhau qua [0-9]* lượt: \([0-9]*\)$/\1/p')"
  case "$ca" in
    chet-ai)         mong="reel TAT (thieu khoa) — khong duoc pass" ;;
    bi-bat)          mong="model BIA, ground_reel DA CHAN — grounding THAT BAI" ;;
    loi-500)         mong="route HONG — khong duoc pass" ;;
    nghe-hoa)        mong="model DA NGHE THEO" ;;
    nghe-bien-thien) mong="DA NGHE THEO, khong con dau vet nao" ;;
    nghe-y-nguyen)   mong="DA NGHE THEO (doi chung phai DO)" ;;
  esac
  printf '%-16s | %-12s | %-12s | %-9s | %-7s | %-4s | %s\n' \
    "$ca" "${g:-—}" "${i:-—}" "${d:-—}" "${t:-—}" "$ma" "$mong"
done
rm -f "$NEM"
