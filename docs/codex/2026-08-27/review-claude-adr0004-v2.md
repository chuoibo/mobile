# Review ADR-0004 v2 — hợp đồng allocator

## Metadata

- **Merge SHA được review:** `fb7d89d6b65f9a40453d0330b0f31c72f9759c94`
- **Commit sửa năm blocker:** `5cfafbef511626217d0b9d735e84cce8c958e136`
- **Phạm vi:** ADR-0004 v2, `phase0/allocator/README.md`, 41 golden vector và hai bộ self-check/mutation test.
- **Cách ly:** không đọc hoặc quét nội dung `phase0/allocator/impl_b/`; không có code allocator nào được dùng làm oracle.
- **Kiểm chứng hiện trạng:** `17 passed, 319 subtests passed`.
- **Verdict:** **`REQUEST_CHANGES`**
- **Blocker còn mở:** **5**

## Kết luận ngắn

ADR v2 đã sửa đúng phần lớn năm blocker cũ. Đặc biệt, public entry point duy nhất, helper precondition, mapping/tuple equality, error vocabulary mới, comparator byte, success/error property, exact gainer tuple và warning iff đều đi đúng hướng. ADR4-04 về largest remainder được **đóng hoàn toàn**.

Nhưng bản hiện tại **chưa đóng băng được**. Có một precedence tự mâu thuẫn ngay trong ADR, hai vùng ID reference chưa được gán validation semantics, black-box API chưa có biểu diễn chung mà hai bản mù có thể cùng tuân theo, miền generator vẫn thiếu cận cho discount, và mutation gate mới vẫn cho qua một mutant composition sai nhưng tự nhất quán.

Vì vậy **không mở W6a/W6b trong lượt này**. Tôi không tạo `impl_a/` hoặc `harness/`.

## Blocker V2-01 — ADR có hai “thứ tự đầy đủ” khác nhau

- **Dẫn chứng:** mục quyết định #20, dòng 155–159, vẫn giữ danh sách cũ chỉ có 12 code. Mục 6, dòng 242–255, lại tuyên bố một danh sách đóng và đầy đủ gồm 19 code với vị trí mới.
- **Phản ví dụ:** `participants=(" a", " a")`, các collection rỗng, `total_vnd=0`. Theo danh sách cũ, lỗi đầu là `DUPLICATE_PARTICIPANT`; theo mục 6, lỗi đầu là `INVALID_PARTICIPANT_ID`.
- **Hậu quả:** hai hiện thực đều có thể viện dẫn đúng một đoạn mang nhãn “đầy đủ” nhưng trả code khác nhau. Differential không thể phân loại đây là bug của bản nào.
- **Tiêu chí gỡ:** chỉ giữ **một** hằng precedence chuẩn trong ADR; mục #20 phải trỏ tới nó thay vì lặp danh sách. Thêm ca tổ hợp trên vào invalid generator.

Cùng dấu hiệu merge sót đó, quyết định #16 ở dòng 149 vẫn viết “cả nhóm nợ ít đi”. Sửa cơ học thành “những participant còn lại phải hoàn ít hơn 1đ”, đúng như đã thống nhất; tổng allocation không giảm.

## Blocker V2-02 — Chưa chốt ID validation áp vào những vị trí nào

- **Dẫn chứng:** `ParticipantId` được dùng ở `participants`, `item.shared_by` và `advancer_id`, nhưng `INVALID_PARTICIPANT_ID` không nói nó kiểm cả ba vị trí hay chỉ ID khai báo trong `participants`. Tương tự, `INVALID_ENTITY_ID` không nói có áp vào `discount.item_id` là một reference hay chỉ các ID khai báo entity.
- **Hai fork cụ thể:**
  - `participants=("a",)`, một item có `shared_by=("",)` có thể là `INVALID_PARTICIPANT_ID` hoặc `UNKNOWN_PARTICIPANT`;
  - `participants=("a",)`, `EVEN_SPLIT`, `advancer_id=""` có thể là `INVALID_PARTICIPANT_ID` hoặc success kèm `advancer_not_participant`.
- **Khoảng trống liên quan:** entity ID có whitespace đầu/cuối hiện chưa được tuyên bố là hợp lệ hay `INVALID_ENTITY_ID`; target `discount.item_id=""` có thể là `INVALID_ENTITY_ID` hoặc `UNKNOWN_ITEM`.
- **Hậu quả:** invalid generator không thể tạo “đúng một lỗi mục tiêu”, và các cặp precedence `INVALID_*`/`UNKNOWN_*` vẫn không phải hàm toàn phần.
- **Tiêu chí gỡ:** thêm một bảng theo **field occurrence**: predicate hợp lệ, owner validation và error code. Bảng phải phủ `participants[*]`, `shared_by[*]`, `advancer_id`, ba declaration ID và `discount.item_id`; chốt luôn whitespace semantics. Nếu malformed wire type/missing field được constructor bên ngoài chặn, ghi rõ đó là precondition/harness bug chứ không phải `AllocationError`.

## Blocker V2-03 — Black-box API chưa có biểu diễn liên vận hành

- **Dẫn chứng:** ADR ghi `ExpenseInput`/`ApportionResult` như kiểu khái niệm, trong khi golden là JSON mapping/list. Chưa có module/type chung nói harness truyền dataclass, mapping hay JSON. Quan trọng hơn, `exact_shares` được khai là `Fraction`, nhưng yêu cầu của `impl_a` là số nguyên thuần, **không `Fraction`**.
- **Fork cụ thể:** impl A có thể trả cặp `(numerator, denominator)` hoặc chuỗi `"num/den"`; impl B có thể trả `fractions.Fraction`. Câu “serialize tối giản” chỉ chốt phép so sau chuẩn hoá, chưa chốt object public hay adapter nào chịu trách nhiệm chuẩn hoá. Mapping equality trực tiếp giữa các dạng này sẽ đỏ dù số học giống nhau.
- **Hậu quả:** harness không thể import và gọi hai bản mù qua cùng một giao diện mà không đọc code rồi viết adapter theo từng bản. Làm vậy sau merge sẽ phá ý nghĩa “differential đã đóng băng”.
- **Tiêu chí gỡ:** trước khi viết hai bản, đóng băng một boundary trung lập: module path và signature, concrete input type, concrete result/error type, và canonical rational representation. Một phương án phù hợp ràng buộc là output rational bằng record hai số nguyên đã tối giản hoặc chuỗi `num/den`; `impl_b` được dùng `Fraction` nội bộ nhưng không để type riêng rò qua boundary.

## Blocker V2-04 — Hợp đồng generator vẫn thiếu một miền hữu hạn

- **Dẫn chứng:** mục 5.1 chốt `items=0…40` và `surcharges=0…5`, nhưng không chốt `len(discounts)` hoặc cận riêng cho item/global discounts. Bản cũ từng có cận này; v2 đã làm mất nó. Tiêu chí gỡ ADR4-03 yêu cầu range cho mọi field.
- **Khoảng coverage:** danh sách bắt buộc chỉ ghi “biên `10¹²`”, chưa buộc cặp sát biên `10¹²` hợp lệ và `10¹² + 1` trả `AMOUNT_TOO_LARGE` ở runtime.
- **Hậu quả:** hai harness hợp lý có thể dùng miền và tần suất discount rất khác nhau; replay theo seed không còn mô tả cùng thí nghiệm, và bug off-by-one ở cận trên có thể không bị ép xuất hiện.
- **Tiêu chí gỡ:** chốt cận số discount, cách chia giữa hai scope, và lịch deterministic cho các ca bắt buộc. Thêm cặp sát biên hợp lệ/không hợp lệ sinh runtime, không lưu literal vào golden nếu repo guard cấm.

## Blocker V2-05 — Mutant G22 chưa chứng minh self-check bắt lỗi composition

`test_selfcheck_catches_mutants.py` gọi mutant G22 là “applying the global discount before the item discount”. Nhưng mutant hiện tại chỉ sửa hai exact share không bảo toàn tổng; nó bị `test_exact_shares_sum_to_total` bắt trước khi kiểm được thứ tự composition.

Tôi thay G22 trong một corpus tạm bằng một mutant **sai nhưng tự nhất quán**: áp global discount trước item discount, rồi tính lại toàn bộ expected:

```text
exact:       a=177325/6, b=177325/6, c=98675/3
allocations: a=29554,    b=29554,    c=32892
gainers:     (c,)
warnings:    ()
```

Mutant này giữ đúng tổng exact, tổng allocation, floor-plus-gainer, exact ranking, warning và reconciliation. Kết quả thực chạy self-check: **return code 0; `15 passed, 313 subtests passed`**.

- **Hậu quả:** nếu người tính tay cũng đảo hai tầng một cách nhất quán, cổng được tuyên bố bảo vệ golden khỏi arithmetic slip vẫn xanh. Mutant G22 hiện chỉ chứng minh conservation check có răng, không chứng minh composition order có răng.
- **Tiêu chí gỡ:** self-check độc lập phải tính lại exact shares từ input theo năm tầng rồi so mapping rational chuẩn; mutant composition phải thay **toàn bộ** expected một cách nhất quán và vẫn bị đỏ. Nếu không muốn self-check trở thành oracle thứ ba, phải hạ đúng tuyên bố phạm vi của nó và thay cổng bằng một artifact tái tính độc lập có reviewer ký; không được tiếp tục gọi mutant hiện tại là bằng chứng bắt composition.

## Những gì đã đạt

- 19 error code mới phủ các vi phạm vật chất mà ADR v1 bỏ trống; ba namespace ID tách biệt và không normalize Unicode là quyết định đúng.
- Một public `allocate(expense)` và helper nội bộ đã đóng lỗ warning/precondition của ADR4-02 ở mức ngữ nghĩa.
- Valid generator xây theo quan hệ và suy ra total; invalid generator có target/precedence lane riêng.
- Property 6–7 khóa đúng largest-remainder allocation và exact ordered gainer tuple; phản ví dụ `9/10` so với `1/10` không còn lọt.
- Self-check mới thật sự khóa byte comparator, advancer tie-break, warning iff và các warning đôi. Ba mutant G02/G16/G21 cũ đều bị bắt.
- 41 golden vector hiện tại qua toàn bộ self-check; không có bằng chứng expected hiện tại sai.

## Verdict cuối

**`REQUEST_CHANGES`. CHƯA ĐÓNG BĂNG ADR-0004 v2; chưa viết `impl_a` hoặc harness.**

Không cần đổi hướng số học. V2-01 và câu #16 là sửa merge cơ học; V2-02/V2-03 cần đóng boundary chính xác; V2-04 là một cận generator còn thiếu; V2-05 cần biến mutation claim thành một phép thử thật. Sau năm sửa này mới có thể nói **ĐÓNG BĂNG ĐƯỢC** mà không dựa vào lựa chọn ngầm của người viết harness.
