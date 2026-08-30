#!/usr/bin/env bash
# QA gate check for PR #266: does probe-xoa-nham-that.mjs measure the PROPERTY
# (buried text must not be erased) or merely "somebody edited che-chu.mjs"?
# Each mutant is verified to have actually landed before the probe runs.
#
# Chay:  bash tests/qa/qa-tt-0016/dot-bien-probe.sh   (tu goc repo, sau khi
#        da `cd apps/mobile && npm run build:check`)
set -uo pipefail
GOC="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$GOC/apps/mobile"

# Let the probe find its own browser unless the caller pinned one. Resolved by
# absolute path off $GOC, not relative to this cwd -- the `cd` above lands in
# apps/mobile, where a `../tests/qa/...` would silently mean apps/tests/qa.
if [ -z "${PUPPETEER_EXECUTABLE_PATH:-}" ]; then
  PUPPETEER_EXECUTABLE_PATH="$(node -e '
    import(process.argv[1]).then((m) => console.log(m.timTrinhDuyet()))
      .catch((e) => { console.error(e.message); process.exit(1); })
  ' "$GOC/tests/qa/tim-trinh-duyet.mjs")" || {
    echo "khong tim thay trinh duyet" >&2
    exit 1
  }
fi
export PUPPETEER_EXECUTABLE_PATH
SRC=tools/che-chu.mjs
D=/tmp/qa16-mutants
rm -rf "$D"; mkdir -p "$D"

# Build one mutant: name, python expression applied to source text.
mk() {
  local name="$1"; shift
  python3 - "$SRC" "$D/$name.mjs" "$@" <<'PY'
import sys
src, dst, old, new = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
t = open(src).read()
n = t.count(old)
if n != 1:
    print(f"KHONG DOT BIEN DUOC: neo xuat hien {n} lan, can dung 1", file=sys.stderr)
    sys.exit(9)
open(dst, "w").write(t.replace(old, new))
PY
}

run() {
  local name="$1" mong="$2" mod="$3"
  local sha="${4:-}"
  local out rc
  if [ -n "$sha" ]; then
    out=$(CHE_CHU_SHA_DOI_CHUNG="$sha" CHE_CHU_MODULE="$mod" node tools/probe-xoa-nham-that.mjs 2>&1)
  else
    out=$(CHE_CHU_MODULE="$mod" node tools/probe-xoa-nham-that.mjs 2>&1)
  fi
  rc=$?
  local line
  line=$(echo "$out" | grep -E 'bi xoa nham \(do\)|CHUA KET LUAN DUOC:|^HONG:' | head -2 | tr '\n' ' ')
  local dau="SAI"; [ "$rc" = "$mong" ] && dau="dung"
  printf '%-42s mong=%s ra=%s  %-5s %s\n' "$name" "$mong" "$rc" "$dau" "${line:0:90}"
}

echo "=== A. dot bien tren MODULE DANG DO (che-chu.mjs) ==="

# M1: pre-patch acquittal rewritten as if/else -- same property broken, different SHAPE.
mk m1-ifelse \
 'verdict: tyLe >= 0.6 ? (cha ? "to-cha" : "cuon-khuat") : "that",' \
 'verdict: (() => { if (tyLe >= 0.6) return cha ? "to-cha" : "cuon-khuat"; if (cha) return "to-cha"; return "that"; })(),' \
 && run "M1 tha bong viet lai bang if/else" 1 "$D/m1-ifelse.mjs"

# M2: acquittal moved DOWN a layer, into the whitelist gate instead of the verdict.
mk m2-laloithat \
 'return !DA_LOAI_TRU.has(kq?.verdict);' \
 'if (kq?.verdict === "that" && kq?.chan) return false;
  return !DA_LOAI_TRU.has(kq?.verdict);' \
 && run "M2 tha bong o tang laLoiThat" 1 "$D/m2-laloithat.mjs"

# M3: shortcut moved UP into the readability counter -- never touches the verdict
# expression at all, inflates nhinThay so the burial reads as readable.
#
# Expected 3, not 1, and that is the interesting part. Inflating nhinThay also
# destroys the probe's own denominator (it only counts burials where
# diemNhinThay === 0), so nothing is left to measure. A two-state gate would
# print "0/0 = 0.0%" here and exit 0 -- a perfect false pass. The `tChon === 0`
# guard turns it into "don't know" instead. Verified by hand on a page built
# without any probe code: M3 returns verdict `to-cha` at 5/5 readable and does
# erase the warning. See do-doc-lap-verdict.mjs.
mk m3-dem \
 'if (tren === el || el.contains(tren) || tren.contains(el)) nhinThay++;' \
 'if (tren === el || el.contains(tren) || tren.contains(el)) nhinThay++;
      else if (selectorTren && tren.matches && tren.matches(selectorTren)) nhinThay++;' \
 && run "M3 duong tat doi len ham DEM diem" 3 "$D/m3-dem.mjs"

echo
echo "=== B. GIU TINH CHAT -- phai XANH (rc=0) ==="

# M4: same 5 samples on the same mid-line, different fractions. Instrument really
# changed; the property it measures did not.
mk m4-diemmau \
 'const diem = [0.1, 0.3, 0.5, 0.7, 0.9].map' \
 'const diem = [0.15, 0.35, 0.5, 0.65, 0.85].map' \
 && run "M4 doi vi tri 5 diem mau" 0 "$D/m4-diemmau.mjs"

# M5: threshold nudged, both sides of 0.6 still classify 0/5 as `that`.
mk m5-nguong \
 'tyLe >= 0.6 ? (cha' \
 'tyLe >= 0.58 ? (cha' \
 && run "M5 nguong 0.6 -> 0.58" 0 "$D/m5-nguong.mjs"

echo
echo "=== C. doi chung bi lam mu -- phai CHUA KET LUAN (rc=3) ==="
run "M6 ghim doi chung vao sha DA VA (1fc37ae)" 3 "$SRC" 1fc37ae
run "M7 ghim doi chung vao sha khong ton tai" 3 "$SRC" deadbee
