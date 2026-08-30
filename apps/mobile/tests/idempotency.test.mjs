/* Bấm hai lần không được biến thành hai lần ghi tiền.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/
 *
 * The server grew an `Idempotency-Key` middleware that covers every write
 * route. It only engages when the request carries the header, and this client
 * never sent one -- so the protection was installed and switched off. Measured
 * against a real server: two identical `POST /expenses` with no header left two
 * rows in `expenses`; the same two with a header left one.
 *
 * Two halves, and shipping only the first is worse than shipping neither:
 *
 *   1. Every write carries the header.
 *   2. A retry of the same press sends a byte-identical body.
 *
 * The middleware fingerprints method + path + body. Three of these bodies used
 * to stamp `new Date()` at call time (`occurred_at`, `due_at`,
 * `guest_link_expires_at`), so pressing again a minute later produced a
 * different body under the same key -- which the server answers with 422
 * `idempotency_key_reuse`. That trades a double write for a hard refusal in
 * front of a person who did nothing wrong. Hence `Attempt`: one press carries
 * both the key and the clock reading the body is built from.
 */
import assert from "node:assert/strict";
import test, { mock } from "node:test";

/** A fixed clock, so a body is comparable across two calls. */
const CLOCK = 1_700_000_000_000;

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

/** Nhóm có thật, dạng `khoiDongNhom` trả về. Đứng đây vì `proposeSplit` nhận
 *  nhóm làm tham số kể từ bug-053800: hằng số cũ chưa từng có row trong
 *  `contexts`, nên `confirm` trả 422 cho mọi khoản chi. */
const NHOM = "7c9e6679-7425-40de-944b-e07fc1f90ae7";

const PROPOSAL = {
  expenseId: "e-1",
  contextId: NHOM,
  serverProposal: { context_id: NHOM, total_amount_vnd: 240_000 },
  allocations: { [NGUOI[0].id]: 120_000, [NGUOI[1].id]: 120_000 },
  roundingGainers: [],
  totalVnd: 240_000,
  advancerId: ACTOR,
  occasion: "Bún chả",
  participants: NGUOI,
};

/** Every write the organiser flow can send, driven with an explicit attempt. */
const WRITES = [
  {
    name: "POST /expenses",
    volatile: true,
    run: (api, attempt) => api.proposeSplit(NHOM, DRAFT, attempt),
  },
  {
    name: "POST /expenses/{id}/confirm",
    volatile: false,
    run: (api, attempt) => api.confirmExpense(PROPOSAL, attempt),
  },
  {
    name: "POST /batches",
    volatile: true,
    run: (api, attempt) => api.openBatch(PROPOSAL, "v-1", true, attempt),
  },
  {
    name: "POST /batches/{id}/publish",
    volatile: true,
    run: (api, attempt) =>
      api.publishBatch("b-1", { payerAcknowledged: true }, ACTOR, attempt, NGUOI),
  },
  {
    name: "POST /obligations/{id}/confirm-receipt",
    volatile: false,
    run: (api, attempt) => api.confirmReceipt("ob-1", 100_000, ACTOR, attempt),
  },
  {
    name: "POST /contexts/{id}/outings",
    volatile: false,
    run: (api, attempt) =>
      api.taoBuoiDi(
        "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        {
          title: "Đà Lạt cuối tuần",
          starts_on: "2026-09-07",
          ends_on: "2026-09-08",
          headcount: 7,
          budget_per_person_vnd: 2_500_000,
        },
        ACTOR,
        attempt,
      ),
  },
  {
    name: "PUT /outings/{id}/timeline",
    volatile: false,
    run: (api, attempt) =>
      api.luuDongThoiGian(
        "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff",
        [{ at: "07:00", label: "Cafe", place_name: null }],
        ACTOR,
        attempt,
        "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
      ),
  },
  {
    name: "POST /outing-invites/{token}/accept",
    volatile: false,
    run: (api, attempt) => api.nhanLoiMoiBuoiDi("token-thu", ACTOR, attempt),
  },
];

function bodyFor(path) {
  if (path.endsWith("/confirm-receipt")) return { obligation_status: "confirmed" };
  if (path.endsWith("/confirm")) {
    return { expense_version_id: "v-1", payer_acknowledgement: "acknowledged" };
  }
  if (path.endsWith("/publish")) return { guest_links: [] };
  if (path.endsWith("/expenses")) {
    return {
      expense_id: "e-1",
      proposal: PROPOSAL.serverProposal,
      allocation: { allocations: PROPOSAL.allocations, rounding_gainers: [] },
    };
  }
  if (path.endsWith("/batches")) return { batch_id: "b-1", obligations: [] };
  if (path.endsWith("/accept")) {
    return {
      invite_id: "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
      outing_id: "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff",
      context_id: NHOM,
      membership_id: "cccccccc-dddd-4eee-8fff-aaaaaaaaaaaa",
      membership_state: "active",
    };
  }
  if (path.endsWith("/timeline") || path.endsWith("/outings")) {
    return {
      id: "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff",
      context_id: "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
      created_by_id: ACTOR,
      title: "Đà Lạt cuối tuần",
      starts_on: "2026-09-07",
      ends_on: "2026-09-08",
      headcount: 7,
      budget_per_person_vnd: 2_500_000,
      created_at: "2026-08-29T04:00:00Z",
      stops: [],
    };
  }
  throw new Error(`bài test chưa có câu trả lời cho ${path}`);
}

/**
 * Record what leaves the app.
 *
 * `body` is kept as the raw string rather than parsed: the server hashes the
 * bytes, so the test has to compare the bytes too. A parsed-then-deep-equal
 * check would call two different `occurred_at` values equal if the surrounding
 * keys matched, which is exactly the bug being pinned.
 */
function capture(problem = null) {
  const real = globalThis.fetch;
  const sent = [];
  globalThis.fetch = async (url, init) => {
    const path = new URL(String(url)).pathname;
    sent.push({
      path,
      method: init.method,
      headers: init.headers,
      body: init.body,
    });
    if (problem) {
      return new Response(JSON.stringify(problem), {
        status: problem.status,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(JSON.stringify(bodyFor(path)), {
      status: 201,
      headers: { "Content-Type": "application/json" },
    });
  };
  return {
    sent,
    restore() {
      globalThis.fetch = real;
    },
  };
}

test("mọi lệnh ghi đều mang header Idempotency-Key", async () => {
  const api = await import("../dist-test/api.js");
  const tap = capture();
  try {
    for (const [i, write] of WRITES.entries()) {
      await write.run(api, { key: `K-${i}`, at: CLOCK });
    }
  } finally {
    tap.restore();
  }

  assert.equal(tap.sent.length, WRITES.length);
  tap.sent.forEach((request, i) => {
    assert.equal(
      request.headers["Idempotency-Key"],
      `K-${i}`,
      `${WRITES[i].name} gửi đi mà không mang khoá của lần bấm này`,
    );
  });
});

test("gửi lại cùng một lần bấm thì payload không đổi một byte", async () => {
  // The case this exists for: the request arrived, the reply did not, and the
  // person pressed again a minute later. If the body drifted with the clock,
  // the server sees a different request under a used key and refuses with 422
  // instead of replaying the answer it already has.
  const api = await import("../dist-test/api.js");
  for (const write of WRITES) {
    const attempt = { key: "K-giu-nguyen", at: CLOCK };
    const tap = capture();
    mock.timers.enable({ apis: ["Date"], now: CLOCK });
    try {
      await write.run(api, attempt);
      mock.timers.tick(90_000);
      await write.run(api, attempt);
    } finally {
      mock.timers.reset();
      tap.restore();
    }

    assert.equal(tap.sent.length, 2);
    assert.equal(
      tap.sent[0].body,
      tap.sent[1].body,
      `${write.name}: lần gửi thứ hai đổi payload, máy chủ sẽ trả 422 chứ không phát lại`,
    );
    assert.equal(tap.sent[0].headers["Idempotency-Key"], "K-giu-nguyen");
    assert.equal(tap.sent[1].headers["Idempotency-Key"], "K-giu-nguyen");
  }
});

test("lần bấm khác là khoá khác, nếu không hai khoản chi khác nhau chỉ ghi được một", async () => {
  // The mirror of the test above, and it has to be here: an attempt that is
  // reused across two genuinely different presses would collapse a second real
  // expense into a replay of the first, which loses money silently rather than
  // loudly.
  const api = await import("../dist-test/api.js");
  const tap = capture();
  mock.timers.enable({ apis: ["Date"], now: CLOCK });
  try {
    await api.proposeSplit(NHOM, DRAFT, api.newAttempt());
    mock.timers.tick(90_000);
    await api.proposeSplit(NHOM, { ...DRAFT, totalVnd: 310_000 }, api.newAttempt());
  } finally {
    mock.timers.reset();
    tap.restore();
  }

  const keys = tap.sent.map((request) => request.headers["Idempotency-Key"]);
  assert.equal(keys.filter(Boolean).length, 2, "có lần gửi không mang khoá");
  assert.notEqual(keys[0], keys[1], "hai lần bấm khác nhau dùng chung một khoá");
});

test("một lần bấm giữ nguyên khoá qua nhiều lần thử, khác lần bấm thì khác khoá", async () => {
  const { attemptFor } = await import("../dist-test/api.js");
  const book = {};
  const first = attemptFor(book, "expense:e-1");
  assert.equal(attemptFor(book, "expense:e-1").key, first.key);
  assert.equal(attemptFor(book, "expense:e-1").at, first.at);
  assert.notEqual(attemptFor(book, "expense:e-2").key, first.key);
});

test("máy chủ từ chối vì khoá thì người dùng không phải đọc tiếng Anh", async () => {
  // Adding the header adds three refusals a person can now reach. Letting them
  // through would put "Idempotency-Key was already used for a different
  // request" on screen next to somebody's money.
  const api = await import("../dist-test/api.js");
  const cases = [
    { status: 409, code: "idempotency_request_in_flight" },
    { status: 422, code: "idempotency_key_reuse" },
    { status: 422, code: "invalid_idempotency_key" },
  ];
  for (const { status, code } of cases) {
    const tap = capture({
      status,
      code,
      detail: "An earlier request with this key never finished; use a new key",
    });
    try {
      await assert.rejects(
        () => api.proposeSplit(NHOM, DRAFT, { key: "K-1", at: CLOCK }),
        (problem) => {
          assert.equal(problem.code, code, "mã lỗi phải giữ nguyên cho báo lỗi");
          assert.doesNotMatch(
            problem.message,
            /Idempotency-Key|never finished|request/i,
            `${code} lọt tiếng Anh của máy chủ ra màn hình: ${problem.message}`,
          );
          return true;
        },
      );
    } finally {
      tap.restore();
    }
  }
});
