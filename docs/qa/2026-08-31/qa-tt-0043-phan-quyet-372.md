# PASS

**Lý do, trước chi tiết.** Bản vá đúng và tôi tái lập được cả hai chiều **trên máy
chủ sống, qua HTTP thật**, không chỉ trong test: gỡ riêng `repository.py` ra thì
mốc "đã tới" biến mất đúng như báo cáo gốc (1 mốc → 0, id chặng đầu đổi); lắp lại
thì mốc sống (1 → 1, id chặng đầu giữ nguyên). Gộp lên `main` hiện tại không làm
đỏ cổng nào. Năm ô biên mà 4 ca test của PR không chạm — bấm Lưu hai lần, đảo
ngược thứ tự, vừa xoá vừa thêm vừa đổi thứ tự trong một lần lưu, xoá sạch lịch,
và hai chặng giống hệt nhau — đều đạt, 15/15.

Có **một suggestion, không phải blocker** (mục 4): dòng `.order_by` mà bản vá thêm
vào là chịu lực, mà không ca nào trong repo gác nó.

---

## Đo trên cái gì

```
PR #372 head        5f14342704b3c83b7ec73478cc0664cd3f091241
cây gộp             8cbb230 = 5f14342 ⊕ origin/main@477cb71   (gộp sạch, 0 xung đột)
sha này             là nhánh CHƯA merge; nhánh cắt từ b56a772, không xếp chồng lên PR nào
DB                  container riêng qa43-pg :5643, migrate từ đầu tới d1e2f3a4b5c6
máy chủ đo          uvicorn dựng TỪ CHÍNH CÂY NÀY trên :8643 — không dùng 8099/8081
```

`origin/main` nhích giữa lượt (98b7b1b → 477cb71, thêm #375 và #363). Tôi đã đo
gộp **hai lần**; số dưới đây là lần thứ hai, trên `main` mới.

## 1. Cổng đã thật sự chạy

| Cổng | Kết quả | Ghi chú |
|---|---|---|
| `pytest services/api/tests tests -q` (head PR 5f14342) | **2614 passed**, 554 skipped, 4902 subtests | khớp con số PR khai |
| `pytest services/api/tests tests -q` (cây gộp 8cbb230) | **2615 passed**, 554 skipped, 4896 subtests | |
| `tests/postgres` + `MOBILE_REQUIRE_POSTGRES_TESTS=1` (cây gộp) | **497 passed**, **0 skipped**, 87.58s | khớp con số PR khai |
| `apps/mobile && npm test` (cây gộp) | **800 pass, 0 fail, 0 skipped** | |
| `scripts/e2e_slice.sh` — lát cắt dọc tiền | **7 pass, 0 fail, 0 skipped**, 2163ms | chạy thật, không phải đường `t.skip` |
| `repo_guard.py tree HEAD` | passed, **1139 file scan(s)** | |
| render migration ra DDL (không cần DB) | `ok` | |

`0 skipped` ở hai dòng giữa là phần đáng đọc: tầng thật đã chạy, không phải bỏ qua
im lặng rồi thoát mã 0.

## 2. Đối chứng: lỗi CÓ trước bản vá

**Ở tầng test.** Gỡ đúng `repository.py` bằng `git apply -R`, giữ nguyên test:

```
4 failed, 17 passed in 5.55s
FAILED test_adding_a_stop_keeps_the_checkins_of_the_stops_that_did_not_change
FAILED test_reordering_the_timeline_carries_each_checkin_with_its_stop
FAILED test_a_stop_dropped_from_the_new_plan_takes_only_its_own_checkins
FAILED test_editing_a_stop_drops_the_checkins_of_the_stop_it_replaced
```

Lắp lại: `21 passed`. Đúng bốn tên PR khai, đúng con số PR khai.

**Ở sản phẩm.** Đây là phần test không thay được. Cùng một máy chủ, cùng một
đường đi người dùng đã báo (`docs/claude/2026-08-30/qa-tt-0038…` mục 3.3), khác
mỗi việc có hay không có bản vá:

```
                        KHÔNG vá            CÓ vá
lưu lịch 2 chặng        200                 200
bấm "Đã tới" chặng đầu  201                 201
GET /checkins           1 mốc               1 mốc
thêm 1 chặng vào cuối   200                 200
GET /checkins           0 mốc  ← mất        1 mốc  ← sống
id chặng đầu giữ nguyên False               True
```

## 3. Thăm dò — năm ô 4 ca test của PR không chạm

Trên máy chủ sống, 15/15 assert đạt:

| Ô | Kết quả |
|---|---|
| Bấm Lưu **hai lần** cùng một lịch (double-tap) | 200/200, mốc còn, id chặng không đổi |
| **Đảo ngược** toàn bộ thứ tự 4 chặng | 200, giữ đủ 2 mốc, mỗi mốc vẫn bám đúng chặng của nó |
| Vừa đổi thứ tự **vừa xoá một vừa thêm một** trong cùng một lần lưu | 200 — không nổ `uq_outing_stops_position`; chỉ mốc của chặng bị xoá đi theo |
| Xoá **sạch** lịch trình | 200, 0 chặng, 0 mốc |
| **Hai chặng giống hệt nhau**, mốc ở chặng trùng thứ hai | mốc còn nguyên và **vẫn ở đúng chặng thứ hai**, không nhảy sang chặng khác |

Ô cuối là ô tôi nghi nhất, vì cả lập luận thiết kế của PR đặt trên câu "mất một
mốc còn thật thà hơn hiển thị một mốc sai". Ghép theo nội dung mà có hai chặng
nội dung y hệt là đúng chỗ để một mốc bị gán nhầm. Nó không bị.

## 4. Suggestion — `.order_by` là dòng chịu lực mà không ca nào gác

Không phải blocker: code đang ship **đúng**. Nhưng đây là một lỗ hổng thật, và tôi
đo được nó chứ không đoán.

Đảo đúng một dòng bản vá thêm vào —
`order_by(OutingStop.position)` → `order_by(OutingStop.position.desc())`:

```
probe của tôi   ĐỎ:  "moc VAN o dung chang thu hai" -> dang o vi tri 0
21 ca của PR    XANH: 21 passed in 6.00s
```

Đột biến này biến hành vi thành **gán mốc sang chặng khác** — đúng cái failure mode
mà phần "Giới hạn còn lại" của PR nói là lý do không ghép theo vị trí. `existing_stops`
mất thứ tự thì `same.pop(0)` không còn giữ được thứ tự tương đối của các chặng trùng
nội dung. Repo hiện không có ca nào bắt được điều đó.

- **Dẫn chứng:** hai dòng kết quả ngay trên, tái lập bằng một lần sửa `.desc()`.
- **Hậu quả:** một lần refactor "dọn dẹp query" sau này gỡ `order_by` đi sẽ đi qua
  toàn bộ cổng mà không ai biết, và sản phẩm hiển thị *người này đã tới chỗ kia*.
- **Tiêu chí gỡ:** thêm một ca ở `tests/postgres` dựng lịch có hai chặng trùng
  nội dung, check-in ở chặng trùng thứ hai, lưu lại, khẳng định mốc vẫn ở vị trí 1.
  Ca đó phải đỏ khi `order_by` bị gỡ.

Không chặn merge. Xếp vào hàng đợi backend.

## 5. Ca test bị xoá — kiểm riêng, và việc xoá là đúng

PR gỡ `test_rewriting_the_timeline_drops_the_checkins_of_the_old_plan`. Tôi đọc bản
`b56a772` của nó: ca này lưu lại **chính `PM_TIMELINE` không đổi một chữ nào** rồi
khẳng định `checkins == []`. Tức là nó ghim đúng con bug như thể là lựa chọn có chủ
ý. Gỡ nó là sửa cổng, không phải nới cổng.

Quét lại toàn bộ `services/api/app`: chỉ còn đúng một chỗ nhắc hành vi cũ, và nó
nói ở **thì quá khứ** ("used to delete and re-insert"), trong docstring mới của
`OutingStopCheckin`. Không còn chỗ nào mô tả hành vi cũ như hiện tại.

## 6. Ô CHƯA quét — phần quan trọng nhất của báo cáo

- **Giao diện.** Tôi đo `PUT /outings/{id}/timeline` và `GET /outings/{id}/checkins`
  qua HTTP. Tôi **không** mở màn lịch trình trong app để xem nút "Đã tới" vẽ lại
  đúng sau khi lưu. Bug gốc được phát hiện từ giao diện; bản vá tôi mới chỉ chứng
  minh ở tầng máy chủ.
- **Đồng thời.** Hai người cùng lưu lịch trình một lúc, hoặc một người bấm "Đã tới"
  đúng lúc người kia lưu lịch. Không quét. `parking` đọc `max(position)` rồi mới ghi
  — hai giao dịch chồng nhau ở đó là câu chỉ khoá thật trả lời được.
- **Giới hạn PR tự khai** (đổi chữ một chặng vẫn mất mốc của nó): tôi xác nhận nó
  được ghim bằng một ca test **hành vi thật**, không phải một dòng comment. Nhưng
  người dùng có chấp nhận được giới hạn đó không thì không phải câu QA trả lời được.
- **Mã QR quét bằng app ngân hàng thật.** Vẫn chưa ai làm. Không liên quan PR này,
  nhưng còn nguyên trong danh sách chưa quét và chỉ leader đóng được.

## 7. Phán quyết

**PASS.** Không blocker nào thuộc 5 loại của charter. Sai tiền: không đụng — lát
cắt dọc tiền chạy thật, 7/7. Riêng tư: không nới bề mặt nào. Mục 4 là suggestion
kèm tiêu chí gỡ chặn, xếp hàng đợi backend.

Digest này không phải bằng chứng tự thân. Mọi lệnh ở mục 1 chạy lại được trong cây
sạch, và tôi đã ghi rõ nó chạy trên máy chủ nào và DB nào.
