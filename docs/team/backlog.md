# Backlog Giai đoạn 0 — phân công

> Chốt 2026-08-26 sau 4 vòng debate. Đổi phân công cần ADR.
> Căn cứ: `docs/superpowers/specs/2026-08-25-group-hangout-ai-design.md` mục 13, 15, 16.

## Nguyên tắc bao trùm

**Chưa được viết product code.** Mục 13 chỉ cho phép: công cụ nghiên cứu dùng một lần, threat model, và phác schema trên giấy. Thứ tự xây ở mục 14.3 **chỉ mở sau khi qua cổng hành vi 13.3**.

Ranh giới dễ trượt nhất, ghi ở đây để cả hai tự soi:
- Study instrument log **sự kiện quan sát được** (`operator_action_started`), **không** log trạng thái sản phẩm giả định (`CollectionBatch.published`).
- "Trên giấy" không phải cửa sau để thiết kế sản phẩm sớm.
- Không có quyền tái sử dụng. Mặc định mọi thứ trong Giai đoạn 0 sẽ bị viết lại.

## Bảng phân công

| ID | Việc | DRI | Reviewer | Chặn cái gì |
|---|---|---|---|---|
| **W0** | Field protocol · measurement contract · preregistration · bias declaration · stopping rule | Claude | Codex | W1, W3 |
| **W9a** | Repo guard: lưu ngoài repo · `.gitignore` · pre-commit · CI check · binary allowlist · runbook nếu PII lọt history | Codex | Claude | Dữ liệu thật vào repo/worktree; công cụ chưa an toàn |
| **W9** | Chính sách dữ liệu: consent · access · retention/deletion · incident response · gói câu hỏi cho counsel | Claude | Codex **+ counsel ngoài** | FIELD-GATE |
| **W4a** | Threat model + data-flow của **hệ thống nghiên cứu đang chạy** | Codex | Claude | FIELD-GATE |
| **W1** | Study instrument: mock UI + timer + append-only operator log + 4 nhãn thao tác + `protocol_version` + tách 2 lane | Codex | Claude | Field waves |
| **W6a/W6b** | Hai allocator độc lập + golden vector + differential gate | Đồng sở hữu | Lẫn nhau | Phiên nào mà **công cụ tính hoặc đề xuất số tiền** (không chặn baseline) |
| **W3** | Experiment suite: text vs form (chính) · chip vs gõ · invocation riêng/chung · thứ tự thông điệp · đo hiểu đúng năng lực ≥80% | Claude | Codex | Các experiment session tương ứng; kết quả input-path + onboarding chặn quyết định 13.3 |
| **W2** | OCR Gate A — 3 metric kỹ thuật | Codex | Claude | Chỉ chặn **đường ảnh bill**, không chặn v1 |
| **W7** | Analysis pipeline · gate packet · giới hạn suy luận | Claude | Codex *(tái lập độc lập toàn bộ số liệu từ input đã khoá, không chỉ đọc narrative)* | Quyết định gate |
| **W8** | Pricing/WTP trên **mẫu tách biệt** | Claude | Codex | — |
| **W4b** | Phác schema sản phẩm | **HOÃN** tới sau W7, **chỉ nếu PASS**. Claude draft, Codex review invariants | | Không chặn và không ảnh hưởng dữ liệu Giai đoạn 0 |
| — | Tuyển nhóm · làm operator · thuê counsel · ngân sách · giám sát tiền thật · sự cố thực địa · **ký quyết định gate** | **LEADER** | | **Tất cả** |
| **W9a-E** | Bật enforcement: required check `repo-guard` · PR bắt buộc · chặn direct push · chạy PR dry-run âm tính và xác nhận **bị chặn thật** · lưu bằng chứng cấu hình (không PII) vào gate packet | **LEADER** | Codex xác minh | **FIELD-GATE** |

### Vì sao W0 thuộc Claude chứ không Codex
Codex sở hữu W1/W2/W4a/W9a. **Người viết giao thức đo không nên là người xây công cụ hiện thực giao thức đó** — công cụ sẽ lặng lẽ định hình lại giao thức. Codex review W0 với quyền chặn đầy đủ.

### Vì sao W6 dùng hai bản độc lập thay vì reviewer/implementer
Allocator nhỏ, tất định, tính đúng là tuyệt đối. Đọc code là biện pháp yếu — reviewer dễ đọc theo logic người viết. Hai bản mù rồi differential test biến review thành **phép đo khách quan**.

Quy trình W6, theo đúng thứ tự:
1. Hai bên chốt black-box contract, miền input hợp lệ, golden vector tính tay — **chưa viết code**.
2. Checkout hai nhánh độc lập, **không đọc code của nhau**.
3. Một bản ưu tiên exact rational / rõ ràng; bản kia ưu tiên integer implementation.
4. Property test + seeded differential fuzzing. Counterexample lưu vào Git ở dạng **tổng hợp, an toàn**.
5. Shrink mỗi failure về ca nhỏ nhất.
6. Phân loại failure: **spec ambiguity · bug implementation · bug harness · generator sinh input ngoài miền · khác biệt kiểu số/overflow**. Không phải mọi bất đồng đều là lỗi spec.
7. Chỉ sau khi kết quả đóng băng mới review code chéo.

⚠️ **Hai bản đồng ý KHÔNG chứng minh đúng** — cả hai có thể cùng hiểu sai một câu spec hoặc cùng mắc lỗi largest-remainder quen thuộc. Golden vector tính tay là bắt buộc.

Ca phải quyết trước, không để fuzzer tự định nghĩa: tập người rỗng · tổng = 0 · tổng dương nhưng không có người · mọi weight = 0 · ID trùng · weight âm · advancer ngoài tập tham gia · tổng nhỏ hơn số người · số nguyên rất lớn.

### Phụ thuộc chéo W2 ↔ W3
Gate A có 5 chỉ số. **W2 không sở hữu được cả 5.**
- W2 (kỹ thuật): độ chính xác tổng tiền · ghép dòng món–giá · sanitizer bỏ sót trường nhạy cảm.
- W3 (cần người thật): nhanh hơn nhập tay ≥30% · số lỗi vật chất người dùng phải sửa.
- W7 hợp nhất thành **một** Gate A packet.
- Image arm của W3 chỉ mở **sau khi** W2 field-ready.

## Thứ tự phụ thuộc

```
W0 protocol + measurement contract ─┬─> W1 study instrument ──────┐
W9 / W9a / W4a governance ──────────┼─> W2 OCR ─> W3 experiments ─┤─> field waves
W6a/W6b reference allocator ────────┘                             │
W8 pricing (mẫu tách biệt, song song về thời gian) ───────────────┤
                                                                  v
                                                            W7 gate packet
                                                                  v
                                     chỉ khi PASS → mục 14.3 → W4b
```

⚠️ **Governance (W0/W9/W9a/W4a) chặn DỮ LIỆU THẬT và thực thi thực địa — KHÔNG chặn việc build và test W1/W2 bằng fixture tổng hợp.** *(Suggestion 3 của Codex, 2026-08-26.)* Mọi mũi tên ở trên là ràng buộc về thứ tự **chạm người thật**, không phải ràng buộc về thứ tự viết code.

## Cửa sổ rỗng của engineer — xử lý trung thực

Dựng công cụ mất ~4–6 tuần. Field waves mất ~12–16 tuần. Ở giữa có một cửa sổ dài.

**Không** làm mục 14.3 sớm để giữ người bận — đó là dùng "giấy" làm cửa sau cho product design.
**Không** giả vờ team phải bận 100%. *Giảm allocation engineer là quyết định quản trị trung thực, không phải thất bại vận hành.*

Việc hợp lệ trong cửa sổ đó:
- kiểm tra chất lượng dữ liệu — **không** tối ưu hậu nghiệm theo kết quả
- calibration nhãn operator, đo mức đồng thuận
- sửa study instrument, có `protocol_version` mới
- OCR / sanitizer (W2 độc lập với cổng hành vi)
- diễn tập analysis trên **dữ liệu tổng hợp**
- tabletop: sự cố, xoá dữ liệu, khôi phục
- adversarial testing chính hệ thống nghiên cứu

**Interim gate** đã đăng ký trước: khi một cohort có ≥10 nhóm thực sự có cơ hội lặp hợp lệ **và** block review đã tới hạn → chạy gate.
- PASS → một engineer bắt đầu prototype tự phục vụ rẻ nhất **trên participant mới**; engineer kia giữ field study.
- 4–5/10 → **không** code sản phẩm; chuyển sang chẩn đoán.
- <4/10 → dừng wedge. **Không chế backlog để bảo vệ utilization.**

Xem interim result phải đúng block/stopping rule đã đăng ký. Không nhìn số mỗi tuần rồi đổi protocol cho đẹp.
