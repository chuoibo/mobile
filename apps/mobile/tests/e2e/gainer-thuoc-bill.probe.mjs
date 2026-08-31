/* Hỏi MÁY CHỦ THẬT: `rounding_gainers` có bao giờ nằm ngoài roster client gửi không?
 *
 * Vì sao phép đo này tồn tại. `DeXuat` là màn chốt tiền vào sổ, và nó đặt tên
 * cho hai thứ đến từ câu trả lời của máy chủ: `advancerId` và mỗi id trong
 * `roundingGainers`. Bản vá bug-050923 đổi `?? id` thành `labelInGroup`, nên
 * hôm nay chỗ đó in "Thành viên" thay vì một UUID 36 ký tự. Nhưng câu hỏi Lead
 * đặt ra không phải "đã vá chưa" mà là **"chỗ đó có phải rò rỉ THẬT không,
 * hay chỉ khớp hình dạng"** — và câu đó chỉ trả lời được bằng cách hỏi máy chủ.
 *
 * Đọc mã nguồn KHÔNG trả lời được, vì có hai đường hỏng khác nhau:
 *
 *   1. TẬP HỢP — máy chủ trả về một id không có trong `participants` client
 *      gửi (người trả trước không nằm trên bill, một người từ roster của máy
 *      chủ, ...). `allocator._apportion` lấy `ranked[:deficit]` từ `exact`, nên
 *      trên giấy là tập con. "Trên giấy" không phải số đo.
 *   2. CHỮ HOA CHỮ THƯỜNG — máy chủ nhận `participants` là chuỗi, pydantic
 *      dựng `UUID`, rồi in lại. Nếu client giữ một id có chữ HOA thì bản in ra
 *      là chữ thường, và `roster.find((p) => p.id === id)` TRƯỢT dù đó đúng là
 *      người ấy. Cùng một triệu chứng, nguyên nhân khác hẳn, và không có phép
 *      đọc mã nào bắt được nó.
 *
 * Cùng câu hỏi cho `allocation.allocations`: `DeXuat` đọc
 * `proposal.allocations[person.id]`, nên một id lệch ở đó cho ra `undefined`
 * chứ không phải một con số.
 *
 * ĐỐI CHỨNG ÂM là bắt buộc và chạy trước. Một phép đo trả "0 vi phạm" mà chưa
 * chứng minh nó ĐỎ được thì không phân biệt được với một phép đo hỏng.
 *
 *   EXPO_PUBLIC_API_URL=http://127.0.0.1:8099 node tests/e2e/gainer-thuoc-bill.probe.mjs
 *
 * Mã thoát: 0 khi mọi ca đạt và đối chứng âm đỏ đúng chỗ; 2 khi có vi phạm
 * hoặc khi đối chứng âm không đỏ được (phép đo tự khai là mù).
 */

const BASE = process.env.EXPO_PUBLIC_API_URL;
if (!BASE) {
  console.error("thiếu EXPO_PUBLIC_API_URL — phép đo này cần MỘT MÁY CHỦ THẬT, không có bản giả");
  process.exit(2);
}

const uuid = () => crypto.randomUUID();

/** Đúng phép so client làm: `Array.prototype.find` với `===` trên chuỗi id.
 *
 * Viết lại ở đây thay vì import `labelInGroup` là có chủ ý: cái đang được đo là
 * QUAN HỆ giữa chuỗi máy chủ gửi và chuỗi client giữ, không phải nhánh dự phòng
 * client chọn khi quan hệ đó gãy. Nhánh dự phòng đã có bộ ca riêng.
 */
function doiChieu(nhan, guiDi, allocation) {
  const coTrenBill = new Set(guiDi);
  const gainerLac = (allocation.rounding_gainers ?? []).filter((id) => !coTrenBill.has(id));
  const keyLac = Object.keys(allocation.allocations ?? {}).filter((id) => !coTrenBill.has(id));
  const thieuKey = guiDi.filter((id) => !(id in (allocation.allocations ?? {})));
  return { nhan, gainerLac, keyLac, thieuKey, soGainer: (allocation.rounding_gainers ?? []).length };
}

function inKetQua(r) {
  const viPham = r.gainerLac.length + r.keyLac.length + r.thieuKey.length;
  const dau = viPham === 0 ? "OK  " : "VI PHẠM";
  console.log(
    `  ${dau} ${r.nhan.padEnd(38)} gainer=${r.soGainer}` +
      (r.gainerLac.length ? ` gainer-ngoài-bill=${JSON.stringify(r.gainerLac)}` : "") +
      (r.keyLac.length ? ` key-ngoài-bill=${JSON.stringify(r.keyLac)}` : "") +
      (r.thieuKey.length ? ` thiếu-key=${JSON.stringify(r.thieuKey)}` : ""),
  );
  return viPham;
}

// ---------------------------------------------------------------------------
// ĐỐI CHỨNG ÂM — chạy TRƯỚC, ngoại tuyến. Phép so phải đỏ được ở cả hai đường.
// ---------------------------------------------------------------------------
console.log("đối chứng âm (không chạm máy chủ) — phép so có đỏ được không:");
const ba = [uuid(), uuid(), uuid()];
const chungAm = [
  {
    ten: "1. id máy chủ tự chế, không hề gửi",
    guiDi: ba,
    allocation: {
      allocations: Object.fromEntries(ba.map((id) => [id, 33])),
      rounding_gainers: [uuid()],
    },
  },
  {
    ten: "2. ĐÚNG người, nhưng máy chủ in chữ thường",
    guiDi: ba.map((id) => id.toUpperCase()),
    allocation: {
      allocations: Object.fromEntries(ba.map((id) => [id, 33])),
      rounding_gainers: [ba[0]],
    },
  },
  {
    ten: "3. sạch — phải KHÔNG đỏ",
    guiDi: ba,
    allocation: {
      allocations: Object.fromEntries(ba.map((id) => [id, 33])),
      rounding_gainers: [ba[0]],
    },
  },
];
let chungAmHong = 0;
for (const [i, c] of chungAm.entries()) {
  const viPham = inKetQua(doiChieu(c.ten, c.guiDi, c.allocation));
  const phaiDo = i < 2;
  if (phaiDo !== viPham > 0) {
    console.log(`    ^^ đối chứng âm SAI HƯỚNG: mong ${phaiDo ? "ĐỎ" : "XANH"}`);
    chungAmHong++;
  }
}
if (chungAmHong > 0) {
  console.error(`\nDỪNG: ${chungAmHong} đối chứng âm sai hướng. Mọi số 0 bên dưới sẽ vô nghĩa.`);
  process.exit(2);
}
console.log("  -> phép so đỏ được ở CẢ HAI đường hỏng, và không đỏ nhầm ở ca sạch.\n");

// ---------------------------------------------------------------------------
// Máy chủ thật
// ---------------------------------------------------------------------------

/** `POST /expenses` đi ẩn danh, nhưng nhóm nó ghi vào thì phải có thật.
 *
 *  Một `context_id` bịa ra trả 404 `context_not_found` cho MỌI ca, và 0/6 ca
 *  hỏi được sẽ in ra "0 vi phạm" nếu ai đó chỉ nhìn con số cuối. Nên phần đếm
 *  ở dưới coi ca lỗi là hỏng, chứ không coi là im lặng.
 */
const ROLES = "member,advancer,recipient,batch_owner";
async function dungNhom() {
  const actor = uuid();
  const headers = { "Content-Type": "application/json", "X-Actor-ID": actor, "X-Actor-Roles": ROLES };
  const nguoi = await fetch(`${BASE}/people/${actor}`, {
    method: "PUT",
    headers: { ...headers, "Idempotency-Key": uuid() },
    body: JSON.stringify({ display_name: "Đo gainer" }),
  });
  if (!nguoi.ok) throw new Error(`không tạo được người đo: ${nguoi.status} ${await nguoi.text()}`);
  const res = await fetch(`${BASE}/contexts`, {
    method: "POST",
    headers: { ...headers, "Idempotency-Key": uuid() },
    body: JSON.stringify({ display_name: `do-gainer-${actor.slice(0, 8)}` }),
  });
  if (!res.ok) throw new Error(`không mở được nhóm: ${res.status} ${await res.text()}`);
  return (await res.json()).id;
}

const contextId = await dungNhom();

async function hoiMayChu({ participants, payerId, totalVnd, items = [] }) {
  const body = {
    context_id: contextId,
    description: "đo gainer",
    recorded_by_id: payerId,
    paid_by_id: payerId,
    verification_scope: items.length > 0 ? "items_reviewed" : "totals_only",
    // Mốc cố định, không phải đồng hồ: một lượt chạy lại phải gửi đúng bytes cũ.
    occurred_at: "2026-08-31T00:00:00Z",
    participants,
    total_amount_vnd: totalVnd,
    items,
    surcharges: [],
    discounts: [],
  };
  const res = await fetch(`${BASE}/expenses`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": uuid() },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  if (!res.ok) return { loi: `${res.status} ${text.slice(0, 200)}` };
  return { allocation: JSON.parse(text).allocation };
}

/** Mỗi ca chọn tổng tiền để CÓ đồng lẻ: không dư thì không có gainer nào để đo. */
const caThat = [
  { ten: "A. 3 người, 100đ (dư 1)", n: 3, totalVnd: 100 },
  { ten: "B. 7 người, 100đ (dư 2)", n: 7, totalVnd: 100 },
  { ten: "C. 3 người, 1.000.001đ (dư 2)", n: 3, totalVnd: 1000001 },
  { ten: "D. người trả trước KHÔNG trên bill", n: 3, totalVnd: 100, payerNgoaiBill: true },
  { ten: "F. có dòng món (items_reviewed)", n: 3, totalVnd: 100, coMon: true },
];

async function chay(ca) {
  let participants = Array.from({ length: ca.n }, uuid);
  if (ca.chuHoa) participants = participants.map((id) => id.toUpperCase());
  const payerId = ca.payerNgoaiBill ? uuid() : participants[0];
  const items = ca.coMon
    ? [{ item_id: "mon-1", label: "Một món", amount_vnd: 100, shared_by: participants }]
    : [];
  const r = await hoiMayChu({ participants, payerId, totalVnd: ca.totalVnd, items });
  if (r.loi) {
    console.log(`  LỖI  ${ca.ten.padEnd(38)} ${r.loi}`);
    return null;
  }
  return doiChieu(ca.ten, participants, r.allocation);
}

console.log(`máy chủ: ${BASE}\nnhóm   : ${contextId}`);
console.log("\nCÂU 1 — tập hợp: máy chủ có bao giờ đặt tên một người KHÔNG trên bill không?");
let viPhamTapHop = 0;
let caLoi = 0;
for (const ca of caThat) {
  const r = await chay(ca);
  if (r === null) caLoi++;
  else viPhamTapHop += inKetQua(r);
}

/* CÂU 2 là một câu khác hẳn, và gộp nó vào câu 1 sẽ đọc sai theo cả hai hướng.
 *
 * Máy chủ in lại id bằng chữ thường là ĐÚNG -- `UUID` là một giá trị, không
 * phải một chuỗi, và RFC 4122 in ra chữ thường. Cái sai nằm ở phía client, nếu
 * client giữ một id không chuẩn rồi so bằng `===`. Nên ca này không tính vào
 * "vi phạm": nó là ĐỐI CHỨNG DƯƠNG cho `tests/id-nguoi-luon-chuan.test.mjs`.
 *
 * Và nó phải TÁI LẬP ĐƯỢC. Ngày nào máy chủ thôi chuẩn hoá, cổng kia đang gác
 * một cơ chế không còn tồn tại, và đó cũng là tin cần biết -- nên ca này đỏ
 * theo chiều ngược lại: không tái lập được cũng là hỏng.
 */
console.log("\nCÂU 2 — chữ viết: id client giữ bằng CHỮ HOA thì còn khớp được không?");
const eChuHoa = await chay({ ten: "E. id client giữ bằng CHỮ HOA", n: 3, totalVnd: 100, chuHoa: true });
if (eChuHoa === null) caLoi++;
else inKetQua(eChuHoa);
const chuanHoaConThat = eChuHoa !== null && eChuHoa.gainerLac.length + eChuHoa.thieuKey.length > 0;

console.log("\n--- phán quyết ---");
console.log(`ca hỏi máy chủ được          : ${caThat.length + 1 - caLoi}/${caThat.length + 1}`);
console.log(`câu 1, vi phạm tập hợp       : ${viPhamTapHop}`);
console.log(`câu 2, máy chủ chuẩn hoá chữ : ${chuanHoaConThat ? "CÓ (tái lập được)" : "KHÔNG"}`);
console.log(
  viPhamTapHop === 0
    ? "=> Không id nào từ máy chủ đi ra ngoài roster client gửi. Hai chỗ DeXuat là\n" +
        "   HÌNH DẠNG của bug-050923, không phải một lần bắt gặp nó sống."
    : "=> CÓ id ra ngoài roster. Đây là rò rỉ THẬT, không phải hình dạng.",
);
if (!chuanHoaConThat) {
  console.log(
    "=> CHÚ Ý: không tái lập được việc máy chủ đổi chữ hoa thành chữ thường.\n" +
      "   `tests/id-nguoi-luon-chuan.test.mjs` được viết ra để gác đúng cơ chế đó.",
  );
}
process.exit(viPhamTapHop === 0 && caLoi === 0 && chuanHoaConThat ? 0 : 2);
