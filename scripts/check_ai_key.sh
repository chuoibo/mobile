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

if [ -n "${GEMINI_API_KEY:-}" ]; then
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
