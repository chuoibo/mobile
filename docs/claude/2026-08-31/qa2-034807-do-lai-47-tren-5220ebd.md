# qa2-034807 — Đo lại 47 tính năng trên `main` `5220ebd`: **39/47**, còn thiếu 8

- **Đo trên**: `main` tại `5220ebd` (mốc trước là `19b4760`, `main` đã đi thêm 14 commit)
- **Máy chủ**: stack dùng một lần dựng từ chính `5220ebd` (`scripts/e2e_slice.sh --keep`)
  → `http://127.0.0.1:45465`, PostgreSQL riêng ở `44948`. Không đụng máy demo `:8099`
- **Bundle**: `expo export --platform web --clear` từ `5220ebd`,
  `EXPO_PUBLIC_API_URL=http://127.0.0.1:45465`, phục vụ ở `127.0.0.1:8951`
- **Cửa vào**: Google → Minh, nhóm **Team Đà Lạt** `0465db53-133c-4fed-829b-1bee963f9b96`.
  Khung 390×844
- **Kỹ năng đã gọi**: `exploratory-testing`
- **protocol_version**: v1 · **Ngày**: 2026-08-31

Đây là **kiểm kê hành vi**, không phải phán quyết PR. Không có verdict trong tài liệu này.

---

## 0. Con số

| Mốc | BẤM-ĐƯỢC | Còn thiếu |
|---|---|---|
| `43dc45a` (#394) | 32 | 15 |
| `43dc45a` (#399, đo ở cửa Google) | 35 | 12 |
| `19b4760` (#403) | 36 | 11 |
| **`5220ebd` (lượt này)** | **39** | **8** |

Ba hàng đổi nhãn, mỗi hàng có commit của nó. Không hàng nào tụt lại.

| Hàng | Trước | Giờ | Vì commit nào | Bằng chứng lượt này |
|---|---|---|---|---|
| **F24** Expense From Chat | TẮC | **BẤM-ĐƯỢC** | `789beca` (#408) | `expense-draft 200` → **"Ghi khoản chi"** → `POST 201 /expenses` → `POST 201 /expenses/{id}/confirm` |
| **F31** Preference Profile | KHÔNG-CÓ-ĐƯỜNG | **BẤM-ĐƯỢC (rỗng)** | `2870ae9` (#382) | `GET 200 …/preference-profile` từ màn "AI hiểu nhóm" |
| **F32** Proactive Suggestion | KHÔNG-CÓ-ĐƯỜNG | **BẤM-ĐƯỢC** | `2870ae9` (#382) | `GET 200 …/suggestion` → lịch AI thật render trên màn |

F33 và F34 đã là BẤM-ĐƯỢC từ trước nên không cộng thêm, nhưng lượt này chúng có
**đường đi riêng** thay vì chỉ tình cờ lộ ra trong câu trả lời của AI: cùng màn
đó gọi `contextual-suggestion` và `budget`.

### Đường bấm tới ba hàng vừa sống dậy

```
Tin nhắn → [AI hiểu nhóm]        → 4 route, cả 4 đều 200, đều mang context_id THẬT
    GET 200 /contexts/0465db53-…/preference-profile      ← F31
    GET 200 /contexts/0465db53-…/suggestion              ← F32
    GET 200 /contexts/0465db53-…/contextual-suggestion   ← F33
    GET 200 /contexts/0465db53-…/budget                  ← F34
```

Trên màn, F32 in ra lịch AI thật chứ không phải trạng thái rỗng:

```
Gợi ý cho nhóm · AI gợi ý
Buổi Tối Đà Lạt Ấm Cúng — Tối thứ Bảy tuần tới
  18:30  Tiệm Nướng Xóm Lào   200.000–250.000đ · 4.7 · 1.2km   "Hợp với nhóm"
  20:30  Chill Đêm Đà Lạt     250.000đ · 4.5 · 1.8km           "Hợp với nhóm"
Căn cứ từ lịch sử: 3 buổi đi · 6.785.000đ đã chia · 323.095đ/người
```

F24 đi hết đường tới sổ cái, và **số tiền cộng đúng**:

```
Tiền nướng tối qua · 360.000đ · Người trả: Minh · Người chia: 7 người
[Ghi khoản chi] → "Đã ghi vào sổ nhóm. Số tiền mỗi người:"
  Đức/Minh/Trang/Quân 51.429đ · Hải/Linh/Ngọc 51.428đ
  51.429×4 + 51.428×3 = 360.000  ✔ luật tiền 2 (Σ phân bổ = tổng)
```

---

## 1. Tám hàng còn thiếu

| F## | Tên | Loại | Bước chết / lý do |
|---|---|---|---|
| F43 | Social Map | TẮC | `GET 403 …1aa00000…/map` |
| F44 | Group Heatmap | TẮC | `GET 403 …1aa00000…/heatmap` |
| F45 | Meet-in-the-middle | TẮC | chọn 2 khu → `POST 403 …1aa00000…/meet` |
| F21 | AI Person Recognition | KHÔNG-CÓ-ĐƯỜNG | chỉ `?man=nhan-mat`, 0 lời gọi API |
| F22 | Visual Food Participation | KHÔNG-CÓ-ĐƯỜNG | chỉ `?man=mon-cua-toi`, 0 lời gọi API |
| F23 | Confidence Score | KHÔNG-CÓ-ĐƯỜNG | màn F21 không in con số tin cậy nào |
| F30 | Group Memory | KHÔNG-CÓ-ĐƯỜNG | sở thích chỉ giữ trong phiên, không route lưu |
| F47 | Auto Place Detection | KHÔNG-CÓ-ĐƯỜNG | từ chối có chủ ý; cần GPS + di chuyển thật |

Năm hàng dưới không đổi so với `19b4760`; chi tiết đã ghi ở #403 mục 2, lượt này
chỉ xác nhận lại bằng đi bộ shell, không đo lại từ đầu.

---

## 2. Ba con 403: **không phải ba tính năng hỏng**, và giờ đã đo được cả hai phía

Đây là câu leader hỏi ở #411. Trả lời dứt điểm bằng phép đo hai cột — cùng
actor, cùng máy chủ, chỉ khác `context_id`:

| Route | `0465db53…` (nhóm THẬT của người đang đăng nhập) | `1aa00000…` (hằng số cứng trong client) |
|---|---|---|
| `GET /map` | **200** · `trending` có Chill Đêm Đà Lạt kèm toạ độ | **403** `{"code":"permission_denied","detail":"is_group_member"}` |
| `GET /heatmap` | **200** · `areas: []`, `scanned_checkins: 0` | **403** cùng thân |
| `POST /meet` | **200** · `origins` đủ 2 khu đã chọn | **403** cùng thân |

Nên: **máy chủ khoẻ, quyền chạy đúng.** Cột trái không có con 403 nào. Ba hàng
TẮC là **một lỗi client, ở một dòng**, và nó vẫn nguyên trên `5220ebd`:

```
apps/mobile/src/screens/kham-pha/KhamPha.tsx:196-202
    <BanDoNhom nguoi={nguoi} moDiemHenNgay={…} onQuayLai={…} />
                                       ↑ vẫn không truyền contextId

apps/mobile/src/screens/kham-pha/ban-do-nhom.ts:320,324,328
    banDoUrl(base, contextId: string = CONTEXT_ID)   ← tham số MẶC ĐỊNH
```

Vì `banDoUrl` có giá trị mặc định, chỗ thiếu đó **không phải lỗi biên dịch** —
nó im lặng rơi về nhóm seed. Tiêu chí gỡ chặn không đổi: `contextId={nhom?.id}`,
ba route hết 403.

**Và trả lời luôn giả thuyết "nhóm demo chưa có dữ liệu":** không phải.
`/heatmap` với nhóm thật trả **200 với `areas: []`**, không phải 403. Hai thứ đó
khác hẳn nhau, và ở đây nó là cái thứ nhất. `/map` với nhóm thật thậm chí trả
dữ liệu thật. Nên cách sửa là **sửa client**, không phải seed thêm dữ liệu.

**Hệ quả im lặng vẫn nguyên**, và nó nghiêm trọng hơn ba con 403 vì không có mã
lỗi nào lộ ra. Lượt này tôi vẫn bắt được nó ngay khi mở tab Khám phá:

```
GET 200 /places?context_id=1aa00000-aaaa-4aaa-8aaa-0000a0000001
```

"AI MATCH" đang chấm theo ngân sách và sở thích của một nhóm mà người dùng không
thuộc về, và máy chủ trả `200` nên không cổng nào đỏ.

---

## 3. Một thứ tôi đo hỏng, và nó suýt thành 8 hàng chết giả

**Stack dùng một lần KHÔNG có `GEMINI_API_KEY`.** `scripts/e2e_slice.sh` không
truyền nó, và worktree không có `.env` (nó nằm ở `/home/lakiet/mobile/.env`,
ngoài mọi worktree). Lượt chạy đầu của tôi vì thế đọc được:

```
POST 503 /contexts/…/messages/…/expense-draft          ← F24 trông y hệt "vẫn TẮC"
GET  200 /contexts/…/suggestion
     {"suggested":false,"reason":"unavailable","source":"none"}   ← F32 trông y hệt "chưa có gì"
```

Trên màn, F32 in *"Gợi ý đang tạm thời không dùng được."* — một câu **đúng về
trạng thái và sai về sản phẩm**. Nếu tôi dừng ở đó thì báo cáo này sẽ ghi F24 và
F32 là hàng chết, và cả hai đều sống.

Sau khi khởi động lại uvicorn với khoá (cùng DB, cùng cổng, bundle không phải
dựng lại):

```
GET 200 …/suggestion  →  {"suggested":true,"reason":"ok","title":"Đà Lạt Tối Cuối Tuần…"}
POST 200 …/expense-draft  →  POST 201 /expenses  →  POST 201 /expenses/{id}/confirm
```

Ghi lại thành luật cho lượt sau: **một stack `e2e_slice` là stack KHÔNG có AI.**
Mọi hàng dựa vào Gemini (F08, F11, F16, F18, F24, F26, F32, F33) đo trên đó sẽ
ra "unavailable", và chữ đó đọc y hệt "tính năng chưa làm". Trước khi gọi một
hàng AI là chết, kiểm `GEMINI_API_KEY` có trong env của tiến trình uvicorn không:

```bash
tr '\0' '\n' < /proc/<pid-uvicorn>/environ | grep -c '^GEMINI_API_KEY='
```

---

## 4. Hai thứ cùng tên "check-in" vẫn nuôi hai bảng khác nhau

Bắt lại được trong lúc đo F46, ghi để không ai đọc trạng thái rỗng của F31/F44
thành "chỉ cần bấm check-in là đầy":

```
POST 201 /outing-stops/{id}/checkins        ← bấm "Đã tới" trên màn chuyến, màn đổi thành "Bạn đã tới"
GET  200 /contexts/{id}/heatmap             → scanned_checkins: 0   (vẫn 0)
GET  200 /contexts/{id}/preference-profile  → checkin_count: 0      (vẫn 0)
```

Check-in của **chặng chuyến đi** không chảy vào bảng mà `/heatmap` và
`/preference-profile` đọc. Nên F31 sẽ ở trạng thái rỗng kể cả khi người dùng bấm
"Đã tới" đủ nhiều — đây không phải bug mới, đó là hai khái niệm trùng tên đã
được ghi nhận từ trước; nhắc ở đây vì nó đúng là lý do F31 rỗng.

---

## 5. Phép đo của tôi hỏng bốn lần trong lượt này

Cả bốn đều tạo **hàng chết giả**, nên ghi ra:

1. **`nth(3)` trong `role=tab`.** Tin nhắn render 4 sub-tab (Chat/Plan/Thành
   viên/File) cũng là `role=tab`, nên tab thứ 4 của thanh dưới hoá ra là "File",
   và lượt chạy đầu ghi màn Cá nhân có nội dung của màn Tin nhắn. Sửa: chọn theo
   `aria-label` trong `[role="tablist"]`.
2. **Chỉ số `data-qa2` ôi.** React thay node khi re-render, mất attribute đã
   stamp, và cú bấm treo 30s ở một chỉ số không còn tồn tại — đọc y hệt nút
   chết. Sửa: `bam()` stamp lại ngay trước mỗi lần bấm.
3. **Bấm "Tách tiền" đầu tiên.** Chat giữ lại mọi tin của mọi lượt chạy trước,
   nên "control đầu tiên khớp nhãn" là thẻ của 20 phút trước. Sửa: lấy thẻ
   **cuối cùng**.
4. **"Quay lại bản đồ nhóm" cũng là button.** Nó đứng trên danh sách khu, nên
   "bấm hai button đầu" là điều hướng đi mất, và F45 bị ghi là không có ô chọn
   khu. Sửa: chỉ nhận nhãn bắt đầu bằng `Thêm một người xuất phát từ`.

Canary hai chiều (bắt buộc, nếu không cả tài liệu này phải vứt):

```
CANARY SẠCH             : button 8 · tab 4 · tablist 1 · radio 5 · innerText 699 ký tự · 15 lời gọi API
CANARY XẤU (chặn **/*.js): mọi vai trò = 0 · innerText 0 ký tự · 0 control
```

Máy chủ đúng là `main`:

```
python3 scripts/check_demo_matches_main.py --url http://127.0.0.1:45465 --ref origin/main
→ Máy demo khớp origin/main: 77 route, không thiếu, không thừa.
scripts/e2e_slice.sh --keep → 7 pass / 0 fail
```

---

## 6. Ô chưa quét (đo được, chỉ là lượt này chưa đo)

- **47 hàng ở cửa số điện thoại** và **cửa "Bỏ qua"** (`nguoi = null`) — chưa ai
  đi đủ 47 hàng qua hai cửa đó, lần nào.
- **Năm hàng KHÔNG-ĐO-ĐƯỢC ở #403 mục 3 vẫn nguyên**: F37/F38/F35 (không stack
  nào có ảnh), F05 và F29 (mã QR quét bằng camera / app ngân hàng thật).
- **Hai mươi tám hàng không đổi** lượt này chỉ được xác nhận tới độ sâu 2 tầng từ
  shell, không đi lại từng bước như #403 đã làm. Nhãn của chúng là nhãn **kế
  thừa**, không phải nhãn đo mới.
- **Khung 320 / 1440 và chủ đề tối** — lượt này chỉ 390×844 sáng.

## 7. Chạy lại thế nào

```bash
scripts/e2e_slice.sh --keep                       # in ra API + DSN dùng một lần
# BẮT BUỘC, xem mục 3 — nếu không, mọi hàng AI đo ra "unavailable":
cd services/api && set -a && . /home/lakiet/mobile/.env && set +a
MOBILE_DATABASE_URL='<dsn+psycopg>' python3 -m uvicorn app.api.main:app --host 127.0.0.1 --port <cổng>
python3 scripts/reset_demo_group.py --dsn '<dsn>' --yes
MOBILE_SEED_API_BASE_URL=<api> MOBILE_DATABASE_URL='<dsn+psycopg>' python3 scripts/seed_demo_data.py
EXPO_PUBLIC_API_URL=<api> npx expo export --platform web --output-dir /tmp/qa2-do47-dist --clear
cd /tmp/qa2-do47-dist && python3 -m http.server 8951 --bind 127.0.0.1 &
python3 tests/qa/qa2-do-lai-47-lan2/probe_di_bo_shell.py      # đi bộ 4 tab   (+ --canary)
python3 tests/qa/qa2-do-lai-47-lan2/probe_hang_doi_nhan.py    # F31/32/33/34 + F43/F44  (+ --canary)
python3 tests/qa/qa2-do-lai-47-lan2/probe_f24_f45.py          # F24 + F45     (+ --canary)
```

Hai hằng `SITE` và `API_HOST` ở đầu mỗi file probe là cổng của lượt đo này; đổi
stack thì sửa chúng.

## 8. Câu không được bỏ

Bảng trên nói *một máy quét bấm được bao nhiêu nút và máy chủ trả gì*. Nó không
nói người thật hiểu sản phẩm, và nó không nói mã QR quét được. ADR-0006: repo
này vẫn chưa có bằng chứng hành vi nào.
