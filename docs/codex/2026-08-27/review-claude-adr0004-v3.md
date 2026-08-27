# Review ADR-0004 v3 — hợp đồng allocator

## Metadata

- **Worktree:** `/home/lakiet/mobile-codex`
- **Nhánh:** `codex/p0-w9a-repo-guard`
- **HEAD được review:** `41a63c7` (`merge: ADR-0004 v3`)
- **Reviewer:** Codex
- **Ngày:** 2026-08-27
- **Cách ly:** không đọc, import, quét hoặc chạy bất kỳ nội dung nào trong `phase0/allocator/impl_b/`
- **Verdict:** **`REQUEST_CHANGES`**
- **Blocker còn mở:** **2**

## Kết luận ngắn

V3 đã sửa đúng phần số học quan trọng nhất. Tôi chạy thật mutant G22 tự nhất quán: full self-check trả đỏ; khi bỏ đúng phép tái tính pipeline thì mutant đi qua. Vì vậy lõi của V2-05 đã đóng. V2-01, bảng reference của V2-02 và miền generator V2-04 cũng đã đi đúng hướng.

Nhưng chưa thể ký đóng băng. ADR vẫn chứa hai định nghĩa public boundary mâu thuẫn đúng tại điểm V2-03 cần xoá fork, và mutation gate tuyên bố tám mutant trong khi mã chỉ chạy bảy. Do verdict chưa phải `APPROVE`, tôi không tạo `impl_a/` hoặc `harness/`.

## Kết quả kiểm lại năm sửa V2

| Mục | Kết quả | Bằng chứng |
|---|---|---|
| **V2-01** | **PASS** | Quyết định #20 chỉ trỏ tới precedence chuẩn ở mục 6; không còn danh sách code thứ hai. Câu #16 đã ghi đúng: participant còn lại hoàn ít hơn 1đ, tổng allocation không giảm. |
| **V2-02** | **PASS trong miền value đã khai** | Bảng theo vị trí cho đúng bốn hệ quả: `shared_by=("",)` → `UNKNOWN_PARTICIPANT`; `advancer_id=""` → success + warning; `discount.item_id=""` → `UNKNOWN_ITEM`; `None` khác chuỗi rỗng. Phần shape/type ngoài miền vẫn cần được chốt cùng blocker V3-01 bên dưới. |
| **V2-03** | **FAIL** | Boundary mới nói `dict -> dict`, rational là chuỗi; schema public cũ ngay sau đó vẫn nói `ExpenseInput -> ApportionResult`, rational là `Fraction`. |
| **V2-04** | **PASS ở mức hợp đồng** | `len(discounts)=0…5`, item `0…3`, global `0…2`; cặp sát biên runtime được ghi bắt buộc. Bằng chứng runtime thuộc việc của harness sau khi ADR đóng băng. |
| **V2-05** | **PASS phần tái tính; FAIL tuyên bố mutation gate** | G22 tự nhất quán bị đúng pipeline recomputation bắt. Tuy nhiên README nói tám mutant, danh sách thực thi chỉ có bảy; mutant G11 hiện chưa tự nhất quán. |

## Blocker V3-01 — Public boundary vẫn có hai schema mâu thuẫn

### Bằng chứng

Trong cùng mục 1:

- dòng 26 khai public `allocate(expense: ExpenseInput) -> ApportionResult`;
- dòng 47 lại khai public `allocate(expense: dict) -> dict`;
- dòng 55 bắt `exact_shares: dict[str, str]`, rational chuẩn `"num/den"`;
- dòng 97 vẫn khai `exact_shares: dict[ParticipantId, Fraction]`;
- schema cũ còn dùng tuple cho collection/output, trong khi boundary golden dùng list.

Đoạn mới đúng và rõ hơn, nhưng đoạn cũ không được đánh dấu là mô hình khái niệm hay helper nội bộ. Nó vẫn nằm dưới “Hình dạng hợp đồng” và vẫn gọi entry point đó là public.

Boundary `dict` cũng chưa chốt hành vi với thiếu khoá hoặc sai wire type. Câu “khớp đúng khoá input của golden” có thể được hiểu là precondition, nhưng chưa nói vi phạm là `harness_bug` hay `AllocationError`. Đây là phần còn thiếu trong tiêu chí gỡ V2-02 trước đó.

### Hậu quả

Hai bản mù vẫn có thể viện dẫn hai đoạn khác nhau để trả object khác kiểu. Đó chính là fork V2-03: mapping equality đỏ dù số học giống nhau, hoặc harness phải viết adapter sau khi đọc hai bản. Với input shape sai, hai bản cũng có thể trả hai loại failure khác nhau mà không bản nào trái câu chữ hiện tại.

### Tiêu chí gỡ

1. Chỉ giữ một public signature `allocate(expense: dict) -> dict`.
2. Thay schema `ApportionResult` cũ bằng đúng boundary concrete (`str` rational, list có thứ tự), hoặc ghi rõ nó chỉ là mô hình toán học nội bộ và không phải object qua biên.
3. Chốt một câu cho thiếu khoá/sai type: hoặc nằm ngoài miền public và mọi ca như vậy là `harness_bug`, hoặc thêm error semantics. Không để hai bản tự chọn.

## Blocker V3-02 — Gate nói tám mutant nhưng chỉ chạy bảy

### Bằng chứng

- README dòng 42 ghi: “8 mutant, mỗi cái bắt buộc làm self-check đỏ”.
- AST của `MUTANTS` đếm được **7** entry: G02, G16, G21, G15, G25, G22, G11.
- Test thật vẫn báo `18 passed, 343 subtests passed`; con số test xanh không chứng minh có mutant thứ tám.

Tôi còn chạy ablation riêng:

| Probe | Return code |
|---|---:|
| G22 tự nhất quán, full self-check | `1` |
| G22 tự nhất quán, tắt riêng test tái tính pipeline | `0` |
| G11 hiện tại, tắt test tái tính pipeline | `1` |
| G11 sửa cho tự nhất quán bằng warning `zero_share_participants`, tắt pipeline | `0` |

G22 vì thế là bằng chứng tốt. G11 hiện tại chưa phải mutant tự nhất quán: chính docstring thừa nhận c có exact share 0 thì phải có warning, nhưng mutation không sửa warning. Nó vẫn đỏ khi bỏ pipeline vì warning-check bắt trước.

### Hậu quả

Không thể ký mệnh đề “tám mutant, tất cả đỏ” khi mutant thứ tám không tồn tại. Mutation cho quyết định #14 cũng chưa cô lập được phép tái tính exact share, nên bằng chứng yếu hơn chính chuẩn đã dùng để bác G22 ở vòng trước.

### Tiêu chí gỡ

1. Thêm mutant thứ tám thật sự và khóa `len(MUTANTS) == 8` trong test.
2. Làm G11 tự nhất quán: cùng exact/allocation/gainer sai phải có warning `zero_share_participants`; full self-check vẫn phải đỏ vì pipeline recomputation.
3. Chạy lại và ghi đúng số test/subtest.

## Đối chiếu số học độc lập

Tôi không dùng self-check làm oracle cho phép tính này.

Với G22:

1. Sau item discount: `(a,b,c) = (27000, 27000, 30000)`, `B=84000`.
2. Global discount 4000 cho hệ số `20/21`: `(180000/7, 180000/7, 200000/7)`.
3. Phụ phí proportional 9000: `(20250/7, 20250/7, 22500/7)`.
4. Phụ phí even 3000: thêm `1000` mỗi người.
5. Exact: `(207250/7, 207250/7, 229500/7)`. Floor sum là 91999; remainder của c là `5/7`, lớn hơn `1/7` của a/b, nên c nhận đồng dư. Golden hiện tại đúng.

G11 cũng đúng theo quyết định #14: 90000 chia cho a/b thành 45000 mỗi người; surcharge even 10000 chia cho cả ba, nên exact là `145000/3`, `145000/3`, `10000/3`. Advancer b chỉ thắng tie giữa a/b.

## Hai hiệu chỉnh số đếm không phải blocker riêng

- Corpus hiện có **23 success + 18 error = 41 vector**, không phải 18 success + 18 error. Khi có harness, phải chạy toàn bộ 41 vector hiện có.
- `contract.py` chỉ có constants và exception class, không có allocation logic. Tuy nhiên constructor của `AllocationError` vẫn có logic kiểm code; câu “không một dòng logic nào” nên đổi thành “không allocation/shared computation logic” để khớp file thật.

## Verdict cuối

**`REQUEST_CHANGES`. CHƯA ĐÓNG BĂNG ADR-0004 v3; không mở VIỆC 3 trong lượt này.**

Không cần đổi đường tính. Chỉ cần xoá dứt điểm schema public cũ, chốt precondition shape/type, và làm mutation gate khớp đúng tuyên bố tám mutant.
