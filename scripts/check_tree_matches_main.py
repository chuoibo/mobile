#!/usr/bin/env python3
"""The tree you are about to build a bundle from must be the tree `main` describes.

## Why this exists

At 03:20 on 2026-08-31 a bundle was exported from a checkout that was four
commits behind `origin/main` and had tracked files sitting in the "deleted"
state. That bundle was published to the demo box. It was missing whole screens
(`AlbumChuyenDi`, `CaNhanHoa`). Every signal on the machine stayed green and
every request answered 200, because *nothing along the path ever compared the
tree to `main`*. The build read the tree, the gates read the same tree, the
server served what it was given.

Re-measured on this machine at 2026-08-31T06:0xZ, before this gate existed:

    $ git -C /tmp/repro0320 status --porcelain
     D apps/mobile/src/screens/album/AlbumChuyenDi.tsx
     D apps/mobile/src/screens/vao-cua/CaNhanHoa.tsx
    $ python3 scripts/check_screens_reachable.py        # in that same tree
    51/52 màn có đường render từ cửa vào · 1 pin · 124 file đã đọc
    exit 0

    # the same command, one directory away, on a clean checkout of origin/main:
    53/54 màn có đường render từ cửa vào · 1 pin · 126 file đã đọc

Two screens vanished and the gate said 51/52 and passed. The denominator moved
with the numerator, because both sides of that check are read from one tree. A
check whose reference and whose subject are the same file cannot detect that
the file is wrong -- it reads exactly like a check that is passing. That is the
same green-by-construction shape `check_demo_matches_main.py` was written for,
one layer down: that one compares the *server* to main, this one compares the
*tree the artifact is built from* to main.

## The one thing it answers

    Cây đang dùng để dựng CÓ khớp origin/main không?

and it answers in exactly one of three words, never a fourth:

    KHỚP             exit 0   build away
    LỆCH             exit 1   and it says by how many commits, and which files
    KHÔNG KIỂM ĐƯỢC  exit 2   and it says what it could not do

"Could not run" is deliberately not folded into "found a problem" and even more
deliberately not folded into "fine". A gate that degrades to a pass when git is
missing or the fetch fails is worse than no gate, because it is trusted.

## Why the dirty-tree half is not a formality

The obvious reading of the 03:20 story is "the checkout was behind, so check
`HEAD == origin/main`". That check alone would not have caught it. Measured:

    $ git reset --hard origin/main~4
    $ rm apps/mobile/src/screens/album/AlbumChuyenDi.tsx   # tracked, now deleted
    $ git pull -q --ff-only
    $ echo $?
    0                              <-- succeeded, printed nothing at all
    $ git rev-parse HEAD; git rev-parse origin/main
    c205f959a91f4916da9e6efa28ff87a026308b50
    c205f959a91f4916da9e6efa28ff87a026308b50     <-- identical
    $ git status --porcelain
     D apps/mobile/src/screens/album/AlbumChuyenDi.tsx    <-- still gone

A fast-forward does not restore a file you deleted underneath it. So the tree
ends up at *exactly* main's SHA while still missing the screen, and a HEAD-only
gate prints KHỚP over a bundle that is missing a screen. Both halves are load
bearing, and the file half is the one that catches the case with no error
message anywhere in it.

(The report said `-q` hid the failure. `-q` did not: when the incoming commits
touch a file you modified, `git pull -q --ff-only` still writes 197 bytes to
stderr and exits 1 -- measured. The genuinely silent case is the one above,
where there is no error to hide because git did not fail. That is why this gate
asks the tree what state it is in rather than asking whether some earlier
command succeeded.)

## Why it fetches

Comparing against an `origin/main` that has not itself been fetched is the same
bug one layer up: a stale reference cannot detect staleness. So it fetches, and
if it cannot, it exits 2 rather than comparing against a ref of unknown age.
`--no-fetch` is the explicit offline escape hatch and it prints that it was
used, because a gate that silently narrows its own question is the thing this
file argues against.

## What it does NOT prove

- Nothing here builds anything. A tree that matches `main` perfectly can still
  export a broken bundle; `make gate ONLY=mobile` is what answers that.
- It says nothing about what is already serving on the demo box. This runs
  *before* the export; `check_demo_matches_main.py` and `demo_watch.py` are the
  ones that ask what is live now.
- It compares the tree to a ref, not the bundle to the tree. If the export
  reads from a stale cache (`--clear` exists for that reason) this gate is
  green and the artifact is still wrong.
- Ignored files are invisible to it, by git's definition of ignored. A bundler
  that reads something in `.gitignore` reads something this gate cannot see.

Usage:
  scripts/check_tree_matches_main.py                     # the tree this script lives in
  scripts/check_tree_matches_main.py --tree /home/lakiet/mobile
  scripts/check_tree_matches_main.py --pham-vi apps/mobile     # narrow the file half
  scripts/check_tree_matches_main.py --no-fetch --json
  scripts/check_tree_matches_main.py --selftest          # prove it can still bite

Exit codes: 0 KHỚP, 1 LỆCH, 2 KHÔNG KIỂM ĐƯỢC.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_REF = "origin/main"

EXIT_KHOP = 0
EXIT_LECH = 1
EXIT_KHONG_KIEM_DUOC = 2

STATE_KHOP = "KHỚP"
STATE_LECH = "LỆCH"
STATE_KHONG_KIEM_DUOC = "KHÔNG KIỂM ĐƯỢC"

EXIT_FOR_STATE = {
    STATE_KHOP: EXIT_KHOP,
    STATE_LECH: EXIT_LECH,
    STATE_KHONG_KIEM_DUOC: EXIT_KHONG_KIEM_DUOC,
}

GIT_TIMEOUT = 120


class KhongKiemDuoc(Exception):
    """The gate could not do its job. Never degrades to a pass."""


@dataclass
class Verdict:
    """One answer, plus every number a reader needs to check it by hand."""

    state: str
    tree: str
    ref: str
    head: str | None = None
    ref_sha: str | None = None
    ahead: int = 0
    behind: int = 0
    fetched: bool = False
    scope: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    staged: list[str] = field(default_factory=list)
    conflicted: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    untracked_ignored_by_flag: bool = False
    reason: str | None = None

    @property
    def dirty(self) -> list[str]:
        """Every tracked-file complaint, in one list, for the summary line."""
        return self.deleted + self.modified + self.staged + self.conflicted

    def to_json(self) -> dict:
        return {
            "state": self.state,
            "tree": self.tree,
            "ref": self.ref,
            "head": self.head,
            "ref_sha": self.ref_sha,
            "ahead": self.ahead,
            "behind": self.behind,
            "fetched": self.fetched,
            "scope": self.scope,
            "deleted": self.deleted,
            "modified": self.modified,
            "staged": self.staged,
            "conflicted": self.conflicted,
            "untracked": self.untracked,
            "untracked_ignored_by_flag": self.untracked_ignored_by_flag,
            "reason": self.reason,
        }


def git(tree: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run git inside `tree`, capturing both streams so failures can be quoted."""
    if shutil.which("git") is None:
        raise KhongKiemDuoc("không tìm thấy `git` trên PATH")
    try:
        return subprocess.run(
            ["git", "-C", str(tree), *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise KhongKiemDuoc(f"`git {' '.join(args)}` quá {GIT_TIMEOUT}s không trả lời")


def git_out(tree: Path, *args: str) -> str:
    """Run git and require success; anything else means the gate cannot answer."""
    done = git(tree, *args)
    if done.returncode != 0:
        detail = (done.stderr or done.stdout).strip().splitlines()
        first = detail[0] if detail else f"thoát {done.returncode}"
        raise KhongKiemDuoc(f"`git {' '.join(args)}` hỏng: {first}")
    return done.stdout.strip()


def doc_trang_thai(tree: Path, scope: list[str]) -> dict[str, list[str]]:
    """Split `git status --porcelain -z` into the categories that matter here.

    `-z` rather than newline splitting: a path with a newline or a quote in it
    would otherwise be silently mis-parsed, and a gate that loses a file from
    its own input is a gate that passes when it should not.
    """
    args = ["status", "--porcelain=v1", "-z", "--untracked-files=normal"]
    if scope:
        args += ["--", *scope]
    done = git(tree, *args)
    if done.returncode != 0:
        detail = (done.stderr or done.stdout).strip().splitlines()
        first = detail[0] if detail else f"thoát {done.returncode}"
        raise KhongKiemDuoc(f"`git status` hỏng: {first}")
    # NOT .strip(): a porcelain entry for an unstaged change begins with a
    # space (" D path"), and stripping the output shifts the first entry one
    # character left -- which silently renames the file in the report rather
    # than failing. The selftest caught exactly that ("an0.tsx").
    raw = done.stdout.rstrip("\0")

    out: dict[str, list[str]] = {
        "deleted": [],
        "modified": [],
        "staged": [],
        "conflicted": [],
        "untracked": [],
    }
    if not raw:
        return out

    fields = raw.split("\0")
    i = 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if not entry:
            continue
        code, path = entry[:2], entry[3:]
        # A rename carries its original path as the next NUL-separated field.
        if code[0] in ("R", "C"):
            i += 1
        if code == "??":
            out["untracked"].append(path)
        elif "U" in code or code in ("AA", "DD"):
            out["conflicted"].append(path)
        elif "D" in code:
            out["deleted"].append(path)
        elif code[1] == "M" or code[1] == "T":
            out["modified"].append(path)
        else:
            # Staged-only: index differs from HEAD (A, M, R, C in slot 0).
            out["staged"].append(path)

    for key in out:
        out[key].sort()
    return out


def danh_gia(
    tree: Path,
    ref: str = DEFAULT_REF,
    *,
    fetch: bool = True,
    scope: list[str] | None = None,
    ignore_untracked: bool = False,
) -> Verdict:
    """Answer the one question. Raises KhongKiemDuoc when it cannot."""
    scope = list(scope or [])
    tree = Path(tree)

    if not tree.exists():
        raise KhongKiemDuoc(f"không có thư mục {tree}")

    inside = git(tree, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        raise KhongKiemDuoc(f"{tree} không phải cây làm việc của git")

    # Resolve the real root: --tree may point at a subdirectory, and reporting
    # the subdirectory as "the tree used to build" would be a quiet lie.
    root = Path(git_out(tree, "rev-parse", "--show-toplevel"))

    fetched = False
    if fetch:
        remote = ref.split("/", 1)[0] if "/" in ref else "origin"
        done = git(root, "fetch", remote, "--quiet")
        if done.returncode != 0:
            detail = (done.stderr or done.stdout).strip().splitlines()
            first = detail[-1] if detail else f"thoát {done.returncode}"
            raise KhongKiemDuoc(
                f"không fetch được `{remote}`: {first}\n"
                f"   So với một {ref} chưa fetch là đúng cái lỗi này lùi một tầng:\n"
                f"   một mốc cũ không phát hiện được sự cũ. Offline thì --no-fetch."
            )
        fetched = True

    head = git_out(root, "rev-parse", "HEAD")

    resolved = git(root, "rev-parse", "--verify", f"{ref}^{{commit}}")
    if resolved.returncode != 0:
        raise KhongKiemDuoc(
            f"không giải được `{ref}` thành một commit trong {root} "
            f"— cây này có remote đó không?"
        )
    ref_sha = resolved.stdout.strip()

    ahead = behind = 0
    if head != ref_sha:
        counts = git_out(
            root, "rev-list", "--left-right", "--count", f"{head}...{ref_sha}"
        )
        parts = counts.split()
        if len(parts) != 2:
            raise KhongKiemDuoc(f"không đếm được khoảng cách tới {ref}: {counts!r}")
        ahead, behind = int(parts[0]), int(parts[1])

    status = doc_trang_thai(root, scope)

    verdict = Verdict(
        state=STATE_KHOP,
        tree=str(root),
        ref=ref,
        head=head,
        ref_sha=ref_sha,
        ahead=ahead,
        behind=behind,
        fetched=fetched,
        scope=scope,
        deleted=status["deleted"],
        modified=status["modified"],
        staged=status["staged"],
        conflicted=status["conflicted"],
        untracked=status["untracked"],
        untracked_ignored_by_flag=ignore_untracked and bool(status["untracked"]),
    )

    off = head != ref_sha or bool(verdict.dirty)
    if verdict.untracked and not ignore_untracked:
        off = True
    verdict.state = STATE_LECH if off else STATE_KHOP
    return verdict


def _in_lech(v: Verdict) -> None:
    """Say what is wrong, with the numbers, and what to type to fix it."""
    print(file=sys.stderr)
    print(
        f"!! LỆCH — cây này KHÔNG khớp {v.ref}. Đừng xuất bundle từ nó.",
        file=sys.stderr,
    )
    print(f"   cây : {v.tree}", file=sys.stderr)
    print(f"   HEAD: {v.head}", file=sys.stderr)
    print(f"   {v.ref}: {v.ref_sha}", file=sys.stderr)

    if v.head != v.ref_sha:
        print(file=sys.stderr)
        if v.behind and v.ahead:
            print(
                f"   ĐÃ RẼ NHÁNH: sau {v.behind} commit, và mang {v.ahead} commit "
                f"{v.ref} không có.",
                file=sys.stderr,
            )
        elif v.behind:
            print(
                f"   ĐỨNG SAU {v.behind} commit. Bundle dựng từ đây thiếu mọi thứ "
                f"{v.behind} commit đó thêm vào — kể cả màn hình.",
                file=sys.stderr,
            )
        elif v.ahead:
            print(
                f"   ĐỨNG TRƯỚC {v.ahead} commit. Bundle dựng từ đây trình diễn thứ "
                f"chưa có trên {v.ref}; lần dựng sau nó biến mất.",
                file=sys.stderr,
            )

    if v.deleted:
        print(file=sys.stderr)
        print(
            f"   {len(v.deleted)} file tracked đang ở trạng thái ĐÃ XOÁ — đây là "
            f"hình dạng của lỗi 03:20, và một fast-forward KHÔNG mang chúng về:",
            file=sys.stderr,
        )
        for path in v.deleted:
            print(f"      {path}", file=sys.stderr)
    for label, paths in (
        ("ĐÃ SỬA", v.modified),
        ("ĐANG CHỜ TRONG INDEX", v.staged),
        ("ĐANG XUNG ĐỘT", v.conflicted),
    ):
        if paths:
            print(file=sys.stderr)
            print(f"   {len(paths)} file tracked {label}:", file=sys.stderr)
            for path in paths:
                print(f"      {path}", file=sys.stderr)
    if v.untracked and not v.untracked_ignored_by_flag:
        print(file=sys.stderr)
        print(
            f"   {len(v.untracked)} file CHƯA THEO DÕI — trình đóng gói đọc đĩa, "
            f"không đọc index, nên những file này VÀO bundle dù {v.ref} không có:",
            file=sys.stderr,
        )
        for path in v.untracked[:20]:
            print(f"      {path}", file=sys.stderr)
        if len(v.untracked) > 20:
            print(f"      … và {len(v.untracked) - 20} file nữa", file=sys.stderr)

    print(file=sys.stderr)
    print("   Đưa cây về đúng mốc rồi xuất lại:", file=sys.stderr)
    print(f"       git -C {v.tree} fetch origin", file=sys.stderr)
    print(
        f"       git -C {v.tree} status          # xem có gì đáng giữ không",
        file=sys.stderr,
    )
    print(f"       git -C {v.tree} checkout --detach {v.ref}", file=sys.stderr)
    print(
        "   Còn file tracked đã xoá/đã sửa thì `checkout --detach` KHÔNG đủ — "
        "`git restore .` (hoặc `git reset --hard`, nó xoá việc chưa commit).",
        file=sys.stderr,
    )


def _in_khop(v: Verdict) -> None:
    scope = f" (phạm vi: {', '.join(v.scope)})" if v.scope else ""
    fetched = "" if v.fetched else " [--no-fetch: mốc có thể đã cũ]"
    print(f"KHỚP — cây dựng đúng bằng {v.ref}{scope}{fetched}")
    print(f"  cây  : {v.tree}")
    print(f"  SHA  : {v.head}")
    if v.untracked_ignored_by_flag:
        print(
            f"  (--bo-qua-chua-theo-doi: {len(v.untracked)} file chưa theo dõi "
            f"đã được BỎ QUA, chúng vẫn sẽ vào bundle.)"
        )


def selftest() -> int:
    """Prove the gate still bites, on real git repositories it builds itself.

    It calls `danh_gia` -- the function the gate runs -- rather than restating
    what the gate ought to do. A self-check that reimplements the logic grades a
    copy of the answer and passes when the original is broken.
    """
    env_args = [
        "-c",
        "user.email=selftest-khong-co-hom-thu",
        "-c",
        "user.name=selftest",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "init.defaultBranch=main",
    ]

    def run(cwd: Path, *args: str) -> None:
        done = subprocess.run(
            ["git", *env_args, "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
        if done.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)}: {done.stderr.strip()}")

    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="cong-cay-khop-") as tmp:
        base = Path(tmp)
        upstream = base / "upstream"
        upstream.mkdir()
        run(upstream, "init", "--quiet")
        for n in range(5):
            (upstream / f"man{n}.tsx").write_text(f"export const Man{n} = 1;\n")
            run(upstream, "add", "-A")
            run(upstream, "commit", "--quiet", "-m", f"man {n}")

        def fresh(name: str, back: int = 0) -> Path:
            work = base / name
            subprocess.run(
                ["git", *env_args, "clone", "--quiet", str(upstream), str(work)],
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT,
                check=True,
            )
            if back:
                run(work, "reset", "--hard", "--quiet", f"HEAD~{back}")
            return work

        def check(name: str, got: str, want: str) -> None:
            mark = "ok  " if got == want else "SAI "
            print(f"  {mark}{name}: {got}" + ("" if got == want else f" (mong {want})"))
            if got != want:
                failures.append(name)

        def state(tree: Path, **kw) -> str:
            try:
                return danh_gia(tree, "origin/main", fetch=False, **kw).state
            except KhongKiemDuoc:
                return STATE_KHONG_KIEM_DUOC

        print("selftest cổng 'cây có khớp main không':")

        check("cây sạch đúng mốc", state(fresh("sach")), STATE_KHOP)

        lui = fresh("lui4", back=4)
        v = danh_gia(lui, "origin/main", fetch=False)
        check("lùi 4 commit", v.state, STATE_LECH)
        check("  đếm đúng 4", str(v.behind), "4")

        # The 03:20 case: fast-forward lands exactly on main, deletion survives.
        # man0 exists at HEAD~4 too, so deleting it is a deletion the incoming
        # commits do not touch -- which is exactly why the fast-forward succeeds
        # and prints nothing while the file stays gone.
        case = fresh("xoa-sau-ff", back=4)
        (case / "man0.tsx").unlink()
        pull = subprocess.run(
            ["git", *env_args, "-C", str(case), "pull", "-q", "--ff-only"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
        check("  `git pull -q --ff-only` thoát 0", str(pull.returncode), "0")
        check("  và in ra 0 byte", str(len(pull.stdout) + len(pull.stderr)), "0")
        v = danh_gia(case, "origin/main", fetch=False)
        check("HEAD==main mà file tracked đã xoá (ca 03:20)", v.state, STATE_LECH)
        check("  HEAD thật sự bằng main", str(v.head == v.ref_sha), "True")
        check("  nêu tên file đã xoá", str(v.deleted), "['man0.tsx']")

        sua = fresh("sua")
        (sua / "man0.tsx").write_text("export const Man0 = 999;\n")
        check("file tracked đã sửa", state(sua), STATE_LECH)

        truoc = fresh("truoc")
        (truoc / "them.tsx").write_text("export const Them = 1;\n")
        run(truoc, "add", "-A")
        run(truoc, "commit", "--quiet", "-m", "nhánh riêng")
        v = danh_gia(truoc, "origin/main", fetch=False)
        check("đứng trước main 1 commit", v.state, STATE_LECH)
        check("  đếm đúng ahead=1", str(v.ahead), "1")

        chua = fresh("chua-theo-doi")
        (chua / "nhap.tsx").write_text("export const Nhap = 1;\n")
        check("file chưa theo dõi", state(chua), STATE_LECH)
        check(
            "  --bo-qua-chua-theo-doi tha nó",
            state(chua, ignore_untracked=True),
            STATE_KHOP,
        )

        pham_vi = fresh("pham-vi")
        (pham_vi / "ngoai").mkdir()
        (pham_vi / "man0.tsx").write_text("bẩn\n")
        check(
            "--pham-vi thu hẹp được nửa file",
            state(pham_vi, scope=["ngoai"]),
            STATE_KHOP,
        )
        check("  không thu hẹp thì vẫn LỆCH", state(pham_vi), STATE_LECH)

        khong = base / "khong-phai-git"
        khong.mkdir()
        check("thư mục không phải git", state(khong), STATE_KHONG_KIEM_DUOC)
        check("thư mục không tồn tại", state(base / "vang-mat"), STATE_KHONG_KIEM_DUOC)

        try:
            danh_gia(fresh("ref-la"), "origin/khong-co-nhanh-nay", fetch=False)
            got = STATE_KHOP
        except KhongKiemDuoc:
            got = STATE_KHONG_KIEM_DUOC
        check("ref không giải được", got, STATE_KHONG_KIEM_DUOC)

    print()
    if failures:
        print(
            f"selftest ĐỎ: {len(failures)} ca sai — {', '.join(failures)}",
            file=sys.stderr,
        )
        return EXIT_LECH
    print("selftest xanh: mọi ca ra đúng trạng thái mong đợi.")
    return EXIT_KHOP


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cây đang dùng để dựng có khớp origin/main không? "
        "KHỚP / LỆCH / KHÔNG KIỂM ĐƯỢC."
    )
    parser.add_argument(
        "--tree",
        default=str(REPO_ROOT),
        help="cây cần kiểm (mặc định: cây chứa script này)",
    )
    parser.add_argument(
        "--ref", default=DEFAULT_REF, help=f"mốc so sánh (mặc định {DEFAULT_REF})"
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="đừng fetch trước khi so — chỉ dùng khi offline, và sẽ được ghi ra",
    )
    parser.add_argument(
        "--pham-vi",
        action="append",
        default=[],
        metavar="ĐƯỜNG_DẪN",
        help="chỉ soi trạng thái file trong đường dẫn này (lặp lại được). "
        "Nửa HEAD vẫn soi cả cây — HEAD không có phạm vi.",
    )
    parser.add_argument(
        "--bo-qua-chua-theo-doi",
        action="store_true",
        help="đừng coi file chưa theo dõi là lệch (chúng vẫn vào bundle)",
    )
    parser.add_argument("--json", action="store_true", help="in kết quả dạng máy đọc")
    parser.add_argument(
        "--selftest", action="store_true", help="tự kiểm bằng repo git thật"
    )
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    if args.no_fetch:
        print(
            f"(--no-fetch: so với {args.ref} đang có sẵn trên máy, có thể đã cũ.)",
            file=sys.stderr,
        )
    if args.pham_vi:
        print(
            f"(--pham-vi: chỉ soi trạng thái file trong {', '.join(args.pham_vi)} — "
            f"file bẩn ngoài phạm vi này KHÔNG được kiểm.)",
            file=sys.stderr,
        )

    try:
        verdict = danh_gia(
            Path(args.tree),
            args.ref,
            fetch=not args.no_fetch,
            scope=args.pham_vi,
            ignore_untracked=args.bo_qua_chua_theo_doi,
        )
    except KhongKiemDuoc as exc:
        if args.json:
            print(
                json.dumps(
                    Verdict(
                        state=STATE_KHONG_KIEM_DUOC,
                        tree=str(args.tree),
                        ref=args.ref,
                        reason=str(exc),
                    ).to_json(),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        print(file=sys.stderr)
        print(f"!! KHÔNG KIỂM ĐƯỢC — {exc}", file=sys.stderr)
        print(
            "   Không kiểm được KHÔNG phải là khớp. Đừng xuất bundle cho tới khi "
            "câu hỏi này có câu trả lời.",
            file=sys.stderr,
        )
        return EXIT_KHONG_KIEM_DUOC

    if args.json:
        print(json.dumps(verdict.to_json(), ensure_ascii=False, indent=2))

    if verdict.state == STATE_KHOP:
        _in_khop(verdict)
    else:
        _in_lech(verdict)
    return EXIT_FOR_STATE[verdict.state]


if __name__ == "__main__":
    raise SystemExit(main())
