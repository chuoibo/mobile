# rd-qa-13 — Cổng đầy đủ trên main, và đối chứng ba bản sửa mới

**FAIL**

Cổng trên `main` xanh toàn bộ, nhưng biện pháp giảm thiểu của #124 không che
được thứ nó ngụ ý đã che: **link mời phát trước khi tắt vẫn nâng người cầm nó
lên ACTIVE và đọc được tin nhắn riêng của nhóm.** Tái lập được bằng ba ca đỏ.
Phạm vi ảnh hưởng thực tế hôm nay bằng không (không DB nào đang có link sống),
nên đây là phiếu cho **thiết kế bước 2**, không phải sự cố đang cháy.

- **protocol_version**: v1
- **Đo tại**: `42228d6c84ebaf78835b3552ef42058fead8f7cb`
- **SHA này**: **ĐÃ ở main** (`origin/main` tại thời điểm đo). Nhánh báo cáo
  `qa/rd-qa-13-doi-chung-rieng-tu` cắt thẳng từ đó, chỉ thêm file dưới
  `tests/qa/rd-qa-13/` và `docs/`.
- **Loại blocker**: loại 3 — quyền riêng tư / rò dữ liệu người khác.

---

## 1. Cổng đầy đủ trên main — tầng nào ĐÃ THẬT SỰ chạy

Tất cả chạy `TZ=UTC` theo yêu cầu của Lead (CI chạy UTC, và đó là oracle đã bắt
lỗi múi giờ ở #96; mất CI là mất sự đa dạng môi trường đó).

| Lệnh | Kết quả |
|---|---|
| `TZ=UTC python3 -m pytest services/api/tests tests -q` | **1011 passed, 198 skipped**, 4580 subtests |
| `tests/postgres` với `MOBILE_REQUIRE_POSTGRES_TESTS=1` | **172 passed, 3 skipped** — 0 skip vì thiếu môi trường |
| `cd apps/mobile && TZ=UTC npm test` | **333/333 pass**, 0 fail, 0 skip |
| `python3 scripts/repo_guard.py staged` | `Repo guard passed` |

**198 skip ở lệnh 1 không phải xanh** — đó là tầng Postgres tự bỏ qua khi thiếu
URL. Lệnh 2 chạy lại đúng tầng đó với `MOBILE_REQUIRE_POSTGRES_TESTS=1` trên
một database riêng (`qa13`), không stamp DB dùng chung.

**3 skip còn lại ở lệnh 2 là chỗ phát hiện bên dưới bắt đầu**: chúng là ba ca
phủ đường link, bị #124 tắt.

---

## 2. Phát hiện — #124 tắt việc PHÁT link, không tắt link ĐÃ PHÁT

### Vì sao ba ca bị skip lại quan trọng

#124 (bug-141903 bước 1) làm `POST /outings/{id}/invites` với `source="link"`
trả 422, rồi đánh dấu `pytest.mark.skip` ba ca đang phủ đường link. Mô tả PR **trung
thực** rằng vị từ tự vòng tròn để lại cho bước 2 — tôi không cho rằng ai giấu
gì.

Nhưng ba ca bị tắt là đúng những ca có thể hỏi câu còn lại: link là **bearer
token nằm trong tin nhắn của người ta**. Từ chối phát link mới không đụng gì
tới link đã phát, và không có gì thu hồi chúng.

Hai route tiêu thụ link vẫn còn mounted trên `main`:

```
POST /outing-invites/{token}/accept       -> membership INVITED cho người cầm link
POST /memberships/{membership_id}/accept  -> is_invitee == hàng vừa ghi ở trên
```

`accept_outing_invite` kiểm `accepted_at` (dùng một lần) nhưng **không kiểm
hạn**, nên một link tồn đọng sống mãi.

### Tái lập

`tests/qa/rd-qa-13/test_link_ton_dong_van_nang_quyen.py` — ba ca, mỗi ca một
khẳng định riêng, để một bản sửa chỉ đổi status code không lặng lẽ làm xanh cả
ba. Hàng `OutingInvite` được ghi thẳng vào DB vì đó là **cách duy nhất trạng
thái ấy còn tồn tại được sau #124** — nó đại diện đúng cho hàng mà mọi deployment
từng chạy code trước #124 đang có.

```
cd services/api && MOBILE_TEST_DATABASE_URL=... MOBILE_REQUIRE_POSTGRES_TESTS=1 \
  python3 -m pytest ../../tests/qa/rd-qa-13 -q
```

Cả ba **đỏ** trên `42228d6`:

| Ca | Mong đợi | Nhận được |
|---|---|---|
| link phát trước khi tắt vẫn redeem được | 404 | **200** `membership_state=invited` |
| người cầm link tự nâng mình lên ACTIVE | 403 | **200** `"state":"active"` |
| người cầm link đọc tin nhắn + số dư nhóm | 403 | **200**, đọc nguyên văn |

Ca 3 in ra chính nội dung tin nhắn riêng:
`"body":"Số tài khoản của mình là 000-bí-mật, chuyển khoản nhé"`.
Đây là **rò dữ liệu người khác**, không chỉ là sai status code.

Phép kiểm khẳng định **cửa ĐÓNG trước** (người lạ nhận 403 khi chưa redeem) rồi
mới khẳng định cửa mở. Một phép kiểm rò rỉ chỉ có vế phủ định sẽ xanh y hệt trên
một trang trắng.

### Phạm vi ảnh hưởng thật — bằng không, hôm nay

Tôi kiểm trước khi tin con số của chính mình:

- DB dùng chung `mobile` đang ở revision `8f1c6a4b2e70`, **chưa có bảng
  `outing_invites`**.
- DB của lane `fe12` (lane đang làm buổi đi chơi) **có** bảng, **0 hàng**.

Không có link nào đang sống ở bất kỳ đâu tôi nhìn được. Nên đây **không** phải
sự cố đang cháy, và tôi không đề nghị chặn merge gì cả.

### Tiêu chí gỡ chặn

Bước 2 phải kèm **thu hồi hoặc hết hạn cho link đã phát**, không chỉ sửa vị từ
`is_invitee`. Sửa vị từ mà để nguyên các hàng `outing_invites` cũ thì mọi link
đã phát vẫn redeem được ngay khi vị từ được nới ra lần nữa. Gợi ý rẻ nhất: một
cột `expires_at` + `revoked_at`, và bỏ skip ba ca cùng lúc.

Ba ca đỏ này chuyển xanh là tiêu chí nghiệm thu tự nhiên cho bước 2.

---

## 3. Đối chứng hai cổng a11y mới — cả hai đều THẬT

Chu kỳ thường trực mục 4: chọn một test đang xanh, làm hỏng code nó lẽ ra phải
bảo vệ, xem nó có đỏ không. Làm với cả #122 và #125.

| Đột biến | Kết quả | Kết luận |
|---|---|---|
| Xoá `tabIndex={0}` khỏi vùng cuộn `CaNhan.tsx` | **331 pass / 2 fail** — đỏ đúng 2 ca của #122 | Cổng #122 thật, không có thiệt hại phụ |
| Xoá `aria-label={label}` khỏi `Field` trong `Kit.tsx` | **327 pass / 6 fail** | Cổng #125 thật |
| Khôi phục cả hai | **333/333 pass** | Cây sạch trở lại |

Không tìm ra cổng giả nào. Đây là kết quả hợp lệ và tôi ghi nó ra đúng như vậy.

---

## 4. Quét a11y trên bundle ĐÃ RENDER

Hai cổng trên đọc markup react-native-web phát ra, **trong node**. Tốt hơn đọc
`.tsx` nhiều, nhưng vẫn không phải trình duyệt — rnw 0.21.2 đã từng nuốt thuộc
tính trên đường ra DOM. Nên tôi dựng bundle mới từ `42228d6`
(`expo export --clear`, `EXPO_PUBLIC_API_URL` ghim 8099) và quét bằng Playwright
+ axe.

Ba lớp chống xanh giả trong `scan-render.mjs`:

1. **Khẳng định app đã mount** (174 node) — zero violation trên trang trắng là
   lời nói dối, không phải kết quả sạch.
2. **Canary**: trồng một `<img>` không alt và bắt buộc axe phải bắt được. axe
   chết và trang sạch trả về **cùng một mảng rỗng**. Canary bắt được →
   `scanner is alive`.
3. **Trạng thái ba giá trị** — `NOT COVERED` không bao giờ in thành `PASS`.

`walk-render.mjs` bấm thật qua ba màn (App.tsx định tuyến bằng state, không có
fragment để deep link).

| Màn | axe critical/serious | #125 | #122 |
|---|---|---|---|
| vao-cua (landing) | 0 | NOT COVERED (không có ô nhập) | NOT COVERED |
| dang-nhap-sdt | 0 | **PASS** | NOT COVERED |
| chon-nguoi (roster) | 0 | NOT COVERED | NOT COVERED |

**#125 xác nhận trong DOM thật**: `aria-label="Số điện thoại"` khác
`placeholder="09xx xxx xxx"`, 2 ô, 0 ô không tên, 0 ô lấy placeholder làm tên.
Bản sửa sống sót qua react-native-web tới tận DOM.

17 rule axe pass, console sạch, 0 uncaught error.

---

## 5. Ô CHƯA QUÉT — phần quan trọng nhất của báo cáo

- **#122 chưa được xác nhận trong trình duyệt.** Không màn nào trong luồng vào
  cửa có vùng cuộn tràn; tới được Cá nhân cần đăng nhập + dữ liệu. Cổng node
  của nó là thật (mục 3), nhưng "rnw có giữ `tabIndex` tới DOM không" thì tôi
  **chưa trả lời được**.
- **Nửa sau của luồng chưa đi bằng tay**: form → chia tiền → đợt thu → publish
  → trang khách. Vẫn chỉ có e2e ở tầng HTTP.
- **Mã QR chưa được quét bằng app ngân hàng thật.** Không agent nào làm được
  việc này; cần leader, một điện thoại, 15 phút.
- **Chỉ quét ở 390×844.** Chưa quét 320 và 1440, chưa quét chủ đề tối.
- **Ba màn đã quét đều là màn vào cửa.** Khám phá, nhóm chat, chia bill, kỷ
  niệm đều chưa có ảnh a11y ở lượt này.
- **Không quét trình đọc màn hình thật** (VoiceOver/NVDA/TalkBack). axe bắt
  30–40%; phần còn lại cần người.

### Ghi chú phương pháp, để lượt sau không mất thời gian

`grep` chuỗi tiếng Việt trong bundle ra **0** ở cả ba bản dựng (qa11/qa12/qa13),
trong khi trình duyệt render đủ chữ. Bundle grep là **dụng cụ sai** cho câu hỏi
"màn này có chữ gì" — đừng đọc kết quả rỗng của nó thành "màn hình trống". Chỉ
URL đã render mới trả lời được.

---

## 6. Việc đã làm, để chạy lại

```bash
git checkout 42228d6

# cổng rẻ
TZ=UTC python3 -m pytest services/api/tests tests -q

# tầng postgres thật, database riêng
docker exec mobile-local-postgres-1 psql -U mobile -d mobile -c "CREATE DATABASE qa13;"
cd services/api && TZ=UTC \
  MOBILE_TEST_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/qa13' \
  MOBILE_REQUIRE_POSTGRES_TESTS=1 python3 -m pytest tests/postgres -q

# ba ca đỏ của phát hiện
cd services/api && TZ=UTC MOBILE_TEST_DATABASE_URL=... MOBILE_REQUIRE_POSTGRES_TESTS=1 \
  python3 -m pytest ../../tests/qa/rd-qa-13 -q

# bundle + quét trình duyệt
cd apps/mobile && EXPO_PUBLIC_API_URL=http://localhost:8099 \
  npx expo export --platform web --output-dir dist-qa13 --clear
python3 -m http.server 8913 --directory dist-qa13 &
cd tests/qa/rd-qa-13 && ln -s ../rd-qa-11/node_modules node_modules
node scan-render.mjs http://localhost:8913/
node walk-render.mjs http://localhost:8913/
```

`node_modules` trong `tests/qa/rd-qa-13/` là symlink sang bản cài của rd-qa-11
và được `.gitignore` — repo guard fail closed với symlink, nên nó không bao giờ
vào Git.
