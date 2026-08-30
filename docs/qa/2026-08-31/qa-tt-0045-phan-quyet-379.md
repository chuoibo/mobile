# FAIL cho #379 tại `ebfa0433`

**Lý do (đọc dòng này là đủ để hành động):** sản phẩm **đúng** — màn Album đi
được cả ba tầng, cả hai cửa vào đều bấm tới nơi, ba route F36/F37 thật sự chạy,
`X-Actor-ID` có trên dây. Nhưng **gộp vào `main` làm `main` đỏ ở hai cổng**, và
cả hai đều xanh trên `main` khi chưa có #379. Hai chỗ phải sửa, đều là giấy tờ,
không phải sản phẩm:

1. `.server-routes-uncalled.json` vẫn ghi ba route album là "không ai gọi",
   trong khi #379 vừa cho chúng người gọi. **#379 không đụng file này.**
2. `apps/mobile/src/screens/album/album-api.ts:158` dựng URL bằng biến
   (`${BASE_URL}${duong}`) nên cổng hợp đồng header không phân giải được.
   Header **có được gửi** — đây là điểm mù của bộ đọc tĩnh, không phải lỗ hổng.

Sửa xong hai chỗ đó là PASS. Tôi không sửa hộ: vá rồi tự nghiệm thu là mất tính
độc lập.

---

## Đo trên cái gì

```
đo tại    ebfa0433d0398461fcf53066d99ae111ed179d60   (head #379 lúc nhận việc)
cây gộp   f2f506e = #379 ⊕ main@7cdb109
kiểm lại  #379 ⊕ main@703db38  (main đã nhích hai lần giữa lượt: 7bd0198 →
          7cdb109 → 703db38; hai cổng đỏ y hệt ở cả hai nền)
sha này   là nhánh CHƯA merge
```

`main` nhích giữa lượt đo, nên mọi con số dưới đây đều ghi kèm nền của nó. Hai
cổng đỏ được xác nhận trên **cả hai** nền `main`, nên kết luận không phụ thuộc
vào việc đoàn tàu merge chạy tới đâu.

## Cổng đã chạy

| Cổng | Nền | Kết quả |
|---|---|---|
| `npx tsc --noEmit` | head #379 | exit 0 |
| `npm test` | head #379 | **819/819**, 0 skipped |
| `npx tsc --noEmit` | cây gộp `f2f506e` | exit 0 |
| `npm test` | cây gộp `f2f506e` | **834/834**, 0 skipped |
| `pytest services/api/tests tests -q` | cây gộp `f2f506e` | **2 failed**, 2623 passed, 563 skipped, 4891 subtests |
| hai cổng đỏ, chạy riêng | `main@7cdb109` | **36 passed** |
| hai cổng đỏ, chạy riêng | `main@703db38` | **36 passed** |
| hai cổng đỏ, chạy riêng | #379 ⊕ `main@703db38` | **2 failed** |

Xanh trên `main`, đỏ sau khi gộp, trên hai nền độc lập → do #379, không phải nợ
sẵn có. Đây đúng hình dạng Lead đã cảnh báo: Git gộp sạch, không một dấu xung
đột, mà cây sau khi gộp thì đỏ.

## Blocker 1 — file nợ còn ghim ba route album

Loại: **vi phạm spec/cổng**.

```
tests/test_server_routes_called_gate.py::TheMechanismIsLoadBearing
  ::test_without_the_debt_file_the_real_tree_is_red

+  '/contexts/{context_id}/albums',
+  '/contexts/{context_id}/albums/{outing_id}',
+  '/contexts/{context_id}/albums/{outing_id}/reel',
: file nợ khai những route này không ai gọi, nhưng cổng không báo đúng tập đó
  khi bỏ ghim đi -- hoặc cơ chế không gác gì, hoặc có dòng đã trả nợ mà chưa gỡ.
```

Đây là trường hợp thứ hai: nợ **đã trả** mà dòng ghim chưa gỡ. #379 cho ba route
người gọi nhưng không sửa `.server-routes-uncalled.json`.

**Gỡ chặn:** xoá ba dòng album khỏi `.server-routes-uncalled.json`.

Lưu ý phối hợp: #365 cũng sửa đúng file này (`+20/-20`). Lead đã dặn *"luôn lấy
HỢP hai bên"* — ai merge sau phải lấy hợp, đừng ghi đè, nếu không route của lane
kia sẽ lặng lẽ quay lại danh sách nợ.

## Blocker 2 — cổng header actor không đọc được URL dựng bằng biến

Loại: **vi phạm spec/cổng**. **Không phải** lỗ hổng quyền.

```
Cổng header actor — 116 file client, 133 lời gọi tới route đòi X-Actor-ID.
HỎNG — 1 chỗ dựng URL mà cổng không phân giải được:
  apps/mobile/src/screens/album/album-api.ts:150 doc()
      ${BASE_URL}${duong}
```

Cổng nói **UNRESOLVED**, không nói *thiếu*. Hai câu đó khác nhau, và chỉ một
trong hai là lỗi sản phẩm — nên tôi đọc header **trên dây** thay vì đọc source.
Cả ba lời gọi album đều mang đủ ba header:

```
/contexts/{cid}/albums                    X-Actor-ID: 46b55e67-…  Roles: member
/contexts/{cid}/albums/{oid}              X-Actor-ID: 46b55e67-…  Roles: member
/contexts/{cid}/albums/{oid}/reel         X-Actor-ID: 46b55e67-…  Roles: member
```

`tieuDe()` ở `album-api.ts:134` gắn `X-Actor-ID` / `X-Actor-Roles` /
`X-Actor-Contexts` cho mọi lời gọi đi qua `doc()`. Sản phẩm đúng.

**Gỡ chặn:** một trong hai — viết lại đường dẫn thành template literal cổng đọc
được, hoặc ghim vào `.actor-header-unresolved.json` (cổng nói thẳng: *"ghim là
nói ra chỗ mù, không phải xoá nó"*).

Đây là **cùng một chặng** đã làm #365 đỏ (phán quyết #373). Lead đã dự đoán đúng
là nó sẽ đập vào hai lane độc lập.

## Sản phẩm thì đúng — và đây là bằng chứng hành vi

Không đọc source, không đếm tên màn: dựng **hai** bundle web thật rồi đi bộ
bằng trình duyệt trên cả hai.

```
TRƯỚC = main@7cdb109
SAU   = #379 ⊕ main@7cdb109
cd apps/mobile && EXPO_PUBLIC_API_URL=http://api.build-check.invalid \
  npx expo export --platform web --output-dir <dir> --clear
python3 tests/qa/qa-tt-0045-album/di_bo_album.py <truoc> <sau>     # exit 0 = ĐẠT
```

| Phép đo | TRƯỚC | SAU |
|---|---|---|
| `[+]` có dòng "Album chuyến đi" | **không** | có |
| Bấm dòng đó tới được kệ album | timeout — không có dòng để bấm | **tới được** |
| Số route `/albums` thật sự chạy | **0** | **3** |
| Lùi được mấy tầng | 0 | **3** |
| `X-Actor-ID` trên mọi lời gọi | không có lời gọi nào | **có đủ** |

Đối chứng TRƯỚC mới là phần đáng giá: `#vao=album` trên `main` rơi về tab Khám
phá và chỉ gọi `/places`. Nếu bản trước cũng tới được album thì phép đo này đang
đo thứ khác chứ không đo #379.

Ba tầng đều render bằng số của máy chủ, không phải hằng số dán sẵn: kệ đọc
`1.240.000đ` · `2 ảnh` · `2 chỗ`; màn một album ra ảnh, "Nhóm thích nhất",
"Đã tới"; thước phim ra hai khoảnh khắc kèm câu AI viết và nhãn "AI dựng thước
phim này". Lùi đi đúng từng tầng một — thước phim → một album → kệ → ra ngoài,
không nhảy thẳng, đúng như mô tả PR.

Cả hai cửa đều đo: cửa `[+]` là đường của **người** (không fragment, chỉ bấm),
cửa `#vao=album` là đường của **công cụ**. Một PR chỉ mở cửa thứ hai vẫn là màn
không ai tới được.

## Phát hiện không chặn

**`place_name: null` in ra UUID trần cho người dùng.** `AlbumChuyenDi.tsx:503`

```tsx
· {p.place_name ?? p.place_id}
```

Đo được:

```
Đã tới
· Quán Gió
· e6a97af8-0415-52a4-9ff2-52980e7dadec
```

Đây là trạng thái **có thật**, không phải hàng hỏng: `AlbumPlace.place_name`
khai nullable trong `openapi.json`, và `domain/album.py::_text()` trả `None` cho
mọi tên rỗng hoặc thiếu. Màn thước phim ở dòng 705 xử lý đúng ca này
(`place_name ? … : ""`); màn một album thì không.

Không thuộc 5 loại blocker → **suggestion**, không chặn merge. Nhưng nó nằm trên
đường hero (Kỷ niệm → Album) nên đáng sửa cùng lúc: bỏ dòng đó đi, hoặc viết
"Chỗ chưa đặt tên".

**Tự đính chính:** vòng đo đầu tiên tôi báo cả hai chỗ đều ra UUID. Sai — stub
của tôi gửi `name` trong khi máy chủ gửi `place_name`, nên màn rơi về id đúng
như nó được viết. Sửa stub theo `openapi.json` rồi đo lại thì ca có tên ra
"Quán Gió". Chỉ ca `null` mới là phát hiện thật.

**Vùng chưa có test.** #379 thêm 804 dòng `AlbumChuyenDi.tsx` + 259 dòng
`album-api.ts`, và test đi kèm chỉ là `navigation.test.mjs` `+7/-4`
(`assert.equal(CREATE_ACTIONS.length, 5)`). Không có file test nào cho album, và
hai file này **không nằm trong `tsconfig.test.json`** (`grep -c album` → `0`),
nên hiện chưa test nào biên dịch được chúng. Ca `place_name: null` ở trên chính
là loại lỗi một test dựng màn sẽ bắt. Suggestion, không chặn.

## Ô CHƯA quét — đọc phần này trước khi tin dấu xanh ở trên

- **`tests/postgres` chưa chạy** lượt này. 563 skipped trong `pytest` là thiếu
  `MOBILE_TEST_DATABASE_URL`; skip không phải xanh. #379 không đụng persistence
  nên tôi không coi đây là rủi ro của PR này, nhưng nó **chưa được chạy**.
- **`npm run test:e2e` chưa chạy** — cần uvicorn + Postgres sống.
- **Album chưa đo trên máy chủ THẬT.** Ba route được chứng minh là *có gọi* và
  *gọi đúng đường*, với payload theo `openapi.json` của chính cây này. Chưa
  chứng minh máy chủ thật trả đúng hình dạng đó cho một nhóm có dữ liệu thật.
  Máy demo 8099 có đủ ba route (77 route, cũ hơn cây: cây có 83).
- **Chỉ quét một khung 390×844, chủ đề sáng.** Chưa quét 320, chưa quét 1440,
  chưa quét chủ đề tối, chưa đo tương phản hay bàn phím trên màn album.
- **Ảnh thật chưa render** — stub trả PNG 1×1, nên chưa nói được gì về bố cục
  lưới ảnh với ảnh thật.
- **Thước phim AI chưa gọi Gemini thật.** Nội dung reel trong phép đo là stub;
  chưa kiểm ảo giác / grounding của `ground_reel`.
- **Mã QR chưa được quét bằng app ngân hàng thật** — vẫn nguyên, không liên quan
  #379 nhưng vẫn là ô mở của sản phẩm.

## Tái lập

```bash
git checkout ebfa0433 && git merge origin/main --no-edit
python3 -m pytest tests/test_actor_header_contract.py \
                  tests/test_server_routes_called_gate.py -q     # 2 failed

git checkout origin/main
python3 -m pytest tests/test_actor_header_contract.py \
                  tests/test_server_routes_called_gate.py -q     # 36 passed
```
