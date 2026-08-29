#!/bin/sh
# Warn -- loudly, by name -- when the stack is about to run with no AI key.
#
# Compose does not forward the host environment into a container; only what a
# service lists under `environment:` crosses. `docker-compose.yml` used to list
# MOBILE_DATABASE_URL and nothing else, so every stack `make up` built ran the
# receipt reader with no credential. Nothing looked wrong: API up, /healthz
# 200, every screen rendering. Only the hero feature was dead, and it failed as
# `422 receipt_unreadable` in 2.5ms -- the same answer a blurry photo gets.
#
# That is the shape this script exists to prevent: a configuration fault that
# only surfaces as somebody else's mistake, halfway through a demo.
#
# It WARNS, it does not refuse. The structured money path -- allocator, ledger,
# collection batches, VietQR -- works without a key, and that is most of the
# repo. Blocking `make up` would trade a silent demo failure for a loud outage
# for everyone working on money.
#
# Usage:
#   check_ai_key.sh            full warning, printed before the build
#   check_ai_key.sh --brief    one line, printed where space is short
#
# Always exits 0. It never prints the value of the variable, only its name.

# Where the key can legitimately live -- both places, in Compose's own order.
#
# Compose resolves `${GEMINI_API_KEY:-}` in docker-compose.yml from TWO sources:
# the shell environment, and `.env` in the project directory. This check used to
# look only at the first. So the person who did exactly what `.env.example` and
# the warning below both instruct -- put the key in `.env` -- was told the key
# was missing while it sat in the container working fine.
#
# That is worse than the silence it was written to replace. A gate that fires on
# correct behaviour gets switched off, and a switched-off gate is not there on
# the day it would have been right.
#
# Precedence below is Compose's, measured against `docker compose config`:
#   shell variable set, even to empty -> that value wins, `.env` is not consulted
#   shell variable unset              -> whatever `.env` assigns, if anything
#
# `.env` is read relative to this script rather than to the caller's directory,
# because that is where docker-compose.yml lives and Compose loads `.env` from
# the compose file's directory. Resolving it any other way lets the two answers
# drift apart again, which is the whole bug.

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd) || exit 0
env_file="$repo_root/.env"

if [ "${GEMINI_API_KEY+set}" = set ]; then
  configured_key=$GEMINI_API_KEY
elif [ -r "$env_file" ]; then
  # dotenv semantics, kept narrow on purpose: skip comments, allow an `export`
  # prefix, drop one layer of matching quotes, last assignment wins. Anything
  # fancier would be guessing at Compose's parser instead of agreeing with it.
  configured_key=$(awk -v q="'" '
    { line = $0; sub(/^[ \t]*/, "", line) }
    line ~ /^#/ { next }
    { sub(/^export[ \t]+/, "", line) }
    line !~ /^GEMINI_API_KEY[ \t]*=/ { next }
    {
      sub(/^GEMINI_API_KEY[ \t]*=/, "", line)
      sub(/[ \t\r]+$/, "", line)
      first = substr(line, 1, 1); last = substr(line, length(line), 1)
      if (length(line) > 1 && first == last && (first == "\"" || first == q))
        line = substr(line, 2, length(line) - 2)
      value = line
    }
    END { printf "%s", value }
  ' "$env_file")
else
  configured_key=
fi

if [ -n "$configured_key" ]; then
  # Silence when configured, on purpose. A warning that prints every time is
  # wallpaper, and wallpaper is not read on the day it matters.
  exit 0
fi

if [ "${1:-}" = "--brief" ]; then
  echo >&2
  echo "!! GEMINI_API_KEY chưa đặt — chụp bill sẽ báo lỗi cấu hình, không đọc được món." >&2
  exit 0
fi

cat >&2 <<'WARNING'

  ┌──────────────────────────────────────────────────────────────────────┐
  │  CẢNH BÁO: thiếu GEMINI_API_KEY — tính năng chụp bill sẽ KHÔNG chạy  │
  └──────────────────────────────────────────────────────────────────────┘

  Biến còn thiếu:  GEMINI_API_KEY

  Hệ vẫn dựng lên bình thường và mọi màn vẫn render. Thứ duy nhất chết là
  đường hero: POST /receipts/scan sẽ trả 503 receipt_reader_not_configured
  thay vì đọc ra danh sách món.

  Phần chia tiền (allocator, sổ cái, đợt thu, VietQR) KHÔNG cần khoá này và
  vẫn chạy đủ. Nếu bạn đang làm về tiền hay migration thì bỏ qua cảnh báo.

  Cách đặt — ghi vào .env ở gốc repo (.gitignore đã chặn, không lỡ commit):

      echo 'GEMINI_API_KEY=<khoá của bạn>' >> .env

  Compose tự đọc .env ở gốc repo, nên chỉ cần `make up` lại. Đang chạy dở
  thì phải dựng lại container api — biến môi trường chỉ đọc lúc khởi động.

WARNING
exit 0
