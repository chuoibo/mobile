#!/usr/bin/env python3
"""Mutation table for PR #363 (bug-223337).

Each row flips ONE decision the patch makes, then runs the whole mobile test
suite.  A row is only informative when the table can also produce GREEN, so a
property-preserving control row is included on purpose: an all-red table proves
the harness is broken, not that the gate has teeth.

Run from anywhere; paths are absolute.
"""

import subprocess
import sys
from pathlib import Path

TREE = Path("/tmp/qa41-pr363/apps/mobile")

NHOM = TREE / "src/screens/chat/nhom.ts"
VOTAB = TREE / "src/navigation/VoTab.tsx"
TINNHAN = TREE / "src/screens/chat/TinNhan.tsx"

# (id, need, file, old, new, why)
#   need == "DO"   -> the suite MUST fail; the patch's claim is guarded
#   need == "XANH" -> control: behaviour is unchanged, the suite MUST pass
MUTANTS = [
    (
        "M1",
        "DO",
        NHOM,
        "return nhomPhien ? moNhomDaCo(nhomPhien, nguoi, opts) : khoiDongNhom(nguoi, opts);",
        "return khoiDongNhom(nguoi, opts);",
        "bo qua nhom cua phien, luon dung lai nhom demo",
    ),
    (
        "M2",
        "DO",
        NHOM,
        "  return docRoster(base, nhom.id, nhom.display_name, nguoi);",
        "  return docRoster(base, nhom.id, nhom.display_name, personById(MINH_SLUG)!);",
        "doc danh sach thanh vien duoi danh nghia nguoi khac (minh), khong phai nguoi dang dang nhap",
    ),
    (
        "M3",
        "DO",
        NHOM,
        "  const slug = nguoi.id;",
        "  const slug = nguoi.id;\n  if (!personById(slug)) {\n    return hong('dat-ten', `${goc(base)}/people`, 0, 'khong co nguoi trong nhom demo');\n  }",
        "tra lai chinh bug-223337: tu choi nguoi khong nam trong bay nguoi seed",
    ),
    (
        "M4",
        "DO",
        VOTAB,
        '{tab === "tin-nhan" ? <TinNhan nguoi={nguoi} nhomPhien={nhom} /> : null}',
        '{tab === "tin-nhan" ? <TinNhan nguoi={nguoi} nhomPhien={null} /> : null}',
        "day noi: VoTab khong dua nhom cua phien xuong tab Tin nhan",
    ),
    (
        "M5",
        "DO",
        VOTAB,
        "return <>{renderKhoanChi(() => setLuongKhoanChi(false), nguoi, nhom)}</>;",
        "return <>{renderKhoanChi(() => setLuongKhoanChi(false), nguoi, null)}</>;",
        "day noi: khoan chi ghi vao nhom demo thay vi nhom dang xem",
    ),
    (
        "M6",
        "DO",
        TINNHAN,
        '  }, [nguoi, nhomPhien]);\n\n  useEffect(() => {\n    if (!nguoi || nhom.kind !== "xong") return;',
        '  }, [nguoi]);\n\n  useEffect(() => {\n    if (!nguoi || nhom.kind !== "xong") return;',
        "effect khong theo doi nhomPhien: doi nhom giua chung thi man khong mo lai",
    ),
    (
        "C1",
        "XANH",
        NHOM,
        "export async function moNhomDaCo(\n  nhom: NhomPhien,\n  nguoi: NguoiDung,\n  opts: { base?: string } = {},\n): Promise<NhomState> {\n  const base = opts.base ?? NHOM_BASE_URL;",
        "export async function moNhomDaCo(\n  nhom: NhomPhien,\n  nguoi: NguoiDung,\n  opts: { base?: string } = {},\n): Promise<NhomState> {\n  const base = opts.base ?? NHOM_BASE_URL;\n  const khongDung = base.length;\n  void khongDung;",
        "DOI CHUNG GIU TINH CHAT: them mot bien khong ai doc, hanh vi y nguyen",
    ),
]

CMD = (
    "npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && "
    "node --test $(find tests -path tests/e2e -prune -o -name '*.test.mjs' -print | sort)"
)


def chay():
    p = subprocess.run(
        ["bash", "-lc", CMD], cwd=TREE, capture_output=True, text=True, timeout=1800
    )
    out = p.stdout + p.stderr
    passed = failed = None
    for line in out.splitlines():
        if line.startswith("# pass "):
            passed = int(line.split()[-1])
        elif line.startswith("# fail "):
            failed = int(line.split()[-1])
    return p.returncode, passed, failed, out


def main():
    print("=== NEN (cay chua dot bien) ===", flush=True)
    rc, p, f, out = chay()
    if rc != 0 or f != 0:
        print(f"NEN KHONG XANH: rc={rc} pass={p} fail={f}")
        print(out[-3000:])
        return 2
    print(f"nen: rc=0 pass={p} fail={f}\n", flush=True)

    bang = []
    for mid, need, path, old, new, why in MUTANTS:
        goc = path.read_text()
        if goc.count(old) != 1:
            bang.append(
                (mid, need, "NEO-HONG", f"neo xuat hien {goc.count(old)} lan", why)
            )
            print(f"{mid}: NEO HONG ({goc.count(old)} lan) — khong do duoc", flush=True)
            continue
        path.write_text(goc.replace(old, new, 1))
        try:
            rc, p, f, out = chay()
        finally:
            path.write_text(goc)
        thuc = "DO" if (rc != 0 or (f or 0) > 0) else "XANH"
        dat = "DAT" if thuc == need else "LOT"
        # first failing test name, for evidence
        ten = ""
        for line in out.splitlines():
            if line.startswith("not ok "):
                ten = line[len("not ok ") :].strip()
                break
        bang.append((mid, need, thuc, f"pass={p} fail={f} rc={rc} | {ten[:90]}", why))
        print(
            f"{mid}: can {need}, do duoc {thuc} -> {dat}  ({f} ca do)  {ten[:70]}",
            flush=True,
        )

    print("\n=== BANG ===")
    print("| id | can | do duoc | ket qua | ca do dau tien | dot bien |")
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
        print(
            "BANG KHONG DUNG DUOC: khong co ca hai gia tri XANH va DO, "
            "nen no khong phan biet duoc cai gi duoc gac."
        )
        return 3
    if lot:
        print(f"CO {lot} DOT BIEN LOT — cong KHONG gac het nhung gi PR khang dinh.")
        return 1
    print("Moi dot bien deu ra dung ket qua can co.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
