/* Khoản chi phải đi vào nhóm CÓ THẬT, cả trong thân lẫn trên header.
 *
 * bug-053800. `src/api.ts` giữ một hằng số `CONTEXT_ID` =
 * `1aa00000-aaaa-4aaa-8aaa-0000a0000001`, và hai comment trong chính repo này
 * nói thẳng ra rằng nó chưa bao giờ có row trong bảng `contexts`. Mọi khoản
 * chi trong app đều gửi id đó.
 *
 * Sống được chừng nào máy chủ còn tin lời người gọi. `POST /expenses` chỉ
 * chia tiền chứ không ghi gì, nên nó trả 200 và màn đề xuất hiện đúng số.
 * `_require_participants_are_members` (service.py) đóng cửa đó lại: nhóm
 * không tồn tại thì không có thành viên nào, nên MỌI người trên bill đều là
 * người lạ, và `confirm` trả `422 participant_not_in_context` -- cho mọi
 * người dùng, trên đúng con đường sản phẩm này sinh ra để trình diễn.
 *
 * Hai nửa, và vá một nửa thì chỉ đổi mã lỗi:
 *
 *   1. Thân request: `context_id` phải là nhóm người gọi nêu tên.
 *   2. Header `X-Actor-Contexts`: `confirm_expense` và `create_batch` so nó
 *      với chính nhóm của khoản chi (service.py:1969, :2026), nên thân đúng
 *      mà header còn hằng số cũ thì 422 chỉ biến thành 403.
 *
 * Vì sao bộ test này đỏ được ở bản CŨ: `confirmExpense` và `openBatch` giữ
 * nguyên chữ ký qua bản vá. Cùng một lời gọi, bản cũ gửi hằng số tổng hợp,
 * bản mới gửi nhóm nằm trên proposal.
 *
 * Chạy từ apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs \
 *       && node --test tests/nhom-cua-khoan-chi.test.mjs
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  attemptFor,
  confirmExpense,
  loadBoard,
  openBatch,
  previewSplit,
  proposeSplit,
} from "../dist-test/api.js";

/** Hằng số cũ. Không import được nữa -- đó chính là một nửa bản vá -- nên
 *  viết lại ở đây để quét: nó không được xuất hiện trong bất kỳ request nào. */
const ID_TONG_HOP = "1aa00000-aaaa-4aaa-8aaa-0000a0000001";

/** Một nhóm có thật, dạng `khoiDongNhom` trả về. */
const NHOM = "7c9e6679-7425-40de-944b-e07fc1f90ae7";

const NGUOI = [
  { id: "6b4bda36-93e6-4a94-b7ca-48757974f361", name: "Hà" },
  { id: "6b4bda36-93e6-4a94-b7ca-48757974f362", name: "Nam" },
];
const ACTOR = NGUOI[0].id;

const DRAFT = {
  occasion: "Bún chả",
  participants: NGUOI,
  advancerId: ACTOR,
  totalVnd: 240_000,
};

const PROPOSAL = {
  expenseId: "e-1",
  serverProposal: { context_id: NHOM, total_amount_vnd: 240_000 },
  allocations: { [NGUOI[0].id]: 120_000, [NGUOI[1].id]: 120_000 },
  roundingGainers: [],
  totalVnd: 240_000,
  advancerId: ACTOR,
  occasion: "Bún chả",
  participants: NGUOI,
  contextId: NHOM,
};

function traLoi(path) {
  if (path.endsWith("/confirm")) {
    return { expense_version_id: "v-1", payer_acknowledgement: "acknowledged" };
  }
  if (path.endsWith("/expenses")) {
    return {
      expense_id: "e-1",
      proposal: PROPOSAL.serverProposal,
      allocation: { allocations: PROPOSAL.allocations, rounding_gainers: [] },
    };
  }
  if (path.endsWith("/batches")) return { batch_id: "b-1", obligations: [] };
  if (path.endsWith("/obligations")) return { disputed_count: 0, obligations: [] };
  throw new Error(`bài test chưa có câu trả lời cho ${path}`);
}

/** Ghi lại mọi thứ rời khỏi app. */
function bat() {
  const that = globalThis.fetch;
  const gui = [];
  globalThis.fetch = async (url, init) => {
    const path = new URL(String(url)).pathname;
    gui.push({
      path,
      headers: init?.headers ?? {},
      body: init?.body === undefined ? null : String(init.body),
    });
    return new Response(JSON.stringify(traLoi(path)), {
      status: 201,
      headers: { "Content-Type": "application/json" },
    });
  };
  return {
    gui,
    thoi() {
      globalThis.fetch = that;
    },
  };
}

/** Mỗi lời gọi trên đường chốt bill, cùng một nhóm nêu ra một lần. */
const LOI_GOI = [
  {
    ten: "POST /expenses (đề xuất)",
    duong: "/expenses",
    chay: () => proposeSplit(NHOM, DRAFT, attemptFor({}, "de-xuat")),
  },
  {
    ten: "POST /expenses (xem trước)",
    duong: "/expenses",
    chay: () =>
      previewSplit(
        {
          contextId: NHOM,
          participantIds: NGUOI.map((n) => n.id),
          totalVnd: 240_000,
          items: [],
          payerId: ACTOR,
          occasion: "xem trước chia",
        },
        attemptFor({}, "xem-truoc"),
      ),
  },
  {
    ten: "POST /expenses/{id}/confirm",
    duong: "/expenses/e-1/confirm",
    chay: () => confirmExpense(PROPOSAL, attemptFor({}, "xac-nhan")),
  },
  {
    ten: "POST /batches",
    duong: "/batches",
    chay: () => openBatch(PROPOSAL, "v-1", true, attemptFor({}, "mo-dot-thu")),
  },
  {
    ten: "GET /batches/{id}/obligations",
    duong: "/batches/b-1/obligations",
    chay: () => loadBoard(NHOM, "b-1", ACTOR, NGUOI),
  },
];

/* `POST /expenses` là lời gọi DUY NHẤT client này gửi ẩn danh -- không
 * `X-Actor-ID`, nên cũng không có header nhóm để gắn vào (xem `call` trong
 * api.ts, về vùng idempotency dùng chung). Ở đó nhóm đi trong thân request, và
 * `confirm` mới là chỗ máy chủ bắt đầu kiểm. Nên phần header dưới đây chỉ hỏi
 * những đường máy chủ THẬT SỰ gác: confirm, mở đợt thu, và bảng thu.
 * Loại trừ này viết ra để đọc được, không phải để lặng lẽ thu hẹp phạm vi. */
const CO_HEADER = LOI_GOI.filter((g) => g.duong !== "/expenses");

for (const loiGoi of CO_HEADER) {
  test(`${loiGoi.ten}: header X-Actor-Contexts mang nhóm được nêu`, async () => {
    const may = bat();
    try {
      await loiGoi.chay();
    } finally {
      may.thoi();
    }
    const req = may.gui.find((r) => r.path === loiGoi.duong);
    assert.ok(req, `không có request nào tới ${loiGoi.duong}`);
    assert.equal(
      req.headers["X-Actor-Contexts"],
      NHOM,
      `${loiGoi.ten} khai một nhóm khác trên header. ` +
        `Máy chủ so header này với nhóm của chính khoản chi, nên sai ở đây là 403.`,
    );
  });
}

for (const loiGoi of LOI_GOI.filter((g) => g.duong === "/expenses" || g.duong === "/batches")) {
  test(`${loiGoi.ten}: thân request mang nhóm được nêu`, async () => {
    const may = bat();
    try {
      await loiGoi.chay();
    } finally {
      may.thoi();
    }
    const req = may.gui.find((r) => r.path === loiGoi.duong);
    assert.ok(req?.body, `${loiGoi.ten} không gửi thân request`);
    assert.equal(
      JSON.parse(req.body).context_id,
      NHOM,
      `${loiGoi.ten} ghi khoản chi vào một nhóm khác nhóm người gọi nêu. ` +
        `Nhóm không có row thì không có thành viên, và confirm trả 422 ` +
        `participant_not_in_context cho mọi người trên bill.`,
    );
  });
}

test("không lời gọi nào còn nhắc tới id tổng hợp cũ", async () => {
  const may = bat();
  try {
    for (const loiGoi of LOI_GOI) await loiGoi.chay();
  } finally {
    may.thoi();
  }
  assert.equal(may.gui.length, LOI_GOI.length, "số request không khớp số lời gọi");
  for (const req of may.gui) {
    const noiDung = `${req.path} ${JSON.stringify(req.headers)} ${req.body ?? ""}`;
    assert.ok(
      !noiDung.includes(ID_TONG_HOP),
      `${req.path} vẫn mang ${ID_TONG_HOP}, id chưa từng có row trong contexts`,
    );
  }
});

/* Nửa còn lại của việc bỏ giá trị mặc định.
 *
 * `actorHeaders` từng mặc định `contexts = CONTEXT_ID`, nên một lời gọi QUÊN
 * nêu nhóm không hỏng mà thừa hưởng lời khai sai -- hỏng im lặng, đúng loại
 * khó thấy nhất. Giờ thiếu thì header không được gửi, và `deps.py` đọc header
 * vắng mặt thành "không thuộc nhóm nào", là câu trả lời đúng sự thật.
 */
test("lời gọi không nêu nhóm thì không gửi header, thay vì mượn một nhóm", async () => {
  const may = bat();
  try {
    await confirmExpense({ ...PROPOSAL, contextId: undefined }, attemptFor({}, "khong-nhom"));
  } finally {
    may.thoi();
  }
  const req = may.gui.find((r) => r.path === "/expenses/e-1/confirm");
  assert.ok(req, "không có request nào tới /expenses/e-1/confirm");
  assert.ok(
    !("X-Actor-Contexts" in req.headers),
    "gửi X-Actor-Contexts dù không ai nêu nhóm nào: đó là lời khai app tự bịa",
  );
});
