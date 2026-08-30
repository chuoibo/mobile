#!/usr/bin/env python3
"""Bảng đột biến hai cột cho F38 — widget ảnh mới nhất của nhóm.

Chạy từ gốc repo:

    python3 scripts/qc/dot_bien_f38_widget.py

## Nó trả lời câu gì

"Hai tầng test của F38 có thật sự gác `read_context_widget` không, hay chúng
xanh vì cây sạch?" Cách duy nhất biết được là làm hỏng sản phẩm rồi xem tầng
nào đỏ. Một bộ test xanh trên cây sạch không nói gì cả.

## Vì sao hai cột chứ không một số tổng

`tests/api/test_widget_leak.py` chạy trên repository giả; `is_member` của nó
là một phép tra `set`. `tests/postgres/test_widget_privacy_postgres.py` chạy
trên PostgreSQL thật sau khi Alembic migrate. Gộp hai tầng thành một con số
"đỏ/xanh" thì một tầng mù hoàn toàn vẫn đọc y hệt một tầng gác tốt — miễn là
tầng kia đỏ. Hai cột nói rõ tầng nào bắt được cái gì, và ô nào trống.

## Vì sao bảng có hàng ĐỐI CHỨNG phải XANH

Một bảng toàn đỏ không phân biệt được "cổng gác đúng tính chất" với "cổng đỏ
với mọi thay đổi". Hai hàng `C*` bên dưới đổi mã thật của widget nhưng GIỮ
nguyên tính chất (ai đọc được, đọc được cái gì). Chúng phải XANH. Nếu chúng
cũng đỏ thì bảng này không đo tính chất, nó đo "có ai sờ vào file không".

## Nó KHÔNG chứng minh gì

- Không chứng minh widget đúng với người dùng thật. Không có trình duyệt, không
  có điện thoại, không có ảnh thật nào được vẽ ra ở đây.
- Không chứng minh mọi đường ghi vào `memories` đều an toàn. Nó đột biến đúng
  một hàm.
- Tầng postgres bị SKIP nếu thiếu `MOBILE_TEST_DATABASE_URL`. Skip không phải
  xanh, và bảng in ra chữ `SKIP` chứ không im lặng đổi nó thành dấu tích.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
API = REPO / "services" / "api"
SERVICE = API / "app" / "api" / "service.py"

FAKE_LAYER = "tests/api/test_widget_leak.py"
LIVE_LAYER = "tests/postgres/test_widget_privacy_postgres.py"

#: Mọi phép thay chuỗi bên dưới chỉ được áp dụng TRONG thân hàm này. Chuỗi
#: `{"is_group_member": self.repository.is_member(context_id, actor.id)}` xuất
#: hiện hơn hai mươi lần trong `service.py`; một `str.replace(..., 1)` toàn file
#: sẽ vá nhầm `confirm_expense` rồi báo ĐỎ vì một lý do không liên quan tới F38.
METHOD_HEAD = "    def read_context_widget("
METHOD_END = "    # -- F43 / F44 / F45: where the group goes"


@dataclass(frozen=True)
class Row:
    key: str
    label: str
    old: str
    new: str
    #: True = phải làm test ĐỎ. False = hàng đối chứng, phải giữ XANH.
    must_break: bool


ROWS = (
    Row(
        key="M1",
        label="hỏi DB -> tin luôn là thành viên (is_member(...) -> True)",
        old='{"is_group_member": self.repository.is_member(context_id, actor.id)}',
        new='{"is_group_member": True}',
        must_break=True,
    ),
    Row(
        key="M2",
        label="đổi quyền sang một action KHÔNG đòi is_group_member (create_post)",
        old='"view_group_memories",',
        new='"create_post",',
        must_break=True,
    ),
    Row(
        key="M3",
        label='bỏ lọc kind="photo" -> check-in mới hơn làm widget trống',
        old='self.repository.list_memories(context_id, limit=1, kind="photo")',
        new="self.repository.list_memories(context_id, limit=1)",
        must_break=True,
    ),
    Row(
        key="M4",
        label="bỏ luôn lời gọi _require_permission (không gác gì)",
        old='        _require_permission(\n            "view_group_memories",',
        new='        _skip_permission(\n            "view_group_memories",',
        must_break=True,
    ),
    Row(
        key="C1",
        label="ĐỐI CHỨNG: limit=1 -> limit=5 (vẫn lấy phần tử [0], newest-first)",
        old='list_memories(context_id, limit=1, kind="photo")',
        new='list_memories(context_id, limit=5, kind="photo")',
        must_break=False,
    ),
    Row(
        key="C2",
        label="ĐỐI CHỨNG: đổi cách lấy phần tử đầu sang next(iter(...), None)",
        old="newest = page.memories[0] if page.memories else None",
        new="newest = next(iter(page.memories), None)",
        must_break=False,
    ),
)

#: `M4` cần một hàm nuốt lời gọi mà không quyết gì. Chèn nó vào cùng lượt vá,
#: nếu không thì `NameError` sẽ làm mọi ca đỏ vì lý do sai — đúng cái bẫy
#: "đột biến với biến ngoài scope đọc nhầm là bắt được".
SKIP_HELPER = (
    "\n\ndef _skip_permission(action, actor, context, **kwargs):\n"
    "    del action, actor, context, kwargs\n\n\n"
)
SKIP_ANCHOR = "def _require_permission(\n"


def method_span(source: str) -> tuple[int, int]:
    start = source.index(METHOD_HEAD)
    end = source.index(METHOD_END, start)
    return start, end


def mutate(source: str, row: Row) -> str:
    """Vá đúng một chỗ, trong đúng một hàm, hoặc dừng hẳn.

    Không có đường "không tìm thấy neo thì bỏ qua". Neo trượt mà vẫn chạy tiếp
    thì bảng in ra một hàng XANH cho một đột biến chưa từng được áp dụng, và
    hàng đó đọc y hệt một hàng đối chứng thật.
    """

    start, end = method_span(source)
    body = source[start:end]
    hits = body.count(row.old)
    if hits != 1:
        raise SystemExit(
            f"[{row.key}] neo khớp {hits} lần trong read_context_widget, cần đúng 1.\n"
            f"    neo: {row.old!r}\n"
            "    Sản phẩm đã đổi -> sửa neo trước khi tin bảng này."
        )
    patched = source[:start] + body.replace(row.old, row.new) + source[end:]
    if row.key == "M4":
        anchor = patched.index(SKIP_ANCHOR)
        patched = patched[:anchor] + SKIP_HELPER.lstrip("\n") + patched[anchor:]
    return patched


def run_layer(target: str, env_extra: dict[str, str] | None = None) -> str:
    env = dict(os.environ)
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            target,
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=API,
        capture_output=True,
        text=True,
        env=env,
    )
    tail = proc.stdout.strip().splitlines()
    summary = tail[-1] if tail else "(không có output)"
    if " no tests ran" in summary or "error" in summary.lower():
        return f"LỖI HARNESS ({summary})"
    if proc.returncode == 0 and "skipped" in summary and "passed" not in summary:
        return f"SKIP ({summary})"
    verdict = "XANH" if proc.returncode == 0 else "ĐỎ"
    return f"{verdict} ({summary})"


def live_env() -> tuple[dict[str, str] | None, str | None]:
    url = os.environ.get("MOBILE_TEST_DATABASE_URL")
    if not url:
        return None, "MOBILE_TEST_DATABASE_URL chưa đặt"
    return {"MOBILE_TEST_DATABASE_URL": url, "MOBILE_REQUIRE_POSTGRES_TESTS": "1"}, None


def main() -> int:
    original = SERVICE.read_text(encoding="utf-8")
    # Neo phải có mặt TRƯỚC khi chạm vào bất cứ thứ gì; nếu không, thà dừng còn
    # hơn in một bảng đo hàm khác.
    method_span(original)

    env_extra, why_skip = live_env()
    if why_skip:
        print(f"!! tầng live sẽ SKIP: {why_skip}\n")

    print("BASELINE (cây sạch, chưa đột biến)")
    base_fake = run_layer(FAKE_LAYER)
    base_live = "SKIP (thiếu URL)" if why_skip else run_layer(LIVE_LAYER, env_extra)
    print(f"  {FAKE_LAYER:<48} {base_fake}")
    print(f"  {LIVE_LAYER:<48} {base_live}\n")
    if not base_fake.startswith("XANH"):
        raise SystemExit("baseline tầng fake không xanh — không đo đột biến được")
    if not (base_live.startswith("XANH") or base_live.startswith("SKIP")):
        raise SystemExit("baseline tầng live không xanh — không đo đột biến được")

    print(f"{'':4} {'đột biến':<62} {'fake':<22} live")
    failures: list[str] = []
    for row in ROWS:
        patched = mutate(original, row)
        try:
            # Ghi lại bản gốc từ BỘ NHỚ, không phải `git checkout --`: bản sửa
            # chưa commit sẽ bị lệnh git xoá mất cùng với đột biến.
            SERVICE.write_text(patched, encoding="utf-8")
            fake = run_layer(FAKE_LAYER)
            live = "SKIP (thiếu URL)" if why_skip else run_layer(LIVE_LAYER, env_extra)
        finally:
            SERVICE.write_text(original, encoding="utf-8")

        print(f"{row.key:<4} {row.label:<62} {fake:<22} {live}")

        want = "ĐỎ" if row.must_break else "XANH"
        got_fake = fake.split(" ")[0]
        got_live = live.split(" ")[0]
        if row.must_break:
            # Đủ điều kiện khi ÍT NHẤT một tầng bắt được, nhưng ô mù được in ra
            # chứ không bị làm tròn thành đạt.
            if got_fake != "ĐỎ" and got_live != "ĐỎ":
                failures.append(f"{row.key}: không tầng nào đỏ, cần {want}")
            elif got_fake != "ĐỎ":
                print(f"     ^ ghi chú: tầng fake mù với {row.key}")
            elif got_live not in {"ĐỎ", "SKIP"}:
                print(f"     ^ ghi chú: tầng live mù với {row.key}")
        else:
            if got_fake != "XANH" or got_live not in {"XANH", "SKIP"}:
                failures.append(
                    f"{row.key}: hàng đối chứng phải XANH cả hai tầng "
                    f"(fake={got_fake}, live={got_live})"
                )

    print()
    if failures:
        for line in failures:
            print(f"HỎNG  {line}")
        return 1
    print(
        f"ĐẠT   {len(ROWS)} hàng đúng kỳ vọng "
        f"({sum(1 for r in ROWS if r.must_break)} phải đỏ, "
        f"{sum(1 for r in ROWS if not r.must_break)} đối chứng phải xanh)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
