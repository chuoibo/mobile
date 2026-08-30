# PASS — PR #278 (rd-fe-33: thả tim và bình luận trên tường kỷ niệm)

**Lý do, trước mọi chi tiết:** tôi tái lập được **từng con số** PR khai, và bảng
đột biến của tôi — viết bằng **hình dạng khác** với bảng của tác giả — cắn đúng
chỗ ở 8/9 hàng. Ba lỗi hạ tầng PR nói đã sửa đều **tái lập được ở bản trước**,
kể cả cái khó nhất: `clickLabel` bấm vào hư không rồi trả về bình thường. Cổng
`client-routes` đỏ là **đỏ đúng và đỏ trung thực** (exit 1 với PR, exit 0 khi
trả `api.ts` về bản main) — nó chặn vì bốn route của devops chưa tồn tại, không
vì khiếm khuyết trong PR này.

Một chỗ mù, **không chặn merge**: lời khai *"số đếm là số máy chủ trả về, không
cộng trừ tại chỗ"* **không được cổng nào đo**. Chi tiết ở F1.

```
protocol_version  v1
verdict           PASS  (điều kiện merge: SAU PR route của devops)
đo tại            63b37142c18b9c608993ec9ae2cd3389589bd9cd   (head #278)
sha này           là NHÁNH CHƯA MERGE, cắt từ main@75de149
cây gộp           c9b6ef8 = origin/main@f13f870 ⊕ 63b3714 — gộp SẠCH, 0 xung đột
blocker còn mở    không có
```

---

## 1. Cây gộp, không chỉ nhánh

`git merge pr278-check` vào `origin/main` hiện tại: sạch. Và quan trọng hơn —

```
git diff --stat origin/main HEAD -- '*.py'   ->  RỖNG
```

PR không đụng một dòng Python nào, nên kết quả tầng backend của main chuyển
nguyên vẹn sang cây gộp. Đo trên cây gộp:

```
python3 -m pytest services/api/tests tests -q
1844 passed, 366 skipped, 4736 subtests passed in 159.57s
```

`npm test` tại đúng head #278 (bước đầu là `expo export`, tức bundle thật):

```
# tests 680   # pass 680   # fail 0   # skipped 0
```

Khớp con số PR khai (674 → 680).

---

## 2. Bảng đột biến của tác giả — tôi chạy lại, không đọc lại

`node tools/dot-bien-tim.mjs`, cây sạch tại 63b3714:

```
nền sạch  6 pass / 0 fail
#1 phá  5 pass / 1 fail  ĐỎ    #5 phá  5 pass / 1 fail  ĐỎ
#2 phá  5 pass / 1 fail  ĐỎ    #6 GIỮ  6 pass / 0 fail  XANH
#3 phá  5 pass / 1 fail  ĐỎ    #7 GIỮ  6 pass / 0 fail  XANH
#4 phá  5 pass / 1 fail  ĐỎ    #8 GIỮ  6 pass / 0 fail  XANH
TẤT CẢ ĐÚNG KỲ VỌNG
```

8/8. Và harness của họ tự gác được ba thứ repo này đã trả giá: neo phải khớp
**đúng một chỗ**, `git diff` phải **khác rỗng** sau khi ghi, và `doc()` chỉ đọc
dòng tổng kết chứ không grep cả output.

---

## 3. Bảng đột biến ĐỘC LẬP — cùng vi phạm, hình dạng khác

Bảng của tác giả chứng minh cổng đỏ **cho những hình dạng tác giả nghĩ ra**.
Theo luật canary của Lead, hình dạng chính là thứ đang được chứng minh. Nên tôi
viết lại **cùng những vi phạm đó** bằng cách khác:
`tests/qa/qa-tt-0020/qa-dot-bien-doc-lap.mjs`.

| # | loại | vi phạm | hình dạng của TÔI | kết quả |
|---|---|---|---|---|
| A1 | phá | tim vẽ khi máy chủ chưa giữ được | `coTuongTac` dùng `!== null` (undefined !== null → true) | 5/1 **ĐỎ** đúng |
| A2 | phá | tim vẽ khi máy chủ chưa giữ được | điều kiện đổi sang trường LUÔN có: `{kyNiem.id ? (` | 5/1 **ĐỎ** đúng |
| B1 | phá | 204 không đọc là thành công | nhánh còn nguyên, lệch mã: `204` → `205` | 5/1 **ĐỎ** đúng |
| B2 | phá | 204 không đọc là thành công | nhánh còn nguyên nhưng vẫn `await response.json()` | 5/1 **ĐỎ** đúng |
| C1 | phá | "số đếm là số máy chủ trả về" | cộng trừ tại chỗ ±1, không đọc lại tường | 6/0 **XANH — CHỖ MÙ** |
| D1 | phá | `clickLabel` phải cuộn trước khi đo | gỡ `scrollIntoView`, GIỮ phép chặn | 5/1 **ĐỎ** đúng |
| D2 | phá | `clickLabel` không được bấm vào hư không | phục nguyên bản TRƯỚC PR | 5/1 **ĐỎ** đúng |
| G1 | **GIỮ** | — | đổi TÊN biến `soTim` → `demTim` | 6/0 **XANH** đúng |
| G2 | **GIỮ** | — | đổi HẰNG SỐ phụ: viewport 390x844 → 414x896 | 6/0 **XANH** đúng |

A1/A2 và B1/B2 là điểm đáng kể nhất: hàng #1 và #2 của tác giả **xoá** thứ cần
xoá, hình dạng dễ đọc nhất. Của tôi **giữ nguyên dòng** và chỉ làm nó sai —
kiểu lỗi người ta thật sự viết ra. Cổng vẫn cắn.

G1/G2 là hai hàng GIỮ mà bảng tác giả không có: một đổi tên, một đổi hằng số
phụ. Cả hai xanh, nên bảng phân biệt được "đo tính chất" với "để ý ai đụng file".

---

## 4. F1 — chỗ mù, và tôi đã loại trừ khả năng đột biến của mình hụt

**PR khai:** *"Sau khi thả tim hay gửi bình luận, tường đọc lại và lấy số đó.
Không cộng trừ tại chỗ."*

C1 thay đúng chỗ đó bằng bản tối ưu lạc quan — cộng 1 tại chỗ, bỏ `onDoiTuong()`
— và bộ test **vẫn xanh 6/0**.

Một chữ XANH ở đây có hai cách đọc ngược nhau: (a) cổng không phân biệt được, hay
(b) đột biến của tôi chưa từng chạy. Repo này đã bị (b) lừa nhiều lần, nên tôi
chạy đối chứng cực trị (`qa-doi-chung-c1.mjs`) — **cùng một đột biến, chỉ đổi
hằng số**:

```
[C1]    cộng/trừ tại chỗ ±1  ->  6 pass / 0 fail  XANH
[C1-x7] cộng/trừ tại chỗ ±7  ->  4 pass / 2 fail  ĐỎ
[C1-x0] cộng/trừ tại chỗ ±0  ->  4 pass / 2 fail  ĐỎ
```

±7 và ±0 đỏ, nên nhánh cộng tay **chạy thật và render thật**. Chữ XANH ở ±1 là
chỗ mù thật.

**Nguyên nhân:** fixture làm hai nguồn số trùng nhau. Ảnh có 2 tim, máy chủ trả
3 sau khi POST — mà `2 + 1` cũng là 3. Ảnh có 1 tim, DELETE trả 0 — mà `1 - 1`
cũng là 0. Bộ test bắt được "số sai" và "số đứng yên", chỉ không bắt được "số
đúng đến từ nguồn sai".

**Phân loại:** *suggestion*, không phải blocker. Không thuộc 5 loại blocker của
charter: không sai tiền, không rò rỉ, không phá tính hợp lệ thí nghiệm. Hôm nay
code **đang đúng**; cái thiếu là cọc giữ cho nó đúng.

**Tiêu chí gỡ:** cho stub trả một con số mà phép cộng tại chỗ không đoán được —
ví dụ POST thả tim đồng thời thêm một người lạ, nên 2 → **4** chứ không phải 3.
Lúc đó `2 + 1 = 3 ≠ 4` và C1 chuyển đỏ. Sửa trong stub, không đụng sản phẩm.

---

## 5. Ba lỗi hạ tầng: tái lập ở bản TRƯỚC, xanh ở bản SAU

Lời khai "đã sửa X" chỉ có giá khi bản trước thật sự hỏng ở X.

**(1) `call()` ném `SyntaxError` thô trên 204.** B1 và B2 tái lập bằng hai hình
dạng khác nhau, cả hai đỏ. Không route nào khác trong bộ này trả 204, nên hai
hàng đó đỏ đúng một ca — đúng như PR mô tả.

**(2) `clickLabel` bấm vào hư không.** Đây là cái đáng giá nhất, và tôi chụp
được **nguyên văn hai kiểu đỏ khác nhau**:

```
D2 — clickLabel BẢN TRƯỚC PR (không cuộn, không chặn):
    error: 'timed out waiting for câu vừa gửi hiện ra'

D1 — gỡ scrollIntoView nhưng GIỮ phép chặn:
    error: 'element with aria-label "Gửi bình luận" is outside the viewport
            even after scrolling (centre 68,859); a click there hits nothing'
```

`y = 859` trên màn cao `844`. Nút thật sự nằm dưới mép **15 pixel**, và con số
đó khớp khoảng `837-881` PR đo được. Hai dòng đỏ trên là toàn bộ lập luận của
bản vá: bản cũ đỏ ở chỗ **đổ lỗi cho sản phẩm** ("câu vừa gửi không hiện ra"),
bản mới đỏ ở chỗ **chỉ đúng vào công cụ**. Cùng một lỗi, một bên tốn nửa buổi
đi tìm trong `TimVaBinhLuan.tsx`.

**(3) `quet-tab-url.mjs` chưa từng quét màn bình luận.** Đọc thẳng từ diff: màn
`ky-niem-binh-luan` là mục **mới** trong `MAN_TUONG_TAC`. Ô nhập, nút gửi và câu
của người khác chỉ tồn tại sau cú bấm, nên con số 0 cũ là số của một bề mặt chưa
từng được dựng.

---

## 6. Máy quét URL — canary của tôi, không phải canary của họ

`PUPPETEER_EXECUTABLE_PATH` ghim sang chromium của Playwright, viewport 390x844:

```
canary xau         findings=5 exit=2   (cần > 0)   OK
canary sach        findings=0 exit=0   (cần = 0)   OK
canary nang sach   findings=0 exit=0   (cần = 0)   OK
canary nang        findings=3 exit=2   cham day trang=co   OK
...
ky-niem            findings=0 exit=0  (đã render: els=280 chars=827, needle OK)
ky-niem-binh-luan  findings=0 exit=0  (đã render: els=288 chars=865, needle OK)
canary nang 908 els vs man nang nhat kham-pha-mo-rong 860 els
tong findings tren cac man: 0
```

Khớp từng con số PR khai. Ba điều tôi kiểm riêng vì luật canary mới của Lead:

- **Canary nặng có bao phủ hình dạng nặng nhất không?** 908 els > 860 els, và
  phép so đó **được `throw`**, không phải chỉ in ra (`quet-tab-url.mjs:637`).
  Đây đúng là hình dạng Lead đòi sau #269 — bảng không được thừa hưởng kết luận
  đo trên trang nhỏ hơn chính nó.
- **Canary có phân biệt "sạch" với "máy đo chết" không?** Có, cả bốn: xấu phải
  đỏ, sạch phải xanh, nặng phải chạm đáy, nặng-sạch phải xanh để chứng minh
  phần lót không tự đẻ finding.
- **Màn mới có render thật không?** `els=288`, needle "Quang Huy" = true. Một số
  0 trên trang trắng đọc y hệt một số 0 trên trang sạch.

`ca-nhan`/`ban-be`/`dia-diem` ra `exit=2` nhưng `findings=0`: bốn finding
`text-occlusion` bị bộ lọc `to-cha`/`cuon-khuat` của #255 loại, mỗi cái kèm
`5/5 điểm mẫu có chính chữ ở trên cùng`. Không phải PR này gây ra, và tôi không
mở lại chuyện #255 ở đây.

---

## 7. Cổng chặn merge là cổng trung thực

```
python3 scripts/check_api_contract.py                        -> MÃ THOÁT 1
  4 chỗ lệch hợp đồng  (reactions ×2, comments ×2)
cùng lệnh, api.ts trả về bản main                            -> MÃ THOÁT 0
  "Client và máy chủ khớp hợp đồng."
```

Tôi đo **mã thoát thật**, không đọc `rc` của `tail` trong đường ống — lần đo
đầu của tôi in ra `rc=0` đúng khuôn "cổng in ra bằng chứng mình đang mù", và đó
là mã của `tail`.

Devops đã có code route trong worktree
(`devops/rd-do-22-tim-va-binh-luan-ky-niem`, HEAD `2308975`) nhưng **chưa đẩy
nhánh nào lên remote**. Nên trạng thái hôm nay là đúng: #278 xanh mọi mặt trừ
một cổng đang chờ nửa kia của tính năng.

---

## 8. Đi bộ như người dùng, vào chỗ 6 ca kia không tới

`tests/qa/qa-tt-0020/qa-di-bo-tim.mjs` — 5 phép kiểm, **0 hỏng**:

| đường đâm | kết quả |
|---|---|
| gửi bình luận **rỗng** | nút `disabled={trong}`, bấm vào không sinh mã máy nào; màn 851 ký tự toàn tiếng Việt |
| gõ **2500 ký tự** | `maxLength=2000` cắt ở phím 2001; cú gửi hợp lệ vẫn đi lọt, bình luận lên tường |
| **bấm tim hai lần** liên tiếp | `disabled={dangDoiTim}` nuốt cú thứ hai; không có 409 nào lên màn, số đếm về đúng 3 |

**Lần viết đầu của phép kiểm thứ hai khai một lỗi, và lỗi đó là của tôi.** Tôi
đi tìm một 422 "quá dài" mà người dùng không được báo — nhưng `maxLength` chặn
ở phím thứ 2001, nên cái 422 đó **không bao giờ xảy ra từ giao diện**. Không có
lỗi để hiện thì "không hiện lỗi" là hành vi đúng. Phép kiểm đã được viết lại để
đo cái có thật, và tôi để lại ghi chú đó trong file thay vì lặng lẽ xoá.

---

## 9. Ô CHƯA QUÉT — đọc kỹ phần này

- **Không có máy chủ thật.** Cả bốn route được stub trong trình duyệt
  (`tab-snapshots.mjs`). **Không gì ở đây chứng minh hợp đồng thật**: thân 201,
  thân rỗng 204, 409 khi thả hai lần, 422 khi rỗng — tất cả là hình dạng do
  frontend **giả định**. Ngày devops merge route, đây là phép kiểm đầu tiên
  phải chạy lại, và nó có thể đỏ mà không ai làm gì sai.
- **Tầng PostgreSQL và `npm run test:e2e` không chạy.** PR không đụng Python và
  chưa có route, nên không có gì cho hai tầng đó chạm.
- **`viewer_has_reacted` của người khác.** PR cố ý không nhận `viewer_id` từ
  query. Tôi **không kiểm được** điều đó ở phía máy chủ vì máy chủ chưa có.
- **Thiết bị thật, trình đọc màn hình thật.** `aria-checked` được đọc từ DOM đã
  render (đúng chỗ rnw 0.21.2 nuốt `accessibilityState`), nhưng chưa ai bật
  TalkBack/VoiceOver nghe nó đọc ra câu gì.
- **Mã QR quét bằng app ngân hàng thật** — vẫn chưa ai làm, không liên quan PR
  này nhưng câu đó chưa được xoá khỏi danh sách.

---

## 10. Nốt nhỏ, không chặn

`.github/workflows/test.yml:365` viết *"the three render checks in
tests/vo-tab-web.test.mjs"*. Giờ có **bốn** file dùng `MOBILE_REQUIRE_WEB_A11Y`
(`vo-tab-web`, `nhom-chat-web`, `luoi-kham-pha`, và `tim-binh-luan` của PR này).
Comment lệch, cơ chế đúng. Đúng loại drift mà chính `quet-tab-url.mjs` tự đếm
số màn để tránh.

Đường bỏ qua **đã được đóng**: `scripts/gate.sh:365` và `test.yml:378` đều đặt
`MOBILE_REQUIRE_WEB_A11Y=1`, nên một máy không có Chrome sẽ đỏ chứ không xanh
rỗng. Tôi chạy toàn bộ bảng đột biến của mình với cờ đó bật.

---

## Lệnh đã chạy

```bash
# cây gộp
git merge pr278-check                                  # sạch, 0 xung đột
git diff --stat origin/main HEAD -- '*.py'             # rỗng
python3 -m pytest services/api/tests tests -q          # 1844 passed, 366 skipped

# tại head #278 (63b3714)
cd apps/mobile && npm test                             # 680/680, 0 skipped
node tools/dot-bien-tim.mjs                            # 8/8 đúng kỳ vọng
node tools/qa-dot-bien-doc-lap.mjs                     # 8/9 đúng, C1 chỗ mù
node tools/qa-doi-chung-c1.mjs                         # ±7 ĐỎ, ±0 ĐỎ, ±1 XANH
PUPPETEER_EXECUTABLE_PATH=... node tools/quet-tab-url.mjs   # 4 canary OK, tổng 0
PUPPETEER_EXECUTABLE_PATH=... node tools/qa-di-bo-tim.mjs   # 5 kiểm, 0 hỏng
python3 scripts/check_api_contract.py                  # exit 1 (đo mã thật)
```

Kỹ năng đã dùng: `e2e-testing` (chặng 2 cổng rẻ, chặng 4 lát cắt, chặng 5 bề mặt
render, chặng 6 thăm dò, chặng 7 kết luận + ô chưa quét), `bug-reproduction`
(đối chứng ba lỗi hạ tầng: đỏ ở bản trước, xanh ở bản sau, và đối chứng cực trị
cho C1 để loại trừ "đột biến của tôi hụt").
