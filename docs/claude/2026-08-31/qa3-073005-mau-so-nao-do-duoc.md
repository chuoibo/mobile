# Mẫu số nào mới dùng được? — đo CẠNH, đừng đếm ĐỈNH

- protocol_version: v1
- commit đo: `e556b4a` (nhánh `qa3/mau-so-do-duoc-cho-tien-do-poc`, dựng lại bundle tại đúng SHA này)
- verdict: **hướng 4 của Lead gần đúng, nhưng phát biểu chưa chính xác** — xem §1
- việc trước: `docs/claude/2026-08-31/qa3-064648-mau-so-47-den-tu-dau.md` (PR #440) kết luận
  `47` NOT VERIFIED. Tài liệu này trả lời câu tiếp theo: *phải đo gì*.

---

## 0. Trả lời gọn cho Lead

Câu "PoC không nên đo bằng tỷ lệ" **chưa đúng hẳn**. Tỷ lệ vẫn dùng được. Cái hỏng không
phải là *tỷ lệ*, mà là **đơn vị**:

> Mọi mẫu số đang tranh cãi — 47, 51, 21, 14, 54 — đều đếm **ĐỈNH** (màn / mục tài liệu).
> Đường demo là **CẠNH** (bấm từ chặng này sang chặng kia).
> Một app đủ cả 54 màn mà thiếu một cạnh thì demo đứt giữa chừng, và không con số
> đếm-đỉnh nào nói ra điều đó.

Đo lại theo cạnh, trên bản dựng `e556b4a`, bằng cách chạy thật hai con walk của repo:

> **Đường hero có 11 cạnh. Máy bấm qua được 7.**

Con số này thấp hơn `41/47` rất nhiều, và **đó là điểm mạnh của nó, không phải điểm yếu**:
nó không đo "đội đã dựng bao nhiêu thứ", nó đo "người xem demo bấm được tới đâu".
Hai câu hỏi khác nhau, và câu thứ hai mới là câu leader đang thật sự hỏi.

Đề nghị cách báo cáo: **đừng bỏ con số, hãy đổi đơn vị và nói cả hai vế** — §6.

---

## 1. Vì sao "đếm tính năng" hỏng: cùng một cây, bảy con số, không con nào sai

Tất cả đo lại độc lập trong lượt này, không kế thừa số của việc trước.

Trong `/home/lakiet/mobile/product/feature_list.md`:

```
$ grep -cE '\b47\b'        feature_list.md   ->  0     # chuỗi "47" KHÔNG có trong spec
$ grep -cE '^#+ F[0-9]'    feature_list.md   -> 47     # đếm mọi mức heading
$ grep -cE '^## F[0-9]'    feature_list.md   -> 35     # đếm h2 (mất EPIC 06 = hero)
$ grep -cE '^# F[0-9]'     feature_list.md   -> 12     # đếm h1
$ grep -cE '^#+ EPIC'      feature_list.md   -> 15
```

Bốn EPIC không mang số F nào — nên không lọt vào bất kỳ phép đếm `F` nào:

```
$ awk '/^#+ EPIC/{if(n&&!f)print n; n=$0; f=0} /^#+ F[0-9]/{f=1} END{if(n&&!f)print n}' feature_list.md
# EPIC 11 — LOCATION AWARENESS
# EPIC 13 — AI TRIP SUMMARY
# EPIC 14 — GROUP ACHIEVEMENTS
# EPIC 15 — NOTIFICATION ENGINE
```

Trong `apps/mobile` tại `e556b4a`:

```
$ find src/screens -name '[A-Z]*.tsx' | wc -l                     -> 54   # mọi component hoa đầu
$ grep -oE 'from "\./src/screens/[^"]+"' App.tsx | sort -u | wc -l -> 21   # App.tsx import
$ node --test tests/moi-man-co-duong-do.test.mjs                  -> 15   # màn App.tsx MOUNT
$ grep -oE 'step: "[^"]+"' tools/tab-snapshots.mjs | sort -u | wc -l -> 18 # bước probe URL
```

| Quy tắc đếm | Ra | Sai ở đâu |
|---|---|---|
| heading F mọi mức | 47 | bỏ 4 epic không đánh số |
| chỉ h2 | 35 | mất trọn EPIC 06 = hero của PoC |
| chỉ h1 | 12 | mất 35 cái còn lại |
| 47 + 4 epic (mỗi epic = 1) | 51 (SÀN) | ranh giới "epic = 1 feature" là quy ước tôi tự đặt |
| `FEATURE_INDEX.md` bộ mockup | 21 | đội dựng theo nó, nhưng báo cáo lại neo vào 47 |
| P0 MUST HAVE | 14 | chỉ là lát cắt ưu tiên, không phải phạm vi |
| file component hoa đầu | 54 | gộp cả `TheDeXuat`, `BongBong`, `ONhap` — thẻ, không phải màn |

**Không quy tắc nào sai.** Đó chính là chẩn đoán: khi bảy quy tắc hợp lý cho bảy đáp án
và không có quy tắc nào được KHAI ở đâu cả, thì con số không phải một phép đo — nó là một
lựa chọn về cách đếm, mặc áo phép đo.

---

## 2. Năm tính chất một mẫu số phải có

Rút ra từ đúng cái đã hỏng ở trên, không phải từ lý thuyết:

| # | Tính chất | Vì sao |
|---|---|---|
| a | **Suy ra từ HIỆN VẬT bằng chương trình** — không phải đếm tay trong tài liệu mô tả | tài liệu mô tả cái ta *định* làm; hiện vật là cái ta *đã* làm |
| b | **Cùng đơn vị với tử số** | `41 màn / 47 feature` không phải một tỷ số |
| c | **Mỗi phần tử có phán quyết NHỊ PHÂN QUAN SÁT ĐƯỢC** | "F31 xong 70%" không kiểm được; "cạnh này bấm qua được / không" thì kiểm được |
| d | **Phép suy ra TỰ KHẲNG ĐỊNH** (regex khớp 0 phải là ĐỎ) | nếu không, mẫu số tụt về 0 và mọi tỷ lệ thành 100% một cách im lặng |
| e | **Phần tử thêm ngày mai TỰ ĐỘNG hiện ra là chưa-phủ** | danh sách viết tay không bao giờ tự biết mình thiếu |

Chấm các ứng viên:

| Mẫu số | a | b | c | d | e | Dùng được? |
|---|---|---|---|---|---|---|
| 47 (heading spec) | ✗ | ✗ | ✗ | ✗ | ✗ | **không** |
| 51 (47 + epic) | ✗ | ✗ | ✗ | ✗ | ✗ | không |
| 21 (bộ mockup) | ✗ | ~ | ✗ | ✗ | ✗ | không |
| 14 (P0) | ✗ | ✗ | ✗ | ✗ | ✗ | không |
| 54 (file component) | ✓ | ~ | ✗ | ✓ | ✓ | không — đếm thẻ lẫn màn, và vẫn là ĐỈNH |
| 15 (`SO_DO`, màn App.tsx mount) | ✓ | ✓ | ✓ | ✓ | ✓ | **đúng hình dạng**, sai phạm vi — §3 |
| **11 (cạnh đường hero)** | ✓ | ✓ | ✓ | ✓ | ~ | **đề xuất** — §4 |

Về hướng 3 của Lead ("giữ 47 nhưng gắn trọng số, và nói rõ ai gắn"): **không nên.**
Trọng số không sửa được lỗi nào trong năm lỗi trên — nó chỉ thêm một lựa chọn chủ quan
thứ hai lên trên một mẫu số vốn đã là lựa chọn chủ quan. Và nó làm con số khó bác bỏ hơn
chứ không đúng hơn: người đọc giờ phải cãi cả cách đếm lẫn cách cân.

---

## 3. Repo ĐÃ CÓ một mẫu số đúng hình dạng — và đội đã tự tìm ra nguyên tắc này năm lần

`apps/mobile/tests/moi-man-co-duong-do.test.mjs` làm đúng cả năm tính chất: mẫu số
**suy ra** từ import của `App.tsx`, phép suy ra tự khẳng định (`assert.ok(mounted.length > 0)`),
và mỗi màn phải có một trong ba câu trả lời — với thứ bậc bằng chứng được viết rõ:

```
do      — probe đi bộ tới, có ảnh + có kim
quet    — có địa chỉ ?man= mở nguội được (YẾU HƠN, cố ý)
chuaDo  — không máy nào mở được; phải nói lý do bằng chữ
```

Chạy thật trong lượt này:

```
$ node --test tests/moi-man-co-duong-do.test.mjs
# màn App.tsx mount: 15, probe đi qua: 0, có địa chỉ quét: 9, chưa máy nào đo được: 6
1..4  # pass 4  fail 0
```

Và quan trọng hơn — đội đã **độc lập tự phát minh ra phép đo theo cạnh**, năm lần, mà
không ai gọi nó bằng tên đó. Năm file, cả năm lái Chrome thật (`chrome-cdp.mjs`):

```
tests/duong-vao-ban-do-nhom.test.mjs        "Khám phá reaches the two map screens
                                             by pressing, not only by URL"
tests/duong-vao-chi-tiet-dia-diem.test.mjs  "The place card on Khám phá opens the
                                             place detail screen"
tests/duong-vao-dong-thoi-gian.test.mjs     "Lên plan reaches the trip timeline by
                                             pressing a trip, not only by URL"
tests/duong-vao-mon-cua-toi.test.mjs        "có người bấm tới được, và nút Lưu gửi
                                             thật lên server"
tests/duong-dong-binh-chon.test.mjs         "'Đóng bình chọn' là một cú bấm có thật"
```

Lý do sinh ra chúng, chép nguyên từ header `duong-vao-ban-do-nhom`:

> `DaiBanDo` và `BanDoNhom` được bàn giao là "có file, được nhắc ở 6 và 8 chỗ, nên chắc
> là không có gì dẫn tới nó". **Cả hai vế đều sai.**

Đó chính xác là luận điểm của tài liệu này, đội đã vấp phải và tự học ra. Vấn đề còn lại
thuần tuý là **báo cáo**: đội ĐO bằng cạnh, nhưng BÁO CÁO bằng đỉnh (`41/47`).

### Chỗ `moi-man-co-duong-do` đang mù

Mẫu số của nó suy ra từ **import của `App.tsx`** — nên màn do vỏ `AppRoot.tsx` mount thì
nó không thấy:

```
$ grep -oE 'from "\.\./screens/[^"]+"' src/navigation/AppRoot.tsx
  chat/nhom · mo-dau/MoDau · vao-cua/DangKy

$ grep -nE 'MoDau|DangKy' App.tsx
  221: * this group without being one of the seeded seven -- `DangKy.tsx` registers
       ^ chỉ trong một COMMENT. App.tsx không hề import hai màn này.
```

`MoDau` (mở app) và `DangKy` (đăng nhập) là **chặng 1 và chặng 2 của đường hero** — hai
màn mọi buổi demo bắt đầu từ đó — và chúng nằm ngoài mẫu số của đúng cái cổng tồn tại để
không màn nào vô hình. Đây là cùng một lớp lỗi cổng đã ghi trong `tools/screen-snapshots.mjs`
dòng 38: *"tab gate ở `quet-du-tab.test.mjs` cũng không nói được — nó kiểm `tabs.ts`, mà
`MoDau` không phải một tab, nên nó lọt qua đúng cái cổng dựng ra để bắt nó."*

Ghi nhận: hai màn này **không** phải chưa được đo — `screen-snapshots.mjs` đi bộ qua cả hai
(§4). Cái sai là **phạm vi mẫu số**, không phải độ phủ.

---

## 4. Phép đo đề xuất: 11 cạnh của đường hero — và số đo thật là 7/11

Mẫu số lấy từ **chính brief của leader**, chứ không từ heading của một file mô tả — nên
nó không phụ thuộc vào việc ai dùng `#` hay `##`:

```
mở app → đăng nhập → Khám phá (thấy AI MATCH)
→ vào nhóm → chat, AI gợi ý chỗ ăn → chốt
→ CHỤP BILL → AI đọc từng món → gán món cho người
→ AI chia → kết quả + VietQR → Cá nhân thấy tài chính cập nhật
```

12 chặng ⇒ **11 cạnh**. Cạnh mới là đơn vị: chặng có tồn tại mà không bấm sang được thì
demo vẫn đứt.

Đo bằng cách **chạy** hai con walk trên bundle dựng lại tại `e556b4a` (không đọc code suy ra):

```
$ npm run build:check                       -> Exported: .expo-build-check
$ node tools/screen-snapshots.mjs --out $OUT -> exit 0, 11 file
   mo-dau · chup-bill · ket-qua-quet-anh · ket-qua · goi-y · goi-y-dong
   nhap · de-xuat · dot-thu · ket-qua-thanh-toan · chia-se
$ node tools/tab-snapshots.mjs               -> exit 0, 18 file
   kham-pha · len-plan · tin-nhan · ca-nhan · ky-niem · nhom · ban-be · dia-diem
   dang-ky · widget · quan-tri · thanh-tich · album{,-mot,-phim} · ban-do
   diem-hen · nhan-loi-moi
```

| # | Cạnh | Phán quyết | Bằng chứng |
|---|---|---|---|
| 1 | mở app → đăng nhập | **ĐI ĐƯỢC** | `screen-snapshots` bấm `"Đăng ký với Apple"` sau `mo-dau` |
| 2 | đăng nhập → Khám phá | **ĐI ĐƯỢC** | bấm `"Vào app với tư cách Minh"` → `waitForScreen("Khám phá")` |
| 3 | Khám phá → vào nhóm | ✗ chưa | `nhom.html` chỉ mở NGUỘI; không walk nào bấm vào — xem ghi chú dưới bảng |
| 4 | vào nhóm → chat | ✗ chưa | app đi thẳng vào **tab** `"Tin nhắn"`, không qua một màn Nhóm |
| 5 | chat → chốt | **ĐI ĐƯỢC** | `duong-dong-binh-chon`: `"Đăng ký với Apple"` → tab `"Tin nhắn: chat nhóm và AI"` → `"Mở bình chọn"` → `"Đóng bình chọn"`, Chrome thật |
| 6 | chốt → CHỤP BILL | ✗ chưa | walk tới máy ảnh bằng lối tắt `[+] → "Tạo khoản chi"`, không đi từ chốt |
| 7 | CHỤP BILL → AI đọc món | **ĐI ĐƯỢC** | `chup-bill` → `ket-qua` liên tục |
| 8 | AI đọc món → gán món | **ĐI ĐƯỢC** | `ket-qua` → `goi-y` |
| 9 | gán món → AI chia | **ĐI ĐƯỢC** | `goi-y`; có kim chống màn rỗng: ma trận phải có `Minh/Trang/Hải` |
| 10 | AI chia → VietQR | **ĐI ĐƯỢC** | `ket-qua-thanh-toan`; có kim `aria-label="Mã VietQR…"` và cấm panel `"Chưa hiện được mã"` |
| 11 | VietQR → Cá nhân CẬP NHẬT | ✗ chưa | xem dưới — đây là cạnh dễ đọc nhầm nhất |

**7 / 11.**

> **Tôi đã tự chấm sai cạnh 5 ở bản nháp đầu, và cách sai đáng ghi lại.** Dòng 8 của
> `duong-dong-binh-chon.test.mjs` có câu *"một màn chỉ mở được sau cửa quét `?man=binh-chon`"*,
> và tôi đọc nó thành cửa vào của chính bài test. Nó không phải — nó tả **trạng thái CŨ** mà
> #402 tìm ra và bài test này sinh ra để vá. Câu hỏi thật của file nằm ở dòng 13-15: *"một
> ngón tay đi từ màn mở đầu có tới được nó không"*. Đọc một câu văn trong header rồi chấm
> điểm là đúng cái lỗi tài liệu này đang tố cáo, chỉ ở quy mô một dòng. Sửa được vì tôi mở
> ra xem nó `bam` cái gì (dòng 134, 145, 180, 228) thay vì tin phần mô tả.

**Cạnh 3 và 4 có thể là lỗi của MẪU SỐ, không phải của app.** Brief tả "vào nhóm → chat"
như thể nhóm là một cái hộp phải bước vào. App lại là app tab: `"Tin nhắn"` **chính là** chat
nhóm — `a11yLabel` của nó trong `src/navigation/tabs.ts` viết thẳng *"Tin nhắn: chat nhóm và AI"*.
Nếu thiết kế đã chốt bỏ chặng "vào nhóm" thì mẫu số đúng là **10 cạnh** và số đo là **7/10**.
Tôi KHÔNG tự quyết việc đó — đây là câu hỏi về phạm vi demo, thuộc quyền Lead/leader.
Nhưng hãy để ý: **đúng loại câu hỏi mà một mẫu số tốt phải làm nổi lên**, và là câu mà `41/47`
không bao giờ có thể đặt ra.

### Cạnh 11 là ví dụ rõ nhất cho toàn bộ luận điểm

Mở `ca-nhan` nguội bằng `tab-snapshots` cho ra số tiền trông rất thuyết phục:

```
$ grep -oE '[0-9]{1,3}(\.[0-9]{3})+ ?đ' .screen-snapshots/ca-nhan.html | head -3
860.000đ · 500.000đ · 360.000đ
```

Nhưng brief không viết "Cá nhân **có** tài chính". Brief viết "Cá nhân thấy tài chính
**CẬP NHẬT**". Những con số kia là số **fixture**, không phải số vừa chia ra ở cạnh 10.
Đếm-đỉnh chấm cạnh này XANH (màn có, số có, đẹp). Đếm-cạnh chấm nó ĐỎ, và đếm-cạnh đúng.

### Lối tắt `[+]` — nói cho công bằng với đội

Ba cạnh chưa đi được **không** có nghĩa demo đứt. Con walk tới được máy ảnh bằng
`Khám phá → [+] Tạo mới → "Tạo khoản chi"`, và đi trọn phần tiền. Nghĩa là:

- **App chạy được.** Nửa tiền — phần khó nhất, và phần đã có 41 golden vector — đi liên tục
  từ máy ảnh tới VietQR, có kim chống-quét-nhầm-màn ở hai chặng cuối.
- **Nhưng lối đi mà brief hứa** (xã hội → chat → AI gợi ý → chốt → bill) **chỉ được đo một
  nửa.** Chat → chốt đã có người bấm qua (cạnh 5). Còn khớp nối `chốt → CHỤP BILL` — đúng
  cái bản lề gắn nửa xã hội vào nửa tiền — thì **không walk nào đi qua**: máy ảnh hiện chỉ
  tới được bằng lối tắt `[+]`.

### Một điểm khác biệt phải giữ cho rõ: từng-cạnh ≠ một-mạch

`7/11` là điểm **từng cạnh** — mỗi cạnh do một con walk nào đó bấm qua, không phải cả 11
trong một phiên. Chuỗi liền mạch dài nhất trong MỘT phiên là `screen-snapshots`:
cạnh 1–2, rồi nhảy tắt, rồi cạnh 7–8–9–10 (bốn cạnh liên tiếp). Hai thước đo này khác nhau
và **một-mạch mới là thước gần với buổi demo thật hơn**; tôi báo thước từng-cạnh vì nó là
thứ đo được hôm nay, và ghi rõ ở đây để không ai đọc `7/11` thành "đi một mạch được 7".

Đó là câu mà `41/47` không thể nói ra, dù nói đi nói lại bao nhiêu lần.

---

## 5. Cái gì đo được và cái gì KHÔNG

**Đo được, đã đo trong lượt này:**
- Bảy quy tắc đếm cho bảy mẫu số khác nhau trên cùng một cây — lệnh tái lập ở §1.
- 15/0/9/6 của `moi-man-co-duong-do`, chạy thật.
- Hai con walk chạy thật trên bundle dựng lại tại `e556b4a`, cả hai exit 0, 11 + 18 file.
- 7/11 cạnh, mỗi cạnh trỏ vào một bước walk hoặc một file test CÓ THẬT, đã mở ra đọc xem
  nó bấm cái gì (không chấm điểm bằng phần mô tả — xem hộp tự đính chính ở §4).

**KHÔNG đo được / KHÔNG khẳng định:**
- **`7/11` chưa được cổng nào gác.** Nó là phán quyết đọc-rồi-chấm của tôi trên đầu ra của
  hai con walk. Đọc nó như một số liệu tự-bảo-trì là đúng cái lỗi tài liệu này đang tố cáo.
  Cách gỡ ở §6.
- Cạnh 3–6 tôi chấm "chưa" nghĩa là **chưa ai chứng minh**, KHÔNG phải "hỏng". Rất có thể
  bấm tay là qua. Chưa đo ≠ đã hỏng — nhưng cũng ≠ xanh.
- Hai con walk **chặn API bằng fixture** (`API_BASE = "http://api.build-check.invalid"`).
  Chúng chứng minh giao diện đi được, KHÔNG chứng minh máy chủ thật trả cùng thứ đó.
- Không đo AI thật. `MATCH 95%` trên `kham-pha.html` là fixture, không phải Gemini trả lời.
- Con số 12 chặng là cách tôi cắt câu brief theo dấu `→`. Cắt khác ra mẫu số khác — **nhưng
  đây là điểm mấu chốt: mẫu số này do LEADER viết ra, nên tranh luận về nó là tranh luận về
  phạm vi demo, đúng cuộc tranh luận nên có.** Còn tranh luận về 47 chỉ là tranh luận về
  kiểu heading của một file.
- Không phán xử `21` hay `14` là sai để dùng cho việc khác. Chúng chỉ không dùng được cho
  câu "demo đi tới đâu".

---

## 6. Đề nghị cách báo cáo — và cách làm nó khỏi mục

Lead nói: *"tôi đã báo leader 41/47 sáu lần, và nếu con số đó không phải cách đúng để nói
về tiến độ thì tôi cần biết để ĐỔI CÁCH BÁO CÁO, không phải để đổi con số."* Trả lời:
**đổi cả hai, và nói rõ vì sao đổi** — nếu chỉ thay số mà không đổi đơn vị thì lần sau lại
đúng câu hỏi này.

Mẫu báo cáo đề nghị, hai vế, không vế nào bỏ được:

> **Đường demo có 11 cạnh. Máy bấm qua được 7.**
> Nửa tiền (chụp bill → AI đọc món → gán món → chia → VietQR) đi liền mạch, có kim chống
> quét-nhầm-màn. Phần chat cũng bấm được tới chốt (mở → bỏ phiếu → đóng bình chọn, Chrome
> thật). Ba cạnh chưa ai chứng minh: vào-nhóm (có thể thiết kế tab đã bỏ chặng này — cần Lead
> xác nhận), chốt → chụp bill (demo hiện đi vòng qua lối tắt `[+]`), và cạnh cuối — Cá nhân
> đang hiện số **fixture**, không phải số vừa chia.
>
> Bề rộng thì tách riêng, và nói rõ đó là đếm đỉnh: `<tử số> / **51 (sàn, không phải 47)**`
> — và tỷ số đó chỉ nói đội dựng được bao nhiêu, không nói người xem bấm được tới đâu.

**Tôi KHÔNG đo tử số `41`.** Nó là con số Lead đang báo, tôi mượn lại để nói về mẫu số và
không kiểm nó lần nào trong lượt này. Đo gần nhất mà tôi biết là `32/47` của qa2. Nếu đổi
mẫu số sang 51 thì tử số phải đo lại trên cùng cây, cùng lượt — ghép tử số cũ với mẫu số
mới là đúng cái lỗi "hai vế khác đơn vị" mà tài liệu này đang chỉ ra, chỉ khác chiều.

**Để `7/11` không mục:** gác nó bằng một file cùng hình dạng `moi-man-co-duong-do.test.mjs`
— bảng 11 cạnh viết tay (vì phán quyết là việc của người), nhưng mỗi ô "đi được" **bắt buộc
trỏ vào một bước walk hoặc một file test CÓ THẬT**, và phép suy ra tự khẳng định. Cạnh thêm
vào ngày mai mà không ai trả lời thì ĐỎ ngay ở commit thêm nó. Tôi **chưa** ship file này
trong lượt này (lượt đã dùng cho đo thật + dựng lại bundle); nếu Lead muốn, đó là việc kế
tiếp gọn nhất và tôi biết chính xác phải viết gì.

Hai việc phụ, nhỏ và độc lập:

1. `moi-man-co-duong-do.test.mjs` nên suy ra mẫu số từ **cả `App.tsx` lẫn `AppRoot.tsx`** —
   hiện `MoDau`/`DangKy` vô hình với nó (§3). Chúng CÓ được đo, nhưng cổng không biết.
2. `tools/tab-snapshots.mjs` **bỏ qua cờ `--out`**: tôi truyền `--out /tmp/heroB-…` và nó
   vẫn ghi vào `apps/mobile/.screen-snapshots/`. Không làm bẩn cây (`.gitignore:283`), nhưng
   là một cái bẫy — ai chạy song song hai lượt sẽ giẫm lên nhau và đọc ra kết quả của lượt kia.
