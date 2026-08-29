#!/bin/sh
# Refuse a stack whose database is not at the migration head its code expects.
#
# ## Why this exists
#
# `scripts/check_alembic_heads.py` proves the migration FILES form one chain.
# Its own docstring says what it deliberately does not prove:
#
#   "It says nothing about what any database has been stamped with -- a
#    database can still be ahead, behind or off on a revision this tree has
#    never heard of. That is a different check against a live server."
#
# That check was never written, and on 2026-08-29 the gap cost the team most of
# an afternoon. The shared `mobile-local` database was stamped `8f1c6a4b2e70`,
# a revision that had been renumbered away and existed in no branch any more.
# Every `alembic upgrade head` against it had been dying with "Can't locate
# revision" for hours. The API did not care: it was already running, so nothing
# re-ran migrate, and `/healthz` deliberately never touches the database. The
# stack reported healthy while `GET /contexts/{id}/outings` returned 500
# `UndefinedTable` to every real member.
#
# So the tell was available the whole time and nothing was looking at it. It is
# looked at here.
#
# ## Why it asks the running image instead of reading the worktree
#
# This machine runs five worktrees against ONE shared Compose project. The
# question that matters is "does the schema match the code that is serving",
# and only the image can answer it -- the worktree you happen to be standing in
# may be two commits ahead of main and carry migrations nobody has merged.
#
# Comparing against the worktree would be worse than useless: on a branch with
# an unmerged migration it would report the shared database as "behind" and
# send you to migrate it up to a branch revision. That is precisely the move
# that created the outage above.
#
# ## Why both `current` and `heads`
#
# Exit code alone is not enough, and this was measured rather than assumed:
#
#   database at head       `current` -> "d4a2e7b91c30 (head)"      exit 0
#   database behind        `current` -> "7c3a8f2d1e6b"             exit 0   <--
#   database on an orphan  `current` -> "FAILED: Can't locate..."  exit 255
#   database never migrated`current` -> ""                         exit 0   <--
#
# The two marked rows are the ones a naive `alembic current || exit 1` reports
# as healthy. A database three migrations behind is exactly as broken to the
# caller as an orphaned one -- the table is missing either way.
#
# Note the orphan's "FAILED:" line arrives on STDOUT, not stderr, so the exit
# code has to be consulted before the text is parsed. Reading the first word of
# stdout without checking status yields the revision id "FAILED:".
#
# ## Usage
#
#   check_db_revision.sh <alembic-runner...>
#
# The runner is a command that accepts an alembic subcommand as its last
# argument. `make smoke` passes the Compose invocation for the running image;
# tests/test_db_revision_gate.py passes a stub, which is why the runner is an
# argument at all rather than hardcoded here.
#
# Exit 0 only when the database is AT the single head the code declares.

if [ "$#" -eq 0 ]; then
  echo "check_db_revision: thiếu lệnh chạy alembic." >&2
  echo "Dùng: check_db_revision.sh <lệnh-alembic...>" >&2
  exit 2
fi

# `current` first: its exit status is the only reliable way to tell an orphan
# stamp from a revision id, because the failure text is printed to stdout.
current_out=$("$@" current 2>/dev/null)
current_status=$?

if [ "$current_status" -ne 0 ]; then
  echo >&2
  echo "!! Database đang bị đóng dấu một revision KHÔNG có trong mã nguồn." >&2
  echo >&2
  echo "$current_out" | sed 's/^/    /' >&2
  echo >&2
  cat >&2 <<'ORPHAN'
Nghĩa là: `alembic upgrade head` trên database này đã hỏng từ lâu, nên mọi
bảng của những migration sau đó KHÔNG tồn tại. API vẫn chạy và /healthz vẫn
200 — nó cố ý không chạm database — trong khi route nào đụng bảng thiếu thì
trả 500.

Hay gặp nhất: một worktree chạy `make up` với migration của nhánh chưa merge,
đóng dấu database DÙNG CHUNG bằng revision của nhánh đó, rồi nhánh được đánh
số lại và revision cũ biến mất khỏi mọi nhánh.

Gỡ (chạy trong ảnh đang phục vụ, KHÔNG phải worktree của bạn):
    alembic stamp --purge <revision-CUỐI-CÙNG-của-main-đã-thật-sự-chạy>
    alembic upgrade head

`stamp` KHÔNG có `--purge` sẽ thất bại y hệt: alembic phải đọc được revision
hiện tại trước khi tính đường đi, và nó đọc không được. Đó là cái bẫy.

Chọn revision để stamp bằng SCHEMA THẬT, đừng đoán: tìm migration cuối cùng
của main mà bảng/cột của nó đã có trong database.
ORPHAN
  exit 1
fi

heads_out=$("$@" heads 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "check_db_revision: không đọc được head của mã nguồn." >&2
  exit 1
fi

# First whitespace-delimited token of each non-empty line. Alembic decorates
# the id with " (head)", which is informative for a human and noise here.
current_rev=$(echo "$current_out" | awk 'NF {print $1; exit}')
heads_rev=$(echo "$heads_out" | awk 'NF {print $1}')
heads_count=$(echo "$heads_out" | awk 'NF' | wc -l | tr -d ' ')

if [ -z "$current_rev" ]; then
  echo >&2
  echo "!! Database chưa chạy migration lần nào — không có bảng nào cả." >&2
  echo "   Gỡ:  make migrate" >&2
  exit 1
fi

# Zero heads means the check read nothing, and "nothing to disagree with" must
# never be reported as agreement -- that is the shape every dead gate in this
# repository has had.
if [ -z "$heads_rev" ]; then
  echo "check_db_revision: mã nguồn không khai head nào. Cây migration hỏng?" >&2
  exit 1
fi

if [ "$heads_count" -ne 1 ]; then
  echo "!! Mã nguồn có $heads_count head, phải có đúng 1." >&2
  echo "   Chạy:  python3 scripts/check_alembic_heads.py" >&2
  exit 1
fi

if [ "$current_rev" != "$heads_rev" ]; then
  echo >&2
  echo "!! Database ĐỨNG SAU mã nguồn." >&2
  echo "   database: $current_rev" >&2
  echo "   mã nguồn: $heads_rev" >&2
  echo >&2
  echo "Bảng của những migration ở giữa chưa tồn tại, nên route nào đụng tới" >&2
  echo "chúng sẽ trả 500 trong khi /healthz vẫn 200." >&2
  echo "   Gỡ:  make migrate" >&2
  exit 1
fi

echo "DB revision: $current_rev (khớp head của mã nguồn)."
