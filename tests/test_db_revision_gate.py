"""Cổng "database có ở đúng head không" phải cắn, và phải cắn đúng bốn kiểu hỏng.

Ngày 2026-08-29, database dùng chung `mobile-local` bị đóng dấu
`8f1c6a4b2e70` — một revision đã bị đánh số lại và không còn nằm trong nhánh
nào. Mọi `alembic upgrade head` lên nó đã chết hàng giờ với "Can't locate
revision". API không hề hấn gì: nó đang chạy sẵn nên không ai chạy lại migrate,
và `/healthz` cố ý không chạm database. Cả bộ báo khoẻ trong khi
`GET /contexts/{id}/outings` trả 500 `UndefinedTable` cho mọi thành viên thật.

`scripts/check_alembic_heads.py` không bắt được ca này, và docstring của chính
nó đã nói trước là không: nó chứng minh các FILE migration thành một chuỗi, chứ
"không nói gì về việc một database đã bị đóng dấu cái gì". Cổng cho vế còn lại
là `scripts/check_db_revision.sh`, và đây là test của nó.

Hai nửa đều chịu lực, giống cổng ruff và cổng alembic head:

- Ca `_hong_*` chứng minh cổng **biết đỏ** — bốn kiểu hỏng, không phải một.
- Ca `_sach_*` chứng minh nó **biết im** khi đúng. Một cổng chỉ từng đỏ thì
  người ta tắt; một cổng chỉ từng xanh thì không phân biệt được với cổng hỏng.

Vì sao phải test cả bốn kiểu: mã thoát của `alembic current` KHÔNG đủ. Đo thật
trên Postgres 16 với ảnh `mobile-local/api:dev`:

    ở đúng head      "d4a2e7b91c30 (head)"     exit 0
    đứng sau         "7c3a8f2d1e6b"            exit 0   <-- vẫn xanh
    revision mồ côi  "FAILED: Can't locate..." exit 255
    chưa migrate     ""                        exit 0   <-- vẫn xanh

Hai dòng đánh dấu là lý do cổng này không thể chỉ là `alembic current || exit`.
Và dòng thứ ba là lý do phải đọc mã thoát TRƯỚC khi đọc chữ: alembic in
"FAILED:" ra **stdout**, nên cắt token đầu tiên mà không xét mã thoát sẽ nhận
được revision tên là "FAILED:".

Mọi ca gọi script thật qua subprocess và đọc mã thoát thật, vì mã thoát là thứ
`make smoke` thực sự đọc. Alembic được thay bằng stub để cổng test được trên
máy không có Docker; ca cuối chạy trên stack thật và **skip có ghi log** khi
không có Docker — skip không phải là xanh.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD = REPO_ROOT / "scripts" / "check_db_revision.sh"


class DbRevisionGate(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="db-revision-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def stub(
        self,
        *,
        current_out: str = "",
        current_status: int = 0,
        heads_out: str = "",
        heads_status: int = 0,
    ) -> str:
        """An `alembic` that answers exactly what a real one answered.

        The outputs used by the cases below were copied off real runs against
        Postgres 16, not invented -- including the detail that the orphan's
        "FAILED:" line comes out on stdout.
        """
        path = self.tmp / "alembic-stub"
        path.write_text(
            "#!/bin/sh\n"
            'case "$1" in\n'
            f'  current) printf %b "{_q(current_out)}"; exit {current_status};;\n'
            f'  heads)   printf %b "{_q(heads_out)}"; exit {heads_status};;\n'
            '  *) echo "stub: khong biet lenh $1" >&2; exit 64;;\n'
            "esac\n",
            encoding="utf-8",
        )
        path.chmod(0o755)
        return str(path)

    def run_guard(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["sh", str(GUARD), *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

    # -- it knows how to go red -------------------------------------------

    def test_hong_revision_mo_coi_bi_tu_choi(self) -> None:
        """Chính sự cố ngày 29/08: database đóng dấu revision không ai giữ."""
        stub = self.stub(
            current_out="FAILED: Can't locate revision identified by '8f1c6a4b2e70'\n",
            current_status=255,
            heads_out="d4a2e7b91c30 (head)\n",
        )

        result = self.run_guard(stub)

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("KHÔNG có trong mã nguồn", result.stderr)
        # Revision phải được gọi tên, nếu không thì người đọc phải tự đi tìm.
        self.assertIn("8f1c6a4b2e70", result.stderr)
        # Và phải chỉ đúng cái bẫy đã mất một giờ để phát hiện.
        self.assertIn("--purge", result.stderr)

    def test_hong_revision_mo_coi_khong_bi_doc_thanh_ten_revision(self) -> None:
        """Regression: "FAILED:" in ra stdout, không phải stderr.

        Cắt token đầu của stdout mà không xét mã thoát trước sẽ ra một revision
        tên là "FAILED:", rồi cổng báo "đứng sau" thay vì "mồ côi" — sai loại
        lỗi, và cách gỡ của hai loại khác hẳn nhau.
        """
        stub = self.stub(
            current_out="FAILED: Can't locate revision identified by '8f1c6a4b2e70'\n",
            current_status=255,
            heads_out="d4a2e7b91c30 (head)\n",
        )

        result = self.run_guard(stub)

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertNotIn("ĐỨNG SAU", result.stderr)
        self.assertNotIn("FAILED:", result.stdout)

    def test_hong_dung_sau_ma_nguon_bi_tu_choi(self) -> None:
        """Mã thoát 0 mà vẫn hỏng — ca mà `alembic current || exit 1` bỏ lọt."""
        stub = self.stub(
            current_out="7c3a8f2d1e6b\n",
            heads_out="d4a2e7b91c30 (head)\n",
        )

        result = self.run_guard(stub)

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("ĐỨNG SAU", result.stderr)
        self.assertIn("7c3a8f2d1e6b", result.stderr)
        self.assertIn("d4a2e7b91c30", result.stderr)

    def test_hong_chua_migrate_lan_nao_bi_tu_choi(self) -> None:
        """Database rỗng cũng exit 0 ở `current`. Rỗng không phải là khớp."""
        stub = self.stub(current_out="", heads_out="d4a2e7b91c30 (head)\n")

        result = self.run_guard(stub)

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("chưa chạy migration lần nào", result.stderr)

    def test_hong_ma_nguon_khong_co_head_bi_tu_choi(self) -> None:
        """ "Không có gì để so" không được phép đọc thành "khớp".

        Đây là hình dạng của mọi cổng chết trong repo này: không đọc được gì,
        nên không có gì để phàn nàn, nên xanh.
        """
        stub = self.stub(current_out="d4a2e7b91c30 (head)\n", heads_out="")

        result = self.run_guard(stub)

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("không khai head nào", result.stderr)

    def test_hong_hai_head_bi_tu_choi(self) -> None:
        stub = self.stub(
            current_out="d4a2e7b91c30 (head)\n",
            heads_out="d4a2e7b91c30 (head)\n8f1c6a4b2e70 (head)\n",
        )

        result = self.run_guard(stub)

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("2 head", result.stderr)

    def test_hong_khong_doc_duoc_head_bi_tu_choi(self) -> None:
        stub = self.stub(current_out="d4a2e7b91c30 (head)\n", heads_status=255)

        result = self.run_guard(stub)

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("không đọc được head", result.stderr)

    def test_hong_goi_thieu_tham_so(self) -> None:
        result = self.run_guard()

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("thiếu lệnh chạy alembic", result.stderr)

    # -- and how to stay quiet --------------------------------------------

    def test_sach_dung_head_thi_xanh(self) -> None:
        stub = self.stub(
            current_out="d4a2e7b91c30 (head)\n",
            heads_out="d4a2e7b91c30 (head)\n",
        )

        result = self.run_guard(stub)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("d4a2e7b91c30", result.stdout)

    def test_sach_khong_bi_lua_boi_nhan_head(self) -> None:
        """`current` in kèm " (head)", `heads` cũng vậy. So phải là so id."""
        stub = self.stub(
            current_out="d4a2e7b91c30 (head)\n",
            heads_out="d4a2e7b91c30\n",
        )

        result = self.run_guard(stub)

        self.assertEqual(result.returncode, 0, result.stderr)

    # -- trên stack thật ---------------------------------------------------

    def test_stack_that_o_dung_head(self) -> None:
        """Ca duy nhất chứng minh cổng đúng với alembic THẬT, không phải stub.

        Skip có ghi log khi thiếu Docker hoặc thiếu stack — skip không phải là
        xanh, và một ca skip im lặng là cách cổng này sẽ chết mà không ai biết.
        """
        if shutil.which("docker") is None:
            self.skipTest("không có docker — không kiểm được stack thật")
        project = os.environ.get("MOBILE_PROJECT", "mobile-local")
        probe = subprocess.run(
            [
                "docker",
                "compose",
                "-p",
                project,
                "ps",
                "--services",
                "--filter",
                "status=running",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        if probe.returncode != 0 or "api" not in probe.stdout.split():
            self.skipTest(f"stack '{project}' chưa chạy — 'make up' trước")

        result = subprocess.run(
            ["make", "db-check"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            result.returncode,
            0,
            f"database của stack '{project}' không ở head:\n"
            f"{result.stdout}{result.stderr}",
        )


def _q(text: str) -> str:
    """Escape for a double-quoted sh string on ONE line of the generated stub.

    Newlines become `\\n` (hence `printf %b` at the call site): a real newline
    here would split the `case` arm across lines and the stub would not parse.
    """
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$")
    return escaped.replace("\n", "\\n")


if __name__ == "__main__":
    unittest.main()
