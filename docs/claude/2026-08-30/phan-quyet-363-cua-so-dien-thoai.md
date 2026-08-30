# PASS cho #363 tại `cafe32cf` — cửa số điện thoại mở lại được, đo trên máy demo sống

**PASS.**

**Lý do, viết trước phần chi tiết:** #363 sửa đúng lỗi nó nói là sửa, và tôi
chứng minh được điều đó ở chỗ chính tác giả ghi là **chưa quét** — trên API sống
8099, bằng hai bundle tôi tự dựng từ hai SHA. Bản trước in đúng thẻ hỏng đã báo
(`Mã: 0`) và bấm Gửi sinh **0 lời gọi HTTP**; bản sau vào được nhóm, và bấm Gửi
sinh `POST /contexts/{id}/messages` thật — tin nhắn nằm trên máy chủ khi đọc lại
bằng `curl`. Cổng đầy đủ xanh ở cả hai phía: `npm test` 790/790,
`pytest services/api/tests tests` 2592 passed / 0 failed.

Cái tôi **không** cho là đủ, và Lead nên đọc trước khi coi việc này đã đóng:
**dây nối làm nên bản vá lại là phần không cổng nào gác.** Đổi
`nhomPhien={nhom}` thành `nhomPhien={null}` trong `VoTab.tsx` — tức trả lại đúng
loại lỗi này — vẫn **790/790 xanh**. Ba đột biến ở dây nối lọt. Đó là nợ cổng,
không phải lỗi của hành vi đang ship, nên nó không chặn merge; nhưng nó có nghĩa
là lần tái phát sau sẽ im lặng.

---

## Đo tại đâu

```
đo tại   cafe32cf7ed515acfbc3573ddb0fe024764261c3   (head #363, một commit)
sha này  là nhánh CHƯA merge; base của nó là 159694b, đã ở main
đối chứng 159694b   (main lúc tôi bắt việc)
main lúc viết  1895e09
```

`git merge-base --is-ancestor origin/main@159694b cafe32c` → đúng: PR đã rebase.

Giữa lúc tôi đo, main nhích từ `159694b` lên `1895e09` (ba commit: #364, SVG
README, #366). **Không commit nào chạm `apps/mobile/`** —
`git diff --name-only 159694b origin/main -- apps/mobile` trả rỗng — nên mọi số
đo dưới đây vẫn nói về cây sẽ lên main. `git merge-tree --write-tree origin/main
cafe32c` → `rc=0`, **0 xung đột**.

Bundle web tôi dùng để đi bộ được dựng bằng chính tay tôi từ hai SHA đó, và hai
bundle có hash **khác nhau** (`0a939a22…` trước / `5fb9b75b…` sau) — không phải
hai lần đọc cùng một bản dựng. Máy phục vụ tĩnh được xác minh bằng hash
`index.html` khớp file trên đĩa, sau khi cổng 8178 hoá ra **đã bị process khác
chiếm** và trả 404 cho cây của tôi.

## Cổng đã chạy

| Lệnh | Cây | Kết quả |
|---|---|---|
| `npm test` (gồm `expo export` + `tsc --noEmit`) | `cafe32c` | **790 pass / 0 fail / 0 skipped** — chạy 3 lượt, xanh cả ba |
| `python3 -m pytest services/api/tests tests -q` | `cafe32c` | **2592 passed, 551 skipped, 4902 subtests passed, 0 failed** (270s) |
| `git merge-tree` với `origin/main@1895e09` | — | 0 xung đột |

551 skipped là tầng PostgreSQL tự bỏ qua khi thiếu `MOBILE_TEST_DATABASE_URL`.
Xem mục "Ô chưa quét".

## Đối chứng đỏ-trước / xanh-sau, tầng lời gọi hàm

Tôi tự chép `tests/nhom-cua-phien.test.mjs` của PR vào một worktree **sạch** ở
`159694b` rồi chạy, chứ không đọc lại bảng của tác giả:

```
cd <cây 159694b>/apps/mobile
npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs \
  && node --test tests/nhom-cua-phien.test.mjs
```

```
# tests 5   # pass 0   # fail 5
not ok 1 - người tự đăng ký mở được nhóm, và việc đó có đi ra mạng
  error: 'người tự đăng ký không sinh lời gọi HTTP nào — bị từ chối trước khi hỏi máy chủ:
          {"kind":"hong","buoc":"dat-ten","url":"http://api.test.invalid/people","status":0,
           "detail":"không có người ... trong nhóm demo, không bịa một người khác"}'
```

**0/5 ở bản cũ, 5/5 ở bản mới.** Ca đầu đỏ đúng triệu chứng được báo — `status: 0`,
tức chưa hỏi ai — chứ không đỏ vì import thiếu. Bảng của tác giả đúng.

## Ô tác giả tự ghi là CHƯA QUÉT, và tôi đã quét: đi bộ trên API sống 8099

PR viết: *"Chưa đi bộ trên API sống… Cần agy/QA đi lại đúng 4 bước tái lập trên
bundle dựng từ SHA này."* Đây là phần đó.

Cùng một trình điều khiển, cùng máy chủ 8099, chỉ khác bundle.
Harness: `docs/claude/2026-08-30/qa-tt-0041/di-bo-cua-so-dien-thoai.mjs`.

### Đường A — đăng ký bằng số điện thoại, rồi bấm tab Tin nhắn

| Phép đo | TRƯỚC `159694b` | SAU `cafe32c` |
|---|---|---|
| vào được shell sau khi nhập số + tên | có | có |
| chữ trên màn chat | `Chưa vào được nhóm` · `Mã: 0` · `không có người "3e9a…" trong nhóm demo` | `Team Đà Lạt` · `8 thành viên` · có lịch sử chat |
| thấy ô nhập tin | có | có |
| **bấm Gửi → số lời gọi HTTP** | **0** | **4** |
| **có `POST /contexts/{id}/messages`** | **không** | **có** |

Chuỗi request bản SAU, đọc từ trình duyệt chứ không từ log máy chủ:

```
POST /identity/person-id → PUT /people/{id} → POST /contexts
→ POST /contexts/{ctx}/members → POST /memberships/{id}/accept
→ GET  /contexts/{ctx}/members → GET /contexts/{ctx}/messages?limit=50
→ POST /contexts/{ctx}/messages → POST /contexts/{ctx}/ai-turn
```

Không dừng ở "trình duyệt có gửi đi". Đọc ngược lại từ máy chủ:

```
GET /contexts/5cacfdee-…/messages?limit=5
  3b7e79e1 'QA41 xin chao'        <- người vừa đăng ký bằng số điện thoại
```

Và nhóm được **replay chứ không mọc thêm cái thứ hai**:
`GET /contexts/5cacfdee-…` trả `display_name: "Team Đà Lạt"`,
`created_at: 13:42:59` — sớm hơn lượt đo của tôi hai tiếng rưỡi.

### Đường B — phiên tự mở nhóm riêng, rồi mới vào Tin nhắn

Đây là khẳng định thứ hai của PR (`moNhomDaCo`: dùng nhóm của phiên, **không**
gửi `POST /contexts` lần nữa). Harness: `di-bo-nhom-cua-phien.mjs`.

Đi: đăng ký → `[+]` → *Tạo nhóm* → đặt tên → *Mở nhóm* → *Đóng* → tab Tin nhắn.

| Phép đo | TRƯỚC `159694b` | SAU `cafe32c` |
|---|---|---|
| chat in tên nhóm vừa mở | **không** | **có** — `QA41 Nhom Rieng 90059` · `1 thành viên` |
| chat in `Team Đà Lạt` | không | không |
| màn chat | thẻ hỏng `Chưa vào được nhóm` | phòng chat rỗng, đúng câu mời gõ |
| `POST /contexts` **sau khi** vào tab chat | — | **không có**, chỉ `GET …/members` + `GET …/messages` |

Bản TRƯỚC đáng đọc kỹ: nó **đã** tạo nhóm của phiên (`POST /contexts` ở bước
tạo nhóm) rồi vẫn in thẻ hỏng ở tab Tin nhắn — tức chat bỏ qua hẳn nhóm người
dùng đang nhìn. Đó chính xác là hậu quả PR mô tả, đo được bằng chân.

## Bảng đột biến — 3 dây nối lọt

Mọi hàng chạy trên cây `cafe32c`, nền xanh 790/790 trước khi bắt đầu.
Bảng có cả hàng **cần XANH** để chứng minh nó phân biệt được, chứ không phải
một bảng đỏ hết rồi tự khen.

| id | cần | đo được | | đột biến | cổng nói gì |
|---|---|---|---|---|---|
| M1 | ĐỎ | **ĐỎ** | ĐẠT | `moNhomChoMan` luôn dựng lại nhóm demo, bỏ nhóm phiên | 1 ca đỏ |
| M2 | ĐỎ | XANH | **LỌT** | `moNhomDaCo` đọc danh sách thành viên dưới danh nghĩa `minh` | 790/790 |
| M3 | ĐỎ | **ĐỎ** | ĐẠT | trả lại chính bug-223337 (từ chối người ngoài bảy người seed) | 7 ca đỏ |
| M4 | ĐỎ | XANH | **LỌT** | `VoTab`: `<TinNhan … nhomPhien={null} />` | 790/790 |
| M5 | ĐỎ | XANH | **LỌT** | `VoTab`: `renderKhoanChi(…, null)` — bill ghi vào nhóm demo | 790/790 |
| M6 | ĐỎ | XANH | **LỌT** | `TinNhan`: deps `[nguoi, nhomPhien]` → `[nguoi]` | 790/790 |
| C1 | XANH | XANH | ĐẠT | thêm một biến không ai đọc trong `moNhomDaCo` | 790/790 |
| C2 | XANH | XANH | ĐẠT | `nhomPhien={nhom ?? null}` trên giá trị vốn đã `\|null` | 790/790 |

Ba chú thích bắt buộc, vì thiếu chúng thì bảng này sai:

1. **Lượt đo đầu của M4/M5/M6 phải vứt đi.** Tôi chạy chúng bằng
   `tsc + node --test`, và đó là phép đo **hỏng** cho `.tsx`:
   `tsconfig.test.json` không biên dịch `.tsx` (không có
   `dist-test/navigation/VoTab.js`), còn `vo-tab-web.test.mjs` thì đọc **bundle**
   `.expo-build-check` — bundle của cây **chưa** đột biến. Ba hàng đó được chạy
   lại bằng nguyên `npm test`, tức có `expo export --clear` dựng lại từ nguồn đã
   đột biến. Số trong bảng là số của lượt hai.
2. **M5 đỏ một lần rồi xanh lần sau, trên cùng một cây.** Lượt đầu ra
   `fail=8`, ca đỏ đầu tiên là *"lưới Khám phá cắt ở bốn"* — không liên quan gì
   tới `renderKhoanChi`. Chạy lại đúng cây đó: `790/790`. Tôi ghi M5 là **LỌT**
   và ghi cái đỏ kia là **flake**, chứ không đọc một dấu đỏ nhầm lý do thành
   "cổng đã gác".
3. **Chỉ `.tsx` mới lọt.** Hai đột biến trong `nhom.ts` bị bắt ngay. Ranh giới
   trùng khít với ranh giới công cụ: `navigation.test.mjs` đọc `VoTab.tsx` bằng
   **regex trên văn bản nguồn**, `vo-tab-web.test.mjs` lái **bundle** bằng
   puppeteer, và không cái nào hỏi *prop nào được truyền xuống*.

`tsc` bắt được prop **thiếu** — đó là điều PR khẳng định và nó đúng. Nó không
bắt được prop **sai giá trị**. Khoảng cách giữa hai câu đó là M4/M5/M6.

## Phát hiện

Phân loại theo 5 loại blocker của charter. **Không cái nào là blocker** —
hành vi đang ship đúng, tôi đã đi bằng chân trên máy sống.

### PH-1 · nợ cổng · dây nối `VoTab → TinNhan/LenPlan/khoản chi` không ai gác
Ba đột biến M4/M5/M6 lọt qua 790 ca. Hậu quả nếu tái phát: chat lại mở nhóm
demo trong khi người dùng đang nhìn nhóm khác — đúng bug-223337 — và mọi cổng
vẫn xanh. Với M5 còn tệ hơn một bậc: bill ghi vào nhóm demo còn cuộc trò chuyện
về nó ở nhóm khác, tức tiền rơi vào chỗ không ai nhìn.
**Tiêu chí gỡ:** một ca đọc `.tsx` ở mức "prop nào tới màn nào" — cùng dạng
`navigation.test.mjs` đang dùng cho bảng tab — hoặc một ca puppeteer đi đường B
ở trên. Đường B tôi đã viết sẵn và commit kèm; biến nó thành ca của repo là một
việc nhỏ.

### PH-2 · nợ cổng · lời hứa "đọc roster bằng chính người đang đăng nhập" không có cổng
`docRoster` gửi `X-Actor-ID` của người đang đăng nhập, và docstring nói rõ hỏi
hộ người khác *"would report a roster this phone has no right to see"*. Đổi
thành `minh`: **790/790 xanh** (M2). Câu khẳng định về quyền riêng tư không có
gì giữ.

### PH-3 · không tái lập được (một lần trong hai) · bộ mobile có flake
Cùng một cây, hai lượt `npm test`: `fail=8` rồi `fail=0`. Nghĩa thực dụng: một
lượt `npm test` ĐỎ ở repo này phải chạy lại trước khi tin. Tôi mới thấy 1/2 lần,
không đủ để chẩn đoán, đủ để cảnh báo.

### PH-4 · cho Lead quyết, không phải lỗi · mỗi lượt vào bằng số ĐT thêm một thành viên vào Team Đà Lạt
Tác giả đã nêu quyết định sản phẩm này trong mô tả PR. Đây là giá của nó, đo
được: sau **một** lượt đi bộ của tôi, `scripts/check_demo_data.py` in
`members 8/7 -> chia tiền giữa sai số người`. Ngày demo, mỗi lần diễn tập cửa số
điện thoại cộng thêm một người vào nhóm demo.
Tôi đã **tự dọn** phần mình gây ra, bằng route thật chứ không đụng sổ:
`DELETE /contexts/{ctx}/members/{person_id}` → `204`, đếm lại còn `7`, và hàng
`members` biến khỏi đầu ra của cổng.
Ba hàng đỏ còn lại (`batches 7/3`, `expenses 40/5`, `outings 4/3`) **đã đỏ từ
trước** lượt đo của tôi — chứng minh bằng chính việc gỡ một thành viên chỉ sửa
đúng hàng `members`.

### PH-5 · FYI backend, ngoài phạm vi PR này
`DELETE /contexts/{id}/members/{person_id}` trả **403** cho admin nhóm mang
`X-Actor-Roles: group_admin,…` nhưng **204** cho chính người đó tự rời. Có thể
là cố ý (chỉ cho tự rời). Không đo thêm, không mở phiếu.

## Dấu vết lượt đo này để lại trên máy demo 8099

Nói ra vì máy demo dùng chung:

- **5 người** mới trong `people` (tên bắt đầu bằng `QA41`), do năm lượt đi bộ có
  đăng ký thành công.
- **2 nhóm** mới do đường B tạo (`QA41 Nhom Rieng …`), mỗi nhóm 1 thành viên.
- **1 tin nhắn** `QA41 xin chao` + **1 lượt `ai-turn`** trong Team Đà Lạt.
- Tư cách thành viên trong Team Đà Lạt: **đã gỡ**, đếm về lại 7.

## Ô CHƯA QUÉT

Phần quan trọng nhất của báo cáo này.

- **`tests/postgres` chưa chạy.** 551 skipped. Lý do chấp nhận được ở đây và chỉ
  ở đây: `gh pr view 363 --json files` liệt kê **8 file, cả 8 nằm dưới
  `apps/mobile/`** — PR không chạm một dòng backend nào.
- **Chỉ đi bộ trên bundle WEB.** `expo export --platform all` (ios + android) tôi
  không dựng lại; con số đó là của tác giả, không phải của tôi.
- **Chỉ một cỡ màn 390×844, chỉ chủ đề sáng, chỉ Chromium 1194.** Không quét
  320px, không quét chủ đề tối, không quét trình đọc màn hình trên màn chat.
- **Chất lượng câu trả lời của AI không được chấm.** Tôi chỉ chứng minh
  `POST /ai-turn` xảy ra và máy chủ trả 2xx. Nội dung nó nói có đúng không, có
  ảo giác không — chưa đo.
- **Không đâm vào đường xấu**: mạng chậm, bấm Gửi hai lần, back giữa lúc đang mở
  nhóm, token sai, tên nhóm rỗng hoặc dài. Chưa lượt nào.
- **Tab Khám phá vẫn ghim cứng `context_id`** (#362 mục 3.2). Tôi thấy đúng nửa
  đó và chỉ nửa đó: mọi lượt đi bộ, kể cả sau khi người dùng đã tự mở nhóm
  riêng, tab Khám phá vẫn gọi
  `GET /places?context_id=1aa00000-aaaa-4aaa-8aaa-0000a0000001`. Nửa còn lại
  (`403 …/map`) tôi **không** bấm tới. PR nói rõ tab này ngoài phạm vi.
- **`imp detect` không được dùng làm bằng chứng gì.** Tác giả đã tự chứng minh
  nó mù với `.tsx`; tôi không chạy lại và không dựa vào nó.
- **Mã VietQR vẫn chưa ai quét bằng app ngân hàng thật.** PR này không chạm tới
  tiền, nhưng câu đó còn nguyên hiệu lực cho sản phẩm.
- **`make gate ONLY="mobile"`** tôi không chạy — tôi chạy thẳng `npm test`, là
  thứ cổng đó bọc, cộng thêm `pytest` toàn bộ.

## Chạy lại

```bash
git worktree add /tmp/pr363 cafe32cf7ed515acfbc3573ddb0fe024764261c3
git worktree add /tmp/base363 159694b
# node_modules: chép từ một cây đã cài; package.json/package-lock.json KHÔNG đổi
#   giữa hai SHA (git diff --stat 159694b cafe32c -- .../package*.json trả rỗng)

cd /tmp/pr363/apps/mobile && npm test                     # 790/790
cd /tmp/pr363            && python3 -m pytest services/api/tests tests -q

# đỏ-trước
cp /tmp/pr363/apps/mobile/tests/nhom-cua-phien.test.mjs /tmp/base363/apps/mobile/tests/
cd /tmp/base363/apps/mobile && npx tsc -p tsconfig.test.json \
  && node tools/fixup-esm.mjs && node --test tests/nhom-cua-phien.test.mjs   # 0/5

# bảng đột biến (sửa đường dẫn TREE ở đầu file nếu đặt worktree chỗ khác)
python3 docs/claude/2026-08-30/qa-tt-0041/dot-bien-nhom-ts.py
python3 docs/claude/2026-08-30/qa-tt-0041/dot-bien-day-noi-tsx.py

# đi bộ trên API sống — cần 8099 đang chạy
cd /tmp/pr363/apps/mobile && EXPO_PUBLIC_API_URL=http://127.0.0.1:8099 \
  npx expo export --platform web --output-dir /tmp/b-sau --clear
(cd /tmp/b-sau && python3 -m http.server 8177 &)   # rồi so hash index.html trước khi tin cổng đó
export PUPPETEER_EXECUTABLE_PATH=/home/lakiet/.cache/ms-playwright/chromium-1194/chrome-linux/chrome
node docs/claude/2026-08-30/qa-tt-0041/di-bo-cua-so-dien-thoai.mjs /tmp/b-sau 8177 sau
node docs/claude/2026-08-30/qa-tt-0041/di-bo-nhom-cua-phien.mjs 8177 nhomphien-sau
```

Ảnh chụp màn (`/tmp/qa41-anh-*.png`) và JSON thô (`/tmp/qa41-ket-*.json`) nằm
ngoài repo: ảnh là binary, repo guard fail closed với binary — đúng như nó nên.

---

`protocol_version: v1` · verdict `PASS` · blocker còn mở: **không có** ·
kỹ năng đã dùng: `e2e-testing`, `bug-reproduction`
