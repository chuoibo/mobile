#!/usr/bin/env python3
"""Mutation table for the two clock guards in the harness's `lane.py`.

## Why this file exists

On 2026-08-31 at 07:44:50 five lanes died in the same second. `state/events.jsonl`
records what each one was:

    LANE_STATE  devops/qa/qa3/frontend/backend   rc=143   outcome="stalled"

`outcome="stalled"` is the SILENCE guard, not the hard ceiling, and rc=143 is
the harness's own SIGTERM -- every lane killed its own brain. The `lane.py` live
at that moment (4a7503a) measured silence against the wall clock:

    last_change = started
    silent = now() - last_change        # now() is time.time()

so one forward step larger than `silence_timeout` (300-420s here) inflates
`silent` in every lane at the same instant and every lane fires at once. That
account matches the three things no other one did: a SIGTERM needs a sender (the
guard itself sent it), five lanes in one second needs a global event (a clock
step is one), and nothing warned beforehand (`silent` jumped, it did not climb).

`khoang()` -- monotonic -- fixed it at 12:08:19, four and a half hours after the
deaths. But the regression tests written alongside that fix cover only the hard
ceiling; that test class deliberately parks `silence_timeout` at 600s so the
ceiling is the only thing that can end a run. Measured before the repair:
reverting all three silence sites to the wall clock left the file GREEN, 3/3.

A guard nothing measures is a guard that comes back. This table is the standing
answer to "is either clock guard actually covered", runnable by anyone.

## How to read a row

Each row edits `lane.py`, runs the harness clock suite, restores the file, and
compares against the cases the row is expected to kill.

  KEEP row   must be GREEN. Without it a table of all-red rows proves nothing:
             a suite that cannot pass fails every mutant for free.
  RED row    must be RED, **and must kill the named cases**. Red alone is not a
             catch. `elapsed = now() - started` with `started` left on the
             monotonic clock subtracts a monotonic reading from a wall-clock
             epoch, so every run instant-times-out in 0.1s and the whole file
             goes red -- red for a reason that has nothing to do with a clock
             STEP. That mutant is written faithfully here (M3 moves `started`
             too) precisely so the table measures what it claims to.

The two ways a row can mismatch are not the same finding, and an earlier version
of this file treated them alike and was flaky for it:

  thieu  a case the row REQUIRED stayed green. The guard is not covered. This is
         the load-bearing signal and it is always a hole (exit 1).
  thua   an extra case died. If it is a still-clock CONTROL the mutant broke the
         fixture rather than exposing a guard -- that is the "red for the wrong
         reason" shape, and it stays a hole. Any other extra is reported as a
         warning and does not fail the table: measured on this machine, under
         load (eight live brains plus nested suites) the ceiling case
         `test_nhay_lui_khong_duoc_thao_tran_cung` starves and dies under M1,
         while alone under the same mutant it passes 3/3. A gate that reddens on
         a busy machine is a gate somebody deletes.

The cost of that choice, stated rather than hidden: a mutant that is broader
than its description, but does not touch a control, is a warning here and not a
failure. `thieu` and the control check are what carry the verdict.

Refusal is not failure: the harness lives outside this repository and has no
remote, so on a CI runner or a fresh clone there is nothing to mutate. That
case exits 2 and says so. It must never be reported as a pass.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HARNESS_DEFAULT = pathlib.Path.home() / "agent-harness"
SUITE = "tests.test_dong_ho_nhay_khong_giet_lane"
SUITE_FILE = pathlib.Path("tests") / "test_dong_ho_nhay_khong_giet_lane.py"

# Every case in the suite, so a row can name what it expects to survive too.
CEILING_CASES = {
    "test_tran_cung_van_ban_khi_dong_ho_dung_yen",
    "test_nhay_toi_khong_duoc_giet_brain_dang_khoe",
    "test_nhay_lui_khong_duoc_thao_tran_cung",
}
SILENCE_CASES = {
    "test_bo_canh_im_lang_van_ban_khi_dong_ho_dung_yen",
    "test_nhay_toi_khong_duoc_bop_co_brain_dang_nghi",
    "test_nhay_lui_khong_duoc_thao_bo_canh_im_lang",
}

# The still-clock positive controls, one per guard. A mutant that kills one of
# these without saying so did not expose a guard -- it broke the fixture.
CONTROLS = {
    "test_tran_cung_van_ban_khi_dong_ho_dung_yen",
    "test_bo_canh_im_lang_van_ban_khi_dong_ho_dung_yen",
}

# Source edits, written as exact one-occurrence replacements. A row whose anchor
# no longer matches is reported as a refusal, not silently skipped: an anchor
# that has drifted means the table is measuring a file it no longer understands.
SILENCE_TO_WALL = [
    ("        last_change = khoang()", "        last_change = now()"),
    (
        "                last_seen, last_change = produced, khoang()",
        "                last_seen, last_change = produced, now()",
    ),
    (
        "            silent = khoang() - last_change",
        "            silent = now() - last_change",
    ),
]
CEILING_TO_WALL = [
    ("        started = khoang()", "        started = now()"),
    (
        "            elapsed = khoang() - started",
        "            elapsed = now() - started",
    ),
]
SILENCE_OFF = [
    (
        "            if silent > self.brain.silence_timeout:",
        "            if False and silent > self.brain.silence_timeout:",
    ),
]
CEILING_OFF = [
    (
        "            if elapsed > self.brain.hard_timeout:",
        "            if False and elapsed > self.brain.hard_timeout:",
    ),
]

ROWS = [
    {
        "id": "K1",
        "what": "khong doi gi -- doi chung duong",
        "edits": [],
        "expect_green": True,
        "kills": set(),
    },
    {
        "id": "M1",
        "what": "bo canh IM LANG -> dong ho treo tuong (dung ban 4a7503a luc 07:44:50)",
        "edits": SILENCE_TO_WALL,
        "expect_green": False,
        # The still-clock control must SURVIVE: a wall clock that never moves
        # measures silence correctly. Only the two step cases may die.
        "kills": {
            "test_nhay_toi_khong_duoc_bop_co_brain_dang_nghi",
            "test_nhay_lui_khong_duoc_thao_bo_canh_im_lang",
        },
    },
    {
        "id": "M2",
        "what": "xoa han bo canh im lang",
        "edits": SILENCE_OFF,
        "expect_green": False,
        # The forward case asserts nothing was strangled, and a deleted guard
        # strangles nothing -- so it must survive. Only the two cases that
        # assert a stall IS caught may die.
        "kills": {
            "test_bo_canh_im_lang_van_ban_khi_dong_ho_dung_yen",
            "test_nhay_lui_khong_duoc_thao_bo_canh_im_lang",
        },
    },
    {
        "id": "M3",
        "what": "TRAN CUNG -> dong ho treo tuong (faithful: doi ca `started`)",
        "edits": CEILING_TO_WALL,
        "expect_green": False,
        "kills": {
            "test_nhay_toi_khong_duoc_giet_brain_dang_khoe",
            "test_nhay_lui_khong_duoc_thao_tran_cung",
        },
    },
    {
        "id": "M4",
        "what": "xoa han tran cung",
        "edits": CEILING_OFF,
        "expect_green": False,
        "kills": {
            "test_tran_cung_van_ban_khi_dong_ho_dung_yen",
            "test_nhay_lui_khong_duoc_thao_tran_cung",
        },
    },
]

FAIL_RE = re.compile(r"^(?:FAIL|ERROR): (test_\w+)", re.MULTILINE)


class Refuse(Exception):
    """The table cannot be run at all. Never reported as a pass."""


def apply_edits(src: str, edits) -> str:
    for old, new in edits:
        if src.count(old) != 1:
            raise Refuse(
                f"KHONG DO DUOC: neo khong con khop duy nhat trong lane.py "
                f"({src.count(old)} lan): {old.strip()!r}. Bang dot bien dang "
                f"do mot file no khong con hieu -- sua neo truoc khi tin so lieu."
            )
        src = src.replace(old, new)
    return src


def run_suite(harness: pathlib.Path, timeout: int) -> tuple[bool, set[str], str]:
    """Run the clock suite in the harness tree, return (green, dead_cases, tail)."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", SUITE, "-v"],
            cwd=str(harness),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return False, {"<TIMEOUT>"}, f"TIMEOUT sau {timeout}s"
    out = (proc.stdout or "") + (proc.stderr or "")
    tail = "\n".join(out.strip().splitlines()[-3:])
    return proc.returncode == 0, set(FAIL_RE.findall(out)), tail


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--harness",
        type=pathlib.Path,
        default=HARNESS_DEFAULT,
        help=f"cay harness (mac dinh {HARNESS_DEFAULT})",
    )
    ap.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="tran thoi gian cho MOI luot chay suite",
    )
    ap.add_argument(
        "--only", action="append", help="chi chay nhung hang nay (vd --only M1)"
    )
    args = ap.parse_args()

    # A misspelled case name in a row's `kills` set can never be matched, so the
    # row would report "DO NHAM LY DO" forever and the reader would go looking
    # for a defect in `lane.py` that is not there. Checked against the real
    # suite's case names before anything is mutated.
    known = CEILING_CASES | SILENCE_CASES
    for row in ROWS:
        unknown = row["kills"] - known
        if unknown:
            print(
                f"KHONG DO DUOC: hang {row['id']} cho doi ca khong ton tai: "
                f"{sorted(unknown)}"
            )
            return 2

    harness: pathlib.Path = args.harness
    lane = harness / "lane.py"
    suite_file = harness / SUITE_FILE

    # Absence is a refusal with a reason, never a green. The harness has no
    # remote; a fresh clone of this repository simply does not contain it.
    if not lane.is_file() or not suite_file.is_file():
        print(f"BO QUA (khong phai DAT): khong thay {lane} hoac {suite_file}.")
        print("  Cay harness nam ngoai repo nay va khong co remote, nen tren mot")
        print("  runner sach thi khong co gi de dot bien. Day la tu choi do,")
        print("  khong phai mot dau xanh.")
        return 2

    rows = ROWS
    if args.only:
        want = {r.upper() for r in args.only}
        rows = [r for r in ROWS if r["id"] in want]
        if not rows:
            print(f"KHONG DO DUOC: --only {sorted(want)} khong khop hang nao.")
            return 2

    original = lane.read_text()
    backup = pathlib.Path(tempfile.mkdtemp(prefix="dotbien-lane-")) / "lane.py.orig"
    backup.write_text(original)

    holes: list[str] = []
    warnings: list[str] = []
    print(f"Bang dot bien dong ho lane -- {lane}")
    print(f"  suite: {SUITE}   backup: {backup}\n")

    try:
        for row in rows:
            try:
                lane.write_text(apply_edits(original, row["edits"]))
            except Refuse as exc:
                lane.write_text(original)
                print(f"  {row['id']}  {exc}")
                return 2

            green, dead, tail = run_suite(harness, args.timeout)
            lane.write_text(original)

            verdict = "XANH" if green else "DO"
            want_green = row["expect_green"]
            line = f"  {row['id']:<3} {verdict:<4} {row['what']}"

            if want_green and not green:
                holes.append(f"{row['id']}: hang KEEP nhung DO -- {sorted(dead)}")
                line += f"   <-- LO HONG: phai XANH, chet: {sorted(dead)}"
            elif not want_green and green:
                holes.append(f"{row['id']}: dot bien SONG SOT -- khong ca nao bat")
                line += "   <-- LO HONG: dot bien song sot"
            elif not want_green and dead != row["kills"]:
                # Red is not a catch. This is the check that separates "the
                # guard is covered" from "the mutant broke something else".
                #
                # The two directions do NOT mean the same thing, and treating
                # them alike made this table flaky. Measured: under load (eight
                # live brains plus nested suites) the ceiling case
                # `test_nhay_lui_khong_duoc_thao_tran_cung` starves -- its 12s
                # brain exits before the parent's poll loop notices a 3s ceiling
                # -- so an unrelated case dies and a strict equality check calls
                # a covered guard a hole. Run alone under the same mutant it
                # passes 3/3. A gate that reddens on a busy machine is a gate
                # somebody deletes.
                thua = sorted(dead - row["kills"])
                thieu = sorted(row["kills"] - dead)
                # A case the row REQUIRED survived: the guard is not covered.
                # This is the load-bearing signal and it is always a hole.
                if thieu:
                    holes.append(f"{row['id']}: KHONG BAT DUOC -- thieu={thieu}")
                    line += f"   <-- LO HONG: thieu={thieu}"
                # A positive control died that this row did not claim: the
                # mutant broke the fixture rather than the guard. That is the
                # "red for the wrong reason" shape -- an unfaithful ceiling
                # mutant kills the still-clock control -- so it stays a hole.
                elif set(thua) & (CONTROLS - row["kills"]):
                    holes.append(
                        f"{row['id']}: DO NHAM LY DO -- chet ca doi chung duong: "
                        f"{sorted(set(thua) & CONTROLS)}"
                    )
                    line += f"   <-- DO NHAM LY DO: chet doi chung {sorted(set(thua) & CONTROLS)}"
                else:
                    # Everything required died; something extra did too, and it
                    # was not a control. Reported, not fatal.
                    warnings.append(
                        f"{row['id']}: chet them {thua} (tai nang? dot bien rong hon mo ta?)"
                    )
                    line += f"   bat du, chet them {thua}"
            else:
                line += (
                    f"   chet dung {len(dead)} ca" if dead else "   (dung nhu mong doi)"
                )
            print(line)
            if not green and tail:
                print(f"        {tail.splitlines()[-1]}")
    finally:
        # Restore unconditionally: an interrupted table must not leave the
        # running harness on a mutated clock.
        lane.write_text(original)
        if lane.read_text() != original:  # pragma: no cover - defensive
            print(f"CANH BAO: khoi phuc that bai, ban goc con o {backup}")
            return 2
        shutil.rmtree(backup.parent, ignore_errors=True)

    print()
    if holes:
        print(f"LO HONG: {len(holes)}")
        for h in holes:
            print(f"  - {h}")
        return 1
    if warnings:
        print(f"CANH BAO (khong phai lo hong): {len(warnings)}")
        for w in warnings:
            print(f"  - {w}")
    print(f"DAT: {len(rows)} hang, moi hang bat duoc dung ca no phai bat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
