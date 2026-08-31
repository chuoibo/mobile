"""No script may measure a same-process interval on the wall clock.

This gate exists because the same defect was found twice in the same file, a
day apart. `watch_for_silence` was fixed in #470; `run_once` sixty lines below
it kept measuring its gap with `time.time()` and kept feeding that number to
the one alert that reports a hung session. The second one was found by hand,
by someone re-reading the file. Hands do not scale to the next script.

Then it was found a THIRD time, and the third one is why this file now resolves
aliases. `lane.py` in the harness enforces its hard timeout with

    elapsed = now() - started            # module-level: def now(): time.time()
    if elapsed > self.brain.hard_timeout: self.kill(proc)

so the source never types `time.time()` anywhere near the subtraction, and the
first version of this detector read the whole file as clean -- 0 findings, while
the line it missed was deciding whether to SIGTERM a running brain. Measured
after teaching it the one-hop alias: 9 findings on the same file, 0 after the
fix. A gate that only recognises one spelling of a thing is a gate that teaches
people the other spelling.

The rule, stated so it can be argued with:

    Reading `time.time()` is fine. SUBTRACTING two readings of it inside one
    process is not, when the earlier reading was taken by that same process.
    A wall clock is not an interval -- it is a number the rest of the system is
    allowed to move -- and `time.monotonic()` is always available and always
    correct for that job.

    "Reading `time.time()`" includes reading it through a module-level name
    bound to it. What matters is what the name RETURNS, never what it is
    called: `lane.py` now ships `now()` and `khoang()` side by side, and a
    detector keyed on names rather than bodies would flag the correct one.

Both directions of a clock step are wrong, and they are wrong in opposite ways.
A forward step invents a gap nobody observed and pages a person about it. A
backward step makes the gap NEGATIVE, so `gap > threshold` is never true and a
genuinely dead process produces no alert at all. The second is the one this
repository keeps rediscovering: a detector that fails by going quiet wears the
same costume as a detector with nothing to report.

WHAT THIS GATE DOES NOT COVER -- read this before trusting a green run:

  * It reads source shape, not behaviour. It proves nobody TYPED the broken
    pattern; the behavioural proof that the supervisor still alerts through a
    clock step is `test_agent_supervisor_dong_ho.py`, and neither file replaces
    the other.
  * It is scoped to `scripts/`. `tests/` legitimately fabricates wall-clock
    timestamps for fixtures, and flagging those would train people to add
    ignores until the gate means nothing.
  * It is scoped to THIS repository, and the third occurrence was not in it.
    `lane.py` lives in `~/agent-harness/`, which has no remote and whose
    working tree is production; nothing here can scan it. The alias hop was
    added so the RULE covers that shape, and the fix was verified by running
    this module's detector against that file by hand -- but no gate in this
    repo runs on every change to the harness, and that gap is real.
  * Two shapes are known-uncovered and pinned as executable cases in
    `MU_CO_CHU_DICH`: a mark passed BETWEEN two module-level functions (no
    scope sees both ends), and an alias of an alias. They are tests rather
    than prose so that "documented" cannot quietly become "believed closed".
  * It cannot flag a CROSS-PROCESS age -- `time.time() - ts` where `ts` was
    persisted by another process, as in `demo_watch.py`. Monotonic is genuinely
    impossible there, because two processes share no monotonic origin. Those
    sites are a different defect class with a different fix (reject a negative
    age instead of reading it as fresh) and this gate is deliberately blind to
    them. Being blind on purpose is only safe while it is written down.
  * It does not read shell. `scripts/gate.sh` times its stages with bash
    `$SECONDS`, which is also wall-clock derived; it feeds a printed duration
    and no guard, so it is a wrong number rather than a silenced alarm.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

_BOC = {"int", "float", "round", "abs"}


def _go_boc(node: ast.AST) -> ast.AST:
    """Strip `int(...)`/`float(...)` so the wrapper cannot hide the call."""
    while (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _BOC
        and node.args
    ):
        node = node.args[0]
    return node


def _la_dong_ho_goc(node: ast.AST) -> bool:
    """True for a literal wall-clock read: `time.time()` or a bare `time()`."""
    node = _go_boc(node)
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "time":
        return isinstance(func.value, ast.Name) and func.value.id == "time"
    return isinstance(func, ast.Name) and func.id == "time"


def _bi_danh_dong_ho(cay: ast.Module) -> set[str]:
    """Module-level names that are just another spelling of `time.time`.

    This exists because the defect's third occurrence hid behind exactly that.
    `lane.py` measures its hard timeout with `now() - started`, where the whole
    module shares

        def now() -> float:
            return time.time()

    The source never types `time.time()` near the subtraction, so a detector
    that only recognises the literal call reads the file as clean. Measured on
    the real file before this hop was added: 0 findings, while the subtraction
    it missed was driving `kill()` on a live supervisor.

    Deliberately ONE hop, and deliberately module level. An alias of an alias,
    or one built at runtime, is not resolved -- chasing those needs real name
    resolution, and a detector that is only mostly right about which names are
    clocks would start reporting lines nobody can act on. One hop is the shape
    that actually occurred; the limit is written down rather than assumed.
    """
    ten: set[str] = set()
    for node in ast.iter_child_nodes(cay):
        # def now(): return time.time()  -- docstring before the return is fine.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            than = [
                c
                for c in node.body
                if not (isinstance(c, ast.Expr) and isinstance(c.value, ast.Constant))
            ]
            if (
                len(than) == 1
                and isinstance(than[0], ast.Return)
                and than[0].value is not None
                and _la_dong_ho_goc(than[0].value)
            ):
                ten.add(node.name)
        # now = time.time  -- the function object rebound, not called.
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Attribute):
            if (
                node.value.attr == "time"
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "time"
            ):
                for dich in node.targets:
                    if isinstance(dich, ast.Name):
                        ten.add(dich.id)
    return ten


def _la_dong_ho_treo_tuong(
    node: ast.AST, bi_danh: frozenset[str] = frozenset()
) -> bool:
    """True for a wall-clock read, whether spelled literally or through an alias."""
    if _la_dong_ho_goc(node):
        return True
    node = _go_boc(node)
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in bi_danh
    )


def _nong(scope: ast.AST):
    """Walk a scope WITHOUT descending into nested function or class bodies."""
    ra: list[ast.AST] = []
    for con in ast.iter_child_nodes(scope):
        if isinstance(con, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        ra.append(con)
        ra += _nong(con)
    return ra


def _ten(node: ast.AST) -> str | None:
    """Dotted name for `x` and `self.x`, so a mark stored on an object counts."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        goc = _ten(node.value)
        return f"{goc}.{node.attr}" if goc else None
    return None


def do_khoang_bang_dong_ho_treo_tuong(source: str, nhan: str = "<nguon>") -> list[str]:
    """Return one line per same-process interval measured on the wall clock.

    The detector is deliberately narrow, because a noisy gate gets suppressed.
    It only reports a subtraction where ONE side reads the wall clock and the
    OTHER side is a name this same function assigned from the wall clock. That
    combination has no honest reading: both endpoints were produced here, so
    monotonic was available for both.

    Consequences of that narrowness, on purpose:
      `time.time() - ts`         where ts came from JSON  -> NOT flagged
      `time.time() - 40 * 3600`  fabricating a past stamp -> NOT flagged
      `since = time.time()`      compared to file mtimes  -> NOT flagged
    """
    cay = ast.parse(source)
    # Resolved once for the whole module: a local alias for `time.time` makes
    # every call to it a wall-clock read, wherever in the file it is used.
    bi_danh = frozenset(_bi_danh_dong_ho(cay))
    # lineno -> (độ ưu tiên, thông báo). One finding per line, reported from the
    # innermost scope that can see both endpoints: the module scope can also see
    # every function's locals, and reporting from there named the same line twice.
    thay: dict[int, tuple[int, str]] = {}

    scopes: list[ast.AST] = [cay]
    scopes += [
        n
        for n in ast.walk(cay)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]

    for scope in scopes:
        # A function walks its whole body, nested closures included -- a mark
        # taken in the outer body and consumed in an inner one is still one
        # process measuring one interval. The module walks only its own top
        # level, or it would re-find every local in the file.
        nodes = list(_nong(scope) if isinstance(scope, ast.Module) else ast.walk(scope))

        moc: set[str] = set()
        for node in nodes:
            if isinstance(node, ast.Assign) and _la_dong_ho_treo_tuong(
                node.value, bi_danh
            ):
                for dich in node.targets:
                    if ten := _ten(dich):
                        moc.add(ten)
            elif (
                isinstance(node, ast.AnnAssign)
                and node.value
                and _la_dong_ho_treo_tuong(node.value, bi_danh)
            ):
                if ten := _ten(node.target):
                    moc.add(ten)
        if not moc:
            continue

        ten_ham = getattr(scope, "name", "<module>")
        uu_tien = getattr(scope, "lineno", 0)
        for node in nodes:
            if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub)):
                continue
            trai, phai = _go_boc(node.left), _go_boc(node.right)
            for a, b in ((trai, phai), (phai, trai)):
                if _la_dong_ho_treo_tuong(a, bi_danh) and (_ten(b) or "") in moc:
                    cu = thay.get(node.lineno)
                    if cu is None or uu_tien > cu[0]:
                        thay[node.lineno] = (
                            uu_tien,
                            f"{nhan}:{node.lineno}: trong {ten_ham}() — "
                            f"đo khoảng bằng time.time() trừ '{_ten(b)}', mà "
                            f"'{_ten(b)}' cũng lấy từ time.time() trong chính "
                            f"phạm vi này. Dùng time.monotonic() cho cả hai đầu.",
                        )
                    break
    return [thay[k][1] for k in sorted(thay)]


# -- the detector's own canary: it must be able to go red -------------------
#
# A gate whose only evidence is "it found nothing" is indistinguishable from a
# gate that cannot find anything. These cases feed the SAME function the real
# scan calls -- not a re-implementation of it, which would only prove the copy
# agrees with itself.

PHAI_BAT = {
    "dạng đã có thật trong run_once": """
import time
def run():
    started = time.time()
    work()
    elapsed = int(time.time() - started)
    return elapsed
""",
    "trừ ngược lại vẫn là đo khoảng": """
import time
def run():
    started = time.time()
    return started - time.time()
""",
    "mốc cất trên self": """
import time
class A:
    def bat_dau(self):
        self.moc = time.time()
    def xong(self):
        return time.time() - self.moc
""",
    "bọc trong int() không giấu được": """
import time
def run():
    started = int(time.time())
    return int(time.time()) - started
""",
    "nằm trong ternary": """
import time
def run():
    started = time.time()
    return (time.time() - started) if xong else 0.0
""",
    "nằm trong f-string": """
import time
def run():
    started = time.time()
    print(f"mat {time.time() - started}s")
""",
    "import trực tiếp": """
from time import time
def run():
    started = time()
    return time() - started
""",
    # The shape that actually got through. Kept verbatim from `lane.py`, where
    # the subtraction it hides was deciding whether to SIGTERM a live brain.
    # The shape that actually got through, kept faithful to `lane.py`: the mark
    # is taken in one method and spent in another, and the CLASS is what lets
    # the detector see both ends. Flattening this to two module-level functions
    # would not be caught -- see `MU_CO_CHU_DICH` below, which pins that hole
    # instead of pretending it is closed.
    "bí danh cục bộ — đúng dạng đã lọt ở lane.py": """
import time
def now() -> float:
    return time.time()
class Lane:
    def run_task(self, task):
        started = now()
        return self.watch(started)
    def watch(self, started):
        elapsed = now() - started
        if elapsed > self.brain.hard_timeout:
            self.kill()
""",
    "bí danh có docstring vẫn là bí danh": """
import time
def now():
    \"\"\"Gio hien tai.\"\"\"
    return time.time()
def run():
    moc = now()
    return now() - moc
""",
    "bí danh gán thẳng, không gọi qua def": """
import time
now = time.time
def run():
    started = now()
    return now() - started
""",
}

PHAI_THA = {
    "tuổi liên tiến trình, mốc từ JSON": """
import time
def doc(data):
    ts = data["ts"]
    return time.time() - ts
""",
    "chế mốc quá khứ để dựng fixture": """
import time
def gia():
    return time.time() - 40 * 3600
""",
    "watermark so với mtime, không hề trừ": """
import time
def watch(out_dir):
    since = time.time()
    return dir_progress(out_dir, since)
""",
    "đã dùng monotonic đúng cách": """
import time
def run():
    started = time.monotonic()
    return time.monotonic() - started
""",
    "hai hàm khác nhau, không phải cùng một khoảng": """
import time
def a():
    started = time.time()
    return started
def b():
    return time.time() - moc_o_dau_do
""",
    # The alias hop must resolve what the name RETURNS, not what it is called.
    # `lane.py` now ships `now()` and `khoang()` side by side; a detector that
    # keyed on the name would flag the correct one and teach people to ignore it.
    "hàm tên giống nhưng trả monotonic — đây là bản ĐÚNG": """
import time
def now():
    return time.monotonic()
def run():
    started = now()
    return now() - started
""",
    "bí danh dùng cho tuổi liên tiến trình vẫn phải tha": """
import time
def now():
    return time.time()
def doc(data):
    return now() - data["ts"]
""",
}


# -- holes this detector KNOWS it has -------------------------------------
#
# Pinned as executable cases rather than as a sentence in the docstring, because
# a documented limitation drifts into a believed-closed one the moment somebody
# skims. If one of these ever starts being caught, this test goes red and asks
# to be promoted into PHAI_BAT -- a gate getting stronger should be a decision,
# not a surprise.
MU_CO_CHU_DICH = {
    # No enclosing scope sees both ends, so the mark and its use never meet.
    # Real interprocedural resolution is the only fix and it costs more than it
    # returns here; `lane.py` was caught because its two halves share a class.
    "mốc đi qua tham số giữa HAI HÀM MODULE-LEVEL": """
import time
def now():
    return time.time()
def watch(started):
    return now() - started
def run():
    watch(now())
""",
    # Two hops. `_bi_danh_dong_ho` resolves exactly one on purpose.
    "bí danh của bí danh": """
import time
def now():
    return time.time()
def gio():
    return now()
def run():
    moc = gio()
    return gio() - moc
""",
}


@pytest.mark.parametrize("ten", sorted(MU_CO_CHU_DICH))
def test_lo_hong_da_biet_van_dung_nguyen_do(ten):
    """These are NOT covered. The test exists so nobody can believe they are."""
    loi = do_khoang_bang_dong_ho_treo_tuong(MU_CO_CHU_DICH[ten])
    assert not loi, (
        f"máy dò đã BẮT ĐƯỢC {ten!r}, một lỗ hổng trước đây được ghi là mù. "
        f"Đây là tin tốt: chuyển ca này sang PHAI_BAT và sửa phần tài liệu "
        f"nói nó không phủ.\n{loi}"
    )


@pytest.mark.parametrize("ten", sorted(PHAI_BAT))
def test_may_do_bat_duoc_dang_hong(ten):
    """Every known shape of the defect must be caught, not just the one seen."""
    loi = do_khoang_bang_dong_ho_treo_tuong(PHAI_BAT[ten])
    assert loi, (
        f"máy dò MÙ với dạng {ten!r} — một cổng bỏ sót hình dạng này sẽ báo "
        f"cây sạch trong khi lỗi vẫn nằm đó:\n{PHAI_BAT[ten]}"
    )


@pytest.mark.parametrize("ten", sorted(PHAI_THA))
def test_may_do_tha_dung_cai_phai_tha(ten):
    """False positives are how a gate gets suppressed. These must stay green."""
    loi = do_khoang_bang_dong_ho_treo_tuong(PHAI_THA[ten])
    assert not loi, (
        f"máy dò BÁO NHẦM ở {ten!r}; đây là cách dùng hợp lệ và một cổng kêu "
        f"oan sẽ bị người ta tắt đi:\n{PHAI_THA[ten]}\n{loi}"
    )


# -- the scan itself --------------------------------------------------------


def _file_scripts() -> list[Path]:
    """Tracked `.py` under `scripts/`, asked of git rather than the filesystem.

    `rglob` would also sweep up scratch files a lane left lying around, which
    turns somebody else's untracked draft into this gate's red.
    """
    ra = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "scripts/*.py"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [REPO_ROOT / d for d in ra.stdout.split() if d.strip()]


def test_co_file_de_quet():
    """Guard the denominator: an empty file list would pass every case below.

    A source scan that finds zero files reports exactly what a clean tree
    reports.
    """
    files = _file_scripts()
    assert len(files) >= 5, (
        f"chỉ tìm thấy {len(files)} file để quét — cổng này đang tự tháo chính "
        "nó; danh sách rỗng thì mọi ca dưới đều xanh mà không đo gì."
    )


def test_scripts_khong_do_khoang_bang_dong_ho_treo_tuong():
    """The real scan."""
    loi: list[str] = []
    for path in _file_scripts():
        nguon = path.read_text(encoding="utf-8")
        loi += do_khoang_bang_dong_ho_treo_tuong(
            nguon, str(path.relative_to(REPO_ROOT))
        )
    assert not loi, "đo khoảng bằng đồng hồ treo tường:\n" + "\n".join(loi)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
