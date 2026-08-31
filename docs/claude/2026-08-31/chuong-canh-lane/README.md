# Kiểm chuông cảnh lane — ba chiều, và bốn thứ rơi ra

- **task**: qa3-073401 · **ngày**: 2026-08-31 · **main**: `2f8a301`
- **skill**: `bug-reproduction`
- **vật đang kiểm**: vòng lặp `Monitor` của Lead, in ra `RỖI HẲN` / `KẸT READY` /
  `SẮP RỖI` / `ĐỢI HẠN MỨC`. Bản sao nguyên văn: `chuong_goc.sh`,
  sha256 `0287cd9bf5ac8899209b0bc242e3163b8c90b732521697931b32620317ed9e63`
- **chạy lại**: `./chay_ba_chieu.sh` (~15s) hoặc `./chay_ba_chieu.sh --cham` (~2,5 phút)

Chuông **kêu được**. Hai chiều đầu đạt, kể cả khi đo bằng đồng hồ thật. Chiều thứ
ba — im khi không nên kêu — **không đạt**, và trong lúc đo còn rơi ra một lỗ hổng
cùng họ với cái lỗ vừa được vá: chuông vẫn đọc sai hàng đợi, chỉ là qua một cửa khác.

## Cách đo

`chuong_goc.sh` là bản trích **nguyên văn** từ transcript phiên của Lead. Rig sửa
**đúng một dòng** — `R=` ở dòng 1 — để chuông đọc hộp cát thay vì harness thật;
`diff` được in ra đầu mỗi lần chạy. Tuổi trạng thái đặt bằng cách lùi `ts` trong
`state.json`, nên **đồng hồ vẫn là đồng hồ thật**: chuông vẫn gọi `datetime.now()`,
không có clock giả nào ở đây.

Mọi phán quyết "IM LẶNG" đều có **canary** đi kèm: cùng thư mục hộp cát, đổi đúng
một trường `state`, chuông phải kêu. Nếu rig trỏ sai chỗ thì canary cũng im — và
nó không im.

## Ba chiều

### Chiều 1 — READY lâu mà còn việc thì phải kêu: **ĐẠT**

Đo bằng đồng hồ thật, không phải bằng `ts` bịa sẵn: đặt lane ở `READY` tuổi 9,3
phút với `PEND=2` (trước mốc thì phải im **hẳn**), rồi để chuông chạy 150 giây.

```
07:56:07  (tuổi 9 phút)   — im
07:57:03  (tuổi 10 phút)  — KẸT READY: qa2 đứng yên 10 phút (từ 07:46:49),
                             hàng đợi còn 2 — lane KHÔNG nhận việc, kiểm ngay
số lần kêu trong 3 lượt: 1
```

Và nó cắn được **đúng ca đã xảy ra**. `state/events.jsonl` ghi qa2:
`2026-08-31T06:50:17 BUSY -> READY`, giữ **41,5 phút**, tới `07:31:47` mới `READY -> BUSY`.
Dựng lại đúng hình dạng đó (`C2`) → chuông kêu, báo 41 phút. Đối chứng âm ở 9 phút
(`C3`) → không có dòng `KẸT READY`. Mốc là mốc thật, không phải luôn-kêu.

### Chiều 2 — RATE_LIMITED thì không giục giao việc: **ĐẠT**

Đúng **một** dòng trong 3 lượt (150 giây), và dòng đó nói `KHÔNG giao thêm, việc
cũ vẫn giữ`. Không có `giao việc`, không có `nạp thêm`. Không phải im tuyệt đối,
nhưng đúng ý: nó báo trạng thái một lần rồi thôi.

*Kèm một khoảng mù*: `case ... continue` nhảy qua **mọi** phép kiểm tuổi. Lane nằm
`RATE_LIMITED` 40 phút (`C4c`) nhận đúng một dòng giống hệt lane vừa vào 1 phút.
Lane kẹt `RATE_LIMITED` vĩnh viễn thì không bao giờ có tiếng thứ hai.

### Chiều 3 — BUSY bình thường thì không được kêu: **KHÔNG ĐẠT khi `PEND ≤ 1`**

| BUSY, số việc chuông đếm được | chuông |
|---|---|
| 2 trở lên | im ✔ |
| 1 | `SẮP RỖI: qa2 còn 1 việc (state=BUSY) — nạp thêm trước khi nó xong` ✘ |
| 0 | `SẮP RỖI: qa2 còn 0 việc (state=BUSY)` ✘ |

Không phải giả thuyết. Chạy `chuong_goc.sh` **y nguyên** trên state thật lúc 07:58:

```
ĐỢI HẠN MỨC: frontend (RATE_LIMITED từ 07:44:50) — KHÔNG giao thêm, việc cũ vẫn giữ
ĐỢI HẠN MỨC: qa (RATE_LIMITED từ 07:44:50) — KHÔNG giao thêm, việc cũ vẫn giữ
SẮP RỖI: qa2 còn 1 việc (state=BUSY) — nạp thêm trước khi nó xong
```

qa2 lúc đó `BUSY` và khoẻ. Nhánh `SẮP RỖI` rõ ràng là **cố ý** ("nạp thêm trước khi
nó xong"), nên đây là câu hỏi thiết kế chứ không phải bug ẩn: nhánh thứ tư đó không
lọc theo `state`, nên nó nói chen vào giữa một lane đang chạy bình thường. Quyết định
là của Lead — hoặc chấp nhận, hoặc thêm `[ "$ST" = "READY" ]` vào điều kiện.

## Bốn thứ rơi ra khi đo

### 1. `PEND` không phải hàng đợi — và đây là **cùng một lỗ** vừa được vá

`PEND` = số `task_id` trong event có type chứa `ASSIGN`, trừ đi số file `*.done`.
`bug-to` phát `BUG_FILED`, không phải `ASSIGNED`. Việc từ `backlog/*.jsonl` và việc
thường trực không phát event nào.

Nên một lane **đang giữ 3 lỗi P0 chưa nhận** mà nằm `READY` 3 phút (`C7`):

```
RỖI HẲN: qa2 READY từ 07:58:56, hàng đợi TRỐNG — giao việc ngay
```

Chuông nói ngược sự thật, và lời khuyên kèm theo là chất thêm việc lên lane đang ôm
ba lỗi khẩn. Cùng lane đó ở 11 phút (`C6`) thì kêu `KẸT READY` đúng, nhưng kèm
`hàng đợi còn 0` — con số làm cho cảnh báo đáng tin lại đọc là *không có gì*, mời
người đọc bỏ qua.

Lỗ vừa vá là "chỉ báo khi hàng đợi TRỐNG". Lỗ này là "chuông không biết hàng đợi
có gì". Cùng họ, khác cửa.

### 2. `PEND` phồng lên vì việc chết — sai ở **cả sáu** lane

Việc đã giao nhưng không bao giờ có marker (hỏng, bị hoãn, bỏ) nằm lại trong `PEND`
mãi mãi. Đo lúc 07:52:

| lane | `PEND` chuông đếm | inbox thật |
|---|---|---|
| devops | 6 | 0 |
| backend | 2 | 1 |
| frontend | 5 | 2 |
| qa | 12 | 1 |
| qa2 | 1 | 0 |
| qa3 | 2 | 1 |

Hậu quả: nhánh `RỖI HẲN` — tín hiệu **nhanh** để giao việc — gần như chết với mọi
lane có lịch sử. devops inbox rỗng thật mà `PEND=6`, nên nếu nó vào `READY` thì
9 phút đầu chuông im, phải chờ đủ 10 phút mới có `KẸT READY`.

### 3. `state.json` đọc dở thì kêu nhầm

Ghi dở / JSON hỏng → `ST` rỗng → rơi xuống nhánh cuối. Với `PEND=1`:
`SẮP RỖI: qa2 còn 1 việc (state=) — nạp thêm`. Với `PEND=5` thì im. Lane **chưa
từng** ghi `state.json` bị `[ -f ] || continue` bỏ qua, không một tiếng nào.

### 4. Chuông chỉ tồn tại trong transcript

Nó là một lệnh `Monitor` trong phiên của Lead, không phải file, không trong git,
không có test. Hết phiên là mất, và không có hiện vật nào để bật lại. Tôi phải dựng
lại nó từ `~/.claude/projects/.../58ad195b-*.jsonl` mới kiểm được — đó là lý do
`chuong_goc.sh` nằm ở đây kèm sha256.

Đang chạy đúng **một** bản, pid `1986799`, khởi động `07:32:08` hôm nay, và nó **có**
`KẸT READY` (tức bản đã vá). Tiến trình dài kia (`3956438`, từ 30/08 19:01) là bộ
canh PR, không liên quan.

## Kết

Chuông kêu được ở chiều nó được dựng ra để kêu, và kêu đúng ca 41,5 phút đã thật sự
xảy ra sáng nay. Lead không điều phối mù.

Nhưng nó vẫn đang đọc một con số hàng đợi sai ở cả sáu lane, và với việc nộp qua
`bug-to` hoặc `backlog` thì nó nói "hàng đợi TRỐNG" trong khi hàng đợi không trống.
Sửa `PEND` (đếm file trong `mailbox/<lane>/inbox/P*.json` — đúng cái `lane.py` đọc)
rẻ hơn nhiều so với hậu quả của một dòng "giao việc ngay" sai lúc.
