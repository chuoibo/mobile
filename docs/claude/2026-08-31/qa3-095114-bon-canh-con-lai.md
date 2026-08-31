# Bốn cạnh còn lại: mỗi cạnh một phán quyết, đo bằng ngón tay chứ không bằng đọc code

- protocol_version: v1
- commit đo: `f9a3b68` (`origin/main` lúc bắt đầu lượt), bundle **tự dựng lại** trong lượt này
- skill bắt buộc đã gọi: `e2e-testing` (chặng 4 — lát cắt dọc qua chính client; chặng 6 — thăm dò), `exploratory-testing` (charter + session log)
- verdict: **mẫu số 11 → 10, và số đo 7/11 → 9/10**
- việc trước: `docs/claude/2026-08-31/qa3-073005-mau-so-nao-do-duoc.md` (PR #446, đã merge)
  kết luận *"đường hero có 11 cạnh, máy bấm qua được 7"* và để mở bốn cạnh: 3, 4, 6, 11.

---

## 0. Trả lời gọn cho Lead

Bốn cạnh, bốn phán quyết. Không cạnh nào còn ở trạng thái "chưa biết".

| Cạnh | Phán quyết | Một câu |
|---|---|---|
| 3 · Khám phá → **vào nhóm** | **KHÔNG PHẢI CẠNH** | nút "vào nhóm" không tồn tại trong app này, và không phải vì thiếu — vì app chỉ có một nhóm |
| 4 · vào nhóm → chat | **KHÔNG PHẢI CẠNH** | gộp với cạnh 3 thành **một** cạnh `Khám phá → chat nhóm`, và cạnh đó **ĐI ĐƯỢC** |
| 6 · chốt → CHỤP BILL | **CẠNH THẬT, CHƯA AI ĐI → đã đo, ĐI ĐƯỢC** | ba cú bấm từ đúng cái màn nút "Đóng bình chọn" sống trên đó |
| 11 · VietQR → Cá nhân cập nhật | **CẠNH THẬT, CHƯA AI ĐI HẾT** | hai nửa đều đo được và đều đạt; **một mạch thì chưa**, và cái chặn là phép đo chứ không phải app |

Nên:

> **Đường demo có 10 cạnh. Máy bấm qua được 9.**

Ba nguồn của bước nhảy `7/11 → 9/10`, tách rời vì chúng khác loại — gộp chúng
lại là cách một con số đẹp lên mà không có gì tốt lên:

| Nguồn | Đóng góp | Loại |
|---|---|---|
| đo cạnh 6 (chưa ai đo, đo ra ĐI ĐƯỢC) | +1 tử số | **độ phủ thật tăng** |
| đo cạnh 3+4 gộp (chưa ai đo, đo ra ĐI ĐƯỢC) | +1 tử số | **độ phủ thật tăng** |
| bỏ đỉnh "vào nhóm" khỏi mẫu số | −1 mẫu số | **sửa phép đo, app không đổi** |

Hai dòng đầu là app tốt hơn chỗ ta tưởng. Dòng thứ ba là **thước cũ sai**, và
sai theo hướng làm sản phẩm xấu đi — đúng cái bẫy việc này được giao để tránh.

---

## 1. Cạnh 3 và 4: "vào nhóm" không phải một đỉnh

### Đo, không đọc

Bundle tự dựng lại trong lượt này, rồi lái Chrome thật (390×844, `puppeteer-core`,
cùng `installBeforeApp` mà hai con walk của repo dùng). Từ màn mở đầu:
`"Đăng ký với Apple"` → `"Vào app với tư cách Minh"` → Khám phá.

**Mọi thứ bấm được trên Khám phá** — không phải grep, mà là quét DOM lấy mọi
`button/[role=button]/[role=tab]/[role=radio]` đang thấy được:

```
button: Tìm bằng AI
radio:  Tất cả
tab:    Khám phá: gợi ý chỗ đi cho nhóm
tab:    Lên plan: chuyến đi của nhóm
tab:    Tin nhắn: chat nhóm và AI
tab:    Cá nhân: hồ sơ và tài chính của bạn
button: Tạo mới
```

Không có gì tên "Nhóm", "Vào nhóm", "Chọn nhóm". Rồi bấm **một** cú vào tab
`"Tin nhắn"` và ghi lại **mọi trạng thái màn liên tiếp trong 12 giây** (lấy mẫu
200ms một lần, gộp trạng thái trùng) — một màn trung gian "đang vào nhóm" phải
hiện ra ở đây:

```
1 trạng thái liên tiếp từ MỘT cú bấm:
 [0] T Team Đà Lạt 7 thành viên | Chat Plan Thành viên File | AI hiểu nhóm | ...
```

**Đúng một trạng thái.** Không có màn trung gian. Màn hiện ra đã là màn nhóm —
tiêu đề của nó *là* tên nhóm và số thành viên (`Team Đà Lạt · 7 thành viên`), và
tab con `Chat` của nó *là* luồng chat.

### Vì sao đây là "không phải cạnh" chứ không phải "cạnh chưa làm"

Một đỉnh thiếu nút bấm và một đỉnh không tồn tại nhìn giống nhau từ ngoài. Phân
biệt được bằng ba dữ kiện, cả ba đo được:

1. **Màn duy nhất trong app tên "Nhóm" là màn TẠO nhóm.** `src/screens/vao-cua/Nhom.tsx`,
   tới được bằng `[+] → "Tạo nhóm. Lập hội mới, mời bạn vào"` (có trong danh sách
   bấm được của menu `[+]` ở trên). `tools/tab-snapshots.mjs:144` chốt bằng kim
   `"Lập hội mới"` và ghi rõ lý do: *"nothing passes a group into `Nhom` from the
   fragment, so there is no member list to wait for"*. Đó là F03/F04 — **lập hội
   mới**, không phải **bước vào cái hội mình đang ở**.
2. **Không có bộ chọn nhóm nào tồn tại.** `grep` cho `danhSachNhom` / `doiNhom` /
   `chuyenNhom` / `listContexts` trong `src/` ra **0**. `moNhomChoMan()`
   (`src/screens/chat/nhom.ts:329`) nhận **một** nhóm phiên hoặc dựng nhóm demo —
   không có nhánh nào chọn giữa nhiều nhóm.
3. **Máy chủ cũng nói một.** `GET /people/{id}/finance` trên stack thật trả
   `group_count: 1`, và màn Cá nhân in đúng số đó (§4).

Một app một-nhóm không có chỗ cho câu hỏi "vào nhóm nào". Câu "vào nhóm" trong
brief mô tả một app có danh sách hội; app đang có là app tab, và **`"Tin nhắn"`
chính là nhóm** — `a11yLabel` của tab tự khai điều đó: `"Tin nhắn: chat nhóm và AI"`.

### Nên mẫu số đổi, và chỉ đổi đúng chỗ này

Brief cắt theo `→` ra 12 đỉnh ⇒ 11 cạnh. Bỏ đỉnh `vào nhóm` còn 11 đỉnh ⇒ **10 cạnh**.
Cạnh 3 và 4 gộp thành **một** cạnh `Khám phá → chat nhóm`, và cạnh đó **ĐI ĐƯỢC**
(một cú bấm, đo ở trên).

Giữ nó trong mẫu số làm con số **thấp đi một cách sai**: nó tính điểm trừ cho app
vì không có một màn mà thiết kế đã cố tình không có. Đây đúng là ô Lead cảnh báo
trước khi giao việc, và nó có thật.

**Điều kiện phán quyết này hết hiệu lực — ghi ra để nó không mục:** nếu app ship
danh sách nhóm hoặc bộ chuyển nhóm (nút `"Tạo nhóm"` trong `[+]` đã cho phép tạo
cái thứ hai, chỉ chưa có đường đi tới nó), thì `vào nhóm` **thành** một đỉnh thật
và mẫu số quay lại 11. Phán quyết này gắn với *app một-nhóm*, không phải với brief.

---

## 2. Cạnh 6: chốt → CHỤP BILL — cạnh thật, và đi được

Việc trước chấm cạnh này `✗ chưa` với lý do: *"walk tới máy ảnh bằng lối tắt
`[+] → Tạo khoản chi`, không đi từ chốt"*. Lượt này đo lại và **kết luận đó sai**.

Chỗ sai là một giả định chưa ai kiểm: rằng `[+]` là một lối tắt **ngoài** đường
hero. Không phải — `[+]` là điều khiển toàn cục nằm ngay trên thanh tab, nên nó
có mặt **trên chính cái màn chốt xảy ra**.

### Trước hết: chốt xảy ra ở đâu

Lượt đầu tôi tìm nút `"Mở bình chọn"` trên tab con `Chat` và **không thấy** —
suýt báo là "không có bình chọn". Nó nằm ở tab con **`Plan`** (`denTabPlan` trong
`tests/duong-dong-binh-chon.test.mjs:171`). Ghi lại vì đây là một cái bẫy: không
thấy trên bề mặt mình đang đứng thì im lặng đọc thành không có.

Trạng thái tab con `Plan`, đo thật:

```
T Team Đà Lạt 7 thành viên | Chat Plan Thành viên File | AI hiểu nhóm
Bình chọn của nhóm | Sáng mai ăn gì? | Bánh mì 0 phiếu | Phở 0 phiếu
0/7 thành viên đã bỏ phiếu | Mở bình chọn mới | Kế hoạch ...
```

bấm được ở đây:

```
tab: Chat / Plan / Thành viên / File
button: AI hiểu nhóm
radio:  Bánh mì, 0 phiếu, không đang dẫn
radio:  Phở, 0 phiếu, không đang dẫn
button: Mở bình chọn mới
tab:    Khám phá / Lên plan / Tin nhắn / Cá nhân
button: Tạo mới          <-- [+] có mặt NGAY TRÊN màn chốt
```

`"Đóng bình chọn"` — cú bấm *là* chốt, đã được `duong-dong-binh-chon.test.mjs`
chứng minh (cạnh 5, đã tính) — sống trên đúng bề mặt này.

### Rồi đi từ đó tới máy ảnh

```
[S1.1] đang đứng trên màn CHỐT (tab con Plan, có "Mở bình chọn mới")
[S1.2] [+] "Tạo mới" mở được NGAY TRÊN màn đó
[S1.3] TỚI ĐƯỢC MÁY ẢNH: "Huỷ  Chụp bill  Đưa bill vào khung hình
       AI sẽ nhận diện từng món ngay sau khi chụp ..."
```

**Ba cú bấm, không địa chỉ URL nào, Chrome thật:** `[+] Tạo mới` →
`"Tạo khoản chi. Chụp bill hoặc nhập tay, AI chia tiền"` → màn `Chụp bill`.

**Cạnh 6 ĐI ĐƯỢC.**

### Đọc yếu và đọc mạnh — nói rõ tôi chấm theo cái nào

- **Đọc yếu** (ngón tay đi từ màn chốt tới máy ảnh được không): **ĐẠT**, đo ở trên.
- **Đọc mạnh** (chỗ vừa chốt có được mang theo vào khoản chi không — chốt "Xóm Lèo"
  rồi khoản chi tự mang tên Xóm Lèo): **KHÔNG ĐẠT.** `[+] → Tạo khoản chi` mở một
  khoản chi trắng; không có gì nối quán đã chốt với tờ bill.

Tôi chấm theo **đọc yếu**, vì brief viết một mũi tên giữa hai chặng — mũi tên là
chuyển tiếp, không phải mang-theo-ngữ-cảnh. Nhưng đọc mạnh là câu hỏi thật cho
chất lượng demo, nên nó nằm ở §5 như ô chưa quét, không bị nuốt vào một dấu tích.

Ghi thêm một đường nữa tôi tìm thấy trong lúc đo, **không** dùng để chấm điểm:
`src/screens/chat/TinNhan.tsx:900` có nút `"Tách tiền"` trên từng bong bóng chat —
chat → khoản chi qua `POST /contexts/{id}/messages/{id}/expense-draft`, tức là
đường có mang ngữ cảnh. Nhưng nó **không đi qua máy ảnh**, nên nó không phải cạnh 6.
Và trong luồng stub của walk nó hiện **0 lần** (`0 nút "Tách tiền"`) vì không tin
nhắn nào trong luồng mẫu đủ điều kiện. Một tính năng có thật, chưa ai đo — nằm
ngoài đường hero, nên nằm ngoài mẫu số này.

---

## 3. Cạnh 11: hai nửa đều đạt, một mạch thì chưa

Đây là cạnh Lead gọi là *"hình dạng cả đêm: một thứ trông như bằng chứng mà không
phải bằng chứng"*. Việc trước chấm nó ĐỎ vì `860.000đ` trên `ca-nhan.html` là số
**fixture**. Lượt này tách cạnh làm hai nửa và đo riêng từng nửa.

### Nửa CÚ BẤM: từ VietQR về được Cá nhân không?

Đi trọn đường tiền trong Chrome thật tới màn VietQR. Mọi thứ bấm được ở đó:

```
button: Đóng khoản chi, quay lại các tab
button: Quay lại gợi ý chia
radio:  Trang
radio:  Hải
button: Chia sẻ kết quả
button: Hoàn tất
```

**Thanh tab KHÔNG có mặt** — luồng khoản chi là một màn chiếm trọn (`VoTab`), nên
không bấm thẳng sang `Cá nhân` được. Hai lối ra, và chúng khác nhau; tôi thử cả hai:

| Bấm | Kết quả đo được |
|---|---|
| `"Hoàn tất"` | **lùi về màn `Đợt thu`**, thanh tab vẫn chưa có → `tab "Cá nhân" bấm được? false` |
| `"Đóng khoản chi, quay lại các tab"` | về `Khám phá`, thanh tab trở lại → `tab "Cá nhân" bấm được? true` → bấm → mở ra màn Cá nhân |

**Nửa cú bấm ĐẠT** — nhưng chỉ qua đúng một trong hai nút, và không phải cái tên
nghe giống "xong việc". Lần đầu tôi bấm `"Hoàn tất"`, tưởng đường cụt và suýt chấm
cạnh này ĐỎ vì lý do sai.

### Nửa DỮ LIỆU: con số Cá nhân đọc có nhúc nhích không?

Màn Cá nhân đọc `GET /people/{id}/finance` (`src/screens/ca-nhan/tai-chinh.ts:223`).
**Không test nào trong repo gọi route đó qua client trên máy chủ thật** —
`tests/e2e/so-du-cuoi-duong-di.test.mjs` gọi `/contexts/{id}/balances`, là route
`App.tsx` dùng, **khác route**.

Dựng stack dùng-một-lần (`scripts/e2e_slice.sh --keep` → `http://127.0.0.1:45409`),
đọc TRƯỚC, ghi một khoản chi qua **chính client đã biên dịch** (`registerPeople` →
`proposeSplit` → `confirmExpense`, đúng thứ tự `App.tsx` gọi), rồi đọc SAU:

```
TRƯỚC  spend_vnd 100000 · settled_vnd 100000 · receivable_vnd 100000 · expense_count 1 · group_count 1
        đã ghi vào sổ: version c73e5780-0ff4-42b5-ba0a-8312fde4c4b6
SAU    spend_vnd 200000 · settled_vnd 200000 · receivable_vnd 300000 · expense_count 2 · group_count 1

=> CÓ ĐỔI:  spend_vnd 100000 -> 200000
            settled_vnd 100000 -> 200000
            receivable_vnd 100000 -> 300000
            expense_count 1 -> 2
```

Σ phân bổ `= 300.000` được khẳng định trước khi confirm, nên đây không phải một
con số trôi tự do.

### Và màn hình có in đúng con số đó không?

Đây là mắt xích việc trước không có. Xuất một bundle thứ hai trỏ **thẳng vào stack
thật** (`EXPO_PUBLIC_API_URL=http://127.0.0.1:45409`, không stub fetch), đăng nhập,
mở Cá nhân:

```
M Minh · Team Đà Lạt · ... · 2 Lần chia bill · 1 Nhóm · chưa có Kỷ niệm · chưa có Đánh giá
"Hai số đầu đọc từ sổ. Kỷ niệm và đánh giá chưa có trong sản phẩm nên để trống."
```

`2` và `1` khớp đúng `expense_count: 2` và `group_count: 1` route vừa trả. **Màn in
số của sổ, không in fixture.** Đối chứng âm nằm sẵn: cùng màn đó chạy dưới stub của
walk (không phục vụ `/finance`) in `0 Lần chia bill · 0 Nhóm` — trạng thái không-có-dữ-liệu,
trung thực, không bịa số.

Và `860.000đ` mà việc trước thấy: nó đến từ `fixtures.finance` viết cứng trong
`tools/tab-snapshots.mjs:1471`. Kết luận "đó là số fixture" **đúng**, và giờ có thêm
vế thứ hai: con số thật tồn tại, và nó động.

### Vậy sao vẫn không tính là ĐI ĐƯỢC?

Vì **không lượt nào làm cả hai nửa trong một phiên.** Thử rồi, và nó dừng ở một
chỗ nói rõ:

```
[A] Cá nhân TRƯỚC: "2 Lần chia bill"
!! DỪNG Ở: AI đọc bill (/receipts/scan trên máy chủ thật)
   màn in: "Máy chủ chưa cấu hình khoá đọc bill nên không gọi được AI.
            Đây là lỗi cấu hình phía máy chủ, không phải [lỗi của bạn]"
```

`scripts/e2e_slice.sh` không truyền `GEMINI_API_KEY` vào stack nó dựng (`grep GEMINI`
trong file ra **0** dòng). Nên trên stack đó không có cách nào tạo một khoản chi
**bằng app** — xem §4.

Ba mảnh ghép lại thì rất giống một cạnh đã đi. Nhưng ghép ba mảnh đo ở ba phiên
khác nhau rồi gọi là một cú đi bộ chính là hình dạng cả đêm nay đi tìm. Nên:

**Cạnh 11 = CẠNH THẬT, CHƯA AI ĐI HẾT.** Chưa ai — kể cả tôi — làm khoản chi trong
app rồi thấy con số Cá nhân nhích lên. Và cái chặn là **phép đo**, không phải app:
mọi mảnh app cần cho cạnh này đều đã đo được và đều đạt.

---

## 4. Hai thứ tìm ra trong lúc đo, đều chặn đúng cạnh 11

**(a) `"nhập tay"` được hứa nhưng không có nút.** Mục menu `[+]` viết
`"Tạo khoản chi. Chụp bill hoặc nhập tay, AI chia tiền"`. Trên bản web, màn `Chụp bill`
chỉ có bốn nút — `Huỷ` · `Chọn ảnh bill` · `Chụp bill` · `Ảnh chụp màn hình` — cả
ba nút không-Huỷ đều đi qua AI. Không có lối nhập tay nào. Hệ quả: máy chủ nào
không có khoá AI thì **không tạo được khoản chi bằng app**, dù allocator và sổ cái
chạy hoàn hảo. *Không kiểm trên bản native* — có thể chỉ là chuyện của web.

**(b) `e2e_slice.sh` dựng stack không có khoá AI.** Đây là thứ rẻ nhất cần sửa để
cạnh 11 đo được một mạch: stack dùng-một-lần đã dựng đúng Postgres, đúng migration,
đúng uvicorn, và `make e2e` xanh 7/7 trên nó — chỉ thiếu một biến môi trường để
chặng `ảnh → món` sống được.

Cả hai đều thuộc lane khác (`(a)` frontend/mobile, `(b)` devops/backend). Tôi
**không sửa**, chỉ báo — và cố ý không mở `bug-to`: `(a)` cần xác nhận trên native
trước khi gọi là lỗi, `(b)` là lựa chọn thiết kế của một script test có thể có lý
do. Đề nghị Lead định tuyến.

---

## 5. Bảng cuối: 10 cạnh, mỗi cạnh một nhãn

`✓` = có một cú bấm thật đi qua, trỏ được vào bước walk / file test cụ thể.

| # | Cạnh | Nhãn | Bằng chứng |
|---|---|---|---|
| 1 | mở app → đăng nhập | ✓ ĐI ĐƯỢC | `screen-snapshots` bấm `"Đăng ký với Apple"` sau `mo-dau` |
| 2 | đăng nhập → Khám phá | ✓ ĐI ĐƯỢC | `"Vào app với tư cách Minh"` → `waitForScreen("Khám phá")` |
| 3 | **Khám phá → chat nhóm** *(gộp 3+4 cũ)* | ✓ **ĐI ĐƯỢC — đo lượt này** | một cú bấm tab `"Tin nhắn"`, **1** trạng thái liên tiếp, tiêu đề `Team Đà Lạt · 7 thành viên` |
| — | ~~vào nhóm → chat~~ | **KHÔNG PHẢI CẠNH** | không có bộ chọn nhóm; `group_count: 1`; màn `Nhom.tsx` là *lập hội mới* |
| 4 | chat → chốt | ✓ ĐI ĐƯỢC | `duong-dong-binh-chon.test.mjs`: mở → bỏ phiếu → `"Đóng bình chọn"`, Chrome thật |
| 5 | **chốt → CHỤP BILL** | ✓ **ĐI ĐƯỢC — đo lượt này** | từ tab con `Plan`: `[+] Tạo mới` → `"Tạo khoản chi…"` → màn `Chụp bill` |
| 6 | CHỤP BILL → AI đọc món | ✓ ĐI ĐƯỢC | `chup-bill` → `ket-qua` liên tục |
| 7 | AI đọc món → gán món | ✓ ĐI ĐƯỢC | `ket-qua` → `goi-y` |
| 8 | gán món → AI chia | ✓ ĐI ĐƯỢC | `goi-y`, có kim chống màn rỗng (`Minh/Trang/Hải`) |
| 9 | AI chia → VietQR | ✓ ĐI ĐƯỢC | `ket-qua-thanh-toan`, kim `aria-label="Mã VietQR…"` |
| 10 | VietQR → Cá nhân CẬP NHẬT | **CHƯA AI ĐI HẾT** | nửa bấm ĐẠT · nửa dữ liệu ĐẠT · một mạch chặn ở `/receipts/scan` thiếu khoá |

> **Đường demo có 10 cạnh. Máy bấm qua được 9.**
> Cạnh cuối là cạnh duy nhất còn mở, và nó mở vì **thiếu một biến môi trường trong
> script test**, không vì thiếu tính năng: cả nút bấm lẫn con số đều đã đo riêng và
> đều đạt trên máy chủ thật.

**Từng-cạnh ≠ một-mạch, vẫn giữ nguyên chỗ khác biệt đó.** `9/10` là điểm từng
cạnh. Chuỗi liền mạch dài nhất tôi tự đi trong **một** phiên lượt này là
`mở app → đăng nhập → Khám phá → chat nhóm → (Chụp bill)` — bốn cạnh, và cạnh
cuối của chuỗi đó đi từ bề mặt chốt chứ không qua cú bấm chốt. Một-mạch gần buổi
demo thật hơn; tôi báo từng-cạnh vì đó là thứ đo được hôm nay, và ghi rõ ở đây để
`9/10` không bị đọc thành "đi một mạch được 9".

---

## 6. Cái gì đo được, cái gì KHÔNG

**Đo được, trong lượt này, lệnh dán ở §7:**

- Bundle tự dựng lại (`390 modules`), không dùng bản dựng sẵn của ai.
- Bốn phiên Chrome thật, mỗi phiên liệt kê **toàn bộ** điều khiển bấm được ở từng
  chặng — không grep tên màn, không đếm số lần nhắc tên.
- `make e2e` trên stack dùng-một-lần: **7 pass · 0 fail · 0 skipped**.
- `/people/{id}/finance` TRƯỚC/SAU một khoản chi thật, bốn trường đổi giá trị.
- Bundle thứ hai trỏ vào stack thật in `2 Lần chia bill · 1 Nhóm`, khớp route.

**KHÔNG đo được / KHÔNG khẳng định:**

- **Cạnh 10 một mạch.** Chặn ở `/receipts/scan` thiếu khoá AI. §3.
- **Đọc mạnh của cạnh 5** (chỗ vừa chốt có được mang vào khoản chi không): **KHÔNG**,
  và tôi cố ý không cho nó chìm vào dấu tích của đọc yếu. §2.
- **Bản native.** Mọi thứ ở đây là RN Web trong Chrome. Nút `"nhập tay"` có thể tồn
  tại trên điện thoại; tôi không kiểm.
- **Ba phiên walk dùng stub fetch** (`http://api.build-check.invalid`). Chúng chứng
  minh giao diện đi được, không chứng minh máy chủ thật trả cùng thứ đó — trừ hai
  phép đo cuối, cố ý chạy trên máy chủ thật đúng vì lý do đó.
- **Không đo AI thật.** `MATCH 95%` trên Khám phá là fixture. Chặng `ảnh → món` đo
  dưới stub; trên máy chủ thật nó chưa từng chạy trong lượt này (nó từ chối).
- **`9/10` chưa được cổng nào gác.** Nó là phán quyết đọc-rồi-chấm của tôi trên đầu
  ra bốn con probe. Đề nghị gác vẫn nguyên như việc trước: một file cùng hình dạng
  `moi-man-co-duong-do.test.mjs`, bảng 10 cạnh viết tay nhưng mỗi ô "đi được"
  **bắt buộc** trỏ vào một bước walk có thật, và phép suy ra tự khẳng định.
- **Mã QR vẫn chưa ai quét bằng app ngân hàng thật.** Ô này không nhúc nhích trong
  lượt này và không được đọc thành đã phủ.

---

## 7. Lệnh đã chạy, để chạy lại được

```bash
cd apps/mobile && npm run build:check          # -> Exported: .expo-build-check (390 modules)

# bốn con probe (đọc/ghi ngoài repo, không làm bẩn cây):
node /tmp/qa3-canh/probe-4-canh.mjs            # Khám phá + [+] + màn VietQR
node /tmp/qa3-canh/probe-ab.mjs                # một cú bấm -> chat nhóm, 1 trạng thái
node /tmp/qa3-canh/probe-b2.mjs                # tab con Plan = bề mặt chốt
node /tmp/qa3-canh/probe-c2.mjs                # cạnh 6 đi được; VietQR không có thanh tab
node /tmp/qa3-canh/probe-s3.mjs                # "Đóng khoản chi, quay lại các tab" -> Cá nhân

# máy chủ thật:
make e2e                                       # 7 pass, 0 fail, 0 skipped
scripts/e2e_slice.sh --keep                    # -> API: http://127.0.0.1:45409
EXPO_PUBLIC_API_URL=http://127.0.0.1:45409 node /tmp/qa3-canh/do-tai-chinh.mjs
EXPO_PUBLIC_API_URL=http://127.0.0.1:45409 npx expo export --platform web \
  --output-dir /tmp/qa3-canh/live-build --clear
node /tmp/qa3-canh/probe-live.mjs              # màn Cá nhân in "2 Lần chia bill · 1 Nhóm"
node /tmp/qa3-canh/probe-live2.mjs             # dừng ở /receipts/scan: thiếu khoá AI
```

Bốn con probe là thứ dùng-một-lần, cố ý để ngoài repo: chúng đo một câu hỏi của
một lượt, không phải cổng. Cái đáng ship là **file gác 10 cạnh** ở §6 — và đó là
việc kế tiếp gọn nhất nếu Lead muốn `9/10` khỏi mục.
