# Đi bộ lại tám tính năng vừa merge, bằng ngón tay chứ không bằng curl

- **Việc**: `qa3-021135`, đuôi `50322101`
  (viết tách đôi: nối liền lại thì repo guard đọc thành một dãy 14 chữ số)
- **Đo tại**: `origin/main` = `62f4ee4`; màn chi tiết địa điểm đo tại `af145a5`
  (head PR #365, đã merge thành `f363639` trong lúc tôi đang đi bộ)
- **Main đã nhích trong lượt đo**: `62f4ee4` → `70b5b18` (#365, #398, #399).
  Bản dựng tôi đi bộ là `62f4ee4`. Ba commit vào sau không đụng màn nào dưới đây.
- **Khung**: Chrome thật 390×844, `deviceScaleFactor: 2`, `isMobile`, `hasTouch`
- **67 ảnh chụp**: `/tmp/qa3-walk/shots/` (ngoài repo — repo guard fail closed với binary)

## Đo cái gì, trên cái gì

Không dùng 8099. Stack riêng, dựng và huỷ trong lượt này:

```
scripts/e2e_slice.sh --keep
  → postgres dùng một lần   127.0.0.1:44933  (container mobile-e2e-pg-2571725-f75d3af4)
  → API lát cắt             127.0.0.1:45865
  → npm run test:e2e        tests 7 · pass 7 · fail 0 · skipped 0
```

Lát cắt dọc chạy **thật** (`MOBILE_REQUIRE_E2E=1` do chính script đặt), 0 skipped.

Rồi một database thứ hai trong cùng container cho bộ dữ liệu demo, vì bộ demo và
lát cắt dọc **đụng nhau ở khoá idempotency cố định** (xem phần bẫy môi trường):

```
database `demo` + alembic upgrade head
uvicorn 127.0.0.1:45899  (có GEMINI_API_KEY thật, nạp từ /home/lakiet/mobile/.env)
scripts/seed_demo_data.py → 7 người · 5 khoản chi · 3 đợt thu · 16 link khách
```

Hai bản dựng web, mỗi bản `--clear`, và **đếm ref trong chính bundle mà
`index.html` trỏ tới** trước khi tin bất kỳ số nào:

| Bản dựng | bundle | ref `45899` | ref `8099` | phục vụ tại |
|---|---|---|---|---|
| `62f4ee4` (main) | `index-9854207b…` | 5 | 0 | `127.0.0.1:45990` |
| `af145a5` (#365) | `index-8244a8de…` | 5 | 0 | `127.0.0.1:45991` |

Màn "Chụp bill" tự in ra `Máy chủ: http://127.0.0.1:45899` — đối chứng thứ hai,
đọc từ giao diện chứ không từ file trên đĩa.

Đếm phần tử bấm được **phủ hết vai trò**, không chỉ `button`:
`button, [role=button], [role=tab], [role=link], [role=menuitem], [role=switch],
[role=checkbox], [role=radio], a, input, select, textarea`. Và `about:blank`
chèn giữa mọi lần nạp, vì `AppRoot` đọc fragment một lần lúc mount.

## Kết quả — ba trạng thái

| # | Tính năng | Trạng thái | Đo được gì |
|---|---|---|---|
| F16 | Hỏi thẳng AI → lịch trình → tab Plan | **BẤM-ĐƯỢC** | `POST /ai-turn` 200, Gemini thật trả 2 chặng, tab Plan có nội dung |
| F14 | Màn chuyến → mời thêm người | **BẤM-ĐƯỢC** | `POST /outings/{id}/invites` 201, có dòng thật trong `outing_invites` |
| F17 | Bình chọn: **mở** | **BẤM-ĐƯỢC** | form mở, 2 lựa chọn lấy từ gợi ý AI của nhóm |
| F17 | Bình chọn: **bỏ phiếu** | **BẤM-ĐƯỢC** | 1 phiếu, 👑 dẫn đầu, "1/7 thành viên đã bỏ phiếu" |
| F17 | Bình chọn: **đóng** | **KHÔNG-CÓ-ĐƯỜNG** | không nút nào trong sản phẩm; nút có thật nằm sau cửa quét |
| F22 | Ô vuông vô danh + tự nhận món | **KHÔNG-CÓ-ĐƯỜNG** | hai màn chỉ mount trong cửa quét `?man=`, callback lưu là no-op |
| — | Màn Quản trị nhóm | **BẤM-ĐƯỢC** | đổi vai trò và mời vào chuyến đều ghi thật xuống DB |
| — | Màn Thành tích | **BẤM-ĐƯỢC** | render số đọc từ sổ (5 bill, 1 nhóm, 75/100 điểm) |
| — | Màn chi tiết địa điểm (#365) | **BẤM-ĐƯỢC** | `GET /places/p-tiem-nuong-xom-lao` 200, màn đầy đủ |
| — | Lên plan → dòng thời gian (#391) | **BẤM-ĐƯỢC** | `GET /outings/{id}/checkins` 200, 3 chặng hiện ra |

Không ô nào **TẮC** — không đường bấm nào chết giữa chừng bằng một mã HTTP.
Hai ô hỏng theo kiểu khác và tệ hơn: **không có đường để tắc.**

## Phát hiện chính: sáu route được xoá khỏi sổ nợ mà ngón tay vẫn không chạm tới

`#375` ("F17 và F22 có màn gọi") gỡ **sáu dòng** khỏi
`.server-routes-uncalled.json` — bốn route bình chọn, `/bills/{id}/my-items`,
`/photos/{id}/face-boxes`. Commit message ghi "gỡ sáu dòng nợ đã trả".

Đi bộ lại thì **không dòng nào trong sáu dòng đó trả được**:

**Bình chọn trong sản phẩm không đi qua máy chủ.** Mở bình chọn, bỏ một phiếu,
tải lại trang — thẻ bình chọn vẫn còn, đếm đúng, 👑 đúng chỗ. Nhưng:

```
select count(*) from votes;        → 0
select count(*) from vote_ballots; → 0
```

Thẻ sống trong **luồng tin nhắn**: `POST /contexts/{id}/messages` 201, không có
lời gọi nào tới `POST /contexts/{id}/votes` hay `POST /votes/{id}/ballots`.
`TinNhan.tsx:236` khai một `boPhieu` cục bộ gửi `guiTheAi(cardBoPhieu(...))`, che
mất `boPhieu` của `api.ts`. Bốn hàm client `docDanhSachBinhChon`, `docBinhChon`,
`boPhieu`, `dongBinhChon` **không màn nào gọi**.

**Màn bình chọn có nút "Đóng bình chọn" chỉ tồn tại sau cửa quét.**
`App.tsx:1397 XemBinhChon` dựng nó từ fixture cứng, và chính file đó viết ra:
`onDong={() => {}}`, kèm câu "no writes, and no route from here into the
product". Nên câu "F17: mở → bỏ phiếu → đóng" dừng ở bước hai.

**Hai màn F22 cũng vậy.** `MonCuaToi` và `NhanMatTrenAnh` được import **đúng một
chỗ** — `App.tsx`, trong cửa quét `?man=mon-cua-toi` và `?man=nhan-mat`, với
`onLuu={() => {}}` và `onXong={() => {}}`. Không màn sản phẩm nào render chúng.
Cả hai render đẹp và đọc được (ảnh `F22-*.png`); chúng chỉ không nối vào đâu cả.

### Vì sao cổng không kêu

`scripts/check_server_routes_called.py` chạy xong in:

```
Máy chủ khai 77 route. 63 có người gọi, 5 miễn, 9 đang nợ, 0 không ai gọi và chưa ghi nhận.
Không có route mới nào bị bỏ rơi.        (thoát 0)
```

`client_mentions()` khai đúng ý định của nó: *"Every route named anywhere in
`apps/mobile/src`"*. Cổng đếm **một chuỗi literal trong `src/api.ts`** là "có
người gọi". Ngoài `api.ts`, sáu đường dẫn này chỉ xuất hiện trong **comment**, mà
`mentions_in_source` cố ý bỏ qua comment — nên `api.ts` là thứ **duy nhất** đang
giữ sáu dòng đó khỏi sổ nợ.

Đối chứng bằng đột biến, không phải bằng suy luận. Đột biến **chỉ** 5 chuỗi
đường dẫn trong `api.ts` (không đụng một màn nào), rồi chạy lại cổng:

| Cây | Kết quả | Mã thoát |
|---|---|---|
| sạch | `63 có người gọi … 0 không ai gọi và chưa ghi nhận` | **0** |
| đột biến 5 chuỗi trong `api.ts` | `58 có người gọi … 5 không ai gọi và chưa ghi nhận` | **1** |

Đúng 5 chuỗi đổi → đúng 5 route bị bắt, 1:1. Không màn nào bị sửa trong lần đột
biến đó, nên con số 63 ở cây sạch **hoàn toàn** dựa vào `api.ts`. `api.ts` đã
được `git checkout -- ` khôi phục ngay sau phép đo; cây sạch lại và cổng về 0.

(Mã thoát phải đọc **không qua pipe**: `... | head` trả 0 kể cả khi cổng thoát 1.)

Đây đúng họ với "route chạm tới ≠ guard được gác": cổng đo sai một tầng — nó hỏi
"có file nào trong `src/` nhắc tên đường dẫn không", câu cần hỏi là "có ngón tay
nào tới được không".

Sửa được bằng cách đã có sẵn trong cây: `tests/moi-man-co-duong-do.test.mjs` bắt
mỗi màn khai `do:` hoặc `chuaDo:`. Cổng route cần cùng hình dạng — một route chỉ
được coi là đã trả nợ khi người gọi nằm **ngoài** `api.ts`, và cửa quét `?man=`
phải đếm là `chuaDo` chứ không phải là người gọi.

### Cổng màn-có-ai-render (#384, merge trong lúc tôi đang đi bộ) cũng đọc cửa quét là đường thật

`scripts/check_screens_reachable.py` vừa lên main. Chạy trên main hiện tại:

```
51/52 màn có đường render từ cửa vào · 1 pin · 122 file đã đọc     (thoát 0)
--json → {"stats": {"screens": 52, "reachable": 51, ...}, "findings": []}
```

`findings` rỗng, và **không** dòng nào nhắc `MonCuaToi`, `NhanMatTrenAnh` hay
`BinhChon` — ba màn mà lượt đi bộ này vừa cho thấy là không có đường bấm tới.
Chúng "có đường render từ cửa vào" đúng theo nghĩa đen: cửa vào là
`App.tsx`, và `App.tsx` render chúng — trong cửa quét `?man=`, với callback lưu
là no-op.

Nên hai cổng khác nhau, viết cách nhau vài ngày, đang cùng đọc **cửa quét** là
bằng chứng phủ. Cửa quét được dựng để một trình duyệt headless mở được màn mà
đo; nó không phải lời khai rằng người dùng tới được. Cả hai cổng cần phân biệt
hai chuyện đó — `moi-man-co-duong-do.test.mjs` đã có sẵn đúng cái từ vựng ấy
(`do:` so với `chuaDo:`).

**Phân loại**: blocker loại 1 (vi phạm cổng) — hai cổng đang in màu xanh cho sáu
route và ba màn người dùng chưa chạm tới được. Không phải loại 2: không đồng
tiền nào sai.

**Tiêu chí gỡ chặn**: hoặc nối sáu route vào màn thật, hoặc trả sáu dòng về
`.server-routes-uncalled.json` và sửa cổng để wrapper trong `api.ts` không còn
tính là người gọi.

## Hai bẫy môi trường, mỗi cái tốn một vòng

**`scripts/reset_demo_group.py` bỏ qua `MOBILE_DATABASE_URL`.** Nó chỉ đọc
`--dsn`, mặc định `postgresql://…@127.0.0.1:5432/mobile` — **database dùng
chung**. Tôi chạy nó với `MOBILE_DATABASE_URL` trỏ vào database dùng một lần của
mình, và nó đổi tên nhóm demo trên **database chung** (`5cacfdee…`), in ra
"1225 key trên máy" trong khi database của tôi gần như trống — đó là dấu hiệu
duy nhất để nhận ra. Tôi đã **khôi phục ngay**:

```
update contexts set display_name = 'Team Đà Lạt' where id = '5cacfdee-955f-4743-9cc4-c6a019480c96';
→ UPDATE 1   (đọc lại: đúng tên cũ, không xoá dòng nào, không đụng key nào)
```

Cùng hình dạng với `alembic -x sqlalchemy_url` bị bỏ qua im lặng: một biến môi
trường đúng tên, đúng ý định, và công cụ không đọc nó. Đề nghị: cho
`reset_demo_group.py` đọc `MOBILE_DATABASE_URL` làm mặc định, hoặc **in DSN nó
sắp đụng và đòi xác nhận** khi DSN là cổng 5432.

**`seed_demo_data.py` và lát cắt dọc đụng nhau trên database mới tinh.** Cả hai
tạo nhóm "Team Đà Lạt" bằng cùng một khoá idempotency cố định, nên chạy
`e2e_slice.sh` trước rồi seed sau thì seed chết ở
`POST /contexts/{id}/members → 409 membership_already_open`, và đổi tên nhóm cũ
không gỡ được vì id nhóm là tất định. Cách đi được: **hai database tách hẳn**.

## Ô CHƯA QUÉT — phần quan trọng nhất

- **Mã QR chưa được quét bằng app ngân hàng thật.** Không agent nào quét được.
  Còn nguyên cho tới khi leader cầm điện thoại thật (ADR-0010 mục 8).
- **Đường hero đầy đủ chưa đi hết**: tôi dừng ở màn "Chụp bill" (có nút "Chọn
  ảnh bill"), **không** tải ảnh lên, nên OCR → gán món → chia → VietQR **không
  đo trong lượt này**. #396 đã đo phần đó trên ảnh chuyển khoản.
- **"Rời nhóm"** trên màn Quản trị: nút có mặt, **tôi không bấm** — nó phá trạng
  thái phiên đang dùng cho các bước sau. Chưa đo.
- **Điện thoại thật**: mọi số ở trên là react-native-web trong Chrome. Không nói
  gì về bản native.
- **Chế độ tối, khung 320 và 1440**: chưa quét. Chỉ đo 390×844, sáng.
- **Trang khách `/g/{token}`**: 16 link đã sinh ra, **chưa mở link nào** trong
  lượt này.
- **Đọc được hay không**: tôi đọc DOM và ảnh chụp, **không chạy** detector,
  axe, hay phép đo tương phản. "Render được" ≠ "đọc được".
- **Hai thẻ bình chọn trùng nhau** trong ảnh chụp là **do tôi tạo hai lần**
  (hai lượt thử), không phải lỗi render. Đừng đi sửa nó.

## Lệnh chạy lại được

```bash
scripts/e2e_slice.sh --keep                       # → API + postgres dùng một lần
docker exec <container> psql -U mobile -d postgres -c "create database demo owner mobile;"
cd services/api && MOBILE_DATABASE_URL=<demo> python3 -m alembic upgrade head
MOBILE_SEED_API_BASE_URL=<api> MOBILE_DATABASE_URL=<demo> python3 scripts/seed_demo_data.py
cd apps/mobile && EXPO_PUBLIC_API_URL=<api> npx expo export --platform web \
  --output-dir <dir> --clear                      # rồi ĐẾM ref trong bundle
python3 -m http.server <port> --bind 127.0.0.1    # trong <dir>
python3 scripts/check_server_routes_called.py     # in "0 không ai gọi" — đó là chỗ mù
```
