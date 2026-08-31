# qa3-064648 — mẫu số 47 đến từ đâu, và tại sao nó không còn dùng được

- **Đo trên**: `main` tại `1ab772d`
- **Nguồn được kiểm**: `/home/lakiet/mobile/product/feature_list.md` (repo `/home/lakiet/mobile`, commit `2a82b1a`)
- **Kỹ năng đã gọi**: `cursor-team-kit:verify-this`
- **protocol_version**: v1
- **Ngày**: 2026-08-31

Đây là **kiểm mẫu số**, không phải phán quyết PR. Không có verdict
`APPROVE` / `REQUEST_CHANGES` / `REJECT` trong tài liệu này.

Bốn tài liệu qa2 đêm nay (`qa2-002802`, `qa2-014654`, `qa2-034807`,
`qa2-042742`) đều đo **tử số** — bao nhiêu trong F01..F47 bấm được. Không
tài liệu nào hỏi 47 từ đâu ra. Tài liệu này chỉ làm phần đó.

---

## 0. Hai phán quyết, tách riêng

> **VERIFIED** — "47 là số heading `F<số>` trong `feature_list.md`."
>
> **NOT VERIFIED** — "47 là mẫu số hợp lệ cho tiến độ PoC."

Con số đếm đúng. Cái nó đếm mới là chỗ sai.

---

## 1. Câu 1 — 47 đến từ đâu?

| | |
|---|---|
| File | `product/feature_list.md`, 1826 dòng |
| Repo | `/home/lakiet/mobile` (khác repo code) |
| Commit | `2a82b1a` — "docs(product): đưa bộ mockup và tài liệu sản phẩm lên repo" |
| Tác giả | `chuoibo` (GitHub noreply) |
| Lúc | **2026-08-30**, lúc **23:22:10** giờ VN |
| Số lần sửa từ đó | **0** — một commit duy nhất chạm file này |

**Quan trọng: chuỗi "47" không hề xuất hiện trong file.**

```
$ grep -cE '\b47\b' feature_list.md
0
```

47 là con số **suy ra**, không phải con số **được khai**. Ai đó đã đếm heading
`F<số>` rồi con số truyền miệng từ đó. Không có dòng nào trong spec nói "sản
phẩm này có 47 tính năng".

Phép đếm đó tái lập được, và cho đúng 47:

```
$ grep -cE '^#+ F[0-9]' feature_list.md
47
$ grep -oE '^#+ F[0-9]+' feature_list.md | grep -oE '[0-9]+' | sort -n | uniq | wc -l
47          # unique = 47, không trùng
             # thiếu trong 1..47: (rỗng), max = 47
```

F01..F47 liên tục, không lỗ, không trùng. **Nên: 47 đúng, với đúng nghĩa "số
heading được đánh số F".**

### 1.1 Phép đếm này mong manh hơn vẻ ngoài

```
$ grep -c '^## F' feature_list.md      → 35
$ grep -c '^# F'  feature_list.md      → 12
$ grep -cE '^#+ F' feature_list.md     → 47
```

**F18–F29 dùng `#` (h1), 35 cái còn lại dùng `##` (h2).** Ai đếm bằng một mức
heading sẽ ra **35** và tưởng mình đã đếm hết.

12 cái bị rơi chính là **EPIC 06 — AI SMART BILL**: Receipt OCR, Bill Item
Detection, Assign Food To Person, Smart Settlement, Payment Link/QR… tức là
**toàn bộ hero của PoC**. Kiểu hỏng im lặng: mất đúng phần quan trọng nhất mà
tổng vẫn ra một con số trông hợp lý.

---

## 2. Câu 2 — còn khớp với sản phẩm hôm nay không?

**Không.** Ba lý do độc lập, mỗi lý do đủ để bỏ mẫu số 47.

### 2.1 Bốn epic trong spec KHÔNG có số F nào

| Epic | Nội dung | Có F? |
|---|---|---|
| EPIC 11 — LOCATION AWARENESS | AI báo "4/6 members arrived" | **không** |
| EPIC 13 — AI TRIP SUMMARY | tổng kết sau mỗi chuyến | **không** |
| EPIC 14 — GROUP ACHIEVEMENTS | badge, gamification | **không** |
| EPIC 15 — NOTIFICATION ENGINE | 4 loại nhắc | **không** |

Đây không phải phần phụ bị bỏ quên. **Chính spec xếp hạng ưu tiên cho chúng**
ở mục 8–10:

- P1 có `Group achievements` (EPIC 14) và `Smart notifications` (EPIC 15)
- P2 có `Location-aware group assistant` (EPIC 11) và `AI-generated trip recap` (EPIC 13)

Spec coi chúng là tính năng thật, có thứ tự làm. Chỉ **cách đánh số** bỏ sót.
Nên sàn trung thực là **51**, không phải 47 — và là "ít nhất 51", vì EPIC 15
có thể tính 1 hoặc 4 tuỳ cách chia.

### 2.2 Năm màn đêm nay: hai màn KHÔNG nằm trong 47

| Màn đêm nay | File | Nằm trong 47? |
|---|---|---|
| Album | `album/AlbumChuyenDi.tsx` | ✅ **F36** Automatic Trip Album |
| AI hiểu nhóm | `ai-hieu-nhom/AiHieuNhom.tsx` | ✅ nhưng gộp **F31+F32+F33+F34** |
| Thành tích | `thanh-tich/ThanhTich.tsx` | ❌ EPIC 14, **không có số F** |
| Cá nhân hóa | `vao-cua/CaNhanHoa.tsx` | ❌ **không có feature nào** |
| Quản trị nhóm | `quan-tri/QuanTriNhom.tsx` | ❌ chỉ là **một trường dữ liệu** |

Hai dòng cuối cần dẫn chứng vì chúng là câu trả lời thẳng cho câu hỏi của anh:

**Cá nhân hóa** — quét cả file, không có feature nào cho việc người dùng chọn
sở thích lúc vào app:

```
$ grep -niE 'personaliz|sở thích|preference|interest' feature_list.md
51:  AI LEARNS GROUP PREFERENCES          ← câu trong Core Product Loop
736: ## F31 — Group Preference Profile    ← hồ sơ NHÓM, AI tự suy, P1
1112:                  User Preferences   ← một hộp trong sơ đồ kiến trúc
1190: get_member_preferences()            ← tên một AI tool
```

`F31` là hồ sơ **nhóm** do AI tự học, không phải màn onboarding người dùng tự
khai. Màn `CaNhanHoa.tsx` là **tính năng thứ 48**.

**Quản trị nhóm** — chữ `admin` xuất hiện **đúng một lần** trong 1826 dòng:

```
$ grep -nE '\badmins?\b' feature_list.md
206:admins
```

Dòng 206 nằm trong khối dữ liệu của `F06 — Create Group`:
`group_id / group_name / avatar / members / admins / created_at`. Đó là **một
trường trong struct**, không phải mô tả hành vi — không có kick, không có
phân quyền, không có chuyển quyền. Màn `QuanTriNhom.tsx` là **tính năng thứ
49**: một trường dữ liệu được nâng thành màn hình.

### 2.3 Tử số và mẫu số không cùng đơn vị

"41/47" đếm **màn** ở tử và **feature** ở mẫu. Một màn `AI hiểu nhóm` phủ bốn
feature — `AiHieuNhom.tsx` import `PreferenceProfileResponse`,
`GroupSuggestionResponse`, `ContextualSuggestionResponse`, `GroupBudgetResponse`
= F31, F32, F33, F34. Ngược lại một feature như F18 Receipt OCR trải qua
`ChupBill` → `KetQuaNhanDien` → `MonCuaToi`. Tỉ số giữa hai đơn vị khác nhau
thì không đọc được như phần trăm.

### 2.4 Có một mẫu số thứ hai, và đội đang dùng CÁI ĐÓ

Cùng commit `2a82b1a` còn đưa lên
`RuDi_Mobile_Product_Mockups/00_product_docs/FEATURE_INDEX.md`:

> **21 màn hình = 7 feature × 3 sub-feature**

Và người dựng màn đang neo vào bộ này chứ không phải vào 47. Header của
`ThanhTich.tsx` tự khai:

```
/** Thành tích — 07.03 of the mockup set, and the one screen of the twenty one
 *  that had no file at all.
```

`07.03` là chỉ số của `FEATURE_INDEX.md`. Nghĩa là **hai mẫu số đang sống song
song**: anh báo cáo theo 47, đội dựng theo 21. Không ai sai, nhưng hai con số
không quy đổi cho nhau được.

---

## 3. Câu 3 — có feature nào đã bị bỏ hoặc gộp chưa?

**Có, cả ba dạng.**

**Gộp** — F31+F32+F33+F34 (+F30 Group Memory cấp dữ liệu) → một màn
`AI hiểu nhóm`. Bốn dòng trong bảng 47, một màn trong app.

**Thu hẹp bằng quyết định, ba lần liên tiếp:**

```
47 feature  (feature_list.md, ngày 2026-08-30)
   ↓ AUDIT_REPORT.md §4: "Không thiếu màn nào so với scope 7 feature × 3 sub-feature đã thống nhất"
21 màn      (FEATURE_INDEX.md, cùng commit)
   ↓ brief PoC: "chứng minh MỘT đường đi, làm tới mức đẹp thật"
1 đường hero
```

**Bị loại khỏi phạm vi mockup** — `AUDIT_REPORT.md` §5 liệt kê 12 vùng "chưa có
mockup riêng", gồm Friend graph (F03/F04/F05), Notifications center, Social Map
(F43), Meet-in-the-middle (F45), AI highlight reel (F37), public feed.

**Và spec tự đánh dấu 4 feature là hậu-MVP nhưng chúng vẫn nằm trong 47.**
Ngay dưới heading `# EPIC 09 — SOCIAL FEED` (dòng 868), ở dòng 870:

> `Feature này nên để sau MVP.`

EPIC 09 = F39 Post, F40 Reactions, F41 Comments, F42 Privacy. Bốn dòng này
luôn được tính vào mẫu số 47 dù chính spec nói đừng làm bây giờ, và mục 11 xếp
"Public social feed" vào P3 — "Không nên build quá sớm". Mọi tỉ số `X/47` vì
vậy **bị kéo xuống bởi những feature không ai định làm**.

---

## 4. Đề nghị cho báo cáo lần sau

Đừng dùng `/47` nữa, hoặc nếu dùng thì phải kèm câu đủ dài để nó không gây hiểu lầm.

Ba mẫu số dùng được, theo thứ tự tôi khuyên:

| Mẫu số | Là gì | Dùng khi |
|---|---|---|
| **/21** | bộ mockup 7×3, đội đang dựng theo cái này | báo tiến độ PoC — **khuyên dùng** |
| **/14** | P0 MUST HAVE, mục 8 của spec | trả lời "MVP xong chưa" |
| **/51** | 47 có số + 4 epic không số | khi thật sự cần nói về toàn bộ spec |

Nếu vẫn muốn giữ 47 thì câu trung thực là: *"47 feature được đánh số, cộng 4
epic không đánh số, trong đó 4 feature spec tự ghi là hậu-MVP và ~12 vùng đã
bị loại khỏi phạm vi mockup."*

---

## 5. Tài liệu này KHÔNG chứng minh gì

- **Không đo tử số.** Tôi không chạy bundle, không bấm màn nào. Bao nhiêu màn
  thật sự bấm được vẫn là con số của qa2 (`32/47` tại `1161570`), và nó vẫn
  mang đúng khiếm khuyết mẫu số mô tả ở trên.
- **Không kiểm 3 màn "nằm trong 47" có làm đúng feature không.** Tôi chỉ đối
  chiếu tên và import, không đo hành vi. `Album` khớp tên `F36` không có nghĩa
  nó làm được việc `F36` mô tả.
- **Không phán xử tính năng 48/49/50 là sai.** Dựng thứ ngoài spec có thể hoàn
  toàn đúng — spec viết lúc 23:22 hôm qua và sản phẩm đã đi tiếp. Vấn đề duy
  nhất là **báo cáo chúng bằng một mẫu số không chứa chúng**.
- **Ranh giới đếm là do tôi chọn.** "EPIC không số = 1 feature" là quy ước của
  tôi; EPIC 15 có 4 mục con nên ai đó có thể đếm ra 54 thay vì 51. Con số 51 là
  **sàn**, không phải giá trị duy nhất đúng.
