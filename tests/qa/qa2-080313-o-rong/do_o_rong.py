#!/usr/bin/env python3
"""Measure the candidate blind spots instead of asserting them.

`quet_o_rong.py` finds the SHAPE. Shape is not a defect: half of the anchor
tables it flags make the gate STRICTER when emptied, which is harmless. This
file answers the only question that decides the difference, per site:

    empty that table -> does the gate get QUIETER or LOUDER?

Quieter is the bug. Louder is noise. Everything here patches the table in
memory and calls the real entry point, so nothing is written to the tree and
no gate is graded against a copy of its own logic.
"""

from __future__ import annotations

import importlib.util
import io
import contextlib
import pathlib
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[3]
RESULTS: list[tuple[str, str, str, str]] = []


def load(rel: str):
    path = REPO / rel
    spec = importlib.util.spec_from_file_location(path.stem + "_probe", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def record(site: str, before: str, after: str, verdict: str) -> None:
    RESULTS.append((site, before, after, verdict))
    print(f"\n--- {site}")
    print(f"    nguyên vẹn : {before}")
    print(f"    bảng RỖNG  : {after}")
    print(f"    => {verdict}")


# ---------------------------------------------------------------------------
# M1 -- check_pin_drift.IMPORT_CRITICAL
# ---------------------------------------------------------------------------


def m1() -> None:
    """A pin that is import-critical and absent must be red (exit 1).

    `critical_offenders` filters `r["critical"]`, which is `name in
    IMPORT_CRITICAL`. Empty that set and no row is ever critical, so the gate
    exits 0 no matter how far the interpreter has drifted from the pins.
    """

    mod = load("scripts/check_pin_drift.py")
    with tempfile.TemporaryDirectory() as tmp:
        req = pathlib.Path(tmp) / "r.txt"
        # A critical package pinned to a version nobody has installed.
        req.write_text("fastapi==0.0.1\npytest==0.0.1\n", encoding="utf-8")

        def run() -> int:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                try:
                    return mod.main(["--requirements", str(req)])
                except SystemExit as exc:
                    return int(exc.code or 0)

        intact = run()
        keep = mod.IMPORT_CRITICAL
        mod.IMPORT_CRITICAL = frozenset()
        try:
            emptied = run()
        finally:
            mod.IMPORT_CRITICAL = keep

    verdict = (
        "MÙ — cùng một cây lệch pin, cổng đỏ khi bảng đầy và XANH khi bảng rỗng"
        if intact != 0 and emptied == 0
        else f"không mù theo phép đo này (intact={intact}, emptied={emptied})"
    )
    record(
        "check_pin_drift.py :: IMPORT_CRITICAL",
        f"exit {intact}",
        f"exit {emptied}",
        verdict,
    )


# ---------------------------------------------------------------------------
# M2 -- repo_guard.SECRET_RULES
# ---------------------------------------------------------------------------


def m2() -> None:
    """Secrets must not be allowlistable.

    `ALLOWLISTABLE_RULES = (CONTENT_RULES - SECRET_RULES) | {...}` is computed
    at import. With `SECRET_RULES` empty the subtraction removes nothing and
    every secret rule becomes something a lane can pin into
    `.repo-guard-allowlist.json` and walk past.
    """

    src = (REPO / "scripts/repo_guard.py").read_text(encoding="utf-8")
    ns_intact: dict = {}
    exec(compile(src, "repo_guard", "exec"), ns_intact)  # noqa: S102 - reading the real file
    intact = "google-api-key" in ns_intact["ALLOWLISTABLE_RULES"]

    emptied_src = src.replace("SECRET_RULES = {", "SECRET_RULES = set() or {", 1)
    # Rebuild with an empty SECRET_RULES by overriding after definition but
    # before ALLOWLISTABLE_RULES is computed -- do it textually so the real
    # expression still runs.
    emptied_src = src.replace(
        "ALLOWLISTABLE_RULES = (CONTENT_RULES - SECRET_RULES)",
        "SECRET_RULES = frozenset()\nALLOWLISTABLE_RULES = (CONTENT_RULES - SECRET_RULES)",
        1,
    )
    ns_empty: dict = {}
    exec(compile(emptied_src, "repo_guard_empty", "exec"), ns_empty)  # noqa: S102
    emptied = "google-api-key" in ns_empty["ALLOWLISTABLE_RULES"]

    verdict = (
        "MÙ — google-api-key từ 'không thể allowlist' thành 'allowlist được'"
        if not intact and emptied
        else f"không mù theo phép đo này (intact={intact}, emptied={emptied})"
    )
    record(
        "repo_guard.py :: SECRET_RULES",
        f"google-api-key allowlist được? {intact}",
        f"google-api-key allowlist được? {emptied}",
        verdict,
    )


# ---------------------------------------------------------------------------
# M3 -- repo_guard.FORBIDDEN_SEQUENCES
# ---------------------------------------------------------------------------


def m3() -> None:
    """A path the guard is supposed to refuse must stay refused."""

    mod = load("scripts/repo_guard.py")
    # Pick a path the intact table actually refuses, so the measurement has a
    # real subject rather than one invented to fit.
    probes = [
        "docs/team/bill/anh.png",
        "data/export/participants.csv",
        "services/api/.env",
        "phase0/raw/transcript.txt",
    ]
    refused = [p for p in probes if mod.is_forbidden_path(p)]
    if not refused:
        record(
            "repo_guard.py :: FORBIDDEN_SEQUENCES",
            "không tìm được đường dẫn mẫu bị từ chối",
            "-",
            "KHÔNG ĐO ĐƯỢC — cần mẫu khớp FORBIDDEN_SEQUENCES",
        )
        return

    keep = mod.FORBIDDEN_SEQUENCES
    mod.FORBIDDEN_SEQUENCES = set()
    try:
        still = [p for p in refused if mod.is_forbidden_path(p)]
    finally:
        mod.FORBIDDEN_SEQUENCES = keep

    verdict = (
        f"MÙ — {len(refused) - len(still)}/{len(refused)} đường dẫn hết bị từ chối"
        if len(still) < len(refused)
        else "không mù — FORBIDDEN_COMPONENTS vẫn bắt được cả mấy mẫu này"
    )
    record(
        "repo_guard.py :: FORBIDDEN_SEQUENCES",
        f"từ chối {len(refused)}/{len(probes)}: {refused}",
        f"từ chối {len(still)}/{len(probes)}: {still}",
        verdict,
    )


# ---------------------------------------------------------------------------
# M4 -- check_api_contract.REQUEST_FUNCTIONS
# ---------------------------------------------------------------------------


def m4() -> None:
    """The reader recognises client calls BY NAME, off `REQUEST_FUNCTIONS`.

    #430 put a floor under `WRAPPERS`, which is derived from this set. This
    asks whether the set the derivation READS FROM has one too.
    """

    mod = load("scripts/check_api_contract.py")
    intact_wrappers = sorted(mod.WRAPPERS)

    src = (REPO / "scripts/check_api_contract.py").read_text(encoding="utf-8")
    hits = [
        ln
        for ln in src.splitlines()
        if "REQUEST_FUNCTIONS" in ln and not ln.strip().startswith("#")
    ]
    floor = [
        ln
        for ln in hits
        if ("len(" in ln and any(op in ln for op in ("<", ">", "!=", "==")))
        or "not REQUEST_FUNCTIONS" in ln
        or "assert" in ln
    ]

    verdict = (
        "MÙ — không có sàn nào cho REQUEST_FUNCTIONS; rỗng thì WRAPPERS rỗng, "
        "và sàn của #430 kêu 'lỗi cấu hình' đúng nhưng nguyên nhân nằm ở bảng trên"
        if not floor
        else f"có sàn: {floor}"
    )
    record(
        "check_api_contract.py :: REQUEST_FUNCTIONS",
        f"WRAPPERS = {intact_wrappers}",
        f"{len(hits)} lần dùng, {len(floor)} sàn",
        verdict,
    )


def main() -> int:
    for fn in (m1, m2, m3, m4):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - a probe that dies must say so
            record(
                fn.__name__, "-", "-", f"KHÔNG ĐO ĐƯỢC — {type(exc).__name__}: {exc}"
            )

    print("\n" + "=" * 78)
    blind = [r for r in RESULTS if r[3].startswith("MÙ")]
    unmeasured = [r for r in RESULTS if r[3].startswith("KHÔNG ĐO ĐƯỢC")]
    print(f"{len(RESULTS)} chỗ đo, {len(blind)} MÙ, {len(unmeasured)} không đo được")
    for site, _b, _a, verdict in RESULTS:
        mark = (
            "MÙ "
            if verdict.startswith("MÙ")
            else ("?  " if verdict.startswith("KHÔNG") else "ok ")
        )
        print(f"  {mark} {site}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
