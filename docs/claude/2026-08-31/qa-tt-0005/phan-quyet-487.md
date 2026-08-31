# FAIL

**Lý do (đọc trước mọi chi tiết):** ba cổng của #487 tự thân đều **đạt** mọi phép
đo tôi ném vào — nhưng ca `test_harness_dang_chay_khong_do_khoang_bang_dong_ho_treo_tuong`
nằm trong `tests/`, tức nằm trong **cổng chặn của cả repo**, mà phán quyết của nó
lại là hàm của `~/agent-harness/` — một thư mục **ngoài repo**, không remote, đang
có 5+ sửa đổi chưa commit, và lane khác đang sửa liên tục. Hệ quả tôi đo được chứ
không suy ra: **cùng SHA `7ed5984`, cùng máy, cùng lệnh, cách nhau 13 phút →
`1 failed` rồi `0 failed`.** Cổng chính của repo hết tái lập được, và cái đỏ đó
không commit nào trong repo sửa được. Blocker loại 5 (không tái lập được) kèm
loại 4 (hỏng tính hợp lệ thí nghiệm: cái đỏ **quy sai địa chỉ**).

```
đo tại   7ed5984d9a47762688cee50a8094e0ac9b86591c
sha này  là nhánh chưa merge; origin/main 7fff89c LÀ tổ tiên của nó
máy      lakiet@WSL2, cây QA sạch (git status trống) suốt cả hai lượt
```

---

## 1. Bằng chứng chặn: cùng một SHA, hai phán quyết

Lệnh mà `CLAUDE.md` bắt mọi lane chạy và Lead dùng để quyết định merge:

```
python3 -m pytest services/api/tests tests -q
```

| lượt | bắt đầu → xong | kết quả |
|---|---|---|
| 1 | 21:09 → 21:13:55 | `1 failed, 2953 passed, 596 skipped, 5273 subtests passed in 303.97s` |
| 2 | 21:16 → 21:22 | `2954 passed, 596 skipped, 5273 subtests passed in 310.30s` |

Không có gì trong repo đổi giữa hai lượt (`git status` trống, HEAD không đổi).
Thứ đã đổi nằm ngoài repo:

```
~/agent-harness/lane.py   mtime 21:15:51   (rồi 21:22:07 — sửa tiếp lần nữa)
~/agent-harness           git status: M brains.py, M queue.py, M roles/... (chưa commit)
```

Nguyên văn cái đỏ ở lượt 1 — chính cổng tự in ra:

```
AssertionError: bản harness ĐANG CHẠY tại /home/lakiet/agent-harness đo khoảng
bằng đồng hồ treo tường (1 chỗ trên 17 file):
  lane.py:528: trong watch() — đo khoảng bằng time.time() trừ 'last_change', mà
  'last_change' cũng lấy từ time.time() trong chính phạm vi này.
```

Đến 21:15 thì `lane.py:528` đã là `silent = khoang() - last_change` (monotonic),
nên lượt 2 xanh. Cổng **không** nói dối ở bất kỳ lượt nào; nó khai đúng trạng thái
production tại đúng giây nó quét. Vấn đề là trạng thái đó không phải thứ PR này
sở hữu, và cũng không phải thứ người đọc dấu đỏ sẽ đi tìm.

### Vì sao đây là hỏng tính hợp lệ thí nghiệm, không chỉ là "hơi phiền"

Nếu tôi dừng lại ở lượt 1, báo cáo của tôi sẽ là *"#487 làm cổng đỏ"* — **sai**.
Cái đỏ đó do lane devops sửa `lane.py` lúc tôi đang chạy. Ngược lại, một lane
frontend chạy cổng để kiểm PR của mình cũng sẽ nhận đúng dấu đỏ đó và không có
cách nào biết nó không phải của mình. Đây đúng lớp hỏng repo này đã trả giá nhiều
lần: dấu đỏ **quy sai địa chỉ** thì tệ hơn không có dấu đỏ.

### Cơ chế, đo tất định (không cần chờ may)

```
AGENT_HARNESS=<bản chép sạch>       → 3 passed
AGENT_HARNESS=<bản chép + 1 hàm>    → 1 failed, 2 passed
```

Một hàm thêm vào **một bản chép ngoài repo** lật được ca test **trong repo**.
Không đặt biến thì ca đó đọc thẳng `~/agent-harness`.

### Lớp này là MỚI, không có sẵn trên main

Kiểm để khỏi đổ oan cho PR:

```
git grep -ln "AGENT_HARNESS\|agent-harness" origin/main -- tests/ services/api/tests/
  tests/test_khong_do_khoang_bang_dong_ho_treo_tuong.py   → chỉ quét git -C REPO_ROOT ls-files
  tests/test_qa_evidence_runs_on_another_machine.py       → chỉ quét git ls-files -- tests/qa
```

Hai file trên `main` chỉ **nhắc** harness trong văn xuôi; cả hai quét `REPO_ROOT`.
`#487` là PR **đầu tiên** đưa vào `tests/` một ca có phán quyết phụ thuộc cây
ngoài repo mà lane khác ghi được.

## 2. Tiêu chí gỡ chặn

Chỉ cần **một** trong ba, và không cái nào đụng tới ba cổng đã đạt:

- **(a) — gọn nhất.** Chuyển `test_harness_dang_chay_...` (và `test_co_file_de_quet`,
  cũng đọc cây thật) ra khỏi bộ chặn, cho chạy ở chặng `gate.sh harness-deploy`
  — chặng đó đã tồn tại và **đã tự dán nhãn "(máy này thôi)"**. Đúng chỗ, không mất
  phép đo.
- **(b)** Giữ trong `tests/` nhưng không chặn: báo cáo thay vì `assert`. (Đừng dùng
  `xfail(strict)` — nó đã làm `main` đỏ ở lane khác một lần rồi.)
- **(c)** Neo phép quét vào một fingerprint đã ghi, để một thay đổi ngoài repo sinh
  ra cái đỏ **ổn định và quy đúng địa chỉ**, thay vì cái đỏ chạy theo thời điểm.

Hai ca còn lại trong file (`test_may_do_that_su_bat_duoc_dang_da_tim_thay`) tự chứa,
không đọc cây thật — giữ nguyên trong bộ chặn được.

---

## 3. Cái tôi đã tấn công mà cổng ĐỨNG VỮNG

Phần này để công bằng với tác giả: tôi vào với giả định sẽ tìm ra cổng mù, và
không tìm được cái nào trong chính ba cổng.

### 3.1 Cổng lệch triển khai — 4/4 đối chứng dương đều đỏ

Cổng đang in `IN_SYNC` cho cả hai cặp. Một dấu xanh như thế trông y hệt máy đo
chết, nên tôi dựng bốn gốc giả trong `/tmp`:

| gốc giả | cổng nói | exit |
|---|---|---|
| `agent_supervisor.py` lấy từ commit cũ thật | `BEHIND — cham 5 commit`, liệt kê đúng 5 SHA thiếu | 2 |
| nội dung chưa từng có trong lịch sử | `DIVERGED — co sua tay`, kèm lệnh `git diff --no-index` | 2 |
| thiếu `agent_checkpoint.py` | `MISSING`, kèm lệnh `git show ... >` để cài | 2 |
| thêm `harness_selfcheck.py` không khai báo | `UNMANAGED`, chỉ đúng tên biến phải sửa | 2 |

Xanh của cổng này **kiếm được**. Thêm nữa: `MIN_PAIRS = 2` là hằng số literal
đứng cạnh `DECLARED_PAIRS` đúng 2 phần tử — bỏ một tên là `1 < 2` → từ chối, nên
không rơi vào bẫy "sàn đo bằng chính danh sách nó gác".

### 3.2 `harness_selfcheck status` — 6/6 nhánh đúng như khai

| ca | exit | dòng đầu |
|---|---|---|
| chưa chạy lần nào | 2 | `CHUA CHAY LAN NAO` |
| bản ghi hỏng JSON | 2 | `KHONG DOC DUOC ban ghi` |
| bản ghi quá hạn | 2 | `CHUA CAI CANH GAC ... la mot luot chay TAY` |
| **tươi + đúng vân tay** | **0** | `XANH — 6 test, 8s truoc, dung ma dang chay` |
| vân tay lệch + sửa cũ | 2 | `BAN GHI NOI VE MA KHAC` |
| vân tay lệch + sửa mới | 0 | `XANH cho ban truoc ... con trong an han 3600s` |

Ca thứ tư là ca quan trọng nhất và hay bị bỏ: nó chứng minh cổng **xanh được** —
một cổng đỏ vĩnh viễn là cổng người ta gỡ. Ca cuối (ân hạn ≤ 3600s trả exit 0)
**đã được PR khai** ở mục 3 mô tả và có đột biến M7 phủ; số đo của tôi khớp lời
khai, không phải phát hiện mới.

*(Ghi lại một cái bẫy: `--harness` là tuỳ chọn **toàn cục**, phải đứng trước
subcommand. Đặt sau, cả 6 ca đều `exit 2` — nhưng là do argparse, tức **đỏ nhầm
lý do**. Nếu chỉ đọc mã thoát thì bảng này đã "6/6 đạt" một cách rỗng tuếch.)*

### 3.3 Cổng đồng hồ — tập quét đủ, và 0 finding là xanh kiếm được

- **Tập quét đủ**: `find ~/agent-harness -name '*.py'` (trừ `wt/`, `__pycache__`)
  ra đúng **17** file — bằng đúng con số PR khai. Không file harness nào lọt ngoài.
- **Dùng lại máy dò #477** thay vì viết máy dò thứ hai — đúng hướng; lỗ hổng bí
  danh mà #477 đã vá được thừa hưởng, không phải làm lại từ đầu.
- **Từ chối thay vì nói dối**: trỏ vào cây không phải git repo → không suy ra danh
  sách file bằng `rglob`, mà báo `KhongTraLoiDuoc`.
- **Canary bắt buộc**: bản chép sạch → `3 passed`; bản chép + một hàm đo khoảng
  bằng `time.time()` → `1 failed`. Nên con số `0 finding` trên harness thật là
  xanh đã được chứng minh, không phải máy đo im.

**Hai canary đầu của tôi viết sai và tôi giữ lại chúng ở đây**, vì chúng dạy đúng
ranh giới máy dò: tôi truyền `started` vào làm **tham số**, và máy dò không nổ.
Đó không phải cổng mù — máy dò chỉ nổ khi **cả hai đầu** phép trừ sinh ra trong
cùng phạm vi, đúng như docstring khai và đúng như `PHAI_THA` ghim. Sửa canary cho
trung thành với file thật (gán `started = time.time()` trong cùng hàm) thì nó đỏ
ngay. Ai đọc lại bảng này đừng kết luận từ hai canary đầu.

---

## 4. Ô CHƯA quét — phần quan trọng nhất

- **`install --apply` chưa chạy.** Tôi không cài khối crontab thật, nên "cron 15
  phút có thật sự gọi tới không" là **chưa đo**. Tôi chỉ đọc `runner_in()` và xác
  nhận nó sinh đường dẫn từ `repo`, không từ `__file__`.
- **`harness_selfcheck run` chưa chạy trên harness thật** — sẽ ghi vào
  `state/selfcheck.json` của production, tôi không đụng. Nên "6 file test của
  harness có thật sự xanh không" là chưa đo ở lượt này.
- **`gate.sh` chưa chạy** ở dạng `guard guard-range ruff harness-deploy
  harness-selfcheck hero-walk`. PR khai `ĐẠT 6 HỎNG 0`; tôi **không** kiểm chứng
  con số đó.
- **`hero_walk.sh` và bảng đột biến 7/7** của PR: chưa kiểm chứng độc lập. Đây là
  phần lớn nhất tôi bỏ trống.
- **`tests/postgres`**: `596 skipped` trong cả hai lượt — tầng PostgreSQL **không
  chạy**. Không liên quan #487, nhưng đừng đọc `2954 passed` thành "đã phủ DB".
- **`apps/mobile && npm test`**: chưa chạy lượt này; #487 không đụng `apps/mobile/`.
- **Mã VietQR chưa từng được quét bằng app ngân hàng thật.** Câu này còn nguyên,
  và chỉ leader đóng lại được.

## 5. Tái lập

```bash
git checkout 7ed5984
bash tests/qa/qa-tt-0005/do_cong_487.sh      # khối A, B, C ở trên, chỉ ghi vào /tmp
python3 -m pytest services/api/tests tests -q # chạy hai lần, cách nhau vài phút
```

Khối C chỉ có nghĩa trên máy có `~/agent-harness`; không có thì script tự nói là
bỏ qua chứ không in xanh.
