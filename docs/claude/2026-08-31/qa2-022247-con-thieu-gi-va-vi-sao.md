# qa2-022247 — 11 tính năng còn thiếu trên `main`, từng cái kèm lý do và bước chết

- **Đo trên**: `main` tại `19b4760` (không phải `43dc45a` — `main` đã đi thêm 6 commit)
- **Máy chủ**: stack dùng một lần dựng từ chính `19b4760` (`scripts/e2e_slice.sh --keep`)
  → `http://127.0.0.1:46229`, PostgreSQL riêng ở `44935`. Không đụng máy demo `:8099`
- **Bundle**: `expo export --platform web --clear` từ `19b4760`,
  `EXPO_PUBLIC_API_URL=http://127.0.0.1:46229`, phục vụ ở `127.0.0.1:8947`
- **Cửa vào**: Google → chọn Minh trong Team Đà Lạt. Khung 390×844
- **Kỹ năng đã gọi**: `exploratory-testing`
- **protocol_version**: v1 · **Ngày**: 2026-08-31

Đây là **kiểm kê hành vi**, không phải phán quyết PR. Không có verdict trong tài liệu này.

**KHÔNG dùng bundle ở `:8081`.** Bundle đó dựng từ `43dc45a` và trỏ vào
`http://localhost:8099` (đọc thẳng trong file `.js` phục vụ ở đó). Máy `:8099`
tụt sau `main`, nên đo ở đó là đo một sản phẩm khác.

---

## 0. Con số, và vì sao nó là **11** chứ không phải 15

| Mốc | BẤM-ĐƯỢC | Còn thiếu |
|---|---|---|
| `1161570` (#394, con số leader đang cầm) | 32 | 15 |
| `43dc45a` (#399, đo ở cửa Google) | 35 | 12 |
| **`19b4760` (lượt này)** | **36** | **11** |

Bốn hàng đã đổi nhãn kể từ con số 32, mỗi hàng có commit của nó:

| Hàng | Đổi ở đâu | Bằng chứng |
|---|---|---|
| F16 lịch trình AI | `c5c74d5` (#388) | `POST 200 /ai-turn` → thẻ 6 chặng |
| F36 album chuyến | `67b64be` (#379) | `[+] → Album chuyến đi` → 3 album |
| F37 thước phim | `67b64be` (#379) | `GET 200 …/reel`, trạng thái rỗng |
| **F38 widget ảnh** | **`f363639` (#365) — lượt này** | `[+] → Kỷ niệm nhóm → "Xem widget ảnh mới nhất của nhóm"` → `GET 200 /contexts/{id}/widget` |

F38 lượt trước tôi ghi KHÔNG-CÓ-ĐƯỜNG và **đó là đúng ở `43dc45a`**:
`git show 43dc45a:…/VoTab.tsx | grep -c onMoWidget` → `0`. Cái nút đến từ #365,
sau lúc tôi đo. Không phải tôi đọc sai; hàng thật sự vừa sống dậy.

11 hàng còn lại chia thành ba loại, và ba loại này cần ba cách xử lý khác hẳn nhau.

---

## 1. TẮC — có đường bấm, chết giữa chừng (4 hàng)

Bốn hàng này người dùng **bấm tới được**, màn **mở ra**, rồi máy chủ từ chối hoặc
màn hết đường đi.

| F## | Tên | Đường bấm | Chết ở đâu |
|---|---|---|---|
| F43 | Social Map | Khám phá → **Xem bản đồ của nhóm** | `GET 403 /contexts/1aa00000-…/map` |
| F44 | Group Heatmap | cùng một cú bấm | `GET 403 /contexts/1aa00000-…/heatmap` |
| F45 | Meet-in-the-middle | … → **Tìm điểm hẹn** → `GET 200 /areas` → chọn 2 khu → **Tìm chỗ gặp** | `POST 403 /contexts/1aa00000-…/meet` |
| F24 | Expense From Chat | Tin nhắn → gõ khoản chi → **Tách tiền** | `POST 200 …/expense-draft` **đọc đúng**, rồi hết nút |

### F43 · F44 · F45 là MỘT lỗi, và nó là **một prop thiếu**

Người dùng thấy: màn "Bản đồ nhóm" mở ra rồi in *"Bạn không còn trong nhóm này —
Bản đồ và lịch sử của một nhóm chỉ người trong nhóm xem được."* Câu đó **đúng về
mặt kỹ thuật và sai về mặt sự thật**: người dùng đang ở trong nhóm của họ, chỉ là
màn hỏi máy chủ về **một nhóm khác**.

Chuỗi nhân quả, ba mắt xích, đọc được bằng mắt:

```
apps/mobile/src/screens/kham-pha/places.ts:53
    export const CONTEXT_ID = "1aa00000-aaaa-4aaa-8aaa-0000a0000001";   // nhóm seed

apps/mobile/src/screens/kham-pha/ban-do-nhom.ts:320,324,328
    banDoUrl(base, contextId: string = CONTEXT_ID)      // ← tham số MẶC ĐỊNH
    nhietDoUrl(base, contextId: string = CONTEXT_ID)
    diemHenUrl(base, contextId: string = CONTEXT_ID)

apps/mobile/src/screens/kham-pha/KhamPha.tsx:197
    <BanDoNhom nguoi={nguoi} moDiemHenNgay={…} onQuayLai={…} />
                                       ↑ không truyền contextId
```

`KhamPha` **đang cầm** nhóm thật: nó nhận prop `nhom` và truyền xuống
`ChiTietDiaDiem` ở ngay dòng 210. Nó chỉ không truyền xuống `BanDoNhom` ở dòng
197. Vì `banDoUrl` có giá trị mặc định, chỗ thiếu đó **không phải lỗi biên dịch**
— nó im lặng rơi về nhóm seed. Tiêu chí gỡ chặn: `contextId={nhom?.id}` ở dòng
197, ba route hết 403.

**Hệ quả im lặng nghiêm trọng hơn ba con 403**, và nó vẫn nguyên: cùng hằng số đó
lái `GET /places?context_id=1aa00000-…` ở `places.ts:310`. Tôi bắt được nó ở mọi
bộ lọc trong lượt quét:

```
GET 200 /places?context_id=1aa00000-aaaa-4aaa-8aaa-0000a0000001&category=cafe
GET 200 /places?context_id=1aa00000-aaaa-4aaa-8aaa-0000a0000001&category=vui-choi
```

Nghĩa là **"AI MATCH 96%" đang chấm theo ngân sách và sở thích của một nhóm mà
người dùng không thuộc về** — và ở đường này máy chủ trả `200`, nên không có con
403 nào lộ ra. Ba hàng TẮC chỉ là chỗ cái ghim đó tình cờ nhìn thấy được.

### F24 — máy chủ đọc đúng, màn không có chỗ chốt

Gõ *"Tiền nướng tối qua 360k, mình trả trước nhé"* → bấm **Tách tiền**:

```
POST 200 /contexts/{id}/messages/{msg}/expense-draft
```

Trên màn:

```
Tiền nướng tối qua
360.000đ
Người trả: Minh
Người chia: Đức, Minh, Trang, Quân, Hải, Linh, Ngọc
Cần xem lại
Chưa ghi khoản chi nào. Đây mới là bản đọc, bạn còn phải chốt.
[Đóng]
```

Toàn bộ nút hiện trên thẻ: `Tách tiền` · **`Đóng`**. Không có đường nào sang form
khoản chi. Màn tự nói *"bạn còn phải chốt"* rồi không cho chỗ chốt. Tiêu chí gỡ
chặn: thẻ có nút mở `NhapKhoanChi` với bản đọc điền sẵn.

---

## 2. KHÔNG-CÓ-ĐƯỜNG — chưa có màn, hoặc có màn mà không nút nào dẫn tới (7 hàng)

Hai loại con, và trộn chúng lại là mất đúng cái phân biệt cần đọc:

### 2a. Backend đã xong, client chưa có màn nào (2 hàng)

Tôi gọi thẳng hai route bằng `curl` với header `X-Actor-Roles: member`:

| F## | Route | Máy chủ trả gì |
|---|---|---|
| F31 | `GET /contexts/{id}/preference-profile` | `200` · `{"has_profile":false,"reason":"no_behaviour","outing_count":3,"split_total_vnd":6785000}` |
| F32 | `GET /contexts/{id}/suggestion` | `200` · **lịch 3 chặng thật, `"source":"ai"`** — Nướng Ngói Trời Thông 18:30 → Lưng Chừng Cafe 20:30 → Chill Đêm 22:00, mỗi chặng kèm lý do |

Cả hai route **không có một literal nào trong `apps/mobile/src`** — chúng nằm
trong `.server-routes-uncalled.json` như nợ đã ghi nhận. Nghĩa là: phần khó đã
xong, F32 đang sinh ra một gợi ý chủ động có thật mà **không màn nào hỏi nó**.
Đây là hai hàng rẻ nhất trong 11 hàng: mỗi hàng cần một màn đọc, không cần backend.

F31 còn một tầng nữa: máy chủ tự khai `no_behaviour` vì nhóm có `checkin_count 0`.
Nên kể cả khi có màn, nó sẽ hiện trạng thái rỗng cho tới khi có người check-in
thật — xem mục 3.

### 2b. Có màn, có cả vỏ bọc API, mà không nút nào dẫn tới (3 hàng)

| F## | Màn | Mở được bằng | Vỏ bọc API | Số nơi gọi |
|---|---|---|---|---|
| F21 | `screens/nhan-mat/NhanMatTrenAnh.tsx` | chỉ `?man=nhan-mat` (`App.tsx:1572`) | `timKhuonMat` → `/contexts/{id}/photos/{id}/face-boxes` (`api.ts:2698`) | **0** |
| F22 | `screens/bill/MonCuaToi.tsx` | chỉ `?man=mon-cua-toi` (`App.tsx:1571`) | `nhanMonCuaToi` → `/bills/{id}/my-items` (`api.ts:2643`) | **0** |
| F23 | — | nằm trên màn F21 | — | — |

Và cái cửa `?man=` đó **cũng không nối vào máy chủ**. Tôi mở cả hai và đếm lời gọi:

```
?man=nhan-mat    → "Nhận mặt trên ảnh", 3 ô vuông bấm được   · lời gọi API: 0
?man=mon-cua-toi → "Món của tôi", 5 món, "Lưu món của tôi"   · lời gọi API: 0
```

Đọc `App.tsx:1429-1495` thì rõ vì sao: cả hai màn nhận **hằng số viết cứng**
(`MON_DEMO`, `O_DEMO` — ba hình chữ nhật vẽ sẵn trên `anh-nhom-dung-san.svg`) và
callback rỗng (`onLuu={() => {}}`, `onTim={() => {}}`). Tên nhóm in ra là *"Hội bạn
Bàn Cờ"* — không phải nhóm của người đang đăng nhập. Đây là **màn cho máy quét
chụp ảnh**, không phải tính năng đứng sau một cánh cửa.

F23 (Confidence Score) đo trên chính màn F21: không có chữ *tin cậy*, không có
`%` nào (`/tin cậy|độ chắc|confidence/i` → false, `/\d+\s*%/` → false). Màn còn
nói thẳng *"Máy chỉ khoanh các hình chữ nhật. Máy không biết ô nào là ai."* —
trung thực, và đúng là chưa có gì để đo.

### 2c. Chưa có gì cả — không màn, không route (2 hàng)

| F## | Tên | Lý do cụ thể |
|---|---|---|
| F30 | Group Memory | Không có bảng/route nào lưu *"Kiệt thích sushi"* theo từng người. Màn **có thu** sở thích — `vao-cua/CaNhanHoa.tsx` (#395) — nhưng `DangKy.tsx:114-118` chỉ gọi `ghiNhoSoThich(chon)` giữ trong bộ nhớ phiên, comment tự khai *"Held for the session and no longer"*. Hết phiên là mất. Và màn đó nằm trên **cửa số điện thoại**; vào bằng cửa Google thì không thấy nó lần nào |
| F47 | Automatic Place Detection | Từ chối có chủ ý. Không route GPS, không màn. Xem thêm mục 3 — kể cả khi viết xong cũng không đo được bằng bộ đồ nghề này |

---

## 3. KHÔNG-ĐO-ĐƯỢC — trạng thái thứ ba, và nó không nằm trong 11 hàng trên

Đây là chỗ dễ đọc nhầm nhất, nên nói rõ: **năm hàng dưới đây tôi đếm là
BẤM-ĐƯỢC** — đường bấm có thật, máy chủ trả `200`. Cái không đo được là **ruột**
của tính năng, và không phép đo nào trong repo này chạm tới được.

| F## | Đường bấm có thật | Cái KHÔNG đo được | Cần gì để đo |
|---|---|---|---|
| F37 | `GET 200 …/albums/{id}/reel` → *"Chưa dựng được thước phim"* | AI có dựng nổi thước phim từ ảnh thật không | Ảnh thật trong nhóm. Cả hai stack đều `count(*) posts where image_url is not null = 0` |
| F38 | `GET 200 /contexts/{id}/widget` → *"Nhóm chưa có ảnh nào"* | Widget với ảnh thật trông thế nào | Cùng lý do |
| F35 | Tường Kỷ niệm mở được, `/memories` `200` | Nửa ảnh của tường | Cùng lý do |
| F05 | Khối "Mã kết bạn của bạn" render được | Mã có **quét được bằng camera thật** không | Hai điện thoại thật |
| F29 | VietQR dựng đúng chuỗi EMVCo + CRC | Mã có **quét được bằng app ngân hàng thật** không | Một điện thoại + một app ngân hàng. 15 phút của leader |

Ba hàng đầu là **cùng một ô trống**: không stack nào có ảnh. Đổ ảnh thật vào là
sai luật (`CLAUDE.md`: không bao giờ đưa ảnh bill / dữ liệu thật vào repo hay
worktree), nên đây không phải việc "chưa ai làm" mà là việc **phải quyết định
cách làm**: một volume ảnh giả ngoài Git, hay chấp nhận ba hàng này mãi là
trạng thái rỗng.

Hai hàng phụ thuộc thời gian và thế giới thật, ghi cho đủ:

- **F32** nếu có màn thì vẫn cần *thời gian trôi qua* để chứng minh phần "chủ
  động" (18:00 thứ Sáu, 3 tuần chưa tụ tập). Lượt này máy chủ trả gợi ý **ngay khi
  được hỏi**, đó là "hỏi thì có", chưa phải "tự nhắc".
- **F47** cần GPS và người **di chuyển thật**. Không trình duyệt nào giả được
  chuyện đó thành bằng chứng.
- **F31** cần hành vi tích luỹ: máy chủ trả `no_behaviour` khi `checkin_count 0`.

---

## 4. Một điểm mù của cổng, tìm ra trong lúc đo

`scripts/check_server_routes_called.py` in ra *"66 có người gọi, 6 đang nợ"* và
xanh. Nhưng "người gọi" của nó là **bất kỳ literal nào trong `apps/mobile/src`** —
và `src/api.ts` viết literal cho **mọi** route nó bọc. Nên một route chỉ cần có
vỏ bọc là đã đủ xanh, dù không màn nào import cái vỏ đó.

Đo độ lớn (`tests/qa/qa2-con-thieu/vo_boc_khong_ai_goi.py`): **54 vỏ bọc trong
`api.ts`, 46 có màn gọi, 8 không ai gọi ngoài chính `api.ts`.**

```
docBill               /bills/{billId}                                    0 nơi gọi
docBangTin            /posts?limit=…                                     0
docBai                /posts/{postId}                                    0
docDanhSachBinhChon   /contexts/{id}/votes                               0
docBinhChon           /votes/{voteId}                                    0
dongBinhChon          /votes/{voteId}/close                              0
nhanMonCuaToi         /bills/{billId}/my-items                           0   ← F22
timKhuonMat           /contexts/{id}/photos/{id}/face-boxes              0   ← F21
```

Nên con số nợ thật là **6 (không có vỏ) + 8 (có vỏ, không màn) = 14 route người
dùng không chạm tới được**, không phải 6. Ba dòng `votes` đáng chú ý riêng: F17
tôi vẫn đếm BẤM-ĐƯỢC (thẻ bình chọn + "Mở bình chọn mới" có thật), nhưng **đọc
danh sách và đóng bình chọn thì không màn nào gọi** — hàng đó đúng một nửa.

Đây là **suggestion, không phải blocker**: cổng đang đo đúng cái nó khai (route
bị bỏ rơi hoàn toàn), chỉ là con số của nó không trả lời được câu "người dùng
chạm được bao nhiêu". Chủ sở hữu cổng quyết định có mở rộng hay không.

---

## 5. Phép đo của tôi hỏng hai lần trong lượt này — cả hai đều tạo hàng chết giả

Ghi lại vì cả hai đều đọc **y hệt** một lỗi sản phẩm:

**Lần 1 — bấm theo nhãn.** `click_label` dùng
`[aria-label="X"], button:has-text("X")`. Phần lớn control ở đây là
`div[role=button]` với nhãn chỉ tồn tại dưới dạng `innerText`, nên **không
selector nào khớp** → timeout. Lượt chạy đầu báo **10 control chết trên Khám phá**;
cả 10 đều sống. Sửa: gắn `data-qa2=<i>` vào từng node lúc kiểm kê rồi bấm theo
chỉ số.

**Lần 2 — trạng thái đọng lại.** Bấm bộ lọc "Đi chơi đêm" xong quay về tab thì
danh sách chỉ còn quán đêm, nên vòng lặp sau không tìm thấy *"Tiệm Nướng Xóm Lào"*
và ghi "không thấy control". Sửa: không thấy nhãn thì **đăng nhập lại từ đầu** rồi
thử lại đúng một lần, để chữ "không thấy" chỉ còn nghĩa "không thấy trên màn sạch".

Sau hai lần sửa: **27 control mở được thứ gì đó · 2 không bấm được**, và hai cái
không bấm được là **đúng**: `Tìm bằng AI` và `Gửi tin nhắn` đều
`aria-disabled=true` + `pointer-events:none` khi ô nhập rỗng.

Canary hai chiều (bắt buộc, nếu không cả tài liệu này phải vứt):

```
CANARY SẠCH            : button 4 · tab 4 · tablist 1 · innerText 276→713 ký tự
CANARY XẤU (chặn **/*.js): mọi vai trò = 0 · innerText 0 ký tự
```

Máy chủ đúng là `main`:

```
python3 scripts/check_demo_matches_main.py --url http://127.0.0.1:46229 --ref origin/main
→ Máy demo khớp origin/main: 77 route, không thiếu, không thừa.
scripts/e2e_slice.sh --keep → 7 pass / 0 fail
```

---

## 6. Bảng gộp — 11 hàng, một dòng một hàng

| F## | Tên | Loại | Bước chết / lý do | Gỡ bằng cách nào |
|---|---|---|---|---|
| F43 | Social Map | TẮC | `GET 403 …1aa00000…/map` | `contextId={nhom?.id}` ở `KhamPha.tsx:197` |
| F44 | Group Heatmap | TẮC | `GET 403 …1aa00000…/heatmap` | cùng dòng |
| F45 | Meet-in-the-middle | TẮC | `POST 403 …1aa00000…/meet` sau khi chọn 2 khu | cùng dòng |
| F24 | Expense From Chat | TẮC | `expense-draft 200`, thẻ chỉ có nút "Đóng" | thẻ mở `NhapKhoanChi` với bản đọc |
| F31 | Preference Profile | KHÔNG-CÓ-ĐƯỜNG (backend xong) | route `200`, 0 literal trong client | một màn đọc |
| F32 | Proactive Suggestion | KHÔNG-CÓ-ĐƯỜNG (backend xong) | route `200` trả lịch AI thật, 0 literal trong client | một màn đọc + cơ chế nhắc |
| F21 | AI Person Recognition | KHÔNG-CÓ-ĐƯỜNG (màn là vỏ) | chỉ `?man=`, 0 lời gọi API, hằng số cứng | nút trong luồng bill + nối `timKhuonMat` |
| F22 | Visual Food Participation | KHÔNG-CÓ-ĐƯỜNG (màn là vỏ) | chỉ `?man=`, 0 lời gọi API, hằng số cứng | nút trong luồng bill + nối `nhanMonCuaToi` |
| F23 | Confidence Score | KHÔNG-CÓ-ĐƯỜNG | màn F21 không in số nào | máy chủ trả độ chắc, màn in kèm |
| F30 | Group Memory | KHÔNG-CÓ-ĐƯỜNG | sở thích thu ở `CaNhanHoa` bị bỏ hết phiên; không route lưu | route lưu sở thích theo người |
| F47 | Auto Place Detection | KHÔNG-CÓ-ĐƯỜNG + KHÔNG-ĐO-ĐƯỢC | không có gì; và cần GPS + di chuyển thật | quyết định có làm không |

---

## 7. Ô chưa quét (đo được, chỉ là lượt này chưa đo)

- **47 hàng ở cửa số điện thoại.** Cửa đó vừa mọc thêm màn Cá nhân hoá (#395),
  chưa ai đi đủ 47 hàng qua nó.
- **Cửa "Bỏ qua"** (`nguoi = null`) — chưa đo hàng nào, lần nào.
- **F41 gõ bình luận mới · F12 câu tìm tiếng Việt mới · F17 đóng một bình chọn.**
- **Tầng 3 trở đi**: lượt quét này sâu 2 tầng từ shell. Một tính năng nấp ở tầng 3
  sẽ không hiện ra trong bản đồ này — với 11 hàng trên tôi đã đi thủ công thêm,
  nhưng tuyên bố "không có đường" chỉ chắc tới đúng độ sâu đã quét.
- **Khung 320 / 1440 và chủ đề tối** — lượt này chỉ 390×844 sáng.

## 8. Chạy lại thế nào

```bash
scripts/e2e_slice.sh --keep                       # in ra API + DSN dùng một lần
python3 scripts/reset_demo_group.py --dsn 'postgresql://…' --yes   # --dsn, KHÔNG phải env
MOBILE_SEED_API_BASE_URL=<api> MOBILE_DATABASE_URL=<dsn+psycopg> python3 scripts/seed_demo_data.py
EXPO_PUBLIC_API_URL=<api> npx expo export --platform web --output-dir /tmp/qa2-cth-dist --clear
cd /tmp/qa2-cth-dist && python3 -m http.server 8947 --bind 127.0.0.1 &
python3 tests/qa/qa2-con-thieu/probe_ban_do_2_tang.py            # bản đồ 2 tầng (+ --canary)
python3 tests/qa/qa2-con-thieu/probe_hang_tac.py                 # F43/F44/F45/F24
python3 tests/qa/qa2-con-thieu/probe_khong_co_duong.py           # F38/F21/F22/F23
python3 tests/qa/qa2-con-thieu/vo_boc_khong_ai_goi.py            # 8 vỏ bọc không màn nào gọi
```

Hai hằng `SITE` và `API` ở đầu mỗi file probe là cổng của lượt đo này; đổi stack
thì sửa chúng.

## 9. Câu không được bỏ

Bảng trên nói *một máy quét bấm được bao nhiêu nút và máy chủ trả gì*. Nó không
nói người thật hiểu sản phẩm, và nó không nói mã QR quét được. ADR-0006: repo này
vẫn chưa có bằng chứng hành vi nào.
