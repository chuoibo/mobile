# Review PR #11 — hai luồng phản đối của khách

## Metadata bắt buộc

- **Nhánh:** `origin/claude/guest-objection-flow`
- **Commit SHA:** `6f375b3f565abf9d320d1a3dd4249a439d7aa82e`
- **Base đối chiếu:** `origin/main@4acac3319f3369270a226e6fc3b818979b330d4f`
- **protocol_version:** `n/a` — PR đổi hành vi sản phẩm, không đổi snapshot
  `docs/protocol/v1/`
- **Verdict:** **`REQUEST_CHANGES`**
- **Blocker còn mở:** **4**

## Kết luận ngắn

Ba nhóm sửa leader yêu cầu kiểm lại đều có thật: method persistence đã nằm trong
`SqlAlchemyApiRepository`, quota phản đối đã được đếm và cưỡng chế trên fake,
và bốn câu tuyên bố hành vi không tồn tại đã bị bỏ khỏi HTML render. Nhưng PR
chưa thể duyệt: phản đối vẫn không dừng nghĩa vụ như spec yêu cầu, yêu cầu bằng
chứng bị quota phản đối chặn trong một trạng thái biên, persistence mới không có
ca PostgreSQL thật, và thay đổi repo guard mở một đường lọt base64 URL-safe.

## Kiểm lại các sửa đã được nêu

| Claim | Kết quả | Bằng chứng và ranh giới |
|---|---|---|
| `save_guest_objection` đã chuyển khỏi `Protocol` | **Có thật** | `ApiRepository` chỉ còn chữ ký ở `repository.py:266–282`; implementation có truy cập session nằm ở `SqlAlchemyApiRepository`, `repository.py:1167–1203`. Test introspection ở `test_guest_objections.py:255–262` cũng khóa vị trí này. |
| Quota thôi là số trang trí | **Có thật nhưng chưa trọn semantics** | Fake đếm event ở `conftest.py:328–333`; projection SQL đếm `AuditEvent` ở `repository.py:964–991`; service trả 429 ở `service.py:556–560`; test request thứ tư ở `test_guest_objections.py:204–223` xanh. Tuy nhiên chưa có test PostgreSQL cho đường này, và B-02 bên dưới cho thấy `evidence_request` vẫn bị chặn sau khi quota phản đối hết. |
| Bốn câu chữ nói dối đã sửa | **Có thật trên HTML render** | Không còn các lời hứa “đã được báo”, “chỉ khoản này tạm dừng”, “đã hỏi … đang chờ”, “khoản này vẫn dừng”. Template hiện nói thật rằng app chưa tự báo/chưa tự dừng (`guest_not_me.html:31–38,59–63`; `guest_wrong_amount.html:54–61,73–90`), và test khóa các phủ định ở `test_guest_objections.py:84–98,128–151`. |

## Blocker còn mở

### PR11-01 — Luồng “số tiền không đúng” cố định hành vi trái spec: ghi event nhưng vẫn thu

- **Loại blocker theo charter mục 4:** (1) vi phạm spec.
- **Dẫn chứng:** spec mục 8.2 nói tranh chấp chỉ dừng đúng nghĩa vụ bị ảnh hưởng
  (`docs/superpowers/specs/2026-08-25-group-hangout-ai-design.md:380–388`);
  mục 10.5 nói nếu không chia sẻ bằng chứng thì dispute vẫn tồn tại và collection
  của nghĩa vụ đó dừng (`:557–563`). Nhưng implementation chỉ thêm một
  `AuditEvent` (`repository.py:1182–1195`), không có projection nào biến nghĩa vụ
  thành disputed hoặc chặn nhắc/thu. Template còn mô tả thẳng “Nothing stops”
  và “chưa tự dừng khoản này” (`guest_wrong_amount.html:54–61`); test
  `test_it_never_claims_collection_stops` khóa chính hành vi thiếu đó
  (`test_guest_objections.py:84–98`).
- **Hậu quả:** khách có thể dùng lựa chọn ngang hàng “Số tiền không đúng”, nhận
  xác nhận đã lưu, nhưng người thu không thấy và vòng thu tiếp tục. Đây không
  chỉ là copy chưa đẹp; nó làm sai contract xử lý phản đối và có thể tăng áp lực
  trả một nghĩa vụ đang tranh chấp.
- **Tiêu chí gỡ chặn:** có projection/state suy ra theo **từng obligation** từ
  event phản đối; mọi đường nhắc/thu phải bỏ qua đúng nghĩa vụ disputed nhưng
  không ảnh hưởng nghĩa vụ khác; người có quyền xử lý phải nhìn thấy action
  item; test fake và PostgreSQL chứng minh gửi phản đối làm dừng đúng một nghĩa
  vụ, còn nghĩa vụ khác vẫn hoạt động. Nếu cố ý chỉ giao “ghi nhận, chưa dừng”,
  phải mở ADR đổi spec trước, không dùng test để hợp thức hóa sai lệch.

### PR11-02 — “Xin cách tính không tốn quota” vẫn bị chặn khi quota phản đối đã hết

- **Loại blocker theo charter mục 4:** (1) vi phạm spec/hành vi đã công bố.
- **Dẫn chứng:** `evidence_request` không được tính vào `objections_used`, đúng
  với comment ở `repository.py:985–990`. Nhưng `record_objection` áp điều kiện
  `objections_used >= objections_allowed` cho **mọi** kind trước khi lưu
  (`service.py:533–560`). Thực nghiệm với envelope tổng hợp có `3/3` phản đối và
  một obligation hợp lệ: gọi `evidence_request` trả
  `429 objection_rate_limited`. Test hiện tại chỉ hỏi bằng chứng nhiều lần khi
  quota phản đối còn nguyên (`test_guest_objections.py:225–252`), nên không chạm
  trạng thái này.
- **Hậu quả:** UI vẫn có thể cho thấy nút xin cách tính, nhưng POST bị 429 chỉ vì
  người đó đã phản đối đủ ba lần. Hỏi căn cứ của số tiền bị biến thành quyền phụ
  thuộc quota mà code/comment tuyên bố không áp dụng.
- **Tiêu chí gỡ chặn:** quota phản đối chỉ được kiểm với các kind thực sự tiêu
  quota; thêm regression “quota phản đối đã hết nhưng evidence request đầu tiên
  vẫn được nhận” và test trạng thái UI tương ứng.

### PR11-03 — Persistence mới chỉ được chứng minh bằng fake và introspection

- **Loại blocker theo charter mục 4:** (5) kết quả/test không tái lập được trên
  tầng được thay đổi.
- **Dẫn chứng:** PR thêm write/read/count JSONB qua `AuditEvent` và cập nhật
  `GuestLink` trong `SqlAlchemyApiRepository` (`repository.py:870–883,964–972,
  1167–1203`). Không có một tham chiếu `save_guest_objection`,
  `guest_objection.*` hay `evidence_request` nào trong `tests/postgres/`; test
  “real repository” chỉ dùng `inspect.getsource` (`test_guest_objections.py:
  255–262`). Suite local báo **241 passed, 7 skipped, 4218 subtests passed**;
  cả 7 skip là suite PostgreSQL vì không có `MOBILE_TEST_DATABASE_URL`.
  `docs/testing/postgres-repository.md` yêu cầu mọi persistence behavior mới có
  ca live tương ứng.
- **Hậu quả:** dấu xanh chưa chứng minh insert audit event, JSONB readback, count
  quota, revoke link hay serialization giao dịch hoạt động trên schema
  PostgreSQL thật. Lỗi ban đầu “mọi test xanh vì chạy fake” chưa được gỡ ở đúng
  tầng bằng chứng.
- **Tiêu chí gỡ chặn:** thêm ca `tests/postgres/` chạy sau Alembic, tối thiểu
  chứng minh: `wrong_amount` được lưu/đếm; `evidence_request` đọc lại theo đúng
  obligation nhưng không tiêu quota; `not_me` thu hồi link và không xóa nghĩa
  vụ; request vượt quota bị từ chối. Workflow PostgreSQL phải chạy các ca đó,
  không được xanh nhờ skip.

### PR11-04 — Heuristic mới bỏ qua mọi fragment base64 URL-safe có dấu gạch dưới

- **Loại blocker theo charter mục 4:** (3) quyền riêng tư/bảo mật.
- **Dẫn chứng:** `looks_encoded` trả `False` ngay khi fragment chứa `_`
  (`scripts/repo_guard.py:160–181`), dù `_` chính là ký tự hợp lệ của base64
  URL-safe. Thực nghiệm tổng hợp: một payload gồm các block base64 URL-safe hợp
  lệ, mỗi block ngắn và có `_`, được xuống dòng thành file **26.999 byte**; gọi
  `content_findings` trả `rules=[]`. Cùng lúc `repo_guard.py tree HEAD` vẫn xanh,
  cho thấy tree scan không phát hiện phản ví dụ này.
- **Hậu quả:** một bill/attachment được mã hóa URL-safe và wrap thành block ngắn
  có thể đi vào file text mà không kích hoạt aggregate, dense-line hay long-token.
  Scanner là lớp giảm thiểu chứ không phải bảo đảm tuyệt đối, nhưng PR đang làm
  yếu chính đường đã được W9a thêm để chặn ảnh nhúng text.
- **Tiêu chí gỡ chặn:** bỏ ngoại lệ blanket theo `_`; dùng predicate phân biệt
  identifier nguồn với payload mà vẫn đếm base64 URL-safe. Thêm regression với
  payload tổng hợp lớn hơn ngưỡng, chia block ngắn có `_`, phải kích hoạt rule;
  đồng thời giữ ca source code dài không false-positive. Output test chỉ được
  ghi rule/vị trí đã che, không in payload.

## Bằng chứng kiểm tra

- `python3 -m pytest services/api/tests tests -q` → **241 passed, 7 skipped,
  4218 subtests passed**.
- Targeted objection + repo guard → **47 passed, 29 subtests passed**.
- `python3 scripts/repo_guard.py tree HEAD` → xanh trên 134 file, nhưng phản ví
  dụ PR11-04 vẫn lọt; dấu xanh này không phủ input đối kháng.
- Không thể tự chạy PostgreSQL 16: sandbox từ chối Docker socket; đây là bất
  định kiểm chứng, không phải bằng chứng branch đúng.
- Ruff không sạch: `ruff check` báo 3 lỗi import-order; `ruff format --check`
  muốn format lại 7 file. Đây là suggestion vệ sinh, không được tính thành
  blocker riêng vì charter không cho chặn chỉ vì style.

## Verdict cuối

**`REQUEST_CHANGES`.** Các sửa được leader nêu là thật, nhưng chúng mới làm cho
UI nói thật về một flow chưa thực hiện contract. Cần gỡ cả bốn blocker trước khi
PR có thể được duyệt.
