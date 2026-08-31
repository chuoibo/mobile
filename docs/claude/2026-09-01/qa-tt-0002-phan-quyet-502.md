# FAIL #502 — bản sửa đúng, nhưng nó dạy máy lái GỬI HAI LẦN một cú bấm đã ăn

- **commit đo:** `66c1c38d05fff1f7cd9febc95fd83eba82c967fb` (nhánh `frontend/bam-truot-thi-bam-lai`)
- **nền:** nhánh CHƯA merge, cắt từ `origin/main@e41bcdc`; đối chứng "trước" chạy trên `origin/main@f8fbf49`
- **protocol_version:** `n/a`
- **verdict:** `REQUEST_CHANGES`
- **blocker còn mở:** 1 (loại 4 — hỏng tính hợp lệ thí nghiệm)

## Lý do, trước mọi chi tiết

Phần lõi của PR này **đúng và đã được đối chứng**: tôi tái lập được đỏ-trước /
xanh-sau của chính các bạn, không sai một con số (0 pass ở driver cũ → 3 pass ở
driver mới).

Cái chặn là một hệ quả mà ba hàng đối chứng của PR **không chạm tới**. Lập luận an
toàn viết trong `quet-man-sau-tap.mjs` và nhắc lại ở mô tả PR:

> *"If the press landed, the screen moved on and the finder no longer matches, so
> nothing is pressed twice — that is what keeps this from double-submitting a save."*
> — và ở mô tả PR: *"Nút đã biến mất nghĩa là cú bấm đã ăn, nên không có chuyện gửi
> 'Lưu' hai lần."*

Câu đó **sai**, và sai ngay ở ca tốt nhất của chính nó. Nút chỉ biến mất **LÚC** màn
đích tới. Cửa sổ đang-bay TRƯỚC đó thì nút vẫn nằm nguyên trên màn và
`bamDuoc()` vẫn trả về nó — hàm ấy chỉ kiểm `disabled` và `aria-disabled`, không
kiểm còn-gắn-DOM, không kiểm còn-nhìn-thấy. Mà cửa sổ đang-bay chính là thứ dài quá
`NHIP_BAM_LAI = 2500ms`.

Nói ngắn: **cú bấm càng chậm thì càng bị bấm lại — trong khi chậm chính là ca mà
bản sửa này sinh ra để phục vụ.**

## Đo được, không phải lập luận

`tests/qa/qa-tt-0002-doi-chung-502/nut-song-nhung-man-cham.mjs`. Trang `<button>`
thật, `addEventListener("click")` thật. Handler tự đếm số lần nó **thật sự chạy**
(`window.__dem`) — đo cú gửi, không đo lời khai của máy lái về cú gửi.

| hàng | màn đích tới sau | nút | driver `f8fbf49` (TRƯỚC) | driver `66c1c38` (PR) |
|---|---|---|---|---|
| A. CHẬM | 4000ms | ở lại | **1 lần gửi** | **2 lần gửi** (cách nhau 2533ms) |
| B. NHANH | 200ms | ở lại | 1 lần gửi | 1 lần gửi |
| C. CHẬM + nút TỰ GỠ khi màn tới | 4000ms | tự gỡ | **1 lần gửi** | **2 lần gửi** (cách nhau 2533ms) |

```
TRƯỚC (origin/main): KHONG tim thay cu gui thua      exit 0
SAU   (#502 66c1c38): CO 2/3 hang gui THUA           exit 1
```

Hàng C là hàng quan trọng: nó dựng **đúng hình dạng mà lập luận của PR cho là an
toàn** (nút biến mất khi điều hướng) và vẫn gửi hai lần. Hàng B là đối chứng âm —
nó phân biệt "máy lái luôn bấm đúp" với "máy lái bấm đúp khi màn chậm"; kết quả là
vế thứ hai.

Đây là **hồi quy do PR này sinh ra**, không phải lỗi có sẵn: cùng một probe, cùng
một máy, driver trên `main` ra 3/3 một-lần-gửi.

## Vì sao hàng NÚT TỐT của PR không bắt được

Cả ba trang trong `bam-truot-thi-bam-lai.test.mjs` đặt chữ đích **ngay lập tức**
trong handler, nên `cho()` giải quyết ở vòng poll đầu và **không hàng nào chạm tới
mốc 2500ms**. Vậy `bam_lai === []` ở hàng NÚT TỐT chứng minh *"màn đích tới trong
2500ms"*, chứ không chứng minh *"bấm trúng thì không bấm lại"* — là điều nó được
ghi chú là đang gác ("Đây là ca chặn 'Lưu' bị gửi hai lần").

Một hàng đối chứng đọc như đang gác một tính chất, mà thật ra gác một tính chất
khác dễ hơn nhiều, là kiểu lỗ hổng đắt nhất: nó làm người đọc sau **ngừng kiểm**.

## Với tới đâu

Chính `quet-man-sau-tap.mjs` chứa những bước bấm-rồi-chờ trên nút KHÔNG idempotent:

```js
{ bamChu: "Chia tiền" },            { cho: "Đúng rồi, ghi vào sổ" }
{ bamChu: "Đúng rồi, ghi vào sổ" }, { cho: "Phát đợt thu" }
{ bamChu: "Phát đợt thu" },         { cho: "Quét để thanh toán", ms: 30000 }
{ bamChu: "Lưu món của tôi" },      { cho: "Gợi ý chia theo người" }
```

Bước `Phát đợt thu` đáng chú ý nhất: ngân sách `ms: 30000` là lời khai của chính
tác giả rằng bước này **được trông đợi là chậm** — tức > 2500ms là ca thường, nên
bấm lại sẽ nổ trên đường hạnh phúc chứ không phải ca hiếm.

**Nói rõ giới hạn của phát hiện này, để không ai đọc quá lên:** các công cụ quét
cài **API stub** vào trang (`quet-man-sau-tap.mjs:774-787`), không bắn vào máy chủ
thật. Nên đây **không** phải "tiền bị ghi sổ hai lần" và **không** phải blocker
loại 2. Thiệt hại là **tính hợp lệ của phép đo** (blocker loại 4): một nút toggle
(`Mở bình chọn` / `Đóng bình chọn`) bị bấm hai lần sẽ **tự quay về trạng thái cũ**,
và công cụ quét sẽ kết luận cái nút không hoạt động — một finding giả, sinh ra bởi
chính dụng cụ đo.

Và nó **im lặng với mọi người tiêu thụ**: PR tự ghi rằng 21 công cụ đọc `window.__lai`
chỉ đọc `xong`/`loi`. `bam_lai` có ghi lại, nhưng không cổng nào đọc nó — nên một
lượt quét bị nhiễm vẫn in xanh.

## Tiêu chí gỡ chặn

Một trong hai, cộng với điều thứ ba:

1. **Điều kiện bấm lại phải thật sự phân biệt được "cú bấm đã ăn"** — chứ không suy
   ra từ "nút còn đó". Tiêu chí đo được: một hàng mà cú bấm **ăn** và màn đích tới
   sau > `NHIP_BAM_LAI` phải cho handler chạy **đúng 1 lần**. Probe ở trên là hàng
   đó; dùng lại hay tự viết đều được.
2. **Hoặc** bấm lại thành **opt-in theo bước**, mặc định TẮT, để không bước không
   idempotent nào (`Đúng rồi, ghi vào sổ`, `Phát đợt thu`, `Lưu món của tôi`,
   `Mở/Đóng bình chọn`) bị bấm lại — kèm một ca chứng minh bước không opt-in không
   bao giờ bấm lại.
3. **Sửa câu chữ**: comment trong code và mô tả PR đang khẳng định một bất biến mà
   phép đo bác bỏ. Comment giải thích sai giữ lỗi sống lâu hơn chính lỗi đó.

## Cái tôi đã kiểm và thấy ĐÚNG

- **Đỏ-trước / xanh-sau của các bạn, tái lập khít.** `bam-truot-thi-bam-lai.test.mjs`
  trên driver `e41bcdc`: `tests 3 | pass 0 | fail 3`. Trên driver `66c1c38`:
  `tests 3 | pass 3 | fail 0`. Chỉ đổi một file driver, không đổi ca test.
- **Hàng NÚT CHẾT là đối chứng âm thật.** Bấm lại không biến lỗi thật thành xanh —
  tôi xác nhận nó vẫn đỏ, và đỏ vì `het gio cho`, đúng lý do.
- **Chẩn đoán "cú bấm bị rơi" của các bạn mạnh hơn chẩn đoán cũ của tôi.** Lượt gác
  #491 tôi từng quy flake này cho ngân sách cứng 20000ms (đo `duration_ms: 21369`).
  Số đo per-bước mà PR này thêm vào cho thấy mọi bước đều < 505ms rồi màn đích không
  bao giờ tới — `21369` chỉ là 20s chờ cộng overhead, không phải bằng chứng máy chậm.
  Chẩn đoán của tôi sai; của các bạn đúng.
- **Thay đổi `__lai` là cộng thêm, không phá.** `ms` / `cho_ms` / `bam_lai` /
  `luc_loi` là field mới; không cổng nào đổi phán quyết vì chúng.
- **Flake khác mà PR tự khai** (`gate-web-khong-doc-ban-cu` ca C): 3 lượt `npm test`
  của tôi **không** tái lập được. Khai báo đó trung thực và tôi không tính vào PR này.

## Cổng đã chạy

| lệnh | kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` @66c1c38 | **2888 passed, 614 skipped**, 5272 subtests |
| `cd apps/mobile && npm test` @66c1c38 — 3 lượt | **1042 pass / 0 fail / 27 suites** × 3 |
| `python3 scripts/repo_guard.py staged` | `Repo guard passed` |
| `pytest tests/test_qa_evidence_runs_on_another_machine.py tests/test_qa_scripts_are_ruff_formatted.py` | **46 passed** |

## Ô CHƯA quét — đọc phần này trước khi dùng con số ở trên

- **Flake gốc có thật sự hết chưa: CHƯA chứng minh.** 3 lượt `npm test` xanh. Với
  tỉ lệ đỏ ~1/4 mà tôi đo ở lượt gác #491, 3 lượt xanh liên tiếp còn ~42% xảy ra
  **kể cả khi chưa sửa gì**. Cái làm tôi tin bản sửa là ba hàng ép-rơi đã đối chứng,
  **không phải** 3 lượt xanh này. Muốn con số về flake thì phải chạy ≥ 20 lượt.
- **Không quét:** `tests/postgres` (không đặt `MOBILE_TEST_DATABASE_URL` — 614
  skipped ở trên gồm cả tầng này), `npm run test:e2e` (không dựng uvicorn +
  Postgres), trang khách, ma trận thiết bị/chủ đề.
- **Chưa đo:** hành vi bấm lại khi có HAI bước bấm liên tiếp không xen `cho`
  (`lamLaiCuoi` bị ghi đè) — probe của tôi chỉ dựng một cặp bấm→chờ.
- **Mã QR chưa được quét bằng app ngân hàng thật** — vẫn nguyên trong ô chưa quét,
  chỉ leader đóng được.

## Tái lập

```bash
git checkout frontend/bam-truot-thi-bam-lai   # 66c1c38
node tests/qa/qa-tt-0002-doi-chung-502/nut-song-nhung-man-cham.mjs   # exit 1: 2/3 hàng gửi thừa

git checkout main                              # f8fbf49
node tests/qa/qa-tt-0002-doi-chung-502/nut-song-nhung-man-cham.mjs   # exit 0: không hàng nào gửi thừa
```

Probe không cần server, không cần Postgres, không cần bundle expo — chỉ cần Chrome.
Nó xanh trên `main` và đỏ trên `#502`, nên nó là máy đo có hướng, không phải một
cái luôn-đỏ.
