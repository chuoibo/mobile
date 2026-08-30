#!/usr/bin/env python3
"""Mutation table for rd-do-22 -- hearts (F40) and comments (F41).

Each row edits ONE thing in the shipped source, runs the gate, restores the
tree, and records the colour. A row that expects RED proves the gate reacts to
that specific property going away. A row that expects GREEN -- the
property-preserving rows at the bottom -- proves the gate is measuring a
property and not merely "somebody touched this file".

Both directions are needed. A gate that goes red at every edit is as useless
as one that never goes red; it just wastes a person's afternoon first.

Run from the repo root, on a CLEAN tree, with Postgres up:

    MOBILE_TEST_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile' \
      python3 scripts/dot_bien_rd_do_22.py

Restore is `git checkout --`, which is why the tree must be committed first: an
uncommitted fix would be thrown away with the mutation. The `__pycache__` sweep
after each restore is not superstition -- a stale `.pyc` has previously made a
restored tree keep failing like the mutated one.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
API = REPO / "services" / "api"

SERVICE = "services/api/app/api/service.py"
REPOSITORY = "services/api/app/api/repository.py"
MODELS = "services/api/app/db/models.py"
MAIN = "services/api/app/api/main.py"
MIGRATION = (
    "services/api/app/db/migrations/versions/"
    "c5e14b7a9d02_them_tim_va_binh_luan_ky_niem.py"
)

PG_FILE = "tests/postgres/test_memory_reactions_postgres.py"
API_FILE = "tests/api/test_validation_error_redaction.py"


@dataclass
class Mutation:
    name: str
    expect: str  # "RED" or "GREEN"
    edits: list[tuple[str, str, str]]  # (path, old, new)
    target: str = PG_FILE
    # Which test names must be the ones that fail. A row that goes red for a
    # different reason than the one it names has proved nothing -- that is the
    # "red for the wrong reason" trap, and it reads exactly like a good gate.
    expect_failing: list[str] = field(default_factory=list)
    #: How many times each anchor is expected to appear. Stated rather than
    #: inferred: a rename touches a definition and its call sites, and the
    #: number of call sites is exactly the thing worth asserting. Leaving it
    #: implicit is how a mutation patches one copy and reports GREEN while the
    #: property is still gone from the other.
    occurrences: int = 1


MUTATIONS: list[Mutation] = [
    # ---------------------------------------------------------------- RED ---
    Mutation(
        name="1. bỏ hẳn phép kiểm quyền trong _memory_of_member",
        expect="RED",
        edits=[(
            SERVICE,
            """        _require_permission(
            action,
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )
        memory = self.repository.get_context_memory(context_id, memory_id)""",
            """        memory = self.repository.get_context_memory(context_id, memory_id)""",
        )],
        expect_failing=[
            "test_an_outsider_cannot_leave_a_heart",
            "test_an_outsider_cannot_comment",
            "test_an_invited_member_cannot_react_or_comment",
            "test_a_departed_member_cannot_react_or_comment",
        ],
    ),
    Mutation(
        name="2. tư cách thành viên đọc từ HEADER thay vì hỏi database (lỗ #253)",
        expect="RED",
        edits=[(
            SERVICE,
            """        _require_permission(
            action,
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )
        memory = self.repository.get_context_memory(context_id, memory_id)""",
            """        _require_permission(
            action,
            actor,
            {"is_group_member": context_id in actor.context_ids},
        )
        memory = self.repository.get_context_memory(context_id, memory_id)""",
        )],
        expect_failing=[
            "test_membership_is_read_from_the_database_not_from_the_header",
        ],
    ),
    Mutation(
        name="3. tra memory TRƯỚC khi kiểm quyền (403/404 thành oracle)",
        expect="RED",
        edits=[(
            SERVICE,
            """        _require_permission(
            action,
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )
        memory = self.repository.get_context_memory(context_id, memory_id)
        if memory is None:
            raise ApiProblem(404, "memory_not_found", "Memory does not exist")
        return memory""",
            """        memory = self.repository.get_context_memory(context_id, memory_id)
        if memory is None:
            raise ApiProblem(404, "memory_not_found", "Memory does not exist")
        _require_permission(
            action,
            actor,
            {"is_group_member": self.repository.is_member(context_id, actor.id)},
        )
        return memory""",
        )],
        expect_failing=["test_an_outsider_learns_nothing_about_which_ids_exist"],
    ),
    Mutation(
        name="4. gỡ unique index một-người-một-tim khỏi schema",
        expect="RED",
        edits=[
            (
                MODELS,
                """        UniqueConstraint("memory_id", "person_id", name="uq_memory_reactions_person"),
""",
                "",
            ),
            (
                MIGRATION,
                """        sa.UniqueConstraint(
            "memory_id", "person_id", name="uq_memory_reactions_person"
        ),
""",
                "",
            ),
        ],
        expect_failing=[
            "test_the_same_person_cannot_react_twice",
            "test_the_index_itself_refuses_a_duplicate_row",
            "test_the_schema_holds_the_cascade_and_the_unique_index",
        ],
    ),
    Mutation(
        name="5. get_context_memory bỏ vị từ context_id (memory nhóm khác với tới được)",
        expect="RED",
        edits=[(
            REPOSITORY,
            """            select(Memory).where(
                Memory.id == memory_id, Memory.context_id == context_id
            )""",
            """            select(Memory).where(Memory.id == memory_id)""",
        )],
        expect_failing=[
            "test_another_groups_memory_is_not_reachable_through_this_context",
        ],
    ),
    Mutation(
        name="6. gỡ tim theo memory, không theo người (gỡ được tim người khác)",
        expect="RED",
        edits=[(
            REPOSITORY,
            """            select(MemoryReaction).where(
                MemoryReaction.memory_id == memory_id,
                MemoryReaction.person_id == person_id,
            )""",
            """            select(MemoryReaction).where(
                MemoryReaction.memory_id == memory_id,
            )""",
        )],
        expect_failing=["test_one_member_cannot_remove_another_members_heart"],
    ),
    Mutation(
        name="7. bình luận ghi tên tác giả của ẢNH thay vì người gọi",
        expect="RED",
        edits=[(
            SERVICE,
            """        self._memory_of_member(context_id, memory_id, actor, "post_group_memory")
        record = self.repository.create_memory_comment(
            memory_id=memory_id,
            author_id=actor.id,""",
            """        memory = self._memory_of_member(
            context_id, memory_id, actor, "post_group_memory"
        )
        record = self.repository.create_memory_comment(
            memory_id=memory_id,
            author_id=memory.author_id,""",
        )],
        expect_failing=["test_a_comment_is_written_under_the_callers_name"],
    ),
    Mutation(
        name="8. đếm tim và bình luận bằng hai outer join (nhân hàng với nhau)",
        expect="RED",
        edits=[(
            REPOSITORY,
            """        reactions = {
            memory_id: int(total)
            for memory_id, total in self.session.execute(
                select(MemoryReaction.memory_id, func.count(MemoryReaction.id))
                .where(MemoryReaction.memory_id.in_(memory_ids))
                .group_by(MemoryReaction.memory_id)
            )
        }
        comments = {
            memory_id: int(total)
            for memory_id, total in self.session.execute(
                select(MemoryComment.memory_id, func.count(MemoryComment.id))
                .where(MemoryComment.memory_id.in_(memory_ids))
                .group_by(MemoryComment.memory_id)
            )
        }""",
            """        joined = list(
            self.session.execute(
                select(
                    Memory.id,
                    func.count(MemoryReaction.id),
                    func.count(MemoryComment.id),
                )
                .select_from(Memory)
                .outerjoin(MemoryReaction, MemoryReaction.memory_id == Memory.id)
                .outerjoin(MemoryComment, MemoryComment.memory_id == Memory.id)
                .where(Memory.id.in_(memory_ids))
                .group_by(Memory.id)
            )
        )
        reactions = {row[0]: int(row[1]) for row in joined}
        comments = {row[0]: int(row[2]) for row in joined}""",
        )],
        expect_failing=["test_hearts_and_comments_do_not_multiply_each_other"],
    ),
    Mutation(
        name="9. feed không truyền viewer_id (viewer_has_reacted luôn False)",
        expect="RED",
        edits=[(
            SERVICE,
            """            viewer_id=actor.id,
        )""",
            """            viewer_id=None,
        )""",
        )],
        expect_failing=["test_viewer_has_reacted_is_a_fact_about_the_reader"],
    ),
    Mutation(
        name="10. văn bản riêng tư của nhóm chảy vào một trường trang khách CÓ vẽ",
        expect="RED",
        edits=[(
            REPOSITORY,
            """        raw_envelope = {
            "recorded_by_display_name": recorded_by,""",
            """        _leaked = self.session.scalars(
            select(MemoryComment.body).limit(1)
        ).first()
        raw_envelope = {
            "recorded_by_display_name": recorded_by + (
                f" — {_leaked}" if _leaked else ""
            ),""",
        )],
        expect_failing=["test_a_group_comment_never_reaches_the_guest_page"],
    ),
    Mutation(
        name="11. gỡ handler 422 (thân lỗi đọc lại nguyên văn câu người ta gõ)",
        expect="RED",
        target=API_FILE,
        edits=[(
            MAIN,
            """    @application.exception_handler(RequestValidationError)
    async def validation_handler(""",
            """    async def validation_handler(""",
        )],
        expect_failing=[
            "test_a_too_long_comment_is_not_repeated_back",
            "test_a_too_long_group_message_is_not_repeated_back",
            "test_no_validation_error_anywhere_carries_an_input_key",
        ],
    ),
    # -------------------------------------------------------------- GREEN ---
    # Everything below KEEPS the property and changes something a person
    # tidying up would change. All four must stay green. A gate that reddens
    # here is a gate that gets switched off within a week.
    Mutation(
        name="GIỮ TÍNH CHẤT A. đổi tên hàm nội bộ _memory_social_counts",
        expect="GREEN",
        # Một định nghĩa và hai chỗ gọi. Con số 3 được KHAI ra chứ không suy ra:
        # nếu sau này thêm chỗ gọi thứ ba mà quên sửa số này, hàng sẽ dừng lại
        # thay vì lặng lẽ đổi tên hai phần ba rồi báo GREEN.
        occurrences=3,
        edits=[(REPOSITORY, "_memory_social_counts", "_wall_social_counts")],
    ),
    Mutation(
        name="GIỮ TÍNH CHẤT B. đổi câu chữ của lời từ chối 409 (giữ nguyên mã)",
        expect="GREEN",
        edits=[(
            SERVICE,
            '"This person has already reacted to this memory",',
            '"Bạn đã thả tim cho kỷ niệm này rồi",',
        )],
    ),
    Mutation(
        name="GIỮ TÍNH CHẤT C. đảo thứ tự hai câu đếm, và đếm bằng count() thay vì count(id)",
        expect="GREEN",
        edits=[(
            REPOSITORY,
            """        reactions = {
            memory_id: int(total)
            for memory_id, total in self.session.execute(
                select(MemoryReaction.memory_id, func.count(MemoryReaction.id))
                .where(MemoryReaction.memory_id.in_(memory_ids))
                .group_by(MemoryReaction.memory_id)
            )
        }
        comments = {
            memory_id: int(total)
            for memory_id, total in self.session.execute(
                select(MemoryComment.memory_id, func.count(MemoryComment.id))
                .where(MemoryComment.memory_id.in_(memory_ids))
                .group_by(MemoryComment.memory_id)
            )
        }""",
            """        comments = {
            memory_id: int(total)
            for memory_id, total in self.session.execute(
                select(MemoryComment.memory_id, func.count())
                .where(MemoryComment.memory_id.in_(memory_ids))
                .group_by(MemoryComment.memory_id)
            )
        }
        reactions = {
            memory_id: int(total)
            for memory_id, total in self.session.execute(
                select(MemoryReaction.memory_id, func.count())
                .where(MemoryReaction.memory_id.in_(memory_ids))
                .group_by(MemoryReaction.memory_id)
            )
        }""",
        )],
    ),
    Mutation(
        name="GIỮ TÍNH CHẤT D. đổi thứ tự cột trong index đọc bình luận",
        expect="GREEN",
        edits=[
            (
                MODELS,
                'Index("ix_memory_comments_memory", "memory_id", "created_at", "id"),',
                'Index("ix_memory_comments_memory", "memory_id", "id", "created_at"),',
            ),
            (
                MIGRATION,
                '        ["memory_id", "created_at", "id"],',
                '        ["memory_id", "id", "created_at"],',
            ),
        ],
    ),
]


def sweep_pycache() -> None:
    for cache in API.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def restore() -> None:
    subprocess.run(
        ["git", "checkout", "--", SERVICE, REPOSITORY, MODELS, MAIN, MIGRATION],
        cwd=REPO,
        check=True,
    )
    sweep_pycache()


def apply(mutation: Mutation) -> None:
    for rel, old, new in mutation.edits:
        path = REPO / rel
        text = path.read_text()
        found = text.count(old)
        if found != mutation.occurrences:
            restore()
            raise SystemExit(
                f"NEO KHỚP {found} LẦN, chờ {mutation.occurrences} cho "
                f"{mutation.name!r} trong {rel}.\n"
                "Khớp 0 lần là đột biến không xảy ra; khớp thừa là vá nhầm bản "
                "sao. Cả hai in ra một màu vô nghĩa."
            )
        path.write_text(text.replace(old, new, mutation.occurrences))
    # The mutation must actually be in the tree. `replace` on a string that was
    # already equal to its replacement writes the file back unchanged and the
    # run below would measure the shipped code while claiming otherwise.
    changed = subprocess.run(
        ["git", "diff", "--quiet", "--", *{rel for rel, _, _ in mutation.edits}],
        cwd=REPO,
    ).returncode
    if changed == 0:
        restore()
        raise SystemExit(f"ĐỘT BIẾN KHÔNG LÀM ĐỔI CÂY: {mutation.name!r}")
    sweep_pycache()


SUMMARY = re.compile(r"^=+ .*(passed|failed|error).* =+$", re.M)


def run_gate(target: str) -> tuple[int, str, set[str]]:
    env = dict(os.environ)
    env["MOBILE_REQUIRE_POSTGRES_TESTS"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", target, "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=API,
        env=env,
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    # Only the last summary line. Grepping the whole output picks up numbers
    # printed inside docstrings of the very tests being run.
    lines = SUMMARY.findall(out)
    tail = [line for line in out.splitlines() if " passed" in line or " failed" in line]
    summary = tail[-1].strip() if tail else (lines[-1] if lines else "<no summary>")
    failing = {
        line.split("::")[-1].split()[0]
        for line in out.splitlines()
        if line.startswith("FAILED ")
    }
    return proc.returncode, summary, failing


def main() -> int:
    if subprocess.run(["git", "diff", "--quiet"], cwd=REPO).returncode != 0:
        print("CÂY BẨN. Commit trước — restore ở đây là `git checkout --`.")
        return 2
    if "MOBILE_TEST_DATABASE_URL" not in os.environ:
        print("Thiếu MOBILE_TEST_DATABASE_URL. Bỏ qua KHÔNG PHẢI ĐẠT.")
        return 2

    print("=== ĐỐI CHỨNG: cây sạch, chưa đột biến ===")
    for target in (PG_FILE, API_FILE):
        code, summary, _ = run_gate(target)
        print(f"  {target}: rc={code}  {summary}")
        if code != 0:
            print("  Cây sạch đã đỏ. Dừng: mọi màu sau đây đều vô nghĩa.")
            return 2

    rows: list[tuple[Mutation, str, str, str]] = []
    for mutation in MUTATIONS:
        apply(mutation)
        try:
            code, summary, failing = run_gate(mutation.target)
        finally:
            restore()

        got = "RED" if code != 0 else "GREEN"
        verdict = "ĐÚNG" if got == mutation.expect else "SAI"
        if got == "RED" and mutation.expect == "RED" and mutation.expect_failing:
            missing = set(mutation.expect_failing) - failing
            if missing:
                verdict = f"ĐỎ NHẦM LÝ DO (thiếu: {sorted(missing)})"
        rows.append((mutation, got, verdict, summary))
        print(f"[{verdict:>4}] {mutation.name}\n        {got}  {summary}")

    print("\n=== BẢNG ===")
    width = max(len(m.name) for m, _, _, _ in rows)
    for mutation, got, verdict, summary in rows:
        print(f"{mutation.name:<{width}}  chờ {mutation.expect:<5} -> {got:<5}  {verdict}")

    bad = [row for row in rows if not row[2].startswith("ĐÚNG")]
    print(f"\n{len(rows) - len(bad)}/{len(rows)} hàng đúng dự đoán.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
