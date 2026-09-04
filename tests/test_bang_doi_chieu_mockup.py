"""The mockup ↔ emulator table (M7) must not drift from the mockup package or the flows.

What each case proves:
- the table covers exactly the 21 mockups of the package and every mockup file exists;
- the audit column is read from the package README, not retyped;
- every candidate screenshot name is declared by a flow (a renamed ``takeScreenshot``
  fails here instead of silently emptying a cell);
- the newest run wins per name, failure screencaps are ignored, and the exit code is 2
  whenever a cell is CHƯA CHỤP / CHƯA CÓ FLOW.
"""

from __future__ import annotations

import importlib.util
import re
import struct
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "bang_doi_chieu_mockup", ROOT / "scripts" / "bang_doi_chieu_mockup.py"
)
assert _SPEC is not None and _SPEC.loader is not None
bdc = importlib.util.module_from_spec(_SPEC)
# dataclasses resolve postponed annotations through sys.modules[cls.__module__].
sys.modules[_SPEC.name] = bdc
_SPEC.loader.exec_module(bdc)


def _png_nho(rong: int = 2, cao: int = 4) -> bytes:
    """A valid RGB PNG built with the stdlib: the table checks existence, the sheet test resizes it."""

    def khoi(loai: bytes, du_lieu: bytes) -> bytes:
        return (
            struct.pack(">I", len(du_lieu))
            + loai
            + du_lieu
            + struct.pack(">I", zlib.crc32(loai + du_lieu) & 0xFFFFFFFF)
        )

    dong = b"\x00" + b"\xfb\x69\x3e" * rong
    return (
        b"\x89PNG\r\n\x1a\n"
        + khoi(b"IHDR", struct.pack(">IIBBBBB", rong, cao, 8, 2, 0, 0, 0))
        + khoi(b"IDAT", zlib.compress(dong * cao))
        + khoi(b"IEND", b"")
    )


def _ghi_png(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_png_nho())
    return path


def test_dung_21_man_va_moi_mockup_ton_tai():
    ma = [m.ma for m in bdc.DANH_SACH_MAN]
    assert len(ma) == 21
    assert len(set(ma)) == 21
    thieu = [
        m.anh for m in bdc.DANH_SACH_MAN if not (bdc.THU_MUC_MOCKUP / m.anh).is_file()
    ]
    assert thieu == []


def test_cot_audit_doc_tu_readme_cua_goi_mockup():
    tu_readme = bdc.audit_theo_readme()
    assert len(tu_readme) == 21
    lech = {
        m.ma: (m.audit, tu_readme.get(m.ma))
        for m in bdc.DANH_SACH_MAN
        if tu_readme.get(m.ma) != m.audit
    }
    assert lech == {}


def test_moi_ung_vien_deu_duoc_mot_flow_khai():
    da_khai_bao = bdc.ten_da_khai_bao()
    assert "28-quyet-toan" in da_khai_bao
    bdc.kiem_ung_vien(bdc.DANH_SACH_MAN, da_khai_bao)


def test_ung_vien_go_sai_ten_bi_tu_choi_chu_khong_de_o_trong():
    sai = (bdc.ManMockup("99.99", "thử", "READY", "x.png", ("28-quyet-toann",)),)
    with pytest.raises(ValueError) as thong_tin:
        bdc.kiem_ung_vien(sai, bdc.ten_da_khai_bao())
    assert "99.99:28-quyet-toann" in str(thong_tin.value)


def _ba_man() -> tuple:
    return (
        bdc.ManMockup(
            "05.03",
            "Settlement",
            "NEEDS UPDATE",
            "05_smart_bill/03_settlement/05_03_settlement.png",
            ("29-quyet-toan-co-dot", "28-quyet-toan"),
        ),
        bdc.ManMockup(
            "02.03",
            "Chi tiết",
            "NEEDS UPDATE",
            "02_discovery/03_place_detail/02_03_place_detail.png",
            ("26-chi-tiet",),
        ),
        bdc.ManMockup(
            "06.03",
            "Thả khoảnh khắc",
            "READY",
            "06_memories/03_share_moment/06_03_share_moment.png",
            (),
            "chưa có flow",
        ),
    )


def test_luot_moi_nhat_thang_va_screencap_that_bai_bi_bo_qua(tmp_path: Path):
    cu = tmp_path / "luot-1-cu-aaaaaaa"
    moi = tmp_path / "luot-2-moi-bbbbbbb"
    _ghi_png(cu / "t1" / "28-chia-bill-that" / "takeScreenshot" / "28-quyet-toan.png")
    # A red-flow screencap that happens to carry a screenshot name is not a capture.
    _ghi_png(cu / "t1" / "26-kham-pha-that" / "26-chi-tiet.png")
    _ghi_png(moi / "t2" / "28-chia-bill-that" / "takeScreenshot" / "28-quyet-toan.png")

    anh = bdc.gop_lan_chay([moi, cu])
    assert anh["28-quyet-toan"][1] == moi.name
    assert "26-chi-tiet" not in anh

    hang = bdc.dung_bang(_ba_man(), anh)
    assert [(h.man.ma, h.trang_thai) for h in hang] == [
        ("05.03", bdc.DA_CHUP),
        ("02.03", bdc.CHUA_CHUP),
        ("06.03", bdc.CHUA_CO_FLOW),
    ]
    van_ban = bdc.xuat_markdown(hang, [moi, cu], "AVD thử", "dark, font 1.3")
    assert "1/3 mockup có ảnh emulator" in van_ban
    assert "`t2/28-chia-bill-that/takeScreenshot/28-quyet-toan.png`" in van_ban
    assert "**CHƯA CHỤP**" in van_ban
    assert "**CHƯA CÓ FLOW** · chưa có flow" in van_ban
    assert "Ô còn thiếu: 02.03 (CHƯA CHỤP), 06.03 (CHƯA CÓ FLOW)." in van_ban
    assert f"  - L1 = `{cu.name}`" in van_ban
    assert f"  - L2 = `{moi.name}`" in van_ban
    assert "| L2 | ĐÃ CHỤP |" in van_ban


def test_mo_ta_luot_khong_de_lai_chuoi_chin_chu_so():
    # Assembled from pieces so this test file itself carries no nine-digit run.
    ten = "-".join(["2026" + "0904", "12" + "5207", "da101c9"])
    mo_ta = bdc.mo_ta_luot(ten)
    assert mo_ta == "`da101c9`, chụp 2026-09-04 lúc 12:52:07"
    assert not re.search(r"\d(?:[ .-]?\d){8,}", mo_ta)
    assert bdc.mo_ta_luot("luot-1-cu") == "`luot-1-cu`"


def test_ma_thoat_2_khi_con_o_thieu_va_0_khi_du(tmp_path: Path, monkeypatch, capsys):
    lan = tmp_path / "luot-3-ccccccc"
    _ghi_png(lan / "t" / "28-chia-bill-that" / "takeScreenshot" / "28-quyet-toan.png")
    out = tmp_path / "bang.md"

    monkeypatch.setattr(bdc, "DANH_SACH_MAN", _ba_man())
    assert bdc.main(["--run", str(lan), "--out", str(out)]) == 2
    assert "bảng: 1/3 đã chụp, 2 chưa" in capsys.readouterr().out
    assert out.read_text(encoding="utf-8").count("| 0") == 3

    du = tuple(m for m in _ba_man() if m.ung_vien)
    _ghi_png(lan / "t" / "26-kham-pha-that" / "takeScreenshot" / "26-chi-tiet.png")
    monkeypatch.setattr(bdc, "DANH_SACH_MAN", du)
    assert bdc.main(["--run", str(lan), "--out", str(out)]) == 0
    assert "Không còn ô CHƯA CHỤP." in out.read_text(encoding="utf-8")


def test_thieu_run_hoac_thu_muc_khong_co_la_loi_tham_so(tmp_path: Path):
    with pytest.raises(SystemExit) as thoat:
        bdc.main([])
    assert thoat.value.code == 2
    with pytest.raises(SystemExit):
        bdc.main(["--run", str(tmp_path / "khong-co")])


def test_anh_canh_nhau_moi_hang_da_chup(tmp_path: Path):
    pytest.importorskip("PIL")
    lan = tmp_path / "luot-4-ddddddd"
    chup = _ghi_png(
        lan / "t" / "26-kham-pha-that" / "takeScreenshot" / "26-chi-tiet.png"
    )
    hang = [
        bdc.HangBang(_ba_man()[1], bdc.DA_CHUP, chup, lan.name),
        bdc.HangBang(_ba_man()[2], bdc.CHUA_CO_FLOW, None, None),
    ]
    so = bdc.ve_bang_canh(hang, tmp_path / "sheet", chieu_cao=120)
    assert so == 1
    from PIL import Image

    with Image.open(tmp_path / "sheet" / "02_03.png") as im:
        assert im.height == 120
        assert im.width > 120
