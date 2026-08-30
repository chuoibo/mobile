# qa2-042742 — Đo lại 47 tính năng trên `main` `880cd6d`: **40/47**, còn thiếu 7

- **Đo trên**: `main` tại `880cd6d` (mốc trước là `5220ebd` ở #414, `main` đã đi thêm 6 commit)
- **Cây chạy phép đo**: nhánh `qa2/dong-no-het-han-routes-uncalled` tại `1dffe30`.
  `git diff 880cd6d..1dffe30` chỉ chạm `.server-routes-uncalled.json` và một file
  dưới `tests/qa/` — **không byte nào của `apps/mobile/` hay `services/api/`**.
  Nên máy chủ và bundle dưới đây đúng là `880cd6d`.
- **Máy chủ**: stack dùng một lần từ `scripts/e2e_slice.sh --keep` →
  PostgreSQL riêng ở `44955`, uvicorn ở `http://127.0.0.1:45812`.
  Không đụng máy demo `:8099`, không đụng `5432` dùng chung.
- **Bundle**: `expo export --platform web --clear`, `EXPO_PUBLIC_API_URL=http://127.0.0.1:45812`,
  phục vụ ở `127.0.0.1:8953`
- **Cửa vào**: **Google → Minh**, khung 390×844, chủ đề sáng
- **Kỹ năng đã gọi**: `exploratory-testing`
- **protocol_version**: v1 · **Ngày**: 2026-08-31

Đây là **kiểm kê hành vi**, không phải phán quyết PR. Không có verdict ở đây.

---

## 0. Con số

| Mốc | BẤM-ĐƯỢC | Còn thiếu |
|---|---|---|
| `43dc45a` (#399, cửa Google) | 35 | 12 |
| `19b4760` (#403) | 36 | 11 |
| `5220ebd` (#414) | 39 | 8 |
| **`880cd6d` (lượt này)** | **40** | **7** |

Một hàng đổi nhãn. Không hàng nào tụt lại.

| Hàng | Trước | Giờ | Vì commit nào |
|---|---|---|---|
| **F22** Visual Food Participation | KHÔNG-CÓ-ĐƯỜNG | **BẤM-ĐƯỢC** | `880cd6d` (#415) |

**Cửa vào của F22, ghi rõ vì lượt trước không có cửa nào để ghi:**

```
Khám phá → [Tạo mới] → [Tạo khoản chi] → chụp bill → [Chọn ảnh bill] (ro.jpg)
  → POST 200 /receipts/scan          ← Gemini đọc 5 món, 235.000đ
  → [Tiếp tục] → goi-y
  → [Thêm Minh vào nhóm] [Thêm Trang vào nhóm]
  → POST 201 /bills                  ← cửa F22 mở ra ở đây, không sớm hơn
  → [Món của tôi] → bỏ tích "Cơm tấm sườn bì chả" → [Lưu món của tôi]
  → POST 200 /bills/{id}/my-items    ← F22
```

Và số tiền về đúng chỗ, đọc trên chính màn `goi-y` sau khi quay lại:

```
Minh 85.000đ · Trang 150.000đ            85.000 + 150.000 = 235.000  ✔ luật tiền 2
```

Ô "Cơm tấm sườn bì chả" giờ chỉ còn ✓ dưới cột T, không còn dưới cột M — nghĩa là
lời khai của một người đã đi tới máy chủ và quay về đúng một dòng, không chạm dòng
của người khác.

Chạy hai lần, hai `bill_id` khác nhau (`b15bebe2…` rồi `8e4a9cf7…`), cùng kết quả.

### Một cái bẫy trong chính cửa này, ghi để lượt sau không đọc nhầm

`POST /bills` **không** bắn khi vừa tới `goi-y`. Chưa chọn ai thì màn nói
*"Chưa lưu được. Ô đã tích chỉ ở máy này."* và nút F22 xám kèm câu
*"Món của tôi, chưa mở được: Chưa lưu được bill, nên chưa nhận món riêng được."*

Lượt chạy đầu của tôi dừng đúng ở đó và **F22 trông y hệt một hàng chết**. Nó
không chết; nó có hai khoá, và cả hai đều ghi ở `bill/mon-cua-toi.ts`
(`khoaMonCuaToi`): phải có bill, và **Minh phải nằm trên bill**. Một phép đo bấm
"Món của tôi" ngay khi tới `goi-y` sẽ ghi F22 là KHÔNG-CÓ-ĐƯỜNG, và sai.

---

## 1. Bảy hàng còn thiếu

| F## | Tên | Loại | Bước chết / lý do |
|---|---|---|---|
| F43 | Social Map | TẮC | `GET 403 …1aa00000…/map` |
| F44 | Group Heatmap | TẮC | `GET 403 …1aa00000…/heatmap` |
| F45 | Meet-in-the-middle | TẮC | chọn 2 khu → `POST 403 …1aa00000…/meet` |
| F21 | AI Person Recognition | KHÔNG-CÓ-ĐƯỜNG | chỉ `?man=nhan-mat` (`App.tsx:1661`), 0 lời gọi API |
| F23 | Confidence Score | KHÔNG-CÓ-ĐƯỜNG | màn nhận diện in *"Đã nhận diện 5 món"* và không con số tin cậy nào |
| F30 | Group Memory | KHÔNG-CÓ-ĐƯỜNG | sở thích chỉ giữ trong phiên, không route lưu |
| F47 | Auto Place Detection | KHÔNG-CÓ-ĐƯỜNG | từ chối có chủ ý; cần GPS + di chuyển thật |

F23 lượt này là **đo sống**, không phải nhãn kế thừa: màn kết quả nhận diện được
mở bằng ảnh thật đi qua Gemini, và chữ trên màn không có con số tin cậy nào.

---

## 2. Ba hàng TẮC: cùng một lỗi client, và lượt này đo **bốn chiều** trên chính stack này

`KhamPha.tsx:197` vẫn không truyền `contextId` cho `<BanDoNhom>`, và
`ban-do-nhom.ts:320,324,328` vẫn có tham số mặc định `contextId: string = CONTEXT_ID`,
nên chỗ thiếu đó **không phải lỗi biên dịch** — nó im lặng rơi về nhóm seed.

Phép đo hai cột ở #414 chỉ trả lời được "máy chủ có khoẻ không". Cột thứ ba mới
là cái biến *tôi đoán* thành *tôi biết*, nên lượt này đo đủ:

| Route | [A] Minh × nhóm THẬT `50586b69…` | [B] Minh × hằng số cứng `1aa00000…` | [C] **người lạ** × nhóm THẬT |
|---|---|---|---|
| `GET /map` | **200** · `trending` có dữ liệu | **403** `is_group_member` | **403** `is_group_member` |
| `GET /heatmap` | **200** · `areas: []` | **403** cùng thân | **403** cùng thân |
| `POST /meet` | **200** · `origins` + `candidates` | **403** cùng thân | **403** cùng thân |

- **[A]** loại trừ "máy chủ hỏng" và "actor bị cấm".
- **[C]** là **đối chứng dương**: quyền thật sự chặn người ngoài, chứ không phải
  lúc nào cũng trả 200 cho ai đi qua. Không có [C] thì [A] không chứng minh gì.
- **[B]** là cái đang xảy ra trong sản phẩm.

`/heatmap` với nhóm thật là **200 với `areas: []`**, không phải 403. Nên giả thuyết
"nhóm demo chưa có dữ liệu" vẫn sai, và cách sửa vẫn là **sửa client**, không phải seed.

**Một phép đo của tôi hỏng ở đây, và nó suýt thành kết luận ngược.** Lần curl đầu
tôi quên `X-Actor-Roles: member`, và **cả ba cột đều 403** — trông y hệt "máy chủ
chặn tất cả". Nhưng thân trả về là `role_not_permitted`, không phải `is_group_member`:
đỏ vì lý do khác hẳn. Một đối chứng đỏ **sai lý do** không chứng minh gì cả, và nếu
tôi chỉ đọc mã 403 thì báo cáo này đã ghi ngược. Đọc `detail`, đừng đọc mã.

### Hệ quả im lặng vẫn nguyên, và vẫn nghiêm trọng hơn ba con 403

```
GET 200 /places?context_id=1aa00000-aaaa-4aaa-8aaa-0000a0000001
```

Bắt được ngay khi mở tab Khám phá, ở cả bốn lượt chạy. "AI MATCH 96%" đang chấm
theo ngân sách và sở thích của một nhóm Minh **không thuộc về**, và máy chủ trả
`200` nên không cổng nào đỏ. Ba con 403 ít nhất còn hiện ra một câu tiếng Việt cho
người dùng; cái này không hiện gì.

---

## 3. Năm hàng KHÔNG-ĐO-ĐƯỢC — tách riêng, và **vẫn nằm trong 40**

Nói rõ vì đây là chỗ dễ đọc nhầm nhất: năm hàng này tôi **đếm là BẤM-ĐƯỢC** (đường
bấm có thật, máy chủ trả `200`). Cái không đo được là **ruột** của tính năng.

| F## | Đường bấm có thật | Cái KHÔNG đo được | Cần gì để đo |
|---|---|---|---|
| F35 | Tường Kỷ niệm mở được, `/memories` `200` | Nửa ảnh của tường | Ảnh thật trong nhóm |
| F37 | `GET 200 …/reel` → *"Chưa dựng được thước phim"* | AI có dựng nổi thước phim không | Cùng lý do |
| F38 | `GET 200 …/widget` → *"Nhóm chưa có ảnh nào"* | Widget với ảnh thật trông thế nào | Cùng lý do |
| F05 | Khối "Mã kết bạn của bạn" render được | Mã có **quét được bằng camera thật** không | Hai điện thoại thật |
| F29 | VietQR dựng đúng chuỗi EMVCo + CRC | Mã có **quét được bằng app ngân hàng thật** không | Một điện thoại + một app ngân hàng |

Ba hàng đầu là **cùng một ô trống**: không stack nào có ảnh trong nhóm. Đổ ảnh
thật vào là sai luật `CLAUDE.md`, nên đây là việc **phải quyết định cách làm**,
không phải việc "chưa ai làm".

Vậy con số đầy đủ là: **40 BẤM-ĐƯỢC, trong đó 5 hàng chỉ chứng minh được vỏ · 3 TẮC · 4 KHÔNG-CÓ-ĐƯỜNG.**

---

## 4. Một lỗi mới bắt được trong lúc đo (không thuộc 47 hàng)

Trên màn `goi-y`, khối *"Trước bữa này, nhóm còn nợ nhau"* in **UUID thô** thay
vì tên người:

```
e3a44e25-4547-508a-8f4d-9b2495c3325f trả Minh 505.094đ
Trang trả Minh 374.262đ                                  ← dòng này đúng
cdadf49b-b6a8-5631-8b9d-aee6a7d532de trả Minh 197.215đ
```

Cùng một khối, cùng một lúc: dòng có tên và dòng có UUID đứng cạnh nhau. Đã báo
sang lane frontend bằng `bug-to`. Không tính vào bảng 47 hàng vì nó không làm hàng
nào tắc — nhưng nó là thứ người dùng thật sẽ thấy đầu tiên.

---

## 5. Canary hai chiều — đọc trước khi tin bất kỳ số nào ở trên

Bốn probe, mỗi cái chạy hai lần: sạch, rồi chặn `**/*.js`.

```
CANARY SẠCH  (probe_di_bo_shell)  : button 8 · tab 4 · tablist 1 · radio 5 · input 1
                                    · innerText 713 ký tự · 12 lời gọi API
CANARY XẤU   (--canary)           : mọi vai trò = 0 · innerText 0 ký tự · 0 lời gọi

CANARY SẠCH  (probe_f22_mon_cua_toi): 5 món tick được · POST 200 /bills/{id}/my-items
CANARY XẤU   (--canary)             : 0 bước · 0 lời gọi API · dừng ở cửa Google
```

Máy chủ đúng là `main`:

```
python3 scripts/check_demo_matches_main.py --url http://127.0.0.1:45812 --ref origin/main
→ Máy demo khớp origin/main: 77 route, không thiếu, không thừa.
scripts/e2e_slice.sh --keep → 7 pass / 0 fail
```

Và `GEMINI_API_KEY` **có** trong env của tiến trình uvicorn — đây là cái bẫy đã ăn
lượt trước (#414 mục 3), nên lượt này kiểm trước khi đo:

```
tr '\0' '\n' < /proc/1731366/environ | grep -c '^GEMINI_API_KEY='  → 1
```

Nếu số đó là `0` thì mọi hàng AI (F08 F11 F16 F18 F24 F26 F32 F33) sẽ ra
"unavailable", và chữ đó đọc y hệt "chưa làm".

---

## 6. Ô chưa quét (đo được, chỉ là lượt này chưa đo)

- **Ba mươi lăm hàng không đổi** lượt này mang **nhãn kế thừa** từ #414/#403, chỉ
  được xác nhận tới độ sâu 2 tầng bằng đi bộ 4 tab. Không đi lại từng bước.
- **47 hàng ở cửa số điện thoại** và cửa **"Bỏ qua"** (`nguoi = null`) — chưa ai đi
  đủ 47 hàng qua hai cửa đó, lần nào.
- **Khung 320 / 1440 và chủ đề tối** — lượt này chỉ 390×844 sáng.
- **F22 ở nhánh "bỏ tích hết rồi Lưu"** — tôi chỉ bỏ tích một món. Câu
  *"Danh sách gửi lên thay hết món bạn nhận trước đó"* nói đây là ca đáng đo, và
  tôi chưa đo.

## 7. Chạy lại thế nào

```bash
scripts/e2e_slice.sh --keep                       # in ra API + DSN ngay ĐẦU output
# BẮT BUỘC, xem mục 5 — nếu không, mọi hàng AI ra "unavailable":
cd services/api && set -a && . /home/lakiet/mobile/.env && set +a
MOBILE_DATABASE_URL='<dsn>' python3 -m uvicorn app.api.main:app --host 127.0.0.1 --port <cổng>
python3 scripts/reset_demo_group.py --dsn '<dsn khong co +psycopg>' --yes
MOBILE_SEED_API_BASE_URL=<api> MOBILE_DATABASE_URL='<dsn>' python3 scripts/seed_demo_data.py
cd apps/mobile && EXPO_PUBLIC_API_URL=<api> npx expo export --platform web \
  --output-dir /tmp/qa2-do47-lan3-dist --clear
cd /tmp/qa2-do47-lan3-dist && python3 -m http.server 8953 --bind 127.0.0.1 &
python3 tests/qa/rd-qa-37/tao-anh-bill.py /tmp/qa2-bill-lan3        # ảnh bill tổng hợp
python3 tests/qa/qa2-do-lai-47-lan3/probe_di_bo_shell.py            # đi bộ 4 tab  (+ --canary)
python3 tests/qa/qa2-do-lai-47-lan3/probe_hang_doi_nhan.py          # F31-34 + F43/F44 (+ --canary)
python3 tests/qa/qa2-do-lai-47-lan3/probe_f24_f45.py                # F24 + F45    (+ --canary)
python3 tests/qa/qa2-do-lai-47-lan3/probe_f22_mon_cua_toi.py        # F22          (+ --canary, --kham-pha)
```

Hai hằng `SITE` và `API_HOST` ở đầu mỗi probe là cổng của lượt đo này; đổi stack
thì sửa chúng. `probe_f22_mon_cua_toi.py --kham-pha` in bảng control ở từng bước
thay vì khẳng định — đó là cách bốn cái nhãn trong mục 0 được tìm ra.

## 8. `main` nhích trong lúc tôi đang đo — con số này neo vào `880cd6d`, không vào "hiện tại"

Lúc bắt đầu, `origin/main` là `880cd6d`. Lúc commit, nó đã là `723abc8`:

```
723abc8  FAIL cho PR 397 (qa-tt-0051)              (#418)   ← tài liệu QA
8312042  actorId thành bắt buộc ở tầng kiểu        (#397)   ← chạm apps/mobile/src
56e0f36  Bốn dòng nợ đã trả từ #382                (#417)   ← PR của chính tôi
```

Tôi **không** đo lại trên `723abc8` — stack và bundle đã dựng từ `880cd6d`, và đo
một nửa trên nền này một nửa trên nền kia là cách tạo ra một con số không thuộc về
cây nào. Nên bảng trên đọc đúng là *"47 hàng tại `880cd6d`"*.

Cái tôi **có** kiểm, để nói được con số còn dùng được hay không:

```
git diff 880cd6d..723abc8 -- apps/mobile/src services/api/app
→ 6 file, tất cả là đường đi của actorId (#397). Không file nào là màn của một
  hàng trong bảng.

git show 723abc8:apps/mobile/src/screens/kham-pha/KhamPha.tsx | grep -A3 "<BanDoNhom"
→ vẫn không có contextId                          ← F43/F44/F45 vẫn TẮC
git show 723abc8:apps/mobile/src/screens/kham-pha/ban-do-nhom.ts | grep "Url(base"
→ vẫn `contextId: string = CONTEXT_ID`            ← vẫn không phải lỗi biên dịch
```

Nên **40/47 nhiều khả năng vẫn đúng ở `723abc8`**, và tôi ghi "nhiều khả năng"
chứ không ghi "đúng": #397 sửa 185 dòng trong `api.ts`, và tôi chưa bấm một nút
nào trên cây đó. Đây là hàng chờ, không phải kết luận.

## 9. Câu không được bỏ

Bảng trên nói *một máy quét bấm được bao nhiêu nút và máy chủ trả gì*. Nó không
nói người thật hiểu sản phẩm, và nó không nói mã QR quét được. ADR-0006: repo này
vẫn chưa có bằng chứng hành vi nào.
