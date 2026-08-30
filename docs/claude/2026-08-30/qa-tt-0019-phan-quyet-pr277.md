# PASS — #277 (cổng luật tiền 1 ở thân trả lời)

**Lý do, viết trước phần chi tiết.** Cổng mới cắn thật và cắn đúng tính chất, không
phải cắn mọi thay đổi. Tôi đặt nguyên file cổng lên code **trước** PR: **46 failed /
121 passed**. Trên code sau PR: **167 passed**. Bảng đột biến độc lập của tôi có đủ
ba loại hàng và cả năm hàng ra đúng màu đã dự đoán, gồm hai hàng *giữ nguyên tính
chất* ra XANH — nên dấu xanh của cổng này phân biệt được "luật còn đúng" với "chưa
ai đụng vào dòng đó". Không có con số tiền nào đang sai được bản vá này sửa, và PR
nói đúng điều đó chứ không khai to hơn.

**Một phát hiện kèm theo, không phải blocker:** phép đi bộ tìm trường tiền **theo
tên** (`MONEY_SUFFIX = "_vnd"` + hai dict ghim tên). Tôi thêm một trường tiền lax
tên `refund_amount` (không hậu tố `_vnd`) vào `PersonFinanceResponse` — cổng ra
**167 passed, exit 0**. Đây là lỗ **ngủ**, không phải lỗ sống: tôi quét toàn bộ 68
model đạt tới từ `response_model` và **0/56 trường còn lax mang tên tiền**. Nhưng
tiêu đề file cổng viết "no money field on a response launders a non-int" — đó là
câu về *ý định*, rộng hơn phạm vi phép đi bộ thật sự chạm tới.

---

## Đo tại đâu

```
đo tại    a337a48   (main)
sha này   ĐÃ ở main — #277 được squash-merge lúc 2026-08-30T03:31:51Z
đối chứng fb44dd4   (main NGAY TRƯỚC #277)
head PR   ee1618a   (bản tôi bắt đầu đo; nội dung khớp bản đã merge)
```

**#277 đã merge trước khi tôi ra phán quyết** — mở 03:24:56Z, merge 03:31:51Z, khoảng
7 phút. Nên đây là **kiểm chứng sau merge**, không phải cổng chặn merge. Tôi ghi rõ
vì Lead đang theo dõi đúng loại tình huống này; lần này nó **không** phạm ràng buộc
Lead tự đặt — #277 *thêm* một máy đo chứ không làm giảm finding của máy đo nào.

## Cổng đã chạy — số thật

| lệnh | kết quả |
|---|---|
| `pytest services/api/tests tests -q` @ `fb44dd4` (trước #277) | **1677 passed**, 366 skipped, 4736 subtests |
| `pytest services/api/tests tests -q` @ `a337a48` (sau #277) | **1844 passed**, 366 skipped, 4736 subtests |
| **có Postgres thật** `MOBILE_REQUIRE_POSTGRES_TESTS=1` @ `a337a48` | **2175 passed, 35 skipped**, 0 failed |
| `cd apps/mobile && npm test` @ `a337a48` | **674 pass, 0 fail**, 0 skipped |
| migration render ra DDL (không cần DB) | rc=0 |

`1844 − 1677 = 167`, đúng bằng số ca cổng mới thêm vào. PR khai nền của họ là 1678;
nền của tôi là 1677. Lệch 1 ca, không đổi kết luận.

**Tầng Postgres:** chạy trên DB riêng `qa19` (`alembic upgrade head` từ đầu), không
stamp lại DB chung. Skip rớt **366 → 35**; 35 ca còn lại là tầng Gemini live (cần
`MOBILE_REQUIRE_GEMINI_TESTS=1`) và một ca cần `apps/mobile/node_modules`. Theo ghi
chép của tôi CI chưa từng chạy tầng này, nên **đây là lượt duy nhất nó thật sự chạy**.

## Đỏ-trước / xanh-sau

Đặt **nguyên file cổng của PR** lên cây `fb44dd4` (code trước PR), không sửa gì khác:

```
46 failed, 121 passed in 0.26s      <- code CŨ + cổng MỚI
167 passed in 0.19s                 <- code MỚI + cổng MỚI
```

45 ca = 15 trường × 3 hình dạng bị từ chối, cộng
`test_a_float_spend_is_refused_by_the_real_response_model`. Khớp con số PR khai.

## Bảng đột biến độc lập

Chạy lại được: `python3 tests/qa/qa-tt-0019/dot-bien-cong-tien-ra.py` (cây sạch, tự
khôi phục `schemas.py`, từ chối chạy nếu neo không duy nhất).

| # | đột biến | loại | kỳ vọng | kết quả |
|---|---|---|---|---|
| A | `MoneyVnd` mất `strict` — 15 trường cùng phụ thuộc một dòng | phá tính chất | ĐỎ | **91 failed**, 76 passed |
| B | trường tiền **thứ N+1** `refund_vnd: int` (tên đúng quy ước) | phá tính chất | ĐỎ | **3 failed**, 168 passed |
| C | trường tiền **thứ N+1** `refund_amount: int` (tên ngoài quy ước) | ngoài phạm vi | — | **167 passed** ← mù |
| D | viết `strict` inline thay vì dùng alias | giữ tính chất | XANH | 167 passed |
| E | đổi **hằng số** `NonNegativeMoneyVnd` `ge=0`→`ge=-1`, giữ `strict` | giữ tính chất | XANH | 167 passed |

Hàng **B** là hàng tác giả chưa chạy và là hàng tôi quan tâm nhất: nó hỏi "cổng có
gác được trường tiền *sẽ được thêm sau này* không, hay chỉ ghim 15 trường hôm nay".
Nó **đạt**.

Hàng **E** là hàng khiến cả bảng đọc được. Nó giữ nguyên tính chất đang được gác và
chỉ đổi một hằng số phụ. Cổng xanh ở đó, nên hàng A/B đỏ vì **tính chất bị phá**,
không phải vì "có người sửa file".

## Phát hiện: phép đi bộ tìm tiền theo TÊN

**Dẫn chứng.** Hàng C ở trên: `refund_amount: int` lax trên `PersonFinanceResponse`
→ `167 passed`, exit 0. Cùng vi phạm, viết bằng tên `refund_vnd` → 3 failed.

**Phạm vi thật, đo được:**

```
68  model đạt tới từ mọi response_model
56  trường còn nhận 82000.0 (lax)
 0  trong 56 trường đó mang tên tiền (_vnd / allocations / expected_allocations)
```

56 trường lax còn lại là timestamp, đếm số, `lat`/`lng`, `rating`, `distance_km`,
`width`/`height` — không cái nào là tiền. **Nên hôm nay không có con số tiền nào
đang sai.**

Tôi cũng kiểm 9 route **không khai `response_model`** (phép đi bộ bỏ qua hẳn):
`/g/{token}*` là HTML trang khách, `/photos/{id}` và `/avatar` là ảnh nhị phân,
`DELETE /members/{id}` là 204. **Không route nào chở tiền JSON** — chỗ mù này không
sống.

**Vì sao vẫn đáng ghi.** Cổng chiều VÀO (#273, đã trên main) dùng **cùng một**
`MONEY_SUFFIX`. Nên đây là chỗ mù **dùng chung của cả hai chiều**, có sẵn từ trước
#277 chứ không phải do #277 gây ra — #277 kế thừa nó. Và nó đúng khuôn Lead vừa nêu:
phép kiểm phụ thuộc vào việc người viết sau **nhớ đặt tên đúng quy ước**, nên trường
thứ N+1 đặt tên khác sẽ lọt, im lặng, với một dấu xanh.

**Phân loại:** suggestion, không phải blocker. Không thuộc 5 loại blocker của
charter — không sai tiền hôm nay, không vi phạm spec, tái lập được, không hỏng tính
hợp lệ thí nghiệm.

**Tiêu chí gỡ nếu ai muốn đóng:** cổng khai `int`/`int | None` trần trên response
model là **lỗi mặc định**, phải ghi tên vào một allowlist "đây không phải tiền" —
đảo chiều mặc định từ *chọn vào theo tên* sang *chọn ra theo chủ ý*. Lúc đó trường
thứ N+1 lọt chỉ khi có người **cố tình** viết tên nó vào allowlist.

## Ô CHƯA quét

- **Mã QR VietQR quét bằng app ngân hàng thật** — chưa, và không agent nào làm được.
  Cần leader, 15 phút, một điện thoại thật. Câu này còn nguyên.
- **Trang khách bằng mắt** (ma trận trạng thái × sáng/tối × 320/390/1440) — lượt này
  không quét; #277 không chạm `app/web/`.
- **Tầng Gemini live** — 35 ca còn skip, cần `MOBILE_REQUIRE_GEMINI_TESTS=1`.
- **`npm run test:e2e`** — không chạy lượt này; #277 chỉ đổi kiểu khai trên schema và
  đã được phủ bởi 2175 ca có driver Postgres thật.
- **Hành vi người thật** — ADR-0006 vẫn gác Giai đoạn 0. Bộ test xanh nói code làm
  đúng điều tác giả nghĩ; nó không nói người thật hiểu sản phẩm.

## Ghi chú vệ sinh cây

Worktree QA còn một file **untracked không thuộc nhánh nào**:
`tests/qa/rd-qa-36/di-bo-ban-be.py`, sót lại từ lượt rd-qa-36 (PR #200, đã CLOSED).
Nó làm `test_qa_scripts_are_ruff_formatted` **đỏ trong cây bẩn** vì cổng đó `rglob`
trên hệ thống file chứ không trên cây git. Trên `main` sạch cổng này xanh — tôi đã
đối chứng ở cả hai cây. Fail-closed là đúng hướng; tôi ghi lại để dấu đỏ đó không bị
ai đọc thành sự cố của main.

---

protocol_version: v1 · verdict: **PASS** · blocker còn mở: **không** ·
suggestion: 1 (phép đi bộ tìm tiền theo tên, dùng chung với #273)
