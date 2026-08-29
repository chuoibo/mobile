# rd-qa-32 · PASS #184 — cảnh báo cắt bớt đi hết đường từ máy chủ tới mắt người dùng

```
verdict           PASS
protocol_version  v1
PR                #184  frontend/bug-223917-noi-bi-cat
đo tại            aa622f4076285426f5b02678a637fb83d6c6aac5
sha này           nhánh chưa merge, dựng thẳng trên origin/main@2ec6680
main lúc đo       082fdcf (#185) — chạm 0 file apps/mobile, không có xung đột ngữ nghĩa
cây đo            /tmp/qa32-pr184 (worktree sạch, detached tại aa622f4)
```

## Lý do PASS (đọc phần này trước)

Ba câu hỏi quyết định PR này, cả ba đều đã trả lời bằng phép đo của QA chứ không
bằng mô tả PR:

1. **Test có đỏ được ở bản cũ không?** Có. Tôi tự hoàn nguyên ba file nguồn về
   `2ec6680` rồi chạy lại đúng file test đó: **22 pass / 7 FAIL**. Bảy ca đỏ trải
   đúng ba tầng — parser, thẻ chat, màn chi tiết — chứ không dồn vào một tầng.
2. **Máy chủ có thật sự phát ra tên trường mà client đọc không?** Có. Tôi gọi
   thẳng `ground_card` của main, lấy payload **thật**, đưa nguyên bytes vào parser
   **thật** của client. Không đoán theo mô tả PR.
3. **Tính năng có tới được người dùng thật không, hay chết ở tầng giữa?** Tới
   được. `parseMessage` truyền `card` nguyên vẹn (`card: m.card ?? null`), không
   whitelist, không nắn lại — nên trường mới không bị tầng wire ăn mất.

Câu 3 là câu tôi lo nhất khi nhận PR này, vì repo này đã có tiền lệ "route không
ai gọi thì tính năng chưa tồn tại". Ở đây đường đi liền mạch và tôi đã đi hết.

## Đối chứng: đỏ trước, xanh sau (tự chạy, không lấy số của PR)

Hoàn nguyên `apps/mobile/src/screens/chat/` về `2ec6680`, **giữ nguyên file test**:

```
npx tsc -p tsconfig.test.json   -> exit 0   (không đỏ typecheck, nên 7 ca đỏ là đỏ THẬT)
node --test tests/lich-trinh-bi-cat.test.mjs
   tests 29 | pass 22 | fail 7
```

Bảy ca đỏ, theo tầng:

| # | Ca | Tầng |
|---|---|---|
| 1 | thẻ lịch trình bị cắt mang theo số chặng đã mất | parser |
| 3 | thẻ địa điểm bị cắt mang theo số chỗ đã mất | parser |
| 5 | keHoachTuCard giữ nguyên số chặng bị cắt | parser |
| 22 | thẻ lịch trình bị cắt nói ra số chặng còn thiếu | thẻ chat |
| 24 | thẻ địa điểm bị cắt nói ra số chỗ còn thiếu | thẻ chat |
| 26 | câu cảnh báo nói rõ phần bị mất không nằm sau nút xem chi tiết | thẻ chat |
| 27 | **màn chi tiết của kế hoạch bị cắt cũng nói ra** | màn chi tiết |

Ca 27 là ca đáng giá nhất và nó **đỏ riêng**. Đây đúng là tầng dễ hở nhất: người
ta bấm "Xem chi tiết" *để đọc cả kế hoạch*, nên im lặng ở đó là chính con bug,
chỉ sâu hơn một cú bấm. Nó không núp sau ca của tấm thẻ.

Khôi phục bản sửa: **29 pass / 0 fail**. Đỏ-trước/xanh-sau khép kín.

## Đối chứng xuyên hai lane: bytes thật của máy chủ, parser thật của client

Không đọc mô tả PR. Gọi `ground_card` trên main, dump JSON, nạp vào
`dist-test/screens/chat/ke-hoach.js`:

| Vào (máy chủ) | Payload máy chủ trả | Màn hình nói |
|---|---|---|
| 8 chặng | `keys=[omitted_stop_count, stops, title]` | "Kế hoạch bị rút gọn, còn 2 chặng nữa chưa được gửi. …" |
| 3 chặng | `keys=[stops, title]` | **im lặng** |
| 8 chỗ | `keys=[intro, omitted_place_count, places]` | "Danh sách bị rút gọn, còn 3 chỗ nữa chưa được gửi. …" |
| 2 chỗ | `keys=[intro, places]` | **im lặng** |

Hai vế đều cần. Chỉ có vế "có cắt thì nói" thì một hiện thực báo lung tung cũng
xanh y hệt.

Hợp đồng khớp ở cả hai đầu: máy chủ `if omitted:` chỉ gắn key khi thực sự cắt
(`companion.py:144,191`); client nhận thiếu key thành `undefined` chứ không phải
`0`. Phân biệt được "không cắt gì" với "mất hai chặng" — đúng thứ một số `0` sẽ
xoá mất.

## Thăm dò của QA: một khẳng định PR đưa ra mà PR không test

PR nói *"Lời nhắn nằm TRÊN nội dung nó nói về, ở cả hai màn"*. Không ca nào assert
vị trí. Tôi tự đo bằng chỉ số ký tự trên markup render từ payload thật:

```
THẺ CHAT       cảnh báo@848    chặng-đầu@1333   -> TRÊN ✓
MÀN CHI TIẾT   cảnh báo@1451   chặng-đầu@2778   -> TRÊN ✓
```

Khẳng định đúng ở cả hai màn. (Lượt đo đầu của tôi ra `-1/-1` vì tôi tự truyền sai
tên prop `the` thay vì `card` — lỗi của phép đo, không phải của sản phẩm. Ghi ra
đây vì một con số `-1` không kiểm lại thì thành một phiếu lỗi giả.)

**Đề nghị (suggestion, KHÔNG phải blocker):** vị trí đang đúng nhưng không có
cổng nào giữ. Một lần sắp xếp lại JSX sẽ đẩy câu cảnh báo xuống dưới sáu chặng mà
29 ca vẫn xanh. Thêm một assert so `indexOf` là đủ.

## Chất lượng bộ test (soi, không gật)

- Render thật qua `renderToStaticMarkup` của react-native-web, không phải chỉ gọi
  hàm parser. Một trường parse đúng mà không component nào vẽ ra thì người dùng
  vẫn không thấy gì.
- Có **cả vế phủ định**: thẻ ngắn phải im. Không có vế này thì "báo đúng lúc" và
  "báo lung tung" xanh như nhau.
- Bảng giá trị xấu phủ 8 trường hợp: `0, -1, 2.5, "2", null, true, NaN, Infinity`
  — mỗi cái đều kiểm cả parser lẫn markup.

## Cổng đã chạy

| Lệnh | Kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` (nền main) | **1273 passed, 285 skipped, 4596 subtests** |
| `cd apps/mobile && npm test` (tại aa622f4, gồm bước `expo export`) | **534/534 pass, 0 fail** |
| `npx tsc --noEmit` | exit 0 |
| `python3 scripts/repo_guard.py range 2ec6680 aa622f4` | passed, 635 file scan |

`npm test` chạy `build:check` (`expo export --clear`) trước khi test, nên 534 ca
này cũng chứng minh bundle web dựng được, không chỉ typecheck sạch.

## Ô CHƯA QUÉT — phần quan trọng nhất

- **`imp detect` trên URL: tôi KHÔNG chạy lại.** PR khai canary xấu 5 finding/exit 2,
  canary sạch 0/exit 0, trang thật 0/exit 0 ở hai khung nhìn. Bộ canary hai đầu là
  đúng luật, nhưng đây là **số của tác giả, không phải của tôi**. Chưa độc lập.
- **Tương phản 5.18:1 / 4.92:1**: số của PR, tôi chưa đo lại.
- **Chưa nhìn bằng mắt trên thiết bị thật.** Câu cảnh báo có được người thật ĐỌC và
  HIỂU không thì không assert nào trả lời. Markup có chuỗi ≠ người dùng nhận ra.
- **Tầng `tests/postgres`: không chạy.** PR chạm 0 file backend nên ngoài phạm vi,
  không phải bỏ sót.
- **`npm run test:e2e` (lát cắt dọc thật): không chạy.** PR không đụng route,
  request hay header. Đường AI-card không nằm trên lát cắt dọc chia tiền.
- **Đường này chỉ chạy khi model trả quá `MAX_STOPS`.** Chính comment máy chủ nói
  đây là fallback chứ không phải đường thường. Là phòng thủ đúng, nhưng nghĩa là
  người dùng thật có thể **chưa bao giờ** thấy câu này. Không phải lỗi của PR.
- **Mã QR quét bằng app ngân hàng thật**: vẫn chưa ai làm, không liên quan PR này.

## Blocker

Không có. Không rơi vào bất kỳ loại nào trong năm loại của charter: không đụng
tiền, không đụng quyền riêng tư, không vi phạm cổng, tái lập được toàn bộ.

Một suggestion duy nhất (vị trí cảnh báo chưa có cổng giữ) — theo charter, đó là
suggestion, không chặn merge.
