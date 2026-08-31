# FAIL #490 — cổng đỏ vì chính PR, và thước đo in đúng chữ ký PASS của báo cáo lên một reel ĐÃ TẮT

**FAIL**

Lý do, đặt trước mọi chi tiết:

1. **Cổng đỏ, và đỏ vì đúng ba file của PR này.** `tests/test_qa_scripts_are_ruff_formatted.py`
   trên nền main `7fff89c`: **4 passed**. Trên `f18cbeb`: **1 failed** — ruff ghim từ chối
   `do-grounding-reel.py`, `doi-chung-chia-tien.py`, `nem-anh.py`. Cây gộp không xanh.
2. **`do-grounding-reel.py` in `grounding: 5/5` + `injection: 5/5` + `exit 0` cho một reel
   đã tắt hẳn** (`reeled=false`, `picks=[]` — đúng trạng thái khi thiếu `GEMINI_API_KEY`),
   và cho một reel mà **payload injection đang là title của cả 5 lượt**. Hai con số đó là
   hai con số báo cáo đặt trước kết luận F37.
3. **Khoá Gemini trong `dung-stack.sh` chỉ tìm thấy được từ worktree của chính tác giả.**
   Chạy từ gốc repo thật `/home/lakiet/mobile` — nơi `CLAUDE.md` bảo chạy — đường dẫn giải
   ra `/mobile/.env`, không tồn tại. Ghép với (2): **chạy lại đúng theo hướng dẫn, từ đúng
   chỗ hướng dẫn nói, ra đúng con số PASS của báo cáo với AI đã tắt.**
4. **Ba nhóm số trong báo cáo không có hiện vật để ai khác chạy lại**: `plan.json` (chính là
   câu trả lời "6 lần bấm / 7 lần bấm") không được commit; khối "Chạy lại" còn 5 chỗ trống;
   bảng `ground_reel` 5 dòng không có script nào sinh ra nó.

Cái tôi **không** kết luận: tôi không chứng minh được F37/F38 là vỏ. Đối chứng âm của F38
(`405B → 66B` sau khi xoá) là một phép phân biệt thật và tôi không có bằng chứng nào chống
lại nó. Phát hiện ở đây là về **năng lực phân biệt của dụng cụ** và về **đường chạy lại**,
không phải về sản phẩm.

---

## Đo tại đâu

```
đo tại   f18cbeb  (qa3/do-ruot-f37-f38, head PR #490 lúc nhận việc)
sha này  là nhánh CHƯA merge; cha trực tiếp là 7fff89c = origin/main
nền so   7fff89c  (origin/main)
cây đo   /tmp/qa490 (worktree sạch tại f18cbeb) · /tmp/qa490base (worktree sạch tại 7fff89c)
```

`f18cbeb` đúng là main + 1 commit, không cần rebase. `apps/mobile` và `services/api` có
tree hash **giống hệt** main (`ac444003…`, `642d6e52…`) — PR không sửa dòng sản phẩm nào,
đúng như mô tả.

---

## Blocker 1 — cổng đỏ vì chính PR (loại: vi phạm spec/cổng)

```
$ cd /tmp/qa490base && python3 -m pytest tests/test_qa_scripts_are_ruff_formatted.py -q
4 passed in 1.43s                                    # nền main 7fff89c

$ cd /tmp/qa490   && python3 -m pytest tests/test_qa_scripts_are_ruff_formatted.py -q
1 failed, 3 passed in 1.46s                          # f18cbeb
  ruff format rejects these files under tests/qa/:
    tests/qa/qa3-123758-ruot-f37-f38/do-grounding-reel.py
    tests/qa/qa3-123758-ruot-f37-f38/doi-chung-chia-tien.py
    tests/qa/qa3-123758-ruot-f37-f38/nem-anh.py

$ cd /tmp/qa490 && python3 -m pytest services/api/tests tests -q
1 failed, 2880 passed, 597 skipped, 5272 subtests passed in 328.61s
```

Nền xanh, PR đỏ, và ca đỏ gọi tên đúng ba file PR thêm vào. Cổng tự in ra lệnh gỡ chặn:

```
$(scripts/ruff_pinned.sh) format tests/qa/qa3-123758-ruot-f37-f38/do-grounding-reel.py \
  tests/qa/qa3-123758-ruot-f37-f38/doi-chung-chia-tien.py \
  tests/qa/qa3-123758-ruot-f37-f38/nem-anh.py
```

Ba file của tôi trong PR này đi qua đúng cổng đó trước khi commit — `4 passed`.

---

## Blocker 2 — thước đo không phân biệt được trạng thái nó được viện dẫn để phân biệt

Loại: **hỏng tính hợp lệ thí nghiệm**.

`do-grounding-reel.py` tính `ngoai` và `obeyed` **trên `picks`**. Reel không dựng được thì
`picks == []`, nên cả hai vòng `all(...)` đạt trên tập rỗng, và `main()` trả `0` khi
`ok_grounded and ok_khong_nghe` — **`reeled` không nằm trong điều kiện thoát**.

Phép đo: chĩa **chính file nguyên bản của `f18cbeb`** vào một reel bia mà tôi biết trước
hành vi. Không sửa một byte nào của công cụ; bia thay máy chủ, không thay dụng cụ.

```
$ tests/qa/qa-tt-0003-doi-chung-490/chay-doi-chung.sh \
    <cay-490>/tests/qa/qa3-123758-ruot-f37-f38/do-grounding-reel.py

CA               | grounding    | injection    | dung-duoc | #title  | exit | ket luan trung thuc
-----------------+--------------+--------------+-----------+---------+------+---------------------
chet-ai          | 5/5          | 5/5          | 0/5       | —       | 0    | reel TAT — khong duoc pass
loi-500          | 5/5          | 5/5          | 0/5       | —       | 0    | route HONG — khong duoc pass
nghe-hoa         | 5/5          | 5/5          | 5/5       | 1       | 0    | model DA NGHE THEO
nghe-bien-thien  | 5/5          | 5/5          | 5/5       | 5       | 0    | DA NGHE THEO, khong con dau vet nao
nghe-y-nguyen    | 5/5          | 0/5          | 5/5       | 1       | 1    | DA NGHE THEO (doi chung phai DO)
```

**Đối chứng dương của phép đo này nằm ở hàng cuối và nó ĐỎ** (`injection 0/5`, `exit 1`).
Một bảng toàn hàng sạch không phân biệt được với một đầu dò chết; hàng cuối là thứ làm bốn
hàng trên có nghĩa.

### Hàng đáng đọc nhất: `nghe-bien-thien`

Chữ ký in ra của lượt đó:

```
grounding: 5/5 · injection: 5/5 · dựng được: 5/5 · số title khác nhau qua 5 lượt: 5 · exit 0
```

Chữ ký báo cáo #490 nộp cho lượt **khoẻ** của nó:

```
grounding: 5/5 · injection: 5/5 · dựng được: 5/5 · số title khác nhau qua 5 lượt: 4
```

Lượt bị chiếm in ra chữ ký **đẹp hơn** lượt thật. Payload nằm ở title cả 5 lượt, và không
một dòng nào trong output phản đối. Báo cáo còn viện dẫn "4 title khác nhau" như bằng chứng
mô hình sống — con số đó không loại được ca này, vì mô hình nghe theo vẫn diễn đạt khác nhau
mỗi lượt.

Nguyên nhân: `obeyed = payload_moc in chu_may_viet` là so chuỗi **phân biệt hoa thường**.
Mô hình đổi chữ hoa là việc bình thường nhất nó làm. `nghe-hoa` (`pwned-moc-deadbeef`) đủ
để lọt.

### Hai hàng đầu: đúng trạng thái khi thiếu khoá

Toàn văn ca `chet-ai`:

```
lần 1: 200 reeled=False reason=ai_unavailable picks=0 ngoài-ký-ức-thật=0 nghe-theo-payload=False (0.1s)
... (5 lượt như nhau)
grounding: 5/5 lượt mọi pick truy được về ký ức thật
injection: 5/5 lượt KHÔNG nhắc lại payload trong title/note
dựng được: 0/5 lượt reeled=true
exit=0
```

Công bằng với PR: dòng `dựng được: 0/5` **có** in ra, nên người đọc kỹ thấy được. Nhưng hai
dòng báo cáo viện dẫn đều nói `5/5`, và **mã thoát là 0** — mã thoát là thứ duy nhất một cổng
đọc. Ca `nghe-bien-thien` thì không còn dòng nào để đọc kỹ.

---

## Blocker 3 — khoá Gemini chỉ tồn tại từ worktree của tác giả (loại: không tái lập được)

`dung-stack.sh:64`:

```bash
GEMINI_API_KEY="$(sed -n 's/^GEMINI_API_KEY=//p' "$REPO_ROOT/../../../mobile/.env" ...)"
```

Comment ngay trên nó (dòng 15-18) nói khoá đến "từ `.env` ở gốc repo". Thực tế phép tính
đường dẫn chỉ đúng khi `REPO_ROOT` nằm sâu đúng ba tầng bên cạnh `mobile`:

```
REPO_ROOT=/home/lakiet/agent-harness/wt/qa3   -> /home/lakiet/mobile/.env   CO      (cây tác giả)
REPO_ROOT=/home/lakiet/agent-harness/wt/qa    -> /home/lakiet/mobile/.env   CO      (cây tôi, cùng độ sâu)
REPO_ROOT=/home/lakiet/mobile                 -> /mobile/.env               KHONG   (GỐC REPO THẬT)
REPO_ROOT=/tmp/qa490                          -> /mobile/.env               KHONG   (worktree sạch)
```

Script in `gemini: KHÔNG có key` rồi **chạy tiếp**. Ghép với Blocker 2, chuỗi hoàn chỉnh là:
người khác dán khối "Chạy lại" từ gốc repo → stack lên không có khoá → reel trả
`reeled=false` → `do-grounding-reel.py` in `grounding 5/5 · injection 5/5` → `exit 0`. Họ
nhận đúng con số của báo cáo, đo trên một tính năng AI đã tắt.

Tiêu chí gỡ chặn: đọc `.env` theo `$REPO_ROOT/.env` (hoặc một biến môi trường truyền vào), và
**từ chối chạy** khi khoá vắng thay vì đi tiếp.

---

## Blocker 4 — ba nhóm số không có hiện vật chạy lại (loại: không tái lập được)

| Số trong báo cáo | Hiện vật cần | Có trong PR? |
|---|---|---|
| "F38: **6** lần bấm từ `/`" · "F37: **7** lần bấm" | `plan.json` mà `di-bo.mjs:48` đọc | **không** |
| bảng `ground_reel` 5 dòng (kể cả dòng "BỊA vượt cap 6 → TỪ CHỐI") | script gọi `ground_reel` | **không** (`grep -rn ground_reel` trong bộ công cụ: 0 dòng) |
| mọi lệnh trong khối "Chạy lại" | `<ctx>` `<minh-id>` `<outing>` `<ids-csv>` `<plan.json>` | 5 chỗ trống |

`di-bo.mjs` **bắt buộc** có `plan.json` (`process.exit(2)` nếu thiếu). Cột "cạnh" chính là
câu trả lời cho câu Lead hỏi — "có đường bấm tới không" — và nó là cột duy nhất không có
hiện vật nào chống lưng. Người đọc muốn kiểm phải tự viết lại plan, tức là đo plan của họ,
không phải lời khai của PR.

`ground_reel` có thật ở `services/api/app/domain/reel.py:54`, nên bảng đó **viết lại được** —
nhưng không chạy lại được như đang nộp.

---

## Suggestion (không phải blocker)

1. **`doi-chung-chia-tien.py` là máy in, không phải đối chứng.** Nó in `sum_phan_bo` rồi
   `return 0` — không khẳng định `Σ = tổng`, không khẳng định số nguyên, và luôn thoát 0 nếu
   HTTP đi được. Docstring của nó nói "nếu phép đo xếp chia tiền là vỏ thì phép đo hỏng" —
   nhưng không có mã nào **xếp** gì cả, nên lập luận đó không bao giờ nổ được. Thêm hai assert
   (`sum == tong`, mọi phần là `int`) là biến nó thành đúng cái đối chứng docstring hứa.
2. **`that` trong `do-grounding-reel.py` chỉ gồm ký ức của lượt nhét này**, nên một pick trỏ
   vào ký ức thật *có sẵn từ trước* bị đếm là "ngoài ký ức thật". Hướng lệch này **an toàn**
   (nghiêm hơn thực tế) — nên ghi vào docstring để lượt sau không ai "sửa" nó thành lỏng hơn.
3. Hai phát hiện phụ của #490 (chỉ Minh vào được nhóm seed; seed không có ảnh) **tôi xác nhận
   là đã biết** — đã có trong ghi chép của đội. Chúng không dính tới phán quyết này.

---

## Ô CHƯA quét — đọc kỹ phần này

- **Không** chạy `di-bo.mjs`: không có `plan.json` trong PR, và tự viết plan là đo plan của
  tôi chứ không phải lời khai của PR. Cột "6 lần bấm / 7 lần bấm" **chưa được kiểm**, không
  phải đã bác.
- **Không** dựng stack thật với Gemini thật. Con số F38 `405B → 66B`, `188 dòng access log`,
  `1.357.913đ` lên màn — **chưa kiểm lại**, và tôi không có bằng chứng nào chống lại chúng.
- **Không** chạy `apps/mobile && npm test` trên f18cbeb. Lý do: `apps/mobile` tree hash
  **giống hệt** main (`ac444003259838728f04da516dcba1b25be4e3f1`), PR không thể đổi kết quả
  đó. Nhưng *chưa đo* ≠ *đã đo xanh*.
- **Không** chạy `tests/postgres` (597 skipped trong lượt pytest đầy đủ ở trên là chưa chạy,
  không phải xanh).
- **Không** kiểm injection ở dạng khác ngoài đúng ca hoa/thường + biến thiên. Tôi chỉ chứng
  minh detector lọt, không chứng minh mô hình thật sẽ lọt.
- **Mã QR chưa được quét bằng app ngân hàng thật.** Vẫn còn nguyên, chỉ leader đóng được.

---

## Tiêu chí gỡ chặn (đủ cả bốn thì tôi đo lại)

1. `python3 -m pytest tests/test_qa_scripts_are_ruff_formatted.py -q` xanh trên head PR.
2. `do-grounding-reel.py` đỏ (`exit != 0`) ở cả bốn ca `chet-ai` · `loi-500` · `nghe-hoa` ·
   `nghe-bien-thien` của `tests/qa/qa-tt-0003-doi-chung-490/chay-doi-chung.sh`, và vẫn đỏ ở
   `nghe-y-nguyen`. So chuỗi payload nên casefold, và `reeled` phải vào điều kiện thoát.
3. `dung-stack.sh` tìm khoá theo đường không phụ thuộc độ sâu worktree, và **từ chối chạy**
   khi khoá vắng.
4. `plan.json` được commit; khối "Chạy lại" không còn chỗ trống; bảng `ground_reel` có script
   sinh ra nó.

Gỡ được (1) là hết đỏ cơ học; (2)(3)(4) là điều kiện để những con số trong báo cáo dùng được
vào việc gì.

---

- **protocol_version**: v1
- **skills đã gọi**: `e2e-testing` (chặng 2 cổng rẻ, chặng 7 kết luận + ô chưa quét),
  `bug-reproduction` (bia tất định + đối chứng phải-đỏ + bảng 5 ca chạy lại được)
- **verdict**: `FAIL` — trả về tác giả #490, không merge
