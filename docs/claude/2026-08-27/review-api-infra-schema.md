# Review schema hạ tầng API (Codex) — dở dang

- **Verdict:** **`REQUEST_CHANGES`**
- **Blocker còn mở:** **3**
- **Trạng thái task:** Codex báo `failed` sau 12m19s. Đã giao `db/` + migration + docker-compose; **chưa** giao `api/`, `payments/vietqr.py`, test, CI.
- **Bằng chứng:** đọc `models.py` (575 dòng) và migration đầu tiên; chạy allocator thật lên golden vector G06 rồi đối chiếu với CHECK constraint

## Làm tốt

**Mọi cột tiền là `BigInteger`.** Không một `Numeric`, `Float` hay `DECIMAL` nào trong 575 dòng. Đây là ràng buộc dễ trôi nhất và nó được giữ.

CHECK constraint ở tầng DB chứ không chỉ ở tầng ứng dụng: không âm, `version_chain` ép `previous_version_number = version_number - 1`, và một CHECK ép chính đẳng thức đối chiếu. Sổ được bảo vệ ngay cả khi có người viết thẳng vào Postgres.

`CollectionBatchVersion` và `CollectionObligationSource` là hai bảng Codex tự thêm ngoài spec. **Tôi đồng ý.** Lý do nó đưa ra đúng: một cột `version` trơ không ghim được *tập nghĩa vụ* và *snapshot tài khoản nhận tiền* vào một phiên bản bất biến. Spec mục 6.5 đòi `BankRecipientSnapshot` phải "đóng băng trong phiên bản batch" — không có bảng nối thì không đóng băng được cái gì.

## Blocker

### D-01 — schema TỪ CHỐI một khoản chi mà allocator CHẤP NHẬN

Mâu thuẫn trực tiếp giữa hai artifact đã đóng băng.

```
ADR-0004 quyết định #9   →  total_vnd = 0 là HỢP LỆ
golden vector G06        →  total 0, participants a+b  →  {a: 0, b: 0}
allocator thật           →  chạy được, trả {'a': 0, 'b': 0}

models.py:115            →  CheckConstraint("total_amount_vnd > 0")
migration:181            →  ck_expense_versions_total_positive
```

Một khoản chi qua được allocator sẽ **bị Postgres từ chối lúc ghi**. Lỗi này chỉ lộ ra ở runtime, sau khi người dùng đã bấm xác nhận.

**Tiêu chí gỡ:** đổi thành `total_amount_vnd >= 0`. Nếu bạn cho rằng khoản chi bằng 0 **không nên** tồn tại thì đó là tranh luận với `ADR-0004` — mở ADR sửa hợp đồng, đừng để hai artifact nói ngược nhau.

### D-02 — không có bảng nào lưu MÓN

`grep -c "expense_items\|item_id"` trên `models.py` trả về **0**.

Allocator nhận `items` kèm `shared_by` — ai ăn món nào. Schema không lưu chúng ở bất kỳ đâu. Hệ quả:

- Không dựng lại được màn drill-down "món nào của ai"
- Spec mục 3 đòi: nếu người dùng sửa tổng của một người khiến chi tiết món không còn khớp thì drill-down phải **được đánh dấu "giải thích cũ" hoặc tính lại**. **Không lưu món thì không làm được cả hai.**
- `verification_scope = items_reviewed` trở thành một cờ không tham chiếu tới thứ gì

Ghi rõ giới hạn của blocker này: **số dư vẫn tính lại được**, vì `ConfirmedAllocation` lưu số tiền theo từng người và đó mới là sổ chính thức (spec mục 3). Bất biến 3 **không** bị vi phạm. Cái mất là **phần giải thích**, không phải phần tiền.

**Tiêu chí gỡ:** thêm `ExpenseItem` (thuộc `ExpenseVersion`) và `ExpenseItemShare` (món ↔ người). Hoặc tuyên bố tường minh rằng v1 chỉ hỗ trợ `verification_scope = totals_only` và bỏ enum kia đi — nhưng phải chọn một, không để lửng.

### D-03 — phụ phí và giảm giá bị làm phẳng, mất `mode` và `scope`

| Allocator | Schema |
|---|---|
| N phụ phí, mỗi cái `mode: proportional \| even` | 3 cột vô hướng `fee` · `vat` · `shipping`, **không có mode** |
| N giảm giá, mỗi cái `scope: global_proportional \| item` | 1 cột vô hướng `discount`, **không có scope** |

Hai khoản chi có **cùng** năm con số nhưng khác `mode` sẽ cho **phân bổ khác nhau**, và schema lưu chúng giống hệt nhau.

Cụ thể, dùng chính golden vector: `G10` (phụ phí 10000 `proportional`) và một biến thể `even` — cùng tổng 110000, cùng subtotal 100000, cùng fee 10000, nhưng allocator trả `{a: 66000, b: 44000}` với `proportional` và `{a: 65000, b: 45000}` với `even`. Ghi vào DB rồi thì **không phân biệt được nữa**.

**Tiêu chí gỡ:** `ExpenseSurcharge` và `ExpenseDiscount` là bảng con của `ExpenseVersion`, giữ nguyên `mode` và `scope`. Năm cột vô hướng hiện tại giữ lại được như **giá trị dẫn xuất** cho truy vấn nhanh, nhưng không được là nguồn sự thật.

## Việc còn thiếu, không tính là blocker

`api/` routes · `payments/vietqr.py` · `tests/db/` · `tests/api/` · test import boundary · CI workflow. Task dừng giữa chừng.

## Nguyên nhân gốc đáng ghi lại

Ba blocker đều cùng một dạng: **schema được thiết kế từ mục 6 của spec, không phải từ `ADR-0004`.** Mục 6 liệt kê thực thể; `ADR-0004` mới là thứ định nghĩa chính xác một khoản chi gồm những gì.

Đây là chi phí thật của việc tôi viết `domain/` song song với bạn viết `db/`. Đúng ra tôi phải đưa hợp đồng allocator làm đầu vào bắt buộc của schema ngay từ prompt.
