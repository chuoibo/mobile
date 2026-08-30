#!/usr/bin/env python3
"""Bảng đột biến cho probe rò rỉ F31/F33/F36 (PR #301).

Một dấu xanh không chứng minh cổng nào cả. Script này tắt từng bất biến một
trong code sản phẩm, chạy lại hai bộ test, và in ra bộ nào ĐỎ.

Hai cột, cố ý: bộ của tác giả PR và probe của QA. Cùng một đột biến làm đỏ cả
hai là chuyện tốt; đột biến chỉ làm đỏ một cột là chỗ cột kia đang mù.

Bảng có hàng GIỮ (`keeps_property=True`): đột biến đổi code nhưng KHÔNG phá
tính chất đang được gác. Hàng đó phải XANH. Một bảng toàn đỏ không phân biệt
được "cổng tốt" với "bất kỳ chỉnh sửa nào cũng làm vỡ thứ gì đó".

Chạy từ services/api:

    MOBILE_TEST_DATABASE_URL=... MOBILE_REQUIRE_POSTGRES_TESTS=1 \
        python3 scripts/mutation_rd_qa_45.py
"""

from __future__ import annotations

import dataclasses
import pathlib
import subprocess
import sys

API_ROOT = pathlib.Path(__file__).resolve().parents[1] / "services" / "api"
REPOSITORY = API_ROOT / "app" / "api" / "repository.py"
SERVICE = API_ROOT / "app" / "api" / "service.py"

AUTHOR_TESTS = "tests/postgres/test_group_intelligence_postgres.py"
PROBE_TESTS = "tests/postgres/test_group_intelligence_leak_probe_postgres.py"

# The real `is_member`, not the Protocol stub one screen above it. The stub is
# a single line ending in `...`; anchoring on three lines of the body is what
# keeps this from patching the copy that has no behaviour to break.
IS_MEMBER_IMPL = """    def is_member(self, context_id: uuid.UUID, person_id: uuid.UUID) -> bool:
        return (
            self.session.scalar("""


@dataclasses.dataclass(frozen=True)
class Mutant:
    name: str
    why: str
    path: pathlib.Path
    old: str
    new: str
    keeps_property: bool = False


MUTANTS = (
    Mutant(
        name="is_member luôn True",
        why="cổng quyền của cả ba tính năng biến mất",
        path=REPOSITORY,
        old=IS_MEMBER_IMPL,
        new="""    def is_member(self, context_id: uuid.UUID, person_id: uuid.UUID) -> bool:
        return True
        return (
            self.session.scalar(""",
    ),
    Mutant(
        name="is_member bỏ điều kiện ACTIVE",
        why="người đã rời nhóm vẫn còn hàng membership, và lại đọc được",
        path=REPOSITORY,
        old=IS_MEMBER_IMPL
        + """
                select(Membership.id)
                .where(
                    Membership.context_id == context_id,
                    Membership.person_id == person_id,
                    Membership.state == MembershipState.ACTIVE,
                    Membership.left_at.is_(None),""",
        new=IS_MEMBER_IMPL
        + """
                select(Membership.id)
                .where(
                    Membership.context_id == context_id,
                    Membership.person_id == person_id,""",
    ),
    Mutant(
        name="album bỏ mệnh đề context_id",
        why="cửa sổ ngày thuần: ảnh của nhóm khác lọt vào album và vào ảnh bìa",
        path=REPOSITORY,
        old="""                    Memory.context_id == outing.context_id,
                    _wall_clock_date(Memory.created_at).between(""",
        new="""                    _wall_clock_date(Memory.created_at).between(""",
    ),
    Mutant(
        name="album bỏ kiểm chuyến đi thuộc context",
        why="thành viên nhóm nào cũng đọc được album của nhóm khác bằng outing_id",
        path=SERVICE,
        old="""                if record.outing.id == outing_id""",
        new="""                if True""",
    ),
    # --- hàng GIỮ tính chất: phải XANH -------------------------------------
    Mutant(
        name="GIỮ: is_member đảo thứ tự hai mệnh đề WHERE",
        why="cùng một tập hàng, chỉ khác thứ tự AND -- tính chất không đổi",
        path=REPOSITORY,
        old=IS_MEMBER_IMPL
        + """
                select(Membership.id)
                .where(
                    Membership.context_id == context_id,
                    Membership.person_id == person_id,""",
        new=IS_MEMBER_IMPL
        + """
                select(Membership.id)
                .where(
                    Membership.person_id == person_id,
                    Membership.context_id == context_id,""",
        keeps_property=True,
    ),
    Mutant(
        name="GIỮ: album đổi thứ tự sắp xếp ảnh",
        why="cùng tập ảnh của cùng nhóm, chỉ khác thứ tự -- không phải rò rỉ",
        path=REPOSITORY,
        old="""                )
                .order_by(Memory.created_at.desc(), Memory.id.desc())""",
        new="""                )
                .order_by(Memory.created_at.asc(), Memory.id.asc())""",
        keeps_property=True,
    ),
)


def _run(test_path: str) -> tuple[bool, str]:
    """True nghĩa là XANH. Trả kèm dòng tóm tắt của pytest."""

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", test_path, "-q", "--no-header", "-x"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    tail = [line for line in proc.stdout.splitlines() if line.strip()]
    return proc.returncode == 0, tail[-1] if tail else "(không có output)"


def _assert_baseline_actually_ran() -> None:
    """Cây sạch phải XANH *và* phải thực sự chạy ca nào đó.

    Thiếu `MOBILE_TEST_DATABASE_URL`, cả hai file skip sạch và pytest thoát 0.
    Khi đó mọi hàng GIỮ đọc là XANH vì không có gì chạy, và bảng này trở thành
    một tờ giấy nói rằng probe gác tốt trong khi nó chưa từng chạy một lần.
    """

    for label, path in (("tác giả", AUTHOR_TESTS), ("probe", PROBE_TESTS)):
        green, tail = _run(path)
        if not green:
            raise SystemExit(f"DỪNG: {label} đã ĐỎ trên cây sạch -- {tail}")
        if " passed" not in tail or "skipped" in tail and "passed" not in tail:
            raise SystemExit(f"DỪNG: {label} không chạy ca nào -- {tail}")
        print(f"nền sạch {label}: {tail}", file=sys.stderr)


def main() -> int:
    _assert_baseline_actually_ran()
    rows = []
    for mutant in MUTANTS:
        source = mutant.path.read_text()
        hits = source.count(mutant.old)
        if hits != 1:
            print(
                f"DỪNG: neo của {mutant.name!r} khớp {hits} chỗ, cần đúng 1. "
                "Neo trùng là cách vá nhầm bản sao và báo xanh giả.",
                file=sys.stderr,
            )
            return 2

        mutant.path.write_text(source.replace(mutant.old, mutant.new, 1))
        try:
            author_green, author_tail = _run(AUTHOR_TESTS)
            probe_green, probe_tail = _run(PROBE_TESTS)
        finally:
            mutant.path.write_text(source)

        rows.append((mutant, author_green, author_tail, probe_green, probe_tail))
        print(
            f"  {mutant.name}: tác giả={'XANH' if author_green else 'ĐỎ'} "
            f"probe={'XANH' if probe_green else 'ĐỎ'}",
            file=sys.stderr,
        )

    # Cây phải sạch trở lại, nếu không mọi số ở trên là số của cây đã bị sửa.
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "app/"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        print(f"DỪNG: cây chưa sạch sau khi khôi phục:\n{dirty}", file=sys.stderr)
        return 2

    print()
    print("| Đột biến | Tính chất | Bộ tác giả | Probe QA |")
    print("|---|---|---|---|")
    failures = []
    for mutant, author_green, _, probe_green, _ in rows:
        want = "GIỮ" if mutant.keeps_property else "PHÁ"
        author = "XANH" if author_green else "ĐỎ"
        probe = "XANH" if probe_green else "ĐỎ"
        print(f"| {mutant.name} | {want} | {author} | {probe} |")

        if mutant.keeps_property and not probe_green:
            failures.append(f"{mutant.name}: giữ tính chất mà probe vẫn đỏ")
        if not mutant.keeps_property and probe_green:
            failures.append(f"{mutant.name}: phá tính chất mà probe vẫn xanh")

    print()
    for mutant, _, _, _, _ in rows:
        print(f"- {mutant.name}: {mutant.why}")

    if failures:
        print("\nKẾT LUẬN: probe KHÔNG gác được:", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1

    print("\nKẾT LUẬN: mọi đột biến PHÁ đều làm probe đỏ; mọi đột biến GIỮ vẫn xanh.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
