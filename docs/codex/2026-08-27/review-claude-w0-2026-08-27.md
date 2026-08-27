# Review W0 — field protocol v1 của Claude

## Metadata bắt buộc

- **Commit SHA:** `e98fc7ad018764441b6a320e32c8b732a513ef2d`
- **protocol_version:** `v1` — **DRAFT**, chưa được đóng băng
- **Verdict:** **`REQUEST_CHANGES`**
- **Blocker còn mở:** **6**
- **Bằng chứng đã xem:** toàn bộ năm file `docs/protocol/v1/00-` đến `04-` và nhật ký W0 tại đúng SHA trên; đối chiếu với spec mục 13.1, 13.3, 13.6, 15, ADR-0001, ADR-0002, charter và backlog hiện hành. Blob của spec, ADR-0001 và ADR-0002 ở nhánh W0 trùng với blob đang dùng để đối chiếu.

## Phạm vi và kết luận ngắn

Tôi review contract đo, khả năng tái lập gate và ranh giới W1; không review product schema. Hướng thiết kế tổng thể đúng: tách sự kiện quan sát khỏi ontology sản phẩm, giữ log append-only, có `indeterminate`, không xoá attrition, khoá cohort, tách hai lane, coi sender guardrail là quyền phủ quyết và giữ `serious_error = 0`.

Nhưng bản này chưa thể đóng băng. Có một sai lệch trực tiếp làm yếu tử số chính, measurement contract chưa đủ để tính lại các chỉ số đã đăng ký, một ngưỡng spec bị bỏ, và ba quy tắc quyết định vẫn cho phép phân loại hoặc dừng theo hướng có lợi sau khi xem kết quả.

## Blocker còn mở

### W0-01 — Tử số chính đếm quá sớm so với spec

- **Loại blocker theo charter mục 4:** (1) vi phạm spec; (4) làm hỏng tính hợp lệ thí nghiệm.
- **Dẫn chứng:** `00-:62–65` tính `self_initiated` ngay khi organizer tự đưa một khoản mới vào công cụ. `02-:93` lấy nhóm có ít nhất một `self_initiated` làm tử số, dù event này không có trong danh mục. `03-:10–17` dùng tử số đó để mở cổng. Trong khi đó spec mục 15 chỉ tính repeat khi người dùng **xác nhận và publish một đợt thu có ít nhất một nghĩa vụ hợp lệ**; cùng mục còn gọi chỉ số chính là đợt thu thứ hai do người dùng chủ động tạo.
- **Hậu quả:** một draft được nhập rồi bỏ, không xác nhận, không chia sẻ và không có nghĩa vụ hợp lệ vẫn có thể đẩy kết quả từ `5/10` lên `6/10` và mở quyền xây prototype. Mốc không-liên-hệ 48 giờ ở `00-:64,71` cũng chưa có căn cứ hay event contact để kiểm tra; một lời nhắc ở giờ thứ 49 vẫn được tính là tự khởi tạo.
- **Tiêu chí gỡ:** tách tín hiệu chẩn đoán “bắt đầu tự nguyện” khỏi **qualifying repeat** dùng cho gate. Tử số gate phải được suy ra từ chuỗi sự kiện quan sát được tương đương organizer tự bắt đầu → xác nhận → tự chia sẻ/phát đợt thu → có ít nhất một nghĩa vụ thật hợp lệ. Giải quyết rõ câu chữ “hoàn tất” và “publish” trong spec bằng ADR nếu cần, không âm thầm chọn phiên bản yếu hơn. Đóng băng quy tắc loại mọi research contact/prompt, log các contact đó, và có fixture dương/âm chứng minh phép suy ra tử số.

### W0-02 — `02-measurement-contract.md` chưa đủ để tái lập chính các chỉ số nó cam kết

- **Loại blocker theo charter mục 4:** (4) tính hợp lệ thí nghiệm; (5) kết quả không tái lập được.
- **Dẫn chứng:** `00-:30` yêu cầu người thứ hai chỉ đọc log cũng phán quyết được. Tuy nhiên:
  - `02-:93` tham chiếu `self_initiated` và `evaluable` nhưng không định nghĩa event, field hay phép suy ra cho hai trạng thái này;
  - `02-:49–50` không mang bằng chứng cho bốn điều kiện cơ hội ở `00-:36–41`: số người, nghĩa vụ thật, người ứng trước và loại chi phí đã có ở baseline;
  - `session`, `action`, `proposal`, `obligation`, correction và independent relabel không có khoá tham chiếu để join; `label_corrected`/`independent_relabel` không chỉ tới action gốc;
  - `02-:67–68,94` không có `obligation_id`, mốc `due_at`/`capability_exposed_at`, thời điểm nghĩa vụ tới tay participant, hoặc event tranh chấp/`waived`/huỷ hợp lệ để tính đúng tỉ lệ 7 ngày;
  - `organizer_active_time` cần khoảng thời gian chủ động, nhưng contract chỉ có các sự kiện tức thời và `session_started/ended`, không có quy tắc pause/wait hay attribution; session cũng không có ID;
  - `schema_version` chưa có giá trị cụ thể; `cohort` chưa có enum; `cycle` dùng dấu `…`, nên chưa phải contract máy có thể kiểm tra;
  - ADR-0001 yêu cầu study ID, consent state, provenance và retention. `02-` mới có group pseudonym và một event consent; chưa có study ID/provenance/retention hoặc invariant chặn event nghiên cứu trước consent.
- **Hậu quả:** W1 buộc phải tự phát minh field và logic join để chạy được. Điều đó vi phạm chính `02-:5`, rồi analysis của Claude và phép tái lập độc lập của Codex có thể dùng hai định nghĩa khác nhau trên cùng log.
- **Tiêu chí gỡ:** bổ sung schema nghiên cứu đầy đủ nhưng không mang ontology sản phẩm: enum hữu hạn; ID/correlation key cho study, cycle/session, opportunity, action, proposal và obligation; event/field đủ để suy ra từng tử số, mẫu số, deadline và exclusion; provenance, consent invariant và retention theo W9; quy tắc thứ tự/correction; bảng derivation cho mọi metric ở `03-`. Cung cấp schema kiểm tra được cùng golden event streams dương/âm cho ít nhất qualifying repeat, opportunity, active time, intervention, collection 7 ngày, attrition và missingness.

### W0-03 — Bỏ sàn thu tiền 50% là đọc sai hai ràng buộc đồng thời

- **Loại blocker theo charter mục 4:** (1) vi phạm spec; (4) tính hợp lệ thí nghiệm.
- **Dẫn chứng:** `03-:28` thay sàn tuyệt đối bằng `>= baseline` của nhóm. Spec mục 15 đồng thời ghi **sàn thử nghiệm >=50%** và baseline bắt buộc vì 50% là vô nghĩa nếu nhóm đang đạt 70%. Hai câu không xung đột: baseline làm ngưỡng chặt hơn khi baseline cao; nó không xoá sàn khi baseline thấp.
- **Hậu quả:** một nhóm baseline 20% có thể đạt 25% và được coi là qua chỉ số phụ, dù vi phạm sàn 50% đã đăng ký trong spec.
- **Tiêu chí gỡ:** yêu cầu đồng thời `rate_concierge >= 50%` **và** `rate_concierge >= rate_baseline` trên comparator cùng nhóm, cùng loại chi phí, cùng mẫu số — tương đương `>= max(50%, baseline)`. Chốt trước cách tổng hợp paired result qua các nhóm, cách xử lý tie/missing và báo cả theo nghĩa vụ lẫn theo nhóm.

### W0-04 — Đường B chưa đủ độc lập để quyết định mẫu số gate

- **Loại blocker theo charter mục 4:** (4) tính hợp lệ thí nghiệm.
- **Dẫn chứng:** `00-:49–56` hỏi sau cửa sổ về “khoản chi chung” và việc “một người trả trước”, rồi dùng câu trả lời để xác định cơ hội. Gửi sau khi cửa sổ đóng có một ưu điểm thật: câu hỏi không thể làm phát sinh ngược một hành vi đã xảy ra trong chính cửa sổ đó. Vì vậy rủi ro chính **không phải** priming hành vi quá khứ; nó là recall/demand bias trong việc phân loại mẫu số. Chỉ nhóm không có sự kiện đăng ký trước mới đi Đường B, respondent biết mình có dùng dịch vụ hay không, và tài liệu chưa quy định ai trả lời, bằng chứng tối thiểu, người resolve có blind với outcome hay không, hay khi nào bắt buộc `indeterminate`. Câu “nếu kết quả đảo chiều thì đó là phát hiện” chưa nói gate sẽ mở hay đóng.
- **Hậu quả:** cùng một tập hành vi có thể thành `5/10` hoặc `6/10` chỉ vì cách một ca biên được nhớ và resolve sau khi outcome đã biết. Câu chữ giống nhau không loại được sai lệch hệ thống này. Check-in còn có thể prime các cửa sổ tương lai nếu nhóm tiếp tục được theo dõi.
- **Tiêu chí gỡ:** đóng băng nguyên văn script, respondent, thời điểm, số lần hỏi và rubric bằng chứng; dùng resolver độc lập/blind với usage outcome khi khả thi; buộc `indeterminate` khi không đủ bằng chứng cho cả bốn điều kiện; đăng ký trước phân tích tách A/B và quy tắc gate khi hai đường khác nhau. Đường B có thể giữ, nhưng không được một mình tạo GO nếu kết quả không bền dưới cách phân loại bảo thủ. Mọi dữ liệu sau check-in phải ghi exposure và có quy tắc loại/washout rõ.

### W0-05 — Cây nhãn đúng thứ tự ưu tiên nhưng ngưỡng tin cậy chưa bảo vệ được gate

- **Loại blocker theo charter mục 4:** (4) tính hợp lệ thí nghiệm; (5) kết quả không tái lập được.
- **Dẫn chứng:** Q1 trước Q3 ở `01-:64–84` là đúng: quyền/hợp đồng phải thắng khả năng kỹ thuật. Kiểm tra provenance ở Q2 trước cơ chế cũng đúng. Nhưng nhánh `01-:68–71` suy từ “sản phẩm có thể có input này” sang `human_judgment_required`; thiếu input trong phiên không chứng minh cần phán đoán con người. Q4 ở `01-:77–79` dùng “khả năng hợp lý” của một model không định danh, nên người thứ hai không thể tái lập. Cuối cùng `01-:90–94` và `03-:50` dùng một Cohen's kappa toàn cục với cutoff 0,6 trên mẫu ngẫu nhiên >=20% không nêu đơn vị lấy mẫu, seed hay xử lý lớp hiếm. Với bốn lớp lệch mạnh, kappa >=0,6 vẫn có thể đi cùng đồng thuận rất tệ riêng ở `human_judgment_required`/`out_of_contract_rescue` — đúng hai lớp quyết định luận đề “phần mềm hay dịch vụ”.
- **Hậu quả:** input bị thiếu có thể bị gọi nhầm là năng lực con người; thao tác khó có thể được gọi là model-plausible theo cảm giác; và một con số kappa đẹp che được lỗi ở lớp gate-critical.
- **Tiêu chí gỡ:** tách hoặc ghi riêng ba trục `contract/authority`, `input provenance` và `generation mechanism`, rồi định nghĩa precedence nếu vẫn cần một trong bốn nhãn cuối. Một input “có thể có nhưng phiên này không có” phải là missing-input/protocol deviation, không tự động là human judgment. Neo `model_plausible` vào capability matrix/model snapshot hoặc replay test đã version. Chốt đơn vị lấy mẫu, seed, coverage lớp hiếm, confusion matrix/class-wise agreement, quy trình adjudication và rule gate cho nhóm “human-only”; báo kappa nhưng không dùng 0,6 làm công tắc duy nhất.

### W0-06 — Stopping rule vẫn là câu tự do, chưa phải preregistration tái lập được

- **Loại blocker theo charter mục 4:** (4) tính hợp lệ thí nghiệm; (5) kết quả không tái lập được.
- **Dẫn chứng:** `01-:103–109` dừng khi hai block không có failure mode mới và “hướng kết quả không còn đảo ngược”. `03-:52–58` chỉ khoá thời điểm xem, chưa định nghĩa “hướng” theo metric/ngưỡng nào, cách quyết hai failure mode có thật sự mới hay chỉ đổi tên, protocol đổi version có reset chuỗi hai block không, hoặc trần tuyển/futility stop. Nhật ký W0 còn nói failure-mode register chưa được tạo.
- **Hậu quả:** sau khi xem block, team có thể gộp/tách failure mode hoặc chọn “hướng” thuận lợi để dừng; hai analyst không nhất thiết ra cùng quyết định trên cùng input.
- **Tiêu chí gỡ:** tạo và version failure-mode register/taxonomy trước dữ liệu đầu tiên; định nghĩa người adjudicate và quy tắc new-vs-existing; định nghĩa “hướng” bằng vị trí so với các ngưỡng đã nêu; nói rõ việc đổi protocol reset hay giữ chuỗi block; đăng ký trần N/thời gian và futility/early-stop. Cung cấp vài chuỗi block tổng hợp làm golden cases cho `continue`, `stop-futility`, `stop-harm` và `stop-saturation`.

## Trả lời đề xuất tách đóng băng `02-`

**Có thể tách về kiến trúc version, nhưng không thể đóng băng riêng bản `02-` hiện tại.** Nó vẫn phụ thuộc trực tiếp vào:

- định nghĩa `self_initiated`, `evaluable` và `valid_cost_opportunity` ở `00-`;
- cây nhãn và reliability rule ở `01-`;
- tử số, mẫu số và ngưỡng ở `03-`;
- enum cohort còn chờ ADR-0002 và modality `bill_image` còn chờ quyết định đường ảnh;
- consent/provenance/retention phải khớp W9;
- semantics version: file ghi `protocol_version: v1`, còn `schema_version` chưa có giá trị. Charter hiện coi `docs/protocol/v1/` là một snapshot bất biến, chưa định nghĩa trạng thái “một file frozen, bốn file draft”.

Ba tham số operator identity, có audit hay không và phạm vi counsel **không nhất thiết** chặn schema nếu contract định nghĩa superset cùng optionality rõ. Nhưng các dependency ngữ nghĩa ở trên chặn thật.

Nếu muốn mở W1 bằng fixture tổng hợp trước khi toàn W0 đóng băng, đường sạch là một ADR tách `measurement_contract_version` khỏi `protocol_version`, định nghĩa contract superset hoàn chỉnh và ghi rõ: freeze contract chỉ mở **W1 synthetic build/test**; không mở W3, không mở dữ liệu thật và không thoả FIELD-GATE. W1 phải log cả hai version. Khi chưa có ADR và chưa gỡ W0-01/W0-02/W0-05, partial freeze sẽ chỉ chuyển quyền viết protocol từ Claude sang code của W1.

## Điểm không tạo blocker

- `indeterminate`, attrition report, enrollment-order rule và cohort lock chống được nhiều cách làm đẹp mẫu số.
- Q1 đứng trước Q3 là lựa chọn đúng; tôi không đề nghị đảo Q3 lên đầu.
- Log event quan sát được thay vì `CollectionBatch.*` là đúng ranh giới giữa measurement contract và product schema.
- Append-only correction, `serious_error = 0`, sender veto, two-lane separation và cảnh báo `receiver_confirmed` không phải bằng chứng ngân hàng đều nên giữ.
- Bản khai thiên lệch concierge theo từng chiều, free-labor, founder-operator, self-report time và “accepted != correct” là thẳng thắn và hữu ích.

## Verdict cuối

**`REQUEST_CHANGES`.** Không blocker nào ở trên là tranh luận phong cách. W0 hiện có thể đếm một draft như repeat, không đủ field để tái lập gate, bỏ một nửa ngưỡng thu tiền, và để denominator/label/stopping rule phụ thuộc phán quyết hậu nghiệm. `02-` có thể được tách version về sau, nhưng chưa phải mục tiêu ổn định cho W1 ở trạng thái hiện tại.
