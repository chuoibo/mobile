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

**Tính tay bởi con người, đối chiếu trực tiếp với ADR-0004.** Tuyệt đối **KHÔNG** được sinh lại từ bất kỳ hiện thực nào — làm vậy là biến golden vector thành ảnh chụp của một bug.

### Ba lớp, ba tuyên bố khác nhau. Không lớp nào một mình là cổng.

| Lớp | Bắt được gì | **KHÔNG** bắt được gì |
|---|---|---|
| `test_golden_selfcheck.py` | Sai số học và mâu thuẫn nội tại của bộ vector. Tính lại exact shares, thứ hạng làm tròn và tập warning từ input | **Việc đọc sai hợp đồng.** File này và bộ vector **cùng một tác giả** — một cách hiểu sai nhất quán sẽ xuất hiện giống nhau ở cả hai và vẫn xanh |
| Tính tay độc lập của reviewer | Đọc sai hợp đồng | Bug hiện thực |
| Differential `impl_a` ↔ `impl_b` | Bug hiện thực | **Hai bản cùng hiểu sai một câu.** Đó là việc của hai lớp trên |

> Tuyên bố này đã bị hạ hai lần dưới review. Bản đầu nói golden vector là "lớp phòng thủ chống hai bản cùng sai" — Codex chứng minh nó cho qua mutant chuyển 1đ sang sai người (`ADR4-05`), rồi chứng minh **lần thứ hai** rằng nó cho qua mutant đảo thứ tự hợp thành một cách tự nhất quán (`V2-05`).

`tests/test_selfcheck_catches_mutants.py` giữ cho lớp thứ nhất **không mất răng lần nữa**: 8 mutant, mỗi cái **bắt buộc** làm self-check đỏ. Một bộ test không thể thất bại thì không phải một cổng.

**Số tiền trong golden giữ dưới 10⁸ VND.** `LONG_NUMBER_RE` ở `scripts/repo_guard.py` chặn mọi chuỗi ≥9 chữ số, và JSON không có comment nên không gắn được annotation miễn trừ. Ca giá trị cực đại (`AMOUNT_TOO_LARGE`, gần cận trên) **sinh trong property test, không lưu thành literal**.

## Chạy

```bash
python3 -m pytest phase0/allocator/tests -q
```
