#!/usr/bin/env python3
"""Bảng đối chiếu 21 mockup ↔ ảnh chụp trên emulator (M7).

Each of the 21 product mockups in ``product/RuDi_Mobile_Product_Mockups`` is
mapped to the Maestro screenshot names that show the same screen on the
emulator. The script finds the newest capture for every mockup across the
harness run directories it is given and writes a Markdown table for the
leader. A mockup with no capture is reported as ``CHƯA CHỤP`` (or
``CHƯA CÓ FLOW`` when no flow photographs that screen yet); the exit code is
2 whenever such a cell exists, so the M7 exit criterion ("no CHƯA CHỤP cell")
is machine-checkable instead of a sentence in a PR body.

The table carries paths and statuses only: emulator PNGs never enter Git
(repo guard fails closed on binaries). ``--sheet-dir`` additionally writes a
side-by-side PNG per captured row (mockup left, emulator right) for reading on
the machine that holds the captures.

Usage, from the repo root::

    python3 scripts/bang_doi_chieu_mockup.py \\
        --run apps/mobile/.impeccable/review/native/<run-id> [--run ...] \\
        [--out docs/claude/<date>/bang-doi-chieu-mockup.md] [--sheet-dir <dir>] \\
        [--may "AVD rudi / Android 15 / 1080x2400@420"] [--che-do "dark, font 1.3"]

Exit codes: 0 every mockup has a capture · 2 at least one cell is CHƯA CHỤP /
CHƯA CÓ FLOW · 1 bad arguments or a candidate name no flow declares.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THU_MUC_MOCKUP = ROOT / "product" / "RuDi_Mobile_Product_Mockups"
THU_MUC_MAESTRO = ROOT / "apps" / "mobile" / ".maestro"
README_MOCKUP = THU_MUC_MOCKUP / "README.md"

CHUA_CHUP = "CHƯA CHỤP"
CHUA_CO_FLOW = "CHƯA CÓ FLOW"
DA_CHUP = "ĐÃ CHỤP"

_TAKE_SCREENSHOT_RE = re.compile(r"^\s*-\s*takeScreenshot:\s*(\S+)\s*$", re.MULTILINE)
_README_ROW_RE = re.compile(
    r"^\|\s*(\d{2}\.\d{2})\s*\|[^|]*\|\s*(?:✅|⚠️)\s*([A-Z ]+?)\s*\|", re.MULTILINE
)


@dataclass(frozen=True)
class ManMockup:
    """One product mockup and the emulator screenshots that show the same screen."""

    ma: str
    ten: str
    audit: str
    anh: str
    ung_vien: tuple[str, ...]
    ghi_chu: str = ""


# Candidate names are Maestro ``takeScreenshot`` names, best match first. A
# name that no flow declares is a drift error (``kiem_ung_vien``), so renaming
# a screenshot in a flow breaks this table loudly instead of silently emptying
# a cell.
DANH_SACH_MAN: tuple[ManMockup, ...] = (
    ManMockup(
        "01.01",
        "Welcome / Màn hình chào",
        "READY",
        "01_onboarding/01_welcome/01_01_welcome.png",
        ("00-welcome", "23-dang-xuat-ben-qua-lan-tat", "11-session-cleared-on-logout"),
    ),
    ManMockup(
        "01.02",
        "Đăng ký / Đăng nhập",
        "READY",
        "01_onboarding/02_login/01_02_login.png",
        ("22-man-dang-nhap", "01-login-google-honest"),
    ),
    ManMockup(
        "01.03",
        "Cá nhân hóa sở thích",
        "READY",
        "01_onboarding/03_personalization/01_03_personalization.png",
        ("01-personalization",),
        "Chỉ bảng mặc định (flow 01) chụp màn này; bảng --otp không đi qua.",
    ),
    ManMockup(
        "02.01",
        "Khám phá địa điểm",
        "READY",
        "02_discovery/01_explore/02_01_explore.png",
        ("26-danh-muc-that", "22-trong-nhom-moi", "04-explore-before"),
    ),
    ManMockup(
        "02.02",
        "AI Match / tìm kiếm tự nhiên",
        "NEEDS UPDATE",
        "02_discovery/02_ai_match/02_02_ai_match.png",
        (),
        "Tìm bằng câu (/places/search) có trong ExploreLive nhưng chưa flow nào chụp kết quả.",
    ),
    ManMockup(
        "02.03",
        "Chi tiết địa điểm",
        "NEEDS UPDATE",
        "02_discovery/03_place_detail/02_03_place_detail.png",
        ("26-chi-tiet", "26-chi-tiet-cuoi"),
    ),
    ManMockup(
        "03.01",
        "Nhóm chat",
        "NEEDS UPDATE",
        "03_group_chat_ai/01_group_chat/03_01_group_chat.png",
        ("30-phan-ung", "30-da-gui", "30-chat-rong"),
    ),
    ManMockup(
        "03.02",
        "AI tạo lịch trình",
        "NEEDS UPDATE",
        "03_group_chat_ai/02_ai_itinerary/03_02_ai_itinerary.png",
        ("40-ai-tra-loi",),
        "Chỉ lượt --ai (có khoá Gemini) chụp thẻ AI; lượt không khoá không có ảnh.",
    ),
    ManMockup(
        "03.03",
        "Bình chọn & chốt plan",
        "NEEDS UPDATE",
        "03_group_chat_ai/03_voting/03_03_voting.png",
        ("30-binh-chon", "06-vote-hidden-after-pick"),
    ),
    ManMockup(
        "04.01",
        "Tạo kèo đi chơi",
        "READY",
        "04_outing_management/01_create_outing/04_01_create_outing.png",
        ("27-tao-keo",),
    ),
    ManMockup(
        "04.02",
        "Lịch trình chuyến đi",
        "NEEDS UPDATE",
        "04_outing_management/02_trip_timeline/04_02_trip_timeline.png",
        ("27-hai-chang", "27-co-chang", "27-keo-moi"),
    ),
    ManMockup(
        "04.03",
        "Check-in & theo dõi nhóm",
        "READY",
        "04_outing_management/03_check_in/04_03_check_in.png",
        ("27-da-toi", "32-check-in"),
    ),
    ManMockup(
        "05.01",
        "Chụp bill / Xem lại hóa đơn",
        "READY",
        "05_smart_bill/01_receipt_review/05_01_receipt_review.png",
        ("28-xem-lai", "28-lui-mot-buoc", "28-bat-dau"),
    ),
    ManMockup(
        "05.02",
        "AI nhận diện món & gán người",
        "NEEDS UPDATE",
        "05_smart_bill/02_ocr_assignment/05_02_ocr_assignment.png",
        ("28-gan-mon", "10-assignment-after"),
    ),
    ManMockup(
        "05.03",
        "Kết quả thanh toán / Settlement",
        "NEEDS UPDATE",
        "05_smart_bill/03_settlement/05_03_settlement.png",
        ("29-quyet-toan-co-dot", "28-quyet-toan", "28-ket-qua", "20-settlement-live"),
    ),
    ManMockup(
        "06.01",
        "Tường nhóm riêng tư",
        "READY",
        "06_memories/01_group_wall/06_01_group_wall.png",
        ("32-tim-binh-luan", "32-check-in", "32-tuong-trong"),
    ),
    ManMockup(
        "06.02",
        "Album chuyến đi",
        "READY",
        "06_memories/02_trip_album/06_02_trip_album.png",
        ("32-album-keo", "32-ke-album"),
    ),
    ManMockup(
        "06.03",
        "Thả khoảnh khắc",
        "READY",
        "06_memories/03_share_moment/06_03_share_moment.png",
        (),
        "ShareMomentLive cần bộ chọn ảnh hệ thống; flow 32 check-in từ tường nên chưa chụp màn này.",
    ),
    ManMockup(
        "07.01",
        "Hồ sơ cá nhân",
        "NEEDS UPDATE",
        "07_profile_finance/01_profile/07_01_profile.png",
        ("24-ho-so-da-sua", "24-ho-so-that"),
    ),
    ManMockup(
        "07.02",
        "Tài chính cá nhân",
        "READY",
        "07_profile_finance/02_finance/07_02_finance.png",
        ("20-finance-live", "02-finance"),
        "Bảng --otp đi qua «Tài chính của tôi» (flow 29) nhưng không chụp; flow 20/02 chụp.",
    ),
    ManMockup(
        "07.03",
        "Thành tích",
        "READY",
        "07_profile_finance/03_achievements/07_03_achievements.png",
        ("32-thanh-tich-cuoi", "32-thanh-tich"),
    ),
)


@dataclass(frozen=True)
class HangBang:
    """One table row: the mockup plus the capture chosen for it (if any)."""

    man: ManMockup
    trang_thai: str
    anh_emulator: Path | None
    luot: str | None


def ten_da_khai_bao(thu_muc_maestro: Path = THU_MUC_MAESTRO) -> set[str]:
    """Every ``takeScreenshot`` name any flow (including ``_`` sub-flows) declares."""
    ten: set[str] = set()
    for flow in sorted(thu_muc_maestro.glob("*.yaml")):
        ten.update(_TAKE_SCREENSHOT_RE.findall(flow.read_text(encoding="utf-8")))
    return ten


def kiem_ung_vien(danh_sach: tuple[ManMockup, ...], da_khai_bao: set[str]) -> None:
    """Refuse a candidate no flow declares: a renamed screenshot must fail here, not empty a cell."""
    la = [
        (m.ma, ten) for m in danh_sach for ten in m.ung_vien if ten not in da_khai_bao
    ]
    if la:
        chi_tiet = ", ".join(f"{ma}:{ten}" for ma, ten in la)
        raise ValueError(f"ứng viên không flow nào khai takeScreenshot: {chi_tiet}")


def quet_lan_chay(thu_muc: Path) -> dict[str, Path]:
    """Map screenshot name → file for one harness run; only ``takeScreenshot`` output counts.

    The harness also writes ``screencap`` files for a red flow next to the log; those are
    evidence of a failure, not of a screen, and are skipped on purpose.
    """
    anh: dict[str, Path] = {}
    for p in sorted(thu_muc.rglob("*.png")):
        if p.parent.name == "takeScreenshot":
            anh[p.stem] = p
    return anh


def gop_lan_chay(cac_lan: list[Path]) -> dict[str, tuple[Path, str]]:
    """Merge runs so the newest run (by directory name, i.e. timestamp) wins per name."""
    gop: dict[str, tuple[Path, str]] = {}
    for lan in sorted(cac_lan, key=lambda p: p.name):
        for ten, path in quet_lan_chay(lan).items():
            gop[ten] = (path, lan.name)
    return gop


def dung_bang(
    danh_sach: tuple[ManMockup, ...], anh: dict[str, tuple[Path, str]]
) -> list[HangBang]:
    hang: list[HangBang] = []
    for man in danh_sach:
        if not man.ung_vien:
            hang.append(HangBang(man, CHUA_CO_FLOW, None, None))
            continue
        chon = next((anh[t] for t in man.ung_vien if t in anh), None)
        if chon is None:
            hang.append(HangBang(man, CHUA_CHUP, None, None))
        else:
            hang.append(HangBang(man, DA_CHUP, chon[0], chon[1]))
    return hang


_TEN_LUOT_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})-([0-9a-f]+)$")


def mo_ta_luot(ten: str) -> str:
    """Describe a harness run directory without a nine-digit run of digits.

    ``YYYYMMDD-HHMMSS-<sha>`` would trip the repo guard's long-number rule inside a
    committed table, so the timestamp is spelled out with a word between date and time;
    the directory name is recoverable mechanically.
    """
    m = _TEN_LUOT_RE.match(ten)
    if not m:
        return f"`{ten}`"
    y, mo, d, h, mi, se, sha = m.groups()
    return f"`{sha}`, chụp {y}-{mo}-{d} lúc {h}:{mi}:{se}"


def _duong_trong_luot(path: Path, cac_lan: list[Path]) -> str:
    for lan in cac_lan:
        try:
            return path.relative_to(lan).as_posix()
        except ValueError:
            continue
    return path.name


def xuat_markdown(
    hang: list[HangBang],
    cac_lan: list[Path],
    may: str | None,
    che_do: str | None,
    hom_nay: _dt.date | None = None,
) -> str:
    """Render the table. Paths only, never image bytes: the leader reads this on ``main``."""
    hom_nay = hom_nay or _dt.date.today()
    da = sum(1 for h in hang if h.trang_thai == DA_CHUP)
    dong = [
        f"# Bảng đối chiếu mockup ↔ emulator ({hom_nay.isoformat()})",
        "",
        f"{da}/{len(hang)} mockup có ảnh emulator. Mockup là *decision comp*, không phải comp đã duyệt; "
        "ô ĐÃ CHỤP nghĩa là màn tồn tại trên máy và được một flow Maestro chụp, không nghĩa là khớp từng pixel.",
        "",
    ]
    if may:
        dong.append(f"- Máy: {may}")
    if che_do:
        dong.append(f"- Chế độ: {che_do}")
    thu_tu = sorted(cac_lan, key=lambda p: p.name)
    nhan = {lan.name: f"L{i + 1}" for i, lan in enumerate(thu_tu)}
    dong.append(
        "- Lượt (thư mục `<ngày><giờ>-<sha>` trong `.impeccable/review/native/`; "
        "lượt sau thắng khi trùng tên ảnh):"
    )
    for lan in thu_tu:
        dong.append(f"  - {nhan[lan.name]} = {mo_ta_luot(lan.name)}")
    dong += [
        "",
        "| # | Màn hình | Audit mockup | Mockup | Ảnh emulator | Lượt | Trạng thái |",
        "|---|---|---|---|---|---|---|",
    ]
    for h in hang:
        if h.trang_thai == DA_CHUP and h.anh_emulator is not None:
            anh = f"`{_duong_trong_luot(h.anh_emulator, cac_lan)}`"
            luot = nhan.get(h.luot or "", f"`{h.luot}`")
            trang_thai = DA_CHUP
        else:
            anh = "—"
            luot = "—"
            trang_thai = f"**{h.trang_thai}**" + (
                f" · {h.man.ghi_chu}" if h.man.ghi_chu else ""
            )
        dong.append(
            f"| {h.man.ma} | {h.man.ten} | {h.man.audit} | `{h.man.anh}` | {anh} | {luot} | {trang_thai} |"
        )
    thieu = [h for h in hang if h.trang_thai != DA_CHUP]
    dong.append("")
    if thieu:
        dong.append(
            "Ô còn thiếu: "
            + ", ".join(f"{h.man.ma} ({h.trang_thai})" for h in thieu)
            + "."
        )
    else:
        dong.append("Không còn ô CHƯA CHỤP.")
    dong.append("")
    return "\n".join(dong)


def ve_bang_canh(hang: list[HangBang], thu_muc: Path, chieu_cao: int = 1600) -> int:
    """Write one side-by-side PNG (mockup | emulator) per captured row; returns the count.

    Pillow is optional: without it the Markdown table is still the deliverable.
    """
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - depends on the machine
        print("Pillow không có: bỏ qua ảnh cạnh nhau, bảng vẫn xuất.", file=sys.stderr)
        return 0
    thu_muc.mkdir(parents=True, exist_ok=True)
    so = 0
    for h in hang:
        if h.trang_thai != DA_CHUP or h.anh_emulator is None:
            continue
        trai = Image.open(THU_MUC_MOCKUP / h.man.anh).convert("RGB")
        phai = Image.open(h.anh_emulator).convert("RGB")
        trai = trai.resize(
            (max(1, round(trai.width * chieu_cao / trai.height)), chieu_cao)
        )
        phai = phai.resize(
            (max(1, round(phai.width * chieu_cao / phai.height)), chieu_cao)
        )
        khe = 24
        canvas = Image.new(
            "RGB", (trai.width + khe + phai.width, chieu_cao), (255, 255, 255)
        )
        canvas.paste(trai, (0, 0))
        canvas.paste(phai, (trai.width + khe, 0))
        canvas.save(thu_muc / f"{h.man.ma.replace('.', '_')}.png")
        so += 1
    return so


def audit_theo_readme(readme: Path = README_MOCKUP) -> dict[str, str]:
    """``{ma: audit}`` parsed from the mockup README table, so the column cannot drift."""
    return {
        ma: audit.strip()
        for ma, audit in _README_ROW_RE.findall(readme.read_text(encoding="utf-8"))
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--run",
        action="append",
        default=[],
        metavar="DIR",
        help="harness run directory (.impeccable/review/native/<run-id>); repeatable",
    )
    parser.add_argument(
        "--out",
        metavar="FILE.md",
        help="write the Markdown table here (default: stdout)",
    )
    parser.add_argument(
        "--sheet-dir",
        metavar="DIR",
        help="also write side-by-side PNGs here (needs Pillow)",
    )
    parser.add_argument(
        "--may",
        help="device line for the header, e.g. 'AVD rudi / Android 15 / 1080x2400@420'",
    )
    parser.add_argument(
        "--che-do", help="capture mode for the header, e.g. 'light, font 1.0'"
    )
    args = parser.parse_args(argv)
    if not args.run:
        parser.error("cần ít nhất một --run")
    cac_lan = [Path(r).resolve() for r in args.run]
    for lan in cac_lan:
        if not lan.is_dir():
            parser.error(f"không phải thư mục: {lan}")
    try:
        kiem_ung_vien(DANH_SACH_MAN, ten_da_khai_bao())
    except ValueError as e:
        print(f"LỖI: {e}", file=sys.stderr)
        return 1
    hang = dung_bang(DANH_SACH_MAN, gop_lan_chay(cac_lan))
    van_ban = xuat_markdown(hang, cac_lan, args.may, args.che_do)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(van_ban, encoding="utf-8")
        print(f"đã ghi {out}")
    else:
        sys.stdout.write(van_ban)
    if args.sheet_dir:
        so = ve_bang_canh(hang, Path(args.sheet_dir))
        print(f"ảnh cạnh nhau: {so} tấm ở {args.sheet_dir}")
    da = sum(1 for h in hang if h.trang_thai == DA_CHUP)
    thieu = len(hang) - da
    print(f"bảng: {da}/{len(hang)} đã chụp, {thieu} chưa")
    return 0 if thieu == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
