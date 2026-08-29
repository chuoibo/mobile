#!/bin/sh
# Warn -- loudly, by name -- when the stack is about to run with no identity key.
#
# Sibling of check_ai_key.sh, same shape, different consequence. Without
# GEMINI_API_KEY one feature reads a bill badly. Without MOBILE_PERSON_ID_KEY
# nobody can sign in at all: POST /identity/person-id answers 503
# identity_key_missing, and the entry door is the first screen of the demo.
#
# The API refuses rather than falling back to an unkeyed digest, and that
# refusal is the point. bug-140342: `people.id` used to be FNV-1a of the
# telephone number computed in the app, so anybody holding an id and a clone of
# this repository could enumerate Vietnamese mobile numbers until one matched.
# Measured at 257,316 candidates per second on one core -- a number recovered
# in 29.75 seconds. A "convenient default key" in the repo would be that bug
# with extra steps, which is why this script asks you to generate one and
# cannot generate it for you.
#
# It WARNS, it does not refuse, for the same reason check_ai_key.sh does: one
# Postgres and one API are shared by every worktree on this machine, so
# blocking `make up` would take the stack away from whoever is working on money
# or migrations, neither of which touches this key.
#
# Usage:
#   check_identity_key.sh            full warning, printed before the build
#   check_identity_key.sh --brief    one line, printed where space is short
#
# Always exits 0. It never prints the value of the variable, only its name.

configured_key=$(sh "$(dirname -- "$0")/env_value.sh" MOBILE_PERSON_ID_KEY)

# 32 characters, the same floor `app/api/person_identity.py` enforces. Checked
# here too because a key that is set and too short fails at the first sign-in
# with the same 503 as no key at all, and being told "it is set" while sign-in
# is dead is the confusion this whole family of scripts exists to remove.
if [ -n "$configured_key" ] && [ "${#configured_key}" -ge 32 ]; then
  # Silence when configured, on purpose. A warning that prints every time is
  # wallpaper, and wallpaper is not read on the day it matters.
  exit 0
fi

if [ -n "$configured_key" ]; then
  reason="quá ngắn (cần từ 32 ký tự)"
else
  reason="chưa đặt"
fi

if [ "${1:-}" = "--brief" ]; then
  echo >&2
  echo "!! MOBILE_PERSON_ID_KEY $reason — đăng nhập bằng số điện thoại sẽ trả 503, không vào được app." >&2
  exit 0
fi

cat >&2 <<WARNING

  ┌──────────────────────────────────────────────────────────────────────┐
  │  CẢNH BÁO: MOBILE_PERSON_ID_KEY $reason — KHÔNG ĐĂNG NHẬP ĐƯỢC
  └──────────────────────────────────────────────────────────────────────┘

  Biến còn thiếu:  MOBILE_PERSON_ID_KEY

  Hệ vẫn dựng lên và mọi màn vẫn render. Thứ chết là cửa vào:
  POST /identity/person-id trả 503 identity_key_missing, nên màn "Đăng nhập
  bằng số điện thoại" báo lỗi và không ai tạo được tài khoản.

  Máy chủ TỪ CHỐI thay vì tự chế một id không khoá, và đó là chủ ý. Trước
  bug-140342 id được băm từ số điện thoại bằng hàm nằm sẵn trong repo, nên
  người cùng nhóm dò ngược ra số của nhau trong 29,75 giây. Một khoá mặc định
  viết trong repo cũng là khoá công khai, tức là đúng lỗi đó lần nữa.

  SINH khoá, đừng tự nghĩ ra:

      python3 -c "import secrets; print('MOBILE_PERSON_ID_KEY=' + secrets.token_urlsafe(48))" >> .env

  Compose tự đọc .env ở gốc repo (.gitignore đã chặn, không lỡ commit), nên
  chỉ cần \`make up\` lại. Đang chạy dở thì phải dựng lại container api —
  biến môi trường chỉ đọc lúc khởi động.

  ĐỔI KHOÁ = ĐỔI HẾT ID. Mọi tài khoản đã tạo bằng khoá cũ không đăng nhập
  lại được; người dùng gõ đúng số cũ sẽ vào một tài khoản mới rỗng. Đặt một
  lần rồi giữ nguyên, hoặc \`make clean\` cho sạch hẳn.

WARNING
exit 0
