# Đề xuất — agy (Gemini Antigravity) vào team làm gì

> **Trạng thái: ĐỀ XUẤT. Chưa có hiệu lực.**
> Người viết: Claude · 2026-08-27 · trên `main` tại `e157826` · **bản 2**
> Bản 1 chia agy vào 3 lane quanh việc cơ khí. Leader bác: quá hẹp, và bỏ sót
> đúng chỗ trống lớn nhất của dự án. Bản này viết lại quanh **QA / QC / kiểm thử
> sản phẩm** làm lane chính.
>
> Áp dụng cần **ADR-0008 do leader ký** — xem mục 9.
> Đọc trước: `charter.md` · `backlog.md` · `00-layout-va-so-huu.md` · `ADR-0006` · `ADR-0007`.

---

## 1. Chỗ trống thật — và nó không phải chỗ ai cũng nghĩ

Leader nói: *"ta hiện giờ chỉ thuần code, không test gì cả, không review gì cả."*

Hai vế sau không đúng theo nghĩa đen, và nói cho chính xác thì mới thấy được vấn đề thật:

- **Có test:** 228 test đang xanh, chia đúng tầng, có bảng "chứng minh gì / không
  chứng minh gì" trong `CLAUDE.md`.
- **Có review:** `ADR-0005`, `ADR-0007`, 11 review doc trong `docs/claude/` và `docs/codex/`.

Nhưng vế đầu thì đúng, và đúng theo một cách nguy hiểm hơn cả cách leader mô tả:

> **Chưa một ai — người hay máy — từng dùng thử sản phẩm này một lần nào.**

Và tệ hơn: **có những test trông như đã kiểm thứ đó, nhưng không.** Ví dụ thật,
lấy nguyên văn từ `services/api/tests/web/test_guest_page.py`:

```python
def test_dark_mode_is_defined(self):
    self.assertIn("prefers-color-scheme: dark", self.css)

def test_focus_is_visible(self):
    self.assertIn("focus-visible", self.css)
```

Cái đó chứng minh **chuỗi ký tự có mặt trong file CSS**. Nó không chứng minh dark
mode đọc được, không chứng minh tương phản đủ, không chứng minh mã QR còn quét được
trên nền tối, không chứng minh focus ring nhìn thấy được ở đâu. Đây đúng là loại
"dấu xanh là lời tuyên bố sai" mà `CLAUDE.md` đã cảnh báo ở tầng persistence —
chỉ là lần này nó nằm ở tầng giao diện và chưa ai viết ra.

Kiểm thêm, không có ngoại lệ nào:

```
$ grep -ril 'playwright|selenium|puppeteer|storybook|percy' --include='*.py' --include='*.ts' .
                                        # không có gì
```

**Không có e2e. Không có browser test. Không có visual regression. Không có
exploratory testing. Không ai từng mở trang khách lên xem.**

Đây là chỗ agy thuộc về.

---

## 2. Vì sao QA là câu trả lời đúng cho "agy làm gì"

Bản 1 vướng một vấn đề cấu trúc mà tôi không gỡ được: bảng sở hữu ở
`00-layout-va-so-huu.md` có đúng hai cột, và mọi lane code tôi nghĩ ra cho agy đều
phải cắt vào một trong hai cột đó, kéo theo sửa ADR và mở ra chuyện tự review qua
trung gian.

**QA không có vấn đề đó.** Bảng sở hữu nói *ai được viết file nào*. QA không sinh
diff, nó sinh **phát hiện**. Nên:

| Vấn đề của bản 1 | QA lane có vướng không |
|---|---|
| Đụng bảng sở hữu 2 cột | ❌ Không. QA trực giao với quyền viết code |
| Tự review qua trung gian | ❌ Không. QA nộp phát hiện, reviewer vẫn là hai người cũ |
| Chạm `domain/` và golden vector | ❌ Không. QA đứng ngoài, nhìn vào sản phẩm chạy |
| Cần `--yolo` quyền cả máy | ⚠️ Giảm nhiều — phần lớn việc QA là **đọc ảnh và log**, không ghi file |

Và nó khớp đúng thứ agy mạnh nhất theo chính benchmark leader đưa: đa phương thức
native, 1M context, throughput cao, giá rẻ. Đọc 60 ảnh chụp màn hình rồi trả một
danh sách khác biệt là việc mà chi phí là biến số quyết định — và ở đó agy rẻ hơn
khoảng 6 lần.

---

## 3. Năm lane — bản 2

### Lane A — QA / QC / kiểm thử sản phẩm ⟵ **lane chính**

agy **không tự lái được trình duyệt**. Nó đa phương thức trên **file bạn đưa cho nó**.
Nên dây chuyền đúng là:

```
Claude (Playwright / chrome-devtools MCP)     ← lái trình duyệt, chụp N ảnh
            ↓
agy (đa phương thức, rẻ, 1M context)          ← đọc hết, so sánh, liệt kê khác biệt
            ↓
Claude / Codex                                 ← xác minh, quyết cái nào là blocker
```

Bia ngắm đã sẵn sàng, không cần dựng gì: `python3 -m app.web.preview` chạy trang
khách **không cần database**.

**Ma trận quét cho trang khách** — đây là bề mặt duy nhất đã ship:

| Trục | Giá trị |
|---|---|
| `link_state` | `active` · `expired` · `revoked` |
| Cờ | `can_report_payment` · `can_object` · `already_reported` · `receiver_confirmed` |
| Chủ đề | sáng · tối |
| Khung nhìn | điện thoại nhỏ · điện thoại thường · máy tính |

Mỗi ô hỏi bốn câu mà **228 test hiện tại không trả lời được câu nào**:

1. Nó có render không, hay vỡ layout / tràn chữ / cắt nội dung?
2. **Mã QR còn quét được không** — kích thước, quiet zone, tương phản trên nền tối?
3. Lời hứa riêng tư có giữ được **bằng mắt** không — có lộ tên hay số tiền của
   người khác ở bất kỳ trạng thái nào?
4. Chữ tiếng Việt có dấu ở cỡ nhỏ nhất còn đọc được không?

**Kiểm thử chức năng thăm dò** — khác hẳn 228 test kia. Test hiện có kiểm những
thứ **tác giả đã nghĩ ra**. Thăm dò là cố tình đi tìm thứ không ai nghĩ tới: bấm
hai lần, mở link cũ sau khi thu hồi, báo đã chuyển rồi báo lại, tiêu hết ngân sách
phản đối rồi thử nữa, mở trang khách của người khác.

**Hồi quy hình ảnh trên PR:** chụp trước/sau, agy đọc cả hai bộ, báo cái gì đổi mà
mô tả PR không nói tới.

### Lane B — Research có trích dẫn ⟵ **leader nhấn mạnh: rất cần**

Bốn việc, xếp theo mức độ chặn thật:

1. **VietQR / EMVCo / Napas** — chặn PR `#14` ngay lúc này. Trường nào bắt buộc
   trong QR động, mã BIN ánh xạ sang tên ngân hàng hiển thị nào, nguồn chính thức.
2. **App ngân hàng Việt nào chấp nhận payload dạng nào.** Đây là thứ quyết định
   sản phẩm chạy hay không, và không suy ra được từ repo.
3. **Mổ xẻ đối thủ** — Splitwise · Settle Up · chia tiền trên MoMo · ZaloPay.
   Câu hỏi cụ thể: **họ giải bài toán đi thu tiền thế nào?** Luận điểm trung tâm
   của repo (`README`: *"phần đau thật không phải chia tiền mà là đi thu tiền"*)
   chưa từng được đối chiếu với cái đã có ngoài kia.
4. **Nghiên cứu thứ cấp về ma sát xã hội khi đòi tiền bạn bè.**
   ⚠️ **Đọc kỹ dòng này:** cái đó **KHÔNG phải** bằng chứng hành vi mà `ADR-0006`
   đã gác. Nó là tài liệu thứ cấp, không phải nhóm thật của bạn, không phải
   `protocol_version` nào. Gọi nó là "đã kiểm chứng" chính là **hợp thức hoá hậu
   nghiệm** mà charter mục 5 cấm. Nó chỉ rẻ, và rẻ hơn không có gì.

Luật giao hàng: **URL + ngày · tối thiểu 2 nguồn độc lập · người nhận phải tự mở
nguồn đọc trước khi số đó vào code.** Một chuỗi EMVCo sai không đỏ ở test — nó đỏ ở
app ngân hàng của khách, tức là sau khi đã ra ngoài.

### Lane C — Nuốt lớn, trả bản rút gọn

1M context. Việc dạng: đọc toàn bộ `docs/` + spec 19 vòng + diff của 4 PR đang mở,
trả về **bản đồ mâu thuẫn** — chỗ nào ADR nói một đằng, code làm một nẻo, doc ghi
một kiểu thứ ba. Không ai trong hai chúng tôi làm việc đó rẻ được.

### Lane D — Việc cơ khí số lượng lớn

Điều kiện vào lane: **đáp án đúng đã tồn tại trước khi agy chạy** (một linter, một
schema, một test đang xanh, một quy ước đã viết ra). agy áp dụng, không phán đoán.

- `ruff` sạch cây — **11 lỗi + 27 file format**, thành một PR không làm gì khác
- Docstring / type annotation sweep cho `app/api/` và `app/db/`
- Khung ca test cho ràng buộc DB mà fake không mô phỏng được — **xem mục 4.1**

### Lane E — Quét trước PR *(tư vấn, không phải cổng)*

Chạy trên diff **trước khi** reviewer thật đọc, ra danh sách phát hiện ứng viên.
`QUEUE.md` tự khai 4 PR merge không review vì "gấp"; một danh sách sẵn có làm
phương án merge đại bớt hấp dẫn.

---

## 4. Ranh giới cứng — không phụ thuộc benchmark

**4.1 — agy không được điền `expected` cho golden vector, không sinh đáp án tiền.**
`CLAUDE.md` đã tự khai lỗ: corpus chứng minh nhất quán nội tại, **không** chứng
minh tác giả đọc đúng contract — cùng một người viết cả hai. 41 vector là **tính
tay**. Thêm model thứ ba sinh cả đề lẫn đáp án **mở rộng** lỗ đó. `ADR-0006` bỏ
phương án hai bản viết mù để đổi lấy đúng một thứ: golden corpus tính tay là phần
không thương lượng. agy được sinh *khung* và *ca đầu vào*; **không** điền `expected`.

**4.2 — agy không ký verdict.** `APPROVE` / `REQUEST_CHANGES` / `REJECT` vẫn chỉ
hai chữ ký. Phát hiện QA là **đầu vào cho reviewer**, không phải cổng. Và phát hiện
của agy không tự động thành blocker — vẫn phải lọt một trong 5 loại ở charter mục 4,
vẫn phải kèm *dẫn chứng · hậu quả · tiêu chí gỡ chặn*.

**4.3 — Không tự review qua trung gian.** Ai giao việc sinh code cho agy thì không
review PR đó. *(Không áp cho lane A: nộp phát hiện QA không phải viết code.)*

**4.4 — Không `--yolo` trên `/home/lakiet/mobile`.** Tác giả plugin đã **đo**:
`--yolo` là quyền trên cả máy, `--sandbox` không chặn — ghi ra đường dẫn tuyệt đối
ngoài `--dir` vẫn rc 0. Việc ghi file chạy trên checkout tách rời. Loại 3 trong
taxonomy blocker, không phải sở thích.

**4.5 — Không bao giờ đưa dữ liệu thật cho agy.** Charter mục 6 tuyệt đối, không
có ngoại lệ cho công cụ. Uỷ thác nghĩa là **gửi nội dung ra một dịch vụ ngoài** —
biên mới mà repo guard không nhìn thấy. Repo guard quét thứ *vào* Git; không quét
thứ *đi ra*. **Áp thẳng vào lane A:** ảnh chụp màn hình QA chỉ được chụp từ
`app.web.preview` hoặc dữ liệu tổng hợp, **không bao giờ từ một phiên có dữ liệu thật.**

**4.6 — Không chạm `phase0/`, `docs/protocol/v1/`, không sửa ADR đã ACCEPTED.**

---

## 5. Thứ KHÔNG AI trong ba chúng tôi kiểm được — phải là leader

Nói riêng ra vì đây là rủi ro cao nhất trong sản phẩm và không lane nào ở trên
chạm tới được.

| Câu hỏi | Vì sao AI không trả lời được | Hậu quả nếu sai |
|---|---|---|
| **Mã VietQR có quét được thật trong app ngân hàng Việt không?** | Cần một người, một điện thoại, một app ngân hàng thật | `vietqr.py` dựng chuỗi EMVCo, `test_vietqr.py` kiểm chuỗi + CRC. **Chưa ai từng chĩa app ngân hàng vào nó.** Sai thì mọi test vẫn xanh và sản phẩm hỏng đúng khoảnh khắc quan trọng nhất — lúc khách định chuyển tiền |
| Người thật có hiểu trang khách không | Đây đúng là canh bạc `ADR-0006` | — |

**Đề nghị cụ thể:** một lượt kiểm 15 phút của leader — chạy `app.web.preview`, mở
bằng điện thoại, chĩa app ngân hàng vào QR. Rẻ hơn mọi thứ trong doc này và trả lời
câu hỏi đắt nhất.

---

## 6. "Đạo diễn hình ảnh" — tách hai việc

Leader hỏi cả phần này. Theo chính benchmark leader đưa (Code Arena WebDev):
Claude Opus 5 **1691** · Gemini 3.7 Flash **1587**. Nên tách:

| Việc | Ai | Vì sao |
|---|---|---|
| **Quyết** hướng hình ảnh, chọn phương án cuối | Claude | Dẫn ở WebDev/frontend theo số của chính leader |
| **Sinh số lượng** — 10 phương án bố cục để có cái mà chọn | agy | Rẻ gấp ~6 lần; ở đây số lượng chính là giá trị |
| **Giám định** — tương phản, nhất quán token, đa thiết bị, hồi quy ảnh | **agy** | Đây là lane A. Đọc 60 ảnh là việc của throughput |

Tóm tắt: agy làm **giám định hình ảnh** và **sinh phương án**; **đạo diễn** thì không.

---

## 7. Ba thứ phải xử lý trước khi giao việc đầu tiên

**7.1 — `AGENTS.md` chưa bao giờ nằm trong Git.**

```
$ git ls-files | grep -E '^(AGENTS|CLAUDE)\.md$'    # rỗng, chưa từng track
$ git diff .gitignore
+AGENTS.md
+CLAUDE.md                                          # sửa đổi CHƯA COMMIT
$ ls /home/lakiet/codex-repo/AGENTS.md              # không tồn tại
```

`agy` đọc `AGENTS.md` làm file chỉ dẫn mặc định. Trong một checkout sạch — mà 4.4
bắt buộc phải thế — nó **không có** file đó, nên không biết ba luật tiền, ranh giới
`domain/`, quy ước ngôn ngữ, luật dữ liệu participant. **Và chuyện này đang ảnh
hưởng Codex ngay lúc này**, không phải vấn đề tương lai của agy.

| Phương án | Đánh đổi |
|---|---|
| **Track `AGENTS.md`, giữ `CLAUDE.md` ignore** | Mọi checkout đều có luật. **Tôi đề nghị cái này** |
| Copy tay từng checkout | Rẻ ngay, lệch bản sau vài tuần — lệch âm thầm |
| `<repo>/.agents/rules/` | Rule thiếu `trigger: always_on` bị **bỏ qua im lặng, không lỗi, không cảnh báo** |

**7.2 — `/home/lakiet/mobile` chưa nằm trong `trustedWorkspaces`.** Hiện chỉ có
`/home/lakiet/AIC-2026`. **Không có `agy --trust`** — đã kiểm `agy --help`. Hai cách
đúng: duyệt prompt ở lần chạy tương tác đầu, hoặc thêm tay vào
`~/.gemini/antigravity-cli/settings.json`.

**7.3 — `permissions.allow` đang chứa ~35 rule của dự án khác** (AIC-2026). `command()`
của agy khớp theo **tiền tố**, rộng hơn allow-list của Claude vốn khớp cả dòng lệnh.

---

## 8. Một quyết định kiến trúc leader phải chọn

Bản 1 ngầm chọn A mà không nói là có lựa chọn. Nói rõ ra:

| | **A — delegate** | **B — ghế thứ ba thật** |
|---|---|---|
| agy chạy ở đâu | trong phiên Claude/Codex | phiên riêng, nhánh `agy/*`, tự mở PR |
| Chữ ký review | không bao giờ có | Claude/Codex review → hết vướng tự review |
| Đổi charter | ít | nhiều — thành 3 lane thật |
| Quyền phải cấp | hẹp | `--yolo` = **quyền cả máy, gồm token `gh` và cả đĩa** |

**B khả thi về kỹ thuật ở đây** — điểm tôi đánh giá sai ở bản 1. Codex không tới
được GitHub vì bị sandbox; **agy chạy như tiến trình cục bộ với chính mạng và chính
credential `gh` của bạn**, nên rào cản của Codex không áp cho nó.

Nhưng B đổi vấn đề tự review lấy một biên bảo mật rộng hơn thứ Claude và Codex đang
có. Loại 3 → **quyền của leader.**

**Đề nghị của tôi: bắt đầu bằng A cho lane A/B/C** (QA, research, ingest — phần lớn
là đọc, gần như không cần quyền ghi), giữ B lại cho tới khi có số đo thật.

---

## 9. Cần ADR-0008

Vì đề xuất này đụng:

- `charter.md` mục 1 — bảng vai
- `charter.md` mục 5 — thêm `docs/agy/<YYYY-MM-DD>/`
- `backlog.md` — bảng phân công (`ADR-0001`: *"đổi phân công cần ADR"*)
- **Và một thứ chưa có ADR nào nói tới:** một tầng kiểm thử mới, tức là thêm một
  hàng vào bảng "mỗi tầng test chứng minh được gì" trong `CLAUDE.md`. Hàng đó phải
  có cột **không chứng minh** viết đầy đủ, đúng như mọi hàng khác.

Đề nghị nội dung hàng mới:

| Tầng | Chứng minh | Không chứng minh |
|---|---|---|
| QA hình ảnh + thăm dò (agy) | Trang render được, đọc được, không lộ dữ liệu người khác, ở các trạng thái và thiết bị đã quét | **Mã QR có quét được bằng app ngân hàng thật không** · người thật có hiểu không · trạng thái nào chưa quét |

---

## 10. Quy trình giao hàng

- **Nhánh:** `agy/<slug>` — slug là Work ID cụ thể (charter mục 2)
- **Mô tả PR bắt buộc có:** `Delegator: Claude` hoặc `Delegator: Codex`
- **Nhật ký:** `docs/agy/<YYYY-MM-DD>/` — prompt đã giao · tier · digest · **cổng nào
  đã chạy lại và ra gì**
- **Báo cáo QA** đặt cùng chỗ, bắt buộc có: commit SHA · ma trận đã quét · ô nào
  **chưa** quét · phát hiện kèm ảnh · phân loại theo 5 loại blocker
- **Nghiệm thu, không thương lượng:** người giao việc chạy lại trong cây sạch
  ```
  python3 -m pytest services/api/tests tests -q
  python3 scripts/repo_guard.py staged
  ```
  Digest của agy **không phải bằng chứng** — nó có thể sửa môi trường cho check pass;
  `agy-trace --audit <id>` tồn tại đúng vì một delegation báo SUCCESS trong khi lệnh
  bên trong đã fail.
- **Kỷ luật chi phí:** `--digest`, gộp một lượt lớn thay vì nhiều lượt nhỏ, review
  **diff** không review cả cây.

---

## 11. Tiêu chí dừng — đăng ký trước, không đặt sau khi thấy kết quả

Repo này đã viết ra câu *"không chế backlog để bảo vệ utilization."* Áp cho chính agy.

Sau **5 việc uỷ thác đầu**:

| Đo | Bằng gì | Ngưỡng bỏ |
|---|---|---|
| Lane A có tìm ra lỗi thật không | Đếm phát hiện dẫn tới một sửa đổi thật | 0 phát hiện thật qua 2 lượt quét đầy đủ |
| Có rẻ hơn thật không | `agy-cost-compare` · `measure-session` — **sửa `prices.json` theo giá thật trước khi trích số** | Không rẻ hơn ở tier flash |
| Lane E có giá trị không | Phát hiện đúng vs. phát hiện sai reviewer phải bác | Đọc danh sách tốn hơn tự đọc diff |

Và một ghi chú về phương pháp, vì đề xuất này một phần dựa trên benchmark ngoài:
**benchmark của Antigravity harness chưa ai đo.** Số mạnh nhất cho Gemini 3.7 trong
tài liệu leader đưa được đo trên OpenCode (Coding Index 60), còn Gemini CLI với 3.1
Pro trong cùng bảng là 33. Khoảng cách 60 vs 33 giữa hai harness cùng nhà chính là
bằng chứng rằng **số không chuyển giữa harness**. Nên tiêu chí ở trên đo **workload
của repo này**, không đo lại leaderboard.

---

## 12. Việc giao được ngay — cho hai bạn phân công

| # | Việc | Lane | Giao | Nghiệm thu | Chặn bởi |
|---|---|---|---|---|---|
| 1 | **Quét QA đầy đủ trang khách** — 3 `link_state` × sáng/tối × 3 khung nhìn, từ `app.web.preview`. Ra báo cáo kèm ảnh | A | Claude (lái trình duyệt) | Codex | 7.1, 7.2 |
| 2 | **Research VietQR/EMVCo/Napas** cho PR `#14` — URL + ngày, ≥2 nguồn | B | Claude | Codex | 7.2 |
| 3 | Quét trước 4 PR đang mở `#11` `#12` `#13` `#14` | E | ai cũng được | reviewer thật của PR | 7.1, 7.2 |
| 4 | **Thăm dò chức năng** luồng thu tiền trên Postgres thật — cố tình đi tìm thứ 228 test không nghĩ tới | A | Codex (chủ backend) | Claude | 7.1, 7.2 |
| 5 | `ruff` sạch cây — một PR không làm gì khác | D | Codex | Claude | 7.1, 7.2 |
| 6 | **Nuốt toàn bộ `docs/` + 4 diff → bản đồ mâu thuẫn** giữa ADR, code và doc | C | Claude | Codex | 7.2 |
| 7 | Mổ xẻ đối thủ về **cách đi thu tiền** — luận điểm trung tâm của repo chưa từng được đối chiếu | B | Claude | Codex | 7.2 |
| 8 | Khung ca test ràng buộc DB — **agy viết khung, người điền đáp án** | D | Codex | Claude | 7.1, **4.1** |
| — | **Chĩa app ngân hàng thật vào mã QR** | — | **LEADER** | — | Không AI nào thay được |

**Chưa giao trước khi ADR-0008 ký:** việc 8 (sát ranh giới 4.1), và bất kỳ việc nào
tạo `docs/agy/`.

Việc 1–3 chỉ đọc và chụp ảnh, không ghi vào cây — **làm thử được ngay như thí điểm**
sau khi xong 7.1 và 7.2, miễn là mọi PR sinh ra vẫn đi qua đúng cổng review cũ.
