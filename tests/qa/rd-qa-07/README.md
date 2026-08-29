# rd-qa-07 · Màn Cá nhân và con số nó nói là "đọc lại từ sổ"

Gác thứ mới nhất trên `main` mà chưa ai gác: route `/people/{id}/finance` và màn
**Cá nhân** (#96, `rd-do-fe-09`). Ba PR gần nhất — #95, #96, #97 — đều được merge
bằng APPROVE của Lead, không có phán quyết QA nào.

Đo trên `main @ aaefbfa`, PostgreSQL thật, API thật, trình duyệt thật.

## Vì sao chỗ này đáng đo

`finance.py` tự viết hợp đồng của nó:

> Every figure this route answers with is recomputed from the ledger on the
> request that asks for it, which is invariant 3 stated as an endpoint.

Đó là bất biến 3 phát biểu thành một endpoint. Nhưng **toàn bộ tầng PostgreSQL bị
skip trong cổng mặc định** (`856 passed, 148 skipped`), nên 14 ca tiền của màn này
chưa ai từng thấy chúng đỏ. Một luật tiền chỉ được ghi trong comment thì không có
gì cưỡng chế nó cả.

## Ba script

| Script | Hỏi gì | Kết quả trên `aaefbfa` |
|---|---|---|
| `01-ca-nhan-doi-chung.mjs` | Số trên MÀN có đúng là số API trả về không? | PASS |
| `02-a11y-ca-nhan.mjs` | axe WCAG 2.2 A/AA, sau khi chứng minh axe còn sống | **FAIL — 2 lỗi thật** |
| `03-mutation-gate.py` | Luật tiền nào thật sự được test bảo vệ? | **FAIL — 3 luật không ai gác** |

```bash
docker compose up -d postgres
python3 tests/qa/rd-qa-07/03-mutation-gate.py      # không cần trình duyệt

# hai script kia cần API + bản web export:
cd services/api && alembic upgrade head
MOBILE_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile' \
  python3 -m uvicorn app.api.main:app --host 127.0.0.1 --port 8640 &
cd apps/mobile && EXPO_PUBLIC_API_URL=http://127.0.0.1:8640 \
  npx expo export --platform web --output-dir /tmp/rdqa07-web --clear
cd /tmp/rdqa07-web && python3 -m http.server 8641 --bind 127.0.0.1 &
cd tests/qa/rd-qa-07 && node 01-ca-nhan-doi-chung.mjs && node 02-a11y-ca-nhan.mjs
```

## Đọc `03-mutation-gate.py` ngược với thói quen

`KILLED` là **tốt** — có test bắt được. `SURVIVED` là **xấu** — cả bộ test xanh
trong khi luật tiền đã bị lật ngược.

Ba mutant đầu là **control**: chúng phải chết. Chúng ở đó để chứng minh bộ test và
chính cái harness này còn sống. Control nào không chết thì mọi verdict `SURVIVED`
trong cùng lượt chạy **vô giá trị** — hỏng môi trường, không phải hỏng code. Thứ tự
đó là toàn bộ điểm mấu chốt: `imp detect` trên repo này từng trả `[] + exit 0` chỉ
vì thiếu trình duyệt, và một detector chưa được thấy phản ứng thì chưa đáng tin.

Harness phục hồi file bằng bản sao ở `/tmp`, **không** bằng `git checkout` —
checkout đưa về HEAD và sẽ xoá luôn thay đổi chưa commit trong cùng file đó.

## Cạm bẫy đã dính trong lượt này

1. **Bắt nhầm một vụ rò rỉ không có thật.** Phép kiểm "màn của Minh không được in số
   của Trang" đỏ ở `550.000đ` — nhưng đó là *tiền đã thanh toán của chính Minh*,
   trùng số với *khoản nợ của Trang* thuần tuý do trùng hợp số học. Đã sửa thành chỉ
   đối chiếu những số **chỉ Trang mới có**, và khi không có số nào như vậy thì script
   in `skip` chứ không in `ok`. Một ô chưa quét phải trông như chưa quét.
2. **Cổng 8099 là container của lane khác, code 7 tiếng trước.** Mọi thứ ở đây chạy
   trên API riêng ở 8640 và đã kiểm `openapi.json` có `/people/{person_id}/finance`
   trước khi tin bất kỳ số nào.
3. **`AxeBuilder` từ chối `browser.newPage()`**, phải `browser.newContext()` rồi
   `context.newPage()`. Bỏ qua thì script chết chứ không âm thầm quét rỗng.
4. **`X-Actor-Contexts` mới quyết định `is_group_member`, không phải bảng trong DB.**
   Thiếu header thì `confirm` trả 403 `is_group_member` dù người đó đã là thành viên
   thật. Và `acknowledge_as_advancer: true` mở thêm cổng thứ hai đòi role `advancer`.
5. **Bộ lỗi axe không hoàn toàn tất định.** `aria-required-children` (critical) ra
   ở mọi lượt và mọi tab; lỗi thứ hai lúc là `scrollable-region-focusable`, lúc là
   `aria-prohibited-attr`, tuỳ thời điểm chụp. Cả hai đều thật; đừng đọc một lượt
   chạy thành danh sách đầy đủ.

## Ô CHƯA quét

- Mã QR quét bằng app ngân hàng thật — vẫn chỉ leader trả lời được (ADR-0010 mục 8).
- Màn Cá nhân trên **thiết bị thật**; ở đây là Chromium 390×844, không phải iOS/Android.
- Trình đọc màn hình thật (VoiceOver/TalkBack). axe không thay được.
- WCAG 2.4.11 (focus bị che), 2.5.7 (kéo thả), 2.5.8 (kích thước vùng chạm) — axe
  không có rule tự động, hoặc chỉ phủ một phần.
- `movements` rỗng trong lượt đo này (chưa có receipt nào được xác nhận), nên phần
  danh sách giao dịch của màn **chưa được đo có dữ liệu**.
- Chế độ tối, 320px, và cỡ chữ 200%.
