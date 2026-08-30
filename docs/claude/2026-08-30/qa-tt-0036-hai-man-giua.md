# PASS — #344 đã lên main tại `aca7f68`, cổng xanh, lời khai chính đúng; một điểm mù của cổng và một tên món bị cắt ở 390px

**Lý do (đọc dòng này là đủ để quyết định):** cổng đầy đủ trên `main@aca7f68` xanh
(backend 2524 pass / 0 fail, mobile 757/757 / 0 fail / 0 skipped). Lời khai trung tâm của
#344 — "hai màn giữa trước đây không máy nào mở được, giờ mở được" — **đúng, có đối chứng
hai chiều trên bundle dựng từ đúng hai SHA**. 4/5 đột biến bị giết. Hai thứ còn lại: cổng
địa chỉ đọc **văn bản nguồn** nên một route bị comment vẫn xanh (đột biến M5 sống sót), và
ở **390px** — khung demo chính — tên món `Lẩu thái hải sản` bị cắt trên `goi-y-chia`, chỗ
mô tả PR ghi là sạch. Cả hai là **suggestion**, không phải blocker theo 5 loại của charter.

```
đo tại   aca7f68  (main)
sha này  ĐÃ ở main — #344 được merge lúc 13:18:23Z, KHÔNG có phán quyết QA nào trước đó
đối chứng fc8c59c (cha của thay đổi, trước PR)
```

## 0. Việc này bắt đầu như một lượt test PR và kết thúc như một lượt gác main

Lúc nhận việc, `gh pr list --state open` còn #344. Tôi checkout `ab32ba9`, chạy cổng
backend (3m42s) — và trong lúc đó #344 được merge. Nên báo cáo này là **hậu kiểm main**,
không phải cổng trước merge.

Một dấu hiệu đáng ghi: trên nhánh `ab32ba9` cổng mobile ra **756/757, 1 fail**. Ca đỏ là
`stacked-branch.test.mjs` → "nhánh này không mang lại file nào đã có nguyên vẹn trên
origin/main". Nó **đỏ vì đúng**: cả 5/5 file của PR lúc đó đã byte-identical với
`origin/main`. Đỏ vì đã merge, không phải vì hỏng. Trên `main` cùng ca đó xanh.

## 1. Cổng đầy đủ trên main — cây sạch

```
python3 -m pytest services/api/tests tests -q
  2524 passed, 547 skipped, 4857 subtests passed   0 fail

cd apps/mobile && npm test
  # tests 757 · # pass 757 · # fail 0 · # skipped 0
```

547 skipped là tầng `tests/postgres` — **chưa chạy**, không phải "không áp dụng". Lượt này
tôi không dựng Postgres; xem mục ô chưa quét.

## 2. Đối chứng hai chiều — lời khai chính của #344 ĐÚNG

Dựng bundle từ **hai SHA** rồi đi bộ bằng Chrome ghim, không đọc mã nguồn.

Trước khi tin số: xác minh máy chủ đang phục vụ **bundle của mình**, vì lượt đầu tôi đo
nhầm — cổng 8636/8637 đã bị lane khác chiếm, `python3 -m http.server` chết với
"Address already in use", còn `curl` vẫn trả 200 từ kẻ chiếm cổng và trình duyệt đọc được
"Directory listing for /tmp". Số đo lượt đó đã bị vứt.

```
hash trong đĩa   sau  : index-1b734498245d4e08a00c411848487da0.js
                 trước: index-770b581b7dd32654874471acbd059076.js
hash máy chủ trả sau  : index-1b73…   trước: index-770b…      → khớp, và hai bản KHÁC nhau
```

| bundle | `?man=nhan-dien` | `?man=goi-y-chia` |
|---|---|---|
| **trước** `fc8c59c` | 0/3 kim — rơi về màn đăng nhập ("Rủ Đi / Đăng ký với Google") | 0/2 kim — cùng màn đăng nhập |
| **sau** `aca7f68` | màn thật: "Kết quả nhận diện · Đã nhận diện 8 món · Tổng cộng 1.125.000đ" | 2/2 kim, ma trận 4 người thật |

Hai màn thật sự không mở được ở bản trước. Đây là điều kiện "đỏ trước" mà một bản vá phải
có mới chứng minh được gì.

**Một phép đo của tôi đã sai và tôi sửa nó, không phải sản phẩm sai.** `?man=nhan-dien` ra
0/3 kim ở cả hai khung, trông như tên món biến mất. Không phải: màn cho sửa tay nên tên món
nằm trong `<input value=...>`, mà `innerText` không trả về giá trị input. Đọc lại đúng cách:

```
24 input · 8 món · Lẩu thái hải sản/1/450.000 · Bò nhúng dấm/2/240.000 · Rau tổng hợp/2/90.000
Nem hải sản/3/120.000 · Cơm trắng/4/60.000 · Bia Sài Gòn/6/90.000 · Nước ép cam/2/50.000 · Kem dừa/1/25.000
                                                                              Σ = 1.125.000 ✓
```

Khớp `DEMO_ALLOCATIONS` tới từng đồng. Fixture của #344 tự nhất quán như PR khai.

## 3. Đột biến — 4/5 bị giết, 1 sống sót

Nền trước khi đột biến: 2 file cổng mới, **9/9 xanh**.

| # | Đột biến | Kỳ vọng | Kết quả |
|---|---|---|---|
| M1 | Đổi tên route `nhan-dien` → `nhan-dien-x`, `SO_DO` vẫn khai `nhan-dien` | đỏ | **GIẾT** 8 pass / 1 fail |
| M2 | Xoá hẳn dòng route `goi-y-chia` | đỏ | **GIẾT** 8 pass / 1 fail |
| M3 | `l6` `lineTotalVnd` 90000 → 96000 (gấp lại lệch) | đỏ | **GIẾT** 7 pass / 2 fail |
| M4 | Thay `allocations: DEMO_ALLOCATIONS` bằng bản viết tay lệch 1 đồng | đỏ | **GIẾT** 8 pass / 1 fail |
| M5 | **Comment dòng route thật, giữ nguyên chuỗi trong comment** | đỏ | **SỐNG — 9 pass / 0 fail** |

M1/M2 giết được đúng hai kiểu nói dối mà docstring của cổng tự nêu. M4 đáng chú ý: hôm nay
`DEMO_SPLIT_PREVIEW.allocations` **là tham chiếu** tới `DEMO_ALLOCATIONS`, nên assert đó
lặp thừa; nhưng nó vẫn có răng đúng với kịch bản nó đặt tên (ai đó thay tham chiếu bằng
bản chép tay).

### M5 — điểm mù: cổng địa chỉ đọc văn bản nguồn, không đo hành vi

`thamSoQuetCuaApp()` regex toàn văn `App.tsx`, nên chuỗi nằm trong **comment** vẫn tính là
route sống:

```js
// TAM TAT de go loi: if (manThamSo() === "goi-y-chia") return <XemGoiYChia />;
```

→ hàng `GoiYChia: { quet: "goi-y-chia" }` vẫn xanh, `# có địa chỉ quét: 5` vẫn in ra 5.

Hậu quả đã được chứng minh, không phải suy đoán: mục 2 cho thấy **không có route thì URL
rơi về màn đăng nhập**. Ghép lại — cổng có thể xanh trong khi màn không mở được.

Đây là suggestion, không phải blocker: cần một người comment route mới kích hoạt. Cách đóng
rẻ nhất là bỏ comment trước khi regex, hoặc tốt hơn là để một lượt đi bộ URL thật xác nhận
`quet` thay vì đọc nguồn.

## 4. Phát hiện mới — 390px cắt tên món trên `goi-y-chia`

Mô tả PR liệt kê `?man=goi-y-chia @390` chỉ có `text-occlusion x2` (đã bác bỏ đúng), và
`text-overflow` **chỉ ở 320px**. Đo lại bằng `scrollWidth` vs `clientWidth` trên bundle đã
ship:

| khung | phần tử | thừa | hộp | style |
|---|---|---|---|---|
| **390** | `Lẩu thái hải sản` (tên món, cột trái ma trận) | **7px** | 106px | `hidden` + `ellipsis` + `nowrap` |
| 320 | `Gợi ý chia theo người` (**tiêu đề màn**, không phải "một ô") | 24px | 179px | `hidden` + `ellipsis` + `nowrap` |

Ảnh 390px xác nhận bằng mắt: **`Lẩu thái hải …`**. Bảy món còn lại vừa hộp.

Không phải vỡ layout — cắt có chủ đích bằng ellipsis. Nhưng đây là màn **gán món cho
người**, và tên món bị cắt là thứ người dùng dựa vào để tick đúng dòng. Nó cũng nối tiếp
đúng mạch tôi báo lượt trước (`qa-tt-0035`: bản vá #342 làm 2 tên món nữa bị cắt, 3/9 → 5/9,
kèm dòng "màn hẹp hơn cắt nhiều hơn; **chưa quét**"). Ô "chưa quét" đó chính là màn này —
và nó chỉ đo được vì #344 cho nó một địa chỉ. Đó là #344 trả lãi, không phải #344 gây ra.

### Hai lời bác bỏ của PR — tôi kiểm lại và chúng ĐÚNG

`css-g5y9jx` mà PR gọi là vùng cuộn: ở 320px nó là **hàng 4 người**, `overflow-x: auto`,
nội dung 434px trong hộp 288px. `Đức Duy` (x 290–342) và `262.500đ` (x 280–352) nằm ngoài
khung 320 nhưng **cuộn tới được**. Là "ngoài màn trong vùng cuộn", không phải "bị che".
Tôi đến kết luận này bằng phương pháp khác (hình học + `overflow-x`), và nó trùng với PR.

Đáng ghi cho người sau: probe chỉ quét **phần tử lá** sẽ bỏ sót đúng ca này, vì vùng cuộn
có con. Probe đầu của tôi mắc lỗi đó.

## 5. Ô CHƯA QUÉT — phần quan trọng nhất

- `tests/postgres` **chưa chạy** lượt này (547 skipped). Không có `MOBILE_REQUIRE_POSTGRES_TESTS=1`.
- `npm run test:e2e` **chưa chạy** — không dựng uvicorn + Postgres.
- Hai màn chỉ đo ở **390 và 320**, chỉ **chủ đề sáng**, chỉ **web**. Chưa đo 1440, chưa đo
  chủ đề tối, **chưa đo trên điện thoại thật** — mà điện thoại mới là mục tiêu chính.
- `?man=nhan-dien` chưa được bấm thử: chưa sửa tên món, chưa xoá món, chưa kiểm bàn phím.
- `quet` vẫn là lời khai **yếu hơn** `do`: fixture đông cứng, không phải máy chủ. Không có
  gì ở đây nói hai màn này hành xử đúng trên luồng sống sau khi chụp bill thật.
- **Mã VietQR vẫn chưa được quét bằng app ngân hàng thật.** Chỉ leader đóng được ô này.
- Chưa có bằng chứng hành vi nào (ADR-0006). Bộ test xanh nói code làm đúng điều tác giả
  nghĩ, không nói người thật hiểu sản phẩm.

## 6. Phán quyết

**PASS** cho `main@aca7f68`. Cổng xanh, lời khai chính của #344 có đối chứng hai chiều,
fixture tự nhất quán, 4/5 đột biến bị giết.

Hai việc đề nghị xếp riêng cho **frontend**, cả hai là suggestion:

1. Cổng `moi-man-co-duong-do.test.mjs` bỏ comment trước khi regex (M5).
2. Cột tên món trên `goi-y-chia` ở 390px cắt `Lẩu thái hải sản` mất 7px.

Và một ghi chú quy trình cho **Lead**: #344 vào main lúc 13:18:23Z khi chưa có phán quyết
QA nào. Lượt này đóng ô đó lại bằng hậu kiểm, nhưng thứ tự đúng là ngược lại.
