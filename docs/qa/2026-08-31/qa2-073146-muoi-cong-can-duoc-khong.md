# Mười cổng mới của đêm nay: cái nào cắn được?

- task_id: `qa2-073146` (hậu tố lượt: 65678201)
- main lúc đo: `2f8a301` (nhánh đo: `qa2/kiem-muoi-cong-can-duoc-khong`)
- kỹ năng: `ai-qa-review`
- phương pháp: mỗi cổng nhận **một vi phạm thật**, đo mã thoát, rồi **bỏ vi phạm
  đi** và đo lại. Hai chiều, không chỉ một.

## Bảng

| # | Cổng | Cắn được? | Bằng chứng |
|---|---|---|---|
| 1 | header actor phân biệt MÙ vs THIẾU (#398) | **CÓ** | 0 / 1 / 2 đều đúng |
| 2 | meta-cổng: chặng gate.sh ↔ job CI (#384) | **CÓ** | đỏ cả hai chiều |
| 3 | demo_watch ba trạng thái (#374) | **CÓ** | 5 ô đều đúng |
| 4 | actorId bắt buộc ở tầng kiểu (#397) | **CÓ** | canary biên dịch lại → đỏ |
| 5 | hợp đồng route neo theo tên wrapper (#419) | **CÓ** | đổi tên → thoát 2 |
| 6 | danh sách wrapper RỖNG là LỖI (#430) | **CÓ** | neo tự tắt → thoát 2 |
| 7 | tương phản màu chữ/nền, 66 màn (#431) | **CÓ**, một nửa | literal đỏ; **qua biến thì mù** |
| 8 | hỏi cây trước khi xuất bundle (#436) | **CÓ** | KHỚP/LỆCH/KHÔNG KIỂM ĐƯỢC đủ ba |
| 9 | phán quyết hero-walk buộc vào CÂY (#439) | **KHÔNG**, ở ô hay gặp nhất | 5/6 ô đúng, ô thứ sáu thoát 0 |
| 10 | một bộ kiểm tiền duy nhất (#437) | **CÓ**, trong phạm vi đã khai | bắt cả 2 cách viết; mù 2 chỗ **có khai** |

Tám cổng cắn được sạch. Một cổng (#431) cắn được đúng hình dạng nó nhắm và mù
với hình dạng kế bên. Một cổng (#439) **có lỗ ở ô hay xảy ra nhất**.

## #439 — lỗ, và nó nằm ở đâu

`scripts/hero_walk.sh --status` từ chối một phán quyết không thuộc về cây đang
đứng. Lời văn của chính #439 nói ra điều nó chặn:

> a walk driven by uncommitted edits recorded the untouched sha underneath them,
> so it vouched for code it never ran

Sáu ô, đo bằng `tests/qa/qa2-073146-muoi-cong/probe_hero_walk_cay_sach.py`
(dựng repo git rời trong `/tmp`, chép `hero_walk.sh` thật vào, gọi chính nó —
không viết lại logic nào của nó):

| ô | phán quyết ghi | cây bây giờ | mong đợi | đo được |
|---|---|---|---|---|
| sach_va_cay_sach | `clean` | sạch | 0 | 0 ✓ |
| **sach_nhung_cay_ban** | `clean` | **có sửa chưa commit** | **2** | **0 ✗** |
| ban_va_van_tay_khop | `dirty:X` | `dirty:X` | 0 | 0 ✓ |
| ban_nhung_van_tay_da_doi | `dirty:X` | `dirty:Y` | 2 | 2 ✓ |
| thieu_truong_tree | (không có) | bất kỳ | 2 | 2 ✓ |
| tree_la_dau_hoi | `?` | bất kỳ | 2 | 2 ✓ |

Nguyên nhân là một dấu thụt lề. Trong `hero_walk.sh`, phép so `tree != now` nằm
**bên trong** nhánh `if tree != "clean":`:

```python
if tree != "clean":
    ...
    if tree != now:        # <- chỉ chạy khi phán quyết ghi là BẨN
        raise SystemExit(2)
```

Nên phán quyết ghi `clean` **không bao giờ** được đem so với cây hiện tại. Nó
được nhận vô điều kiện.

**Vì sao ô này quan trọng hơn năm ô kia cộng lại.** Đi bộ hero trên main sạch,
rồi bắt đầu sửa — đó là trạng thái làm việc bình thường của mọi lane, mọi ngày.
Từ giây bắt đầu sửa, mọi `make gate` đều in `ĐI ĐƯỢC` về một cây chưa ai đi bộ.
Năm ô kia là ô người ta phải cố ý mới rơi vào; ô này là ô người ta rơi vào khi
làm việc đúng cách.

Đo trực tiếp trên cây thật, không qua probe:

```
runner tự khai vân tay cây:  dirty:3759d77b000dcfe4
phán quyết ghi tree      :  clean
hero_walk.sh --status    :  EXIT=0  "ĐI ĐƯỢC ... 16/16 chặng"
```

**Bộ ca của #439 có 11 ca và phủ được năm ô — thiếu đúng ô thứ sáu.** Không
phải cổng chết: bất đối xứng. Chiều `dirty → dirty khác` chặn đúng.

### Tiêu chí gỡ chặn (đã thử, có số)

Đưa phép so ra ngoài nhánh:

```python
if tree != now:
    if tree == "clean":
        print("hero_walk: lượt đi bộ chạy trên CÂY SẠCH, còn cây bây giờ có sửa chưa commit.")
        raise SystemExit(2)
```

- probe sáu ô: `EXIT=1` (1 ô lệch) → `EXIT=0` (cả sáu đúng)
- `tests/test_hero_walk_binds_to_the_tree_it_walked.py`: **11 passed** trước và
  sau bản vá — bản vá không phá ca nào đang có

`scripts/hero_walk.sh` là file của devops (tạo ở #354), nên bản vá **không** nằm
trong PR này. Đã `bug-to devops`.

## #431 — cắn được hình dạng nó nhắm, mù với hình dạng kế bên

Tiêm đúng lỗi khai sinh (`aiInk` trên `aiSoft`, chip "Level N"):

```
src/screens/thanh-tich/ThanhTich.tsx:258 [sang] aiInk(#ffffff) trên aiSoft(#f5f1ff) = 1.11:1 < 4.5:1
src/screens/thanh-tich/ThanhTich.tsx:258 [toi]  aiInk(#150a30) trên aiSoft(#221046) = 1.1:1  < 4.5:1
```

2 ca đỏ, đúng dòng, đúng cả hai bảng màu. Bỏ ra: 10/10 xanh lại.

**Cùng lỗi đó, viết qua một biến, thì im hoàn toàn:**

```tsx
const mauChuChip = c.aiInk;              // một bước nhảy
<Text style={{ ...type.label, color: mauChuChip }}>
```

→ **10/10 pass**. Đây đúng chỗ `qa-tt-0054` (#435) đã nêu; tôi tiêm độc lập và
ra cùng kết quả.

**Và sàn coverage không đỡ được chỗ đó.** Sàn viết `soCap > 300`, số thật là
**670** — bộ đọc mù đi **55%** mà sàn vẫn xanh. Sàn đó đang canh "bộ đọc chết
hẳn", không canh "bộ đọc mù dần".

## #437 — mù có khai, khác với mù không biết

Bắt được **cả hai** cách viết, kể cả cách không dùng `isinstance` nào:

| cách viết bản sao thứ 14 | kết quả |
|---|---|
| `isinstance(v, bool) or not isinstance(v, int)` | **đỏ** — nêu tên `_kiem_so_tien_moi` |
| `type(v) is not int` | **đỏ** — nêu tên |
| `try: int(v) / except` | xanh — **mù** |
| bản sao y hệt đặt trong `app/web/` | xanh — **ngoài SCOPE** |

Hai chỗ mù đều **được khai trong docstring của chính nó**. Đó là mù có khai, và
nó khác hẳn loại mù ở #439: người đọc `test_one_money_check.py` biết mình chưa
được phủ chỗ nào. Ghi vào cột thứ ba, không ghi vào cột "hỏng".

Ghi chú riêng: cổng này **đóng được** lỗ `type(v) is not int` mà lượt đo
`require_vnd` (#429) tìm ra trước đó.

## Cột thứ ba — cái tôi KHÔNG kiểm được

- **Không cổng nào trong mười cái được đo qua CI.** Actions vẫn chết vì billing;
  mọi số ở trên là `make`/`pytest`/`node --test` **trên máy này**. Cổng có chạy
  trong CI hay không là câu hỏi khác, và #384 chỉ chứng minh *có tên chặng*, tự
  nó nói thế.
- **#436 và #374 chỉ đo được với `origin/main` của máy này.** Ô "remote không
  giải được" tôi dựng bằng ref bịa; ô "mạng chết giữa chừng" chưa đo.
- **#439 ô thứ bảy chưa đo**: phán quyết ghi `clean` trong khi cây có **file
  mới chưa track**. `cay_van_tay` có đọc `ls-files --others`, nhưng vì nhánh
  `clean` không so gì cả, ô đó nhiều khả năng cũng thoát 0 — chưa dựng ca nên
  chưa khai là đã đo.
- **#397 chỉ đo `tsc`**, không đo bundle dựng ra có thật sự gửi header không.
- Tôi **không** đo được "cổng có bị ai `--no-verify` đi vòng không" — branch
  protection chưa bật, nên mọi cổng vẫn là kỷ luật.

## Một điều về phép đo, để lần sau không ai lặp lại

Lượt này suýt ghi sai **#398**. Lệnh đầu tiên tôi chạy là:

```bash
python3 scripts/check_actor_headers.py 2>&1 | tail -12; echo "exit=$?"
```

In ra `exit=0` — và đó là mã thoát của `tail`, không phải của cổng. Cổng thật sự
thoát **2**. Nếu tôi tin con số đó, báo cáo này sẽ ghi "#398 in ra MÙ nhưng vẫn
thoát 0" — một lỗi nặng, về một cổng hoàn toàn lành.

Đo mã thoát thì **đừng nối ống**:

```bash
python3 scripts/check_actor_headers.py >/tmp/out 2>&1; echo "EXIT=$?"; tail -12 /tmp/out
```

## Lệnh đã chạy

```
# nền xanh trước khi tiêm (cây sạch ở 2f8a301)
python3 -m pytest tests/test_actor_header_contract.py tests/test_gate_covers_every_workflow_job.py \
  tests/test_demo_watch.py tests/test_api_contract.py tests/test_tree_matches_main_gate.py \
  tests/test_hero_walk_binds_to_the_tree_it_walked.py tests/test_api_contract_unresolved_pin.py -q
  -> 128 passed, 16 subtests passed

cd services/api && python3 -m pytest tests/test_one_money_check.py -q
  -> 11 passed, 110 subtests passed

cd apps/mobile && node --test tests/actor-id-bat-buoc.test.mjs tests/tuong-phan-cap-mau.test.mjs
  -> # pass 12  # fail 0

# probe sáu ô của #439
python3 tests/qa/qa2-073146-muoi-cong/probe_hero_walk_cay_sach.py
  -> EXIT=1, ô sach_nhung_cay_ban: mong đợi 2, đo được 0
  -> với bản vá thử: EXIT=0, cả sáu ô đúng, và 11 ca của #439 vẫn xanh
```

Mọi vi phạm đã tiêm đều được gỡ; cây trở lại sạch sau từng cổng và nền xanh
được đo lại mỗi lần.
