# Đêm nay đã đo được gì, và chưa đo được gì

- lượt: `qa3-093210`
- neo: `main` tại `0c04cb7`, **tree `09f5062`** — mọi con số ở cột 1 chạy trên đúng tree này
  trừ khi hàng đó tự khai SHA khác
- protocol_version: v1
- verdict: **FYI — bản đồ phạm vi hiểu biết, không sửa code, không phán quyết PR nào**
- skill: `ai-qa-review` (batch audit: soi từng khẳng định xem nó có phép đo chạy lại được không)

## Luật của trang này

Một dòng được nằm ở **cột 1** khi và chỉ khi nó có (a) một lệnh người khác dán vào chạy lại
được, và (b) một SHA/tree phép đo đó đã chạy trên. Thiếu một trong hai → **cột 2**, dù ta tin
nó đến mấy.

Đo xong rồi tôi phải thêm **trục thứ ba**, vì hai trục trên chưa đủ: **đo ở CÂY NÀO.** Một con
số đo tại một SHA cũ vẫn là phép đo thật, nhưng nó **có hạn dùng** — main đêm nay nhích 10
commit kể từ lúc `7/11` được đo. Nên cột 1 tách làm hai khối: đo **trong lượt này**, và đo ở
**cây cũ, chưa ai đo lại**.

---

## CỘT 1A — ĐÃ ĐO ĐƯỢC, chạy lại trong lượt này trên tree `09f5062`

| # | Khẳng định | Lệnh chạy lại | Số ra thật |
|---|---|---|---|
| 1 | Bộ test Python (domain + API fake repo + repo guard) xanh | `python3 -m pytest services/api/tests tests -q` | **2817 pass · 580 skip · 5049 subtest** · 354.88s |
| 2 | Bộ test mobile xanh | `cd apps/mobile && npm test` | **1008 pass · 0 fail · 24 suite** · 23.9s |
| 3 | Cây không mang hiện vật cấm | `python3 scripts/repo_guard.py tree HEAD` | rc=0, **1297 file scan** |
| 4 | Mọi màn `App.tsx` mount đều có câu trả lời "cái gì đo màn này" | `cd apps/mobile && node --test tests/moi-man-co-duong-do.test.mjs` | **15 mount / 0 probe / 9 quét / 6 chưa đo** · 4/4 pass |
| 5 | `47` là một **lựa chọn cách đếm**, không phải phép đo | `grep -cE '^#+ F[0-9]' feature_list.md` và 4 biến thể (§1 của #446) | `"47"` xuất hiện **0** lần · mọi mức=**47** · h2=**35** · h1=**12** · EPIC=**15** |
| 6 | Bộ mockup có 21 mục và 21 file ảnh | `find …/RuDi_Mobile_Product_Mockups -name '*.png' \| wc -l` | **21 file** · index khai **12 READY / 9 NEEDS UPDATE** |
| 7 | Phán quyết hero-walk trên đĩa **không** nói về cây này | `make hero-walk-status` | **exit 2** — "lượt đi bộ chạy ở client `cd1e97a`, KHÔNG nằm trong HEAD" |
| 8 | Cạnh 11 có người đo **nửa máy chủ** | `grep -n 'CA NHAN' tests/qa/qa-tt-0031/di-bo-hero-tren-demo.mjs` | dòng **323**: chặng `"CA NHAN: so du cap nhat (GET /contexts/{id}/balances)"` |
| 9 | Con walk demo đó **không có trình duyệt** | `grep -nE '^import' …/di-bo-hero-tren-demo.mjs` | 4 import, không có `chrome-cdp`; gọi qua `dist-test/api.js` |
| 10 | 5 lane có việc **chưa đẩy**, không ai ngoài worktree đó thấy | `git worktree list` + `git show-ref refs/remotes/origin/<b>` | **5/5 CHƯA có trên origin**, commit mới nhất 4–25 phút trước |

Ghi chú cho hàng 2: `npm test` **loại trừ `tests/e2e/`** (`find tests -path tests/e2e -prune -o …`
trong `package.json`). 1008 ca đó phủ **97/100** file. Ba file còn lại xem cột 2.

Ghi chú cho hàng 7: `cd1e97a` là HEAD của `qa2/dem-duong-vong-validate-tien` — một nhánh **chỉ
tồn tại trong worktree `wt/qa2`**, không trên origin, không trong PR nào. Phán quyết hero-walk
đang nằm trên đĩa vì thế **không tái lập được bởi bất kỳ ai khác**, kể cả khi họ tin nó.

---

## CỘT 1B — ĐÃ ĐO ĐƯỢC, nhưng ở CÂY CŨ và chưa ai đo lại

Đây vẫn là phép đo thật. Cái chúng thiếu là **hiệu lực hôm nay**.

| Khẳng định | Đo tại | Cách đo lại | Main đã đi bao xa |
|---|---|---|---|
| **7/11 cạnh** đường hero bấm qua được | `e556b4a` (#446) | dựng lại bundle tại SHA, chạy `tools/screen-snapshots.mjs` + `tools/tab-snapshots.mjs`, chấm tay theo bảng §4 | **10 commit** |
| F29 — tấm hình QR mang đúng chuỗi EMVCo, **4/4** giải ngược bằng OpenCV | `2fcd723` | `apps/mobile/tools/qr-roundtrip.py` | 35 commit |
| F05 — ô vuông link kết bạn giải ngược **9/9** | `2fcd723` | cùng file trên | 35 commit |
| F35 — ruột Tường Kỷ niệm xanh | `10f886b` (#428) | xem #428 | 32 commit |

---

## CỘT 2 — CHƯA ĐO ĐƯỢC

Không dòng nào dưới đây là "hỏng". Chúng là **chưa biết**, và mỗi dòng nói rõ chưa biết vì sao.

### Bốn cạnh còn lại của đường hero — và ba lý do khác nhau, không phải một

Lead hỏi: *chưa đi được, hay chưa ai đi?* Đáp án tách làm ba, và sự khác nhau là phần đáng đọc:

| Cạnh | Loại | Nội dung |
|---|---|---|
| 3 · Khám phá → vào nhóm | **có thể là lỗi MẪU SỐ** | app là app tab; `"Tin nhắn"` *chính là* chat nhóm. Nếu thiết kế đã bỏ chặng "vào nhóm" thì mẫu số đúng là 10 và số đo là 7/10. **Câu hỏi phạm vi demo, thuộc Lead/leader — không phải phép đo.** |
| 4 · vào nhóm → chat | **có thể là lỗi MẪU SỐ** | cùng lý do trên |
| 6 · chốt → CHỤP BILL | **CHƯA AI ĐI** | máy ảnh hiện chỉ tới được bằng lối tắt `[+] → "Tạo khoản chi"`. Không walk nào đi từ chốt sang. Đo được, chỉ là chưa ai đo. |
| 11 · VietQR → Cá nhân CẬP NHẬT | **ĐO ĐƯỢC NỬA, KHÔNG AI ĐO ĐƯỢC NỬA KIA** | khác hẳn ba cạnh trên — xem ngay dưới |

**Cạnh 11 không phải "chưa ai đi".** Ba dụng cụ chĩa vào nó, cả ba dừng ở cùng một chỗ:

- Walk **bundle** (`screen-snapshots` / `tab-snapshots` / các test Chrome) có ngón tay bấm lên
  pixel, **nhưng chặn API bằng fixture** (`EXPO_PUBLIC_API_URL=http://api.build-check.invalid`).
  Nên số tiền trên màn Cá nhân **theo cấu tạo** luôn là số fixture. Không phiên bản nào của phép
  đo này trả lời được "cập nhật" — nó bị chặn từ thiết kế, không phải vì ai lười.
- Walk **máy demo** (`di-bo-hero-tren-demo.mjs`) chạy trên máy chủ thật, allocator thật, và
  **có** chặng `CA NHAN` (dòng 323) — nhưng nó gọi `GET /contexts/{id}/balances` qua
  `dist-test/api.js`. **Không có trình duyệt.**
- `apps/mobile/tests/e2e/so-du-cuoi-duong-di.test.mjs` **tồn tại đúng cho khúc đuôi này**, và đã
  bắt được một lỗi thật (`balances` trả **403 `permission_denied`** cho chính nhóm app dùng, vì
  `CONTEXT_ID` chưa từng có dòng trong `contexts`; `App.tsx` nuốt lỗi dưới
  `.catch(() => setSoDu(null))` nên trên màn nó **trông như "chưa tiêu gì"**). Nhưng nó cũng gọi
  qua `dist-test/api.js`, **cũng không có trình duyệt**, cần máy chủ sống + `MOBILE_REQUIRE_E2E=1`,
  và **`npm test` prune nó ra** — nên **không chạy trong lượt này**. Con 403 ở trên là **lời khai
  trong header của chính file, đo tại `bf3c757`**; tôi **không** chạy lại nó, nên theo luật của
  trang này nó thuộc cột 2, không phải cột 1.

> Cả ba dừng ở tầng HTTP. **Không dụng cụ nào đi hết từ ngón tay tới pixel trên màn Cá nhân sau
> một lần chia thật.** Cạnh 11 rơi đúng vào khe đó — và cái khe ấy là chỗ lỗi 403 ở trên đã sống
> sót đủ lâu để không ai thấy.

### Những chỗ còn lại đang là suy đoán hoặc chưa ai chạm

| Chỗ | Trạng thái đo được | Vì sao chưa đo được |
|---|---|---|
| **580 ca SKIP** trong hàng 1 | đếm được, nội dung thì không | tầng `tests/postgres` bỏ qua vì thiếu `MOBILE_TEST_DATABASE_URL`. `CLAUDE.md` nói thẳng: **skip không phải là xanh**. Lượt này tôi **không** chạy tầng Postgres thật. |
| **`tests/e2e/` — 3 file `.test.mjs`** | 0 ca chạy | `npm test` prune nó ra (`find tests -path tests/e2e -prune -o …`). Cần máy chủ sống + `MOBILE_REQUIRE_E2E=1`. Thêm nữa, `vertical-slice` và `duong-bill` **cố ý từ chối** chạy trên 8099 (một cái sẽ ghi đè tài khoản nhận thật của demo, cái kia hỏng tiền đề roster) — cả hai từ chối đều **đúng**, nhưng hệ quả là bộ đã ship không trả lời được "đường hero còn chạy trên máy sắp demo không". |
| **`7/11` chưa cổng nào gác** | — | nó là phán quyết đọc-rồi-chấm của một người trên đầu ra hai con walk. Đọc nó như số liệu tự-bảo-trì là đúng cái lỗi #446 đang tố cáo. File cổng đề xuất ở §6 của #446 **chưa ship**. |
| **Tử số `41`** của `41/47` | **chưa đo lần nào** | #440 kết luận mẫu số `47` NOT VERIFIED, nhưng **không ai đo lại tử số**. Đo gần nhất tôi biết là `32/47` của qa2, ở một cây khác. Ghép tử số cũ với mẫu số mới là cùng một lỗi lệch đơn vị, chỉ đảo chiều. |
| **F37 · F38** (2 trong 5 hàng "chỉ có vỏ") | ô 1 — chờ dữ liệu | F29 · F05 · F35 đã đo xong (cột 1B). Hai hàng này cần **một tấm ảnh bất kỳ trong nhóm** (ảnh sinh bằng code là đủ, không vi phạm `CLAUDE.md`). F37 cần **thêm** một phép đo grounding **chưa ai thiết kế**. |
| **`model_construct`** | lỗ đã tái lập, bản vá **chưa vào** | PR **#450 còn OPEN**. `allocate()` nhận `float` → crash, nhận `True` → **1 đồng im lặng**. Đây là *lỗ hổng ngủ*: hôm nay pydantic chặn ở HTTP, nên chưa khai thác được từ ngoài. |
| **`repo_guard` SECRET_RULES** | bản vá tồn tại, **không ai ngoài lane đó thấy** | `devops/repo-guard-secret-rules-san`, commit 7 phút trước, **chưa đẩy lên origin**, chưa có PR. |
| **mockup 21/21 — màn nào chỉ là vỏ?** | **chưa ai đo** | 21 file PNG có thật (cột 1 hàng 6). Nhưng `FEATURE_INDEX.md` tự khai `12 READY / 9 NEEDS UPDATE`, và **lời tự khai không phải phép đo** — không cổng nào đối chiếu nhãn đó với hiện vật. Chưa ai hỏi "màn này có ruột không" cho từng mục trong 21. |
| **AI thật (Gemini)** | 0 lần gọi trong lượt này | `MATCH 95%` trên `kham-pha.html` là fixture. Mọi con số ở trang này đo phần mềm, **không đo mô hình**. |
| **5 nhánh lane chưa đẩy** | đếm được (cột 1 hàng 10), nội dung thì không | frontend · devops · qa2 · qa · backend đều có commit trong 25 phút qua, **0/5 trên origin**. Không lane nào khác — và không cổng nào — nhìn thấy chúng. |
| **Bằng chứng hành vi** | **không có, theo thiết kế** | ADR-0006 gác Giai đoạn 0. Không dòng nào ở trang này nói sản phẩm *đúng với người dùng*; chúng nói phần mềm *làm cái nó khai là làm*. |

---

## Một câu cho leader

Hai con số đo hai thứ khác nhau và cả hai đều thật:

> **Đường demo có 11 cạnh, máy bấm qua được 7** — đo ở `e556b4a`, chưa đo lại trên main hôm nay.
> **Bề rộng thì tách riêng và nói rõ đó là đếm đỉnh**, với mẫu số **51 (sàn)**, không phải 47 —
> và tử số của tỷ số đó **chưa ai đo trên cây hiện tại**.

Cái trang này thêm vào, so với một bảng toàn số: **ba cạnh chưa xanh vì ba lý do khác nhau**
(mẫu số sai · chưa ai đi · chưa có công cụ), và gộp chúng thành một con số `7/11` làm mất đúng
phần Lead cần để xếp việc.
