"""Two measurements behind the qa-tt-0052 verdict on PR #419.

Run it, do not read a summary of it:

    python3 tests/qa/qa-tt-0052-neo-wrapper/probe_neo_wrapper.py

Neither measurement touches the working tree. The client is copied to a
temporary directory and `CLIENT_ROOT` is pointed at the copy, so the rename
under test exists only for the duration of one call.

A. THE PREMISE OF #419 IS STILL TRUE ON MAIN.
   Rename a wrapper in the copied client and `check()` returns *no findings*.
   The script exits 0 and prints "Client và máy chủ khớp hợp đồng" while a
   double-digit number of call sites have stopped being read. Only
   `tests/test_api_contract.py` catches it, so `scripts/check_api_contract.py`
   run on its own -- which is what `scripts/gate.sh:338` does -- still lies.

B. THE FIX AS WRITTEN CANNOT LAND.
   `CLIENT_WRAPPERS = ("call", "translated")` on the #419 branch names two
   functions `api.ts` no longer declares, because #397 renamed them to the
   four `*AsActor` / `*Anonymous` names before #419 was rebased. This probe
   reports which of the reader's wrapper names the real client still declares,
   which is the one number that decides whether the merged gate can run.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GATE = REPO_ROOT / "scripts" / "check_api_contract.py"


def load_gate():
    """Import the gate as a module without putting scripts/ on sys.path."""
    spec = importlib.util.spec_from_file_location("contract_gate", GATE)
    module = importlib.util.module_from_spec(spec)
    # Registered before exec: @dataclass resolves its own module by name.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def measure(gate, rename: tuple[str, str] | None) -> tuple[int, int, int]:
    """(findings, paths, sites) for the real client, optionally renamed.

    The rename is applied to a copy. `check()` reads whatever `CLIENT_ROOT`
    points at, so pointing it elsewhere is the whole mechanism.
    """
    original_client = gate.CLIENT_ROOT
    original_root = gate.REPO_ROOT
    with tempfile.TemporaryDirectory() as tmp:
        # The copy mirrors apps/mobile/src under a fake root, because `check()`
        # reports each file as `path.relative_to(REPO_ROOT)` and those strings
        # are the keys of `.api-contract-unresolved.json`. A flat copy would
        # give every pin a new name and turn all nine into fresh findings.
        copy = Path(tmp) / "apps" / "mobile" / "src"
        copy.parent.mkdir(parents=True)
        shutil.copytree(original_client, copy)
        if rename is not None:
            old, new = rename
            for path in copy.rglob("*.ts*"):
                text = path.read_text(encoding="utf-8")
                if old in text:
                    path.write_text(text.replace(old, new), encoding="utf-8")
        gate.CLIENT_ROOT = copy
        gate.REPO_ROOT = Path(tmp)
        try:
            findings, summary = gate.check()
        except RuntimeError:
            # The anchor fired: `check()` refuses to report numbers it does not
            # trust. That is the gate working, so it is a result and not a
            # crash -- (-1, -1, -1) is the caller's signal for "red, not blind".
            return -1, -1, -1
        finally:
            gate.CLIENT_ROOT = original_client
            gate.REPO_ROOT = original_root
    return len(findings), summary["duong_dan_tim_thay"], summary["lan_goi_doc_duoc"]


def main() -> int:
    gate = load_gate()

    wrappers = sorted(
        name for name in gate.REQUEST_FUNCTIONS if name not in gate.DIRECT_FETCH
    )
    declared = gate.declared_wrappers() if hasattr(gate, "declared_wrappers") else None

    print("Tên wrapper bộ đọc đang dùng :", wrappers)
    if declared is not None:
        print("Tên wrapper client khai báo  :", sorted(declared))
        missing = [n for n in getattr(gate, "CLIENT_WRAPPERS", ()) if n not in declared]
        print("CLIENT_WRAPPERS còn thiếu    :", missing or "(không)")
        if missing:
            print(
                "  -> cổng sẽ NÉM RuntimeError và thoát 2 trên cây này: "
                "danh sách neo viết tay đã lệch khỏi client."
            )

    base_findings, base_paths, base_sites = measure(gate, None)
    print(
        f"\nNỀN            : {base_paths} đường dẫn / {base_sites} lần gọi, "
        f"{base_findings} finding"
    )

    # Every wrapper, not just one. Renaming `callAnonymous` alone costs two
    # call sites and no paths, so a probe that stopped at the first name would
    # have reported this gap as closed.
    blind: list[str] = []
    for victim in wrappers:
        ren_findings, ren_paths, ren_sites = measure(gate, (victim, victim + "V2"))
        if ren_findings < 0:
            print(f"Đổi tên {victim:<20}: cổng NÉM RuntimeError -> thoát 2. Đã bịt.")
            continue
        lost = base_paths - ren_paths
        silent = lost > 0 and ren_findings == 0
        if silent:
            blind.append(victim)
        print(
            f"Đổi tên {victim:<20}: {ren_paths} đường dẫn / {ren_sites} lần gọi, "
            f"{ren_findings} finding, mất {lost} đường dẫn"
            f"{'   <-- MÙ, vẫn thoát 0' if silent else ''}"
        )

    print()
    if blind:
        print(
            f"MÙ ở {len(blind)}/{len(wrappers)} wrapper: {blind}. Đổi tên bất kỳ tên "
            "nào trong số đó thì scripts/check_api_contract.py chạy lẻ vẫn THOÁT 0 "
            "và in 'khớp hợp đồng'."
        )
        print(
            "Chỉ tests/test_api_contract.py bắt được. Đó là khoảng trống #419 nhắm tới,"
            " và nó vẫn mở trên main."
        )
        return 0
    print("Không tên nào làm cổng mù im lặng — khoảng trống đã được bịt ở tầng script.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
