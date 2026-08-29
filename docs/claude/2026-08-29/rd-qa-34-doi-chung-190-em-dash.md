# rd-qa-34 · PASS #190 — em-dash biến mất khỏi thứ trình đọc màn hình đọc, không chỉ khỏi source

**PASS.**

Lý do, viết trước phần chi tiết: cổng của #190 là cổng **nguồn**, nên tôi không chấm
nó bằng chính nó. Tôi dựng lại cả hai bundle và đo ở **DOM sống**: bản trước PR có
**4 trên 4 `aria-label` của tab mang dấu gạch dài**, bản PR có **0** — cùng một
probe, và probe đó đã đỏ đúng chỗ ở bản trước nên số 0 kia có nghĩa. Chữ **nhìn
thấy được** thì 0 ở cả hai bản, tức đúng như PR nói: đây là câu chữ mắt không thấy.
Cổng chịu được hai đột biến của riêng tôi. Một lỗ phạm vi có thật nhưng **không
chặn**: `App.tsx` nằm ngoài vùng quét, xem mục 5.

```
đo tại   0fe4be0a9d39f0446ab7d2aeb07cd7781f17c607   (head #190)
sha này  là cherry-pick lên origin/main@2d61e39, NHÁNH CHƯA MERGE
đối chứng 2d61e39                                    (đúng đỉnh main lúc đo)
cây đo   /tmp/qa34-head và /tmp/qa34-before, hai worktree ghim SHA,
         `git status` rỗng ở cả hai trước và sau mọi phép đo
```

---

## 1. Đối chứng tầng nguồn — cổng đỏ được trên main hôm nay

Thả **một mình file test** vào cây `2d61e39`, không thả bản sửa câu chữ:

```
/tmp/qa34-before @ 2d61e39 + chỉ tests/dau-gach-dai.test.mjs
  # pass 2  # fail 1
  còn 22 chỗ dùng dấu gạch dài
```

22, đếm bằng máy. Bốn `a11yLabel` của tab có thật trong danh sách:

```
navigation/tabs.ts:42  Khám phá — gợi ý chỗ đi cho nhóm
navigation/tabs.ts:52  Lên plan — chuyến đi của nhóm
navigation/tabs.ts:58  Tin nhắn — chat nhóm và AI
navigation/tabs.ts:64  Cá nhân — hồ sơ và tài chính của bạn
camera/native.ts:42    Camera chưa sẵn sàng — thử lại sau một nhịp.
navigation/VoTab.tsx:125  " chưa dựng — mới có chỗ trong menu.
```

Ở `0fe4be0`: `# pass 3  # fail 0`.

## 2. Đối chứng tầng render — cái này mới là bằng chứng

Cổng của #190 đọc source. Source sạch **không** kéo theo người dùng hết thấy dấu
gạch dài, nên tôi hỏi câu mà cổng đó không hỏi được: nó có thật sự rời khỏi bản
người ta chạy không.

Dựng lại cả hai bundle bằng `expo export --clear`. Hash khác nhau, nên là dựng
thật chứ không phải cache:

```
before  index-2b653c6d294d3746225cea8257543541.js
head    index-f474898ec96a5896cebed1a0ee3e4122.js
```

**Một bẫy đo lường phải nói ra**, vì nó suýt cho tôi một dấu xanh giả và nó sẽ cắn
người kế tiếp: bundle của expo **không chứa một byte ngoài ASCII nào**, và nó mã
hoá tiếng Việt bằng **hỗn hợp `\uXXXX` và `\xXX`** (`\xe1` cho "á", `ắ` cho
"ắ"). Nên `grep "Khám phá"` trên bundle trả về **0** — và `grep "Khám phá — gợi ý"`
cũng trả về 0. Hai số 0 cạnh nhau đọc y hệt "đã sửa xong", trong khi thật ra phép
đo mù. Phải giải mã escape trước khi đếm:

| bundle | em-dash | en-dash (cố ý cho phép) |
|---|---|---|
| trước PR (`2d61e39`) | **22** | 5 |
| head PR (`0fe4be0`) | **0** | 5 |

22 ở bản render khớp đúng 22 mà cổng nguồn tìm ra — phạm vi `src/` của cổng phủ
đúng phần render, không hụt. Và en-dash **5/5 không đổi**: ngoại lệ có chủ ý cho
khoảng giá trị (`~200–250k/người`) không bị PR này quét nhầm.

## 3. DOM sống, Chrome thật, cùng một probe cho hai bản

Probe của riêng tôi (`/tmp/qa34-probe.mjs`): serve bundle, mở Chrome
`--headless=new`, đi qua màn chọn người như người dùng, đợi đủ bốn tab, rồi đọc
mọi `aria-label` và `innerText` của DOM.

```
=== CANARY: bundle TRƯỚC PR ===
   aria-label đọc được:            6
   aria-label CÓ em-dash:          4      <-- probe đỏ đúng chỗ
      ! Khám phá — gợi ý chỗ đi cho nhóm
      ! Lên plan — chuyến đi của nhóm
      ! Tin nhắn — chat nhóm và AI
      ! Cá nhân — hồ sơ và tài chính của bạn
   dòng chữ HIỂN THỊ có em-dash:   0

=== bundle PR HEAD ===
   aria-label CÓ em-dash:          0
   dòng chữ HIỂN THỊ có em-dash:   0
      • Khám phá: gợi ý chỗ đi cho nhóm
      • Lên plan: chuyến đi của nhóm
      • Tin nhắn: chat nhóm và AI
      • Cá nhân: hồ sơ và tài chính của bạn
```

Hai dòng đáng đọc kỹ:

- Canary **đỏ 4/4** ở bản trước. Không có nó thì số 0 ở head chỉ là một probe chết.
- `dòng chữ HIỂN THỊ có em-dash: 0` ở **cả hai** bản. Nghĩa là suốt thời gian trôi,
  không lượt kiểm bằng mắt nào bắt được — nó chỉ sống trong câu trình đọc màn hình
  đọc lên. Đây là chỗ luận điểm của PR đúng theo nghĩa đen, và tôi đo được nó.

Chuỗi truyền: `tabs.ts` → `ThanhTab.tsx:129 accessibilityLabel` → `aria-label` trên
DOM. Chuỗi đó còn nguyên, react-native-web không nuốt `accessibilityLabel` như nó
đã nuốt `accessibilityState`.

Hai ô "câm" ở màn Cá nhân, đọc từ bundle head: `{label:"Kỷ niệm",value:"chưa có"}`,
`{label:"Đánh giá",value:"chưa có"}` — trước đây chính là `"—"`.

## 4. Bốn đột biến — hai cái của riêng tôi, khác của tác giả

| # | đột biến | kỳ vọng | thật |
|---|---|---|---|
| M1 | template literal **có nội suy**, em-dash nằm ở đoạn `TemplateTail`: `` `Xin chào ${t} — mời bạn đi chơi` `` | ĐỎ | **ĐỎ** `# pass 2 # fail 1` |
| M3 | file mới trong thư mục con **mới** `src/qa-tam/sau/hon/moi.tsx` | ĐỎ | **ĐỎ**, chỉ đúng `qa-tam/sau/hon/moi.tsx:1` |
| M2 | em-dash trong `App.tsx` (**ngoài** `src/`) | — | **XANH** — xem mục 5 |
| — | khôi phục cả ba | 3/3 | 3/3, `git status` rỗng |

M1 quan trọng vì nó là dạng chuỗi mà một phép duyệt AST viết ẩu dễ bỏ sót nhất:
`TemplateHead/Middle/Tail` là ba node khác nhau, không phải một. Cổng bắt được.

## 5. Lỗ phạm vi — có thật, KHÔNG chặn

`sourceFiles(SRC)` chỉ đi vào `apps/mobile/src`. `App.tsx` nằm cạnh nó, không ở
trong nó. Tôi tiêm một chuỗi có em-dash vào `App.tsx`, cổng vẫn **3/3 xanh**.

Đo độ lớn của phần không được gác, bằng chính hàm `readableChunks` của cổng:

```
App.tsx:  206 đoạn chữ,  23 đoạn là câu tiếng Việt người dùng đọc
index.ts:   2 đoạn chữ,   0
```

Vài câu trong 23 đó:

```
• Đóng khoản chi, quay lại các tab      <- nhãn a11y, đúng loại đã trôi lâu nhất
• Ghi tài khoản nhận cho
• xem trước chia
• người ứng tiền
```

Và `App.tsx` không phải file phụ: nó là luồng người tổ chức, tức **chính đường
hero** (camera → bill → chia tiền → VietQR).

Vì sao đây **không** phải blocker: `App.tsx` hôm nay **sạch**, không có em-dash nào.
Không có gì hỏng, và #190 làm mọi thứ tốt lên chứ không làm xấu đi. Đây là việc
tiếp theo, không phải điều kiện của PR này.

Gỡ chặn cho lượt sau: đổi `sourceFiles` nhận thêm gốc `apps/mobile` với danh sách
loại trừ (`node_modules`, `dist-*`, `.expo*`, `tests`, `tools`), hoặc thêm `App.tsx`
và `index.ts` vào danh sách quét. Nhớ nâng luôn hai sàn ở test 2 — chúng là thứ giữ
cho "0 phát hiện" không sinh ra từ một phép duyệt mù.

## 6. Cổng đầy đủ, cây sạch

```
cd apps/mobile && npm test          # tests 511  pass 511  fail 0  skipped 0
                                    # (main 508 + 3 test của cổng này; bước đầu là expo export thật)
python3 -m pytest services/api/tests tests -q
                                    # 1278 passed, 287 skipped, 4597 subtests passed in 75.08s
```

`# skipped 0` ở lượt mobile là con số đáng chú ý: các test trình duyệt trong đó
(`vo-tab-web`, `aria-state`, `aria-vai-tro`, …) bỏ qua bằng `{ skip: ... }` khi
không tìm thấy Chrome. Không có dòng skip nào, nên chúng **đã chạy thật**, không
xanh rỗng.

287 skipped ở lượt backend là tầng `tests/postgres` (thiếu `MOBILE_TEST_DATABASE_URL`).
PR này không chạm một dòng Python nào nên đó không phải bề mặt rủi ro ở đây — nhưng
nó là **skip, không phải xanh**, và tôi ghi nó vào mục 7.

## 7. Ô CHƯA quét

- **Bản native (iOS/Android).** Tôi chỉ đo bản web export. `a11yLabel` →
  `accessibilityLabel` là code dùng chung nên nhiều khả năng như nhau, nhưng
  *nhiều khả năng* không phải *đã đo*. Không có thiết bị thật trong lượt này.
- **Trình đọc màn hình thật.** Tôi đọc chuỗi `aria-label` từ DOM; tôi **không** cho
  TalkBack hay VoiceOver đọc nó lên. Việc dấu `:` nghe có tự nhiên hơn dấu gạch dài
  không, với người dùng thật, là câu chưa ai trả lời.
- **Tầng `tests/postgres`** — 287 skipped, không chạy trong lượt này.
- **Mã VietQR quét bằng app ngân hàng thật** — vẫn mở, như mọi lượt. Không agent nào
  quét được mã QR; cần leader và một điện thoại.
- **Các màn ngoài vỏ tab, ở DOM sống.** Probe DOM của tôi dừng ở vỏ tab. Phần còn
  lại được phủ ở tầng bundle (giải mã toàn bộ chuỗi, 0 em-dash trên **cả** bundle),
  chứ không phải bằng mắt trên từng màn.

## 8. Phân loại theo 5 loại blocker của charter

Không có blocker nào thuộc 5 loại. Không chạm tiền, không chạm quyền riêng tư,
không đổi hợp đồng route, đối chứng tái lập được ở cả hai tầng.

Mục 5 là **suggestion**, không phải blocker: không vi phạm cổng nào đang có, không
làm hỏng gì đang chạy.
