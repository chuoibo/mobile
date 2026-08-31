"""`watch_for_silence` must measure silence on a clock that only moves forward.

`scripts/agent_supervisor.py` exists for one reason: an agent that stops
answering exits cleanly and produces nothing, so the only way to learn about an
hour of silence is to watch the gap AS IT GROWS. Every other failure mode in
that file's own docstring is a variant of "an exit code is not a progress
signal".

The gap was measured with `time.time()` -- the wall clock. A wall clock is not
an interval: it is a number somebody else is allowed to move. On this machine
(WSL2) it moves for two ordinary reasons, an NTP step correction and the
Windows host suspending and resuming, and neither of them says anything about
whether the agent is working.

Both directions are wrong, and they are wrong in opposite ways:

  forward step  -> a working agent is reported silent for an interval nobody
                   observed. The alert names a number that never happened.
  backward step -> `quiet` goes NEGATIVE and a genuinely dead agent produces
                   no alert at all.

The second is the one that matters. This whole repository is a list of
detectors that failed by going quiet -- the URL scanner with no Chrome
returning `[]` and exit 0, `ruff_pinned.sh` printing a path and exiting 0,
`demo_watch` whose crontab entry was deleted. A watchdog silenced by a clock
step wears exactly that costume: no output, and no output is also what a
healthy watchdog prints.

The three cases below are one positive control and two defects. The control is
load-bearing and must be read first: `test_dong_ho_lanh_manh_van_keu` proves
this fixture can produce an ALERT at all. Without it, the "no false alarm" case
would pass just as happily against a `watch_for_silence` that was deleted, and
the "must alert" case would be the only thing standing between us and a fixture
that measures nothing.
"""

from __future__ import annotations

import argparse
import importlib.util
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SUPERVISOR = REPO_ROOT / "scripts" / "agent_supervisor.py"

HEARTBEAT = 180
POLL = 30


def _load():
    spec = importlib.util.spec_from_file_location("agent_supervisor", SUPERVISOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DongHoGia:
    """A wall clock and a monotonic clock that can be moved independently.

    The point of the fake is that the two disagree. A fake where they move
    together cannot tell a correct implementation from the broken one, because
    the broken one only misbehaves when somebody moves the wall clock.

    The wall clock starts far in the future so that no real file on disk is
    ever newer than the run's `since` watermark; otherwise unrelated files
    under the scratch directory would register as this agent's progress.
    """

    def __init__(self) -> None:
        self._wall = 4_000_000_000.0
        self._mono = 1_000.0

    # -- the surface `agent_supervisor` actually consumes ------------------
    def time(self) -> float:
        return self._wall

    def monotonic(self) -> float:
        return self._mono

    def strftime(self, fmt: str, *rest: object) -> str:
        # Delegated to the real thing: the timestamp in a log line is cosmetic
        # and freezing it would only make failures harder to read.
        return time.strftime(fmt, *rest)  # type: ignore[arg-type]

    def sleep(self, seconds: float) -> None:
        self.troi(seconds)

    # -- what the scenarios drive -----------------------------------------
    def troi(self, seconds: float) -> None:
        """Ordinary passage of time: both clocks advance together."""
        self._wall += seconds
        self._mono += seconds

    def buoc_wall(self, seconds: float) -> None:
        """Somebody steps the wall clock. Monotonic does not care."""
        self._wall += seconds


class StopGia:
    """A `threading.Event` stand-in that runs a scripted timeline.

    Each entry is applied AFTER the corresponding wait, so a scenario reads in
    the order the world happens: thirty seconds pass, then the clock jumps.
    """

    def __init__(self, clock: DongHoGia, kich_ban: list[object]) -> None:
        self.clock = clock
        self.kich_ban = list(kich_ban)
        self.n = 0
        self._set = False

    def is_set(self) -> bool:
        return self._set

    def wait(self, seconds: float) -> bool:
        if self.n >= len(self.kich_ban):
            self._set = True  # timeline exhausted: let the watcher return
            return True
        self.clock.troi(seconds)
        step = self.kich_ban[self.n]
        self.n += 1
        if callable(step):
            step(self.clock)
        return False


def _chay(monkeypatch, tmp_path, capsys, kich_ban: list[object]) -> list[str]:
    """Run `watch_for_silence` over a scripted timeline, return emitted lines.

    The agent is deliberately given nothing to do: an empty output directory
    and an empty scratch directory mean `world()` never changes, so the agent
    is genuinely silent for the entire run. Every case below therefore differs
    only in what the CLOCK does.
    """
    sup = _load()
    clock = DongHoGia()
    monkeypatch.setattr(sup, "time", clock)

    out_dir = tmp_path / "ra"
    out_dir.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    # The real scratch path is shared by every project on this machine and is
    # written to by live agents. Left alone it would make these cases flaky for
    # reasons that have nothing to do with clocks.
    monkeypatch.setattr(sup, "AGY_SCRATCH", scratch)

    args = argparse.Namespace(heartbeat=HEARTBEAT)
    sup.watch_for_silence(
        "agy", args, out_dir, tmp_path / "repo", StopGia(clock, kich_ban)
    )
    return [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]


def _alerts(lines: list[str]) -> list[str]:
    return [ln for ln in lines if ln.startswith("ALERT")]


# -- positive control: read this before believing either case below ---------


def test_dong_ho_lanh_manh_van_keu(monkeypatch, tmp_path, capsys):
    """With a well-behaved clock, silence past the threshold must ALERT.

    This is the case that gives the other two meaning. It runs 240 simulated
    seconds against a 180 second threshold and touches no clock step at all.
    """
    lines = _chay(monkeypatch, tmp_path, capsys, [None] * 8)
    keu = _alerts(lines)
    assert keu, f"canh gác không kêu dù im lặng 240s > ngưỡng {HEARTBEAT}s: {lines}"
    assert any("im lang" in ln for ln in keu), keu


# -- defect 1: the dangerous direction -------------------------------------


def test_buoc_lui_khong_duoc_bit_mieng_canh_gac(monkeypatch, tmp_path, capsys):
    """A backward wall-clock step must not silence a real alert.

    Timeline: 30s pass, the wall clock steps back 600s (a host resume or an NTP
    correction), then 330 more seconds pass with the agent producing nothing.
    Total real silence is 360s, double the threshold.

    Measured on the wall clock the elapsed time reads NEGATIVE for the whole
    run, so `quiet >= heartbeat` is never true and the watchdog says nothing --
    while the agent it was watching is dead.
    """
    kich_ban: list[object] = [lambda c: c.buoc_wall(-600)] + [None] * 11
    lines = _chay(monkeypatch, tmp_path, capsys, kich_ban)

    assert _alerts(lines), (
        "đồng hồ lùi 600s đã bịt miệng cảnh gác: agent im lặng 360s "
        f"(ngưỡng {HEARTBEAT}s) mà không có ALERT nào. Đây là kiểu hỏng tệ "
        f"nhất — im lặng của kẻ canh gác trông y hệt lúc mọi thứ bình thường. "
        f"Dòng đã in: {lines}"
    )


# -- defect 2: the loud direction ------------------------------------------


def test_buoc_toi_khong_duoc_bao_dong_gia(monkeypatch, tmp_path, capsys):
    """A forward wall-clock step must not invent silence nobody observed.

    Timeline: 30s pass, the wall clock jumps forward an hour, 30 more seconds
    pass. The agent has been silent for 60 simulated seconds -- a third of the
    threshold, entirely normal.

    Measured on the wall clock that reads as 3660s of silence and pages a
    person about an interval that never happened.
    """
    kich_ban: list[object] = [lambda c: c.buoc_wall(3600), None]
    lines = _chay(monkeypatch, tmp_path, capsys, kich_ban)

    keu = _alerts(lines)
    assert not keu, (
        f"đồng hồ nhảy tới 3600s đẻ ra báo động giả: agent mới im {2 * POLL}s, "
        f"dưới ngưỡng {HEARTBEAT}s, mà cảnh gác đã kêu: {keu}"
    )


def test_so_giay_trong_alert_la_so_giay_that(monkeypatch, tmp_path, capsys):
    """The number in the alert must be the interval that actually elapsed.

    An alert that fires at the right moment but names a wrong number still
    costs the reader the investigation: "silent 3660s" and "silent 210s" send a
    person to two different places.
    """
    kich_ban: list[object] = [lambda c: c.buoc_wall(3600)] + [None] * 7
    lines = _chay(monkeypatch, tmp_path, capsys, kich_ban)
    keu = _alerts(lines)
    assert keu, f"không có ALERT để đọc số: {lines}"

    import re

    so = [int(m) for ln in keu for m in re.findall(r"im lang (\d+)s", ln)]
    assert so, f"ALERT không nói được nó đo bao nhiêu giây: {keu}"
    assert max(so) <= 8 * POLL, (
        f"ALERT khai {max(so)}s im lặng nhưng cả lượt chạy chỉ dài {8 * POLL}s "
        f"— con số này đến từ bước nhảy đồng hồ, không phải từ agent: {keu}"
    )


# -- the branch the three cases above never enter --------------------------
#
# Everything so far keeps `world()` frozen, so the loop only ever walks the
# silence path. Two of the three clock reads live in the OTHER branch -- the
# one taken when the agent speaks again -- and a fix whose test never enters a
# branch has not guarded it. Left out, this file would report a fully fixed
# function while half the fix sat behind an `if` nothing evaluates.


def _noi_lai(out_dir: Path):
    """Make `world()` change: a file newer than the run's `since` watermark.

    The mtime is set explicitly rather than left to the filesystem. `since`
    comes from the fake wall clock, which sits in the year 2096 so that real
    files never register; a real mtime would be far below it and this "new"
    file would be invisible.
    """

    def buoc(_clock: DongHoGia) -> None:
        path = out_dir / "bao-cao.md"
        path.write_text("agent nói lại", encoding="utf-8")
        import os

        os.utime(path, (4_000_000_100, 4_000_000_100))

    return buoc


def test_noi_lai_sau_im_lang_bao_dung_so_giay(monkeypatch, tmp_path, capsys):
    """When the agent speaks again, the recovery line must name a real gap.

    Timeline: 210s of silence (one ALERT fires), then the agent writes a file
    at the same moment the wall clock jumps forward an hour.

    On the wall clock the recovery line reported thousands of seconds of
    silence for a run that was 240 seconds long -- and that number is what a
    person reads at 3am when deciding whether the night was lost.
    """
    kich_ban: list[object] = [None] * 7 + [_noi_lai(tmp_path / "ra")]
    # The clock step rides along with the same tick the file appears on.
    kich_ban.append(lambda c: c.buoc_wall(3600))
    lines = _chay(monkeypatch, tmp_path, capsys, kich_ban)

    noi_lai = [ln for ln in lines if "noi lai sau" in ln]
    assert noi_lai, f"agent nói lại mà cảnh gác không ghi nhận: {lines}"

    import re

    so = [int(m) for ln in noi_lai for m in re.findall(r"noi lai sau (\d+)s", ln)]
    assert so, f"dòng nói-lại không kèm số giây: {noi_lai}"
    assert max(so) <= 10 * POLL, (
        f"dòng nói-lại khai {max(so)}s im lặng nhưng cả lượt chỉ dài "
        f"{10 * POLL}s — số này đến từ bước nhảy đồng hồ: {noi_lai}"
    )


# -- the SECOND gap in this same file -------------------------------------
#
# `watch_for_silence` above was fixed and `run_once` sixty lines below it was
# not, which is the ordinary way a fix stops halfway: the reported defect names
# one function, the defect class covers two.
#
# `run_once` measures how long the whole session ran, and that number is not
# cosmetic -- it feeds the "hung session" test:
#
#     if code == 0 and elapsed > 300 and len(output.strip()) < 200:
#         emit("ALERT", "... nghi treo phien")
#
# which exists for failure #3 in the module docstring: agy hit its own
# print-timeout after a 42-cell QA run and wrote nothing down. Exit 0, no
# output, hours gone. `elapsed` is the ONLY thing separating that from a fast
# clean run, and measured on the wall clock it is not an interval.


class _KetQua:
    """`subprocess.CompletedProcess` is a dataclass; only three fields are read."""

    def __init__(self, returncode: int, stdout: str, stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _phien_treo(clock: DongHoGia, that: float, buoc_wall: float = 0.0):
    """A session that runs `that` REAL seconds, exits 0, and says nothing.

    This is failure #3 from the module docstring, reproduced exactly: the
    process ends cleanly and produces no output, so the duration is the only
    evidence that anything went wrong. `buoc_wall` is somebody stepping the
    wall clock while that session is in flight.
    """

    def chay(*_args: object, **_kwargs: object) -> _KetQua:
        clock.troi(that)
        clock.buoc_wall(buoc_wall)
        return _KetQua(0, "")

    return chay


def _chay_run_once(
    monkeypatch, tmp_path, capsys, *, that: float, buoc_wall: float = 0.0
) -> list[str]:
    sup = _load()
    clock = DongHoGia()
    monkeypatch.setattr(sup, "time", clock)
    monkeypatch.setattr(sup.subprocess, "run", _phien_treo(clock, that, buoc_wall))

    prompt = tmp_path / "prompt.md"
    prompt.write_text("lam viec di", encoding="utf-8")
    args = argparse.Namespace(
        timeout=7200,
        cwd=str(tmp_path),
        out_dir=str(tmp_path),
        print_timeout="600",
    )
    sup.run_once("agy", str(prompt), args)
    return [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]


def _treo(lines: list[str]) -> list[str]:
    return [ln for ln in _alerts(lines) if "treo phien" in ln]


# -- positive control: this fixture can produce the alert at all ------------


def test_run_once_phien_treo_that_van_keu(monkeypatch, tmp_path, capsys):
    """A 600s silent clean exit must raise the hung-session ALERT.

    Load-bearing, exactly like `test_dong_ho_lanh_manh_van_keu` above: without
    it the backward-step case below could pass against a `run_once` whose alert
    was simply deleted.
    """
    lines = _chay_run_once(monkeypatch, tmp_path, capsys, that=600)
    assert _treo(lines), (
        f"phiên chạy 600s, exit 0, không in gì — đúng sự cố #3 trong docstring "
        f"của module — mà không có ALERT nào: {lines}"
    )


# -- defect 1: the quiet direction, again ----------------------------------


def test_run_once_buoc_lui_khong_duoc_bit_mieng(monkeypatch, tmp_path, capsys):
    """A backward wall-clock step must not hide a hung session.

    600 real seconds pass while the wall clock steps back 900 (a host resume or
    an NTP correction). On the wall clock `elapsed` reads -300, `elapsed > 300`
    is false, and the one alert that exists for this failure never fires.

    The session is just as dead as in the control above. Only the clock moved.
    """
    lines = _chay_run_once(monkeypatch, tmp_path, capsys, that=600, buoc_wall=-900)

    assert _treo(lines), (
        "đồng hồ lùi 900s đã bịt miệng ALERT treo phiên: phiên chạy thật 600s, "
        "exit 0, không in gì — mà cảnh gác im. Đây là kiểu hỏng tệ nhất, vì im "
        f"lặng của kẻ canh gác trông y hệt một lượt chạy sạch. Đã in: {lines}"
    )


def test_run_once_khong_bao_gio_khai_so_giay_am(monkeypatch, tmp_path, capsys):
    """The duration in the log must be a duration.

    `ket thuc sau -300s` is not a slightly-wrong number, it is a number that
    cannot happen -- and it is the line a person greps when asking how long
    last night's run took.
    """
    lines = _chay_run_once(monkeypatch, tmp_path, capsys, that=600, buoc_wall=-900)

    import re

    so = [int(m) for ln in lines for m in re.findall(r"ket thuc sau (-?\d+)s", ln)]
    assert so, f"không có dòng 'ket thuc sau' để đọc: {lines}"
    assert min(so) >= 0, (
        f"báo cáo thời lượng ÂM ({min(so)}s) — một khoảng thời gian không thể "
        f"âm; con số này đến từ bước nhảy đồng hồ chứ không từ phiên chạy: {lines}"
    )


# -- defect 2: the loud direction ------------------------------------------


def test_run_once_buoc_toi_khong_duoc_bao_dong_gia(monkeypatch, tmp_path, capsys):
    """A forward wall-clock step must not invent a hung session.

    The session runs 10 real seconds and exits clean -- a fast, healthy run.
    An NTP step of one hour lands mid-flight, the wall clock reads 3600s, and
    the supervisor pages somebody about a hang that did not happen.
    """
    lines = _chay_run_once(monkeypatch, tmp_path, capsys, that=10, buoc_wall=3600)

    assert not _treo(lines), (
        "đồng hồ nhảy tới 3600s đẻ ra báo động treo phiên giả: phiên chỉ chạy "
        f"10s thật và thoát sạch: {_treo(lines)}"
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
