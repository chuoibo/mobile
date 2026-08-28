"""rd-qa-02 - Break the money on purpose and see which gate notices.

A green suite proves nothing until you have watched it go red. This runner
applies one surgical mutation at a time to the money path, runs the gate that
is supposed to catch it, records the exit code, and puts the file back with
``git checkout``. A mutation whose gate stays green is a hole in the suite, and
it is reported as one rather than quietly dropped.

Run from the repo root, with PostgreSQL up and the API port in MOBILE_QA_API:

    MOBILE_QA_API=http://127.0.0.1:PORT python3 tests/qa/rd-qa-02/run_mutations.py

The server-side mutations restart uvicorn themselves, because a process that
started before the edit is still running the old code -- which is exactly how a
mutation run talks itself into a false green.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
API_BASE = os.environ.get("MOBILE_QA_API", "http://127.0.0.1:8099")
API_PORT = API_BASE.rsplit(":", 1)[-1]


@dataclass
class Mutation:
    name: str
    what: str
    path: str
    old: str
    new: str
    gate: str
    gate_name: str
    restart_api: bool = False
    env: dict[str, str] = field(default_factory=dict)


MUTATIONS = [
    Mutation(
        name="M1",
        what="Bỏ bước chia phần dư: mỗi người chỉ nhận phần nguyên, "
        "Σ phân bổ nhỏ hơn hoá đơn.",
        path="services/api/app/domain/allocator.py",
        old="    gainers = ranked[:deficit]",
        new="    gainers = ranked[:0]",
        gate="python3 -m pytest services/api/tests/domain -q",
        gate_name="golden vectors (tests/domain)",
    ),
    Mutation(
        name="M2",
        what="Đảo tie-break làm tròn: người ứng tiền luôn thắng phần dư "
        "thay vì phần dư lớn nhất thắng.",
        path="services/api/app/domain/allocator.py",
        old="        return (-remainder, 0 if is_advancer else 1, participant.encode(\"utf-8\"))",
        new="        return (0 if is_advancer else 1, -remainder, participant.encode(\"utf-8\"))",
        gate="python3 -m pytest services/api/tests/domain -q",
        gate_name="golden vectors (tests/domain)",
    ),
    Mutation(
        name="M3",
        what="Máy chủ thôi so `expected_allocations` với số nó tự tính: "
        "client đẩy được con số của riêng mình vào sổ.",
        path="services/api/app/api/service.py",
        old="        if wire.allocations != request.expected_allocations:",
        new="        if False and wire.allocations != request.expected_allocations:",
        gate=(
            "node --test tests/qa/rd-qa-02/money-server-truth.mjs"
        ),
        gate_name="rd-qa-02 server invariants (ca chống giả mạo)",
        restart_api=True,
    ),
    Mutation(
        name="M4",
        what="Nghĩa vụ thu bớt 1đ so với phần được chia: tổng nợ nhỏ hơn tổng có.",
        path="services/api/app/api/service.py",
        old="                amount_vnd=item[\"amount_vnd\"],",
        new="                amount_vnd=item[\"amount_vnd\"] - 1,",
        gate="node --test tests/qa/rd-qa-02/money-server-truth.mjs",
        gate_name="rd-qa-02 server invariants (ca tổng nợ = tổng có)",
        restart_api=True,
    ),
    Mutation(
        name="M5",
        what="Định dạng tiền nhóm 4 chữ số thay vì 3: 1234567 in ra '123.4567'.",
        path="packages/shared/money.mjs",
        old="    if (i > 0 && (digits.length - i) % 3 === 0) out += \".\";",
        new="    if (i > 0 && (digits.length - i) % 4 === 0) out += \".\";",
        gate="node packages/shared/money.test.mjs",
        gate_name="money.mjs golden format cases",
    ),
    Mutation(
        name="M6",
        what="parseAmountVnd nhận cả số vượt trần thay vì từ chối: "
        "một con số quá lớn đi thẳng vào đề xuất.",
        path="packages/shared/money.mjs",
        old="  if (tooLong || tooBig) {",
        new="  if (false && (tooLong || tooBig)) {",
        gate="node packages/shared/money.test.mjs",
        gate_name="money.mjs parse refusals",
    ),
    Mutation(
        name="M7",
        what="Client tự chia lại tiền: `Math.floor(total / n)` quay lại api.ts.",
        path="apps/mobile/src/api.ts",
        old="export async function proposeSplit(draft: Draft, attempt: Attempt): Promise<PendingProposal> {",
        new=(
            "export function evenSplit(total: number, n: number): number {\n"
            "  return Math.floor(total / n);\n"
            "}\n\n"
            "export async function proposeSplit(draft: Draft, attempt: Attempt): Promise<PendingProposal> {"
        ),
        gate=(
            "cd apps/mobile && npx tsc -p tsconfig.test.json && "
            "node tools/fixup-esm.mjs && node --test tests/offline.test.mjs"
        ),
        gate_name="offline.test.mjs (chống mọc lại allocator ở client)",
    ),
    Mutation(
        name="M8",
        what="Trang khách in một số, chép một số khác: amount_display lệch 1đ so với amount_vnd.",
        path="services/api/app/web/guest_view.py",
        old="            \"amount_display\": format_vnd(obligation[\"amount_vnd\"]),",
        new="            \"amount_display\": format_vnd(obligation[\"amount_vnd\"] + 1),",
        gate="python3 -m pytest services/api/tests/web -q",
        gate_name="tests/web (trang khách)",
    ),
]


def sh(cmd: str, env: dict[str, str] | None = None) -> tuple[int, str]:
    merged = {**os.environ, "EXPO_PUBLIC_API_URL": API_BASE, **(env or {})}
    proc = subprocess.run(
        cmd,
        shell=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=merged,
        timeout=900,
    )
    return proc.returncode, (proc.stdout + proc.stderr)[-1500:]


_api_proc: subprocess.Popen | None = None


def api_up() -> bool:
    try:
        with urllib.request.urlopen(f"{API_BASE}/healthz", timeout=2) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def restart_api() -> None:
    """Bring the service back up on the code that is on disk right now."""
    global _api_proc
    if _api_proc is not None:
        os.killpg(os.getpgid(_api_proc.pid), signal.SIGTERM)
        _api_proc.wait(timeout=30)
        _api_proc = None
    for _ in range(40):
        if not api_up():
            break
        time.sleep(0.5)
    _api_proc = subprocess.Popen(
        ["uvicorn", "app.api.main:app", "--port", API_PORT, "--host", "127.0.0.1"],
        cwd=ROOT / "services" / "api",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(60):
        if api_up():
            return
        time.sleep(0.5)
    raise RuntimeError("API did not come back up")


def restore(path: str) -> None:
    subprocess.run(["git", "checkout", "--", path], cwd=ROOT, check=True)


def main() -> int:
    # Refuse to run on a dirty tree: a mutation runner that cannot tell its own
    # edits from somebody else's will restore the wrong thing.
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        print("cây làm việc không sạch, dừng lại:\n" + dirty)
        return 2

    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    print(f"commit: {sha}\napi: {API_BASE}\n")

    results = []
    for m in MUTATIONS:
        target = ROOT / m.path
        source = target.read_text(encoding="utf-8")
        if m.old not in source:
            results.append((m, "KHÔNG ÁP DỤNG ĐƯỢC", "chuỗi gốc không còn trong file", ""))
            print(f"{m.name}: KHÔNG ÁP DỤNG ĐƯỢC (chuỗi gốc đã đổi)")
            continue
        if source.count(m.old) != 1:
            results.append(
                (m, "KHÔNG ÁP DỤNG ĐƯỢC", f"chuỗi gốc xuất hiện {source.count(m.old)} lần", "")
            )
            print(f"{m.name}: KHÔNG ÁP DỤNG ĐƯỢC (chuỗi không duy nhất)")
            continue

        try:
            target.write_text(source.replace(m.old, m.new), encoding="utf-8")
            if m.restart_api:
                restart_api()
            code, out = sh(m.gate, m.env)
        finally:
            restore(m.path)
            if m.restart_api:
                restart_api()

        verdict = "ĐỎ" if code != 0 else "VẪN XANH"
        tail = out.strip().splitlines()[-1] if out.strip() else ""
        results.append((m, verdict, f"exit={code}", tail))
        print(f"{m.name}: {verdict} (exit={code}) — {m.gate_name}")

    # Baseline: with everything restored the same gates must be green again,
    # or the "red" above proves nothing about the mutation.
    print("\n-- kiểm lại cây đã phục hồi --")
    if any(m.restart_api for m in MUTATIONS):
        restart_api()
    baseline = {}
    for gate in sorted({m.gate for m in MUTATIONS}):
        code, _ = sh(gate)
        baseline[gate] = code
        print(f"exit={code}  {gate}")

    print("\n| ca | đột biến | cổng | kết quả |")
    print("|---|---|---|---|")
    for m, verdict, detail, _tail in results:
        print(f"| {m.name} | {m.what} | {m.gate_name} | {verdict} ({detail}) |")

    caught = sum(1 for _, v, _, _ in results if v == "ĐỎ")
    print(f"\n{caught}/{len(results)} đột biến bị bắt.")
    if any(code != 0 for code in baseline.values()):
        print("CẢNH BÁO: cây đã phục hồi vẫn còn cổng đỏ — kết quả trên không tin được.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
