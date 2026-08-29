"""Chạy migration không được TẮT logger của chính ứng dụng nó vừa migrate.

`app/db/migrations/env.py` gọi `logging.config.fileConfig(...)`. Tham số
`disable_existing_loggers` của hàm đó mặc định là **True**: mọi logger đã tồn
tại mà không được gọi tên trong `alembic.ini` bị đặt `disabled = True` cho tới
hết tiến trình. Không có ngoại lệ nào, và không có một dòng cảnh báo nào.

Đo được ngày 2026-08-29 trong tầng postgres, trước khi có bản sửa — một lần
migrate giết cả tám logger `app.*` mà thứ tự import đã tạo ra tới lúc đó:

    app · app.api · app.api.routes · app.api.routes.places
    app.api.service · app.places · app.places.reasons · app.places.search

Hỏng câm hai lần:

1. **Sản phẩm.** Tiến trình nào migrate trong cùng process rồi mới phục vụ thì
   mất log ứng dụng. Không crash, không báo — chỉ là im.
2. **Test, và đây mới là chỗ đau.** Các ca quyền riêng tư khẳng định
   `assert SECRET not in caplog.text`. Một kênh log RỖNG thoả mãn khẳng định đó
   một cách hoàn hảo. Cổng trông có mặt trong khi nó đã vắng — đúng hình dạng
   "xanh vì không chạy gì" mà CLAUDE.md dặn phải đi tìm.

`services/api/tests/postgres/test_suggestion_postgres.py` đã đụng đúng bẫy này
và tự cứu mình bằng cách bật lại logger ngay trong thân test, kèm một khẳng
định liveness. Đó là bản vá đúng cho MỘT ca; nó không cứu ca nào khác, và
không có gì ngăn ca tiếp theo được viết lại y như cũ. File này vá ở gốc:
`alembic.ini` gọi tên `app`, nên fileConfig coi `app.*` là logger con cần giữ
chứ không phải người lạ cần tắt.

Hai nửa đều chịu lực:

- `test_cay_that_...` là **chính cổng**. Nó đỏ vào đúng ngày ai đó gỡ `app`
  khỏi `alembic.ini`.
- `test_cong_biet_do` dựng lại đúng hình dạng TRƯỚC bản sửa và đòi nó phải đỏ.
  Một cổng chỉ từng xanh không phân biệt được với một cổng hỏng.

Cả hai chạy alembic THẬT ở chế độ offline (`--sql`), nên `env.py` được thực thi
thật. Không cần database, không cần docker — file này nằm trong lệnh cổng chuẩn
`python3 -m pytest services/api/tests tests -q`.

Cái này KHÔNG chứng minh: rằng ứng dụng có ghi log điều đáng ghi, hay rằng một
khẳng định `not in caplog.text` cụ thể nào đó đang đọc kênh sống. Nó chỉ chứng
minh migration không còn là thứ giết kênh đó.
"""

from __future__ import annotations

import configparser
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
API_DIR = REPO_ROOT / "services" / "api"
REAL_INI = API_DIR / "alembic.ini"

# The eight names measured in the postgres tier on 2026-08-29. Created up front
# so the probe is deterministic: `fileConfig` only disables loggers that exist
# when it runs, so a test that relied on import order would drift into passing.
APP_LOGGERS = (
    "app",
    "app.api",
    "app.api.routes",
    "app.api.routes.places",
    "app.api.service",
    "app.places",
    "app.places.reasons",
    "app.places.search",
)

PROBE = """
import contextlib, io, logging, sys

NAMES = {names!r}
for name in NAMES:
    logging.getLogger(name)

from alembic import command
from alembic.config import Config

config = Config(sys.argv[1])
config.set_main_option("sqlalchemy.url", "postgresql+psycopg://offline/offline")
# Offline render: runs env.py (and therefore fileConfig) without a database.
with contextlib.redirect_stdout(io.StringIO()):
    command.upgrade(config, "head", sql=True)

dead = [n for n in NAMES if getattr(logging.getLogger(n), "disabled", False)]
print("RAN=1")
print("DEAD=" + ",".join(dead))
"""


def _run_probe(ini_path: Path) -> tuple[int, str, str]:
    """Migrate offline with `ini_path`, report which app loggers came out dead."""
    proc = subprocess.run(
        [sys.executable, "-c", PROBE.format(names=list(APP_LOGGERS)), str(ini_path)],
        cwd=API_DIR,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _dead_from(stdout: str) -> list[str]:
    for line in stdout.splitlines():
        if line.startswith("DEAD="):
            body = line[len("DEAD=") :].strip()
            return [n for n in body.split(",") if n]
    raise AssertionError(f"probe không in dòng DEAD=; stdout:\n{stdout}")


class MigrationKeepsAppLoggers(unittest.TestCase):
    def test_cay_that_migrate_khong_tat_logger_nao_cua_app(self) -> None:
        """Cổng thật: chạy migration của CÂY NÀY, không logger `app.*` nào chết."""
        code, out, err = _run_probe(REAL_INI)
        self.assertEqual(code, 0, f"probe hỏng:\n{out}\n{err}")
        # Guard the guard: a probe that silently skipped the upgrade would report
        # zero dead loggers for the one reason that must not count as passing.
        self.assertIn("RAN=1", out, f"migration không hề chạy:\n{out}\n{err}")
        self.assertEqual(
            _dead_from(out),
            [],
            "migrate xong mà logger của app bị tắt — mọi khẳng định "
            "`not in caplog.text` sau đó đang đọc kênh rỗng",
        )

    def test_cong_biet_do_khi_alembic_ini_thoi_goi_ten_app(self) -> None:
        """Bỏ `app` khỏi alembic.ini là phải đỏ, nếu không cổng này vô nghĩa."""
        pre_fix = self._ini_without_app_logger()
        code, out, err = _run_probe(pre_fix)
        self.assertEqual(code, 0, f"probe hỏng:\n{out}\n{err}")
        self.assertIn("RAN=1", out, f"migration không hề chạy:\n{out}\n{err}")
        self.assertEqual(
            sorted(_dead_from(out)),
            sorted(APP_LOGGERS),
            "dựng lại hình dạng trước bản sửa mà KHÔNG thấy logger nào chết — "
            "nghĩa là phép đo này không đo được thứ nó nói là đang đo",
        )

    def _ini_without_app_logger(self) -> Path:
        """Cùng file alembic.ini, chỉ gỡ đúng phần bản sửa đã thêm.

        Dẫn xuất từ file thật thay vì chép tay, để nửa 'biết đỏ' không trôi ra
        khỏi nửa đang thực sự gác.
        """
        # Raw: `%(here)s` is alembic's, not configparser's, and interpolation
        # would explode on it.
        parser = configparser.RawConfigParser()
        parser.optionxform = str  # type: ignore[assignment]
        parser.read(REAL_INI, encoding="utf-8")

        keys = parser.get("loggers", "keys")
        remaining = [k for k in keys.split(",") if k.strip() and k.strip() != "app"]
        self.assertNotEqual(
            remaining,
            [k for k in keys.split(",") if k.strip()],
            "alembic.ini không còn khai báo logger `app` — bản sửa đã bị gỡ, "
            "và ca này không còn dựng lại được hình dạng cũ",
        )
        parser.set("loggers", "keys", ",".join(remaining))
        parser.remove_section("logger_app")

        # `%(here)s` resolves against the ini's own directory, so a copy in
        # /tmp would look for the migrations there. Pin both paths absolute.
        parser.set("alembic", "script_location", str(API_DIR / "app/db/migrations"))
        parser.set("alembic", "prepend_sys_path", str(API_DIR))

        tmp_dir = Path(tempfile.mkdtemp(prefix="alembic-ini-pre-fix-"))
        self.addCleanup(shutil.rmtree, tmp_dir, ignore_errors=True)
        out = tmp_dir / "alembic.ini"
        with out.open("w", encoding="utf-8") as fh:
            parser.write(fh)
        return out


if __name__ == "__main__":
    unittest.main()
