# Review tài liệu Claude — 2026-08-26

## Metadata bắt buộc

- **Commit SHA:** `1c9f18f3d45e6275235d7fbbe528b5aae0a9d643`
- **protocol_version:** `n/a` — chưa có snapshot dưới `docs/protocol/`; bốn artifact là governance/ADR trước protocol
- **Verdict:** **YÊU CẦU SỬA**
- **Blocker còn mở:** **2**
- **Bằng chứng đã xem:** toàn bộ bốn file ở SHA trên; đối chiếu chéo với spec cùng commit, mục 13.1–13.6, 15 và 16; xác minh working copy của bốn file không khác SHA được review

## Phạm vi review

1. `docs/team/charter.md`
2. `docs/team/backlog.md`
3. `docs/decisions/ADR-0001-quy-trinh-va-phan-cong-giai-doan-0.md`
4. `docs/decisions/ADR-0002-chon-bien-the-giai-doan-0.md`

Tôi review tính nhất quán của gate, phân công, quyền chặn, cỡ mẫu và trạng thái quyết định. Tôi không coi việc “đã debate bốn vòng” là bằng chứng tài liệu đúng.

## Blocker còn mở

### B-01 — Required repo-guard check không có DRI kích hoạt trong nguồn quyết định

- **Loại blocker theo charter mục 4:** (1) vi phạm cổng; (3) quyền riêng tư/bảo mật.
- **Dẫn chứng:** `charter.md:35–41` cho phép FIELD-GATE khi W9a “xong” và leader lane sẵn sàng; `backlog.md:20` giao Codex tạo CI check, nhưng leader row ở `backlog.md:30` không có branch protection/required check. `charter.md:80` nói nhật ký không phải nguồn quyết định.
- **Hậu quả:** Engineer có thể giao workflow và W9a bị đánh dấu xong trong khi status check vẫn optional. Local hook bị bỏ qua bằng `--no-verify`; PR vẫn merge được khi scanner đỏ hoặc không chạy. Khi đó FIELD-GATE có thể được hiểu là mở dù hàng rào server chưa thực sự enforce.
- **Tiêu chí gỡ:** ADR được duyệt **trước FIELD-GATE** để cập nhật charter/backlog: giao leader bật required status `repo-guard`, bắt buộc PR, chặn direct push/giới hạn bypass, chạy một PR dry-run âm tính, và lưu bằng chứng cấu hình không chứa PII trong gate packet. Đồng thời định nghĩa rõ “W9a engineering artifact xong” khác “W9a enforcement đã active”.

### B-02 — Miễn review đệ quy dựa trên một CI scope-check chưa có owner/artifact

- **Loại blocker theo charter mục 4:** (1) vi phạm cổng; (5) test/kết quả không tái lập được.
- **Dẫn chứng:** `charter.md:27` miễn review đệ quy cho review-only PR chỉ khi CI xác nhận diff chỉ có Markdown review, không executable/binary/symlink. Không work item nào trong `backlog.md:17–30` sở hữu check này, không có tên check/contract, và base SHA được review chưa có CI artifact để tái lập điều kiện miễn.
- **Hậu quả:** Team có một ngoại lệ MERGE-GATE nhưng không có cơ chế xác định khi nào ngoại lệ hợp lệ. Một review branch có executable, binary hoặc symlink có thể được gọi là “review-only” rồi merge mà không qua review artifact tương ứng.
- **Tiêu chí gỡ:** Hoặc (a) thêm work item/DRI và CI check có test âm tính cho executable, binary, symlink và file ngoài `docs/<reviewer>/<date>/...review...md`, ghi tên required check; hoặc (b) bỏ miễn review đệ quy cho tới khi check tồn tại. Kết quả phải tái lập trên PR dry-run.

## Kết quả đối chiếu không tạo blocker

- Tách MERGE-GATE và FIELD-GATE ở `charter.md:29–43` là nhất quán với ADR-0001 và không đánh đồng merge với ra thực địa.
- Phân biệt mốc Giai đoạn 0 với sàn pilot trong ADR-0002 là đúng với spec: wave/block/opportunity gate ở mục 13.1, còn sàn pilot nằm ở mục 15. ADR-0002 cũng nói rõ 10–15/cohort chỉ cho so sánh mô tả, không chứng minh cohort thắng.
- P0-Gọn được ghi là controlled deviation, chờ leader và không được suy diễn sang cohort ở trọ. Không có cơ sở coi ADR-0002 đã được chấp nhận; status `ĐỀ XUẤT` là đúng.
- ADR-0001 giữ W4b sau gate, tách measurement contract khỏi product schema và tách W8 khỏi Track H; không thấy mâu thuẫn nội bộ đủ loại blocker.
- Các ràng buộc counsel, consent, không giữ/chuyển tiền hộ và nghĩa vụ thật ở ADR-0002 khớp charter/spec.

## Suggestion — không chặn

1. Chuẩn hoá vocabulary verdict (`APPROVE`, `REQUEST_CHANGES`, `REJECT`) trong charter để review automation không phải suy diễn text tự do.
2. Nếu leader chọn P0-Gọn, ADR tiếp theo nên biến “6–10 tuần” thành estimate có assumptions về tỷ lệ nhóm thật sự có repeat opportunity; không biến deadline thành lý do thay observation bằng self-report.
3. Sơ đồ dependency ở backlog nên chú thích governance chặn **dữ liệu thật/field execution**, không chặn việc build/test W1/W2 bằng fixture tổng hợp; ADR-0001 mới nói rõ ngoại lệ này cho W1.

## Verdict cuối

**YÊU CẦU SỬA.** Hai blocker không phải tranh luận phong cách: cả hai là điều kiện gate đang dựa vào CI enforcement nhưng chưa có owner và bằng chứng tái lập. B-01 trực tiếp ảnh hưởng privacy boundary trước dữ liệu thật; B-02 làm ngoại lệ review không kiểm chứng được. Các phần về phạm vi Giai đoạn 0, cỡ mẫu và controlled deviation chưa phát hiện blocker.
