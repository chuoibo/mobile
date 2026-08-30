# rd-qa-31 · PASS #172 — cổng đỏ được khi APP hỏng, không chỉ khi công cụ hỏng

`PASS`

**Lý do, viết trước phần chi tiết:** ba đột biến trong mô tả #172 đều bẻ *công cụ*
— chúng chứng minh công cụ tự gác được chính nó, chưa chứng minh nó gác được sản
phẩm. Tôi làm hai đột biến trên **mã sản phẩm** mà tác giả không làm, cả hai **đỏ**:
link `dia-diem=` im lặng không mở thẻ → `exit 1`, và nút "Tìm bằng AI" bấm được
nhưng không gửi gì → `exit 1`. Đây là cổng thật, không phải đồ trang trí. PR chạm
**0 dòng mã sản phẩm**, merge lên main hiện tại sạch, và cả hai cổng đầy đủ đều
xanh sau merge. Bản chụp không giấu chuyện F46 chưa vào được: chính công cụ in ra
`F46 KHÔNG nằm trong bản chụp này`.

Một chi tiết đã cũ, **không chặn merge**: PR nói F46 bị chặn vì "không có
`GET /contexts/{id}` trên máy chủ". Route đó **đã lên main** ở #175
(`services/api/app/api/routes/contexts.py:116`). Kết luận của công cụ vẫn đúng —
frontend chưa nối — nhưng lý do đã hết hạn, và việc nối tiếp giờ không còn bị chặn.

## Đo trên cái gì

```
đo tại   214c053  = pr172 (6f86f21) ⊕ main@2ec6680
6f86f21  là nhánh chưa merge, dựng trên main@d1ced77 — đứng SAU main 16 commit
2ec6680  là main lúc đo
```

Đo trên bản **merge**, không chỉ trên SHA của PR, vì main đã đi 16 commit kể từ
base — và #179 sửa **đúng cùng một file** `tools/tab-snapshots.mjs` mà PR này cũng
sửa. Git báo 0 xung đột văn bản; đó chính là hình dạng của một xung đột ngữ nghĩa,
nên nó phải được chạy chứ không được suy luận. Sau merge cả hai phía đều còn
nguyên: bước `len-plan` của #179 và chốt entry `import.meta.url` của #172.

## Cổng đã chạy, cây sạch

| Lệnh | Kết quả |
|---|---|
| `npm test` tại `6f86f21` | **498 pass / 0 fail / 0 skipped** — khớp đúng con số tác giả nêu |
| `npm test` tại bản merge `214c053` | **505 pass / 0 fail / 0 skipped** |
| `pytest services/api/tests tests -q` tại bản merge | **1273 passed, 285 skipped**, 4596 subtest |
| `node tools/tuong-tac-snapshots.mjs` tại `6f86f21` | `exit 0`, ghi đủ 3 file |
| `node tools/tuong-tac-snapshots.mjs` tại bản merge | `exit 0`, ghi đủ 3 file, cùng kết luận |

285 ca skip là tầng `tests/postgres` thiếu DB — PR này chạm 0 dòng backend, nên
tầng đó không nằm trong phạm vi phán quyết. Nói ra để dấu xanh không bị đọc rộng
hơn thứ nó phủ.

## Phần quan trọng nhất: cổng đỏ được khi SẢN PHẨM hỏng

Ba đột biến trong mô tả PR nhắm vào công cụ (bỏ `nut.click()`, bỏ nhánh nhận diện,
làm yếu needle). Chúng cần thiết nhưng chưa đủ: một cổng chỉ đỏ khi bạn bẻ chính
nó thì nó gác chính nó, không gác sản phẩm. Hai đột biến dưới đây bẻ **app**, và
được làm sau khi commit bản merge nên khôi phục về HEAD là sạch.

| Đột biến trên mã sản phẩm | Mô phỏng lỗi thật nào | Kết quả |
|---|---|---|
| `lien-ket.ts:136` — `diaDiem` luôn `null` | link `dia-diem=` im lặng mở lưới danh mục thay vì thẻ chi tiết, đúng "màn sai dưới tên file đúng" | **ĐỎ** `exit 1`, `timed out waiting for "Khoảng giá"` |
| `KhamPha.tsx` — `timNgay` trả về sớm | nút bấm được nhưng không gửi gì, đúng "kết cục thứ ba" công cụ tự nhận là bắt | **ĐỎ** `exit 1`, `tim-kiem-thay: timed out waiting for "Nướng Ngói Ba Cây Thông"` |

Đột biến thứ nhất là cái đáng giá nhất: `dia-diem.html` mà chụp nhầm lưới danh mục
thì vẫn render đẹp, vẫn ghi ra file, vẫn `exit 0`. Nó không.

Sau khi khôi phục: `git status` không còn sửa đổi nào trên file theo dõi.

## Số `imp detect` của tác giả tái lập đúng

```
tim-kiem-thay          4 anti-patterns found / exit 2
tim-kiem-khong-thay    4 anti-patterns found / exit 2
dia-diem               4 anti-patterns found / exit 2
```

Đúng 4 finding tác giả nêu, và đúng 4 cái đã phân loại là dương tính giả ở #168:
`cramped-padding` ×2 trên `css-g5y9jx` (class `<View>` dùng chung toàn app),
`clipped-overflow-container` trên `body` (hiện vật của phép chụp DOM), và
`overused-font: roboto` (stack mặc định react-native-web). **Không finding mới nào**
riêng của ba màn này — không contrast, không occlusion.

Ở đây quét theo **FILE**, không theo URL, nên bẫy "preflight nói dối, thiếu Chrome
trả `[]` + `exit 0`" không áp dụng. Và `exit 2` với 4 finding **tự nó** là bằng
chứng máy quét còn sống — mạnh hơn một canary, vì canary chỉ chứng minh gián tiếp
điều mà một kết quả khác 0 chứng minh trực tiếp.

Một bẫy tôi dính và ghi lại: `imp` **không có trên PATH** trong worktree này. Gọi
trần `imp detect` in `No such file or directory` mà shell vẫn trả `EXIT=0` — trông
y hệt một lượt quét sạch. Đường dẫn đúng:
`/home/lakiet/.claude/skills/impeccable-pipeline/scripts/imp`.

## Ba ghi chú, không cái nào chặn merge

1. **Lý do nêu cho blocker F46 đã hết hạn.** PR viết "không có `GET /contexts/{id}`
   trên máy chủ để đọc tên nhóm". #175 đã đưa route đó lên main
   (`contexts.py:116`). Kết luận không đổi — công cụ vẫn in `TU-CHOI: chưa có nhóm`
   vì `VoTab` chưa chuyền nhóm cho `KhamPha` — nhưng nửa còn lại giờ **không còn bị
   chặn**, và người nhận việc tiếp cần biết điều đó.

2. **Comment của cổng #179 thành sai sau PR này.** `tests/quet-du-tab.test.mjs` giải
   thích nó đọc source bằng text vì "`tab-snapshots.mjs` chạy `main()` của chính nó
   khi được nạp". PR này thêm đúng chốt entry gỡ bỏ lý do đó. Cổng vẫn chạy đúng và
   vẫn xanh; chỉ có lời giải thích là dẫn người đọc sai. Suggestion, không phải blocker.

3. **Chưa cổng nào giữ ba màn mới.** #179 tồn tại vì "màn thiếu và màn sạch cùng một
   dấu xanh", nhưng nó chỉ đối chiếu `tabs.ts` với `tab-snapshots.mjs`. Ba màn tương
   tác không có sổ đăng ký tương đương để đối chiếu, nên chưa có gì bắt được nếu
   một trạng thái F12 mới ra đời rồi không ai chụp. Cùng một lỗ hổng, dịch sang một
   tầng. Ghi lại làm việc kế, không chặn PR này.

## Ô CHƯA quét — đọc phần này trước khi đọc chữ PASS

- **Thẻ check-in thật của F46** vẫn chưa URL nào tới được. Công cụ tự khai, tôi
  xác nhận lại bằng chính đầu ra của nó.
- **Chỉ 390×844, chỉ chủ đề sáng.** Không có ma trận sáng/tối, không khung máy khác.
- **Ba trạng thái lỗi của F12** (`bi-tu-choi`, `qua-nhieu-lan`, `chua-co-endpoint`)
  có state trong code, chưa lần nào được render.
- **Không ai bấm bằng tay ba màn này.** Bản chụp chứng minh trang render được và
  không có anti-pattern mới; nó không chứng minh người thật hiểu được màn hình.
- **Mã QR chưa được quét bằng app ngân hàng thật.** Ô này vẫn mở, và không agent
  nào đóng được nó.
- **Tầng `tests/postgres`** không chạy trong lượt này (285 skip). Ngoài phạm vi PR
  nhưng nói ra để không ai đọc dấu xanh rộng hơn thứ nó phủ.

## Phân loại theo 5 loại blocker của charter

Không có blocker nào thuộc 5 loại. Không sai tiền (PR chạm 0 dòng mã tiền), không
vấn đề quyền riêng tư (bản chụp dùng dữ liệu tổng hợp, không dữ liệu thật), tái lập
được toàn bộ, không vi phạm cổng. Ba ghi chú ở trên là suggestion và việc kế tiếp.
