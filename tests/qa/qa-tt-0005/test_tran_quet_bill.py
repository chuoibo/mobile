"""Trần nhịp quét bill là một quyết định; trên main nó là một hằng số tự do.

`#227` đặt trần cho `POST /receipts/scan`, lượt gọi vision đắt nhất của sản
phẩm và là chặng giữa của đường hero (chụp bill → AI đọc từng món). Bộ test đi
kèm nó chứng minh **cơ chế** rất kỹ: burst bị cắt, cắt theo từng người, cửa sổ
mở lại, lượt bị từ chối không chạm tới model, và một lượt retry không đẩy cửa
sổ ra xa thêm. Không có chỗ nào trong số đó cần sửa.

Cái nó không chứng minh là **con số**. `test_the_shipped_route_meters_without_
any_test_installing_a_limiter` suy kỳ vọng RA TỪ chính hằng số đang được kiểm::

    codes = [scan(client).status_code for _ in range(RECEIPT_SCAN_LIMIT_PER_WINDOW + 1)]
    assert codes == [200] * RECEIPT_SCAN_LIMIT_PER_WINDOW + [429]

Đặt hằng số bằng 3000 thì vòng lặp chạy 3001 lượt và khẳng định
`[200] * 3000 + [429]`, rồi xanh. File ngay bên cạnh, cho `/places/search`, thì
ghim thẳng (`assert SEARCH_LIMIT_PER_WINDOW == 12`) — route rẻ hơn được ghim,
route đắt hơn thì không.

Đo tại `23b603f` (đã ở main), toàn bộ `services/api/tests` + `tests`, nền là
1486 passed / 328 skipped / 4713 subtests:

=========================================  ======================  =============
đột biến                                   hậu quả                 kết quả
=========================================  ======================  =============
`RECEIPT_SCAN_LIMIT_PER_WINDOW` 30 → 3000  trần biến mất           1486 xanh
`RECEIPT_SCAN_WINDOW_SECONDS`   60 → 1     trần/phút → trần/giây   1486 xanh
`RECEIPT_SCAN_LIMIT_PER_WINDOW` 30 → 1     hero chết ở lượt 2      17 ĐỎ
=========================================  ======================  =============

Hàng thứ ba là hàng phải đọc kỹ, vì nó trông giống một cổng đang hoạt động và
không phải. Mười bảy ca đỏ đó nằm ở `tests/qa/rd-qa-37/test_exif_duong_bill.py`
và `tests/qa/rd-qa-38/` — test về lột EXIF và về mã lỗi, không ca nào khẳng
định bất cứ điều gì về trần. Chúng đỏ vì cùng dùng `from app.api.main import
app`, tức cùng MỘT limiter mức tiến trình, và ở trần bằng 1 thì lượt quét thứ
hai của cả phiên bị 429. Đo đỉnh thật trên chính singleton đó: **23 trên 30**.
Nên chiều hạ trần được che bởi một tai nạn, không phải bởi một khẳng định, và
lớp che ấy mỏng đúng bảy lượt quét.

Cổng này khẳng định **hành vi ở hai đầu** trên chính đối tượng `create_app`
cài, chứ không ghim một con số duy nhất: con số đúng là một khoảng, và một phép
ghim `== 30` chỉ bắt người sau sửa test cho khớp. Khoảng lấy từ lập luận mà
chính `app/api/search_rate_limit.py` đã viết ra — trần phải nằm "well above any
plausible human burst and far below loop scale".
"""

from __future__ import annotations

import uuid

from app.api.errors import ApiProblem
from app.api.search_rate_limit import build_receipt_scan_limiter

# Chặn dưới, và nó không phải một con số chọn cho đẹp. `#227` khởi đầu ở 10 và
# chính bộ test bác bỏ nó: `tests/qa/rd-qa-38` đẩy một người qua hơn 10 lượt
# quét trong một cửa sổ mà không làm gì bất thường, nên trần đã dời lên 30 vì
# bằng chứng đó. Số đo của lượt này nói cùng một chuyện, độc lập: đỉnh thật
# trên limiter mức tiến trình của cả bộ test là 23 lượt trong một cửa sổ.
#
# Nên chặn dưới phải nằm trên vùng đã bị bác bỏ, chứ không sát mép nó. Mười hai
# — đúng trần của `/places/search` — thì không: nó chỉ hơn con số đã bị bác bỏ
# đúng hai lượt, và một canary đặt trần quét bill bằng trần tìm kiếm đã đi lọt
# qua bản đầu của cổng này. Hai mươi là gấp đôi vùng đã bác bỏ và vẫn dưới trần
# đang ship, nên cổng vẫn là một khoảng chứ không phải một phép ghim.
BURST_NGUOI_THAT = 20

# Chặn trên. Một vòng lặp bắn hàng trăm request mỗi giây, nên bất kỳ trần nào ở
# mức hàng chục cũng ghim chi tiêu của một phút vào một hằng số nhỏ. Con số này
# không phải "trần đúng"; nó là ranh giới mà vượt qua thì trần thôi không còn
# là trần nữa, và việc vượt qua phải là một dòng diff có người đọc.
TRAN_TOI_DA = 60

# Cửa sổ. Dưới 60 giây thì "tối đa N lượt mỗi 60 giây" thành một câu sai trong
# chính thông điệp từ chối gửi cho người dùng; trên 5 phút thì "thử lại sau ít
# phút" thành một câu sai theo chiều kia, và người bị chặn đợi lâu hơn họ được
# báo.
CUA_SO_TOI_THIEU = 60
CUA_SO_TOI_DA = 300


def _da_ship():
    """Chính đối tượng `create_app` cài vào `state.receipt_scan_limiter`.

    Không dựng lại một `FixedWindowLimiter` bằng tay ở đây. Một limiter tự dựng
    trong test là thứ chứng minh cơ chế rồi vẫn xanh khi bản ship được cấu hình
    bằng một con số không ai định — đó đúng là chỗ hở file này tồn tại để bịt.
    """

    return build_receipt_scan_limiter()


def test_nguoi_chup_lai_bill_may_lan_khong_bi_tu_choi():
    """Chặn dưới, đo bằng hành vi trên chính limiter đã ship.

    Chiều này hiện có bị bắt, nhưng bị bắt bởi mười bảy ca ở hai file QA khác
    nói về EXIF và mã lỗi — chúng đỏ vì hết ngân sách chung, không vì khẳng định
    điều gì về trần. Sửa hay tách hai file đó ra là gỡ luôn lớp che. Ca này nói
    thẳng điều cần giữ, ở chỗ người sửa trần sẽ nhìn.
    """

    limiter = _da_ship()
    nguoi = uuid.uuid4()

    for lan in range(1, BURST_NGUOI_THAT + 1):
        try:
            limiter.check(nguoi)
        except ApiProblem as exc:  # pragma: no cover - chỉ chạy khi cổng đỏ
            raise AssertionError(
                f"lượt quét thứ {lan} của MỘT người đã bị từ chối, trong khi "
                f"{BURST_NGUOI_THAT} lượt trong một cửa sổ là hành vi bình "
                "thường của người chụp lại tờ bill mờ; trần đang thấp hơn "
                "burst của người thật, nên đường hero hỏng trước khi có vòng "
                "lặp nào bị chặn"
            ) from exc


def test_mot_vong_lap_van_bi_chan_o_muc_hai_con_so():
    """Chặn trên, đo bằng hành vi: trần vẫn phải là một trần.

    Đây là ca đỏ khi trần bị nâng tới mức không còn giới hạn cái gì. Bài kiểm
    hiện có vẫn xanh ở đó vì nó đọc kỳ vọng ra từ chính hằng số.
    """

    limiter = _da_ship()
    nguoi = uuid.uuid4()

    cho_qua = 0
    for _ in range(2_000):
        try:
            limiter.check(nguoi)
        except ApiProblem:
            break
        cho_qua += 1
    else:  # pragma: no cover - chỉ chạy khi cổng đỏ
        raise AssertionError(
            "2000 lượt quét liên tiếp từ MỘT người, không lượt nào bị chặn; "
            "đây là lượt gọi vision đắt nhất của sản phẩm và trên thực tế nó "
            "đang không có trần nào"
        )

    assert cho_qua <= TRAN_TOI_DA, (
        f"một người đi qua {cho_qua} lượt quét vision trong một cửa sổ; trên "
        f"{TRAN_TOI_DA} thì đây không còn là trần chặn bán kính thiệt hại"
    )


def test_cua_so_dai_bang_phut_dung_nhu_cau_tu_choi_da_hua():
    """Cửa sổ là nửa còn lại của trần, và nó nằm trong chính câu từ chối.

    `RECEIPT_SCAN_WINDOW_SECONDS` xuống 1 thì "tối đa 30 lượt mỗi 60 giây" trở
    thành 30 lượt mỗi giây — trần danh nghĩa không đổi, trần thật nhân 60 lần —
    và không ca nào trên main đỏ. Đọc thẳng từ đối tượng đã ship, vì đó là thứ
    `create_app` cài, không phải hằng số mà test tự nhập lại.
    """

    limiter = _da_ship()

    assert limiter.window_seconds >= CUA_SO_TOI_THIEU, (
        f"cửa sổ {limiter.window_seconds}s: trần {limiter.limit} lượt mỗi cửa "
        f"sổ thành {limiter.limit * 60 / limiter.window_seconds:.0f} lượt mỗi "
        "phút, và câu từ chối gửi cho người dùng đang nói một con số khác"
    )
    assert limiter.window_seconds <= CUA_SO_TOI_DA, (
        f"cửa sổ {limiter.window_seconds}s: câu từ chối hứa 'thử lại sau ít "
        "phút' nhưng người bị chặn phải đợi lâu hơn thế"
    )
