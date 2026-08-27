# W6 — allocator tiền

> ⚠️ **Đây là ORACLE NGHIÊN CỨU DÙNG MỘT LẦN, không phải lõi production.**
>
> Mặc định nó sẽ **bị viết lại hoặc thẩm định lại** sau khi qua cổng 13.3. **Không có quyền tái sử dụng.** Đừng import nó từ code sản phẩm, đừng xây kiến trúc quanh nó, đừng thêm tính năng ngoài `ADR-0004`.

## Vì sao vẫn xây bây giờ

Phiên concierge chạm **nghĩa vụ tiền thật giữa participant**. Số học sai là `serious_error`, và guardrail của Giai đoạn 0 là **0 lỗi loại này** (spec mục 13.3). Đây cũng là phần duy nhất của sản phẩm mà tính đúng **tuyệt đối** — không phụ thuộc kết quả nghiên cứu.

## Cấu trúc

```
ADR-0004  (docs/decisions/)   hợp đồng đóng băng — nguồn sự thật duy nhất
golden/                       vector TÍNH TAY, chống "hai bản cùng sai"
impl_a/                       Codex — số nguyên thuần
impl_b/                       Claude — Fraction, ưu tiên rõ nghĩa
harness/                      Codex — generator, differential, shrinker
tests/                        property test + golden runner + self-check
```

## Quy tắc viết mù

Hai bản viết **độc lập, không đọc code của nhau**, và blindness được **cưỡng chế bằng cấu trúc nhánh**: mỗi bản chỉ tồn tại trên nhánh của người viết cho tới khi kết quả differential đã đóng băng.

Đọc code của nhau sớm không phải là gian lận nhỏ — nó **phá chính phép đo**. Toàn bộ giá trị của W6 nằm ở chỗ hai cách hiểu độc lập về cùng một hợp đồng có trùng nhau hay không.

## Về `golden/`

**Tính tay bởi con người, đối chiếu trực tiếp với ADR-0004.** Tuyệt đối **KHÔNG** được sinh lại từ bất kỳ hiện thực nào — làm vậy là biến golden vector thành ảnh chụp của một bug, và mất luôn lớp phòng thủ duy nhất chống "hai bản cùng hiểu sai một câu spec".

`tests/test_golden_selfcheck.py` kiểm tra **tính nhất quán nội tại** của bộ vector mà **không import allocator nào** — bắt lỗi số học của chính người viết vector trước khi có bất kỳ hiện thực nào tồn tại.

**Số tiền trong golden giữ dưới 10⁸ VND.** `LONG_NUMBER_RE` ở `scripts/repo_guard.py` chặn mọi chuỗi ≥9 chữ số, và JSON không có comment nên không gắn được annotation miễn trừ. Ca giá trị cực đại (`AMOUNT_TOO_LARGE`, gần cận trên) **sinh trong property test, không lưu thành literal**.

## Chạy

```bash
python3 -m pytest phase0/allocator/tests -q
```
