#!/usr/bin/env python3
"""Which tests in the blocking suite read state OUTSIDE this repository.

A test whose verdict is a function of a directory outside the working tree
makes the whole suite non-reproducible: the same SHA answers differently on two
machines, or on one machine thirteen minutes apart. QA blocked #487 for exactly
that -- `1 failed` then `0 failed`, no commit in between -- and the fix moved
one file out of `tests/`.

That fix was measured in the wrong direction and so it stopped halfway. The
sweep that cleared the rest of the suite perturbed the outside world toward
ABSENT, and a test that cannot find the tree it wanted skips politely; the
failure only appears when the tree is PRESENT and different. Measured
2026-08-31 on `tests/test_harness_selfcheck.py`, which that sweep had called
clean, with the repository byte-identical:

    ~/agent-harness as it is today            43 passed
    the same tree + one new test file         1 failed, 36 passed, 6 skipped

So this asks a question that does not depend on guessing what a plausible
foreign tree looks like: at run time, which test items touched a path outside
the repository at all? A test that touched nothing outside cannot have a
verdict that depends on outside state. A test that did might, and this repo has
now paid twice for assuming otherwise.

## Why runtime and not a grep

The obvious version greps `tests/` for `Path.home()` and `AGENT_HARNESS`. That
version is blind the same way the AST clock gate was blind to
`def now(): return time.time()`: one local alias and the pattern is gone while
the behaviour stays. This installs `sys.addaudithook` in the pytest process and
records `open` / `os.scandir` / `os.listdir` / `os.mkdir` and
`subprocess.Popen` argv, attributing each to the test item that was running.
An alias cannot hide a syscall.

## What it does NOT prove

Touching an outside path is not the same as having a verdict that depends on
it, so a finding here is a question, not a conviction -- a test may read
`~/.gitconfig` and assert nothing about it. The reverse direction is the sound
one: an item with no findings could not have been swayed.

It cannot see an existence check. CPython raises no audit event for `stat`,
so `HARNESS_THAT.is_dir()` -- the guard the offending file used in its `skipif`
-- passes under this hook unseen. That bounds the claim in a specific way: a
test that SKIPS on the state of an outside tree can hide from this, while a
test that ASSERTS on the contents of one cannot, because reading contents means
`open`, `os.scandir` or a subprocess. The failing direction is the covered one.

It cannot see a dependency carried by something other than the filesystem --
the wall clock, `$TZ`, the network, an environment variable read with
`os.environ`. It sees `subprocess.Popen` argv but not what that child process
then opens, so a test that shells out to a script which reads the outside world
is reported by the argv only if the outside path is spelled in the argv.

Entries already on `sys.path` are allowed, because the import machinery walks
them on every import and attributing that to whichever test ran first is noise;
a test that deliberately reads a file from a `sys.path` directory is therefore
invisible here.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

# --- the probe half: imported by pytest via `-p check_suite_stays_in_repo` ---

_ENV_REPO = "SUITE_PROBE_REPO"
_ENV_OUT = "SUITE_PROBE_OUT"

# Measured, not assumed: CPython raises NO audit event for `stat`, so
# `Path(...).is_dir()` and `os.path.exists()` are invisible here. `os.stat` was
# in this tuple until a hermetic case proved the name does nothing. It is left
# out rather than left in, because a dead event name in this list is a claim of
# coverage that does not exist.
_EVENTS_PATH = ("open", "os.scandir", "os.listdir", "os.mkdir")


def _allowed_roots(repo: Path) -> list[str]:
    """Directories a test may touch without that saying anything about it."""
    paths = sysconfig.get_paths()
    raw = [
        paths.get("stdlib"),
        paths.get("purelib"),
        paths.get("platlib"),
        paths.get("data"),
        sys.prefix,
        sys.base_prefix,
        tempfile.gettempdir(),
        "/proc",
        "/dev",
        "/sys",
        "/usr",
        "/etc",
        "/run",
        "/var/tmp",
        # The OS itself. Spelled out rather than resolved through symlinks:
        # `/sbin` is `/usr/sbin` on a merged-usr system and `os.path.realpath`
        # would say so, but realpath lstats, lstat raises an audit event, and
        # an audit hook that resolves paths re-enters itself. Measured before
        # this list existed: `exec /sbin/ldconfig`, three items, from ctypes.
        "/bin",
        "/sbin",
        "/lib",
        "/lib64",
        "/opt",
        # The import machinery walks these on every import; see the module
        # docstring for the coverage this costs.
        *sys.path,
    ]
    out = []
    for p in raw:
        if not p:
            continue
        # BOTH forms, and this is not belt-and-braces. Resolving only this side
        # is a hole that measured itself: `/sbin` resolves to `/usr/sbin` on a
        # merged-usr system, the observed path stays `/sbin/ldconfig` because
        # the hook must not lstat, and the two never compare equal -- three
        # items reported for calling a system binary.
        out.append(os.path.normpath(str(p)))
        try:
            out.append(os.path.normpath(str(Path(p).resolve())))
        except OSError:  # pragma: no cover - unresolvable entry is not ours
            continue
    return [p for p in out if p and p != os.sep]


class _Probe:
    def __init__(self, repo: Path, out: Path) -> None:
        self.repo = os.path.normpath(str(repo.resolve()))
        self.out = out
        self.allow = [a for a in _allowed_roots(repo) if not self._under(a, self.repo)]
        self.current = "<collection>"
        self.hits: dict[str, set[str]] = {}
        self.items = 0

    @staticmethod
    def _under(path: str, root: str) -> bool:
        return path == root or path.startswith(root + os.sep)

    def _outside(self, raw: object) -> str | None:
        if not isinstance(raw, (str, bytes, os.PathLike)):
            return None
        try:
            p = os.fsdecode(raw)
        except (ValueError, TypeError):
            return None
        if not os.path.isabs(p):
            return None
        p = os.path.normpath(p)
        if self._under(p, self.repo):
            return None
        for a in self.allow:
            if self._under(p, a):
                return None
        return p

    def hook(self, event: str, args: tuple) -> None:
        if event in _EVENTS_PATH:
            found = self._outside(args[0] if args else None)
            if found:
                self.hits.setdefault(self.current, set()).add(f"{event} {found}")
        elif event == "subprocess.Popen":
            argv = args[1] if len(args) > 1 else None
            if not isinstance(argv, (list, tuple)):
                return
            for a in argv:
                found = self._outside(a)
                if found:
                    self.hits.setdefault(self.current, set()).add(f"exec {found}")

    def dump(self) -> None:
        self.out.write_text(
            json.dumps(
                {
                    "items": self.items,
                    "hits": {k: sorted(v) for k, v in self.hits.items()},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


_PROBE: _Probe | None = None

if os.environ.get(_ENV_REPO) and os.environ.get(_ENV_OUT):
    _PROBE = _Probe(Path(os.environ[_ENV_REPO]), Path(os.environ[_ENV_OUT]))
    sys.addaudithook(_PROBE.hook)


def pytest_runtest_protocol(item, nextitem):  # noqa: ARG001 - pytest hook shape
    if _PROBE is not None:
        _PROBE.current = item.nodeid
        _PROBE.items += 1
    return None


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001 - pytest hook shape
    if _PROBE is not None:
        _PROBE.dump()


# --- the driver half: run pytest with the probe and judge the result --------


# Items known to reach outside the repository, each with the reason and the
# lane that owns the file. Two rules keep this from becoming the thing it
# guards against: an item NOT in here is a failure, and an item in here that
# stopped reaching outside is ALSO a failure. A pin that no longer fires is a
# pin nobody removed, and a list that only ever grows is an allowlist with
# extra steps.
DA_BIET: dict[str, str] = {
    "tests/qa/qa-tt-0010/test_duong_phan_quyet_ruff_thu_hai.py"
    "::DuongPhanQuyetRuffThuHai"
    "::test_cong_ratchet_khong_doi_phan_quyet_khi_path_co_ruff_la": (
        "chay ruff da ghim tu ~/.cache/mobile-gate/ruff/<ban>/bin/ruff. "
        "Phan quyet phu thuoc cache ngoai repo co dung ban do khong. "
        "File cua lane QA -- da bao Lead, chua sua o day."
    ),
    "tests/test_phone_path.py::NodeSelection"
    "::test_node_plan_itself_leaves_a_working_path_node_alone": (
        "quet ~/.fnm/node-versions va ~/.nvm/versions/node. May co fnm/nvm "
        "hay khong doi duoc phan quyet, va khong may nao trong doi giong nhau."
    ),
}


class Refuse(Exception):
    """The question could not be answered. Never reported as a pass."""


def run_probe(targets: list[str], repo: Path, extra: list[str]) -> dict:
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "probe.json"
        env = {
            **os.environ,
            _ENV_REPO: str(repo),
            _ENV_OUT: str(out),
            "PYTHONPATH": os.pathsep.join(
                [str(repo / "scripts"), str(repo / "services" / "api")]
                + ([os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else [])
            ),
        }
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "check_suite_stays_in_repo",
                "-p",
                "no:cacheprovider",
                "-q",
                *extra,
                *targets,
            ],
            cwd=str(repo),
            env=env,
            capture_output=True,
            text=True,
        )
        if not out.is_file():
            raise Refuse(
                "KHONG KIEM DUOC: bo do khong ghi duoc ket qua -- pytest thoat "
                f"{proc.returncode}. Doan cuoi cua no:\n"
                + "\n".join(proc.stdout.strip().splitlines()[-15:])
                + "\n"
                + "\n".join(proc.stderr.strip().splitlines()[-10:])
            )
        data = json.loads(out.read_text(encoding="utf-8"))
        data["pytest_rc"] = proc.returncode
        data["tail"] = proc.stdout.strip().splitlines()[-1:]
        return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Ca test nao trong bo chan doc trang thai NGOAI repo."
    )
    ap.add_argument("targets", nargs="*", default=None)
    ap.add_argument("--repo", default=None)
    ap.add_argument(
        "--min-items",
        type=int,
        default=500,
        help="san cho mau so: chay it hon the nay la KHONG KIEM DUOC, vi mot "
        "lan chay 0 ca doc y het mot lan chay sach",
    )
    ap.add_argument("--pytest-arg", action="append", default=[])
    args = ap.parse_args(argv)

    repo = (
        Path(args.repo).resolve()
        if args.repo
        else Path(__file__).resolve().parent.parent
    )
    targets = args.targets or ["tests"]

    try:
        data = run_probe(targets, repo, args.pytest_arg)
    except Refuse as exc:
        print(str(exc), file=sys.stderr)
        return 3

    items = data["items"]
    if items < args.min_items:
        print(
            f"KHONG KIEM DUOC: chi chay {items} ca (san {args.min_items}). "
            "Mot luot quet khong chay gi tra ve 0 finding, doc y het mot bo "
            "test sach -- nen day la tu choi chu khong phai DAT.\n"
            f"  pytest thoat {data['pytest_rc']}: {' '.join(data['tail'])}",
            file=sys.stderr,
        )
        return 3

    hits = data["hits"]
    ngoai_ca = {k: v for k, v in hits.items() if k != "<collection>"}
    if hits.get("<collection>"):
        print("  (luc thu thap, khong quy cho ca nao):")
        for v in hits["<collection>"]:
            print(f"      {v}")
    moi = {k: v for k, v in ngoai_ca.items() if k not in DA_BIET}

    def _trong_pham_vi(pin: str) -> bool:
        """Only a pin whose file this run actually covered can be stale.

        Without this, `... tests/test_phone_path.py` reports every other pin as
        a pin that stopped firing, which is a red for asking a narrower
        question -- the opposite of what the staleness rule is for.
        """
        f = pin.split("::")[0]
        if not (repo / f).is_file():
            # The pin names a file this repo does not have, so this run cannot
            # say anything about it. Cost of this line, stated rather than
            # hidden: a pin whose file was DELETED is not reported as stale.
            return False
        return any(f == t or f.startswith(t.rstrip(os.sep) + "/") for t in targets)

    ghim_cu = sorted(p for p in set(DA_BIET) - set(ngoai_ca) if _trong_pham_vi(p))

    for node in sorted(set(ngoai_ca) & set(DA_BIET)):
        print(f"  (da ghim) {node}\n      {DA_BIET[node]}")

    if not moi and not ghim_cu:
        print(
            f"XANH: {items} ca; {len(ngoai_ca)} ca cham ra ngoai va ca "
            f"{len(ngoai_ca)} deu da duoc ghim kem ly do."
        )
        return 0

    if ghim_cu:
        print(
            f"\nDO: {len(ghim_cu)} muc ghim khong con cham ra ngoai nua -- "
            "xoa chung khoi DA_BIET:\n  " + "\n  ".join(ghim_cu),
            file=sys.stderr,
        )
    if moi:
        print(f"\nDO: {len(moi)}/{items} ca cham duong NGOAI repo ma chua ghim:\n")
        for node in sorted(moi):
            print(f"  {node}")
            for v in moi[node]:
                print(f"      {v}")
        print(
            "\nPhan quyet cua bo chan phai la ham cua repo. Phep do can cay "
            "ngoai repo thuoc ve mot chang `gate.sh` da dan nhan '(may nay "
            "thoi)' -- xem `harness-clock` va `harness-contract`.",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
