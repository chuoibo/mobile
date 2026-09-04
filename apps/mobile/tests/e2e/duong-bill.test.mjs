/* Bước bill của đường hero, qua đúng client mà app dùng.
 *
 * `vertical-slice.test.mjs` bắt đầu từ một khoản chi đã có sẵn. Nửa trước nó --
 * CHỤP BILL -> AI đọc từng món -> gán món cho người -- chưa có cổng nào đi qua.
 * Đo được, không phải phỏng đoán: trước file này
 *
 *     grep -rn "taoBill\|luuGanMon" --include=*.mjs --include=*.ts .
 *
 * chỉ ra `src/api.ts` (nơi định nghĩa) và `App.tsx` (nơi gọi thật). Không một
 * test nào, ở bất kỳ tầng nào, từng gọi hai hàm đó. `POST /bills` và
 * `PUT /bills/{id}/assignments` có test backend đầy đủ ở cả tầng fake lẫn
 * tầng postgres; `billCreateBody`/`assignmentsBody` có test thuần client ở
 * `tests/bill-gan-mon.test.mjs`. Hai nửa đều xanh, và chưa ai từng nối chúng
 * lại với nhau.
 *
 * Đó chính là hình dạng đã làm hỏng cả buổi tối 30/08. #235 siết
 * `POST /expenses/{id}/confirm` để chỉ ghi nợ cho thành viên ACTIVE. Backend
 * xanh, client "đang chạy", hợp lại thì chốt bill trả 422 cho MỌI người, vì
 * client gửi một nhóm chưa bao giờ tồn tại. Không cổng nào thấy, tới lúc
 * #239 thêm chặng e2e mới lộ.
 *
 * #247 vừa siết đúng như thế trên ĐƯỜNG BILL: `confirm_bill_assignments` giờ
 * đòi mọi người được gán món phải là thành viên active. Cùng một loại thay
 * đổi, cùng một chỗ mù -- lần này có cổng trước.
 *
 * Cần server thật, và bỏ qua khi không có, giống `vertical-slice.test.mjs`.
 * `MOBILE_REQUIRE_E2E=1` biến một lần bỏ qua thành một lần hỏng.
 * `scripts/gate.sh e2e` tự dựng API + PostgreSQL rồi đặt cờ đó.
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  attemptFor,
  BASE_URL,
  docBill,
  luuGanMon,
  newAttempt,
  taoBill,
} from "../../dist-test/api.js";
import { khoiDongNhom } from "../../dist-test/screens/chat/nhom.js";
import { DEMO_PEOPLE, personById } from "../../dist-test/rudi/nhom-demo.js";
import { batPhienE2E } from "./phien-e2e.mjs";

// The API this file talks to runs in `prod` and does not believe `X-Actor-ID`
// (ADR-0014). `scripts/e2e_slice.sh` mints a real session per demo person and
// names the file in MOBILE_E2E_SESSIONS; without it -- a `dev` server -- this
// returns null and changes nothing.
const NGUOI_DANG_NHAP = batPhienE2E(personById("minh")?.personId);

/* Tự chứa, không dùng chung helper với `vertical-slice.test.mjs`.
 *
 * Không phải vì trùng lặp là tốt. Vì hai file cùng thư mục này đang được sửa
 * trên hai nhánh song song (#245 thêm `so-du-cuoi-duong-di.test.mjs`), và một
 * module dùng chung là đúng một file để ba PR cùng giành. Gộp lại khi cả ba
 * đã vào main là việc rẻ; gỡ một xung đột ngữ nghĩa giữa ba nhánh thì không. */
const SLUGS = ["minh", "trang", "ngoc"];

function tenCuaNguoi(personId, displayName) {
  return (
    displayName ?? DEMO_PEOPLE.find((p) => p.personId === personId)?.name ?? personId
  );
}

/**
 * Mở nhóm demo và trả về roster ACTIVE của nó.
 *
 * Lọc `state === "active"` là bản sao đúng của `nguoiCoTheChia` trong
 * `App.tsx`: đó là danh sách app vẽ thành nút bấm trên màn gán món. Cổng này
 * chỉ có nghĩa nếu nó gán món cho đúng những người app cho phép gán -- gán
 * cho một id nào khác là kiểm một màn hình không tồn tại.
 */
async function moNhom() {
  let state = null;
  for (const slug of SLUGS) {
    // `khoiDongNhom` takes the person, not the slug (bug-223337): a slug has no
    // `.personId`, so passing one addresses `PUT /people/undefined` and the run
    // dies at `dat-ten` on `X-Actor-ID must be a UUID`. `.mjs` is not typed, so
    // only a live run says so.
    const nguoiDangNhap = personById(slug);
    assert.ok(nguoiDangNhap, `khong co nguoi "${slug}" trong nhom demo`);
    state = await khoiDongNhom(nguoiDangNhap, { base: BASE_URL });
    if (state.kind !== "xong") {
      assert.fail(
        `khong mo duoc nhom o buoc "${state.buoc}" (${state.status}) ${state.url}: ${state.detail}`,
      );
    }
  }
  const nguoi = state.members
    .filter((m) => m.state === "active")
    .map((m) => ({ id: m.personId, name: tenCuaNguoi(m.personId, m.displayName) }));
  assert.equal(
    nguoi.length,
    SLUGS.length,
    `nhom co ${nguoi.length} thanh vien active, cho doi ${SLUGS.length}`,
  );
  return { contextId: state.contextId, nguoi };
}

/** Một tờ bill hai món, hình dạng đúng như màn sửa lại trả ra sau khi đọc ảnh. */
function toBill() {
  return {
    lines: [
      {
        id: "mon-0",
        name: "Lẩu thái",
        quantity: 1,
        lineTotalVnd: 360000,
        read: { name: "Lau thai", quantity: 1, lineTotalVnd: 360000 },
      },
      {
        id: "mon-1",
        name: "Trà tắc",
        quantity: 2,
        lineTotalVnd: 60000,
        read: { name: "Tra tac", quantity: 2, lineTotalVnd: 60000 },
      },
    ],
    printedTotalVnd: 420000,
    needsReview: false,
    warnings: [],
  };
}

function idsCuaMon(bill, itemKey) {
  const item = bill.items.find((i) => i.item_key === itemKey);
  assert.ok(item, `bill khong co mon "${itemKey}"`);
  return item.shares.map((s) => s.participant_id).sort();
}

function nguonCuaMon(bill, itemKey) {
  const item = bill.items.find((i) => i.item_key === itemKey);
  assert.ok(item, `bill khong co mon "${itemKey}"`);
  return [...new Set(item.shares.map((s) => s.source))].sort();
}

async function serverIsUp() {
  try {
    const response = await fetch(`${BASE_URL}/healthz`);
    return response.ok;
  } catch {
    return false;
  }
}

/** Đặt khác rỗng khi một lần bỏ qua phải được đọc là một lần hỏng. */
const REQUIRED = Boolean(process.env.MOBILE_REQUIRE_E2E);

/** @returns true khi người gọi phải return sớm. */
async function skipWithoutServer(t) {
  if (await serverIsUp()) return false;
  if (REQUIRED) {
    assert.fail(
      `MOBILE_REQUIRE_E2E dat roi nhung khong co server tai ${BASE_URL}. ` +
        `Chay uvicorn tren cong do roi chay lai.`,
    );
  }
  t.skip(`khong co server tai ${BASE_URL} — chay uvicorn roi chay lai`);
  return true;
}

test("một tờ bill đi từ ảnh tới món mang tên người trong nhóm", async (t) => {
  if (await skipWithoutServer(t)) return;

  const { contextId, nguoi } = await moNhom();
  const [a, b, c] = nguoi;
  const lanBam = {};
  const reading = toBill();

  // Cái AI đoán: lẩu cả ba người, trà tắc của một người. Gửi lên như GỢI Ý.
  const goiY = { "mon-0": [a.id, b.id, c.id], "mon-1": [c.id] };

  const bill = await taoBill(reading, contextId, goiY, a.id, attemptFor(lanBam, "tao-bill"));

  assert.ok(bill.id, "POST /bills khong tra ve id");
  assert.equal(bill.context_id, contextId);
  assert.equal(bill.items_total_vnd, 420000, "tong dong khong khop tong dong cac mon");
  assert.equal(bill.items.length, 2);

  // Chưa ai bấm gì, nên mọi share phải còn mang nhãn phỏng đoán. Đây là tính
  // chất tách "AI đoán" khỏi "người đồng ý", và là thứ màn hình vẽ khác nhau.
  assert.equal(bill.assignment_state, "ai_suggested");
  assert.deepEqual(nguonCuaMon(bill, "mon-0"), ["ai_suggested"]);
  assert.deepEqual(idsCuaMon(bill, "mon-0"), [a.id, b.id, c.id].sort());

  // Người dùng sửa lại: trà tắc hoá ra hai người uống. Rồi bấm xác nhận.
  const daChot = { "mon-0": [a.id, b.id, c.id], "mon-1": [b.id, c.id] };
  const sauKhiChot = await luuGanMon(
    bill.id,
    reading,
    daChot,
    a.id,
    contextId,
    attemptFor(lanBam, "gan-mon"),
  );

  assert.equal(sauKhiChot.assignment_state, "confirmed", "gan mon xong ma van la phong doan");
  assert.deepEqual(sauKhiChot.suggested_item_keys, [], "van con mon mang nhan goi y");
  assert.deepEqual(nguonCuaMon(sauKhiChot, "mon-1"), ["confirmed"]);
  assert.deepEqual(idsCuaMon(sauKhiChot, "mon-1"), [b.id, c.id].sort());

  // Đọc lại bằng một lời gọi khác, không tin đối tượng vừa trả về.
  //
  // Đây là tính chất #237 ship: ticks sống sót qua lần đóng app. Một máy chủ
  // trả về đúng thân request rồi rollback vẫn làm mọi assert ở trên xanh.
  const docLai = await docBill(bill.id, a.id, contextId);
  assert.equal(docLai.id, bill.id);
  assert.equal(docLai.assignment_state, "confirmed");
  assert.deepEqual(idsCuaMon(docLai, "mon-1"), [b.id, c.id].sort());
  assert.deepEqual(idsCuaMon(docLai, "mon-0"), [a.id, b.id, c.id].sort());
});

test("không gán được món cho người ngoài nhóm", async (t) => {
  if (await skipWithoutServer(t)) return;

  const { contextId, nguoi } = await moNhom();
  const [a] = nguoi;
  const lanBam = {};
  const reading = toBill();

  const bill = await taoBill(
    reading,
    contextId,
    { "mon-0": [a.id], "mon-1": [a.id] },
    a.id,
    attemptFor(lanBam, "tao-bill"),
  );

  // Một UUID hợp lệ không trỏ tới ai. Trước #247 máy chủ nhận nó và trả 200:
  // `ExpenseItemShare.participant_id` không có FK sang `people`, nên hàng lưu
  // xuống nguyên vẹn rồi quay ra ở `GET /bills/{id}` như món của một người,
  // kèm `decided_by_id` nói rằng đã có người ĐỒNG Ý.
  //
  // Viết bằng hex nhiều chữ cái, không phải một dãy số 0: repo guard chặn dãy
  // 20 chữ số liền, và một allowlist entry cho một id bịa ra là trả giá đúng
  // chỗ sai -- luật đó tồn tại để chặn số tài khoản thật lọt vào Git.
  const nguoiLa = "3f1c9a7e-4b2d-4e6a-9c8f-a1b2c3d4e5f6";

  await assert.rejects(
    () =>
      luuGanMon(
        bill.id,
        reading,
        { "mon-0": [a.id, nguoiLa], "mon-1": [a.id] },
        a.id,
        contextId,
        newAttempt(),
      ),
    (error) => error.status === 422,
    "may chu nhan mon gan cho nguoi khong o trong nhom",
  );

  // Và lời từ chối phải không để lại gì. Một máy chủ ghi rồi mới kiểm cũng
  // ném đúng exception; hàng đã ghi mới là thứ quay lại ở lần đọc sau.
  const docLai = await docBill(bill.id, a.id, contextId);
  assert.deepEqual(idsCuaMon(docLai, "mon-0"), [a.id]);
  assert.equal(docLai.assignment_state, "ai_suggested", "loi tu choi van doi trang thai bill");
});

test("bấm hai lần chỉ tạo một tờ bill", async (t) => {
  if (await skipWithoutServer(t)) return;

  const { contextId, nguoi } = await moNhom();
  const [a] = nguoi;
  const reading = toBill();
  const goiY = { "mon-0": [a.id], "mon-1": [a.id] };

  // `taoBill` mô tả đúng ca này trong docstring của nó -- "Two presses of
  // 'Tiếp tục' on a slow connection are one person asking once" -- và cho tới
  // đây chưa có gì kiểm câu đó với một máy chủ thật.
  const attempt = newAttempt();
  const lan1 = await taoBill(reading, contextId, goiY, a.id, attempt);
  const lan2 = await taoBill(reading, contextId, goiY, a.id, attempt);

  assert.equal(lan2.id, lan1.id, "hai lan bam de lai hai to bill cho mot bua an");

  const khac = await taoBill(reading, contextId, goiY, a.id, newAttempt());
  assert.notEqual(khac.id, lan1.id, "mot to bill khac lai bi gop vao to cu");
});
