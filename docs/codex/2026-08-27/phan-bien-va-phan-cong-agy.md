# Phản biện và phân công agy — 2026-08-27

- **Đối tượng:** `docs/team/de-xuat-agy.md`, bản 2, trạng thái ĐỀ XUẤT
- **Quyết định mới của leader:** team có bốn thành viên — leader, Claude, Codex,
  agy; agy làm QA/QC và kiểm thử sản phẩm toàn diện, không sở hữu mã sản phẩm
- **Kết luận:** **CHƯA DUYỆT BẢN 2.** Giữ hướng QA, nhưng phải viết lại mục 3, 4,
  8, 9, 10, 11 và 12 trước khi đưa thành ADR.

Tôi đã đọc toàn bộ `AGENTS.md`, `docs/team/charter.md`, ADR-0007,
`CLAUDE.md` và đề xuất. Phản biện này không dùng dữ liệu người thật, không chạy
trình duyệt, không bật `--dangerously-skip-permissions`, không truy cập token và
không gửi nội dung ra dịch vụ ngoài.

## Kết luận ngắn

Đề xuất nhìn đúng chỗ trống — chưa có QA sản phẩm — nhưng dựng lane chính trên một
tiền đề chưa được kiểm chứng và rất có khả năng sai: “agy không tự lái được trình
duyệt”. Máy hiện có đúng đường nối để agy điều khiển Playwright. Trạng thái
`enabled` chưa chứng minh một vòng E2E thật, nhưng đã đủ để bác việc viết kiến trúc
như thể đường đó không tồn tại.

Ranh giới “không điền `expected` cho golden vector” là cần nhưng chưa đủ. agy có
thể đưa ra một *phát hiện sai*, rồi con người dùng nó để sửa contract hoặc code
theo hướng sai. Một finding phải đi qua oracle có trước, tái lập độc lập và phân
loại “lỗi”/“khoảng trống contract” trước khi được phép gây ra diff.

Tôi chọn **B — ghế thứ ba thật**, vì đó là quyết định tổ chức leader vừa chốt.
Nhưng B **không đồng nghĩa** với `--dangerously-skip-permissions`. Nếu B chỉ chạy
được bằng quyền cả máy và token `gh` kế thừa thì B chưa được mở; dùng A như một
thí điểm có giám sát không biến nó thành kiến trúc đích.

## Biên bằng chứng capability cục bộ

### Đã xác nhận read-only

| Quan sát | Bằng chứng cục bộ | Kết luận hợp lệ |
|---|---|---|
| CLI agy có mặt | `/home/lakiet/.local/bin/agy`, phiên bản `1.1.22` | Có CLI cục bộ |
| agy có cơ chế MCP | `agy --help`; `agy mcp` có `add`, `list`, `enable`, `disable` | agy có thể nhận MCP server |
| MCP nhận browser server kiểu stdio | `agy mcp add --help` nhận `<commandOrUrl> [args...]`, mặc định `stdio` | Có đường kỹ thuật để nối một browser MCP |
| Playwright MCP đã cấu hình | `agy mcp list` trả `playwright  stdio  enabled  npx -y @playwright/mcp@latest` | Playwright MCP hiện **configured + enabled** cho agy |
| Package browser có trên máy | cache npm có `@playwright/mcp` `0.0.79` và `chrome-devtools-mcp` `1.6.0` | Hai package từng được materialize cục bộ; không đồng nghĩa cả hai đang cấu hình cho agy |

Hai chi tiết không được lờ đi:

- Cấu hình agy hiện chỉ liệt kê Playwright; Chrome DevTools MCP được thấy trong
  cache, không được xác nhận là server enabled của agy.
- `npx -y @playwright/mcp@latest` là đầu vào trôi theo thời gian và có thể tải/chạy
  mã mới. Nó không đạt yêu cầu tái lập và là biên supply-chain chưa khóa.

### Chưa xác nhận

Chưa có bằng chứng trong lượt này rằng agy đã tự hoàn tất vòng
`navigate → interact → observe → assert → lưu trace` trên app. Tôi cố ý không bật
browser để tránh side effect. Vì vậy kết luận đúng là:

> Câu tuyệt đối “agy không tự lái được trình duyệt” không còn đứng vững. Đường
> capability đã có và đang enabled; closed-loop E2E vẫn phải qua một bài
> qualification bằng fixture tổng hợp trong môi trường cô lập.

## Mục 3 — nếu agy tự lái được browser, những gì sụp theo

| Phần của bản 2 | Cái sụp | Phải thay bằng gì |
|---|---|---|
| Dây chuyền Claude chụp ảnh → agy đọc ảnh | Claude không còn là driver bắt buộc; câu hỏi “ai chụp ảnh” biến mất | agy tự chạy ma trận đã đóng băng; Claude chỉ giao contract, Codex tái lập finding |
| Lập luận “phần lớn QA chỉ đọc ảnh/log nên quyền giảm nhiều” | Browser MCP có thể điều hướng, bấm, gửi form, tạo trạng thái và đọc nội dung phiên browser | allowlist đích `localhost`, profile rỗng dùng một lần, credential tổng hợp, chặn mạng ngoài và ghi action trace |
| Ma trận chỉ nói ảnh chụp | Ảnh không ghi đủ chuỗi hành động, network response, console, timing và trạng thái DB | evidence packet gồm trace, request/response đã lọc, console, seed, commit, phiên bản browser/MCP và ảnh cần thiết |
| Việc số 1 bị chặn bởi việc Claude lái browser | Dependency và người giao sai | Claude giao state/visual oracle; agy chạy; Codex tái lập độc lập |
| Luận điểm chi phí dựa trên “đọc 60 ảnh” | Chi phí giờ gồm planning, tool call, retry, tạo trạng thái và người tái lập | đo tổng chi phí trên một ô coverage và một finding được chấp nhận, gồm phút người |
| Tiêu chí dừng “tìm ra lỗi thật” | Self-driving mở thêm lỗi do harness, timing và quyền; đếm sửa đổi càng dễ bị game | đo reproducibility, false-positive, seeded recall, coverage và tổng chi phí, không đếm diff đơn thuần |
| Quy trình giao hàng chỉ cần ảnh + digest | Không tái lập được đường đi tạo ảnh | lưu action trace tất định và script/harness do owner viết; digest không thay trace |

Những phần **không** sụp: agy vẫn không được ký verdict, không sở hữu mã sản phẩm,
không được dùng dữ liệu thật; QA browser không chứng minh người thật hiểu trang;
và chỉ leader với điện thoại/app ngân hàng thật mới kiểm được QR có quét được.
Khả năng lái browser cũng không tự biến agy thành người quyết định hướng hình ảnh.

Ngoài ra, mục 7.1 đã cũ: theo commit `4acac33`, `AGENTS.md` đã nằm trong Git và có
“Shared Team Invariants”. Nó không còn là blocker cho việc 1–3. Mục 9 cũng dùng sai
số: repo đã có `ADR-0008 — Bot đọc luồng nhóm`; ADR cho tổ chức agy phải lấy số
còn trống, không ghi đè ADR-0008.

## Mục 4 — ranh giới cho finding, không chỉ cho `expected`

### Vì sao 4.1 chưa đủ

Không cho agy điền đáp án tiền chỉ chặn một đường gây sai. Các đường còn mở:

- agy gọi một hành vi đúng là bug vì tự suy diễn contract;
- agy gán severity/blocker sai và kéo reviewer vào một sửa đổi không cần thiết;
- agy biến khác biệt hình ảnh thành yêu cầu sản phẩm dù không có oracle;
- agy chọn input thiên lệch rồi báo “không có lỗi” như bằng chứng bao phủ;
- agy sinh test với assertion ngầm đóng băng hành vi sai dù trường tên không phải
  `expected`;
- một finding về tiền sai hướng có thể khiến owner sửa allocator/corpus đúng thành
  sai mà vẫn giữ được tổng 100%.

### Trạng thái bắt buộc của một finding

```text
OBSERVATION
    │  có commit + môi trường + seed + fixture tổng hợp + trace tối thiểu
    ▼
REPRODUCED
    │  người không chạy lượt đầu tái lập được từ cây sạch
    ▼
CONTRACT_CHECKED
    ├── oracle có trước bị vi phạm ──► ACCEPTED_DEFECT
    └── không có oracle / oracle mâu thuẫn ──► CONTRACT_GAP
```

Chỉ `ACCEPTED_DEFECT` mới được mở việc sửa code. `CONTRACT_GAP` đi về leader/ADR;
không được đổi thành bug bằng biểu quyết của model. `REJECTED` và `DUPLICATE` phải
được giữ để tính false-positive, không xóa khỏi mẫu.

### Ranh giới bổ sung bắt buộc

1. **Oracle có trước agy.** Codex đóng băng OpenAPI, ADR/spec và predicate bất biến
   cho API; Claude đóng băng state/visual oracle cho web. Nếu chưa có oracle, agy
   chỉ được nộp câu hỏi `CONTRACT_GAP`.
2. **agy không viết assertion kỳ vọng**, snapshot chuẩn, severity, verdict, ADR,
   spec hay bản vá mã sản phẩm. “Không điền `expected`” áp theo ý nghĩa, không theo
   tên field.
3. **Finding không tự thành blocker.** Người nghiệm thu phải chỉ đúng một trong năm
   loại ở charter mục 4 và ghi đủ *dẫn chứng · hậu quả · tiêu chí gỡ chặn*.
4. **Tái lập chéo.** Finding trên bề mặt Claude sở hữu do Codex tái lập; finding
   trên bề mặt Codex sở hữu do Claude tái lập. PR sửa vẫn theo reviewer độc lập của
   ADR-0007.
5. **Artifact đầy đủ.** Mỗi finding có target SHA, phiên bản migration/app/browser/
   MCP, seed, fixture ID + digest, hành động/request tối thiểu, nguồn của oracle,
   actual, log đã lọc và những ô chưa quét.
6. **Fixture tổng hợp duy nhất.** Không tên participant thật, ảnh bill thật, số tài
   khoản thật, transcript/export thật hay `.env` thật. Screenshot chỉ từ preview
   hoặc DB tổng hợp.
7. **Không tự động sửa.** Không hook nào biến finding thành test, issue, diff hoặc
   merge mà chưa có `ACCEPTED_DEFECT`.
8. **Không tuyên bố phủ định toàn cục.** Quét xanh chỉ nói về đúng commit, môi
   trường, seed và các ô đã chạy.

## Mục 8 — chọn B, nhưng bác phép đồng nhất B với quyền cả máy

Quyết định “công ty bốn thành viên, ba agent” là **B về governance**. Tuy nhiên,
bảng A/B của đề xuất tạo một lưỡng phân giả: agy có thể là ghế thứ ba với prompt
permission, sandbox đã kiểm định, filesystem/network allowlist và credential hẹp.
`--dangerously-skip-permissions` là một lựa chọn vận hành nguy hiểm, không phải
điều kiện định nghĩa một thành viên.

### Điều kiện mở B

B chưa được chạy độc lập cho tới khi tất cả điều kiện sau có bằng chứng:

- ADR mới được leader chấp nhận, sửa `charter.md` thành leader + 3 agent, khai rõ
  agy chỉ sở hữu finding/artifact QA, không sở hữu product source và không ký
  verdict;
- chạy trong OS user/container/VM riêng, checkout riêng; không đọc được
  `/home/lakiet/mobile`, home, SSH agent, credential store hay worktree khác;
- **cấm** `--dangerously-skip-permissions`; mọi quyền ngoài allowlist phải hỏi,
  `--sandbox` phải qua test thoát sandbox trước khi được tin;
- môi trường được scrub, không kế thừa `GH_TOKEN`, credential `gh`, SSH key hay
  cookie/profile browser thật;
- nếu cần tự mở PR, cấp credential riêng, thời hạn ngắn, đúng một repo, chỉ đủ tạo
  branch/PR, không admin, không secret, không bypass branch protection; việc tạo PR
  tách khỏi phiên browser/test;
- pin chính xác phiên bản và integrity của MCP/browser; thay
  `@playwright/mcp@latest` bằng bản cố định đã review, không chạy `npx -y latest`;
- browser dùng profile rỗng dùng một lần, chỉ tới origin localhost đã allowlist,
  không extension, không đăng nhập, không internet tùy ý;
- API chỉ dùng service local + Postgres/schema dùng một lần, credential tổng hợp,
  có rate/time/tool-call limit và kill switch;
- trace tool call/action/network được lưu để audit; artifact chạy qua repo guard và
  review dữ liệu trước khi vào Git;
- capability qualification chứng minh được cả việc được phép lẫn việc bị cấm,
  nhưng test canary không được tự ý đọc secret thật để “chứng minh”.

Nếu thiếu một điều kiện, leader có thể cho chạy thí điểm delegate có giám sát,
nhưng không được gọi đó là ghế B đã an toàn. Đặc biệt, việc Codex không có mạng
GitHub không phải lý do trao toàn bộ credential máy cho agy.

## Mục 11 — bản hiện tại là utilization theater dù có chữ “đăng ký trước”

“Sau 5 việc” không phải đơn vị đo: năm việc thuộc lane khác nhau, độ lớn khác nhau
và có thể được chọn sau cho dễ thắng. “Finding dẫn tới sửa đổi” thưởng cho việc
chấp nhận finding và sửa code, không thưởng cho finding đúng; nó còn biến chính
diff do finding gây ra thành nhãn sự thật. Không tìm được bug trong hai lượt cũng
có thể nghĩa là bề mặt sạch, không phải agy vô dụng.

So giá tier mà không tính thời gian giao việc, dựng fixture, tái lập, bác false
positive và sửa harness là cost theater. “Đọc danh sách tốn hơn đọc diff” không có
đồng hồ, baseline hay định nghĩa người đọc nên cũng không tái lập được.

### Protocol đánh giá phải đăng ký trước

| Pha | Mẫu phải khóa trước | Đo | Luật dừng |
|---|---|---|---|
| Capability/security qualification | Các task local tổng hợp cố định: browser navigate/interact/assert; API request/trace; các capability bị cấm | hoàn thành tất định từ môi trường sạch, trace đầy đủ, không vượt scope | dừng ngay khi có egress/scope/credential breach; không qua nếu không lặp lại được |
| Detection calibration | Một bộ mutant tổng hợp ẩn + clean control, do người khác tạo; không chạm product branch | seeded recall, false-positive rate, reproducibility | leader ký ngưỡng trước khi lộ đáp án; không dùng bug tự nhiên để suy recall |
| So sánh paired | Cùng commit/matrix cho agy và baseline độc lập, thứ tự khóa trước | finding mới được chấp nhận, coverage, phút người, chi phí tool, thời gian tới repro | dừng/tiếp tục theo ngưỡng đã ký, không theo số diff sinh ra |
| Workload tự nhiên | Danh sách commit/flow cố định trước lượt chạy | accepted-defect yield theo severity và tổng chi phí; contract-gap tách riêng | chỉ là bằng chứng hiệu dụng sau qualification, không thay calibration |

Mỗi metric phải có tử số, mẫu số và owner gắn nhãn. False positive, duplicate,
contract gap và ô chưa chạy đều nằm trong báo cáo. Ngưỡng số cụ thể là lựa chọn
budget/risk của leader và phải ký **trước** pilot; tài liệu này không tự bịa ngưỡng
để bảo vệ utilization.

## Hợp đồng kiểm thử API giao cho agy

Đây là phần bản 2 bỏ sót. “Test API” không thể nằm trong một dòng lane E. Mọi task
dưới đây dùng target SHA cố định, app local, Postgres 16/schema dùng một lần và
fixture tổng hợp. Codex cung cấp oracle/predicate; agy chỉ sinh request, chạy,
quan sát và nộp finding. Không task nào cho agy tự điền đáp án tiền.

### API-FUZZ — fuzz contract có seed

Lấy OpenAPI tại target SHA làm grammar, rồi quét mọi endpoint hiện diện, tối thiểu
`POST /expenses`, `/expenses/{id}/confirm`, `/batches`,
`/batches/{id}/publish`, `GET /g/{token}`,
`POST /g/{token}/da-chuyen`, `POST /obligations/{id}/confirm-receipt` và endpoint
phản đối khi nhánh tương ứng có nó.

Các lớp input: sai/thiếu/thừa field; `null`; boolean/string/float thay integer;
integer âm, 0, rất lớn; UUID sai/không tồn tại; enum sai; datetime thiếu timezone;
list rỗng, trùng, đổi thứ tự, cardinality lớn; Unicode tiếng Việt; JSON sai;
content type sai. Predicate do Codex cung cấp phải kiểm: không `float`/`Decimal`
lọt vào money path, tổng allocation đúng total khi request hợp lệ, request 4xx
không để lại material fact dở dang, lỗi có shape ổn định và không lộ stack/secret.
Mỗi failure phải có seed và minimal request tái lập.

### API-ERROR — ma trận lỗi và authorization

Quét thiếu/sai actor headers, role/context không phù hợp, actor ở context khác,
ID đúng định dạng nhưng không tồn tại, object thuộc context khác, token guest sai/
hết hạn/thu hồi, quota cuối đã dùng, transition sai thứ tự, publish/confirm lặp,
payment report trỏ obligation không thuộc envelope và receipt trỏ report của
obligation khác. Với từng ca, ghi status, `ErrorResponse`, số row/event trước/sau
và kiểm không lộ object của context khác. Auth header hiện là gateway stub phải
được ghi rõ trong kết luận; QA không được gọi nó là auth production.

### API-PG — thăm dò trên Postgres thật

Từ schema rỗng: chạy Alembic, chạy trọn lát cắt dọc, restart API giữa các transition,
thử lỗi giữa transaction, rồi đối chiếu material facts/audit events. Tập trung vào
append-only trigger, partial unique index, JSONB/view, snapshot recipient đã đóng
băng, rollback không để orphan/partial rows, guest envelope không lộ chéo và parity
giữa fake với SQL cho cùng contract. Chỉ báo xanh khi xác nhận đang dùng PostgreSQL
thật; skip vì thiếu URL là **chưa chạy**.

### API-RACE — race condition bằng barrier, không bằng loop tuần tự

Mỗi kịch bản dùng ít nhất hai client được nhả cùng một barrier: confirm cùng expense;
publish cùng batch; report payment ở slot quota cuối; phản đối ở slot quota cuối;
hai receipt cùng/different idempotency key; report/revoke hoặc report/expiry cạnh
biên thời gian. Ghi cả kết quả HTTP và rows/events sau commit. Oracle phải nói
trước “một thắng + một conflict”, “cùng resource” hay kết quả hợp lệ khác; nếu
chưa nói thì kết quả là `CONTRACT_GAP`, không phải bug. Bất biến tối thiểu: không
duplicate material fact ngoài contract, không mất event, không partial write,
ledger vẫn tái tính được và tổng tiền vẫn đúng.

### API-IDEM — idempotency và retry

Cho `report_payment` và `confirm_receipt`, quét tuần tự lẫn đồng thời:

- cùng key + cùng payload;
- cùng key + payload khác;
- cùng key qua obligation/context/endpoint khác nhau để xác định scope;
- server commit nhưng client mất response rồi retry;
- transaction fail trước commit rồi retry;
- key bị gửi lại sau restart;
- trường hợp `report_payment` bỏ trống key, vì schema hiện cho phép.

Mỗi ca kiểm resource ID, response, event count, amount và side effect. Codex phải
đóng băng trước scope của key và semantics khi payload khác; constraint DB hiện
tại không tự nó là contract. Agy không được nhìn unique constraint rồi tự tuyên bố
hành vi mong đợi.

## Bảng phân công giao được ngay

“Nghiệm thu” dưới đây là nghiệm thu **finding/artifact**, không phải tự động chấp
nhận bản vá. Mọi bản vá tiếp theo vẫn qua ADR-0007.

| Việc | Lane | Ai giao | Ai nghiệm thu | Chặn bởi cái gì |
|---|---|---|---|---|
| **CAP-01:** qualification Playwright MCP: local preview, navigate/interact/assert hai lượt từ profile sạch, lưu trace | A / capability | Leader | Claude + Codex cùng đối chiếu trace | quyền chạy thử; MCP phải pin version; profile rỗng; localhost allowlist; fixture tổng hợp |
| **WEB-01:** tự lái ma trận `link_state` × cờ × sáng/tối × ba viewport; kiểm layout, focus, privacy bằng mắt và QR quiet zone | A / web | Claude | Codex tái lập mẫu finding | CAP-01 xanh; state oracle của Claude; preview/fixture tổng hợp; không dùng app ngân hàng thật |
| **API-FUZZ:** fuzz OpenAPI/schema + predicate tiền/lỗi với seed cố định và shrink request | A / API | Codex | Claude tái lập; leader xử lý contract gap | OpenAPI + predicate đóng băng; Postgres dùng một lần; rate limit; CAP security xanh |
| **API-ERROR:** ma trận 4xx/transition/auth/context/token/quota và kiểm không có side effect/rò chéo | A / API | Codex | Claude tái lập; Codex xác nhận nguồn oracle | error/auth contract có trước; actor/ID/token đều tổng hợp; endpoint nhánh nào chỉ chạy trên đúng SHA nhánh đó |
| **API-PG:** exploratory trên Postgres thật từ Alembic tới restart/rollback/append-only/envelope isolation | A / API-PG | Codex | Claude chạy lại từ schema rỗng | PostgreSQL 16 disposable; `MOBILE_REQUIRE_POSTGRES_TESTS=1`; migration target cố định; cấm DB thật |
| **API-RACE:** barrier test cho confirm, publish, quota, report/revoke/expiry, receipt đồng thời | A / API-concurrency | Codex | Claude tái lập đúng seed/schedule; leader chốt semantics thiếu | race oracle có trước; harness barrier; DB dùng một lần; endpoint revoke/object phải tồn tại ở target SHA |
| **API-IDEM:** retry và scope key: same/different payload, cross-object/context, lost response, restart | A / API-idempotency | Codex | Claude tái lập; leader xử lý contract gap | idempotency scope/response contract phải đóng băng; fault proxy tổng hợp; DB dùng một lần |
| **PR-SCAN:** quét diff trước review, nộp candidate finding có line/evidence, không ký verdict | E | Reviewer thật của PR | Chính reviewer đó bác/nhận từng finding | target SHA + base cố định; không write source; finding state machine hoạt động |
| **DOC-MAP:** bản đồ mâu thuẫn ADR/spec/code/test, tách contradiction khỏi câu hỏi | C | Leader | Claude + Codex xác nhận phần thuộc ownership của mình | snapshot docs/diff cố định; không sửa `phase0/` hay `docs/protocol/v1/` |
| **RESEARCH-QR:** nguồn chính thức VietQR/EMVCo/Napas, URL + ngày + ít nhất hai nguồn; không gửi fixture/data repo | B | Claude | Codex tự mở nguồn và kiểm claim | network research được leader cho phép; không dùng nguồn để tuyên bố QR đã quét thật |

Việc `WEB-01` và toàn bộ API task có thể được chuẩn bị contract/harness ngay,
nhưng agy chỉ chạy sau CAP-01 và các ranh giới dữ liệu/quyền ở trên. Không việc nào
được dùng tên participant, số tài khoản, ảnh bill, transcript, export hay tiền
thật.

## Blocker của bản đề xuất, theo charter mục 4

| ID | Loại hợp lệ | Dẫn chứng | Hậu quả | Tiêu chí gỡ chặn |
|---|---|---|---|---|
| AGY-01 | 1, 3, 5 | Mục 3 nói agy không tự lái browser; `agy mcp list` cho thấy Playwright MCP enabled qua `@latest` | kiến trúc giao việc sai và supply chain không tái lập/an toàn | chạy CAP-01; pin MCP; viết lại mục 3/10/12 theo kết quả |
| AGY-02 | 1, 2, 4 | Mục 4 chỉ cấm điền golden `expected`, không có oracle/tái lập/adjudication cho finding | finding sai có thể lái contract hoặc money code sai, làm hỏng bằng chứng QA | thêm finding state machine và tám ranh giới ở trên |
| AGY-03 | 3 | Mục 8 đồng nhất ghế B với quyền cả máy và token `gh` | một tool/browser prompt có thể vượt repo và làm lộ credential/dữ liệu | B chỉ mở sau toàn bộ điều kiện least-privilege; cấm dangerous mode |
| AGY-04 | 4, 5 | “5 việc”, “finding dẫn tới sửa”, cost không gồm giờ người, không baseline/denominator | không phân biệt năng lực với mật độ bug; kết quả dễ bị chọn mẫu và game | đăng ký protocol qualification/calibration/paired trước khi chạy |
| AGY-05 | 1, 5 | API chỉ được nhắc chung ở lane E và một dòng exploratory | quyết định “agy test API” không có bề mặt, oracle, race hay idempotency plan giao được | đưa API-FUZZ/ERROR/PG/RACE/IDEM và bảng owner/acceptance vào đề xuất |
| AGY-06 | 1 | Mục 7.1 vẫn nói thiếu `AGENTS.md`; mục 9 đòi `ADR-0008` dù số này đã dùng | proposal dựa trên trạng thái stale và có thể đè namespace quyết định | cập nhật theo `4acac33`; dùng ADR number còn trống và sửa charter trước hiệu lực |

Sau khi sáu blocker được gỡ, hướng QA và lựa chọn B có thể đi tiếp. Trước đó,
“enabled MCP”, test xanh hay một danh sách finding dài đều chưa phải bằng chứng agy
là tầng QA đáng tin.
