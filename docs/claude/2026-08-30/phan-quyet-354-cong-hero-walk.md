# Phán quyết QA — PR #354 (cổng `hero-walk`)

**FAIL**

Lý do, trước mọi chi tiết: nửa cổng *biện minh cho sự tồn tại của PR* — đi qua mối
nối `POST /receipts/scan` → `readingFromWire()` → `POST /bills` — **không kiểm
chứng được lúc này**, và con số đầu bài "13/13" **không tái lập được**: tôi chạy
lại chính `scripts/dot_bien_hero_walk.py` ra **12/13, mã thoát 1**, với dòng đối
chứng dương C1 ĐỎ và chính script tự kết luận *"Bảng KHÔNG chứng minh được cổng
gác đúng"*. Nguyên nhân là bộ đọc bill trên máy demo đang trả **502** (3/3 lần),
**không phải lỗi của PR** — nhưng nó làm phần đắt nhất của bằng chứng thành chưa
xác nhận. Cộng thêm: chặng nằm trong danh sách mặc định và **đang báo ĐẠT trong
khi mối nối đã 502**, phán quyết nó đọc **không ràng buộc vào code** (đang xanh
nhờ `client 412c412` — không phải head của PR, không có trên main), và nhánh
**xung đột với main**.

Nói ngay phần khen, vì nó là phần đáng giá nhất của PR: **đối chứng dương C1 đã
làm đúng việc của nó.** Nếu bảng đột biến chỉ có các dòng "cần ĐỎ", lượt đo hôm
nay của tôi đã ra A1/A2/A3 toàn ĐỎ và tôi đã đọc nhầm một môi trường chết thành
một cổng có răng. C1 là thứ chặn đúng cái đó lại. Đây là hình dạng bảng đột biến
mà repo này nên nhân rộng.

---

## Đo tại đâu

```
nhánh PR    devops/cong-di-bo-duong-hero @ a2bc103f2f42
cây đã đo   CÂY GỘP  a2bc103f ⊕ origin/main@4463aeb  =  312e63b
sha này     nhánh CHƯA merge — `git merge-base --is-ancestor a2bc103f origin/main` -> CHƯA merge
            nhánh đi SAU main 9 commit
máy demo    http://127.0.0.1:8099 — /healthz 200, openapi 76 route, đủ 4 route mối nối
```

Phải đo trên cây gộp, không phải đầu nhánh — đây là luật Lead chốt lúc 22:15 sau
vụ #348.

**Gộp main vào nhánh này ĐỤNG ĐỘ:**

```
git merge origin/main
-> CONFLICT (content): Merge conflict in Makefile      (dòng .PHONY)
```

Tôi giải xung đột tại chỗ (hợp nhất hai danh sách `.PHONY`: `demo-reset` từ main +
`hero-walk hero-walk-status` từ PR) **chỉ để có cây đo được**. Tác giả vẫn phải
rebase — mọi số dưới đây đo trên cây gộp tôi tự giải, không phải trên một cây ai
đã ship.

---

## Cổng thật trên cây gộp 312e63b

```
python3 -m pytest services/api/tests tests -q
-> 2592 passed, 551 skipped, 4903 subtests passed in 255.09s        XANH

python3 -m pytest tests/test_gate_covers_every_workflow_job.py -q
-> 6 passed, 15 subtests passed in 0.15s                            XANH

scripts/gate.sh hero-walk
-> ĐẠT 1  HỎNG 0  BỎ QUA 0   (0 giây)                               XANH
   hero_walk: ĐI ĐƯỢC 33 phút trước — 16/16 chặng, http://127.0.0.1:8099,
              client 412c412, model đọc 5 món.
```

Backend không bị PR chạm; phần pytest xanh là kỳ vọng, không phải bằng chứng về
cổng này.

---

## Blocker 1 — bằng chứng đầu bài không tái lập được

*Loại: không tái lập được.*

Tôi chạy lại chính script của PR, **cách ly thư mục phán quyết** (`MOBILE_HERO_WALK_DIR=/tmp/qa39-mut`)
để không đạp lên phán quyết dùng chung của các lane khác:

```
MOBILE_HERO_WALK_DIR=/tmp/qa39-mut python3 scripts/dot_bien_hero_walk.py

ĐẠT   B1 chưa ai đi bộ bao giờ                        ĐỎ (cần ĐỎ)
ĐẠT   B2 lượt gần nhất ĐỨT                            ĐỎ (cần ĐỎ)
ĐẠT   B3 phán quyết quá cũ                            ĐỎ (cần ĐỎ)
ĐẠT   B4 phán quyết về máy KHÁC                       ĐỎ (cần ĐỎ)
ĐẠT   B5 phán quyết hỏng                              ĐỎ (cần ĐỎ)
ĐẠT   B0 ĐỐI CHỨNG: phán quyết tốt                    XANH (cần XANH)
ĐẠT   B6 xoá bài đi bộ                                mã 2 (cần 2)
ĐẠT   B7 máy cũ hơn tính năng                         mã 2 (cần 2)
ĐẠT   B8 không có máy nào                             mã 1 (cần 1)
ĐẠT   A1 readingFromWire trả 0 món                    ĐỎ (cần ĐỎ)
ĐẠT   A2 tiền không còn là số nguyên đồng             ĐỎ (cần ĐỎ)
ĐẠT   A3 scanReceipt gọi sai đường                    ĐỎ (cần ĐỎ)
HỎNG  C1 ĐỐI CHỨNG: đổi hình dạng, GIỮ hành vi        ĐỎ (cần XANH)

12/13 dòng đúng kỳ vọng.
Bảng KHÔNG chứng minh được cổng gác đúng — xem dòng HỎNG ở trên.
MUT_EXIT=1
```

Đọc cho đúng: **A1/A2/A3 ĐỎ ở lượt này không chứng minh gì cả.** Chúng đỏ vì máy
demo không đọc được bill, không phải vì cổng bắt được đột biến. C1 là dòng duy
nhất phân biệt được hai chuyện đó, và nó nói thẳng là không phân biệt được.

Nói cách khác: **9 dòng lớp B tôi tự kiểm chứng và chúng đứng vững. 4 dòng lớp A
+ C1 — đúng phần chứng minh cổng đi qua mối nối — vẫn là ô CHƯA QUÉT.**

## Blocker 2 — chặng báo ĐẠT trong khi mối nối đã đứt

*Loại: vi phạm spec/cổng.*

Mối nối đang hỏng trên máy demo, đo trực tiếp, 3/3 lần:

```
curl -X POST http://127.0.0.1:8099/receipts/scan \
     -H 'X-Actor-ID: <uuid persona demo>' \
     -F 'image=@/tmp/mobile-hero-walk-anh/ro.jpg;type=image/jpeg'

lan 1: HTTP=502 {"code":"receipt_reader_unavailable", ...}
lan 2: HTTP=502
lan 3: HTTP=502
```

Và lượt đi bộ thật cũng đứt đúng đó:

```
scripts/hero_walk.sh --url http://127.0.0.1:8099
-> HONG o chang 4/4: QUET BILL: anh -> mon (POST /receipts/scan)      WALK_EXIT=1
```

Trong khi đó, cùng lúc, cùng cây:

```
scripts/gate.sh hero-walk   ->   ĐẠT   (0 giây)
```

`gate.sh` có ghi thẳng ra hạn chế này (*"A demo that broke five minutes ago passes
this stage until the verdict ages out"*) và tôi ghi nhận sự trung thực đó. Nhưng
hạn chế được khai báo vẫn là hạn chế: **hôm nay, chặng này trong danh sách mặc
định đang trả màu xanh cho một đường hero đã 502.** Đây là ngày trước hạn, và
`make gate` là cổng duy nhất còn nghĩa khi CI chết.

## Blocker 3 — phán quyết không ràng buộc vào code

*Loại: vi phạm spec/cổng. Đây là blocker yếu nhất trong ba cái, và tôi kèm luôn
đường sửa rẻ.*

`--status` kiểm 4 thứ: có phán quyết · đúng `url` · `rc == 0` · chưa quá 24 giờ.
Nó **in ra** `client <sha>` nhưng **không so** sha đó với cây đang được gác.

`demo_watch` có `--expect-ref origin/main`, và `gate.sh` giải thích rất đúng vì
sao cần nó: *"a verdict about another box is the failure that looks most like a
pass."* Cùng lập luận đó áp cho code, nhưng đối xứng ấy không có.

Bằng chứng sống, không phải giả thiết — chính lúc tôi đo, cổng đang xanh nhờ:

```
verdict.json: "sha": "412c412"
git merge-base --is-ancestor 412c412 a2bc103f   ->   KHÔNG phải tổ tiên của head PR
```

`412c412` không phải head của PR và không có trên main. Nghĩa là màu xanh hiện tại
chứng nhận cho một cây **không ai ship**.

Và hệ quả trực tiếp — tôi đột biến chính mối nối trên cây gộp:

```
apps/mobile/src/receipt.ts:154
-   lines: wire.items.map((item, index) => ({
+   lines: [].map((item: any, index: number) => ({      # readingFromWire trả 0 món

scripts/gate.sh hero-walk   ->   ĐẠT   (0 giây)         # y hệt lúc chưa đột biến
```

Chặng chạy 0 giây và không đọc một dòng code nào, nên nó xanh với bất kỳ đột biến
nào. Điều đó đúng theo thiết kế record-and-read; cái thiếu là ràng buộc để màu
xanh của nhánh A không chứng nhận cho nhánh B.

**Đường sửa rẻ, không làm chặng đỏ trên mọi feature branch:** ghi sha vào phán
quyết (đã có) rồi ở `--status` so nó với `git merge-base --is-ancestor <sha> HEAD`.
Cùng tổ tiên thì xanh; khác nhánh thì in cảnh báo hoặc mã 2. Không tốn thêm lời
gọi model nào.

## Cần rebase

```
git merge origin/main -> CONFLICT in Makefile (.PHONY)
```

Không phải blocker theo charter, nhưng "sẵn sàng merge" hiện chưa đúng.

---

## Ô CHƯA QUÉT — phần quan trọng nhất của báo cáo

| Ô | Vì sao chưa quét |
|---|---|
| A1/A2/A3 + C1 của bảng đột biến | máy demo trả 502, không lấy được kết quả có nghĩa |
| Chặng có đỏ đúng lúc mối nối hỏng thật không | cùng lý do — chưa dựng lại được nền xanh để đột biến |
| `make hero-walk` đường hạnh phúc | chưa đi được lần nào xanh trong lượt này |
| Cổng đầy đủ (`make gate` cả danh sách) | tôi chỉ chạy chặng `hero-walk`, `pytest`, và test cổng |
| `apps/mobile && npm test` trên cây gộp | chưa chạy lượt này |
| Mã QR quét bằng app ngân hàng thật | chưa ai làm, vẫn là việc của leader (ADR-0010 mục 8) |

## Tiêu chí gỡ chặn

1. Bộ đọc bill trên 8099 trả 200 lại (**không thuộc PR này** — xem phiếu gửi devops).
2. Chạy lại `scripts/dot_bien_hero_walk.py` ra **13/13 và mã thoát 0**, có C1 XANH.
3. Rebase lên main, hết xung đột `Makefile`.
4. Blocker 3: ràng buộc phán quyết với code, hoặc Lead ghi rõ là chấp nhận rủi ro
   đó và vì sao.

Nếu Lead đi **đường 2** (PR hạ tầng: CI + review là đủ, agy hậu kiểm), thì xin ghi
rõ trong comment merge rằng lớp A của bảng đột biến **chưa ai xác nhận**, để người
đọc sau biết mức bằng chứng đang ở đâu.
