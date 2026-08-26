# Điều lệ làm việc — team 2 engineer + leader

> Kết quả hội tụ sau 4 vòng debate Claude ↔ Codex, 2026-08-26.
> Tài liệu này là **nguồn sự thật về quy trình**. Đổi nó cần một ADR trong `docs/decisions/`.

## 1. Vai

| Vai | Ai | Chịu trách nhiệm |
|---|---|---|
| Leader | Chủ sản phẩm | Tuyển nhóm, chỉ định/đóng vai operator, thuê counsel, ngân sách và khuyến khích, giám sát tiền thật giữa participant, xử lý sự cố thực địa, **ký quyết định gate** |
| Engineer | Claude | Giao thức đo, thiết kế thí nghiệm, chính sách dữ liệu, phân tích và gate packet |
| Engineer | Codex | Study instrument, threat model, repo guard, OCR harness |

**Leader lane là đường găng thật.** Hai engineer chỉ sản xuất *công cụ* và *giao thức*. Không engineer nào bù được việc chưa tuyển được nhóm hoặc chưa có operator bằng cách viết thêm code.

Engineer không phủi trách nhiệm kỹ thuật khi công cụ lỗi, kể cả công cụ dùng một lần.

## 2. Nhánh

```
<owner>/p0-w<N>-<slug>            ví dụ  codex/p0-w9a-repo-guard
<owner>/review-p0-w<N>-<slug>     ví dụ  claude/review-p0-w9a-repo-guard
```

`<slug>` mơ hồ kiểu `backend` / `research` là sai. **Work ID là thứ nối branch ↔ review ↔ nhật ký ↔ protocol_version.**

Reviewer tạo review-only branch từ HEAD của nhánh đích, thêm file dưới thư mục của mình, rồi merge commit review vào nhánh đích. Review-only PR **miễn review đệ quy** — nhưng chỉ khi CI xác nhận diff chỉ chứa Markdown review, không executable, không binary, không symlink.

## 3. Hai cổng tách biệt

**MERGE-GATE** — được phép merge vào `main`:
- reviewer đã ra verdict, không còn blocker mở
- test/kết quả tái lập được

**FIELD-GATE** — được phép chạm người thật và dữ liệu thật:
- W9a (repo guard) xong
- W9 (chính sách dữ liệu) xong + **counsel checkpoint đã qua**
- W4a (threat model nghiên cứu) xong
- W0 (protocol + measurement contract) đã đóng băng ở một `protocol_version`
- W6 differential gate xanh — nếu phiên đó có công cụ tính hoặc đề xuất số tiền
- leader lane sẵn sàng: operator đã chỉ định, nơi lưu dữ liệu ngoài repo, kế hoạch sự cố/hoàn trả, đã chạy dry run

Merge được **không** đồng nghĩa được ra thực địa.

## 4. Quyền chặn

Blocker chỉ hợp lệ nếu thuộc một trong năm loại:

1. vi phạm spec hoặc vi phạm cổng
2. sai tiền
3. quyền riêng tư / bảo mật / consent
4. làm hỏng tính hợp lệ của thí nghiệm
5. kết quả hoặc test không tái lập được

Mọi thứ khác — đặt tên, phong cách, "tôi thích cách kia hơn" — là **suggestion**, không chặn được.

Blocker phải kèm: dẫn chứng · hậu quả · tiêu chí cụ thể để gỡ chặn.

**SLA 1 ngày làm việc cho phản hồi review đầu tiên** (không phải cho phê duyệt). Quá hạn → leader can thiệp.

Review hai lần: **protocol/contract trước khi implement hoặc thu dữ liệu**, và **artifact trước khi merge**. Review sau khi đã thu dữ liệu người thật không sửa được thiết kế thí nghiệm.

Leader phá được thế bế tắc về đánh đổi sản phẩm. Leader **không** phá được bằng cách: miễn consent · chấp nhận sai tiền · đổi ngưỡng sau khi đã thấy kết quả. Đổi protocol thì tăng `protocol_version` và **không gộp dữ liệu cũ**.

## 5. Tài liệu

```
docs/protocol/              giao thức thực địa — có version, snapshot bất biến
docs/decisions/             ADR — mọi thay đổi protocol/gate/phạm vi
docs/team/                  điều lệ + backlog
docs/claude/<YYYY-MM-DD>/   nhật ký + review việc của Codex
docs/codex/<YYYY-MM-DD>/    nhật ký + review việc của Claude
docs/superpowers/specs/     spec sản phẩm — ĐÓNG BĂNG cho tới sau gate
```

Mỗi `protocol_version` là **snapshot bất biến**. Không sửa `v1` tại chỗ; ADR cho phép tạo `v2` và dữ liệu mới trỏ tới `v2`. ADR phải được duyệt **trước** khi thay đổi có hiệu lực — không hợp thức hoá hậu nghiệm.

Review doc bắt buộc có: **commit SHA · protocol_version · verdict · blocker còn mở · bằng chứng đã xem.**

Nhật ký là nhật ký, **không phải nguồn quyết định**. Quyết định sống ở `docs/decisions/`.

### Nhịp ghi
- **Hằng ngày** — chỉ trong những ngày thực sự có build work.
- **Hằng tuần** — trong các tuần chạy thực địa với allocation giảm.
- **Theo sự kiện, ngay lập tức** — mỗi thay đổi protocol · mỗi sự cố · mỗi lần mở block tuyển · mỗi interim gate.

## 6. Dữ liệu người tham gia — tuyệt đối

**Không bao giờ** đưa vào Git: ảnh bill · số tài khoản · tên người tham gia · transcript thô · file export.

Dữ liệu thật nằm **ngoài repository và ngoài worktree**, có kiểm soát truy cập. Thư mục bị `.gitignore` là chưa đủ.

Kiểm tra tự động (W9a) là **lớp giảm thiểu, không thay thế quy tắc trên** — không scanner nào nhận ra mọi tên người Việt hay PII nằm trong ảnh nén.

Không ai trong team — leader, operator, engineer — **giữ hoặc chuyển tiền hộ**. Nghĩa vụ giữa participant phải là nghĩa vụ thật, tự họ chuyển trực tiếp cho nhau. Không có nghĩa vụ thật thì rơi vào bẫy "tạo khoản nợ giả" mà mục 13.6 của spec cấm.
