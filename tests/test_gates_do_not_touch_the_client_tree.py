"""Cổng không được dùng `apps/mobile/src` làm giấy nháp.

Hình dạng lỗi này đã cắn thật, ngày 2026-08-31: `scripts/gate.sh client-routes`
chạy song song với `pytest` in ra 77 lời gọi và 1 finding rồi thoát 1, còn lượt
chạy lại trên cây yên in 76 lời gọi và thoát 0. Cùng một commit, `git status`
rỗng ở CẢ HAI lượt. Không có gì để lần ra, vì thủ phạm là một file `.ts` do
chính bộ test thả vào cây client thật rồi tự xoá vài giây sau.

Vì sao nó tệ hơn một ca đỏ bình thường:

- Nó buộc tội SẢN PHẨM. Cổng header actor in "HỎNG — 1 chỗ gọi route đòi
  X-Actor-ID mà không gửi" rồi trỏ vào một file không nằm trong git. Người đọc
  log không có cách nào biết dòng đó nói về canary của chính cổng.
- Nó không tái lập được. File tự xoá, nên phiếu lỗi mở từ lượt đo đó dẫn người
  nhận tới một cây sạch.
- Nó làm lệch MỌI con số của bốn bộ đọc khác cùng soi thư mục đó. Đo được trong
  đúng cửa sổ đó: 67→68 đường dẫn, 79→80 lời gọi, 12→13 file (check_api_contract);
  53/54 màn đọc từ 126→127 file (check_screens_reachable); 21→22 chỗ dựng header
  (check_cors_contract). Repo này dùng đúng những con số ấy làm bằng chứng.

ĐO BẰNG inotify, KHÔNG bằng mtime hay lấy mẫu — và lý do đáng ghi lại:

Bản đầu của ca này so mtime của thư mục trước/sau, vì tạo-rồi-xoá một file có
đổi mtime thư mục kể cả khi danh sách file đã trở lại y hệt. Đối chứng dương
đã giết thiết kế đó: dấu thời gian inode của Linux lấy từ đồng hồ thô (cỡ vài
ms), nên một lượt `write_text()` + `unlink()` liền nhau nằm gọn trong MỘT tick
và mtime trước/sau bằng nhau tới từng nanosecond. Đo cạnh nhau trên cùng một
lượt tạo-rồi-xoá: mtime nói `False`, inotify nói `['__nhap__.ts', ...]`.

Lấy mẫu bằng vòng lặp cũng bị loại, vì cùng một lý do ở dạng khác: cửa sổ bẩn
của `--selftest` đo được chỉ khoảng 1ms, nên lấy mẫu 2ms bắt được nó theo xác
suất chứ không chắc chắn. Một cổng chỉ đúng theo xác suất là một cổng sẽ có
ngày xanh nhầm. inotify là sự kiện của nhân, không bỏ sót.

KHÔNG chứng minh: rằng cổng đọc client ĐÚNG. Ca này chỉ nói cổng chạy xong mà
không để lại dấu tay. Một cổng mù hoàn toàn cũng không để lại dấu tay.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import pathlib
import struct
import subprocess
import sys
import tempfile
import threading
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CLIENT_DIR = REPO_ROOT / "apps" / "mobile" / "src"

IN_CREATE = 0x00000100
IN_DELETE = 0x00000200
IN_MOVED_FROM = 0x00000040
IN_MOVED_TO = 0x00000080
IN_Q_OVERFLOW = 0x00004000

#: Chỉ những sự kiện đổi THÀNH PHẦN của cây. Cố ý bỏ IN_MODIFY và IN_CLOSE_WRITE:
#: sửa nội dung một file đã có là việc bình thường của một lane đang gõ code
#: trong worktree của mình, và bắt nó sẽ làm ca này đỏ giả.
WATCH_MASK = IN_CREATE | IN_DELETE | IN_MOVED_FROM | IN_MOVED_TO

_EVENT_HEAD = struct.Struct("iIII")


class InotifyWatch:
    """Ghi lại mọi file được tạo/xoá/đổi tên dưới `root` trong lúc watch mở.

    Sự kiện của nhân, nên không có cửa sổ nào ngắn tới mức lọt — đó là toàn bộ
    lý do lớp này tồn tại thay cho phép so mtime đơn giản hơn nhiều.
    """

    def __init__(self, root: pathlib.Path) -> None:
        self.root = root
        self.names: set[str] = set()
        self.overflowed = False
        self._fd = -1
        self._stop_r = -1
        self._stop_w = -1
        self._thread: threading.Thread | None = None
        self._libc = ctypes.CDLL(
            ctypes.util.find_library("c") or "libc.so.6", use_errno=True
        )

    def _drain(self) -> None:
        import select

        while True:
            r, _, _ = select.select([self._fd, self._stop_r], [], [])
            if self._fd in r:
                try:
                    buf = os.read(self._fd, 1 << 16)
                except (BlockingIOError, OSError):
                    buf = b""
                off = 0
                while off + _EVENT_HEAD.size <= len(buf):
                    _wd, mask, _cookie, ln = _EVENT_HEAD.unpack_from(buf, off)
                    raw = buf[off + _EVENT_HEAD.size : off + _EVENT_HEAD.size + ln]
                    name = raw.split(b"\0")[0].decode("utf-8", "replace")
                    if mask & IN_Q_OVERFLOW:
                        self.overflowed = True
                    if name:
                        self.names.add(name)
                    off += _EVENT_HEAD.size + ln
            if self._stop_r in r:
                return

    def __enter__(self) -> InotifyWatch:
        self._fd = self._libc.inotify_init1(0)
        if self._fd < 0:
            raise OSError(ctypes.get_errno(), "inotify_init1 thất bại")
        # Watch không đệ quy, nên phải cắm vào từng thư mục con. Thư mục MỚI
        # sinh ra giữa chừng không được cắm — nhưng chính lượt tạo nó là một
        # IN_CREATE trên thư mục cha, nên nó vẫn bị nêu tên.
        for d in [self.root, *(p for p in self.root.rglob("*") if p.is_dir())]:
            if self._libc.inotify_add_watch(self._fd, str(d).encode(), WATCH_MASK) < 0:
                raise OSError(ctypes.get_errno(), f"inotify_add_watch thất bại: {d}")
        self._stop_r, self._stop_w = os.pipe()
        self._thread = threading.Thread(target=self._drain, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        os.write(self._stop_w, b"x")
        if self._thread is not None:
            self._thread.join(timeout=10)
        for fd in (self._fd, self._stop_r, self._stop_w):
            try:
                os.close(fd)
            except OSError:
                pass


@unittest.skipUnless(sys.platform.startswith("linux"), "inotify chỉ có trên Linux")
class TheDetectorCanActuallySeeAWrite(unittest.TestCase):
    """ĐỐI CHỨNG DƯƠNG — trên thư mục tạm, không đụng cây client.

    Bỏ lớp này đi thì ca dưới trở thành thứ repo này bị cắn nhiều nhất: một phép
    đo luôn trả "sạch" vì nó không đo được gì. Đối chứng cố ý chạy trên thư mục
    TẠM: một đối chứng phải bẩn cây thật mới chứng minh được điều gì thì nó
    chính là cái lỗi đang bị đi bịt.
    """

    def test_it_sees_a_file_created_and_removed_inside_one_clock_tick(self):
        # Cố ý KHÔNG khẳng định gì về mtime ở đây. Bản nháp của ca này có thêm
        # một dòng `assertEqual(mtime_truoc, mtime_sau)` để ghi lại rằng mtime
        # mù — và chính nó đỏ khi chạy cả file, xanh khi chạy lẻ, vì nó phụ
        # thuộc vào chuỗi thao tác có vắt qua một tick đồng hồ hay không. Một
        # khẳng định đúng theo xác suất là thứ ca này tồn tại để loại bỏ, nên nó
        # bị gỡ. Lý do mtime bị loại nằm ở docstring đầu file, chỗ không đỏ được.
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            with InotifyWatch(root) as w:
                scratch = root / "__nhap__.ts"
                scratch.write_text("y", encoding="utf-8")
                scratch.unlink()

            self.assertEqual(
                sorted(p.name for p in root.iterdir()),
                [],
                "đối chứng dựng sai: file phải đã bị xoá, nếu không thì ca này "
                "chỉ đang đo một file còn sót chứ không đo dấu tay",
            )
            self.assertIn(
                "__nhap__.ts",
                w.names,
                "inotify KHÔNG thấy một lượt tạo-rồi-xoá — giác quan này mù, nên "
                "kết luận 'cây client sạch' ở dưới vô giá trị",
            )


@unittest.skipUnless(sys.platform.startswith("linux"), "inotify chỉ có trên Linux")
class NoGateUsesTheClientTreeAsScratchSpace(unittest.TestCase):
    def _assert_clean_while(self, argv: list[str], nhan: str) -> None:
        self.assertTrue(CLIENT_DIR.is_dir(), f"{CLIENT_DIR} biến mất")
        with InotifyWatch(CLIENT_DIR) as w:
            done = subprocess.run(
                argv, cwd=REPO_ROOT, capture_output=True, text=True, timeout=900
            )
        self.assertFalse(
            w.overflowed,
            "hàng đợi inotify tràn — ca này KHÔNG kết luận được là sạch, vì nó "
            "đã bỏ sót sự kiện",
        )
        self.assertEqual(
            sorted(w.names),
            [],
            f"{nhan} đụng vào cây client thật: {sorted(w.names)}\n"
            "Đây là thứ làm cổng của lane khác đỏ giả và buộc tội sản phẩm.\n"
            f"mã thoát {done.returncode}, stdout:\n{done.stdout[-2000:]}",
        )

    def test_the_actor_gate_selftest_leaves_the_client_tree_untouched(self):
        self._assert_clean_while(
            [sys.executable, "scripts/check_actor_headers.py", "--selftest"],
            "`check_actor_headers.py --selftest`",
        )

    def test_the_actor_gate_test_module_leaves_the_client_tree_untouched(self):
        self._assert_clean_while(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_actor_header_contract.py",
                "-q",
            ],
            "`pytest tests/test_actor_header_contract.py`",
        )


if __name__ == "__main__":
    unittest.main()
