# Review PR #566 — UI-0/1 hệ hình ảnh v2 (nền tảng + vào cửa)

- **PR:** https://github.com/chuoibo/ru-di-app/pull/566 · base `main` `4259407` · head chấm **`991b3ea`** (chuỗi `4167e2b` → `1f2aa74` ruff format → `991b3ea` sửa theo review).
- **Verdict (ADR-0007):** APPROVE — người merge: Claude (lane tác giả) theo lệnh trực tiếp của Lead tối 05/09/2026; vì charter cấm tác giả tự chấm, cổng gồm hai bên không viết code này: agy QA (bắt buộc trước merge) và một reviewer Claude context mới đọc diff theo 5 loại blocker.
- **Blocker còn mở:** không. Blocker đã đóng: CI `ruff format --check` đỏ ở `4167e2b` → `1f2aa74`.
- **Bằng chứng đã xem:** log cổng trong phiên (npm test 654/654, pytest gốc 3093 passed/654 skipped Postgres, guard, contracts, screens 38/38), CI GitHub trên `1f2aa74` (10 pass / 1 fail = 5 ca `test_android_emulator_may_ket.py` đỏ sẵn trên main) và `991b3ea` (10 pass, job `api and domain` còn chạy lúc merge), bảng native trên head gộp main (light, dark 1.3, OTP `--ai`) và bảng light trên `991b3ea` (19 ảnh, XANH), finish reviewer Impeccable `ship` ở `d168b63` (nhật ký §7–9 `ui-v2-direction-round.md`).
- **Không kiểm được:** tablet dark, iOS, máy thật; render native của agy/reviewer (không dùng emulator theo brief).

## 1. agy QA — `/tmp/agy-pr-566-report/verdict.md` (head `4167e2b`, checkout sạch, npm ci)

PASS
Mọi test tự động đều xanh trên head 4167e2b, các ràng buộc thiết kế v2 được giữ vững và không có test nào thả trôi lỗi đột biến.

### 1. Kết quả chạy test
**Pytest (backend):**
- Đạt 3093 passed, 5389 subtests passed. 
- Tầng Postgres (`services/api/tests/postgres`) và các test phụ thuộc DB đã **SKIP 654 test** vì thiếu cấu hình `MOBILE_TEST_DATABASE_URL` — ghi nhận đúng thiết kế môi trường, không bị gọi là xanh ảo.

**NPM Test (mobile):**
- Đạt 654/654 test. Mọi logic biên dịch, format và cấu trúc component (motion, adaptive, SVG,...) đều vượt qua các bộ self-check tĩnh.

**Hợp đồng API & Repo Guard:**
- `check_screens_reachable.py`: 38/38 màn có đường render từ cửa vào.
- `check_api_contract.py` / `check_server_routes_called.py`: Client và máy chủ khớp hợp đồng (91 route, không có route mới nào bị bỏ rơi).
- `check_actor_headers.py`: Đạt — 209 lời gọi đều gửi X-Actor-ID hợp lệ.
- `repo_guard.py`: Passed (37339 file scan(s) trong 25 commit(s)).

**Cụm Script sinh mã (Design Tokens & Textures):**
- `sinh_token_ui_v2.py` chạy qua êm đẹp, `git status` không đổi file nào (script idempotent).
- `sinh_chat_lieu_ui_v2.py --kiem`: Khớp tham số đo phẳng `muc-in: alpha mean 38.2, stddev on coral @0.32 = 10.48`.

### 2. Phát hiện vùng mã chưa được cover (UI Primitives)
Qua kiểm tra tập file `apps/mobile/src/rudi/ui/*.tsx`, một số primitive mới không hề được import ở bất kỳ chỗ nào trong cây app. Do đó, chúng không có unit test Node nào chạm tới và không có flow Maestro nào đi qua:
- `ErrorState.tsx`
- `MediaSlot.tsx`
- `Sheet.tsx`
- `Skeleton.tsx`
- `Stepper.tsx`
*(Lưu ý: Đây là phát hiện mã chết hoặc mã chuẩn bị sẵn cho tương lai, không phải lỗi sai behavior).*

### 3. Kết quả thử nghiệm đột biến (Mutation)
Đã cô lập từng đột biến trên bản sao hoặc worktree, đảm bảo không lưu lại rác trong repo `/tmp/agy-pr-566`. Kết quả: **Tất cả các đột biến đều bị bắt quả tang đỏ rực**.
1. **`duong-svg.ts`**: Đổi đoạn cuối từ `Z` thành ` L Z` -> test `duong-svg.test.mjs` LỖI ngay lập tức (`AssertionError`).
2. **`luoi-chat-lieu.ts`**: Bỏ vòng lặp bảo vệ `while (cols * rows > maxTiles)` -> test `luoi-chat-lieu.test.mjs` LỖI vì không xử lý được lưới lớn 4000x4000.
3. **`tokens.json`**: Đổi mã màu `light.ground` thành `#ff0000` -> `test_contrast_floor.py` (kiểm tra độ tương phản) và `test_shared_tokens.py` (kiểm tra khớp với `guest.css`) đều LỖI đồng loạt do giá trị nguồn bị hỏng.
4. **`StampButton.tsx`**: Đổi opacity từ `0.26` xuống `0.10` -> `test_chat_lieu_tiles.py` LỖI ngay lập tức vì không đạt mốc pha chữ ký.
5. **`Avatar.tsx`**: Chèn lén một mã màu hex `#ff0000` -> `rudi-khong-hex.test.mjs` LỖI (phát hiện hex lọt ra ngoài `theme.ts`).
6. **`Welcome.tsx`**: Đổi text hiển thị `Đăng nhập` thành `Đăng nhập —` -> `dau-gach-dai.test.mjs` LỖI (không cho phép ký tự gạch ngang em dash sai chuẩn).

### 4. Vùng chưa test được
- Không kiểm tra được Layout và Render thực tế trên Emulator (do quy định KHÔNG dùng ADB/Emulator, KHÔNG dùng app thật). Các lỗi giao diện như tràn viền text, lỗi font Bricolage Grotesque, hay giật lag vật lý khi render các Texture 256x256 không thể đánh giá được trên môi trường Node.


## 2. Reviewer context mới — verdict cho `1f2aa74`

## APPROVE

**PR #566** · nhánh `claude/p0-w-ui0-nen-tang-design-system` · base `origin/main` = `4259407` (cũng là merge-base) · reviewer context mới, chỉ đọc + chạy cổng, không sửa repo.

### Head đã review

- **`4167e2b`** — head được giao. Đọc toàn bộ diff `origin/main...4167e2b`: 72 file, +4858/−869, 25 commit (24 không phải merge). Không file nào thuộc `services/api/app/{api,db,domain}` (Codex) hay `phase0/`, `docs/protocol/v1/` (đóng băng).
- **`1f2aa74`** — head **hiện tại** của PR, được đẩy lúc 22:06 (giữa lúc review; worktree `/home/lakiet/wt-ui0` bị chuyển sang SHA này lúc 22:05:36). Delta `4167e2b..1f2aa74` = 3 file Python (`scripts/sinh_token_ui_v2.py`, `tests/test_chat_lieu_tiles.py`, `services/api/tests/web/test_contrast_floor.py`), tôi so `git show` hai phía: **AST bằng nhau từng file** — chỉ là `ruff format`. Không file `.ts/.tsx/.json/.css/.md` nào đổi.
- **Phán quyết áp cho `1f2aa74`.** Riêng `4167e2b` đứng một mình thì là REQUEST_CHANGES: cổng CI `ruff on changed files` đỏ ở nửa `ruff format --check` (tái lập được — xem "Blocker đã đóng"). `1f2aa74` sửa đúng cái đó, CI ruff xanh, và vì delta chỉ là format nên mọi kết luận về hành vi dưới đây đúng cho cả hai SHA. Vì worktree đổi SHA giữa chừng, **toàn bộ cổng trong bảng dưới được chạy lại trên `1f2aa74` với worktree sạch** (`git status` rỗng).

### Blocker còn mở

**Không có** (theo 5 loại của charter §4).

### Blocker đã đóng (chỉ tồn tại ở `4167e2b`)

| | |
|---|---|
| Loại | (1) vi phạm cổng + (5) tái lập được |
| Dẫn chứng | CI run `3396…7347` trên `4167e2b`: job `ruff on changed files` **failure** (`##[error]ruff HỎNG trên file nhánh này chạm`). Tái lập tại chỗ: `ruff format --check` (cấu hình mặc định, như `scripts/ruff_changed.sh`) trên ba file `git show 4167e2b:…` → "3 files would be reformatted". Nửa `ruff check` xanh ở cả hai SHA. |
| Hậu quả | Mô tả PR ghi «ruff trên file đổi» trong khi cổng CI ruff đỏ ở head được giao review. |
| Đã gỡ | `1f2aa74` (chỉ format, AST không đổi); CI run `3397…3363`: `ruff on changed files` **pass**; tôi kiểm lại `ruff format --check` trên bản `1f2aa74` → sạch. |

### Hai điểm merger/Lead cần thấy trước khi bấm (không phải blocker theo taxonomy, nhưng không được im)

1. **ADR-0020 dòng 3 tự mâu thuẫn với chính PR này.** Dòng 3 ghi: «ĐỀ XUẤT — chờ Lead đánh ĐÃ CHẤP NHẬN. **Lát UI-1 trở đi không merge trước khi dòng này đổi**; UI-0 (nền tảng) có thể merge vì không đổi màn nào». PR này là **UI-0/1**: Welcome/Login/OTP đổi hẳn, tab bar tự vẽ, display face trên mọi tiêu đề. Lịch sử: dòng 3 viết ở `266a493` (12:19), giữ nguyên ở `ea59713` (13:17); UI-1 vào nhánh ở `fc434be` (13:37) mà dòng không đổi. Vì sao tôi **không** xếp là blocker: thẩm quyền thực chất đã có — `docs/claude/2026-09-05/ui-v2-direction-round.md §5` ghi «Lead (13:0x, 05/09) giao cho Claude tự chọn và tự thực hiện, đánh giá bằng ảnh thật», và ADR-0020 tự ghi «Quyết định bởi: Lead (bốn quyết định chốt trong phiên 2026-09-05)»; cái còn thiếu là con dấu hình thức, không phải quyết định. Nhưng Lead chỉ đọc `main`, và trên `main` sẽ có một ADR nói «UI-1 chưa được merge» cạnh Welcome v2. **Cách rẻ nhất (một dòng, trong PR này):** viết lại dòng 3 thành mô tả đúng thực tế — UI-0/1 gộp một PR theo uỷ quyền của Lead 13:0x 05/09 (dẫn §5), các lát UI-2… chờ Lead đánh ĐÃ CHẤP NHẬN — hoặc Lead comment chấp nhận trên PR rồi đổi trạng thái. Nếu Lead muốn giữ đúng trình tự tự đặt (UI-0 vào trước, đọc ADR, rồi UI-1) thì đây là lý do để tách; tôi để Lead quyết.
2. **CI job `api and domain` đỏ trên cả hai SHA — nhưng là đỏ sẵn của `main`, không phải của PR.** 5 ca `tests/test_android_emulator_may_ket.py` (`test_down_khong_dung_may_cua_AVD_khac`, `test_down_khong_co_gi_thi_noi_khong_co_gi`, `test_up_khong_bat_instance_thu_hai_len_AVD_dang_bi_giu` timeout 90 s, `test_down_khong_tu_giet_chinh_no`, `test_down_khong_treo_khi_adb_khong_tra_loi` «down mất 48.x s») đỏ **y hệt** ở run `3395…9222` trên `main` `4259407` (và ba run `main` trước đó). PR không chạm `scripts/android_emulator.sh` hay test đó. Số đếm còn xác nhận điều PR thêm: `main` 3067 passed / 669 skipped → PR 3073 passed / 669 skipped = **+6 passed, 0 skip mới** = đúng 6 ca `tests/test_chat_lieu_tiles.py` (Pillow có trên runner, `importorskip` không kích). Nợ này thuộc lane devops (`devops/emulator-android-tai-lap-duoc` đang mở trong `git worktree list`), không chặn PR này.

### Suggestion (không chặn; đặt tên/phong cách/nợ tài liệu)

**Tài liệu lệch với cây**
- `DESIGN.md:586` và `:788`, `.impeccable/design.json:774` nói `WordmarkEmbossed.tsx` «còn trong kit / có trong kit, không màn nào ship dùng» — file đã xoá ở `5cc57d2` (không có trong `git ls-tree HEAD`, chưa từng có trên `main`). Sửa ba câu.
- ADR-0020 §2.3 «nhúng bằng plugin `expo-font` lúc build» ↔ `apps/mobile/assets/fonts/README.md` «Nạp runtime bằng `expo-font` (`src/rudi/fonts.ts`), **không nhúng lúc build**». Cây làm theo README (`useFonts` + `require`); `app.json` khai plugin `expo-font` không có `fonts` option nên vô hại. Chọn một câu.
- `packages/shared/tokens.json` khối `type`: `"displayFace": "BricolageGrotesque"` đứng ngay trên ghi chú `"_": "System stack có chủ đích… Một webfont ở đây tốn LCP… đổi lại không được gì"`. Ghi chú cũ giờ sai.
- `fonts/README.md` «đủ 527 glyph» — bốn file có 597 glyph (fontTools). Nhỏ.
- Mô tả PR «52 cặp chữ ≥ 4.61:1» — DESIGN.md và `design.json` sinh ra **50** cặp (`pairsChecked: 50`, min 4.61). «Guard range 24 commit» — thực 25 (kể merge) ở `4167e2b`, 26 ở `1f2aa74`; không sao.

**Font (kỹ thuật, ngoài phạm vi Android đã khai)**
- Bảng `name` của **cả bốn** `.ttf` giống nhau: family/full name đều «Bricolage Grotesque 96pt ExtraBold», subfamily «Regular» (instancer không cập nhật name table). Android/expo-font phân giải theo key nên bảng native không lộ; **trên iOS** bốn face cùng PostScript name có nguy cơ CoreText từ chối đăng ký trùng → Bold/SemiBold/Condensed đổ về ExtraBold. PR đã khai iOS chưa chứng minh; khi làm iOS thì cắt lại với `--update-name-table` hoặc đặt nameID 1/2/4/6 theo instance. nameID 13 = OFL có đủ; `OFL-BricolageGrotesque.txt` kèm — giấy phép ổn.

**Tiền (đúng luật, nhưng ghi để người sau không đọc nhầm)**
- `ui/Money.tsx` `useCountUp`: `Math.round(from + (target − from) * eased)` — trung gian là float **của phép nội suy hiển thị**, không phải phép tính tiền; mọi giá trị render là số nguyên và giá trị cuối là `vnd` máy chủ gửi. Nhưng trong ≤ 200 ms màn hiển thị các số nguyên **không có trong sổ**, và `accessibilityLabel={text}` đọc cả số trung gian cho screen reader. `countUp` mặc định `false`, `moneyCountUpMs` chặn khi domain state chưa hợp lệ (test `motion.test.mjs` pin, đột biến bỏ guard → đỏ), và **chưa màn nào dùng `Money`**. Đề nghị: `accessibilityLabel` = giá trị đích, và ghi vào DESIGN.md rằng count-up là hiệu ứng, không phải dữ liệu.
- `Money.tsx` import `dinhDangTienVnd` từ **cây legacy** `src/screens/chat/ke-hoach.ts`; `ui/Avatar.tsx` import `chuDau` từ `src/screens/ca-nhan/ban-be.ts`. ADR-0016 muốn xoá legacy theo mảng — hai import này sẽ ghim hai file legacy sống. Chuyển hai helper vào `src/rudi/` khi tới lát UI-5/UI-7.
- Không có UI ngân hàng/QR/thanh toán mới (grep `vietqr|qr|bank|ngân hàng|số tài khoản|momo|chuyển khoản|EMV` trên `+` của `apps/mobile/src`, `apps/mobile/app` → 0).

**Code nhỏ**
- `screens/Welcome.tsx` `openCover`: bấm hai lần trong 300 ms → hai `setTimeout(router.push("/login"))` → hai màn Login chồng. Khoá bằng ref/`disabled` trong lúc bìa nhấc.
- `app/_layout.tsx`: `if (!fontsLoaded && !fontsError) return null;` — đúng thứ tự hook (không hook nào sau early return); không có hạn giờ nếu `useFonts` không bao giờ resolve. Với asset đóng gói thì chấp nhận được; ghi để biết.
- `ui/Sheet.tsx:50` đọc `progress.value` trên JS thread trong render — Reanimated khuyên tránh; primitive chưa ai dùng.
- `scripts/sinh_token_ui_v2.py`: dưới **cấu hình ruff của `services/api`** (`select` có `I`) còn `I001` (thiếu dòng trống sau `from __future__ import annotations`) ở cả hai SHA. CI chạy `ruff_changed.sh` với cấu hình mặc định cho file gốc repo nên xanh; nếu đội muốn script gốc theo cùng chuẩn thì `ruff check --fix` một dòng.
- `tests/test_chat_lieu_tiles.py`: `Image.getdata` có DeprecationWarning (Pillow 14); tên ca «đúng từng byte» nhưng so **pixel** (đúng ý, chỉ lệch tên).
- `tests/duong-svg.test.mjs` ca «không số mũ»: xem mục đột biến — lời khai này chưa được pin.

### Cổng đã chạy — trên `1f2aa74`, worktree sạch, từ `/home/lakiet/wt-ui0` (node v22.23.2 tại `$HOME/.nvm/versions/node/v22.23.2/bin`)

| Cổng | Lệnh | Kết quả |
|---|---|---|
| Web tests (tokens ↔ guest.css ↔ DESIGN.md, contrast floor đọc `ui/**`) | `python3 -m pytest services/api/tests/web -q` | `42 passed, 179 subtests passed` (8 contrast_floor · 30 guest_page · 4 shared_tokens) |
| Ô chất liệu | `python3 -m pytest tests/test_chat_lieu_tiles.py -q` | `6 passed` (chạy 4 lần, không flaky) |
| Screens reachable | `python3 scripts/check_screens_reachable.py` | `38/38 màn có đường render từ cửa vào · 0 pin · 190 file đã đọc` |
| Contract / routes / actor / CORS | `python3 scripts/check_{api_contract,server_routes_called,actor_headers,cors_contract}.py` | «Client và máy chủ khớp hợp đồng.» · «Không có route mới nào bị bỏ rơi.» · «ĐẠT — 209 lời gọi đều gửi X-Actor-ID.» · «Mọi header và method client gửi đều qua được preflight.» |
| Typecheck | `cd apps/mobile && npx tsc --noEmit` | rc=0 |
| Build test + 5 test mới | `npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs` rồi `node --test tests/<f>.test.mjs` | duong-svg 4/4 · luoi-chat-lieu 4/4 · adaptive 6/6 · motion 5/5 · tat-nut-noi-dev-menu 3/3 |
| Hex chỉ ở theme.ts · cấm em-dash · vòng import | `node --test tests/{rudi-khong-hex,dau-gach-dai,vong-import}.test.mjs` | 3/3 · 3/3 · 3/3 (ba file test không bị PR sửa; hex gate quét `src/rudi` + `app`) |
| Toàn bộ node (trừ e2e, **không** `build:check` theo chỉ dẫn) | `node --test $(find tests -path tests/e2e -prune -o -name '*.test.mjs' -print \| sort)` | `# tests 654 · pass 652 · fail 2` — hai ca đỏ là **guard bundle cũ** của `tests/base-url.test.mjs` («bản web ở .expo-build-check dựng lúc 20:15:06, cũ hơn nguồn … Dựng lại trước: npm run build:check»), không phải lỗi mã. CI job `mobile bundle and tests` (có `build:check`) **pass** ở cả `4167e2b` và `1f2aa74`; log tác giả 654/654. |
| Backend pytest | `python3 -m pytest services/api/tests -q -p no:cacheprovider` | `2221 passed, 632 skipped, 5170 subtests passed in 181s` (Postgres skip vì không có URL — skip không phải xanh; CI job PostgreSQL Repository **pass** ở cả hai SHA) |
| Root tests (một phần) | `python3 -m pytest tests -q --ignore=<file nào nhắc adb/emulator/docker>` | `677 passed, 22 skipped` — **danh sách ignore rộng** (loại cả `test_chat_lieu_tiles.py` vì docstring nhắc «emulator»; ca đó chạy riêng ở trên). Lượt đầy đủ lấy từ CI: 3073 passed / 669 skipped, đỏ đúng 5 ca android như `main`. |
| Repo guard | `python3 scripts/repo_guard.py tree HEAD` · `range 4259407 1f2aa74` | «passed tracked tree: 1516 file scan(s)» · «passed commit range: 38855 file scan(s) in 26 commit(s)» (ở `4167e2b`: 25 commit, 37339 scan, cũng pass) |
| Ruff | `cd services/api && ruff check <4 file đổi>` · `ruff format --check` | check: `I001` ở `scripts/sinh_token_ui_v2.py` (config services/api) / sạch với config mặc định; format: **`4167e2b` 3 file would reformat**, `1f2aa74` sạch |
| Binary mới | `git diff --name-only --diff-filter=A \| grep -Ei 'png\|jpg\|ttf\|otf'` + `sha256sum` + đọc header PNG/fontTools | Đúng 4 `.ttf` + 3 `.png`, **không** jpg/ảnh khác. sha256 cả 7 khớp `.repo-guard-allowlist.json` (mỗi mục có `reason`); `Wordmark.tsx` sha `f1d79e99…` khớp pin (`long-number`, `vn-phone` là toạ độ glyph). PNG 256×256 RGBA 8-bit, tEXt provenance (`impeccable:prompt`/`Comment`) có mặt; font có nameID 13 OFL. |
| PII/secret | grep trên 4923 dòng `+`: số ĐT VN, `+84`, email, `token/secret/bearer=`, chuỗi ≥10 chữ số ngoài lockfile, `MOBILE_*=`, tên người | 0 kết quả (một false-positive «Phạm vi»). `.env` không có. |
| WordmarkEmbossed | `grep -rn WordmarkEmbossed apps/mobile --include=*.ts,*.tsx,*.mjs,*.js,*.json` (trừ node_modules) | 0 import; file không có trong `HEAD` lẫn `origin/main`; chỉ 3 câu doc còn nhắc (suggestion ở trên) |

CI (GitHub) đối chiếu: `1f2aa74` run `3397…3363` — xanh: repo-guard, PostgreSQL 16, ruff, `RuDi driven on a real Android emulator`, api image, client headers, screens rendered, mobile bundle+tests, shared money format, vertical slice; đỏ: `api and domain` (5 ca android đỏ sẵn trên `main`, xem mục 2).

### Chất lượng test mới (skill `ai-qa-review`) — đột biến làm trên **bản sao** ở `/tmp/claude-1000/-home-lakiet-mobile/5f2c7e7c-c90f-442d-b74e-3c8a66cf7c27/scratchpad/review-566/mut/`, không đụng repo

Mỗi file chạy ≥ 3 lần xanh (hai lượt cổng + baseline của bảng đột biến), mỗi ca < 40 ms, không flaky. Import đều resolve; không dữ liệu chung chung (`John Doe`/`example.com`); hằng số ngoài (`EXDevMenuShowFloatingActionButton`) **có thật** trong `node_modules/expo-dev-menu/android/.../DevMenuPreferences.kt:73` — không phải bịa.

| File | Điều nó pin | Đột biến trên bản sao → kết quả | Mức |
|---|---|---|---|
| `tests/duong-svg.test.mjs` (4 ca) | Ngữ pháp `d` theo cách Java `PathParser` parse (arity cố định, số thập phân thường), kín, trong hộp, răng cưa hai mép, xác định | M1 `parts.push("L","Z")` (tái hiện đúng bug bảng 2026-09-05) → **đỏ** · M3 `inset=0` (x ra ngoài hộp) → **đỏ** · **M2 `so()` → `String(n)` (bỏ chống số mũ) → XANH, sống sót**: ca «vạch sáng… không số mũ» gọi `duongVachSang(1e-7)` nhưng `1e-7` là *bề rộng*; toạ độ ra `-7.9999999`, không bao giờ nhỏ tới mức JS in `e`. Lời khai «không số mũ» hiện **không ai đo**. Sửa: `duongVachSang(8 + 1e-7)` (để `w − inset = 1e-7`) hoặc export và test `so()` với `1e-7`, `1e21`, `-0`. | **trung bình** (lời khai không đo được; rủi ro thật thấp vì toạ độ ở thang dp) |
| `tests/luoi-chat-lieu.test.mjs` (4 ca) | Lưới phủ hộp, ≤ 60 view, ô = PNG ở pixel máy, không NaN khi chưa layout, ratio < 1 kẹp về 1 | bỏ vòng ngân sách → **đỏ** (2 ca) · `ceil→floor` → **đỏ** (3 ca) · bỏ guard `w>0&&h>0` → **đỏ** | thấp |
| `tests/adaptive.test.mjs` (6 ca) | Biên 600/840, chiều cao ngắn 480, hợp đồng cột/lề/rail/twoPane, đơn điệu theo bề rộng | `600→700` → **đỏ** · `twoPane: true` → **đỏ** · bỏ guard `Number.isFinite` → **đỏ**. Nit: comment «a phone on its side is compact by width» nhưng assert `"medium"` cho 800 dp (assert đúng, comment sai). | thấp |
| `tests/motion.test.mjs` (5 ca) | Bốn bậc đọc từ `tokens.json` (100/200/300/550, trần 240/650), Reduce Motion → 0 trừ instant, **tiền không đếm lên trước domain state**, celebrate một lần/sự kiện, easing hợp lệ | bỏ guard `domainStateValid` → **đỏ** · bỏ Reduce Motion → **đỏ** (3 ca) · bỏ ngân sách celebrate → **đỏ**. Ghim chặt vào `tokens.json` (đổi 200→250 là đỏ) — đúng ý «token là hợp đồng». | thấp |
| `tests/tat-nut-noi-dev-menu.test.mjs` (3 ca) | `app.json` khai plugin; manifest nhận đúng một `meta-data` kể cả chạy hai lần; không đụng meta-data khác | `"false"→"true"` → **đỏ** · thay `addMetaDataItemToMainApplication` bằng `push` thô → **đỏ** (nhân đôi). Dùng `expo/config-plugins` thật, không mock. **Không chứng minh** APK dựng ra không còn bánh răng — cái đó chỉ ảnh native chứng minh (PR có ảnh, tôi không mở). | thấp |
| `tests/test_chat_lieu_tiles.py` (6 ca) | 256² RGBA, provenance nhúng, alpha trung bình < 80; ô mực phá coral ở 0.26 (stddev 6–12); `StampButton.tsx` dùng `material="mucIn"` + `opacity={0.26}`; script sinh ra đúng pixel trên đĩa | thay `muc-in.png` bằng ô giấy (phẳng) → **đỏ 2 ca** (stddev 1.27, khớp pixel) · `DO_MO_CON_DAU 0.26→0.20` → **đỏ** (kiểm chuỗi nguồn). Rủi ro `importorskip("PIL")` → skip im lặng: **đã loại** bằng số đếm CI (+6 passed, 0 skip mới). Ca đọc chuỗi nguồn `.tsx` là cố ý (đổi opacity mà không đo lại thì đỏ). | thấp |
| `services/api/tests/web/test_contrast_floor.py` (đổi) | `KIT` = `ui.tsx` + mọi `ui/*.tsx` nối bằng `export {}` boundary; thêm viền `CoverButton` trên `cover` vào `interactive_boundaries()` | Lập luận từ assertion (không đột biến file repo): regex `borderColor:\s*colors\.(\w+)` đọc `coverLineStrong` từ chính `CoverButton.tsx`; đổi sang `coverLine` (`#3a3f63`/`#1d2140` ≈ 1.5:1) hay bỏ export → đỏ. Điểm yếu nhỏ: `kit_component` lấy **lần xuất hiện đầu** trong `[ui.tsx, *sorted(ui/*.tsx)]`, trùng tên sẽ bị `ui.tsx` che; `StampButton`/`Washi` (mực tĩnh trên coral, 5.41:1) nằm ở bảng «Tầng thương hiệu» viết tay của DESIGN.md, không phải bảng sinh — chưa có cổng đo. | thấp |

Sáu chiều: **Readability** rõ, tên ca nói lời khai; **Reliability** thuần/xác định, chỉ tiles phụ thuộc Pillow (đã kiểm không skip trên CI); **Diagnostic** thông báo mang giá trị đo (`d.slice`, stddev, `${w}x${h}@${ratio}`); **Design** dùng `for` quét tham số trong thân ca thay vì bảng dữ liệu — một ca đỏ khó biết cỡ nào hỏng (nhỏ); **AI-generated** vòng khép kín tác giả viết cả impl lẫn test — bù bằng điểm đột biến **15/16 mutant bị bắt**, 1 sống sót (số mũ) đã nêu; **Coverage** có biên và ca âm (NaN, 0, ratio < 1, chiều cao ngắn, Reduce Motion, chạy hai lần, ô phẳng).

### Kiểm tra thực chất khác

- **Maestro flow 10** (`centerElement: true → false` ở đúng một `scrollUntilVisible`): **de-flake, không phải nới lời khai**. Chuỗi khẳng định giữ nguyên: `scrollUntilVisible` (Maestro mặc định `visibilityPercentage` 100) → `tapOn "Xác nhận cách chia"` → `extendedWaitUntil visible "Quyết toán chuyến đi"` → `assertVisible "919.583đ"` + `assertNotVisible "1.106.250đ"` + tổng bill 1.280.000đ. Doc §8 ghi bốn biến thể (căn giữa 100 % đỏ · 80 % đỏ · không căn giữa xanh · vuốt ×3 xanh) và hierarchy; tôi đối chiếu `flow10-maestro-hierarchy.json` trong scratchpad tác giả: nút `[42,2180][1038,2316]` trên màn 2400 — đúng «phần tử cuối nội dung cuộn, trọn trên màn». Không chạy lại Maestro (không đụng emulator).
- **Ownership**: chỉ `apps/mobile/**`, `services/api/app/web/static/guest.css`, `services/api/tests/web/*`, `packages/shared/tokens.json`, `DESIGN.md`, `.impeccable/*`, docs/ADR, `.repo-guard-allowlist.json`, `.gitignore`, và ba file mới ở gốc (`scripts/sinh_token_ui_v2.py`, `scripts/sinh_chat_lieu_ui_v2.py`, `tests/test_chat_lieu_tiles.py`). Đúng như PR khai.
- **Tab bar tự vẽ** (`RudiTabBar`): 4 tab có `accessibilityRole="tab"` + `selected`, FAB `role="button"` «Tạo mới» — không mất điều hướng (bẫy đếm role đã ghi trong memory).
- **`DemoBadge compactLabel`**: chữ ngắn «Demo»/«Nháp» nhưng `accessibilityLabel` giữ nguyên câu đủ → flow Maestro khớp theo content-desc vẫn đúng.

### Mô tả PR — đối chiếu

| Lời khai | Kiểm |
|---|---|
| tsc · npm test 654/654 | tsc rc=0 tại chỗ; 654 ca đúng, 652 pass tại chỗ vì tôi bỏ `build:check`; CI bundle+tests pass cả hai SHA |
| pytest gốc 3093 passed / 654 skipped | Log tác giả có dòng đó; tôi không chạy đủ lượt gốc (ba file android có thể giết emulator thật — memory). CI: 3073/669 với 5 ca android đỏ **sẵn trên main** |
| pytest web 42 · contrast floor đọc `ui/**` · 52 cặp ≥ 4.61 | 42 đúng; đọc `ui/**` đúng; **50** cặp chứ không 52 |
| screens-reachable 38/38 · hex/em-dash/vòng import · contract/routes/actor/CORS | Đúng hết |
| ruff trên file đổi | **Sai ở `4167e2b`** (CI format đỏ) — đúng ở `1f2aa74` |
| repo guard tree + range 24 commit; font/wordmark/ba ô pin allowlist | Pass; 25/26 commit; pin khớp sha |
| Native head gộp: light XANH 19 ảnh · dark/1.3 XANH 19 · OTP `--ai` XANH 14 flow 81 ảnh canary đỏ đúng chỗ · tablet mini-bảng | **Chỉ đọc log** `rc-merged-{light,dark13,otp,otp-ai}.log`: ba dòng cuối «XANH: bảng qua (1 lượt)… canary đỏ đúng thiết kế» với dấu vân `feb647a-…`/`f30453f-…`; `rc-merged-otp.log` (không `--ai`) ĐỎ flow 30/32 rồi `--ai` xanh — khớp lời PR. Không phải bằng chứng của tôi. |
| Hai lỗi chỉ emulator bắt (Reanimated `transform: undefined`, path «L Z») | Test node cho «L Z» có và bắt được (M1); `PressScale`/`Stamp`/`Washi` chỉ spread `transform` khi có giá trị — đúng bài học memory |
| Sự cố 14:47 đụng emulator chung của lane `wt-m10` | Tự khai; ngoài khả năng kiểm |
| ADR-0020 «ĐỀ XUẤT»; «UI-0 có thể merge vì không đổi màn» | Khai đúng trạng thái; mâu thuẫn với nội dung PR như mục 1 ở trên |

### Không kiểm được / ngoài phạm vi review này

- Bảng native (light/dark 1.3/OTP/tablet), APK dev-client «superset» trên emulator-5554, ảnh bàn giao `~/rudi-anh/20260905-UI0/` (27 mục, tồn tại, không mở), verdict finish reviewer (`.impeccable/review/` 15 PNG, gitignored) — tất cả đọc như **lời khai của tác giả**, không chạy lại (không đụng adb theo ràng buộc).
- iOS (font name table trùng — xem suggestion), máy thật, tablet dark.
- Tầng Postgres tại chỗ (skip); dựa CI job PostgreSQL 16 pass.
- Lượt `pytest` gốc **đầy đủ** tại chỗ (loại các file nhắc adb/emulator/docker vì có ca từng giết emulator thật); dựa CI cho phần đó.
- Kiểm thử của agy trước merge («agy test trước merge theo luật đội», doc §10) — không thuộc review này; worktree `/tmp/agy-pr-566` (detached `4167e2b`) đang tồn tại, tôi không đọc kết quả.
- Reviewer là một instance Claude context mới; ADR-0007 «không tự review PR của chính mình» — merger tự cân nhắc theo cách đội đang áp dụng (memory: approve chéo).

### Hiện vật review

`/tmp/claude-1000/-home-lakiet-mobile/5f2c7e7c-c90f-442d-b74e-3c8a66cf7c27/scratchpad/review-566/`: `full.diff` (4167e2b), `added-lines.txt`, log từng cổng (`pytest-web.log`, `pytest-tiles.log`, `pytest-backend.log`, `pytest-root.log`, `guard-*.log`, `node-*.log`, `h2-node-*.log` = lượt trên 1f2aa74, `tsc-*.log`, `screens-reachable.log`, `check_*.log`), `mut/` (bản sao đột biến + `run.sh` + log), `old-head/`, `new-head/` (ba file Python hai SHA để so AST/ruff).


## 3. Reviewer context mới — phụ lục delta `1f2aa74..991b3ea`

## APPROVE

**Phụ lục cho PR #566 — delta `1f2aa74..991b3ea` (một commit).** APPROVE của bản `verdict.md` **giữ nguyên** cho `991b3ea`. Chỉ review `git -C /home/lakiet/wt-ui0 diff 1f2aa74 991b3ea`; worktree đang ở `991b3ea`, `git status` rỗng. Read-only, không adb, không giết tiến trình.

### Phạm vi delta (đọc toàn bộ)

8 file, +30/−13: `.impeccable/design.json`, `DESIGN.md`, `apps/mobile/assets/fonts/README.md`, `apps/mobile/src/rudi/screens/Welcome.tsx`, `apps/mobile/src/rudi/ui/Money.tsx`, `apps/mobile/tests/duong-svg.test.mjs`, `docs/decisions/ADR-0020-…md`, `packages/shared/tokens.json`. Không đụng `duong-svg.ts`, allowlist, binary, đường Codex.

### Từng lời khai của commit — kiểm, không tin

| Lời khai | Kiểm trên diff/cây | Kết quả |
|---|---|---|
| ADR-0020 dòng 3 mô tả đúng thực tế, vẫn ĐỀ XUẤT | Dòng mới: «UI-0 + UI-1 … đi chung một PR (#566) theo uỷ quyền của Lead 13:0x 05/09 (§5 direction-round) **và lệnh merge trực tiếp của Lead tối 05/09**; các lát UI-2 trở đi chờ Lead đổi dòng này». Trạng thái vẫn 🟡 ĐỀ XUẤT. | Đúng ý điểm 1 của tôi (không còn câu «UI-1 không merge trước»). **Một mệnh đề tôi không kiểm được từ repo:** «lệnh merge trực tiếp của Lead tối 05/09» — không có hiện vật trong cây; ghi nhận là lời khai. Không phải blocker: Lead đọc `main` và tự thấy dòng này. |
| §2.3 khớp fonts/README (nạp runtime `useFonts`, plugin không nhúng) | §2.3 mới: «nạp runtime bằng `expo-font` (`useFonts`, `src/rudi/fonts.ts`) … plugin `expo-font` khai trong `app.json` không nhúng font lúc build». Khớp `src/rudi/fonts.ts` (`useFonts` + `require`) và README. | Đúng. |
| DESIGN.md hai chỗ + design.json: WordmarkEmbossed «đã xoá ở 5cc57d2» | `DESIGN.md:587` và `:788-789` đổi; `design.json` `narrative` đổi «bị reviewer loại; đã xoá khỏi cây ở 5cc57d2». `git ls-tree HEAD` không còn file này (đã kiểm ở verdict trước). | Đúng. |
| tokens.json `type._` viết lại; design.json sinh lại, chỉ khối `type` khác; contrast **byte-identical** | So JSON `git show 1f2aa74` vs `991b3ea`: top-level key khác = `type` (chỉ `type._`) và `narrative` (câu WordmarkEmbossed ở trên); `contrast` **giống hệt** (`json.dumps(sort_keys)` bằng nhau); `design.type == tokens.type`, `design.color == tokens.color`, `design.motion == tokens.motion` đều `True`. Diff thô của design.json đúng 2 dòng `-/+` ×2. | Đúng (kèm `narrative`, là chỗ WordmarkEmbossed đã khai riêng). |
| fonts README 527 → 597 glyph | Dòng đổi «đủ 597 glyph (fontTools)». fontTools đếm 597 ở verdict trước. | Đúng. |
| `duong-svg.test.mjs`: pin lời khai «không số mũ» bằng `duongVachSang(8 + 1e-7)` = `"M 8 1.5 L 0 1.5"` | Hai assertion mới đúng như khai. Toán: `w − inset = 1e-7` → `so()` = `(1e-7).toFixed(2)` = `"0.00"` → `"0"`. `1e21` không nằm trong miền dp — chấp nhận lý do. | Đúng; xem mục đột biến. |
| `Money.tsx` `accessibilityLabel` = giá trị chốt | Thêm `const textCuoi = withSign(dinhDangTienVnd(Math.abs(vnd)), vnd, sign)`; `accessibilityLabel={textCuoi}`; chữ hiển thị vẫn `text` (khung đếm). Cùng formatter, cùng luật dấu. | Đúng. |
| `Welcome.tsx`: `dangMo` ref chặn tap thứ hai; `useFocusEffect` reset guard + `lift.value = 0` | `openCover`: `if (dangMo.current) return; dangMo.current = true;` trước `withTiming`/`setTimeout(router.push)`. `useFocusEffect(useCallback(() => { dangMo.current = false; lift.value = 0; }, [lift]))`. | Đúng. Luật hook: mọi hook (`useRouter`, `useSafeAreaInsets`, `useAdaptiveLayout`, `useMotion`, `useRudiTheme`, 3×`useState`, `useSharedValue`, `useRef`, `useFocusEffect(useCallback)`, `useAnimatedStyle`) đứng trước `return (` duy nhất của component (dòng 52 của thân hàm); `return` sớm duy nhất nằm **trong** handler `openCover`, không phải thân component. `useFocusEffect` có thật: `expo-router/build/exports.d.ts:19`. `lift` ổn định làm dependency: Reanimated `useSharedValue` = `const [mutable] = useState(() => makeMutable(value))` (`lib/module/hook/useSharedValue.js:24-26`) → cùng object qua mọi render → callback `useCallback` ổn định → effect chạy đúng một lần mỗi lần focus. Reduce Motion: `ms = 0`, push tức thì, guard vẫn chặn tap kép, reset khi quay lại. |

### Cổng chạy lại trên `991b3ea` (worktree sạch, `/home/lakiet/wt-ui0`)

| Cổng | Kết quả |
|---|---|
| `npx tsc --noEmit` (Money/Welcome đổi) | rc=0 |
| `npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs` | rc=0 |
| `node --test tests/duong-svg.test.mjs` (test đổi) | 4/4 |
| `node --test tests/{dau-gach-dai,rudi-khong-hex,vong-import,motion}.test.mjs` | 3/3 · 3/3 · 3/3 · 5/5 (không em-dash mới trong Welcome/Money; import `useFocusEffect` không tạo vòng) |
| Toàn bộ node trừ e2e, không `build:check` | `654 tests · 652 pass · 2 fail` — vẫn đúng hai guard bundle cũ của `base-url.test.mjs` («bản web … dựng lúc 20:15:06, cũ hơn nguồn … tokens.json sửa lúc 22:43:03» = mtime của lần checkout 991b3ea), không phải lỗi mã; CI job `mobile bundle and tests` **pass** trên `991b3ea` |
| `python3 -m pytest services/api/tests/web -q` (DESIGN.md/tokens.json đổi) | `42 passed, 179 subtests passed` |
| `python3 -m pytest tests/test_chat_lieu_tiles.py -q` | `6 passed` |
| `python3 scripts/check_screens_reachable.py` (Welcome đổi) | `38/38 màn có đường render từ cửa vào · 0 pin · 190 file đã đọc` |
| `check_api_contract` · `check_server_routes_called` · `check_actor_headers` · `check_cors_contract` | khớp · không route bỏ rơi · 209 lời gọi có X-Actor-ID · preflight qua |
| `python3 scripts/repo_guard.py tree HEAD` · `range 4259407 991b3ea` | «passed tracked tree: 1516 file scan(s)» · «passed commit range: 40371 file scan(s) in 27 commit(s)». Năm file doc/token đổi **không** file nào sha-pinned trong allowlist. |
| CI GitHub trên `991b3ea` (lúc viết) | 10 pass (repo-guard, PostgreSQL 16, ruff, mobile bundle+tests, vertical slice, screens rendered, client headers, shared money format, api image, RuDi emulator job) · `api and domain` **pending** — kỳ vọng cùng 5 ca `test_android_emulator_may_ket.py` đỏ sẵn trên `main` như hai run trước; không chờ. |

### Đột biến — M2 chạy lại trên bản sao (`mut/`, dist-test dựng lại ở 991b3ea; `duong-svg.ts` không đổi)

| Bản | Kết quả với test **mới** |
|---|---|
| `base2` (không đột biến) | 4/4 xanh |
| **M2 `so()` → `String(n)`** (mutant sống sót ở verdict trước) | **ĐỎ 1/4** — đúng ca «vạch sáng…»: `actual 'M 8 1.5 L 9.99999993922529e-8 1.5'` vs `expected 'M 8 1.5 L 0 1.5'`. Lời khai «không số mũ» giờ **được đo thật**. |
| M1 `push("L","Z")` | đỏ 1/4 (như trước) |
| M3 `inset = 0` | đỏ 1/4 (như trước) |

Điểm đột biến toàn PR: **16/16 mutant bị bắt** (trước: 15/16).

### Còn mở từ verdict trước (đều là suggestion, commit này không nhắm tới — không chặn)

Bảng `name` bốn `.ttf` trùng tên (rủi ro iOS, ngoài phạm vi) · `Money.tsx`/`Avatar.tsx` import từ cây legacy (`ke-hoach.ts`, `ban-be.ts`) · `Sheet.tsx:50` đọc `progress.value` trong render · `I001` ở `scripts/sinh_token_ui_v2.py` dưới config `services/api` (CI dùng config mặc định nên xanh) · `test_chat_lieu_tiles.py` dùng `Image.getdata` (deprecation) · `kit_component` lấy lần xuất hiện đầu · `StampButton`/`Washi` 5.41:1 nằm ở bảng viết tay, chưa có cổng đo · mô tả PR «52 cặp» (thực 50).

### Không kiểm

Bảng native light đang chạy trên `991b3ea` (không chờ, không đụng adb); QA của agy; mệnh đề «lệnh merge trực tiếp của Lead tối 05/09» trong ADR-0020 dòng 3; job CI `api and domain` còn pending.

### Kết luận

Commit `991b3ea` làm đúng và chỉ đúng những gì nó khai; không thêm hành vi mới ngoài hai sửa nhỏ đã kiểm (guard tap kép + reset lift; `accessibilityLabel` giá trị chốt), mọi cổng liên quan xanh, mutant sống sót đã bị bắt. **APPROVE giữ nguyên cho `991b3ea`.**

