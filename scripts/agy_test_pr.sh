#!/usr/bin/env bash
# Hand one pull request to agy and wait for a verdict with evidence behind it.
#
# Every PR now needs agy to have tested it before it merges. Code review no
# longer gates a merge; this does. The rule came out of one day in which two
# things reached `main` that nobody had exercised:
#
#   - an endpoint that accepted an `actor` argument and never read it, so any
#     valid header plus an id returned every obligation, every name, every
#     amount, and the private reason a guest gave for objecting
#   - a permission check with no test behind it: deleting the check outright
#     left 275 tests green
#
# Both were merged by one person reading their own work. agy found the first
# one an hour after it landed. This pulls that hour back to before the merge.
#
#   scripts/agy_test_pr.sh 42
#
# Writes a report next to the worktree and prints PASS or FAIL. It never
# merges anything: deciding is the merger's job, and this only makes sure the
# decision has something under it.

set -uo pipefail

PR="${1:?can nhap so PR}"
HARNESS="${AGENT_HARNESS:-$HOME/agent-harness}/agent_supervisor.py"
WORK="${AGY_PR_WORK:-/tmp/agy-pr-$PR}"
REPO_ROOT="$(git rev-parse --show-toplevel)"

command -v gh >/dev/null || { echo "can gh CLI" >&2; exit 1; }
[[ -f "$HARNESS" ]] || { echo "khong thay $HARNESS" >&2; exit 1; }

BRANCH="$(gh pr view "$PR" --json headRefName --jq .headRefName)"
TITLE="$(gh pr view "$PR" --json title --jq .title)"
[[ -n "$BRANCH" ]] || { echo "khong doc duoc PR #$PR" >&2; exit 1; }

# A separate worktree, not a checkout of the shared tree. Switching branches
# under a running dev server has already broken things here twice: it deleted
# a module out from under Metro, and it made the supervisor script vanish
# mid-launch.
rm -rf "$WORK"
git -C "$REPO_ROOT" fetch --quiet origin "$BRANCH"
git -C "$REPO_ROOT" worktree add --quiet --force --detach "$WORK" "origin/$BRANCH"
trap 'git -C "$REPO_ROOT" worktree remove --force "$WORK" 2>/dev/null || true' EXIT

OUT="${WORK}-report"
mkdir -p "$OUT"
PROMPT="$OUT/prompt.md"

cat > "$PROMPT" <<PROMPT_END
Ban la QA. Nhiem vu: test PR #$PR truoc khi no duoc merge.

  Tieu de: $TITLE
  Nhanh:   $BRANCH
  Ma nguon da checkout san tai: $WORK

KHONG sua file nao trong $WORK va KHONG sua gi trong $REPO_ROOT.
Moi file ban tao ghi bang DUONG DAN TUYET DOI bat dau bang: $OUT

# Viec 1 — chay het test cua chinh PR do

    cd $WORK
    python3 -m pytest services/api/tests tests -q
    cd $WORK/apps/mobile && npm test        # neu thu muc do ton tai

Ghi lai so test pass/fail NGUYEN VAN. Neu co test do, do la FAIL, dung
tim cach giai thich cho qua.

# Viec 2 — doc diff va tim cho no KHONG duoc test

    cd $WORK && git diff origin/main...HEAD

Cau hoi trung tam: **thay doi nao trong diff nay khong co test nao cham toi?**

Cach kiem manh nhat: chon mot dong quan trong trong diff, tu hoi "neu xoa
dong nay thi test nao do?" Neu cau tra loi la "khong cai nao" thi do la mot
phat hien — bat ke code co dung hay khong.

Hom nay da co hai lan dung kieu nay lot qua:
- mot tham so \`actor\` duoc nhan roi khong bao gio doc
- mot khoi kiem quyen co that nhung xoa di van 275 test xanh

# Viec 3 — co tinh lam vo tinh nang moi

Doc diff de biet PR nay them gi, roi tan cong dung cho do. Neu no dung toi
tien, quyen rieng tu, hay danh tinh nguoi dung thi uu tien cao nhat.

# BAO CAO — bat buoc

Ghi ra $OUT/verdict.md, DONG DAU TIEN phai la dung mot trong hai:

    PASS
    FAIL

Roi:
  - So test da chay va ket qua nguyen van
  - Cho nao trong diff KHONG duoc test cham toi
  - Loi tim duoc (neu co), kem chuoi thao tac tai hien
  - Da thu lam vo nhung khong vo — liet ke cu the
  - Chua test duoc, va vi sao

LUAT: chi ghi PASS khi ban DA NHIN thay test xanh va DA thu lam vo. Khong
duoc ghi "moi thu deu on". Khong chac thi ghi FAIL kem ly do — mot cai
cong ma bao gio cung mo thi khong phai cong.
PROMPT_END

echo "agy dang test PR #$PR ($BRANCH)"
AGY_OUT="$OUT" python3 "$HARNESS" agy \
  --prompt-file "$PROMPT" --out-dir "$OUT" \
  --print-timeout 16m --timeout 1200 --max-restarts 2 --checkpoint 45

VERDICT="$OUT/verdict.md"
if [[ ! -f "$VERDICT" ]]; then
  echo "FAIL: agy khong ghi verdict. Khong co xac nhan thi khong merge." >&2
  exit 2
fi

FIRST="$(head -1 "$VERDICT" | tr -d '[:space:]')"
echo "--- $VERDICT ---"
head -40 "$VERDICT"

if [[ "$FIRST" == "PASS" ]]; then
  echo
  echo "PASS — PR #$PR co xac nhan cua agy"
  exit 0
fi
echo
echo "FAIL — PR #$PR chua duoc merge" >&2
exit 1
