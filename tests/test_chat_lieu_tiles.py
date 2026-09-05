"""Ba ô chất liệu của UI v2 (apps/mobile/assets/textures) — pin điều mà ảnh chụp mới chứng minh được.

Bảng native 2026-09-05 cho thấy hai lần «có chất liệu» chỉ đúng trên giấy: ô giấy ở
opacity 0.07 và ô mực (giấy) trong con dấu đo ra phẳng (stddev ≈ 2) trên emulator.
Test này đo bằng số điều reviewer đo bằng mắt: ô mực in phải phá được mặt coral ở
opacity StampButton dùng (≈ 8 mức, cùng bậc với vải trên bìa), ô nào cũng có
provenance nhúng, và không ô nào là ảnh chụp (kích thước 256², RGBA, nền trong).
Pillow là phụ thuộc của bộ test dịch vụ; vắng nó thì test này skip có lý do, không
phải xanh.
"""

from __future__ import annotations

import pathlib

import pytest

PIL = pytest.importorskip("PIL", reason="Pillow chưa cài trong môi trường này")
from PIL import Image, ImageStat  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
THU_MUC = ROOT / "apps/mobile/assets/textures"
CORAL = (0xFB, 0x69, 0x3E)
DO_MO_CON_DAU = 0.26  # phải khớp StampButton.tsx


def _do_tren(anh: Image.Image, nen: tuple[int, int, int], do_mo: float) -> float:
    r, g, b, a = anh.split()
    lop = Image.merge("RGBA", (r, g, b, a.point(lambda v: int(v * do_mo))))
    day = Image.new("RGBA", anh.size, nen + (255,))
    return ImageStat.Stat(Image.alpha_composite(day, lop).convert("RGB")).stddev[0]


@pytest.mark.parametrize("ten", ["vai-bia.png", "giay-trang.png", "muc-in.png"])
def test_o_chat_lieu_la_o_lap_thu_tuc(ten: str) -> None:
    anh = Image.open(THU_MUC / ten)
    assert anh.mode == "RGBA" and anh.size == (256, 256), (anh.mode, anh.size)
    # Provenance: imp embed-prompt (tEXt «impeccable:prompt», đặt SAU IDAT nên Pillow chỉ
    # đọc khi load()) hoặc Comment của script sinh.
    anh.load()
    meta = anh.info
    assert "impeccable:prompt" in meta or "Comment" in meta, f"{ten} không có provenance nhúng"
    # Không ô nào là ảnh chụp: nền trong suốt chiếm phần lớn diện tích alpha.
    alpha_mean = ImageStat.Stat(anh).mean[3]
    assert alpha_mean < 80, f"{ten}: alpha trung bình {alpha_mean:.1f}, không còn là ô nhiễu trên nền trong"


def test_muc_in_pha_duoc_mat_coral_o_do_mo_con_dau() -> None:
    anh = Image.open(THU_MUC / "muc-in.png")
    do = _do_tren(anh, CORAL, DO_MO_CON_DAU)
    assert 6.0 <= do <= 12.0, f"stddev {do:.2f} trên coral @{DO_MO_CON_DAU}: dưới 6 là phẳng (như bảng 2026-09-05), trên 12 là nhiễu"


def test_stamp_button_dung_dung_o_va_do_mo() -> None:
    src = (ROOT / "apps/mobile/src/rudi/ui/StampButton.tsx").read_text(encoding="utf-8")
    assert 'material="mucIn"' in src, "StampButton phải dùng ô mực in, không phải ô giấy (đo phẳng trên coral)"
    assert f"opacity={{{DO_MO_CON_DAU}}}" in src, "đổi opacity trong StampButton thì đổi DO_MO_CON_DAU ở đây để phép đo còn đúng"


def test_script_sinh_ra_dung_tung_byte() -> None:
    """Cùng seed, cùng byte: đổi tham số mà không sinh lại + ghim lại là hai ô khác nhau."""
    import importlib.util
    import io

    spec = importlib.util.spec_from_file_location("sinh_chat_lieu", ROOT / "scripts/sinh_chat_lieu_ui_v2.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    anh = mod.sinh()
    tren_dia = Image.open(THU_MUC / "muc-in.png").convert("RGBA")
    assert list(anh.getdata()) == list(tren_dia.getdata()), "muc-in.png trên đĩa không khớp script sinh (đổi tham số mà chưa sinh lại?)"
    buf = io.BytesIO(); anh.save(buf, format="PNG")
    assert buf.tell() > 0
