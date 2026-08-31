# Gác PR #468 — cỗ máy quét mặc định "?? id"

- protocol_version: v1
- commit được gác: `8581c11bbc8e5d567cf669120e1803ac75d02e2d` (nhánh `frontend/co-may-sinh-mac-dinh-id`, chưa merge)
- nền so sánh: `origin/main` = `475244f`
- verdict: **APPROVE**
- blocker còn mở: không
- kỹ năng đã dùng: `e2e-testing`, `bug-reproduction`

## PASS

**Lý do:** cổng xanh đủ ở SHA đã test, và đối chứng đứng vững — máy quét ĐỎ được đúng
hai dòng `DeXuat.tsx` khi tôi hoàn nguyên bản vá, ba phép đối chứng của chính nó ĐỎ khi
tôi rút ruột walker, và chỗ thứ ba tuy máy quét không gác nhưng `tsc` gác (exit 2). Không
phát hiện nào rơi vào 5 loại blocker. Hai ghi chú hiệu chỉnh ở dưới là **suggestion**.

```
đo tại   8581c11bbc8e5d567cf669120e1803ac75d02e2d
sha này  là nhánh CHƯA merge, sau origin/main 4 commit (475244f)
         4 commit đó KHÔNG chạm apps/mobile — git merge-tree exit 0, không xung đột
```

### Cổng đã chạy (cây sạch)

| lệnh | kết quả |
|---|---|
| `cd apps/mobile && npm test` | **1025 pass, 0 fail, 0 skipped** |
| `python3 -m pytest services/api/tests tests -q` | **2833 passed, 580 skipped** |

580 skip là tầng Postgres. PR này chạm 0 file backend nên tầng đó không phải cái gác nó
— tôi ghi ra chứ không tính là đã quét.

### Đối chứng — đỏ TRƯỚC vá

**1. Hai chỗ `DeXuat.tsx`: máy quét bắt được.** Hoàn nguyên về bản trước vá:

```
not ok 4 - không giá trị hiển thị nào lấy id thô làm mặc định
    còn 2 chỗ lấy id làm mặc định:
    screens/DeXuat.tsx:37  people.find((p) => p.id === proposal.advancerId)?.name ?? proposal.advancerId
    screens/DeXuat.tsx:40  people.find((p) => p.id === id)?.name ?? id
```

Đúng hai dòng, đúng tên file. Vá lại → 4/4 xanh.

**2. Ba phép đối chứng là thật, không phải trang trí.** Tôi rút ruột walker cho
`fallbacksToId` trả `{hits: [], seen: 0}` — đúng kiểu "chết im lặng" tác giả mô tả:

```
not ok 1 - phép quét nhận ra hình dạng...      ← fixture
not ok 2 - phép quét ĐỎ được trên bản trước vá ← đối chứng ghim sha
not ok 3 - phép quét thật sự đọc hết cây nguồn ← cọc sàn
ok     4 - không giá trị hiển thị nào lấy id thô làm mặc định   ← XANH RỖNG
```

Đây là hình dạng đúng: phép kiểm chính xanh vô nghĩa, cả ba đối chứng đỏ. Cổng này
không chết im được.

**3. Sha ghim `0c04cb7` KHÔNG mồ côi.** Tôi kiểm riêng vì repo này từng mất một phán
quyết theo đúng cách đó: `git merge-base --is-ancestor 0c04cb7 origin/main` → **có**,
nằm trong lịch sử `main`. Đối chứng đỏ sống sót qua clone sạch.

### Hai ghi chú hiệu chỉnh (suggestion, không chặn)

**a) Chỗ thứ ba được gác bằng cơ chế KHÁC, không phải máy quét này.**

Bảng trong mô tả xếp cả ba chỗ như nhau, nhưng `tim-kiem.ts` không phải một lần gỡ
`?? id` — biểu thức `nhan.get(id) ?? id` vẫn còn và nằm trong allowlist; cái được gỡ là
mặc định `= []`. Hoàn nguyên riêng nó thì **toàn bộ 1025 test vẫn xanh**. Cái gác nó là
`tsc`, theo chiều tiến:

```
$ # cho một chỗ gọi bỏ quên categories
src/screens/kham-pha/CauAiHieu.tsx(50,16): error TS2554: Expected 2 arguments, but got 1.
npm test exit thật = 2
```

Nên nó CÓ được gác, chỉ là bằng trình biên dịch chứ không bằng cổng mới. Đáng nói ra vì
người đọc bảng sẽ tưởng một máy quét đang giữ cả ba.

**b) Con số "3" là 3 *trong ba cách viết*, không phải 3 chỗ đúc id thô.**

Mô tả nói thẳng phạm vi là `??`, `||`, ternary — nên đây không phải lời hứa bị lỗi. Tôi
đo phần còn lại: **9/10 cách viết khác lọt**, gồm `??=`, `||=`, `?? (id)`, `?? String(id)`,
`` ?? `${id}` ``, `?? id.slice(0,8)`, tham số mặc định, `as string`.

Đáng chú ý nhất là `??=`/`||=`: cùng họ toán tử, cách một token
(`QuestionQuestionEqualsToken`), và **đội này thật sự viết nó** — 3 chỗ đang sống:

```
src/screens/len-plan/NhanLoiMoi.tsx:57   (lanBam.current ??= newAttempt())
src/screens/len-plan/buoi-di.ts:236      (theo[c.stop_id] ??= []).push(c)
src/api.ts:142                           (book[name] ??= newAttempt())
```

**Nhưng: 0 chỗ sống trong cây hôm nay lọt qua.** Tôi viết một máy quét rộng hơn (đi
xuyên ngoặc/`as`/template/call, cộng tham số mặc định) chạy trên 125 file nguồn thật.
Nó ra 4 chỗ, và cả 4 là **dương tính giả của máy quét TÔI**, không phải lỗ của cổng:

- `chat/binh-chon.ts:143` — `!optionId || daThay.has(optionId)`: guard boolean khử trùng, không hiển thị gì
- `kham-pha/ban-do-nhom.ts:320/324/328` — `contextId: string = CONTEXT_ID`: id đi vào đường dẫn URL, tức id dùng LÀM id

Nên **"3" đúng ở hôm nay**. Khoảng hở là chống-tương-lai, không phải rò rỉ đang chạy —
và vì thế nó là suggestion. Nếu muốn đóng rẻ: thêm hai token `??=`/`||=` và bóc
`ParenthesizedExpression`/`AsExpression` trong `idBearing` là bịt được phần lớn.

### Ô CHƯA quét

- Tầng Postgres (580 skip) — PR không chạm backend, tôi không chạy.
- `npm run test:e2e` — chưa chạy (cần uvicorn + Postgres); PR không đổi hợp đồng client.
- Màn `DeXuat` **chưa được nhìn bằng mắt** ở bản vá. Tác giả khai hai bản render
  `de-xuat.html` TRƯỚC/SAU giống hệt từng byte — tôi **không** tự dựng lại bundle để
  kiểm lời khai đó, nên nó vẫn là lời khai của tác giả, không phải số đo của tôi.
- Mã QR quét bằng app ngân hàng thật — vẫn chưa ai làm.
