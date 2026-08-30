# QA F37 — thước phim kỷ niệm (PR #352)

Hai kịch bản đi bộ trên **API sống**, không phải trên fake repository.

```
đo tại   b516f4b (nhánh backend/rd-be-37-highlight-reel)
         backend giữa b516f4b và e58e38e (head lúc viết) KHÔNG đổi một dòng nào:
         git diff b516f4b e58e38e -- services/api  ->  rỗng
sha này  là nhánh CHƯA merge; gate trên cây gộp chạy riêng, xem báo cáo
```

## Chạy

```bash
# một stack dùng một lần, tự dựng và tự xoá — không đụng bộ `make up` của lane nào
set -a && . /đường/dẫn/.env && set +a          # cần GEMINI_API_KEY, thước phim gọi model THẬT
scripts/e2e_slice.sh --keep                     # in ra API URL nó vừa dựng

export no_proxy=127.0.0.1,localhost NO_PROXY=127.0.0.1,localhost
REEL_API=http://127.0.0.1:<port> python3 tests/qa/qa-37-reel/di-bo-reel.py
REEL_API=http://127.0.0.1:<port> python3 tests/qa/qa-37-reel/do-cua-so-va-tiem-chich.py
```

`SKIP_WINDOW=1` bỏ phần đo cửa sổ 60 giây của file thứ hai (phần đó cố ý ngồi
chờ hết một phút thật).

## Vì sao chúng tồn tại

Mọi tầng có sẵn của nhánh đều giả một nửa: `tests/api/` giả repository,
`tests/domain/` không có HTTP, `tests/postgres/` không có ASGI app phía trước
SQL. Bốn câu hỏi dưới đây không tầng nào trả lời được, nên phải đi bộ:

| Câu hỏi | Đo bằng |
|---|---|
| Người nhóm A **nói dối header** có lấy được thân của nhóm B không | so byte 403 của outing thật với 403 của outing bịa |
| Thước phim có **chọn được ảnh thật** không, hay trả danh sách rỗng | gọi Gemini thật, đối chiếu id trả về với id máy chủ đã chào |
| Trần nhịp chặn ở đâu, và **có đúng một phút** không | đếm tới lúc 429, rồi đo lại ở +35s và +67s trên đồng hồ tường |
| Ảnh trong thước phim **đã tước EXIF** chưa, người ngoài tải được không | nhồi GPS + Make + UserComment canary vào JPEG rồi tải lại |

## Bẫy đã trả giá khi viết hai file này

**Chuyến đi nhận ảnh THEO NGÀY, không theo khoá ngoại** (xem docstring của
`list_outing_memories`). Một chuyến "rỗng" tạo trong hôm nay sẽ âm thầm thừa
hưởng ảnh của chuyến khác cùng ngày — bản đầu của `di-bo-reel.py` làm đúng thế
và biến phép đo trần nhịp thành 45 lời gọi model thật. Chuyến rỗng phải nằm ở
một ngày khác.

**Phép kiểm rò rỉ phải thu hẹp về đúng phần model viết.** Ba lần liên tiếp bản
nháp báo đỏ trên `caption` và trên chuỗi uuid nằm trong `caption` — đó là câu
chính nhóm đã gõ, máy chủ trả lại hàng của họ cho họ. Chỉ `title` và `note` là
chữ của model; quét cả thân là gọi một biên đang chạy đúng là hỏng.

**Canary phải chứng minh được là mình đo thật.** Mỗi phép kiểm rò rỉ đi kèm một
đối chứng dương: chính chủ nhóm B *phải* thấy được dữ liệu của mình, ảnh gốc
*phải* thật sự có EXIF. Thiếu vế đó thì một con số 0 chỉ nói rằng phép đo đã chết.
