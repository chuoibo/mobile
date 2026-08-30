"""Prove the probe bites: break the product on purpose, one property at a time.

A probe that only ever runs against correct code has never demonstrated it can
fail. Each mutation below removes exactly ONE guarantee from the server, restarts
the real uvicorn process so the mutated code is actually loaded, re-runs the probe
that claims to cover that guarantee, and requires it to go RED. A mutation that
leaves the probe green is reported as a hole in the probe, not as a win.

Two anchoring hazards this file is written around:

* ``select(Vote)...with_for_update()`` appears twice in ``repository.py`` --
  once in ``upsert_ballot`` and once in ``close_vote``. Anchors here carry
  enough surrounding text to name the intended copy, so a mutation cannot
  silently patch the other one and report a false RED.
* Every mutation restores the source in a ``finally`` block and re-verifies the
  file is byte-identical to ``git show HEAD:<path>`` afterwards.
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[3]
API = REPO / "services" / "api"
REPOSITORY = API / "app" / "api" / "repository.py"
VOTE_DOMAIN = API / "app" / "domain" / "vote.py"
PROBE = Path(__file__).resolve().parent / "probe_binh_chon_that.py"

PORT = 8232
BASE_URL = f"http://127.0.0.1:{PORT}"
DB_URL = "postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile_qa24"

# The vote-row lock inside upsert_ballot. VOTE_CLOSED (not VOTE_ALREADY_CLOSED)
# is what distinguishes this copy from the identical select in close_vote.
UPSERT_VOTE_LOCK = """        vote = self.session.scalar(
            select(Vote).where(Vote.id == vote_id).with_for_update()
        )
        if vote is None:
            raise RepositoryConflict("VOTE_NOT_FOUND")
        if vote.closed_at is not None:
            raise RepositoryConflict("VOTE_CLOSED")"""

UPSERT_VOTE_NO_LOCK = UPSERT_VOTE_LOCK.replace(
    "select(Vote).where(Vote.id == vote_id).with_for_update()",
    "select(Vote).where(Vote.id == vote_id)",
)

BALLOT_LOCK = """        ballot = self.session.scalar(
            select(VoteBallot)
            .where(
                VoteBallot.vote_id == vote_id,
                VoteBallot.voter_id == voter_id,
            )
            .with_for_update()
        )
        replaced_previous_ballot = ballot is not None"""

BALLOT_NO_LOCK = BALLOT_LOCK.replace("\n            .with_for_update()", "")

BALLOT_ALWAYS_INSERT = BALLOT_LOCK + "\n        ballot = None"

TIE_HONEST = (
    "    decided_option_id = leading_option_ids[0] "
    "if len(leading_option_ids) == 1 else None"
)
TIE_PICKS_A_SIDE = (
    "    decided_option_id = leading_option_ids[0] if leading_option_ids else None"
)


@dataclass
class Mutation:
    name: str
    path: Path
    before: str
    after: str
    probe_args: list[str]
    expects: str


MUTATIONS = [
    Mutation(
        name="M1 - bo khoa FOR UPDATE tren hang VOTE trong upsert_ballot",
        path=REPOSITORY,
        before=UPSERT_VOTE_LOCK,
        after=UPSERT_VOTE_NO_LOCK,
        probe_args=["--only", "5", "--rounds", "20"],
        expects="hai phieu cung luc cua cung mot nguoi khong con duoc noi tiep nhau",
    ),
    Mutation(
        name="M2 - bo khoa FOR UPDATE tren hang BALLOT",
        path=REPOSITORY,
        before=BALLOT_LOCK,
        after=BALLOT_NO_LOCK,
        probe_args=["--only", "5", "--rounds", "20"],
        expects="tang khoa thu hai bien mat",
    ),
    Mutation(
        name="M3 - luon CHEN phieu moi thay vi thay phieu cu",
        path=REPOSITORY,
        before=BALLOT_LOCK,
        after=BALLOT_ALWAYS_INSERT,
        probe_args=["--only", "1"],
        expects="bo phieu lan hai phai de lai hai hang / hoac vo rang buoc",
    ),
    Mutation(
        name="M4 - cho may chon ho khi hoa",
        path=VOTE_DOMAIN,
        before=TIE_HONEST,
        after=TIE_PICKS_A_SIDE,
        probe_args=["--only", "3"],
        expects="hoa phai bi bao thanh mot ben thang",
    ),
]


def wait_for_server(deadline: float = 45.0) -> bool:
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        try:
            if httpx.get(f"{BASE_URL}/healthz", timeout=2.0).status_code == 200:
                return True
        except Exception:  # noqa: BLE001 - polling a port that may not be open yet
            pass
        time.sleep(0.5)
    return False


def stop_server() -> None:
    subprocess.run(
        ["pkill", "-f", f"uvicorn app.api.main:app --port {PORT}"], check=False
    )
    time.sleep(1.5)


def start_server() -> subprocess.Popen:
    log = open("/tmp/uvicorn-qa24.log", "a")  # noqa: SIM115 - lives as long as the server
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.api.main:app",
            "--port",
            str(PORT),
            "--host",
            "127.0.0.1",
        ],
        cwd=API,
        stdout=log,
        stderr=subprocess.STDOUT,
        env={**__import__("os").environ, "MOBILE_DATABASE_URL": DB_URL},
    )
    if not wait_for_server():
        raise SystemExit("server khong len duoc sau khi restart")
    return process


def restart_server() -> subprocess.Popen:
    stop_server()
    return start_server()


def apply_patch(path: Path, before: str, after: str) -> str:
    original = path.read_text(encoding="utf-8")
    hits = original.count(before)
    if hits != 1:
        raise SystemExit(
            f"neo dot bien khop {hits} lan trong {path.name}, phai khop dung 1 lan"
        )
    path.write_text(original.replace(before, after), encoding="utf-8")
    return original


def assert_pristine(path: Path) -> None:
    relative = path.relative_to(REPO)
    committed = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if committed != path.read_text(encoding="utf-8"):
        raise SystemExit(f"KHONG khoi phuc duoc {relative} -- dung lai, dung commit gi")


def run_probe(args: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(PROBE), *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=900,
    )
    return result.returncode, result.stdout + result.stderr


def main() -> int:
    print("=== doi chung: cay SACH phai XANH truoc da ===")
    restart_server()
    code, output = run_probe(["--only", "5", "--rounds", "20"])
    print(output.strip().splitlines()[-1] if output.strip() else "(khong co output)")
    if code != 0:
        print("cay sach da DO -- khong the doc ket qua dot bien nao sau day")
        return 1

    verdicts: list[tuple[str, bool, str]] = []
    for mutation in MUTATIONS:
        print(f"\n=== {mutation.name} ===")
        print(f"    mong doi: {mutation.expects}")
        original = None
        try:
            original = apply_patch(mutation.path, mutation.before, mutation.after)
            restart_server()
            code, output = run_probe(mutation.probe_args)
            tail = [
                line
                for line in output.splitlines()
                if "FAIL" in line or "phep kiem" in line
            ]
            for line in tail[:8]:
                print("   ", line.strip())
            caught = code != 0
            verdicts.append(
                (mutation.name, caught, "\n".join(tail[:4]) if tail else output[-300:])
            )
            print(
                f"    -> probe {'DO (bat duoc)' if caught else 'XANH (KHONG bat duoc)'}"
            )
        finally:
            if original is not None:
                mutation.path.write_text(original, encoding="utf-8")
            assert_pristine(mutation.path)

    restart_server()
    print("\n=== bang dot bien ===")
    missed = 0
    for name, caught, _ in verdicts:
        print(f"  {'DO   ' if caught else 'XANH '} {name}")
        missed += 0 if caught else 1
    print(f"\n{len(verdicts) - missed}/{len(verdicts)} dot bien bi bat")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
