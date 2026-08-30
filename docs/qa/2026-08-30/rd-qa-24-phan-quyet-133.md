# PASS — #133 (F17 Bình chọn) tại `be574da`

> **Ghi chú khi đưa lên main (2026-08-31).** Bản gốc của phán quyết này nằm ở PR
> 321, và PR đó mang theo cả phần backend bình chọn. Phần backend ấy nay đã có
> trên main qua đường khác, nên PR này **chỉ còn tài liệu và script bằng chứng**.
> Đo tại `b4f6991`: 7 file lõi bình chọn (`routes/votes.py`, `domain/vote.py`,
> migration `d1e2f3a4b5c6`, và cả ba file test) **giống hệt từng byte** với bản
> trong PR 321. Sáu file dùng chung còn lại chỉ khác ở 8 dòng, và 8 dòng đó
> không dính gì tới bình chọn — chúng là bản **cũ** của code khác (`plan_turn`,
> `create_expense`, `session.flush`, ba cột UUID). Nói cách khác PR 321 không
> thêm được gì cho main, và gộp nó vào sẽ kéo lùi main ở đúng 8 dòng đó. Vì vậy
> PR 321 nên được đóng, không rebase.

Năm câu hỏi Lead đặt ra đều đo được trên app thật và đều đạt; riêng ca đồng thời
— cái Lead quan tâm nhất — được chứng minh là **có người gác**, vì gỡ đúng ổ khoá
đó ra thì nó đỏ ngay ở vòng đầu với đúng lỗi Lead dự đoán.

---

## Đo tại đâu

```
đo tại   be574dae792ea6ec4bf15dc735f7d84f86ce457b   (head PR #133)
sha này  là nhánh chưa merge; đã chứa origin/main (d63a4b1) qua commit merge be574da
         git merge-base --is-ancestor origin/main HEAD → "ĐÃ có main"
máy chủ  uvicorn dựng TỪ chính cây này, cổng 8232, DB riêng mobile_qa24
```

Cổng 8124 đã bị lane khác chiếm (một `http.server` trả 404 cho mọi thứ). Nếu tôi
không kiểm cổng trước khi bắn thì mọi con số dưới đây là số đo trên sản phẩm của
người khác. Cổng 8232 được xác nhận trống trước khi dựng.

DB `mobile_qa24` là DB **mới tạo**, migrate bằng `MOBILE_DATABASE_URL` (không phải
`MOBILE_TEST_DATABASE_URL` — biến TEST bị alembic bỏ qua im lặng và sẽ migrate DB
chung). Kết quả: 43 bảng, một alembic head `d1e2f3a4b5c6`.

## Cổng đã chạy

| Cổng | Kết quả |
|---|---|
| `python3 -m pytest services/api/tests tests -q` | **2239 passed, 0 failed**, 461 skipped, 4848 subtests |
| `tests/postgres` với `MOBILE_REQUIRE_POSTGRES_TESTS=1` | **410 passed, 0 skipped** |
| `apps/mobile && npm test` | **705 pass, 0 fail**, 0 skipped |
| migration render ra DDL (không cần DB) | exit 0 |
| `alembic heads` | **một head**, `d1e2f3a4b5c6` treo dưới `a7d3f2b81c56` |
| `scripts/repo_guard.py staged` | passed |

**Một lần đỏ, và nó là của tôi.** Lượt đầu `test_no_new_unformatted_file_under_tests_qa`
đỏ trên `tests/qa/qa-tt-0031/probe-cuon-lai-khi-loi.py` — file nháp **chưa commit
của chính tôi** từ lượt trước. Cổng đó quét filesystem chứ không quét cây git. Dọn
ra ngoài rồi chạy lại: 2239 passed. Không liên quan tới #133.

## Năm câu Lead hỏi

Đo bằng `tests/qa/rd-qa-24-binh-chon-be/probe_binh_chon_that.py`, qua HTTP thật.
Mọi phép đếm hàng đọc thẳng `vote_ballots` bằng một kết nối psycopg riêng, **không
đọc từ thân trả về của API** — máy chủ nói dối về cái nó vừa ghi thì probe không
đồng ý theo.

**1. Một người một phiếu.** Bỏ phiếu lần hai → HTTP 200, `replaced_previous_ballot=true`,
và bảng vẫn **đúng 1 hàng**. Hàng đó trỏ sang lựa chọn mới, `created_at` giữ nguyên
còn `updated_at` mới hơn — nên đây là UPDATE, không phải INSERT rồi xoá.

**2. Đổi phiếu trước/sau khi đóng.** Trước khi đóng: 200. Sau khi đóng: **409
`vote_closed`**, cho cả người đổi phiếu lẫn người bỏ phiếu mới, và số hàng không đổi.

**3. Hoà thì hiện hoà.** Hoà 1-1 → `is_tie=true`, `decided_option_id=null`,
`leading_option_ids` liệt kê cả hai. Hoà ba bên → liệt kê cả ba. **Đóng một cuộc
hoà không phá thế hoà** — đọc lại sau khi đóng vẫn ra hoà.

**4. Người ngoài nhóm.** Bỏ phiếu → **403**, thân đúng
`{"code":"permission_denied","detail":"is_group_member"}` — không có câu hỏi, không
có nhãn lựa chọn, không có id người trong nhóm. Số bản ghi không đổi. Đọc kết quả và
liệt kê vote của nhóm cũng 403.

**5. Ca đồng thời — câu Lead quan tâm nhất.** Không phải hai request mà **năm**
request bắn cùng một khoảnh khắc từ một `threading.Barrier`, **40 vòng**, chạy ở
cả hai hình dạng đua:

- INSERT vs INSERT (người chưa có phiếu — chính là lúc `SELECT FOR UPDATE` trên
  hàng phiếu **không khoá gì**, vì hàng chưa tồn tại)
- UPDATE vs UPDATE (người đã có phiếu)

Kết quả cả hai: đúng **một hàng** ở cả 40/40 vòng, **0 lỗi 5xx**, mọi request đều
200, và đọc kết quả sau đó luôn 200 với đúng 1 phiếu.

Thêm hai biến thể: ba người **khác nhau** bắn cùng lúc → cả ba 200, đủ ba hàng,
đếm lại ra 2-1 không hoà. Bỏ phiếu **cùng lúc với** đóng cuộc bình chọn, 10 vòng →
không 5xx, và mã trả về luôn khớp với cái đã ghi (200 ⇒ có hàng, 409 ⇒ không hàng).

**43/43 phép kiểm đạt.**

## Vì sao con số 0 đó có nghĩa — bảng đột biến

Một probe chưa bao giờ đỏ thì chưa chứng minh được nó biết đỏ. Bốn tính chất, mỗi
cái tắt **riêng** trên máy chủ thật, restart uvicorn để chắc chắn code hỏng được
nạp, rồi chạy lại đúng probe khai là phủ nó
(`tests/qa/rd-qa-24-binh-chon-be/chay_dot_bien.py`):

| Đột biến | Probe |
|---|---|
| **M1** — bỏ `FOR UPDATE` trên hàng **vote** trong `upsert_ballot` | **ĐỎ** |
| **M2** — bỏ `FOR UPDATE` trên hàng **ballot** | XANH (không bắt được) |
| **M3** — luôn CHÈN phiếu mới thay vì thay phiếu cũ | **ĐỎ** |
| **M4** — cho máy chọn hộ khi hoà | **ĐỎ** |

**M1 là kết quả đáng đọc nhất.** Gỡ ổ khoá đó ra thì ngay vòng 1, 2, 3 đều
**HTTP 500**, và log máy chủ ghi đúng nguyên nhân:

```
sqlalchemy.exc.IntegrityError: (psycopg.errors.UniqueViolation)
duplicate key value violates unique constraint "uq_vote_ballots_one_per_person"
```

20 lần 500 trong 20 vòng đột biến; **0 lần** trong 40 vòng trên cây sạch. Ba điều
rơi ra từ đó:

1. Probe của tôi **thật sự chồng lấn** request trong máy chủ — không có chuyện
   barrier không nổ và tôi đọc nhầm sự tuần tự thành sự an toàn.
2. Đúng cái Lead lo — "500 vì DUPLICATE_BALLOT" — là kết cục **có thật** nếu thiếu
   khoá. Ràng buộc `UNIQUE` một mình **không đủ**: nó biến cuộc đua thành 500 chứ
   không biến thành hành vi đúng.
3. Thứ cứu tình huống này là `SELECT ... FOR UPDATE` trên hàng **vote** (hàng đã
   tồn tại), không phải trên hàng ballot. Thiết kế đó đi vòng qua đúng cái bẫy
   "khoá hàng chưa tồn tại thì không khoá gì" mà Lead nêu.

**M2 xanh, và tôi báo nó là lỗ của probe chứ không phải điểm cộng.** Khoá trên hàng
ballot là dư thừa *đối với phép đo này*: khoá hàng vote đã tuần tự hoá mọi đường ghi
phiếu của cùng một cuộc rồi. Không phải lỗi — là hai lớp phòng thủ mà lớp ngoài đã
đủ. Nhưng nghĩa là **không phép đo nào của tôi bảo vệ được dòng đó**; ai xoá nó sau
này sẽ không bị bảng này chặn.

## Ba đường đâm thêm, ngoài đề bài

`probe_quyen_bien.py` — **11/11 đạt**:

- Người **đã rời nhóm** đổi phiếu → 403 `is_group_member`, phiếu cũ không bị ghi đè,
  đọc kết quả cũng 403.
- Thành viên **không phải người tạo** đóng cuộc → 403 `is_vote_creator`, cuộc vẫn mở;
  người tạo thì đóng được.
- Mượn `option_id` của cuộc bình chọn **khác trong cùng nhóm** → 422 `unknown_option`,
  không hàng nào được ghi, và phiếu **không bị dồn sang** cuộc kia.

Lần chạy đầu của probe này ra 3 FAIL trông như "người rời nhóm vẫn bỏ phiếu được".
Không phải: bước gỡ thành viên của tôi gọi sai — `DELETE /contexts/{id}/members/{pid}`
đòi `is_self` (rời nhóm là việc của chính người đó, admin không đá ai). Nên `binh`
chưa từng bị gỡ. **Phép thử của tôi hỏng, không phải sản phẩm.** Sửa probe, không
sửa sản phẩm; ghi chú lý do đã để lại ngay trong file.

## Ô CHƯA quét — phần quan trọng nhất của báo cáo

1. **F17 chưa thông đầu-cuối, và đây là điều Lead cần biết trước khi merge.**
   `main` **không có** `routes/votes.py`; frontend #135 đã merge từ 29/08 và đếm
   phiếu **ở client**, trên `ai_card` trong luồng tin nhắn — `apps/mobile/src/api.ts`
   không gọi `/votes` hay `/ballots` một lần nào. Tác giả #135 nói thẳng chuyện đó
   trong docstring và chừa sẵn mối nối (`tongHopBinhChon`). Nên sau khi #133 vào,
   sản phẩm có **hai bộ đếm phiếu song song** cho tới khi client được chuyển sang
   route mới. Không phải blocker cho #133 — #133 là nửa còn thiếu, và merge nó là
   điều kiện để gỡ. Nhưng đừng đọc "#133 merged" thành "F17 chạy trên app".
2. **Màn hình bình chọn chưa được quét lượt này** — không chụp ảnh, không axe,
   không kiểm tương phản/bàn phím. Lý do: màn hiện tại chạy trên đường client cũ,
   quét nó không nói gì về #133.
3. **Không đo dưới tải thật nhiều tiến trình.** uvicorn ở đây chạy **một worker**.
   Với nhiều worker, khoá vẫn nằm ở PostgreSQL nên kết luận không đổi về mặt lý
   thuyết, nhưng tôi **chưa đo**.
4. **Không đo hai máy chủ cùng lúc** trên cùng một DB.
5. **Không đo `outing_id`** trỏ tới buổi đi của nhóm khác qua đường HTTP (tầng
   postgres của PR có ca này; tôi không chạy lại độc lập).
6. **Dòng khoá trên hàng ballot (M2) không có phép đo nào gác.**
7. `GEMINI`/AI, tiền, VietQR: #133 không đụng tới. Ca "vòng đời bình chọn không đổi
   một hàng nào ở sáu bảng tiền" là của chính PR, tôi **không** viết lại ca đối chứng.

## Phân loại theo 5 loại blocker của charter

Không có blocker nào. Mục 1 ở trên là **thông tin điều phối**, không phải blocker:
nó không vi phạm spec/cổng, không sai tiền, không hở quyền riêng tư, không hỏng tính
hợp lệ thí nghiệm, và tái lập được.

## Verdict

**PASS.** Năm câu hỏi đều đạt trên app thật; ca đồng thời có bằng chứng hai chiều
(xanh khi có khoá, đỏ đúng lý do khi gỡ khoá). Không tự sửa môi trường: cây sản
phẩm sau bốn đột biến được xác nhận **byte-identical** với `HEAD` (`git status`
trên `services/api/` rỗng).

Chữ ký `APPROVE`/`REQUEST_CHANGES` vẫn là của người review, không phải của tôi.
