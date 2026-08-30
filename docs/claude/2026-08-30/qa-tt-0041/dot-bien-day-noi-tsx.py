#!/usr/bin/env python3
"""Lan hai cho ba dot bien .tsx.

Lan mot do chung bang `tsc + node --test`, va do la mot phep do HONG cho .tsx:
`tsconfig.test.json` khong bien dich .tsx (khong co dist-test/navigation/VoTab.js),
con `vo-tab-web.test.mjs` lai lai doc BUNDLE `.expo-build-check` — bundle do la cua
cay CHUA dot bien. Ba hang M4/M5/M6 cua lan mot vi the khong noi gi.

Lan nay chay nguyen `npm test`, tuc co ca buoc `build:check` (expo export --clear),
nen bundle duoc dung lai tu chinh nguon da dot bien.
"""
import subprocess
import sys
from pathlib import Path

TREE = Path("/tmp/qa41-pr363/apps/mobile")
VOTAB = TREE / "src/navigation/VoTab.tsx"
TINNHAN = TREE / "src/screens/chat/TinNhan.tsx"

MUTANTS = [
    (
        "M4", "DO", VOTAB,
        '{tab === "tin-nhan" ? <TinNhan nguoi={nguoi} nhomPhien={nhom} /> : null}',
        '{tab === "tin-nhan" ? <TinNhan nguoi={nguoi} nhomPhien={null} /> : null}',
        "day noi: VoTab khong dua nhom cua phien xuong tab Tin nhan",
    ),
    (
        "M5", "DO", VOTAB,
        "return <>{renderKhoanChi(() => setLuongKhoanChi(false), nguoi, nhom)}</>;",
        "return <>{renderKhoanChi(() => setLuongKhoanChi(false), nguoi, null)}</>;",
        "day noi: khoan chi ghi vao nhom demo thay vi nhom dang xem",
    ),
    (
        "M6", "DO", TINNHAN,
        "  }, [nguoi, nhomPhien]);\n\n  useEffect(() => {\n    if (!nguoi || nhom.kind !== \"xong\") return;",
        "  }, [nguoi]);\n\n  useEffect(() => {\n    if (!nguoi || nhom.kind !== \"xong\") return;",
        "effect khong theo doi nhomPhien: doi nhom giua chung thi man khong mo lai",
    ),
    (
        "C2", "XANH", VOTAB,
        '{tab === "len-plan" ? <LenPlan nguoi={nguoi} nhomPhien={nhom} /> : null}',
        '{tab === "len-plan" ? <LenPlan nguoi={nguoi} nhomPhien={nhom ?? null} /> : null}',
        "DOI CHUNG GIU TINH CHAT: `nhom ?? null` tren mot gia tri da la `NhomWire|null`",
    ),
]


def chay():
    p = subprocess.run(["bash", "-lc", "npm test"], cwd=TREE,
                       capture_output=True, text=True, timeout=2400)
    out = p.stdout + p.stderr
    passed = failed = skipped = None
    for line in out.splitlines():
        if line.startswith("# pass "):
            passed = int(line.split()[-1])
        elif line.startswith("# fail "):
            failed = int(line.split()[-1])
        elif line.startswith("# skipped "):
            skipped = int(line.split()[-1])
    return p.returncode, passed, failed, skipped, out


def main():
    print("=== NEN (npm test day du, cay chua dot bien) ===", flush=True)
    rc, p, f, s, out = chay()
    print(f"nen: rc={rc} pass={p} fail={f} skipped={s}", flush=True)
    if rc != 0 or f:
        print(out[-4000:])
        return 2

    bang = []
    for mid, need, path, old, new, why in MUTANTS:
        goc = path.read_text()
        if goc.count(old) != 1:
            print(f"{mid}: NEO HONG ({goc.count(old)} lan)", flush=True)
            bang.append((mid, need, "NEO-HONG", "", why))
            continue
        path.write_text(goc.replace(old, new, 1))
        try:
            rc, p, f, s, out = chay()
        finally:
            path.write_text(goc)
        thuc = "DO" if (rc != 0 or (f or 0) > 0) else "XANH"
        ten = ""
        for line in out.splitlines():
            if line.startswith("not ok "):
                ten = line[len("not ok "):].strip()
                break
        print(f"{mid}: can {need}, do duoc {thuc}  pass={p} fail={f} skipped={s}  {ten[:70]}", flush=True)
        bang.append((mid, need, thuc, f"pass={p} fail={f} skipped={s} | {ten[:80]}", why))

    print("\n| id | can | do duoc | ket qua | chi tiet | dot bien |")
    print("|---|---|---|---|---|---|")
    lot = 0
    for mid, need, thuc, chi, why in bang:
        dat = "DAT" if thuc == need else "LOT"
        if dat == "LOT":
            lot += 1
        print(f"| {mid} | {need} | {thuc} | {dat} | {chi} | {why} |")
    co_xanh = any(t == "XANH" for _, _, t, _, _ in bang)
    co_do = any(t == "DO" for _, _, t, _, _ in bang)
    print()
    if not (co_xanh and co_do):
        print("BANG KHONG DUNG DUOC: chi ra mot gia tri, khong phan biet duoc gi.")
        return 3
    print(f"{lot} dot bien lot." if lot else "Khong dot bien nao lot.")
    return 1 if lot else 0


if __name__ == "__main__":
    sys.exit(main())
