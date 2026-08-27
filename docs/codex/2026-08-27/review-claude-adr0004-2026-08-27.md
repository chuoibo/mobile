# Review ADR-0004 — hợp đồng allocator của Claude

## Metadata

- **Merge SHA được review:** `50a8491b1fca02e5743c89b589f5a6b718d4dc99`
- **ADR gốc:** `36fa45e716aa586454b29a70a4ae5645c6a4cd7f`
- **Golden + self-check:** `bc08897ab5f1fa03cf984099d1738094ac83d582`
- **Nguồn đối chiếu:** spec mục 4; ADR-0004; `phase0/allocator/README.md`; toàn bộ năm file golden; `test_golden_selfcheck.py`; backlog W6
- **Verdict:** **`REQUEST_CHANGES`**
- **Blocker còn mở:** **5**
- **Ranh giới review:** chưa có và tôi không viết/đọc code allocator. Tôi tính lại các vector từ hợp đồng, không sinh expected output từ một hiện thực.

## Kết luận ngắn

Hướng số học đúng và đã tiến rất gần một hợp đồng đóng băng được. Tôi tính lại bằng tay toàn bộ **18 vector thành công**, kiểm tra ý nghĩa của **11 vector lỗi**, và không tìm thấy sai số học trong 29 expected output hiện tại. `pytest` cho self-check cũng xanh: **12 test, 220 subtest**.

Tôi đồng ý với bốn quyết định được hỏi trực tiếp:

- **#16: THÊM 1đ.** Trong phương pháp phần dư lớn nhất, người “thắng” là người nhận đơn vị dư. Vì allocation là phần người đó chịu, advancer chịu thêm 1đ và những người còn lại phải hoàn ít hơn 1đ. Đây là cách đọc thuật toán rõ hơn cách đọc “thắng = được lợi”.
- **#17: byte UTF-8.** G16 đúng: byte của `z` đứng trước byte của `á`. Không dùng input order hay collation ngôn ngữ.
- **#1: từ chối, không co giãn.** Ca thật thiếu dòng có thể biểu diễn bằng surcharge/discount tường minh; ca không có chi tiết dùng `EVEN_SPLIT`. Co giãn ngầm sẽ làm expected output không còn truy nguyên được.
- **#3: phần 0 hợp lệ.** Đây không tự mở bug bỏ sót nếu output bắt buộc giữ đủ key participant và consumer không lọc dòng 0đ. Warning là đúng; cần siết thêm invariant output bên dưới.

Nhưng **chưa được đóng băng**. Các khoảng im lặng còn lại không phải chuyện đặt tên: hai hiện thực hợp lý vẫn có thể trả code khác nhau, nhận input khác nhau, hoặc cùng vượt qua chín invariant dù phân bổ sai largest remainder.

## Blocker ADR4-01 — Miền dữ liệu và thứ tự lỗi chưa là một hàm toàn phần

- **Loại:** contract/spec ambiguity; reproducibility.
- **Dẫn chứng:** kiểu dữ liệu ở ADR dòng 40–62 cấm participant rỗng/bao whitespace, cấm `shared_by` trùng, yêu cầu amount của item/surcharge/discount `> 0`, và yêu cầu `discount.item_id` đúng khi-và-chỉ-khi scope là `item`. Nhưng danh sách lỗi và thứ tự ở dòng 144–148, 201–207 không gán hành vi cho các vi phạm này.
- **Các ca hiện vẫn im lặng:**
  - item/surcharge/discount có `amount_vnd = 0`;
  - participant ID rỗng hoặc có whitespace đầu/cuối;
  - `shared_by` chứa cùng participant hai lần;
  - `item_id`, `surcharge_id`, `discount_id` rỗng, trùng hoặc không encode UTF-8 được;
  - hai item trùng `item_id`, khiến một item discount có thể bị áp vào một, cả hai, hoặc item bị map ghi đè;
  - scope `item` nhưng `item_id = None`, hoặc scope global nhưng lại mang `item_id`;
  - `kind` rỗng hoặc không phải chuỗi hợp lệ.
- **Vì sao #20 chưa cứu được:** với đúng 12 code đã liệt kê và ID hợp lệ/duy nhất, thứ tự code hiện tại là tất định. Nhưng “sort theo ID” không phá được tie giữa hai entity trùng ID, và không nói code nào dành cho các vi phạm chưa có tên. Hai bản có thể hợp lý khi một bản coi amount 0 là no-op còn bản kia từ chối.
- **Hậu quả:** differential failure sẽ không phân loại được là `impl_bug` hay `generator_out_of_domain`; tệ hơn, duplicate item ID có thể làm đổi nghĩa vụ tiền chứ không chỉ đổi error message.
- **Tiêu chí gỡ:** chọn rõ một trong hai cách cho **từng** ca trên: (a) precondition đã được typed constructor bên ngoài bảo đảm và tuyệt đối không đi vào allocator/harness, hoặc (b) thêm error code đóng cùng vị trí chính xác trong precedence. Chốt uniqueness namespace cho ba loại entity ID; equality/normalization của participant ID; so sánh byte là lexicographic trên byte không dấu, prefix ngắn hơn đứng trước; và giới hạn độ dài ID hữu hạn cho generator. Thêm vector lỗi/permutation cho các ca được allocator nhận trách nhiệm.

## Blocker ADR4-02 — Black-box API đang làm mất warning và chưa định nghĩa failure của `apportion`

- **Loại:** contract ambiguity; reproducibility.
- **Dẫn chứng:** ADR dòng 25–32 khai hai hàm. `compute_exact_shares` chỉ trả dict; `apportion` chỉ nhận `total_vnd`, `exact`, `advancer_id` nhưng lại phải trả `ApportionResult` có `warnings`. Warning `proportional_fallback_to_even` chỉ biết được ở tầng phụ phí; thông tin này không còn trong bất kỳ đối số nào của `apportion`.
- **Khoảng im lặng thứ hai:** dòng 162 nói `Σ exact_i == total_vnd` phải “kiểm tra, không giả định”, nhưng danh sách `AllocationError` không có code cho việc vi phạm tiền đề. Cũng chưa chốt `exact` phải có đúng key participant, không âm, hay `apportion` chỉ là hàm nội bộ không bao giờ được fuzz trực tiếp.
- **Hậu quả:** impl A có thể đặt warning ở wrapper riêng, impl B trả từ `compute_exact_shares`, trong khi harness không có một entry point thống nhất để so. Với input sai tiền đề, một bản assert, một bản trả error, một bản vẫn làm tròn — cả ba đều chưa trái câu chữ hiện tại.
- **Tiêu chí gỡ:** đóng băng **một public entry point**, đề xuất `allocate(expense: ExpenseInput) -> ApportionResult`. Hai tầng có thể là helper nội bộ; nếu vẫn public thì `compute_exact_shares` phải trả cả computation warnings hoặc `apportion` phải nhận chúng. Ghi rõ precondition của helper và vi phạm được phân loại là `harness_bug`/assertion hay `AllocationError` nào. Chốt equality để differential so sánh: dict là mapping không xét insertion order; tuple có xét order; Fraction serialize dạng tối giản `numerator/denominator`; lỗi so bằng `code`.

## Blocker ADR4-03 — Mục 5 chưa đủ để viết generator hợp lệ

- **Loại:** generator_out_of_domain risk; experiment reproducibility.
- **Dẫn chứng:** bảng dòng 184–194 chỉ có range cho số lượng, participant ID, total, item amount/shared count và advancer. Nó chưa có miền cho entity ID, surcharge/discount amount, `mode`, `scope`, `kind`, target item, hoặc các ràng buộc liên trường.
- **Ràng buộc thành công còn thiếu:** participant/entity ID duy nhất; `shared_by ⊆ participants` và không trùng; discount target tồn tại; tổng item discount trên từng item không vượt item; global discount không vượt `B`; `listed_vnd == total_vnd` trừ đúng ca `EVEN_SPLIT`; mọi enum hợp lệ. Nếu lấy mẫu các field độc lập, gần như mọi ca sẽ rơi vào error thay vì kiểm đường số học.
- **Lẫn hai lane:** câu “generator chỉ được sinh trong miền này” mâu thuẫn với nhu cầu fuzz error code, amount vượt cận và precedence. README nói ca cực đại sẽ được sinh ở property test, nhưng mục 5 không định nghĩa generator invalid hay cách giữ lỗi mục tiêu khỏi bị một lỗi ưu tiên cao hơn che mất.
- **Coverage bắt buộc còn thiếu:** mixed item discount + global discount + proportional/even surcharge; nhiều discount trên cùng item; mọi item net về 0 rồi proportional fallback; cặp warning đồng thời; biên `10**12`/`10**12 + 1`; permutation của `shared_by`; ID prefix và ít nhất một ca ngoài BMP nếu comparator có khả năng được port sang TypeScript.
- **Tiêu chí gỡ:** tách hai hợp đồng generator: `valid_success_generator` xây input theo ràng buộc quan hệ và suy ra `total_vnd`; `invalid_case_generator` tạo một lỗi mục tiêu hoặc một tổ hợp lỗi đã đăng ký để kiểm precedence. Ghi range/distribution cho mọi field, cap byte của ID, seed/replay format, và bảng ca bắt buộc cho cả hai lane. Không cần lưu literal cực đại vào golden nếu repo guard cấm; property test có thể tạo runtime.

## Blocker ADR4-04 — Chín invariant chưa đặc tả largest remainder

- **Loại:** correctness; false-pass của property gate.
- **Phản ví dụ:** `total = 1`, exact share `a = 9/10`, `b = 1/10`, nhưng output `allocations = {a: 0, b: 1}`, `rounding_gainers = (b,)`. Output này sai vì `a` có phần dư lớn hơn, nhưng vẫn qua cả chín invariant hiện tại: tổng đúng, int, không âm, đủ key, tất định, một gainer, không gainer nào có remainder 0, và exact sum đúng.
- **Thiếu trực tiếp:**
  - `allocations[p] == floor(exact[p]) + 1[p ∈ rounding_gainers]`;
  - `rounding_gainers` phải **bằng đúng tuple** `deficit` người đầu theo khoá `(-remainder, advancer, utf8_bytes)`, không chỉ đúng số lượng;
  - key của `exact_shares` đúng bằng participants và mọi exact share không âm;
  - warning xuất hiện khi-và-chỉ-khi điều kiện #7/#15/#21 đúng, không trùng, theo thứ tự đóng;
  - permutation invariant bao gồm thứ tự trong từng `shared_by`, và “cùng output” phải nói mapping equality thay vì insertion order.
- **Hai câu đang đặt sai lớp:** invariant “chạy trên MỌI ca” không thể áp vào ca trả `AllocationError`; và “không float kể cả trung gian” không quan sát được bằng black-box property test. Đây là implementation constraint cần lint/static inspection hoặc test instrumented riêng.
- **Tiêu chí gỡ:** tách properties cho success và error; thêm các đẳng thức/ranking ở trên; chuyển no-float sang implementation constraint có cách kiểm; thêm metamorphic permutation cho `shared_by`; và buộc exact/warning/result shape bằng property chứ không chỉ bằng type hint.

## Blocker ADR4-05 — Golden hiện đúng, nhưng self-check cho qua mutant sai tie-break

- **Loại:** test validity; “hai bản cùng sai” vẫn có thể lọt.
- **Dẫn chứng:** self-check dòng 89–131 chỉ kiểm allocation = floor + gainer, số lượng gainer và một điều kiện rất yếu về remainder 0. Nó không tính lại ranking. Vì vậy các mutant sau vẫn qua toàn bộ self-check hiện tại:
  - G02 đổi gainer từ advancer `b` sang `a`, đồng thời chuyển +1đ sang `a`;
  - G16 đổi gainer từ `z` sang `á`;
  - G21 đổi gainers từ `(a, b)` sang `(a, c)`, với allocations tương ứng.
- **Warning cũng có lỗ:** test dòng 154–178 chỉ khóa warning advancer ngoài tập và zero share. Xoá `proportional_fallback_to_even` khỏi G15 vẫn qua self-check.
- **Corpus đang thiên về từng feature riêng lẻ:** chưa có success vector kết hợp item discount, global discount, cả hai mode surcharge và tie-break trong cùng đường tính. Hai bản có thể cùng đảo sai thứ tự composition mà 29 vector hiện tại không chạm.
- **Hậu quả:** lớp được tuyên bố chống “hai bản cùng sai” không thực sự khóa #15–#17. Differential xanh cộng self-check xanh vẫn chưa đủ cho money guardrail 100%.
- **Tiêu chí gỡ:** không import allocator, nhưng self-check phải tự suy `expected_gainers` từ **exact shares đã ghi** bằng comparator đóng băng và so đúng tuple; kiểm warning fallback iff; thêm ít nhất một vector composition; thêm vector warning đôi `advancer_not_participant + zero_share_participants` và `advancer_not_participant + proportional_fallback_to_even`; thêm permutation pair cho một error có nhiều entity. Expected output vẫn phải tính tay, không sinh từ impl.

## Trả lời trực tiếp các điểm được yêu cầu tấn công

### #16 — Tôi không đọc ngược

Tôi xác nhận **advancer nhận THÊM 1đ**. Lập luận quyết định là semantics của largest-remainder, không phải chữ “thắng” theo nghĩa được ưu đãi. Nên sửa câu “cả nhóm nợ ít đi” thành “những participant còn lại phải hoàn ít hơn 1đ” để không tạo cảm giác tổng allocation giảm; bất biến tổng vẫn giữ nguyên.

### #20 — Có ca chưa tất định

Precedence của **12 code đã nêu** là đủ nếu mọi ID hợp lệ/duy nhất và shape precondition đã được bảo đảm. Các ca chưa tất định nằm ở duplicate/invalid entity ID, amount 0, duplicate `shared_by`, và discount scope-target mismatch. Đó là blocker ADR4-01. Duyệt byte ID không tự giải quyết được input có hai entity cùng ID.

### #17 — Quyết định đúng, comparator cần thêm một câu hình thức

Giữ byte UTF-8. Chỉ cần đóng thêm: UTF-8 hợp lệ; so lexicographic trên byte không dấu; nếu một dãy là prefix của dãy kia thì dãy ngắn hơn đứng trước. G16 là golden đúng nhưng self-check phải thật sự khóa nó.

### #1 — Dùng được trong ca thật

Từ chối mismatch là đúng cho oracle. Chênh dương dùng surcharge `unlisted`; chênh âm phải được đưa thành discount tường minh; không có item dùng `EVEN_SPLIT`. Điều cần giữ ở caller/UI là nhãn giải thích của adjustment, không phải co giãn trong allocator.

### #3 — Không phải blocker nếu giữ đủ participant ở output

Cho phép exact share 0 là đúng. Bug UI chỉ xuất hiện nếu consumer lọc allocation 0; đó phải là một consumer invariant. Ở allocator, cần bổ sung `exact_shares.keys() == participants`, giữ invariant allocations hiện tại, và có golden advancer chính là người zero-share để chứng minh tie-break không vượt remainder.

### Miền generator và chín invariant

Miền generator hiện **chưa đủ**; chín invariant hiện **thiếu điều kiện quyết định largest remainder**. Chi tiết và phản ví dụ nằm ở ADR4-03/04.

## Những điểm đã đạt, không tạo blocker

- Công thức exact rational, đúng một điểm làm tròn và reconciliation cưỡng chế là đúng.
- #15, #19, #21, #22 đóng được các nhánh `B = 0`/`B' = 0` về mặt số học.
- Từ vựng warning đóng, không payload và sort cố định là lựa chọn đúng về differential contract.
- G01–G17/G21 hiện tại đều có expected arithmetic đúng; G21 đúng khi remainder thắng advancer priority.
- 11 vector lỗi hiện tại trả đúng code theo precedence đã viết.
- Giới hạn oracle dùng một lần, không tái sử dụng production, và quy tắc viết mù phải giữ nguyên.

## Verdict cuối

**`REQUEST_CHANGES`. Chưa đóng băng ADR-0004; chưa mở W6a/W6b; tôi chưa viết `impl_a`.**

Không cần thay hướng số học hay đảo #16. Cần làm hợp đồng thành hàm toàn phần trên miền đã tuyên bố, đóng một entry point, tách success/error generator, bổ sung property thật sự đặc tả largest remainder, và làm self-check bắt được mutant tie-break. Khi năm blocker này được gỡ, tôi kỳ vọng vòng kế có thể đi thẳng tới `APPROVE` thay vì mở lại thiết kế từ đầu.
