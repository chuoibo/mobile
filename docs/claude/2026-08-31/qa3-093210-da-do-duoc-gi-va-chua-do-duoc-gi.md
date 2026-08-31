# Đêm nay đã đo được gì, và chưa đo được gì

> **Con số 41/47 đếm ĐỈNH. Con số 7/11 đếm CẠNH. Người dùng đi trên cạnh.**

*Ghi thêm lúc `10:24` hôm nay, sau khi #463 vào `main`:* con số **cạnh** bây giờ là
**9/10**, không còn là 7/11 — và một trong ba lý do của bước nhảy đó là **thước cũ
sai**, không phải app tốt lên. Câu in đậm ở trên **không hỏng vì thế**: nó nói hai
con số **đếm cái gì**, không nói giá trị của chúng. Đọc chi tiết ở §1A hàng 11.

- lượt: `qa3-101734` (cập nhật trang `qa3-093210`)
- neo: `main` tại `fee2d73`, **tree `80f1c07`** — mọi con số ở cột 1 chạy trên đúng
  tree này trừ khi hàng đó tự khai SHA/tree khác. Vài hàng **có** khai khác, và
  chỗ khai đó là phần đáng đọc chứ không phải chú thích cho đủ.
- protocol_version: v1
- verdict: **FYI — bản đồ phạm vi hiểu biết, không sửa code, không phán quyết PR nào**
- skill: `ai-qa-review` (batch audit: soi từng khẳng định xem nó có phép đo chạy lại
  được không — và lượt này **chạy lại thật**, không chép số từ doc gốc)

## Luật của trang này

Một dòng được nằm ở **cột 1** khi và chỉ khi nó có (a) một lệnh người khác dán vào chạy lại
được, và (b) một SHA/tree phép đo đó đã chạy trên. Thiếu một trong hai → **cột 2**, dù ta tin
nó đến mấy.

Đo xong rồi tôi phải thêm **trục thứ ba**, vì hai trục trên chưa đủ: **đo ở CÂY NÀO.** Một con
số đo tại một SHA cũ vẫn là phép đo thật, nhưng nó **có hạn dùng**. Nên cột 1 tách làm hai
khối: đo **trong lượt này**, và đo ở **cây cũ, chưa ai đo lại**.

**Lượt này thêm một luật thứ hai, học được đúng trong lúc cập nhật trang:** chép một
con số kèm lệnh của nó **không phải** là kiểm lại nó. Hàng #441 dưới đây là hàng duy
nhất tôi định chép nguyên văn, tôi chạy lại cho đủ thủ tục, và **lệnh đó không còn ra
số cũ nữa** — xem §1B. Từ giờ hàng nào vào cột 1 thì lệnh của nó phải được **bấm**.

---

## CỘT 1A — ĐÃ ĐO ĐƯỢC, chạy lại trong lượt này

| # | Khẳng định | Lệnh chạy lại | Số ra thật |
|---|---|---|---|
| 1 | Bộ test Python (domain + API fake repo + repo guard) xanh | `python3 -m pytest services/api/tests tests -q` | **2833 pass · 580 skip · 5272 subtest** · 329.14s — cùng ba con số ở cả hai tree, xem ghi chú |
| 2 | Bộ test mobile xanh | `cd apps/mobile && npm test` | **1017 pass · 0 fail · 24 suite** · 21.59s |
| 3 | Cây không mang hiện vật cấm | `python3 scripts/repo_guard.py tree HEAD` | rc=0, **1313 file scan** (`1311` trên `origin/main`; nhánh này thêm 2 hiện vật ở §"Tự kiểm") |
| 4 | **Luật 1 cưỡng chế ở LÕI allocator, chặn `float` VÀ `bool`** | `cd services/api && python3 -m pytest tests/domain/test_allocator_rejects_non_integer_amounts.py -q` | **7 pass · 223 subtest** · 0.09s — #450, ADR-0012 |
| 5 | …và không đường vòng nào lọt: `allocate()` **0/5** lần trả về tiền từ đầu vào phi-`int`; **28/28** slot tiền trả `AMOUNT_NOT_INTEGER` | `cd services/api && python3 tests/qa/qa-tt-0057-gac-450/probe_duong_vong_model_construct.py` và `cd services/api && python3 tests/qa/qa-tt-0057-gac-450/probe_ma_tran_slot_tien.py` | exit 0 · exit 0 — phán quyết #461 |
| 6 | **9 nguồn tiền** chảy vào `allocate()`, **5 không qua rào pydantic** | `cd services/api && python3 tests/qa/backend-092115-nguon-tien-vao-allocate/dan_xuat_nguon.py` | exit 0 — **9 nguồn · qua rào 4 · KHÔNG qua 5** (COMPUTED 1 · DB_RECORD 4). Trục cũ đếm được 3 |
| 7 | …và tầng cuối **làm tròn thay vì từ chối** | `cd services/api && MOBILE_TEST_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile' python3 tests/qa/backend-092115-nguon-tien-vao-allocate/probe_nguon_tien.py` | exit 0 trên **PostgreSQL 16 thật**: `1500.5→1500`, `1501.5→1502` (nửa về chẵn, im lặng); `bool` **bị** từ chối (`CannotCoerce`); fake giữ nguyên float |
| 8 | **4/7 cơ chế dựng object đi vòng được qua rào tiền** — và hôm nay **0** chỗ đang đi | `cd services/api && python3 tests/qa/qa2-085832-duong-vong-tien/probe_duong_vong_rao_tien.py` | exit 0 — hai nhân chứng độc lập đều ra **chặn 3/7 · LỌT 4/7**; quét `app/`: **0 chỗ** đang dùng lối vòng |
| 9 | **Cửa thứ tư (gán thuộc tính sau khi dựng) MỞ, nhưng 0 người đi qua** — và số 0 đó có đối chứng | `cd services/api && python3 tests/qa/qa2-095741-cua-thu-tu/probe_cua_thu_tu_gan_thuoc_tinh.py` | exit 0 — đối chứng dương **6/6 hình dạng bị bắt**; mẫu số **125** chỗ gán thuộc tính; trường tiền bị gán sau khi dựng: **0**; 1 tên-giống-tiền cần người phán |
| 10 | **`repo_guard` TỪ CHỐI NẠP khi `SECRET_RULES` rỗng** — bảng rỗng là LỖI, không phải "không có luật nào để vi phạm" | `python3 -m pytest tests/test_repo_guard_secret_rules_floor.py -q` | **9 pass** · 11.37s — #458 |
| 11 | **Đường hero có 10 cạnh, máy bấm qua được 9** (không còn 7/11) | doc `docs/claude/2026-08-31/qa3-095114-bon-canh-con-lai.md` §7; phần chạy lại được: `cd apps/mobile && npm run build:check` + `make e2e` | #463 **đã merge** lúc `10:23:54`. `make e2e` **7 pass · 0 fail · 0 skip**, đo ở `f9a3b68`, **không** chạy lại trong lượt này |
| 12 | **Lỗ #439 mà #441 báo là "cổng KHÔNG cắn được" nay đã ĐÓNG** — và bảng của #441 **không** còn đo được nguyên văn | `python3 tests/qa/qa3-101734/probe_441_con_do_duoc_khong.py` | exit 0 — nguyên văn: **6/6 ô thoát 2** (không phân biệt được gì); bản phủ: **6/6 ô ĐÚNG**, kể cả `sach_nhung_cay_ban` |
| 13 | Mọi màn `App.tsx` mount đều có câu trả lời "cái gì đo màn này" | `cd apps/mobile && node --test tests/moi-man-co-duong-do.test.mjs` | **15 mount · 0 probe đi qua · 9 có địa chỉ quét · 6 chưa máy nào đo được** · 4/4 pass |
| 14 | `47` là một **lựa chọn cách đếm**, không phải con số spec tự khai | `cd /home/lakiet/mobile/product && grep -cE '^#+ F[0-9]' feature_list.md` và 3 biến thể theo mức tiêu đề | mọi mức = **47** · h1 = **12** · h2 = **35**. Token `47` xuất hiện đúng **1** lần trong spec và đó là **`## F47 — Automatic Place Detection`** (dòng 997) — **không dòng nào khai "47 tính năng"** |
| 15 | Bộ mockup có 21 mục và 21 file ảnh | `find /home/lakiet/mobile/product/RuDi_Mobile_Product_Mockups -name '*.png' \| wc -l` | **21 file** · `FEATURE_INDEX.md` tự khai **12 READY / 9 NEEDS UPDATE** |
| 16 | Phán quyết hero-walk trên đĩa **không** nói về cây này | `make hero-walk-status` | **exit 2** — "lượt đi bộ chạy ở client `9e13f9f`, KHÔNG nằm trong HEAD `fee2d73` — nhánh khác" |
| 17 | Cạnh cuối có người đo **nửa máy chủ**, và con walk đó **không có trình duyệt** | `grep -n 'CA NHAN' tests/qa/qa-tt-0031/di-bo-hero-tren-demo.mjs` | dòng **323**: chặng `"CA NHAN: so du cap nhat (GET /contexts/{id}/balances)"` — gọi qua `dist-test/api.js`, không qua pixel |
| 18 | `scripts/e2e_slice.sh` **không** truyền khoá AI vào stack nó dựng | `grep -c GEMINI scripts/e2e_slice.sh` | **0** — đây là thứ chặn cạnh cuối đo được một mạch |

**Ghi chú hàng 1.** Lần đo đầu chạy trên tree `faea162` (main `f8682b6`), rồi main nhích
hai commit **trong lúc** tôi đang đo — đúng cái bẫy trang này tồn tại để bắt. Nên tôi chạy
lại lần thứ hai trên cây của nhánh này: **cùng `2833 / 580 / 5272`**. Kiểm rẻ đi kèm:
`git diff --name-only f8682b6..fee2d73 | grep '\.py$'` ra **rỗng** — delta là tài liệu +
`apps/mobile/`, khớp với việc ba con số không nhúc nhích.

**Ghi chú hàng 2.** `npm test` **loại trừ `tests/e2e/`** (`find tests -path tests/e2e -prune -o …`
trong `package.json`). 1017 ca đó không phủ 3 file e2e — xem cột 2.

**Ghi chú hàng 11.** Đây là hàng **Lead ghi vào danh sách "chưa đo" lúc `10:17`**, và nó đã
được trả lời lúc `10:23:54` khi #463 vào `main`. Tôi để nó ở cột 1 vì đó là chỗ đúng của nó
bây giờ, và ghi cả hai mốc giờ ra để không ai phải đoán trang này lệch pha ở đâu. **Cái nó
KHÔNG chứng minh:** năm con probe Chrome sinh ra `9/10` là file dùng-một-lần nằm ở
`/tmp/qa3-canh/`, **không** trong git — nên người khác dán lệnh vào **không** chạy lại
được chúng. Phần chạy lại được của hàng này là `npm run build:check` và `make e2e`; phần
"ngón tay bấm" thì đọc doc, đừng đọc như số tự-bảo-trì.

**Ghi chú hàng 16.** Bản trước của trang này ghi client `cd1e97a`. Hôm nay là `9e13f9f` —
**vẫn một nhánh không nằm trong `HEAD`**. Nghĩa là ô này không nhúc nhích: phán quyết
hero-walk trên đĩa vẫn không tái lập được bởi người khác, chỉ đổi tên nhánh nó đến từ.

**Một hàng của bản trước bị bỏ, nói rõ ra chứ không im.** Bản `qa3-093210` có hàng
*"5 lane có việc chưa đẩy, 0/5 trên origin"*. Đó là ảnh chụp một **thời điểm** (`09:32`),
Lead đã hành động theo nó lúc `09:53`, và một trong năm nhánh đó nay đã merge (#463). Chạy
lại `git worktree list` hôm nay trả lời một câu **khác** (58 nhánh worktree, đủ mọi tuổi),
nên tôi **không** làm mới con số đó — làm mới bằng một phép đo khác là cách một hàng chết
tiếp tục trông như đang sống. Ai cần lại câu đó thì đo lại theo cửa sổ thời gian, không
theo danh sách nhánh.

---

## CỘT 1B — ĐÃ ĐO ĐƯỢC, nhưng ở CÂY CŨ và chưa ai đo lại

Đây vẫn là phép đo thật. Cái chúng thiếu là **hiệu lực hôm nay**.

| Khẳng định | Đo tại | Cách đo lại | Main đã đi bao xa |
|---|---|---|---|
| **10 cổng của đêm 30–31: 8 cắn được** sạch; #431 cắn đúng hình dạng nó nhắm, **mù** khi lỗi viết qua biến; #439 **hở** ở ô hay gặp nhất | `2f8a301` (#441) | xem hàng dưới — **lệnh nguyên văn không còn ra số cũ** | ~20 commit |
| **7/11 cạnh** đường hero bấm qua được | `e556b4a` (#446) | **đã bị thay** bởi #463 (`9/10`, cột 1A hàng 11) — giữ lại đây để ai đọc số cũ ở chỗ khác biết nó hết hạn | — |
| F29 — tấm hình QR mang đúng chuỗi EMVCo, **4/4** giải ngược bằng OpenCV | `2fcd723` | `apps/mobile/tools/qr-roundtrip.py` | ~40 commit |
| F05 — ô vuông link kết bạn giải ngược **9/9** | `2fcd723` | cùng file trên | ~40 commit |
| F35 — ruột Tường Kỷ niệm xanh | `10f886b` (#428) | xem #428 | ~37 commit |

### Hàng #441 hỏng cách chạy lại — và đó là phát hiện, không phải sự cố

Đây là hàng duy nhất trong danh sách Lead giao mà tôi **định** chép nguyên văn. Chạy lại
cho đủ thủ tục thì nó ra thế này:

```
python3 tests/qa/qa2-073146-muoi-cong/probe_hero_walk_cay_sach.py     -> exit 1
  sach_va_cay_sach            mong 0   được 2   LỆCH
  sach_nhung_cay_ban          mong 2   được 2   ĐÚNG
  ban_va_van_tay_khop         mong 0   được 2   LỆCH
  ban_nhung_van_tay_da_doi    mong 2   được 2   ĐÚNG
  thieu_truong_tree           mong 2   được 2   ĐÚNG
  tree_la_dau_hoi             mong 2   được 2   ĐÚNG
  cổng nói: "phán quyết KHÔNG GHI những thứ ngoài git mà lượt đi bộ cần"
```

**Cả sáu ô đều thoát 2.** Bảng không còn phân biệt được gì — bốn ô "ĐÚNG" đúng vì
**một lý do khác** với lý do chúng được viết ra để đo. Đây đúng hình dạng "bảng toàn
đỏ nhìn như bảng gác chặt".

Nguyên nhân: `hero_walk.sh` từ #444 → #449 → #454 thêm một trường **bắt buộc**
`ngoai_git` (`scripts/hero_walk.sh:472`), và phép kiểm đó chạy **trước** phép so cây,
**cho mọi phán quyết**. Bộ ca của #441 viết phán quyết theo hình dạng cũ, thiếu trường
đó, nên chết ở cổng sớm hơn — trước khi chạm tới câu hỏi nó muốn hỏi.

Phủ lên hai dòng (hỏi chính `hero_walk.sh --ngoai-git` lấy vân tay, **không** tự dựng
lại chuỗi) rồi chạy lại trên tree `80f1c07`:

```
python3 tests/qa/qa3-101734/probe_441_con_do_duoc_khong.py            -> exit 0
  cả 6/6 ô ĐÚNG — "phán quyết buộc được vào cây ở mọi chiều"
  sach_nhung_cay_ban:  mong 2, được 2   <== lỗ #441 tố cáo, nay ĐÓNG
```

File đó **phủ lúc chạy, không fork**: hai bản sao của một cổng gác tiền là cách hai
bảng bắt đầu nói hai số khác nhau. Nếu qa2 sửa probe gốc, neo của bản phủ mất và nó
**dừng kèm thông báo** thay vì lặng lẽ chấm một bản sao cũ — `"Không áp được" KHÔNG
đọc thành "đã sửa"`.

Nên hàng #441 đọc đúng là: **`8/10` là số thật của cây `2f8a301`, và nó đã cũ theo
hướng TỐT** — cái cổng thứ chín bị chấm "KHÔNG cắn được" nay cắn được. Nhưng `8/10`
**không** tự sửa thành `9/10`: chín cổng còn lại tôi chưa đo lại trong lượt này, và
`probe_441_va_ngoai_git.py` nằm ở `/tmp`, không trong git.

**Việc gọn nhất rơi ra từ đây (thuộc lane qa2):** vá `probe_hero_walk_cay_sach.py`
trong repo để nó ghi `ngoai_git`. Không vá thì bộ ca đó đang là một cổng **im lặng
mù** — nó vẫn chạy, vẫn in bảng, và bảng đó không còn đo cái gì.

---

## CỘT 2 — CHƯA ĐO ĐƯỢC

Không dòng nào dưới đây là "hỏng". Chúng là **chưa biết**, và mỗi dòng nói rõ chưa biết vì sao.

### Bốn câu Lead đặt lúc `10:17` — trạng thái từng câu

| Câu hỏi | Trạng thái | Chi tiết |
|---|---|---|
| Có đường nào **ghi tiền THẲNG xuống sổ cái, không qua `allocate()`** không? | **đang đo (qa2)** | Cột 1A hàng 6 đếm **đường VÀO** `allocate()`. Câu này hỏi chiều ngược: đường **né hẳn** nó. Chưa có phép đo nào trên trang này trả lời được, và không suy ra được từ hàng 6 — một cái đếm cửa vào, một cái đếm cửa bên. |
| **4 cạnh hero còn lại** thuộc loại nào trong ba loại? | **ĐÃ TRẢ LỜI** — chuyển lên cột 1A hàng 11 | #463 merged `10:23:54`, 6 phút sau khi câu này được viết. Ba loại thành: 2 cạnh **không phải cạnh** (thước sai), 1 cạnh **đi được** (chưa ai đo), 1 cạnh **chưa ai đi hết**. |
| **Phép tính trên tiền**: `bill.py:104` và mọi chỗ dùng `/` thay `//` | **đang đo (backend)** | Trang này có đúng **một** dữ kiện liên quan, và nó tới từ phép đo của hàng 6 chứ không phải từ việc đọc code: `dan_xuat_nguon.py` xếp `app/domain/bill.py:104` là nguồn **COMPUTED** duy nhất, **`rào: không có`** — kiểu của nó kế thừa từ các số hạng. Đó là lý do câu hỏi này có thật. Số chỗ dùng `/` thì **chưa ai đếm**, và tôi cố ý **không** `grep` một con số vào đây: `grep` bắt cả comment và cả chuỗi, và một con số sai trên trang này tệ hơn một ô trống. |
| **21/21 màn mockup có file — có màn nào chỉ là VỎ không?** | **chưa ai đo** | 21 file PNG có thật. Nhưng `FEATURE_INDEX.md` **tự khai** `12 READY / 9 NEEDS UPDATE`, và lời tự khai không phải phép đo — không cổng nào đối chiếu nhãn đó với hiện vật. Chưa ai hỏi "màn này có ruột không" cho từng mục trong 21. |

### Cạnh cuối của đường hero: hai nửa đều đạt, một mạch thì chưa

Cạnh `VietQR → Cá nhân CẬP NHẬT` là cạnh duy nhất còn mở trong `9/10`, và nó mở vì
**phép đo**, không vì thiếu tính năng (#463 §3):

- **nửa cú bấm ĐẠT** — `"Đóng khoản chi, quay lại các tab"` → tab `Cá nhân` bấm được
  (nút `"Hoàn tất"` thì **không**: lùi về `Đợt thu`, thanh tab chưa trở lại).
- **nửa dữ liệu ĐẠT** — `GET /people/{id}/finance` trên stack thật đổi 4 trường sau một
  khoản chi; bundle trỏ vào stack thật in đúng `2 Lần chia bill · 1 Nhóm`.
- **một mạch thì DỪNG** ở `/receipts/scan`: `scripts/e2e_slice.sh` không truyền
  `GEMINI_API_KEY` vào stack nó dựng (`grep GEMINI` trong file ra **0** dòng), nên trên
  stack đó **không tạo được khoản chi bằng app**.

> Ghép ba mảnh đo ở ba phiên rồi gọi là một cú đi bộ chính là hình dạng cả đêm nay đi tìm.
> Nên nó nằm ở cột 2, không phải cột 1.

### Những chỗ còn lại đang là suy đoán hoặc chưa ai chạm

| Chỗ | Trạng thái đo được | Vì sao chưa đo được |
|---|---|---|
| **580 ca SKIP** trong hàng 1 | đếm được, nội dung thì không | tầng `tests/postgres` bỏ qua vì thiếu `MOBILE_TEST_DATABASE_URL`. `CLAUDE.md` nói thẳng: **skip không phải là xanh**. Lượt này tôi **có** chạy một probe trên Postgres thật (hàng 7) nhưng **không** chạy tầng `tests/postgres`. |
| **`tests/e2e/` — 3 file `.test.mjs`** | 0 ca chạy | `npm test` prune nó ra. Cần máy chủ sống + `MOBILE_REQUIRE_E2E=1`. Thêm nữa, `vertical-slice` và `duong-bill` **cố ý từ chối** chạy trên 8099 — cả hai từ chối đều **đúng**, nhưng hệ quả là bộ đã ship không trả lời được "đường hero còn chạy trên máy sắp demo không". |
| **`9/10` chưa cổng nào gác** | — | như `7/11` trước nó: phán quyết đọc-rồi-chấm của một người trên đầu ra các con probe. Đề nghị gác vẫn nguyên: một file cùng hình dạng `moi-man-co-duong-do.test.mjs`, mỗi ô "đi được" **bắt buộc** trỏ vào một bước walk có thật. **Chưa ship.** |
| **Tử số `41`** của `41/47` | **chưa đo lần nào** | #440 kết luận mẫu số `47` NOT VERIFIED, nhưng **không ai đo lại tử số**. Đo gần nhất tôi biết là `32/47` của qa2, ở một cây khác. Ghép tử số cũ với mẫu số mới là cùng một lỗi lệch đơn vị, chỉ đảo chiều. |
| **F37 · F38** (2 trong 5 hàng "chỉ có vỏ") | ô 1 — chờ dữ liệu | F29 · F05 · F35 đã đo xong (cột 1B). Hai hàng này cần **một tấm ảnh bất kỳ trong nhóm**. F37 cần **thêm** một phép đo grounding **chưa ai thiết kế**. |
| **Cửa thứ tư sau hôm nay** | hôm nay `0/125`, ngày mai thì không ai biết | Probe hàng 9 nói rõ: không cổng nào gác điều này. Một `obj.amount_vnd = x` thêm vào tuần sau **sẽ không làm đỏ cái gì**, và triệu chứng sẽ là một con số hơi lệch trong sổ chứ không phải một lỗi 500 ai đó nhìn thấy. |
| **AI thật (Gemini)** | 0 lần gọi trong lượt này | `MATCH 95%` trên `kham-pha.html` là fixture. Mọi con số ở trang này đo phần mềm, **không đo mô hình**. |
| **Mã QR quét bằng app ngân hàng thật** | **chưa ai làm** | F29 chứng minh chuỗi EMVCo giải ngược được bằng OpenCV. Không phải cùng một câu hỏi. Ô này không nhúc nhích đêm nay và không được đọc thành đã phủ. |
| **Bản native** | **chưa ai đo** | Mọi phép đo giao diện ở trang này là RN Web trong Chrome. Nút `"nhập tay"` được hứa trong menu `[+]` mà **không có** trên bản web; có thể tồn tại trên điện thoại — chưa ai kiểm. |
| **Bằng chứng hành vi** | **không có, theo thiết kế** | ADR-0006 gác Giai đoạn 0. Không dòng nào ở trang này nói sản phẩm *đúng với người dùng*; chúng nói phần mềm *làm cái nó khai là làm*. |

---

## Tự kiểm: trang này có giữ được luật của chính nó không

Một trang bảo "mỗi hàng phải có lệnh chạy lại được" có thể đúng **về hình thức** —
hàng nào cũng có một khối lệnh — mà sai **về việc**: lệnh in ra đã trôi khỏi lệnh
thật sự được chạy, và không ai thấy, vì **đọc một lệnh không phải là chạy nó**.

Nên tôi bóc từng khối lệnh ra khỏi chính bảng §1A rồi dán vào `bash` chạy nguyên văn:

```
python3 tests/qa/qa3-101734/chay_lenh_nguyen_van.py
  -> 17/18 hàng chạy nguyên văn được, mã thoát đúng như hàng đó khai
     hàng 11 BỎ QUA và in rõ lý do (make e2e dựng cả stack; trang đã tự khai không chạy lại)
     hàng 16 mong thoát 2 — cổng TỪ CHỐI phán quyết của cây khác, thoát 2 LÀ kết quả
     hàng 18 mong thoát 1 — `grep -c` thoát 1 khi đếm ra 0, và 0 là con số hàng đó khai
```

Lượt chạy đầu tiên **đỏ 5 chỗ**, và phân loại chúng là phần đáng giữ lại:

| Chỗ đỏ | Là gì | Xử lý |
|---|---|---|
| hàng 14 `grep … feature_list.md` | **lỗi thật của trang** — lệnh chỉ chạy được nếu người đọc đang đứng ở `~/mobile/product`, mà trang không nói | thêm `cd` vào lệnh |
| hàng 12 | **lỗi thật của trang** — ô ghi một *đường dẫn*, không phải một *lệnh*; và file đó chỉ có trên `/tmp` của máy này | viết thành lệnh, và **đưa hẳn probe vào repo** (`tests/qa/qa3-101734/`) |
| hàng 15 `find … \| wc -l` | lỗi của **máy kiểm**: nó cắt ô ở dấu `\|` của lệnh, tưởng đó là biên cột | máy kiểm tách theo pipe **chưa escape** |
| hàng 16 · 18 | lỗi của **máy kiểm**: chấm mọi mã khác 0 là đỏ, trong khi mã ≠ 0 chính là phép đo | khai mã mong đợi kèm **lý do**, không im lặng tha |

Hai hàng đầu là lỗi mà **chỉ có việc chạy mới tìm ra** — cả hai đọc rất trơn tru trên
trang. Hai hàng cuối là lời nhắc rằng một máy kiểm quá nghiêm và một máy kiểm quá dễ
đều nói dối, chỉ khác chiều.

**Cái tự kiểm này KHÔNG chứng minh:** rằng số ra là số **đúng**. Nó chứng minh lệnh
**chạy được và thoát đúng mã đã khai**. Một lệnh chạy xanh mà đo nhầm thứ vẫn xanh ở
đây — hàng #441 ở §1B là ví dụ sống, và nó bị bắt bởi việc đọc **đầu ra**, không phải
bởi mã thoát.

---

## Một câu cho leader

Ba con số, ba thứ khác nhau, cả ba đều thật:

> **Đường demo có 10 cạnh, máy bấm qua được 9** — đo ở `f9a3b68`, đã merge (#463).
> Cạnh còn lại mở vì **thiếu một biến môi trường trong script test**, không vì thiếu
> tính năng.
>
> **Bề rộng thì tách riêng và nói rõ đó là đếm ĐỈNH**, với mẫu số **51 (sàn)**, không
> phải 47 — và tử số của tỷ số đó **chưa ai đo trên cây hiện tại**.
>
> **Rào tiền dày một lớp và lớp đó nay ở LÕI**, không còn ở biên: `allocate()` tự từ
> chối `float` và `bool` (#450/#461). Bốn cửa vòng vẫn mở về mặt cơ chế, và **0 chỗ
> trong `app/` đang đi qua chúng hôm nay** (#459/#462).

Cái trang này thêm vào, so với một bảng toàn số: **mỗi ô trống nói rõ nó trống vì lý do
gì** — chưa ai đi · không có dụng cụ · thước sai · đang có người đo. Bốn lý do đó xếp
việc khác nhau hoàn toàn, và gộp chúng thành một tỷ lệ phần trăm làm mất đúng phần Lead
cần.

Và một cảnh báo rút ra từ chính lượt cập nhật này: **một hàng ở cột 1 có thể mục mà
không ai thấy.** Hàng #441 vẫn có lệnh, vẫn có SHA, vẫn chạy — và đã ngừng đo cái nó
nói nó đo từ lúc nào không rõ. Trang này chỉ đáng tin tới mức người cập nhật nó chịu
**bấm lại** từng lệnh thay vì chép chúng.
