# ADR-0015 — Bỏ đường thanh toán: sản phẩm nói phần của mỗi người rồi dừng

- **Trạng thái:** 🟢 **ĐÃ CHẤP NHẬN VÀ ĐÃ HIỆN THỰC** 2026-09-03
- **Quyết định bởi:** Lead
- **Hiện thực:** PR #515 (nhánh `claude/p0-w-bo-scope-thanh-toan`)
- **Thay đổi phạm vi sản phẩm**, không phải thay đổi kỹ thuật. Đọc trước khi ai đó "khôi phục lại QR cho tiện".

## Quyết định

Sản phẩm **thông báo mỗi người phải bỏ ra bao nhiêu và vì những khoản nào**, rồi dừng. Chuyển tiền bằng cách nào — app ngân hàng nào, số tài khoản nào, tiền mặt hay không — là chuyện giữa hai người, **không thuộc phạm vi**.

Đi theo quyết định đó, những thứ sau **bị gỡ**, không phải hoãn:

| Gỡ | Cái gì |
|---|---|
| `app/payments/` | Dựng chuỗi VietQR EMVCo + CRC, danh mục ngân hàng |
| `app/web/qr.py` | Vẽ payload thành ảnh PNG cho trang khách |
| `app/domain/bank_account.py` | Chuẩn hoá và kiểm định dạng số tài khoản |
| 2 bảng | `bank_recipients`, `bank_recipient_snapshots` |
| 1 cột | `collection_obligations.bank_recipient_snapshot_id` (NOT NULL) + khoá ngoại ghép |
| 4 route | `POST/GET /bank-recipients*`, `PUT/GET /people/{id}/bank-recipient` |
| Client | `ui/MaVietQr.tsx`, `ui/vietqr.ts`, cả màn `tai-khoan/`, `packages/shared/banks.json` |

## Cái gì ở lại, và vì sao

**Trang khách `/g/{token}` ở lại.** Người không cài app vẫn cần biết phần của mình. Nó nói ai được trả, bao nhiêu, vì bữa nào — và nói thẳng một câu mà trước đây không cần: *«RuDi chỉ tính phần của bạn. Chuyển bằng cách nào là chuyện giữa bạn và X.»* Một trang hiện số tiền rồi im lặng sẽ khiến người đọc tưởng trang lỗi.

**Vòng «đã chuyển» / «đã nhận» ở lại.** `payment_reports` và `receipt_confirmations` không phải đường thanh toán, chúng là cách nhóm theo dõi ai đã trả. Bỏ chúng thì nhóm mất luôn khả năng biết còn ai chưa trả, và đó là phần đau mà spec nói là đau nhất.

**Đợt thu, nghĩa vụ, envelope ở lại.** Nghĩa vụ vẫn đủ nghĩa sau khi bỏ cột tài khoản: `sender_id`, `recipient_id`, `amount_vnd`, `due_at` vẫn nói được ai nợ ai bao nhiêu, tới khi nào.

**`ui/qr.ts` ở lại.** Nó là encoder QR chung, và người dùng nó là **mã kết bạn** (F05, `MaCuaToi`), không phải thanh toán. Xoá nó là xoá nhầm một tính năng khác.

## Ba luật theo nhau đổ, và đã đổ

Đây là phần dễ bỏ sót nhất khi gỡ, nên ghi ra:

1. **Cổng publish `valid_bank_recipient_snapshot_required`** — không còn tài khoản để đóng băng thì cổng luôn xanh. Một cổng không bao giờ đỏ được là một dòng chữ trông như bảo vệ. Đã bỏ; `unmet_publish_gates` còn hai cổng.
2. **Predicate `all_recipients_eligible` của `publish_batch`** — nghĩa là «mọi người nhận đều có tài khoản dùng được». Đã bỏ; sở hữu đợt thu là toàn bộ phép kiểm.
3. **Luật «người nhận chưa sẵn sàng» (spec 8.4)** — bắt người tổ chức chọn *chờ tất cả* hay *tách nhóm bị chặn*. Không còn trạng thái đó nên không còn lựa chọn nào để bắt chọn. Đã bỏ cùng `UNREADY_CHOICES`.

Cộng một action quyền chết theo: `revoke_capability_own_recipient_account` — người nhận thu hồi một capability *vì nó mang tài khoản của họ*. Không còn tài khoản trong envelope thì không còn rủi ro đó và không còn chủ thể đó.

## Cái này KHÔNG chứng minh gì

- **Không chứng minh người dùng thật thấy đủ.** Rất có thể người ta mở trang khách, thấy «250.000đ trả cho Minh» và hỏi ngay «chuyển vào đâu?». Câu trả lời là «hỏi Minh», và đó là quyết định của Lead chứ không phải phát hiện từ người dùng.
- **Không chứng minh việc theo dõi «ai trả rồi» còn dùng được.** Vòng tự khai vẫn nguyên, và `receiver_confirmed` vẫn **không phải** bằng chứng ngân hàng (không đổi so với trước).
- **Ảnh trong README chưa vẽ lại.** `docs/assets/luong-chia-tien.jpg` và mockup trong `product/` vẫn có mã QR. Chúng là hiện vật đóng băng theo sha256 trong repo guard allowlist; alt-text đã sửa, ảnh thì cần một lượt thiết kế riêng.

## Đường lùi

Không có đường lùi rẻ. Migration `e7a1c4d90b52` dựng lại được schema cũ nhưng **từ chối chạy khi bảng nghĩa vụ còn dòng**: cột cũ là `NOT NULL` và không có giá trị nào để điền cho một nghĩa vụ đã tồn tại. Bịa một bản chụp tài khoản để thoả ràng buộc là cách tệ nhất để lùi một bảng tiền.

Muốn quay lại thì mở ADR mới. Đừng khôi phục bằng cách revert commit: giữa chừng có một migration đã chạy trên dữ liệu thật.
