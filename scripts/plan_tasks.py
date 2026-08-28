"""The plan, in a form a machine can check instead of read.

An autonomous agent that decides for itself what to do next needs to know what
is already done. Asking it is not enough -- an agent that believes it finished
something reports it finished, and the loop then moves on past a gap. So every
task here carries a `check`: a command that exits 0 only when the repository
actually contains the thing. The loop runs the checks, and the first failing
task in that agent's lane is the task.

**The checks are deliberately test-shaped, not grep-shaped.** A grep for a
function name is satisfied by writing the name; `pytest -k <name>` is satisfied
only by a test with that name that passes. That is still not proof the test is
any good -- a test can be written to pass without pinning anything, which has
happened three times in this repo already. The check is a floor, not a ceiling:
it stops the loop from advancing past untouched work. agy's testing is what
decides whether the work is real, and merging still waits on that.

Ordering is by what blocks the customer demo, not by what is interesting.
"""

TASKS = [
    {
        "id": "tai-khoan-nhan",
        "lane": "codex",
        "title": "Route đăng ký tài khoản nhận tiền",
        "why": (
            "Không có gì trong bề mặt HTTP ghi vào bảng `bank_recipients`. "
            "`load_bank_recipients` đọc nó, và khi trống thì `/batches` từ chối "
            "đóng băng với `recipient_setup_incomplete`. Hệ quả: không luồng nào "
            "chạy hết được từ trong app — không envelope, không VietQR, không "
            "trang khách. Đây là chỗ chặn demo lớn nhất còn lại. Bài e2e của app "
            "(`apps/mobile/tests/e2e/`) đang phải seed thẳng dòng đó vào Postgres "
            "để đi tiếp; file seed đó xoá đi ngay khi route này có."
        ),
        "brief": (
            "Thêm route cho người nhận tự khai tài khoản nhận tiền, và một route "
            "đọc lại trạng thái đó để cổng 2 của mục 8.3 đọc được câu trả lời "
            "thật thay vì đoán.\n\n"
            "Ràng buộc từ chính bảng `bank_recipients` đang có:\n"
            "- `bank_bin` đúng 6 chữ số, `account_number` 1-19 ký tự chữ-số\n"
            "- partial unique index: mỗi người nhận chỉ có MỘT bản ghi chưa thu hồi\n"
            "- `confirmed_by_recipient_at` là bắt buộc\n\n"
            "Hai điều spec đòi và dễ làm sai:\n"
            "- Chỉ CHÍNH người nhận mới khai được tài khoản của mình. Người khác "
            "khai hộ nghĩa là tiền của cả nhóm chảy vào tài khoản kẻ đó.\n"
            "- `confirmed_by_recipient_at` KHÔNG phải bằng chứng sở hữu tài khoản "
            "ngân hàng. Ghi rõ điều đó trong code, đừng để người sau đọc nhầm.\n\n"
            "Đổi tài khoản thì thu hồi bản cũ (`revoked_at`) rồi tạo bản mới — "
            "không ghi đè, vì snapshot trong đợt thu đã phát phải bất biến."
        ),
        "check": "cd services/api && python -m pytest tests -q -k bank_recipient_route",
    },
    {
        "id": "auth-khong-tin-header",
        "lane": "codex",
        "title": "`X-Actor-*` mặc định KHÔNG được tin",
        "why": (
            "`app/api/deps.py` đọc danh tính thẳng từ header client gửi. Mở ra "
            "internet là ai đặt header cũng thành bất kỳ ai — kể cả thành người "
            "ứng tiền của một nhóm họ chưa từng nghe tên."
        ),
        "brief": (
            "Bắt buộc khai tường minh rằng đang chạy chế độ tin header (biến môi "
            "trường), mặc định là KHÔNG tin. Không khai mà vẫn gửi `X-Actor-ID` "
            "thì từ chối — không lui về tin header. Test phải đỏ khi xoá dòng "
            "kiểm tra đó đi."
        ),
        "check": "cd services/api && python -m pytest tests -q -k actor_header_not_trusted",
    },
    {
        "id": "token-khong-ro",
        "lane": "codex",
        "title": "Token trang khách không rò qua Referer / cache",
        "why": (
            "`/g/{token}` mang capability trong đường dẫn. URL rò theo nhiều "
            "đường người ta không nghĩ tới: header `Referer`, lịch sử trình "
            "duyệt, log proxy, ảnh chụp màn hình."
        ),
        "brief": (
            "`Referrer-Policy: no-referrer` và `Cache-Control: no-store` trên mọi "
            "phản hồi trang khách. Kiểm xem có chỗ nào log full URL không. Tìm "
            "được đường rò khác thì ghi ra, đừng im."
        ),
        "check": "cd services/api && python -m pytest tests -q -k guest_no_referrer",
    },
    {
        "id": "gioi-han-nhip",
        "lane": "codex",
        "title": "Giới hạn nhịp HTTP cho route khách",
        "why": (
            "Quota phản đối và quota báo đã chuyển là quota nghiệp vụ. Không có "
            "gì chặn ai đó gọi `/g/{token}` mười nghìn lần, hoặc dò token bằng "
            "vét cạn."
        ),
        "brief": (
            "Giới hạn nhịp cho các route khách. Nói rõ trong code nó chặn được gì "
            "và KHÔNG chặn được gì — giới hạn theo IP không chặn kẻ có nhiều IP, "
            "và viết ra điều đó quan trọng hơn giả vờ nó chặn."
        ),
        "check": "cd services/api && python -m pytest tests -q -k guest_rate_limit",
    },
]
