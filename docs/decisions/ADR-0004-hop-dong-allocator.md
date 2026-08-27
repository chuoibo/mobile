# ADR-0004 — Hợp đồng allocator (W6)

- **Trạng thái:** 🟢 **ĐÓNG BĂNG** 2026-08-27, sau **4 vòng review** với Codex
- **Corpus:** 23 vector thành công + 18 vector lỗi
- **Ngày:** 2026-08-27
- **DRI:** Claude · **Reviewer:** Codex
- **Chặn:** W6a (Codex), W6b (Claude), harness, golden vector
- **Sửa đổi:** #18–#22 thêm ngày 2026-08-27 — **cả năm do chính việc tính golden vector bằng tay lôi ra**, trước khi viết bất kỳ dòng code allocator nào. Đây là lý do bước đóng băng hợp đồng tồn tại

> **KHÔNG ai được viết code allocator trước khi ADR này đóng băng.** Đây là bước 1 trong quy trình 7 bước ở `docs/team/backlog.md`. Viết code trước rồi hợp thức hoá hợp đồng sau sẽ biến differential test thành nghi lễ.

## Bối cảnh

W6 là **oracle nghiên cứu dùng một lần**, không phải lõi production. Nhưng nó sẽ chạm nghĩa vụ tiền **thật giữa participant** trong phiên concierge, nên số học sai là `serious_error` — guardrail phải bằng 0.

Hai bản viết mù rồi differential test. Điều đó chỉ có giá trị nếu **cả hai viết theo cùng một hợp đồng**. Mọi chỗ hợp đồng im lặng sẽ biến thành một bất đồng không phân loại được.

Nguồn duy nhất: **spec mục 4**. ADR này không phát minh quy tắc mới; nó **quyết những chỗ spec im lặng**.

---

## 1. Hình dạng hợp đồng

Một **entry point công khai duy nhất**, hai tầng là helper nội bộ, **đúng một điểm làm tròn**.

```python
allocate(expense: ExpenseInput) -> ApportionResult      # ← DUY NHẤT public

_compute_exact_shares(expense) -> tuple[dict[ParticipantId, Fraction], tuple[str, ...]]
_apportion(total_vnd, exact, advancer_id) -> tuple[dict[ParticipantId, int], tuple[ParticipantId, ...]]
```

> **Sửa theo blocker ADR4-02 của Codex.** Bản đầu khai **hai hàm public**, và thiết kế đó **làm mất warning**: `proportional_fallback_to_even` chỉ biết được ở tầng phụ phí, nhưng `apportion` không có đối số nào mang được thông tin đó. Impl A có thể đặt warning ở wrapper, impl B trả từ tầng một — và harness **không có entry point thống nhất để so**.
> Bản đầu cũng nói `Σ exact_i == total_vnd` phải "kiểm tra, không giả định" nhưng **không có error code** cho việc vi phạm tiền đề. Với input sai tiền đề, một bản assert, một bản trả error, một bản vẫn làm tròn — **cả ba đều không trái câu chữ cũ**.

**Helper là nội bộ.** Vi phạm precondition của helper là lỗi lập trình, không phải `AllocationError`: nó phải `assert`, và nếu harness gọi thẳng helper thì mọi thất bại phân loại là **`harness_bug`**, không phải `impl_bug`. Harness **chỉ được fuzz qua `allocate`**.

`Fraction` là **ngôn ngữ của hợp đồng** để nói "chính xác". `impl_a` được phép dùng số nguyên thuần miễn kết quả trùng khớp.

### Biên liên vận hành — đóng băng TRƯỚC khi viết hai bản

> **Sửa theo blocker V2-03 của Codex.** ADR khai `exact_shares` kiểu `Fraction`, nhưng `impl_a` bị yêu cầu dùng **số nguyên thuần, không `Fraction`**. Impl A có thể trả `(num, den)`, impl B trả `fractions.Fraction` — **mapping equality sẽ đỏ dù số học giống hệt nhau.** Và harness sẽ phải đọc code từng bản rồi viết adapter riêng, tức là **phá luôn ý nghĩa "viết mù"**.

**Biên là `dict` thuần Python, đúng bằng schema của golden vector.** Không dataclass ở biên, không kiểu riêng của bản nào.

```python
# phase0/allocator/impl_{a,b}/allocator.py
def allocate(expense: dict) -> dict: ...
```

| | |
|---|---|
| **Input** | `dict` khớp đúng khoá `input` của golden vector |
| **Output** | `dict` có `allocations` · `exact_shares` · `rounding_gainers` · `warnings` |
| **`allocations`** | `dict[str, int]` |
| **`exact_shares`** | `dict[str, str]` — **chuỗi `"num/den"` đã TỐI GIẢN, `den > 0`**, kể cả số nguyên (`"100000/1"`) |
| **`rounding_gainers`** | `list[str]`, **có thứ tự** |
| **`warnings`** | `list[str]`, sắp xếp alphabet |
| **Lỗi** | `raise AllocationError(code)` từ `phase0/allocator/contract.py` |

`impl_b` được dùng `Fraction` **nội bộ**, nhưng kiểu đó **không được rò qua biên**.

`contract.py` là module dùng chung **duy nhất**, và nó chỉ chứa **hằng số và lớp ngoại lệ — không một dòng logic nào**. Chia sẻ logic sẽ phá viết mù.

Hệ quả đáng giá: golden corpus **chạy thẳng** được lên cả hai bản, không cần adapter.

### Ngữ nghĩa so sánh — đóng băng cho differential

### Lược đồ dữ liệu — MỘT biểu diễn duy nhất

> **Sửa theo blocker V3-01 của Codex.** Bản v3 để lại **hai** biểu diễn: khối kiểu khái niệm (`ExpenseInput`, `Fraction`) và biên `dict` mới. Lỗi merge, không phải bất đồng thiết kế — nhưng nó đủ để hai bản trả hai kiểu khác nhau.

`dict` thuần, đúng bằng schema của golden vector. Không có kiểu riêng nào ở biên.

```jsonc
// input
{
  "participants": ["a", "b"],          // KHÔNG rỗng, không trùng, mỗi ID 1..64 byte
  "total_vnd": 110000,                 // >= 0, <= 10**12
  "items": [
    {"item_id": "i1", "amount_vnd": 60000, "shared_by": ["a"]}   // amount > 0; shared_by KHÔNG rỗng, không trùng
  ],
  "surcharges": [
    {"surcharge_id": "s1", "kind": "fee", "amount_vnd": 10000, "mode": "proportional"}  // mode: proportional | even
  ],
  "discounts": [
    {"discount_id": "d1", "amount_vnd": 4000, "scope": "global_proportional", "item_id": null}
    // scope: global_proportional | item ; item_id bắt buộc KHI VÀ CHỈ KHI scope == "item"
    // amount luôn là ĐỘ LỚN, luôn bị TRỪ
  ],
  "advancer_id": "a"                   // hoặc null
}

// output
{
  "allocations":      {"a": 66000, "b": 44000},        // int, Σ == total_vnd
  "exact_shares":     {"a": "66000/1", "b": "44000/1"}, // chuỗi "num/den" TỐI GIẢN, den > 0
  "rounding_gainers": [],                               // CÓ THỨ TỰ
  "warnings":         []                                // sắp xếp alphabet, từ vựng đóng
}
```

**Không có trường `currency`.** V1 chỉ VND (spec mục 4).

**`rounding_gainers` là bắt buộc, không phải tiện ích.** Spec mục 4: *"Quy tắc phải hiện ra cho người dùng thấy."* Giao diện phải nói được "Hà chịu thêm 1đ do làm tròn". Một allocator trả về mỗi con số cuối là không đủ.

---

## 2. Đường tính

```
Tầng 1 — phần món
  mỗi món:  item_net = item.amount_vnd − Σ(giảm giá gắn món đó)
            item_net chia ĐỀU cho item.shared_by          → Fraction
  base_i  = Σ phần món của người i

Tầng 2 — giảm giá chung, theo tỉ lệ
  B = Σ base_i ;  D = Σ(giảm giá global_proportional)
  base'_i = base_i × (B − D) / B          (nếu B > 0)

Tầng 3 — phụ phí
  B' = Σ base'_i
  proportional:  s_i += surcharge × base'_i / B'
  even:          s_i += surcharge / n          (n = len(participants))

Tầng 4 — cộng lại
  exact_i = base'_i + s_i

Tầng 5 — làm tròn, MỘT LẦN DUY NHẤT
  apportion(total_vnd, exact, advancer_id)
```

### Đối chiếu — cưỡng chế, không co giãn

```
listed_vnd = Σ items.amount_vnd + Σ surcharges.amount_vnd − Σ discounts.amount_vnd
```

Bắt buộc `listed_vnd == total_vnd`. Không khớp → **từ chối** với `RECONCILIATION_MISMATCH`.

### Ca `EVEN_SPLIT`

Khi `items`, `surcharges`, `discounts` **đều rỗng**: toàn bộ `total_vnd` chia đều cho `participants`. Bỏ qua đối chiếu.

Đây là ca đặc biệt **duy nhất** trong hợp đồng, có tên, có test riêng.

---

## 3. Hai mươi hai quyết định

Spec im lặng ở những chỗ này. Để fuzzer tự quyết là sai — nó sẽ biến bất đồng thiết kế thành "bug" của một trong hai bản.

| # | Tình huống | Quyết định | Vì sao |
|---|---|---|---|
| **1** | `listed_vnd ≠ total_vnd` | ❌ `RECONCILIATION_MISMATCH` | Co giãn ngầm = **thay đổi vật chất số tiền người dùng đã nhìn**, trái spec mục 3. Muốn hoà thì caller thêm `Surcharge(kind="unlisted")` **tường minh** — phần lệch phải nhìn thấy được trong dữ liệu, không giấu trong một trường đặc biệt |
| **2** | `items` rỗng | ✅ `EVEN_SPLIT`, chỉ khi surcharge và discount cũng rỗng | Đây là ca phổ biến nhất ngoài đời. Bắt caller bịa một "món giả" sẽ khiến món giả đó hiện ra ở drill-down như một món thật — đúng thứ spec mục 3 cảnh báo về "giải thích cũ" |
| **3** | Participant không thuộc `shared_by` của món nào, không có phụ phí `even` | ✅ Hợp lệ, phần = **0**. Thêm warning `zero_share_participants` | Người đi cùng mà không ăn gì là ca thật — họ vẫn có thể là người ứng tiền. Từ chối sẽ chặn ca hợp lệ. Nhưng phải **hiện ra**, không im lặng |
| **4** | `item.shared_by` rỗng | ❌ `EMPTY_SHARED_BY` | Mặc định "chia cho tất cả" là **tự bịa ra nghĩa vụ**. Bắt ai đó trả khoản họ không nợ là chế độ hỏng tệ nhất — `serious_error` |
| **5** | Giảm giá gắn món > chính món đó | ❌ `DISCOUNT_EXCEEDS_ITEM` | Kẹp về 0 làm mất tiền một cách im lặng và phá đối chiếu. Cho âm tạo phần chia âm — đó là `CreditAdjustment`, thực thể khác (mục 6.3) |
| **6** | `Σ` giảm giá chung > `B` | ❌ `DISCOUNT_EXCEEDS_BASE` | Như trên |
| **7** | Advancer ngoài tập tham gia | ✅ Hợp lệ. **Không tạo phần** cho họ, và họ **mất quyền tie-break** | Nguyên văn spec mục 4 |
| **8** | Participant ID trùng | ❌ `DUPLICATE_PARTICIPANT` | |
| **9** | `total_vnd = 0`, participants khác rỗng | ✅ Hợp lệ, mọi phần = 0 | |
| **10** | `participants` rỗng | ❌ `NO_PARTICIPANTS` — kể cả khi `total_vnd = 0` | Tiền phải đi đâu đó. Không có ai thì không có gì để phân bổ |
| **11** | `total_vnd < n` (3 đồng, 5 người) | ✅ Hợp lệ. `total_vnd` người đầu theo thứ tự tie-break nhận 1đ, còn lại 0 | Bất biến vẫn giữ. Không có lý do từ chối |
| **12** | Bất kỳ số tiền nào < 0 | ❌ `NEGATIVE_AMOUNT` | Hoàn tiền là `CreditAdjustment` (spec mục 4, 6.3) |
| **13** | Số tiền quá lớn | ❌ `AMOUNT_TOO_LARGE` khi bất kỳ số tiền nào > `10**12` | Khoản chi nhóm bạn không bao giờ tới nghìn tỉ. Miền input vô hạn khiến fuzzer đốt thời gian ở vùng không học được gì. Cũng giữ golden vector và log ở kích thước lành mạnh |
| **14** | Phụ phí `even` | Chia đều cho **MỌI** participant, kể cả người phần = 0 | Phí ship/phục vụ là chi phí của việc **cả nhóm có mặt**, không phải của việc bạn ăn gì. Và "chia đều" theo nghĩa thông thường là tất cả — đó chính là lý do người dùng chọn tuỳ chọn này |
| **15** | Phụ phí `proportional` khi `B' = 0` | Lui về **chia đều**. Warning `proportional_fallback_to_even` | Không có cơ sở tỉ lệ thì chia đều là phân bố duy nhất bảo vệ được. Thay thế duy nhất là chia cho 0 |
| **16** | **Advancer thắng tie-break nghĩa là nhận THÊM hay BỚT 1đ?** | **THÊM** — advancer nhận `+1đ` | ⚠️ Đây là chỗ mơ hồ thật, dễ đọc ngược. Phần chia = **số tiền người đó nợ**. Advancer nhận thêm 1đ ⇒ **người ứng tiền nuốt phần lẻ**; những participant còn lại phải hoàn ít hơn 1đ. Tổng allocation **không** giảm. Đó là hành vi đúng về mặt xã hội và là cách đọc duy nhất khiến "thắng" có nghĩa là chịu thiệt thay cho nhóm |
| **17** | "Thứ tự ổn định theo ID" là thứ tự nào? | Sắp xếp `participant_id` theo **byte UTF-8**, KHÔNG theo thứ tự input, KHÔNG theo collation ngôn ngữ | Thứ tự input khác nhau giữa client và server. Collation tiếng Việt khác nhau giữa nền tảng và phiên bản ICU. Byte UTF-8 là thứ duy nhất tái lập được ở mọi nơi — và điều này quan trọng nếu sau này thêm bản TypeScript |
| **18** | Định dạng `warnings` | **Từ vựng đóng, không mang payload, sắp xếp theo alphabet:** `advancer_not_participant` · `proportional_fallback_to_even` · `zero_share_participants` | ⚠️ Tự tìm ra khi tính golden vector bằng tay. Nếu để mở, hai bản sẽ format chuỗi khác nhau (`"zero:a,c"` với `"zero_share=a, c"`) và tạo ra một **bất đồng giả** không phải lỗi số học. Chi tiết ai phần 0 caller tự suy ra từ `allocations` — không nhân bản dữ liệu vào chuỗi |
| **19** | `items` rỗng nhưng `surcharges` hoặc `discounts` KHÔNG rỗng | ✅ Hợp lệ. **Không phải** `EVEN_SPLIT` — đi đường thường, có đối chiếu, `B = 0` | ⚠️ Cũng tự tìm ra khi viết golden vector. Quyết định #2 chỉ định nghĩa `EVEN_SPLIT`, nó **không** cấm ca này. Kết hợp với #15 (`B' = 0` → lui về chia đều) thì ca "toàn bộ khoản chi là phụ phí" có hành vi xác định |
| **20** | Nhiều lỗi cùng áp dụng — trả `code` nào? | **Thứ tự kiểm tra cố định:** cấu trúc → tham chiếu → số học → đối chiếu. Trong mỗi nhóm, duyệt phần tử theo **thứ tự byte của `item_id` / `surcharge_id` / `discount_id`**, KHÔNG theo thứ tự input | ⚠️ Tự tìm ra khi viết golden vector cho ca lỗi. Nếu không chốt, hai bản sẽ trả `code` khác nhau cho cùng input — một **bất đồng giả**. Và nếu duyệt theo thứ tự input thì đảo thứ tự `items` sẽ đổi `code`, **phá bất biến 6** |

**Danh sách precedence chuẩn duy nhất nằm ở mục 6.** Không lặp lại ở đây.

> **Sửa theo blocker V2-01 của Codex.** Bản v2 để lại **hai** danh sách cùng mang nhãn "đầy đủ": 12 code ở đây và 19 code ở mục 6. Phản ví dụ của Codex: `participants = (" a", " a")` → theo danh sách cũ là `DUPLICATE_PARTICIPANT`, theo mục 6 là `INVALID_PARTICIPANT_ID`. **Hai hiện thực đều viện dẫn được một đoạn có nhãn "đầy đủ" mà trả code khác nhau.** Đây là lỗi merge, không phải bất đồng thiết kế.

| # | Tình huống | Quyết định | Vì sao |
|---|---|---|---|
| **21** | `zero_share_participants` kích hoạt khi nào? | Khi **phần chính xác** của một người bằng 0 **VÀ** `total_vnd > 0` | ⚠️ Lại một chỗ tự tìm ra khi tính vector. Nếu tính theo **allocation** = 0 thì ca `total_vnd < n` (3 đồng / 5 người) sẽ báo warning cho những người chỉ đơn giản bị làm tròn xuống — nhiễu. Phần chính xác bằng 0 nghĩa là người đó bị loại **về mặt cấu trúc** khỏi mọi món và mọi phụ phí chia đều; đó mới là thứ đáng hiện ra. Điều kiện `total_vnd > 0` chặn ca khoản chi bằng 0 báo warning cho tất cả mọi người |
| **22** | `B = 0` ở tầng giảm giá chung | `base'_i = 0`, **không chia**. Nếu `D > 0` thì `DISCOUNT_EXCEEDS_BASE` đã kích hoạt trước đó (`D > 0 = B`) | Chặn chia cho 0. Ràng buộc `D ≤ B` khiến `B = 0 ⟹ D = 0`, nên nhánh này luôn xác định |

---

## 4. Làm tròn — phần dư lớn nhất

```
tiền_đề:  Σ exact_i == total_vnd   (đẳng thức hữu tỉ chính xác — kiểm tra, không giả định)

floor_i      = ⌊exact_i⌋
remainder_i  = exact_i − floor_i          →  0 ≤ remainder_i < 1
deficit      = total_vnd − Σ floor_i      →  0 ≤ deficit < n

khoá sắp xếp, tăng dần:
    ( −remainder_i ,  0 nếu là advancer-và-là-participant ngược lại 1 ,  byte UTF-8 của participant_id )

deficit người đầu tiên nhận +1đ
```

**Advancer chỉ thắng khi phần dư BẰNG NHAU.** `remainder` là khoá chính. Đây là "tie-break", không phải ưu tiên toàn cục.

**Chứng minh `deficit` không bao giờ vượt quá số người có phần dư > 0:** nếu mọi `remainder_i = 0` thì `Σ exact` là số nguyên và bằng `Σ floor`, nên `deficit = 0`. Vậy không bao giờ phải trao +1đ cho người có phần dư bằng 0 trong khi vẫn còn người có phần dư dương. Bản nào vi phạm điều này là có bug — **đây là một property test, không phải nhận xét**.

---

## 5. Hai hợp đồng generator — tách bạch

> **Sửa theo blocker ADR4-03 của Codex.** Bản đầu chỉ có range cho số lượng và số tiền, không có miền cho entity ID, `mode`, `scope`, `kind`, target item, hay **ràng buộc liên trường**. Lấy mẫu từng field độc lập thì **gần như mọi ca sẽ rơi vào đường lỗi** thay vì kiểm đường số học — fuzzing chạy cả đêm mà không chạm tới phép làm tròn.
> Và câu "generator chỉ được sinh trong miền hợp lệ" **mâu thuẫn** với nhu cầu fuzz chính thứ tự lỗi.

### 5.1 `valid_success_generator` — xây theo quan hệ, KHÔNG lấy mẫu độc lập

Xây theo thứ tự nhân quả, rồi **suy ra** `total_vnd` từ những gì đã xây. Như vậy đối chiếu **luôn khớp theo cấu tạo**, và ca sinh ra thật sự kiểm đường số học.

```
1. participants        1…30, ID duy nhất
2. items               0…40; shared_by ⊆ participants, không trùng, không rỗng
3. item discounts      Σ trên MỖI item ≤ amount của item đó
4. global discounts    Σ ≤ B
5. surcharges          0…5, mode ∈ {proportional, even}
6. total_vnd  :=  Σ items + Σ surcharges − Σ discounts     ← SUY RA
7. advancer            trong participants | ngoài | None — cả ba phải xuất hiện
```

`EVEN_SPLIT` sinh riêng: items, surcharges, discounts rỗng; `total_vnd` lấy tự do trong `0…10¹²`.

| Trường | Miền |
|---|---|
| `participant_id` | UTF-8 hợp lệ, **1…64 byte**. Bắt buộc có: ca tiếng Việt có dấu · ca chỉ khác nhau ở dấu · ca **prefix của nhau** (`"a"` và `"aa"`) · ≥1 ca **ngoài BMP** |
| `item_id` / `surcharge_id` / `discount_id` | UTF-8 hợp lệ, 1…64 byte, **duy nhất trong namespace của chính loại đó** |
| `item.amount_vnd` | 1…10⁹ |
| `surcharge.amount_vnd` / `discount.amount_vnd` | 1…10⁹ |
| `kind` | chuỗi không rỗng, 1…32 byte |
| `len(discounts)` | **0…5**, chia: item-scoped **0…3**, global-proportional **0…2** |
| `total_vnd` (EVEN_SPLIT) | 0…10¹² |

**Ca bắt buộc có mặt, không phó mặc xác suất:**
`n = 1` · `total_vnd = 0` · `total_vnd < n` · phần dư bằng nhau ở nhiều người · một món cho một người · một món cho tất cả · giảm giá **vừa đúng bằng** món · toàn bộ khoản chi là phụ phí · `EVEN_SPLIT` · **item discount + global discount + cả hai mode phụ phí trong CÙNG một ca** · nhiều discount trên **cùng** một item · mọi item net về 0 rồi phụ phí proportional lui về chia đều · **hai warning cùng lúc** · **cặp sát biên sinh runtime: `total_vnd = 10¹²` HỢP LỆ và `10¹² + 1` → `AMOUNT_TOO_LARGE`** · **permutation của `shared_by`**.

### 5.2 `invalid_case_generator` — một lỗi mục tiêu, có đăng ký

Sinh **đúng một** lỗi mục tiêu, hoặc **một tổ hợp lỗi đã đăng ký trước** để kiểm precedence.

Bắt buộc kiểm: mỗi code ở mục 6 có ít nhất một ca đơn lẻ · mỗi cặp precedence liền kề có một ca tổ hợp · **permutation của thứ tự phần tử phải cho cùng `code`**.

⚠️ Sinh lỗi mà **không kiểm soát** thì một lỗi ưu tiên cao hơn sẽ che mất lỗi đang muốn kiểm. Đó là lý do phải sinh có mục tiêu, không sinh mù.

### 5.3 Seed và replay

Mọi ca sinh ra phải tái tạo được từ `(generator_name, seed, index)`. Counterexample lưu vào Git ở dạng **tổng hợp, an toàn**, kèm bộ ba đó.

---

## 6. Lỗi

> **Sửa theo blocker ADR4-01 của Codex.** Miền dữ liệu ở mục 1 cấm nhiều thứ mà **danh sách lỗi không gán hành vi cho chúng**. Nguy hiểm nhất: **hai item trùng `item_id`** — một item discount có thể áp vào item này, item kia, cả hai, hoặc map bị ghi đè. Đó là **đổi nghĩa vụ tiền**, không phải đổi thông báo lỗi. Và "duyệt theo thứ tự byte của ID" **không phá được tie giữa hai entity trùng ID**.

Một ngoại lệ `AllocationError` mang `code`. **Danh sách đóng, đầy đủ, có vị trí chính xác trong precedence:**

### Nhóm 1 — cấu trúc

`NO_PARTICIPANTS` → `INVALID_PARTICIPANT_ID` *(rỗng, có whitespace đầu/cuối, > 64 byte, không phải UTF-8 hợp lệ)* → `DUPLICATE_PARTICIPANT` → `INVALID_ENTITY_ID` *(item/surcharge/discount)* → `DUPLICATE_ENTITY_ID` *(trùng trong cùng namespace)* → `NEGATIVE_AMOUNT` → `ZERO_AMOUNT` *(item/surcharge/discount amount = 0)* → `AMOUNT_TOO_LARGE` → `INVALID_KIND` → `INVALID_MODE` → `INVALID_SCOPE` → `SCOPE_TARGET_MISMATCH` *(scope `item` mà `item_id = None`, hoặc scope global mà lại mang `item_id`)* → `EMPTY_SHARED_BY` → `DUPLICATE_SHARED_BY`

### Nhóm 2 — tham chiếu
`UNKNOWN_PARTICIPANT` → `UNKNOWN_ITEM`

### Nhóm 3 — số học
`DISCOUNT_EXCEEDS_ITEM` → `DISCOUNT_EXCEEDS_BASE`

### Nhóm 4 — đối chiếu
`RECONCILIATION_MISMATCH` — **luôn cuối cùng**

Đối chiếu đứng cuối vì nó là **hệ quả**: giảm giá vượt món gần như luôn kéo theo lệch đối chiếu, và báo `RECONCILIATION_MISMATCH` khi nguyên nhân thật là `DISCOUNT_EXCEEDS_ITEM` sẽ khiến giao diện **chỉ sai chỗ** cho người dùng.

### Validation theo VỊ TRÍ XUẤT HIỆN — hàm toàn phần

> **Sửa theo blocker V2-02 của Codex.** `ParticipantId` xuất hiện ở **ba** vị trí, nhưng ADR không nói `INVALID_PARTICIPANT_ID` kiểm cả ba hay chỉ khai báo. Fork cụ thể: `shared_by = ("",)` → `INVALID_PARTICIPANT_ID` hay `UNKNOWN_PARTICIPANT`? `advancer_id = ""` → lỗi hay success kèm warning?

**Quy tắc một câu: KHAI BÁO thì validate, THAM CHIẾU thì phân giải.**

| Vị trí | Loại | Kiểm gì | Vi phạm → |
|---|---|---|---|
| `participants[*]` | khai báo | UTF-8 hợp lệ · 1…64 byte · không rỗng · **không whitespace đầu/cuối** | `INVALID_PARTICIPANT_ID` |
| `item.shared_by[*]` | **tham chiếu** | chỉ kiểm thuộc `participants` | `UNKNOWN_PARTICIPANT` |
| `advancer_id` | **tham chiếu** | chỉ kiểm thuộc `participants` | *(không lỗi)* → warning `advancer_not_participant` |
| `item_id` · `surcharge_id` · `discount_id` | khai báo | như `participants[*]` | `INVALID_ENTITY_ID` |
| `discount.item_id` | **tham chiếu** | chỉ kiểm tồn tại trong `items` | `UNKNOWN_ITEM` |

Hệ quả được nêu rõ chứ không giấu:
- `shared_by = ("",)` → **`UNKNOWN_PARTICIPANT`**, không phải `INVALID_PARTICIPANT_ID`
- `advancer_id = ""` → **thành công**, kèm warning `advancer_not_participant`
- `discount.item_id = ""` → **`UNKNOWN_ITEM`**, không phải `INVALID_ENTITY_ID`
- `advancer_id = None` (không có người ứng tiền) **khác** `advancer_id = ""` (có, nhưng ngoài tập) — và khác nhau ở warning

`advancer_id = ""` không bị từ chối là **có chủ ý**: validate tham chiếu sẽ tạo lại đúng fork mà quy tắc này xoá bỏ. Cái giá là một ID rỗng lọt qua thành warning — chấp nhận được vì nó **không sinh nghĩa vụ tiền cho ai**.

### Quy tắc định danh — đóng băng

| | |
|---|---|
| **Namespace** | `item_id`, `surcharge_id`, `discount_id` là **ba namespace tách biệt**. Trùng nhau giữa các loại là hợp lệ |
| **Bằng nhau** | So sánh **byte UTF-8 chính xác**. **KHÔNG normalize Unicode.** Normalize sẽ gộp hai ID mà caller coi là khác nhau — tức có thể **gộp hai người** |
| **Thứ tự** | Lexicographic trên **byte không dấu**. Nếu một dãy là **prefix** của dãy kia thì **dãy ngắn hơn đứng trước** |
| **Độ dài** | 1…64 byte. Vượt → `INVALID_PARTICIPANT_ID` hoặc `INVALID_ENTITY_ID` |

**Hai bản phải trả cùng `code` cho cùng input** — `code` là thứ giao diện dùng để nói cho người dùng biết họ sai ở đâu. Khác `code` là bất đồng thật.

---

## 7. Property — tách SUCCESS và ERROR

> **Sửa theo blocker ADR4-04 của Codex.** Chín bất biến cũ **không đặc tả largest remainder**. Phản ví dụ của Codex:
> ```
> total = 1,  exact = {a: 9/10, b: 1/10},  output = {a: 0, b: 1},  gainers = (b,)
> ```
> Sai — `a` có phần dư lớn hơn. **Nhưng nó qua cả chín bất biến cũ:** tổng đúng, int, không âm, đủ key, tất định, một gainer, gainer có phần dư ≠ 0, exact sum đúng.
> Cổng property của tôi là một **cổng cho qua giả**. Đây là blocker nghiêm trọng nhất trong năm.

### 7.1 Property cho ca THÀNH CÔNG

1. `Σ allocations.values() == total_vnd` — **không ngoại lệ, 100%**
2. Mọi allocation là `int`, và `≥ 0`
3. `set(allocations) == set(exact_shares) == set(participants)` · mọi `exact_share ≥ 0`
4. Advancer ngoài tập tham gia **không** xuất hiện trong `allocations`
5. `Σ exact_shares == total_vnd` — đẳng thức **hữu tỉ chính xác**
6. **`allocations[p] == floor(exact[p]) + (1 nếu p ∈ rounding_gainers ngược lại 0)`**
7. **`rounding_gainers` BẰNG ĐÚNG TUPLE** `deficit` người đầu tiên theo khoá `(−remainder, 0 nếu advancer-và-là-participant ngược lại 1, byte UTF-8 của id)` — **không chỉ đúng SỐ LƯỢNG**
8. `warnings` xuất hiện **khi và chỉ khi** điều kiện #7 / #15 / #21 đúng · không trùng · sắp xếp alphabet · thuộc từ vựng đóng
9. **Metamorphic:** đảo thứ tự `participants`, `items`, `surcharges`, `discounts`, **và thứ tự bên trong từng `shared_by`** → **cùng output** theo ngữ nghĩa so sánh ở mục 1

Property 7 là thứ bắt được phản ví dụ ở trên. Property 6 và 7 cùng nhau **đặc tả trọn vẹn** phần dư lớn nhất.

### 7.2 Property cho ca LỖI

10. Ném `AllocationError` với `code` thuộc danh sách đóng ở mục 6
11. **Metamorphic:** đảo thứ tự phần tử → **cùng `code`**
12. Tổ hợp lỗi đã đăng ký → `code` của nhóm có **ưu tiên cao nhất**

> Property 1–9 **không áp được** vào ca lỗi. Câu "chạy trên MỌI ca sinh ra" ở bản đầu là sai lớp.

### 7.3 Ràng buộc hiện thực — KHÔNG phải property

**"Không `float` ở bất kỳ đâu, kể cả trung gian"** không quan sát được bằng black-box property test.

Kiểm bằng: lint/AST cấm `float`, `/` trên số không phải Fraction, `round`, `math.floor` trên float — **cộng** một test có instrument. Ghi ở đây để không ai tưởng property test đã bao phủ nó.

---

## 8. Chưa thuộc phạm vi W6

`WriteOff` · `CreditAdjustment` · nhiều người ứng tiền một khoản chi · nhiều loại tiền tệ · bù trừ giữa các khoản chi · `verification_scope`.

Ghi ra để không ai lặng lẽ kéo chúng vào oracle. Chúng thuộc tầng sổ, không thuộc tầng số học.
