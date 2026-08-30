# Phán quyết QA — PR #333 (cổng `server-routes`)

**FAIL**

**Lý do (đọc trước phần chi tiết):** bản thân cổng thì ĐÚNG — 7/7 đột biến bị bắt,
có đối chứng dương, hai mẫu số đều được gác. Nhưng **hiện vật nộp lên không merge
được**: nhánh ở sau `main` 11 commit, `scripts/gate.sh` xung đột, và khi gộp lên
`main` hiện tại thì cổng **ĐỎ với 6 route thật** mới merge vào từ #133/#303. Lead
bấm merge bây giờ là `make gate` trên `main` đỏ ngay. Tiêu chí gỡ chặn ở cuối, rẻ.

Đo tại: nhánh PR `8241e2455931f29d777c6df7b9a72cd17e684595`
Gộp thử lên: `main@267971e` (merge-base `8b6f847`, PR thiếu 11 commit của main)
SHA này: **nhánh CHƯA merge**; kết quả gộp là cây tôi tự dựng, không phải bản tác giả đẩy.

Xung đột khi gộp: `scripts/gate.sh` — `main` thêm chặng `demo-watch`, PR thêm
`server-routes`. Tôi giải bằng hợp (union) để đo tiếp. **Tác giả phải tự giải lại**;
bản giải của tôi không phải bản để merge.

---

## 1. Cổng có thật sự bắt được không — 7 đột biến

Nền đo: cây gộp `main@267971e ⊕ #333`. Vì cây gộp ĐỎ sẵn (6 route), tôi ghim tạm 6
route đó vào `.server-routes-uncalled.json` để có **nền XANH (exit 0)**, rồi mới đột
biến. Không có nền xanh thì mọi đột biến đều "đỏ" và bảng không phân biệt được gì.
Ghim tạm đã gỡ; file trong PR không bị sửa.

| # | Đột biến | Mong đợi | Đo được | Kết |
|---|---|---|---|---|
| M1 | Thêm route mới không màn nào gọi | ĐỎ + nêu tên | `exit 1`, nêu đúng tên | **BẮT** |
| M2 | Route mới chỉ được nhắc trong **comment** | vẫn ĐỎ | `exit 1`, nêu đúng tên | **BẮT** |
| M3 | Route mới **có** người gọi thật (`fetch`) | XANH | `exit 0` | **ĐỐI CHỨNG DƯƠNG** |
| M4 | Phá bộ đọc client (`tokenize` trả `[]`) | không được XANH | `exit 2`, từ chối chạy | **BẮT** |
| M5 | Phá mẫu số máy chủ (`load_openapi` → `{"paths":{}}`) | không được XANH | `exit 2`, từ chối chạy | **BẮT** |
| M6 | Mục nợ thiếu `reason` | `exit 2` | `exit 2` | **BẮT** |
| M7 | Gỡ người gọi thật của `/expenses` trong `apps/mobile/src` | ĐỎ + nêu tên | `exit 1`, nêu `/expenses` **và** `/expenses/{expense_id}/confirm` | **BẮT** |

**M3 là hàng quan trọng nhất của bảng.** Một cổng luôn đỏ cũng cho 6/6 "BẮT" ở các
hàng kia. M3 chứng minh nó phân biệt được có/không có người gọi, nên các hàng đỏ
mới có nghĩa.

**M4/M5 là chỗ phần lớn cổng trong repo này đã chết.** Khi bộ đọc hỏng, mẫu số về 0
và cổng in "0 route không ai gọi" rồi `exit 0` — xanh rỗng. Script này **tự từ chối**:

```
KHÔNG CHẠY ĐƯỢC: không đọc được đường dẫn API nào trong apps/mobile/src -- hoặc
client không còn gọi API, hoặc bộ đọc đã hỏng. Cả hai đều không phải 'đạt', và
nếu coi là đạt thì mọi route đều bị báo chết.

KHÔNG CHẠY ĐƯỢC: OpenAPI dựng được nhưng không có route nào -- từ chối coi là đạt
```

Hai câu này có sẵn trong code kèm comment giải thích. Comment không phải bằng chứng —
tôi đã đột biến từng cái và xem nó nổ thật.

## 2. Canary "xanh giả" của PR tự chứng minh trên dữ liệu sống

PR nói: khớp chuỗi con làm 4 route `/posts` bị coi là có người gọi, vì chữ "posts"
là văn xuôi tiếng Anh trong màn. Điều đó **đang xảy ra ngay lúc này** với F17:

```
apps/mobile/src/screens/chat/TheKeHoach.tsx:169  * and another way on the ballot the group votes with. */
apps/mobile/src/screens/chat/binh-chon.ts:1      /** Counting the votes. The whole of F17's correctness ...
apps/mobile/src/screens/chat/binh-chon.ts:245    // options cannot be swapped under votes
apps/mobile/src/screens/chat/TinNhan.tsx:664     * The votes come first because that is the order ...
```

Bốn dòng nhắc "votes", **cả bốn đều là comment**, không dòng nào là literal đường dẫn.
Bộ đọc khớp chuỗi con sẽ kết luận 4 route vote đã có người gọi. Script này loại comment
trước khi đọc literal nên vẫn báo chúng chết — và đó là kết luận đúng.

## 3. Sáu route ĐỎ trên `main` hiện tại — đã kiểm bằng tay, đều thật

| Route | Đến từ | Literal trong `apps/mobile/src` |
|---|---|---|
| `/contexts/{context_id}/votes` | #133 (F17) | 0 |
| `/votes/{vote_id}` | #133 (F17) | 0 |
| `/votes/{vote_id}/ballots` | #133 (F17) | 0 |
| `/votes/{vote_id}/close` | #133 (F17) | 0 |
| `/contexts/{context_id}/photos/{photo_id}/face-boxes` | #303 (F22) | 0 |
| `/bills/{bill_id}/my-items` | #303 | 0 |

Kiểm bằng `grep -rn` trực tiếp, không qua script — 0 dòng cho `face-boxes` và
`my-items`; 4 dòng cho `votes` và cả 4 là comment (mục 2).

Hai hệ quả đáng ghi:

- **F17 trùng khớp với phán quyết ở PR #321** ("F17 chưa thông đầu-cuối"). Máy chủ
  có đủ 4 route, `binh-chon.ts` đếm phiếu **trong máy**, không route nào được gọi.
  Hai lượt đo độc lập, cùng một kết luận.
- **F22 là lỗ hổng phán quyết của chính tôi.** Tôi đã PASS #303 tại `c7b55e2`
  (qa-tt-0032) và không hỏi câu "có màn nào gọi `face-boxes` không". Cổng này hỏi
  đúng câu tôi thiếu. Đây là lý do PR nên vào, không phải lý do giữ nó lại.

## 4. Cổng có được nối vào không

| Chỗ nối | Kết quả |
|---|---|
| `scripts/gate.sh server-routes` chạy thật, truyền mã lỗi | `exit 1` trên cây đỏ — **đúng** |
| `server-routes` nằm trong `STAGES` của `gate.sh` | có |
| Bước trong `.github/workflows/test.yml` (job `api`) | có, chạy `--selftest` **rồi** chạy cổng thật |
| `--selftest` nội bộ | `exit 0`, có canary xấu ĐỎ và canary sạch XANH |
| Test riêng của PR | 46 passed, 86 subtests passed |

Bước CI có nhánh bỏ qua `if [ ! -d apps/mobile/src ]` → `::notice::`. Đúng quy ước đã
có của repo cho `apps/mobile` (CLAUDE.md), và trên `main` hôm nay thư mục đó tồn tại
nên nhánh bỏ qua không kích hoạt. Không tính là lỗi, nhưng nó **là** một đường xanh
im lặng nếu sau này ai đó đổi layout.

## 5. Cổng đầy đủ trên cây gộp

```
python3 -m pytest services/api/tests tests -q
2516 passed, 547 skipped, 4887 subtests passed in 224.52s
```

547 skipped là tầng PostgreSQL (thiếu `MOBILE_TEST_DATABASE_URL`). **skipped không
phải xanh** — nhưng PR này không chạm `app/`, `db/`, `payments/`, nên tầng đó không
nằm trong rủi ro của PR. Ghi rõ là **chưa quét**, không phải "không áp dụng".

## 6. Ô CHƯA quét

- `tests/postgres` / `tests/qa` tầng live (547 ca) — chưa chạy lượt này.
- `cd apps/mobile && npm test` — chưa chạy; PR không sửa file nào của `apps/mobile`.
- `npm run test:e2e` lát cắt dọc — chưa chạy.
- Cây gộp **sau khi tác giả tự giải xung đột** — tôi chỉ đo được bản giải của mình.
- Mã QR quét bằng app ngân hàng thật — vẫn chưa ai làm, ngoài phạm vi PR này.

## 7. Blocker và tiêu chí gỡ chặn

**Loại 1 — vi phạm spec/cổng.** Gộp #333 lên `main@267971e` làm `make gate` ĐỎ.

Dẫn chứng: mục 1 (`exit 1`, 6 route) và mục 3 (kiểm tay).
Hậu quả: mọi lane chạy `make gate` trên `main` đều đỏ cho tới khi có người xử lý.

Gỡ chặn — cả ba, đều rẻ:

1. `git rebase origin/main` (hoặc merge) lên `267971e`.
2. Giải `scripts/gate.sh`: giữ **cả hai** chặng — `... client-routes server-routes
   cors ... pinned-import demo-watch shared ...`.
3. Xử lý 6 route ở mục 3 theo đúng thứ tự ưu tiên mà chính script in ra: viết màn
   gọi (đúng nhất), xoá route, hoặc ghim vào `.server-routes-uncalled.json` **kèm
   `reason` thật** — không phải câu giữ chỗ. Ghim là ghi nợ, không phải trả nợ.

Không có blocker nào khác. Chất lượng cổng: đây là cổng chặt nhất tôi đo trong tuần —
nó gác cả hai mẫu số, có đối chứng dương, và bắt được một lỗ hổng mà phán quyết
trước của tôi đã bỏ sót.

---

### Lệnh tái lập

```bash
git checkout -b thu origin/main && git merge origin/qa3/cong-route-may-chu-khong-ai-goi
# giải xung đột scripts/gate.sh bằng hợp hai danh sách STAGES
python3 scripts/check_server_routes_called.py ; echo "exit=$?"   # 1, sáu route
python3 scripts/check_server_routes_called.py --selftest         # 0
bash scripts/gate.sh server-routes ; echo "exit=$?"              # 1
python3 -m pytest services/api/tests tests -q                     # 2516 passed
```

Đột biến M4 (bộ đọc client hỏng) tái lập bằng cách chèn `return []` vào đầu
`tokenize` trong `scripts/check_api_contract.py`; M5 bằng `return {"paths": {}}` vào
đầu `load_openapi` cùng file. Cả hai phải ra `exit 2` kèm câu từ chối, **không** ra
`exit 0`.

skills dùng: `e2e-testing` (chặng 2 cổng rẻ, chặng 7 kết luận), `bug-reproduction`
(nền xanh trước, đột biến một biến một lượt, đối chứng dương M3, khôi phục sau mỗi lượt).
