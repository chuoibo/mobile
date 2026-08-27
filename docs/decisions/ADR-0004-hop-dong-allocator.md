# ADR-0004 — Hợp đồng allocator (W6)

- **Trạng thái:** 🟡 **ĐỀ XUẤT** — chờ Codex tấn công. Đóng băng khi cả hai ký.
- **Ngày:** 2026-08-27
- **DRI:** Claude · **Reviewer:** Codex
- **Chặn:** W6a (Codex), W6b (Claude), harness, golden vector

> **KHÔNG ai được viết code allocator trước khi ADR này đóng băng.** Đây là bước 1 trong quy trình 7 bước ở `docs/team/backlog.md`. Viết code trước rồi hợp thức hoá hợp đồng sau sẽ biến differential test thành nghi lễ.

## Bối cảnh

W6 là **oracle nghiên cứu dùng một lần**, không phải lõi production. Nhưng nó sẽ chạm nghĩa vụ tiền **thật giữa participant** trong phiên concierge, nên số học sai là `serious_error` — guardrail phải bằng 0.

Hai bản viết mù rồi differential test. Điều đó chỉ có giá trị nếu **cả hai viết theo cùng một hợp đồng**. Mọi chỗ hợp đồng im lặng sẽ biến thành một bất đồng không phân loại được.

Nguồn duy nhất: **spec mục 4**. ADR này không phát minh quy tắc mới; nó **quyết những chỗ spec im lặng**.

---

## 1. Hình dạng hợp đồng

Hai tầng, **đúng một điểm làm tròn**. Làm tròn hai lần là nguồn lỗi kinh điển của loại bài toán này.

```python
compute_exact_shares(expense: ExpenseInput) -> dict[ParticipantId, Fraction]
    # Σ giá trị == expense.total_vnd, đẳng thức HỮU TỈ CHÍNH XÁC, không xấp xỉ

apportion(total_vnd: int,
          exact: dict[ParticipantId, Fraction],
          advancer_id: ParticipantId | None) -> ApportionResult
    # Σ allocations == total_vnd, đẳng thức SỐ NGUYÊN
```

`Fraction` chỉ là **ngôn ngữ của hợp đồng** để nói "chính xác". Bản `impl_a` được phép hiện thực bằng số nguyên thuần miễn kết quả trùng khớp.

### Kiểu dữ liệu

```python
ParticipantId = str          # không rỗng, không khoảng trắng đầu/cuối

Item:       item_id: str
            amount_vnd: int            # > 0
            shared_by: tuple[ParticipantId, ...]   # KHÔNG rỗng, không trùng, ⊆ participants

Surcharge:  surcharge_id: str
            kind: str                  # "fee" | "vat" | "shipping" | "unlisted" | nhãn khác
            amount_vnd: int            # > 0
            mode: "proportional" | "even"

Discount:   discount_id: str
            amount_vnd: int            # > 0 — luôn là ĐỘ LỚN, luôn bị TRỪ
            scope: "global_proportional" | "item"
            item_id: str | None        # bắt buộc khi và chỉ khi scope == "item"

ExpenseInput:
            participants: tuple[ParticipantId, ...]   # KHÔNG rỗng, không trùng
            total_vnd: int                            # >= 0
            items: tuple[Item, ...]
            surcharges: tuple[Surcharge, ...]
            discounts: tuple[Discount, ...]
            advancer_id: ParticipantId | None

ApportionResult:
            allocations: dict[ParticipantId, int]     # Σ == total_vnd
            exact_shares: dict[ParticipantId, Fraction]
            rounding_gainers: tuple[ParticipantId, ...]   # ai nhận +1đ, theo đúng thứ tự
            warnings: tuple[str, ...]
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

## 3. Mười bảy quyết định

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
| **16** | **Advancer thắng tie-break nghĩa là nhận THÊM hay BỚT 1đ?** | **THÊM** — advancer nhận `+1đ` | ⚠️ Đây là chỗ mơ hồ thật, dễ đọc ngược. Phần chia = **số tiền người đó nợ**. Advancer nhận thêm 1đ ⇒ **người ứng tiền nuốt phần lẻ**, cả nhóm nợ ít đi. Đó là hành vi đúng về mặt xã hội và là cách đọc duy nhất khiến "thắng" có nghĩa là chịu thiệt thay cho nhóm |
| **17** | "Thứ tự ổn định theo ID" là thứ tự nào? | Sắp xếp `participant_id` theo **byte UTF-8**, KHÔNG theo thứ tự input, KHÔNG theo collation ngôn ngữ | Thứ tự input khác nhau giữa client và server. Collation tiếng Việt khác nhau giữa nền tảng và phiên bản ICU. Byte UTF-8 là thứ duy nhất tái lập được ở mọi nơi — và điều này quan trọng nếu sau này thêm bản TypeScript |

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

## 5. Miền input hợp lệ — dành cho generator của harness

Generator **chỉ** được sinh trong miền này. Sinh ra ngoài rồi coi lỗi là `impl_bug` là `generator_out_of_domain` — một trong 5 loại phân loại.

| Trường | Miền |
|---|---|
| `len(participants)` | 1 … 30 |
| `participant_id` | chuỗi không rỗng; **phải** có ca ký tự tiếng Việt có dấu và ca chỉ khác nhau ở dấu, để ép lộ vấn đề thứ tự byte |
| `total_vnd` | 0 … 10¹² |
| `len(items)` | 0 … 40 |
| `item.amount_vnd` | 1 … 10⁹ |
| `len(item.shared_by)` | 1 … `len(participants)` |
| `len(surcharges)` | 0 … 5 |
| `len(discounts)` | 0 … 5 |
| `advancer_id` | thuộc participants · ngoài participants · `None` — **cả ba đều phải xuất hiện** |

Ca **bắt buộc có mặt** trong bộ sinh, không phó mặc xác suất:
`n = 1` · `total_vnd = 0` · `total_vnd < n` · phần dư bằng nhau ở nhiều người · một món chia cho một người · một món chia cho tất cả · giảm giá vừa đúng bằng món · toàn bộ khoản chi là phụ phí · `EVEN_SPLIT`.

---

## 6. Lỗi

Một ngoại lệ `AllocationError` mang `code`. Danh sách đóng:

`RECONCILIATION_MISMATCH` · `EMPTY_SHARED_BY` · `DISCOUNT_EXCEEDS_ITEM` · `DISCOUNT_EXCEEDS_BASE` · `DUPLICATE_PARTICIPANT` · `NO_PARTICIPANTS` · `NEGATIVE_AMOUNT` · `AMOUNT_TOO_LARGE` · `UNKNOWN_PARTICIPANT` · `UNKNOWN_ITEM` · `INVALID_MODE` · `INVALID_SCOPE`

**Hai bản phải trả về cùng `code` cho cùng input.** Khác `code` là một bất đồng thật, không phải chi tiết hiện thực — vì `code` là thứ giao diện dùng để nói cho người dùng biết họ sai ở đâu.

---

## 7. Bất biến — property test, chạy trên MỌI ca sinh ra

1. `Σ allocations.values() == total_vnd` — **không ngoại lệ, 100%**
2. Mọi giá trị allocation là `int`. **Không `float` ở bất kỳ đâu**, kể cả trung gian
3. Mọi allocation `≥ 0`
4. `set(allocations.keys()) == set(participants)` — không bịa người, không bỏ sót người
5. Advancer ngoài tập tham gia **không** xuất hiện trong `allocations`
6. Tất định: cùng input → cùng output, **kể cả khi đảo thứ tự** `participants`, `items`, `surcharges`, `discounts`
7. `len(rounding_gainers) == deficit`, và mỗi người nhận nhiều nhất +1đ
8. Không ai có `remainder = 0` được nhận +1đ khi còn người `remainder > 0` chưa nhận
9. `Σ exact_shares == total_vnd` chính xác về mặt hữu tỉ

Bất biến 6 đặc biệt quan trọng: nó bắt được mọi chỗ hiện thực lén dùng thứ tự input thay vì thứ tự byte của ID.

---

## 8. Chưa thuộc phạm vi W6

`WriteOff` · `CreditAdjustment` · nhiều người ứng tiền một khoản chi · nhiều loại tiền tệ · bù trừ giữa các khoản chi · `verification_scope`.

Ghi ra để không ai lặng lẽ kéo chúng vào oracle. Chúng thuộc tầng sổ, không thuộc tầng số học.
