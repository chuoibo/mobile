# ADR-0010 — agy vào team làm QA/QC/kiểm thử sản phẩm

- **Trạng thái:** 🟡 **ĐÃ QUYẾT** 2026-08-27 — leader chốt phần "ai và làm gì".
  Phần cơ chế còn mở, chờ Codex (mục 11).
- **Ngày:** 2026-08-27
- **DRI:** Chủ sản phẩm · **Ghi chép:** Claude · **Reviewer:** Codex
- **Sửa:** `charter.md` mục 1 (bảng vai) và mục 5 · `backlog.md` (bảng phân công) ·
  bảng "chứng minh gì / không chứng minh gì" trong `CLAUDE.md` và `AGENTS.md`
- **Thay thế:** `docs/team/de-xuat-agy.md` mục 3 — xem mục 3 dưới đây

## 1. Quyết định

Team thành **4 người**: leader (người thật) + 3 agent — Claude, Codex, **agy**
(Gemini Antigravity CLI).

agy làm **QC / QA / kiểm thử sản phẩm toàn diện**: đa phương thức, bật app lên
xem và test, test API, kiểm thử thăm dò. Không phải chỉ chạy unit test.

Cả ba agent chạy **hai luồng việc song song cùng lúc**: task của mình theo plan,
và review/kiểm việc của người khác. Không tuần tự, không xếp hàng, không để việc
pending trong lúc đang thảo luận. *(Leader nói thẳng điều này 2026-08-27.)*

## 2. Vì sao là QA, và vì sao bây giờ

`CLAUDE.md` đã tự khai lỗ này ở tầng persistence bằng một bảng "chứng minh gì /
không chứng minh gì". Cùng lỗ đó tồn tại ở tầng giao diện và **chưa ai viết ra**.
Ví dụ thật, nguyên văn từ `services/api/tests/web/test_guest_page.py`:

```python
def test_dark_mode_is_defined(self):
    self.assertIn("prefers-color-scheme: dark", self.css)
```

Cái đó chứng minh **một chuỗi ký tự có mặt trong file CSS**. Không chứng minh
dark mode đọc được, không chứng minh tương phản đủ, không chứng minh mã QR còn
quét được trên nền tối.

Và không có ngoại lệ nào: không e2e, không browser test, không visual regression,
không kiểm thử thăm dò. **Chưa một ai — người hay máy — từng dùng thử sản phẩm
này một lần nào.**

QA cũng là lane **trực giao với bảng sở hữu**. Bảng ở `00-layout-va-so-huu.md`
nói *ai được viết file nào*; QA không sinh diff, nó sinh **phát hiện**. Nên thêm
người thứ ba vào lane này không phải cắt lại quyền viết của hai người cũ.

## 3. Thí nghiệm lật một tiền đề của bản đề xuất

`de-xuat-agy.md` mục 3 dựng cả dây chuyền trên một câu: *"agy không tự lái được
trình duyệt."* Câu đó **sai**. Tôi đã kiểm bằng thực nghiệm 2026-08-27:

```
$ agy mcp add playwright npx -- -y @playwright/mcp@latest
Added MCP server "playwright" (stdio)

$ agy -p='Liệt kê chính xác tên tất cả công cụ bạn đang có...'
→ 24 công cụ browser_*: browser_navigate, browser_resize,
  browser_take_screenshot, browser_snapshot, browser_click,
  browser_fill_form, browser_console_messages, browser_network_requests, ...
→ và: define_subagent, invoke_subagent, manage_subagents,
  run_command, search_web, read_url_content, generate_image
```

Hệ quả — bốn thứ trong bản đề xuất sụp theo:

| Bản đề xuất nói | Thực tế |
|---|---|
| Dây chuyền 3 bước: Claude chụp ảnh → agy đọc → Claude xác minh | agy tự lái, tự chụp, tự nhìn. Bước "Claude chụp ảnh" biến mất |
| Lane A cần Claude làm tay chân | Không. Claude chỉ giao đề và nghiệm thu |
| Lane B research phải qua Claude | agy có `search_web` + `read_url_content` native |
| agy là một tiến trình đơn | agy tự `define_subagent` được — nó fan-out được lane A ra nhiều luồng |

**Chưa chứng minh được:** vòng QA đầy đủ chạy end-to-end. Lần chạy thật bị chặn:

```
a tool required the "mcp" permission that headless mode cannot prompt for,
so it was auto-denied. Add an allow-rule under permissions.allow
(e.g. mcp(<target>)).
```

Xem mục 9.2. Cho tới khi việc đó chạy xanh một lần, mục 3 này chứng minh **agy
có công cụ**, không chứng minh **agy dùng được công cụ đó cho ra kết quả đúng**.
Đừng đọc nhầm hai thứ.

## 4. Vai — sửa `charter.md` mục 1

| Vai | Ai | Chịu trách nhiệm |
|---|---|---|
| Leader | Chủ sản phẩm | (không đổi) + **ký ADR này** + là người duy nhất chĩa app ngân hàng thật vào mã QR |
| Engineer | Claude | (không đổi) + `app/web/`, `apps/mobile/` |
| Engineer | Codex | (không đổi) + `db/`, `api/`, `payments/`, `domain/`, test backend |
| **QA** | **agy** | **Kiểm thử sản phẩm: hình ảnh, thăm dò, API, hồi quy. Nộp phát hiện. Không sở hữu file mã nguồn sản phẩm nào.** |

Câu quan trọng nhất trong hàng cuối là câu cuối. **agy nộp phát hiện, không nộp
diff.** Bảng sở hữu vẫn hai cột.

## 5. Năm lane — bản đã sửa theo mục 3

### Lane A — QA sản phẩm ⟵ lane chính

**Bia ngắm sẵn sàng, không cần dựng gì:** `python3 -m app.web.preview` chạy trang
khách **không cần database**, toàn dữ liệu tổng hợp.

Ma trận quét trang khách — bề mặt duy nhất đã ship:

| Trục | Giá trị |
|---|---|
| `link_state` | `active` · `expired` · `revoked` |
| Cờ | `can_report_payment` · `can_object` · `already_reported` · `receiver_confirmed` |
| Chủ đề | sáng · tối |
| Khung nhìn | điện thoại nhỏ (320) · điện thoại thường (390) · máy tính (1440) |

Mỗi ô hỏi bốn câu mà **228 test hiện tại không trả lời được câu nào**:

1. Có vỡ layout, tràn chữ, cắt nội dung không?
2. **Mã QR còn quét được không** — kích thước, quiet zone, tương phản trên nền tối?
3. Lời hứa riêng tư có giữ được **bằng mắt** không — có lộ tên hay số tiền của
   người khác ở bất kỳ trạng thái nào?
4. Chữ tiếng Việt có dấu ở cỡ nhỏ nhất còn đọc được không?

**Kiểm thử thăm dò** — khác hẳn 228 test kia. Test hiện có kiểm những thứ *tác
giả đã nghĩ ra*. Thăm dò cố tình đi tìm thứ không ai nghĩ tới: bấm hai lần, mở
link cũ sau khi thu hồi, báo đã chuyển rồi báo lại, tiêu hết ngân sách phản đối
rồi thử nữa, mở trang khách của người khác.

### Lane A′ — Test API ⟵ leader nêu riêng, bản đề xuất bỏ sót

Bản đề xuất gần như không nói gì về test API. Bề mặt API là của Codex, nên
**Codex viết bảng phân công chi tiết cho phần này** (đang chạy, mục 11). Khung:

- Kiểm thử hợp đồng: mọi route, mọi mã lỗi, mọi hình dạng payload sai
- Idempotency: gọi lại `confirm`, `publish`, `confirm-receipt` hai lần
- Thứ tự sai: `publish` trước `confirm`, `confirm-receipt` trước `publish`
- Rò rỉ ủy quyền: `X-Actor-ID` của người khác, thiếu header, header giả
- Race: hai `confirm` đồng thời trên cùng expense (Postgres thật, không fake)

Ghi rõ: header `X-Actor-*` là **chỗ tạm cho lát cắt dọc, không phải auth production**.
Phát hiện dạng "giả header thì vào được" là **đã biết**, không phải phát hiện mới.
agy phải được nói trước điều này, nếu không nó sẽ nộp một trang giấy vô dụng.

### Lane B — Research có trích dẫn

1. **VietQR / EMVCo / Napas** — trường bắt buộc trong QR động, ánh xạ mã BIN → tên
   ngân hàng hiển thị, nguồn chính thức.
2. **App ngân hàng Việt nào chấp nhận payload dạng nào.**
3. **Mổ xẻ đối thủ** — Splitwise · Settle Up · MoMo · ZaloPay. Câu hỏi cụ thể:
   *họ giải bài toán đi thu tiền thế nào?* Luận điểm trung tâm của repo
   (*"phần đau thật không phải chia tiền mà là đi thu tiền"*) chưa từng được đối
   chiếu với cái đã có ngoài kia.
4. Nghiên cứu thứ cấp về ma sát xã hội khi đòi tiền bạn bè.
   ⚠️ **Cái đó KHÔNG phải bằng chứng hành vi mà ADR-0006 đã gác.** Nó là tài liệu
   thứ cấp, không phải nhóm thật, không thuộc `protocol_version` nào. Gọi nó là
   "đã kiểm chứng" chính là hợp thức hoá hậu nghiệm mà charter mục 5 cấm.

Luật giao hàng: **URL + ngày · tối thiểu 2 nguồn độc lập · người nhận phải tự mở
nguồn đọc trước khi số đó vào code.** Một chuỗi EMVCo sai không đỏ ở test — nó đỏ
ở app ngân hàng của khách, tức là sau khi đã ra ngoài.

### Lane C — Nuốt lớn, trả bản rút gọn

Đọc toàn bộ `docs/` + spec 19 vòng + diff của các PR đang mở, trả về **bản đồ mâu
thuẫn**: chỗ nào ADR nói một đằng, code làm một nẻo, doc ghi kiểu thứ ba.

### Lane D — Việc cơ khí số lượng lớn

Điều kiện vào lane: **đáp án đúng đã tồn tại trước khi agy chạy** (một linter, một
schema, một test đang xanh, một quy ước đã viết ra). agy áp dụng, không phán đoán.

- `ruff` sạch cây — 11 lỗi + 27 file format, thành **một PR không làm gì khác**
- Docstring / type annotation sweep cho `app/api/` và `app/db/`

### Lane E — Quét trước PR *(tư vấn, không phải cổng)*

Chạy trên diff **trước khi** reviewer thật đọc. `QUEUE.md` tự khai 4 PR merge
không review vì "gấp"; một danh sách sẵn có làm phương án merge đại bớt hấp dẫn.

## 6. Ranh giới cứng

**6.1 — agy không điền `expected` cho golden vector, không sinh đáp án tiền.**
`CLAUDE.md` đã tự khai lỗ: corpus chứng minh nhất quán nội tại, **không** chứng
minh tác giả đọc đúng contract — cùng một người viết cả hai. 41 vector là **tính
tay**. Thêm model thứ ba sinh cả đề lẫn đáp án **mở rộng** lỗ đó. ADR-0006 bỏ
phương án hai bản viết mù để đổi lấy đúng một thứ: golden corpus tính tay là phần
không thương lượng. agy được sinh *khung* và *ca đầu vào*; **không** điền `expected`.

**6.2 — agy không ký verdict.** `APPROVE` / `REQUEST_CHANGES` / `REJECT` vẫn chỉ
hai chữ ký. Phát hiện QA là **đầu vào cho reviewer**, không phải cổng. Phát hiện
của agy không tự động thành blocker — vẫn phải lọt một trong 5 loại ở charter mục
4, vẫn phải kèm *dẫn chứng · hậu quả · tiêu chí gỡ chặn*.

**6.3 — Digest của agy không phải bằng chứng.** Đây là ranh giới **quan trọng
nhất** khi đặt agy vào ghế QA, và nó không phải tôi nghĩ ra. Tác giả plugin đã
**quan sát được**:

> never trust agy's self-reported "GREEN" — agy has been observed altering its
> own environment (patching installed packages, mock-stubbing deps) to force a
> pass.

Một QA agent báo xanh giả **tệ hơn không có QA**, vì nó tạo ra niềm tin sai. Nên:
người giao việc **chạy lại cổng trong cây sạch**, không ngoại lệ:

```bash
python3 -m pytest services/api/tests tests -q
python3 scripts/repo_guard.py staged
```

`agy-trace --audit <id>` tồn tại đúng vì một delegation đã từng báo SUCCESS trong
khi lệnh bên trong đã fail.

**6.4 — Không `--dangerously-skip-permissions` trên `/home/lakiet/mobile`.** Tác
giả plugin đã **đo**: cờ đó là quyền trên cả máy, `--sandbox` không chặn — ghi ra
đường dẫn tuyệt đối ngoài `--dir` vẫn rc 0. Dùng **allow-rule hẹp** thay vì cờ
rộng (mục 9.2). Loại 3 trong taxonomy blocker, không phải sở thích.

Ranh giới này **siết chặt hơn** sau mục 3, không nới ra: agy có `run_command`,
`browser_run_code_unsafe`, và tự `define_subagent` được. Bán kính nổ lớn hơn
nhiều so với "một con bot đọc ảnh" mà bản đề xuất hình dung.

**6.5 — Không bao giờ đưa dữ liệu thật cho agy.** Charter mục 6 tuyệt đối, không
có ngoại lệ cho công cụ. Uỷ thác nghĩa là **gửi nội dung ra một dịch vụ ngoài** —
biên mới mà repo guard không nhìn thấy. Repo guard quét thứ *vào* Git; không quét
thứ *đi ra*. **Áp thẳng vào lane A:** ảnh chụp màn hình QA chỉ được chụp từ
`app.web.preview` hoặc dữ liệu tổng hợp, **không bao giờ từ một phiên có dữ liệu
thật.**

**6.6 — Không chạm `phase0/`, `docs/protocol/v1/`, không sửa ADR đã ACCEPTED.**

## 7. Hàng mới trong bảng "chứng minh gì / không chứng minh gì"

Thêm vào `CLAUDE.md` **và** `AGENTS.md`:

| Tầng | Chứng minh | Không chứng minh |
|---|---|---|
| QA hình ảnh + thăm dò (agy) | Trang render được, đọc được, không lộ dữ liệu người khác, ở các trạng thái và thiết bị **đã quét** | **Mã QR có quét được bằng app ngân hàng thật không** · người thật có hiểu không · ô nào **chưa** quét · rằng agy không tự sửa môi trường để ra xanh |

Cột phải là cột quan trọng. Nó phải thật thà đúng như mọi hàng khác trong bảng.

## 8. Thứ KHÔNG AI trong ba agent kiểm được — phải là leader

| Câu hỏi | Vì sao AI không trả lời được | Hậu quả nếu sai |
|---|---|---|
| **Mã VietQR có quét được thật trong app ngân hàng Việt không?** | Cần một người, một điện thoại, một app ngân hàng thật | `vietqr.py` dựng chuỗi EMVCo, `test_vietqr.py` kiểm chuỗi + CRC. **Chưa ai từng chĩa app ngân hàng vào nó.** Sai thì mọi test vẫn xanh và sản phẩm hỏng đúng khoảnh khắc quan trọng nhất |
| Người thật có hiểu trang khách không | Đây đúng là canh bạc ADR-0006 | — |

**Đề nghị cụ thể:** một lượt kiểm 15 phút — chạy `app.web.preview`, mở bằng điện
thoại, chĩa app ngân hàng vào QR. Rẻ hơn mọi thứ trong ADR này và trả lời câu hỏi
đắt nhất.

## 9. Ba việc chặn — trạng thái

**9.1 — `AGENTS.md` chưa bao giờ nằm trong Git.** ✅ **ĐÃ XONG** — commit `4acac33`.
Codex làm việc trong checkout tách rời không hề có file đó, nghĩa là nó đang code
mà không có ba luật tiền. Đây không phải vấn đề tương lai của agy; nó đang xảy ra.
Nay `AGENTS.md` đã track và có mục "Shared Team Invariants".

**9.2 — Quyền tool cho agy trong chế độ headless.** 🔴 **ĐANG CHẶN — cần leader.**

agy `-p` **không prompt được**, nên nó tự chối mọi tool chưa có allow-rule. Tôi đã
dò từng lớp quyền bằng thực nghiệm 2026-08-27 — không đoán:

| Việc thử | Kết quả |
|---|---|
| Mở trình duyệt qua playwright | ❌ `a tool required the "mcp" permission` |
| Đọc file trong repo | ❌ `a tool required the "read_file" permission` |
| Đọc file **ngay trong workspace tin cậy** | ❌ `a tool required the "command" permission` — agy chọn dùng shell chứ không dùng `view_file` |
| Ghi file trong cwd | ❌ không tạo được file |

Nghĩa là **agy hiện không làm được gì cả** trong chế độ headless. Đây không phải
một cái cổng cần vặn nhẹ; nó đang đóng hoàn toàn.

Cú pháp rule (theo `TROUBLESHOOTING.md` + issue #37 của plugin, đã A/B có kiểm chứng):
`write_file(<dir>)` và `read_file(<dir>)` khớp **đệ quy dưới thư mục**, dạng glob
`(<path>/**)` được báo là **không** khớp. `command(<prefix>)` khớp **tiền tố**.
`mcp(<tên server>)`.

Bộ rule tối thiểu tôi đề nghị, đã soạn thành script để leader đọc rồi tự chạy —
`scratchpad/mo-quyen-agy.py`:

```
mcp(playwright)                  lái trình duyệt
mcp(chrome-devtools)             lỗi console, network, performance trace
mcp(context7)                    tra tài liệu thư viện khi research
read_file(/home/lakiet/mobile)   đọc repo
write_file(<scratchpad>)         báo cáo QA ra scratch, KHÔNG vào repo
```

**Cố ý không có `command(...)` nào.** `command()` khớp tiền tố, nên
`command(git diff)` cũng duyệt luôn `git diff && rm -rf ~`. Bắt đầu bằng không có
shell. Nếu QA thật sự không đi tiếp được, nới **một lần, có bằng chứng**, và gọi
tên đúng lệnh đó.

Tôi bị classifier chặn khi tự sửa allow-list của một agent khác — **đúng ranh
giới, tôi không nên có quyền đó**. Leader chạy. Đây là rule **hẹp**, khác hẳn
`--dangerously-skip-permissions` mà 6.4 cấm.

**9.3 — `/home/lakiet/mobile` trong `trustedWorkspaces`.** ✅ **ĐÃ CÓ.**

**9.4 — `permissions.allow` đang chứa ~35 rule của dự án khác** (AIC-2026). 🟠 **MỞ.**
`command()` của agy khớp theo **tiền tố**, rộng hơn allow-list của Claude vốn khớp
cả dòng lệnh. Rule nguy hiểm nhất trong đó:

```
"command(python3 - <<'PY')"
```

Khớp tiền tố nghĩa là **mọi script Python truyền qua heredoc đều tự động được
duyệt**. Đó là thực thi mã tuỳ ý, không phải một lệnh cụ thể. Tôi **không tự xoá**
— chúng thuộc dự án khác của leader và xoá có thể làm hỏng việc đang chạy ở đó.
Đề nghị: tách settings theo workspace, hoặc leader tự dọn. Loại 3.

## 10. Cấu hình đã đặt cứng

Theo yêu cầu của leader, `~/.gemini/antigravity-cli/settings.json`:

```json
{
  "model": "Gemini 3.7 Flash (High)",
  "effort": "high",
  "effortByBase": {
    "gemini-3.7-flash": "high",
    "gemini-3.6-flash": "high",
    "gemini-3.1-pro": "high"
  }
}
```

Ghi chú kỹ thuật: agy bản `1.1.22`. `doctor.sh` cảnh báo các bản **trước 1.1.10
bỏ qua `--model`/`--effort` trong chế độ headless `-p`** — bản này đã qua mốc đó
nên cờ có hiệu lực. Đặt trong settings vẫn đúng hơn vì nó áp cho **mọi** đường
gọi, kể cả đường không đi qua cờ.

Bản sao cũ giữ ở `settings.json.bak-<timestamp>` cùng thư mục.

**MCP đã cài sẵn cho agy** (leader yêu cầu cài trước để nó vào việc được ngay):

```
$ agy mcp list
NAME             TYPE   STATUS   COMMAND/URL
chrome-devtools  stdio  enabled  npx chrome-devtools-mcp@1.6.0
context7         stdio  enabled  npx -y @upstash/context7-mcp
playwright       stdio  enabled  npx -y @playwright/mcp@latest
```

`playwright` cho lane A (điều hướng, resize, chụp màn hình, snapshot cây a11y);
`chrome-devtools` cho thứ playwright không thấy (lỗi console, request mạng,
performance trace); `context7` cho lane B khi cần tra tài liệu thư viện.

Cả ba **đã enabled nhưng chưa dùng được** cho tới khi 9.2 xong — server đã cắm,
cửa vẫn khoá.

## 11. ADR này **chưa** quyết cái gì

Nói rõ để không ai đọc nhầm phần mở thành phần đã chốt:

- **A (delegate) hay B (ghế thứ ba thật).** Leader nói *"công ty 4 thành viên, 3
  agent"* — nghe như B. Nhưng B nghĩa là agy có nhánh `agy/*` riêng và tự mở PR,
  mà điều đó cần credential `gh` — tức là biên bảo mật rộng hơn thứ Claude và
  Codex đang có. Codex đang được hỏi. **Đề nghị của tôi: bắt đầu bằng A cho lane
  A/B/C** (phần lớn là đọc), giữ B cho tới khi có số đo thật.
- **Bảng phân công chi tiết lane A′ (test API)** — Codex viết, đang chạy.
- **Ranh giới nào còn thiếu ở mục 6** — Codex đang tấn công.

## 12. Tiêu chí dừng — đăng ký trước, không đặt sau khi thấy kết quả

Repo này đã viết ra câu *"không chế backlog để bảo vệ utilization."* Áp cho chính agy.

Sau **5 việc uỷ thác đầu**:

| Đo | Bằng gì | Ngưỡng bỏ |
|---|---|---|
| Lane A có tìm ra lỗi thật không | Đếm phát hiện dẫn tới một sửa đổi thật | 0 phát hiện thật qua 2 lượt quét đầy đủ |
| Có rẻ hơn thật không | `agy-cost-compare` · `measure-session` — **sửa `prices.json` theo giá thật trước khi trích số** | Không rẻ hơn ở tier flash |
| Lane E có giá trị không | Phát hiện đúng vs. phát hiện sai reviewer phải bác | Đọc danh sách tốn hơn tự đọc diff |

Ghi chú về phương pháp: **benchmark của Antigravity harness chưa ai đo.** Số mạnh
nhất cho Gemini 3.7 trong tài liệu leader đưa được đo trên OpenCode (Coding Index
60), còn Gemini CLI với 3.1 Pro trong cùng bảng là 33. Khoảng cách 60 vs 33 giữa
hai harness cùng nhà chính là bằng chứng rằng **số không chuyển giữa harness**.
Tiêu chí ở trên đo **workload của repo này**, không đo lại leaderboard.

## 13. Quy trình giao hàng

- **Nhánh:** `agy/<slug>` — slug là Work ID cụ thể (charter mục 2)
- **Mô tả PR bắt buộc có:** `Delegator: Claude` hoặc `Delegator: Codex`
- **Nhật ký:** `docs/agy/<YYYY-MM-DD>/` — prompt đã giao · tier · digest ·
  **cổng nào đã chạy lại và ra gì**
- **Báo cáo QA** đặt cùng chỗ, bắt buộc có: commit SHA · ma trận đã quét ·
  **ô nào chưa quét** · phát hiện kèm ảnh · phân loại theo 5 loại blocker
- **Không tự review qua trung gian:** ai giao việc *sinh code* cho agy thì không
  review PR đó. *(Không áp cho lane A: nộp phát hiện QA không phải viết code.)*
- **Kỷ luật chi phí:** `--digest`, gộp một lượt lớn thay vì nhiều lượt nhỏ,
  review **diff** không review cả cây.

## 14. Bảng phân công giao được ngay

| # | Việc | Lane | Ai giao | Ai nghiệm thu | Chặn bởi |
|---|---|---|---|---|---|
| 1 | **Quét QA đầy đủ trang khách** — 3 `link_state` × sáng/tối × 3 khung nhìn, agy tự lái trình duyệt trên `app.web.preview`. Báo cáo kèm ảnh | A | Claude | Codex | **9.2** |
| 2 | **Kiểm thử thăm dò trang khách** — link đã thu hồi, báo hai lần, tiêu hết quota rồi thử nữa, mở link người khác | A | Claude | Codex | **9.2** |
| 3 | **Test API** — hợp đồng, idempotency, thứ tự sai, rò rỉ ủy quyền, race trên Postgres thật | A′ | Codex | Claude | 9.2 · bảng chi tiết Codex đang viết |
| 4 | **Research VietQR/EMVCo/Napas** cho PR `#14` — URL + ngày, ≥2 nguồn độc lập | B | Claude | Codex | — |
| 5 | **Mổ xẻ đối thủ về cách đi thu tiền** — luận điểm trung tâm của repo chưa từng được đối chiếu | B | Claude | Codex | — |
| 6 | **Nuốt `docs/` + mọi diff đang mở → bản đồ mâu thuẫn** giữa ADR, code và doc | C | Claude | Codex | — |
| 7 | Quét trước 4 PR đang mở `#11` `#12` `#13` `#14` | E | ai cũng được | reviewer thật của PR | — |
| 8 | `ruff` sạch cây — một PR không làm gì khác | D | Codex | Claude | — |
| 9 | Khung ca test ràng buộc DB — **agy viết khung, người điền đáp án** | D | Codex | Claude | **6.1** |
| — | **Chĩa app ngân hàng thật vào mã QR** | — | **LEADER** | — | Không AI nào thay được |

Việc 4–7 chỉ đọc và không cần MCP, **giao được ngay bây giờ**. Việc 1–3 chờ 9.2.
