# PASS — hậu kiểm #444 trên main

**Lý do (viết trước chi tiết):** lỗi #444 nói nó vá là **có thật và tôi tái lập
được độc lập** ở bản trước bản vá (`8e5541b`): phán quyết ghi `tree: "clean"` +
cây bây giờ có sửa chưa commit → `ĐI ĐƯỢC`, mã 0. Sau bản vá → mã 2, đúng câu
chữ. Đối chứng dương (cây sạch thật) vẫn xanh, nên đây không phải cổng đỏ với mọi
thứ. Hai ca test mới **cắn được**: đổi đúng một thứ là script, 2 failed → 13
passed. **5/5 đột biến bị giết**, bản không đột biến xanh. Ba tầng cổng trên main
xanh sạch. Một **lỗ còn lại** đo được, nêu ở cuối — nó **không** phải hồi quy do
#444 và **không** thuộc năm loại blocker.

```
protocol_version : 1
verdict          : PASS (hậu kiểm — #444 đã merge lúc 01:26:00Z, squash bf7cc78)
đo tại           : 5cfcefa  (= bf7cc78 + #445 thuần tài liệu)
sha này          : ĐÃ ở main
bản TRƯỚC bản vá : 8e5541b
scripts/hero_walk.sh giữa bf7cc78..5cfcefa : không đổi (diff rỗng)
```

## Ghi chú quy trình: main nhích HAI lần giữa lượt đo

#444 được squash-merge **trong lúc tôi đang đo nó** (lần thứ ba đêm nay). Rồi
`origin/main` nhích thêm lần nữa khi #445 vào. Vì `.git` **dùng chung giữa các
worktree**, một `git fetch` của lane khác đã dời `origin/main` **giữa hai lệnh
bash của tôi** — nên lượt đo "bản CŨ" đầu tiên của tôi thực ra chạy **bản MỚI**.

Tôi bắt được vì md5 của hai bản dựng ra giống hệt nhau, chứ không phải vì cẩn
thận. Bài học ghi lại: **ghim SHA tuyệt đối, đừng bao giờ đo qua một ref biết
chạy** (`origin/main`). Toàn bộ số dưới đây đo trên SHA đã ghim.

## Lỗi có trước bản vá — tái lập độc lập, không dùng probe của tác giả

Repo git tạm, runner lấy từ SHA ghim, phán quyết XANH hợp lệ mọi trường khác:

```
BẢN 8e5541b (TRƯỚC)                     BẢN bf7cc78 (SAU)
ô A  phán quyết clean + cây bây giờ BẨN
     vân tay: clean -> dirty:70816d7a
     ĐI ĐƯỢC, EXIT=0        <-- MÙ       "CÂY SẠCH ... CÓ SỬA CHƯA COMMIT", EXIT=2
ô B  phán quyết clean + cây bây giờ SẠCH  (đối chứng dương)
     ĐI ĐƯỢC, EXIT=0                     ĐI ĐƯỢC, EXIT=0
ô C  phán quyết clean + now = "?" (index hỏng)
     ĐI ĐƯỢC, EXIT=0        <-- MÙ       "KHÔNG ĐỌC ĐƯỢC ... BÂY GIỜ", EXIT=2
```

Ô B là phần giữ bảng này có nghĩa: thiếu nó thì "cổng biết từ chối" và "cổng đỏ
với mọi thứ" nhìn giống hệt nhau.

Ô C dựng bằng `printf 'GARBAGE-NOT-AN-INDEX' > .git/index`. Đo được, không suy
luận: `rev-parse` rc=0, `status --porcelain -z` rc=128 → `cay_van_tay` in `?`.
Tức là mọi phép kiểm sha ở trên vẫn qua, chỉ còn trục cây gác — đúng như PR mô tả.

## Ca test mới có cắn không — đổi ĐÚNG MỘT THỨ là script

File test giữ nguyên từng byte (`bf7cc78:tests/...`), chỉ thay script:

```
script = 8e5541b (cũ)  ->  2 failed, 11 passed
script = bf7cc78 (vá)  ->  13 passed
```

Hai ca đỏ đúng là hai ca mới, và đỏ **vì đúng lý do** (`assert 0 == 2`, stdout
in ra `ĐI ĐƯỢC`), không phải đỏ vì import hay môi trường.

## Đột biến trên bản ĐÃ MERGE — 5/5 bị giết

```
M0 nguyên bản (đối chứng)                       13 passed     <-- bảng phân biệt được
M1 if tree != now:      -> if False:             3 failed
M2 lồng lại y như lỗi cũ (and tree != "clean")   2 failed
M3 if now == "?":       -> if False:             1 failed
M4 != đảo thành ==                               5 failed
M5 chỉ gác khi phán quyết bẩn (startswith dirty) 2 failed
```

M2 và M5 là hai cách viết lại **chính lỗi cũ** mà vẫn giữ nguyên mọi câu chữ mới
trong file — tức là cổng không chỉ so chuỗi, nó thật sự đo hành vi.

## Ca gốc trong docstring đã đóng TỪ TRƯỚC — nên #444 vá đúng chiều còn lại

Kịch bản mở đầu file test (đi bộ trên cây bẩn có bản vá local, rồi
`git checkout -- .` trả cây về bản hỏng đã commit):

```
8e5541b: EXIT=2   bf7cc78: EXIT=2
```

Cả hai đều đỏ. Nên #444 **không** vá lại thứ đã vá; nó vá đúng chiều ngược lại
(`clean` → bẩn), và mô tả PR gọi đúng tên: **bất đối xứng**, không phải cổng chết.

## Cổng đầy đủ trên main (5cfcefa), cây sạch

```
python3 -m pytest services/api/tests tests -q
  -> 2765 passed, 580 skipped, 5049 subtests passed in 303.14s

# đóng skip, không giải thích skip:
MOBILE_TEST_DATABASE_URL=... MOBILE_REQUIRE_POSTGRES_TESTS=1 \
  python3 -m pytest services/api/tests tests -q
  -> 3305 passed, 40 skipped, 5049 subtests passed in 400.94s

cd services/api && MOBILE_REQUIRE_POSTGRES_TESTS=1 python3 -m pytest tests/postgres -q
  -> 523 passed, 0 skipped in 77.61s

cd apps/mobile && npm test
  -> tests 999, pass 999, fail 0, skipped 0, suites 24
```

580 skip → 40. **40 skip còn lại là tầng Gemini sống** (`GEMINI_API_KEY` +
`MOBILE_REQUIRE_GEMINI_TESTS=1`). Tôi **không** chạy tầng đó: nó đốt quota model
mà các lane khác đang dùng. Đó là ô **chưa quét**, không phải ô đã xanh.

## Lỗ CÒN LẠI, đo được — không phải hồi quy, không phải blocker

Bản vá **cố ý** giữ phép kiểm `worktree` bên trong nhánh bẩn, với lý do ghi
trong comment: *"a clean tree at a given commit is the same bytes in every
worktree"*. Đo thì thấy câu đó **không đúng với thứ lượt đi bộ thật sự phụ thuộc**:

```
phán quyết: tree="clean", worktree="/mot/cay/HOAN/TOAN/KHAC"
cây thật  : /tmp/qa0056-wt/cay  (sạch, cùng commit)
--status  -> ĐI ĐƯỢC, EXIT=0        <-- nhận phán quyết của một cây khác

touch .env  (đã gitignore)  -> cay_van_tay vẫn in "clean"
```

`cay_van_tay` dựng từ `git status --porcelain -z`, nên file **bị gitignore không
bao giờ vào vân tay**: `.env`, `node_modules/`, `dist-test/`. Mà lượt đi bộ hero
**chạy app thật và gọi model** (`so_mon: 5` cần `GEMINI_API_KEY` trong `.env`), và
trong repo này **`.env` không có mặt trong worktree**. Nên một lượt đi bộ xanh
chạy ở repo gốc có thể bảo lãnh cho một worktree mà ở đó chính lượt đi bộ đó sẽ
đứt.

Phân loại cho đúng, đây là chỗ dễ đọc quá tay:

- **Không phải hồi quy do #444.** Trước #444 nhánh `clean` không kiểm **gì cả**;
  sau #444 nó kiểm vân tay. Nghiêm ngặt tốt hơn.
- **Không thuộc năm loại blocker** trong charter. Không sai tiền, không lộ dữ
  liệu, không hỏng tính hợp lệ thí nghiệm, tái lập được.
- Nên nó là **việc nối tiếp cho devops**, không phải cớ để revert. Đã gửi kèm
  bước tái lập.

## KHÔNG chứng minh

- Tầng Gemini sống (40 skip) — chưa chạy, cố ý.
- Lượt đi bộ hero **thật** (16 chặng, máy 8099): tôi kiểm `--status`, tức phần
  ĐỌC phán quyết. Tôi **không** chạy một lượt đi bộ đầu-cuối thật trong lượt này.
- Mã VietQR **vẫn chưa được quét bằng app ngân hàng thật**. Ô đó còn nguyên.
- #444 làm cổng chặt hơn ở trục cây; nó **không** chứng minh các commit thêm vào
  sau lượt đi bộ vẫn giữ đường hero chạy được (kiểm ancestry, không phải bằng nhau).
