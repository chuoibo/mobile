# Phán quyết QA cho PR #382 — "AI hiểu nhóm": bốn route đọc giờ có màn gọi

**FAIL**

**Lý do, viết trước chi tiết.** PR làm đỏ một test đã có sẵn **trong chính cây của
nó**: `apps/mobile/tests/nhom-chat-web.test.mjs` khẳng định hàng chip của màn chat là
tablist **đúng 4 tab**, còn PR thêm chip thứ năm ("AI hiểu nhóm"). Tôi dựng lại bản
export từ đúng SHA của PR và test đỏ; dựng lại từ commit cha thì test xanh. Trên cây
gộp, một root cause này kéo theo **hai** test đỏ, vì meta-cổng `gate-web-khong-doc-ban-cu`
(ca C) chạy lại chính cổng web kia và đòi nó xanh. Gộp nguyên trạng là `main` đỏ.

Phần còn lại của PR thì **đúng**: tiền đề của nó kiểm chứng được, bốn route có thật
trên máy chủ ở `main`, màn có cửa vào thật, và năm chip vẫn vừa màn 320px. Đây là
một PR tốt bị chặn bởi một dòng assert cần cập nhật — không phải một thiết kế sai.

---

## Đo tại đâu

```
PR head (đã test)   5703986  57039866c18d163f5adf9cdcaf25334de48bf9d7  -- nhánh CHƯA merge
cha của PR (đối chứng) 9101e42                                        -- ĐÃ ở main
cây gộp             4527415  = PR 5703986 ⊕ main@8f126d8
main lúc viết       07ea4ce  (nhích 2 commit giữa lượt: #401, #402 — thuần tài liệu,
                              không chạm apps/mobile, nên phán quyết không đổi)
```

PR đứng **sau `main` 22 commit**, nên mọi số ở đây đo trên **cây gộp**, trừ cặp
đối chứng đỏ/xanh vốn phải đo tại đúng SHA của PR và của cha nó.

**Cảnh báo môi trường, đã xử lý trước khi đo:** worktree QA có 20 thư mục
`apps/mobile/dist-qa*` untracked — hiện vật của các lượt QA trước của chính tôi,
không nằm trong nhánh nào. `tsconfig.json` chỉ loại `dist` và `dist-test`, nên
`dist-qa09` vẫn lọt vào `include: **/*`. Tôi đã dời cả 20 ra `/tmp/qa-dist-stash/`
**trước** khi chạy cổng, để không có con số nào ở đây là do rác của tôi.

---

## Blocker (1) — loại "vi phạm spec/cổng"

### Dẫn chứng: đỏ ở PR, xanh ở cha, cả hai đều dựng lại export

Cổng web này đọc `.expo-build-check` — **bản export**, không phải `dist-test`. Một
export cũ đo một sản phẩm khác (đúng bug-010019 mà #386 đã vá), nên mỗi vế dưới đây
đều chạy `npm run build:check` sạch trước khi chạy test.

```
$ git checkout 9101e42          # cha của PR
$ rm -rf .expo-build-check dist-test && npm run build:check && npx tsc -p tsconfig.test.json
$ node --test tests/nhom-chat-web.test.mjs
# pass 7   # fail 0

$ git checkout 5703986          # head của PR
$ rm -rf .expo-build-check dist-test && npm run build:check && npx tsc -p tsconfig.test.json
$ node --test tests/nhom-chat-web.test.mjs
not ok 5 - hàng chip là tablist đúng chuẩn: đúng 4 tab, không lẫn nút khác
    nhãn bốn chip không đúng
    + actual - expected
      [ 'Chat', 'Plan', 'Thành viên', 'File',
    +   'AI hiểu nhóm'
      ]
# pass 6   # fail 1
```

Assertion "đúng 4 tab" đến từ 8533aa8 (#119) — một commit **cũ, đã có sẵn ở head của
PR**. Đây không phải va chạm do PR tụt lại sau `main`; chạy `npm test` một lần trên
nhánh là thấy.

### Hậu quả: trên cây gộp thành hai test đỏ

```
$ git checkout 4527415   # cây gộp, export dựng lại
$ node --test tests/nhom-chat-web.test.mjs tests/gate-web-khong-doc-ban-cu.test.mjs tests/ai-hieu-nhom.test.mjs
not ok 17 - cổng web phải từ chối bản export cũ hơn nguồn      <- ca C, cùng root cause
not ok 18 - nhóm chat, đo trên trang render thật
# tests 26   # pass 24   # fail 2
```

`gate-web-khong-doc-ban-cu` ca C ("bản dựng đúng từ cây này: cổng vẫn chạy và vẫn
xanh") chạy lại chính cổng web kia và đòi nó xanh — nên nó đỏ theo. Sửa một chỗ là
tắt cả hai; đừng chữa riêng ca C.

### Tiêu chí gỡ chặn

Cập nhật hợp đồng tablist trong `tests/nhom-chat-web.test.mjs` cho khớp 5 chip (tên
test lẫn `expected` đều đang ghi cứng số 4), rồi `npm test` trong `apps/mobile` xanh
**trong cây sạch**. Không cần đổi code sản phẩm.

Một lưu ý khi sửa: vế "không lẫn nút khác" của test đó là phần đáng giữ — nó gác việc
nhét nút không phải tab vào tablist. Chỉ nới con số, đừng nới ý.

---

## Cái PR nói và tôi kiểm chứng được là ĐÚNG

**Tiền đề "bốn route đã sống nhưng không màn nào gọi" — đúng cả hai vế.**

```
$ for r in preference-profile 'contexts/.*suggestion' contextual-suggestion 'contexts/.*budget'; do
    git grep -l "$r" 9101e42 -- apps/mobile/src | wc -l; done
0    0    0    0                       <- TRƯỚC PR: không màn nào gọi
$ git grep -l preference-profile 5703986 -- apps/mobile/src
apps/mobile/src/screens/ai-hieu-nhom/ai-hieu-nhom.ts    <- SAU PR: có người gọi
```

**Bốn route có thật trên máy chủ ở `main`** (không phải route ma):

```
services/api/app/api/routes/preferences.py:33   "/contexts/{context_id}/preference-profile"
services/api/app/api/routes/suggestions.py:59   "/contexts/{context_id}/suggestion"
services/api/app/api/routes/suggestions.py:93   "/contexts/{context_id}/contextual-suggestion"
services/api/app/api/routes/budget.py:39        "/contexts/{context_id}/budget"
```

**Cửa vào có thật**: thanh tab → **Tin nhắn** → chip "AI hiểu nhóm"
(`TinNhan.tsx`, `ChipId` thêm `"ai-hieu"`). Không phải màn mồ côi chỉ tới được bằng URL.

**Cổng backend trên cây gộp xanh**:

```
$ python3 -m pytest services/api/tests tests -q
2664 passed, 574 skipped, 4891 subtests passed in 256.79s
```

**Năm chip vẫn vừa màn nhỏ** — đo trên bản render thật, export dựng từ cây gộp
(`apps/mobile/tests/qa-tt-0048/do-hang-chip.mjs`):

| | 320×720 | 390×844 |
|---|---|---|
| chip tràn ra ngoài | 0/5 | 0/5 |
| chip cao < 44px | 0/5 | 0/5 |
| nhãn bị cắt | 0/5 | 0/5 |

Nỗi lo "thêm chip thứ 5 thì vỡ hàng ở 320px" **không xảy ra**. Tôi ghi ra vì người
sửa sắp nới con số 4 thành 5, và nếu layout có vỡ thì đó đúng là kiểu cổng được sửa
cho khớp một thực tại đã hỏng — ở đây thì không phải vậy.

---

## Suggestion (không chặn merge)

**S1 — test mới có cắn, nhưng hở đúng nhánh 403.** Nền xanh 16/16; tôi chạy 5 đột
biến trên `ai-hieu-nhom.ts`, **3 bị giết, 2 sống sót**:

| # | Đột biến | Kết quả |
|---|---|---|
| M1 | đổi path `/preference-profile` → `/preference-profile-SAI` | **giết** (fail 2) |
| M2 | bỏ header `X-Actor-Roles` | **giết** (fail 1) |
| M3 | bỏ guard `!opts.actorId` → `chua-biet-la-ai` | **giết** (fail 1) |
| M4 | `401 \|\| 403` → chỉ `401` (403 rơi xuống `may-chu-loi`) | **SỐNG** (16/16 vẫn xanh) |
| M5 | đảo thứ tự ưu tiên lỗi trong `chonLoi` | **SỐNG** (16/16 vẫn xanh) |

M4 không phải đột biến tương đương: `AiHieuNhom.tsx:62` và `:70` render hai nhánh
khác nhau, nên người dùng thấy "máy chủ lỗi" + detail thô thay vì "bị từ chối". Đáng
nói vì chính comment trong `ai-hieu-nhom.ts` ghi rằng cả bốn quyền trả **403
`role_not_permitted`** khi chỉ có `X-Actor-ID` — tức 403 là đường từ chối *được
mong đợi*, và nó đúng là nhánh chưa có ca nào phủ.

**S2 — "AI hiểu nhóm" xuống 3 dòng ở 320px.** Không bị cắt, vẫn đọc được, chip vẫn
53×47. Nhưng `scrollHeight` 45px ở `line-height` 15px = 3 dòng ("AI / hiểu / nhóm"),
trong khi "Thành viên" chỉ 2 dòng và ba chip kia 1 dòng — hàng tab cao lên trên máy
nhỏ. Nhãn ngắn hơn ("AI hiểu", "Hiểu nhóm") gỡ được. Thẩm mỹ, không phải lỗi.

---

## ĐÃ CHẠY

- `python3 -m pytest services/api/tests tests -q` — cây gộp 4527415 — **2664 passed,
  574 skipped** (repo guard nằm trong tập này).
- `npm test` (`apps/mobile`, gồm `expo export` + `tsc -p tsconfig.test.json`) — cây
  gộp — **918 tests, 916 pass, 2 fail** (hai fail là blocker ở trên).
- `node --test tests/nhom-chat-web.test.mjs` — tại 9101e42 (7/0) **và** tại 5703986
  (6/1), mỗi vế dựng lại `.expo-build-check` + `dist-test` từ đúng SHA đó.
- `node --test tests/ai-hieu-nhom.test.mjs` — 16/16 — cộng 5 đột biến (bảng S1).
- `apps/mobile/tests/qa-tt-0048/do-hang-chip.mjs` — 320×720 và 390×844 trên bản
  render thật qua Chrome CDP.
- `git grep` đối chứng tiền đề tại 9101e42 và 5703986; grep 4 route trong
  `services/api/app` tại `origin/main`.

## KHÔNG CHẠY — phần này quan trọng hơn phần trên

- **`tests/postgres` (tầng PostgreSQL thật)** — không dựng DB cho lượt này. 574
  `skipped` ở trên phần lớn là tầng đó. PR không chạm `services/api/`, nên tôi đánh
  giá rủi ro thấp, **nhưng tầng đó đã không chạy** và tôi không nói nó xanh.
- **`npm run test:e2e` (lát cắt dọc)** — không chạy, cần server sống. PR không chạm
  đường tiền.
- **Đo 4 route qua HTTP trên máy chủ sống** — **không chạy**. Nên tôi **chưa** chứng
  minh: (a) bốn route trả 200 với đúng cặp header client gửi; (b) lời khẳng định
  trong comment rằng chỉ `X-Actor-ID` thì trả 403 `role_not_permitted`; (c) máy chủ
  xử lý thế nào khi client **tự khai** `X-Actor-Roles: "group_admin,member"` cho mọi
  người dùng. Điểm (c) đáng có người xem lại: client ghi cứng vai `group_admin`, và
  lập luận "máy chủ vẫn kiểm tư cách thành viên theo hàng dữ liệu" nằm ở comment chứ
  chưa có ca kiểm nào của PR này chứng minh.
- **Nội dung màn "AI hiểu nhóm" với dữ liệu máy chủ thật** — không quét. Tôi chỉ đo
  hàng chip; các trạng thái `xong` / `bi-tu-choi` / `khong-noi-duoc` / `may-chu-loi`
  chưa được nhìn bằng mắt trên trang render.
- **Tương phản màu, trình đọc màn hình, bàn phím** cho panel mới — không quét.
- **Grounding của hai route gợi ý** (`suggestion`, `contextual-suggestion` có
  `source: "ai"`) — không kiểm ảo giác, không kiểm căn cứ.
- **Mã QR quét bằng app ngân hàng thật** — vẫn là ô chưa quét của cả sản phẩm, không
  liên quan PR này nhưng chưa ai đóng.

---

## Tóm tắt cho người sửa

Sửa một chỗ: hợp đồng "4 tab" trong `tests/nhom-chat-web.test.mjs`. Chạy `npm test`
trong cây sạch, thấy xanh, đẩy lại — tôi test lại đúng SHA mới. Hai suggestion S1/S2
tuỳ bạn, không chặn.

Và vì PR đứng sau `main` 22 commit: rebase trước khi đẩy, để lần đo sau của tôi
không phải suy diễn từ một cây gộp tôi tự dựng.
