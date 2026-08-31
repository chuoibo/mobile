#!/usr/bin/env bash
# Re-run every number in docs/claude/2026-08-31/qa-tt-0006/phan-quyet-491.md.
#
# Nothing here writes to a shared service and nothing here needs a database.
# The URL scan is NOT run automatically: it needs a pinned Chrome and takes
# about ten minutes, so the script prints the exact command instead of hiding
# a ten-minute wait inside a gate script.
#
#     bash tests/qa/qa-tt-0006/do_cong_491.sh
#
# Run it from the repo root of a worktree whose tree is clean. The script
# checks out detached heads and restores the branch it started on.
set -u

PR_SHA=b6205be216736f76f63b64d3ae69124def098d2c
MAIN_SHA=7fff89c

ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT" || exit 1
BAN_DAU=$(git rev-parse --abbrev-ref HEAD)
[ "$BAN_DAU" = HEAD ] && BAN_DAU=$(git rev-parse HEAD)

if [ -n "$(git status --porcelain)" ]; then
  echo "CAY BAN -- dung lai. Mot lenh doi HEAD tren cay ban thi mat viec cua nguoi khac."
  git status --short
  exit 1
fi

ve_cho_cu() { git checkout "$BAN_DAU" >/dev/null 2>&1; }
trap ve_cho_cu EXIT

echo "############ 1. Cong backend tai PR head ############"
git checkout --detach "$PR_SHA" >/dev/null 2>&1 || { echo "khong checkout duoc $PR_SHA"; exit 1; }
python3 -m pytest services/api/tests tests -q 2>&1 | tail -1

echo
echo "############ 2. Cong mobile tai PR head ############"
( cd apps/mobile && npm test 2>&1 | grep -E "^# (tests|pass|fail)" )

echo
echo "############ 3. Cua ?man= CHUA MO -- PR vs MAIN ############"
# This is cuaChuaMo() from tools/quet-tab-url.mjs, lifted out so it can be run
# against a tree other than the one it lives in. Reading the tool's own numbers
# back would prove nothing about the tool.
cat > /tmp/qa491-cuachuamo.mjs <<'EOF'
import fs from "node:fs";
const [appPath, toolPath] = process.argv.slice(2);
const src = fs.readFileSync(appPath, "utf8");
const tool = fs.readFileSync(toolPath, "utf8");
const dung = [...src.matchAll(/manThamSo\(\)\s*===\s*"([^"]+)"/g)].map((m) => m[1]);
const dau = [...src.matchAll(/manThamSo\(\)\?\.startsWith\("([^"]+)"\)/g)].map((m) => m[1]);
const moi = new Set([...tool.matchAll(/truyVan:\s*"man=([^"]+)"/g)].map((m) => m[1]));
const tatCa = [...new Set([...dung, ...dau])];
const chuaMo = tatCa.filter((v) => !moi.has(v) && ![...moi].some((m) => m.startsWith(v)));
console.log(`  route ?man= trong App.tsx: ${tatCa.length}`);
console.log(`  cua tool CO mo (${moi.size}): ${[...moi].sort().join(", ") || "-"}`);
console.log(`  cua CHUA mo (${chuaMo.length}): ${chuaMo.sort().join(", ") || "-"}`);
EOF
git show "$MAIN_SHA":apps/mobile/App.tsx > /tmp/qa491-App-main.tsx
git show "$MAIN_SHA":apps/mobile/tools/quet-tab-url.mjs > /tmp/qa491-qtu-main.mjs
echo "-- MAIN $MAIN_SHA  (cho: 13 chua mo) --"
node /tmp/qa491-cuachuamo.mjs /tmp/qa491-App-main.tsx /tmp/qa491-qtu-main.mjs
echo "-- PR $PR_SHA  (cho: 5 chua mo) --"
node /tmp/qa491-cuachuamo.mjs apps/mobile/App.tsx apps/mobile/tools/quet-tab-url.mjs

echo
echo "############ 4. So hoc tuong phan (cho: 3.66:1 va 4.56:1) ############"
python3 -c "
def L(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
for a in (0.40, 0.46):
    px = round(a * 255)
    print(f'  alpha={a} -> pixel {px} (#{px:02x}{px:02x}{px:02x}) tren nen den = {(L(px)+0.05)/0.05:.2f}:1')
"

echo
echo "############ 5. Hai dot bien MO_KHI_BAN -- ca hai PHAI SONG SOT ############"
echo "   (dot bien song sot = cong van xanh = khong cong nao giu hang so nay)"
CHUP=apps/mobile/src/screens/ChupBill.tsx
for GIA_TRI in 0.40 0; do
  sed -i "s/^const MO_KHI_BAN = .*;/const MO_KHI_BAN = $GIA_TRI;/" "$CHUP"
  echo "-- MO_KHI_BAN = $GIA_TRI --"
  ( cd apps/mobile && npm test 2>&1 | grep -E "^# (pass|fail)" | sed 's/^/    /' )
  # The build carries the mutation, so it is not a no-op. Check, do not assume.
  if [ "$GIA_TRI" = "0" ]; then
    echo -n "    dot bien co toi ban dung khong: "
    grep -qo "opacity:0" apps/mobile/.expo-build-check/_expo/static/js/web/*.js \
      && echo "CO (bundle chua opacity:0)" || echo "KHONG -- dot bien la no-op, ket qua tren vo nghia"
  fi
  git checkout -- "$CHUP"
done

echo
echo "############ 6. Quet URL -- CHAY TAY, khong tu chay o day ############"
cat <<'EOF'
  export PUPPETEER_EXECUTABLE_PATH=/home/lakiet/.cache/ms-playwright/chromium-1194/chrome-linux/chrome
  cd apps/mobile && npm run build:check && node tools/quet-tab-url.mjs

  Cho doi: EXIT=2, "tong findings tren cac man: 2" (doc-bill + doc-bill-chuan-bi),
  "cua ... KHONG mo (5)", va BON canary:
      canary xau 5/exit2 · canary sach 0/exit0 · canary nang 3/exit2 · nang-sach 0/exit0
  Canary xau KHONG do thi moi so 0 phia duoi deu vo nghia -- vut ca luot quet.
EOF

echo
echo "############ 7. Cong mobile tren MAIN (doi chung) ############"
git checkout --detach "$MAIN_SHA" >/dev/null 2>&1
( cd apps/mobile && npm test 2>&1 | grep -E "^# (tests|pass|fail)" )

echo
echo "LUU Y ve flake: tests/duong-vao-mon-cua-toi.test.mjs do khoang 1/4 luot khi"
echo "chay qua 'npm test' (ngan sach cho cung 20000ms o tools/quet-man-sau-tap.mjs:595)."
echo "Mot luot do o dung ca do KHONG phai bang chung ve nhanh dang do."
