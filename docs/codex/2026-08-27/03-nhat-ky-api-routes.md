# Nhật ký nối API routes — 2026-08-27

## Phạm vi và ranh giới

- Worktree duy nhất: `/home/lakiet/mobile-codex2`.
- Nhánh: `codex/api-routes`.
- Không đọc hoặc sửa `/home/lakiet/mobile`; không chạm `/home/lakiet/mobile-codex`.
- Code và comment bằng tiếng Anh; tài liệu này bằng tiếng Việt.
- `domain/` vẫn thuần: không import `db/`, `api/`, `payments/`, FastAPI, Pydantic hoặc SQLAlchemy.

Mục tiêu của lát cắt là nối allocator → sổ → đợt thu → capability/VietQR → trang khách → hai loại event thanh toán. Route chỉ điều phối qua `ApiService`; tiền do domain tính, request/response do Pydantic kiểm ở biên API, persistence do `ApiRepository` đảm nhiệm.

## Bảy endpoint

### 1. `POST /expenses`

- Nhận `ExpenseInput`; mọi trường `*_vnd` là strict integer. Chuỗi số, float và bool bị Pydantic từ chối trước domain.
- Chuyển UUID wire sang chuỗi ID của hợp đồng ADR-0004 rồi gọi `app.domain.allocator.allocate()`.
- Chỉ tạo stable `Expense` identity để có `expense_id`; **không** tạo `ExpenseVersion`, `ConfirmedAllocation` hoặc nghĩa vụ.
- Trả lại proposal tự chứa cùng allocations, exact shares, rounding gainers và warnings.

Proposal tự chứa là lựa chọn bắt buộc vì schema hiện không có bảng `ExpenseProposal`. Client gửi lại đúng proposal và `expected_allocations` khi confirm; server luôn chạy allocator lại và từ chối nếu allocations khác thứ người dùng đã xem.

### 2. `POST /expenses/{id}/confirm`

- Gọi quyền `confirm_expense_proposal` với predicate membership theo context.
- Chạy allocator lại; không tin allocations do client gửi.
- Ghi transaction gồm `ExpenseVersion`, item/share/surcharge/discount và một `ConfirmedAllocation` cho mỗi participant.
- Scalar roll-up subtotal/fee/VAT/shipping/discount được `app.domain.expense.component_rollups()` tính; route không cộng tiền.
- `acknowledge_as_advancer=true` là hành động tường minh thứ hai: gọi riêng `acknowledge_advancer_role`, chỉ qua khi actor đúng `paid_by_id`. Vì vậy cổng 1 không tự thay cổng 2.

### 3. `POST /batches`

- Gọi `create_batch`, rồi `freeze_batch` qua bảng quyền tập trung. Người tạo trở thành owner trước khi domain đánh giá freeze.
- Chỉ lấy phiên bản khoản chi mới nhất, đã confirm, chưa có allocation dương nào được đưa vào `CollectionObligationSource`.
- Với từng expense version, gọi `obligations_from_allocations()`; sau đó gọi `merge_obligations()` để chỉ cộng cùng cặp `sender → recipient`, không bù trừ hướng ngược hoặc khác recipient.
- Gọi `transition("accruing", "freeze", context)`.
- Ghi batch/version, snapshot tài khoản nhận, obligation và provenance allocation trong một transaction.
- Mỗi obligation có `due_at` và số tiền nguyên đồng; không có cột trạng thái nghĩa vụ.

Nếu thiếu BankRecipient, domain vẫn buộc caller chọn cách xử lý. Schema hiện chưa có loại batch `blocked_recipient_setup`, nên adapter trả 409 thay vì âm thầm bỏ nghĩa vụ hoặc tạo obligation thiếu snapshot.

### 4. `POST /batches/{id}/publish`

- Gọi quyền `publish_batch` với `owns_batch` và eligibility context.
- Gọi trực tiếp `unmet_publish_gates()` cho ba cổng: advancer ack, snapshot hợp lệ, delivery method; sau đó gọi `transition(..., "publish", ...)`.
- Mỗi sender nhận đúng một `CollectionEnvelope` trong đúng một batch version.
- Token tạo bằng `secrets.token_urlsafe(32)`; database chỉ lưu SHA-256 digest. Raw token chỉ trả đúng lúc publish.
- Mỗi obligation gọi `app.payments.vietqr.build_payload()` với integer VND.
- Không tự chuyển batch sang `collecting`; mốc đó thuộc hành động expose capability, endpoint hiện chưa có.

### 5. `GET /g/{token}`

- Hash token rồi query đúng `GuestLink → CollectionEnvelope → obligations` cùng sender và batch version.
- Gọi quyền `view_guest_envelope` với vai trò capability `guest`.
- Projection dữ liệu thô được đưa qua `app.web.guest_view.build_guest_view()`.
- Template `guest.html` chỉ nhận `view`, neutral preview và token dùng cho form; không nhận ORM row, group balance, member list hoặc dữ liệu nhóm thô.
- Response đặt `Cache-Control: no-store`, `Referrer-Policy: no-referrer`, `X-Robots-Tag: noindex, nofollow`.

### 6. `POST /g/{token}/da-chuyen`

- Nhận Pydantic form gồm `obligation_id` và idempotency key tuỳ chọn.
- Repository chỉ resolve obligation nếu nó thuộc đúng sender và batch version của capability.
- Gọi quyền `report_payment` với ba predicate: đúng capability, link active, còn report budget.
- Ghi `PaymentReport` với số tiền của obligation. Response vẫn suy ra `outstanding` nếu chưa có `ReceiptConfirmation`; self-report không tham gia công thức trạng thái.
- Form trình duyệt nhận `303` quay lại chính trang guest (POST/Redirect/GET); client API nhận Pydantic JSON khi không yêu cầu `text/html`.

### 7. `POST /obligations/{id}/confirm-receipt`

- Nhận positive strict integer VND, idempotency key bắt buộc và `payment_report_id` tuỳ chọn.
- Gọi quyền `confirm_receipt`; predicate chỉ đúng khi actor là `recipient_id` của chính obligation.
- Ghi append-only `ReceiptConfirmation`.
- Trạng thái response gọi `app.domain.ledger.obligation_status()` trên tổng các receipt event; không lưu enum trạng thái vào obligation.
- Cùng idempotency key + cùng payload trả cùng event; tái sử dụng key cho payload khác trả 409.

## Quyền tập trung

Không route nào tự quyết bằng kiểu `if role == ...: allow`. Các fact như `actor.id == batch.owner_id` chỉ là context đưa vào `permissions.denial_reason()`; quyết định allow/deny nằm ở đúng một bảng trong `app.domain.permissions`.

Các action bổ sung cho lát cắt: `create_batch`, `view_guest_envelope`, `report_payment`, `confirm_receipt`. Test HTTP ghi lại lời gọi permission ở confirm và kiểm các denial path của member, owner, guest scope và recipient.

## Capability scope — hoàn tất việc C

Thêm `app.domain.capability.capability_scope()`:

- từ chối tập rỗng;
- từ chối obligation khác sender;
- từ chối obligation khác batch version;
- từ chối obligation trùng;
- trả tuple ID canonical để biểu diễn tập bất biến.

Database đã làm phần còn lại: batch version, obligation và envelope là append-only; `CollectionEnvelope` unique theo `(batch_version_id, sender_id)`; `GuestLink` chỉ trỏ một envelope. Cả publish và guest query đều gọi/tuân contract scope này.

## Repo guard SECRET — hoàn tất việc A

Thêm ba rule không allowlist/annotation được:

- `github-token`: token prefix GitHub cổ điển và fine-grained;
- `aws-access-key-id`: `AKIA*`/`ASIA*`;
- `aws-secret-access-key`: secret 40 ký tự cạnh tên field tương ứng.

Finding chỉ in `<redacted-secret> (chars=N)`, vị trí và path đã che. Test unit + staged integration chứng minh raw credential và raw path không xuất hiện trong stdout/stderr. Đây vẫn chỉ là mitigation: chưa phủ mọi provider, private key, JWT, password hoặc token bị làm rối; credential đã lộ vẫn phải revoke/rotate.

## Kiểm thử

### Kết quả

- API/domain/service suite: `172 passed, 4179 subtests passed` sau khi thêm test roll-up và POST/Redirect/GET.
- Repo guard: `27 passed, 29 subtests passed`.
- Ruff check/format, `compileall`, import-boundary và `git diff --check` nằm trong checklist trước commit.

### Vì sao test API dùng fake repository

Không dùng SQLite. Schema production phụ thuộc PostgreSQL-specific `JSONB`, regex check, partial index, view tính progress và trigger append-only. SQLite bỏ qua hoặc mô phỏng sai các bảo đảm đó, tạo green test giả.

Fake repository có trạng thái, không phải mock trả hằng: nó lưu expense identity, confirmed version/allocation, batch, obligation, capability digest, PaymentReport và ReceiptConfirmation; nhờ đó test chạy trọn luồng HTTP và kiểm self-report không đóng khoản. Giới hạn: fake **không chứng minh** SQL thực thi được, lock chống race, trigger append-only, partial unique index hoặc migration chạy trên PostgreSQL. Docker CLI có mặt nhưng daemon từ chối quyền truy cập socket, nên phiên này không thể khởi động PostgreSQL/container; cần integration job PostgreSQL riêng trước deploy.

Runner hiện tại còn có lỗi môi trường: thread executor Python 3.13 deadlock ngay cả với `asyncio.to_thread(lambda: 1)`. Test ASGI dùng HTTPX transport và chỉ trong fixture fake thay adapter thread bằng thực thi inline. Production route vẫn là sync FastAPI bình thường; workaround không nằm trong app code.

## Giới hạn và nợ còn lại — không che

1. **Auth chưa production-ready.** Schema chưa có Account/Session/Membership. `X-Actor-ID`, `X-Actor-Roles`, `X-Actor-Contexts` hiện là adapter cho upstream auth; public deployment chỉ an toàn nếu trusted gateway xoá header từ client rồi tự điền fact đã xác thực. Chạy app trực tiếp ngoài internet cho phép giả header và là blocker.
2. **Eligibility mới là proxy.** Chưa có claim/identity tables trong slice; `all_recipients_eligible` hiện dùng active recipient-confirmed bank snapshot là fact mạnh nhất có sẵn. Nó không chứng minh PersonStub claim hợp lệ.
3. **Tên hiển thị chưa có nguồn.** Schema không có profile/bank registry; production guest projection phải fallback UUID hoặc account holder name/bank BIN. Chưa đạt chất lượng participant-facing.
4. **Dispute/object chưa có bảng.** Guest view đặt objection budget bằng 0; hai nút phản đối hiện chưa có endpoint trong bảy route.
5. **Advancer ack chưa có endpoint độc lập.** Có thể ack tường minh cùng confirm nếu chính advancer là actor. Nếu một member khác confirm và để pending, publish bị chặn đúng, nhưng cần route/capability riêng để advancer ack sau đó.
6. **Blocked recipient split chưa có persistence model.** Chọn `split_to_blocked_batch` vẫn trả 409; không làm mất obligation.
7. **Raw capability chỉ trả lúc publish.** Chưa có endpoint rotate/revoke/expose; batch giữ `published`, chưa tự nhận là `collecting`.
8. **OffsetProposal chưa làm.** Việc B kéo theo model + migration + lifecycle + acceptance events; không nhét vội vào PR đường găng khi chưa có thời gian chạy PostgreSQL integration.

Các giới hạn 1–7 không phủ định test của bảy đường đi đã làm, nhưng chúng chặn tuyên bố “sẵn sàng public production”.
