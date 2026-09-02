/* Who a request says it is, and what happens when the server stops agreeing.
 *
 * `docs/architecture/01-duong-toi-production.md` B1 measures the hole this is
 * the client half of: auth today is `X-Actor-ID`, a header the client writes
 * itself, so anybody who can set a header can be anybody. ADR-0014 replaces it
 * with a server-issued bearer.
 *
 * The server half is Codex's lane and the ADR is still ĐỀ XUẤT, so the route
 * that mints a token does not exist. What CAN be built and gated today is
 * everything that does not need a new path:
 *
 *   - with a bearer, the client-asserted identity headers must not leave the
 *     device at all -- omitted, not merely ignored server-side;
 *   - a 401 while holding one must drop the token rather than retry a
 *     credential that cannot work;
 *   - and "the login route does not exist" must be a fact with a test on it,
 *     not a comment.
 *
 * The last test is the one that will go red when the route lands. That is the
 * intended way to find out.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { datPhienBearer, datXuLyMatPhien, dangCoPhien, docSoDu } from "../dist-test/api.js";
import { ChuaCoRouteError, doiLoiMoiLayPhien, traLaiPhien } from "../dist-test/rudi/phien.js";

const CONTEXT = "1aa00000-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const NGUOI = "46b55e67-932b-5415-a5ee-08fb2641a4ff";

/** Capture the headers a call really put on the wire. */
function batHeader(status = 200, payload = { balances: [] }) {
  const that = globalThis.fetch;
  const daGui = [];
  globalThis.fetch = async (url, init) => {
    daGui.push({ url: String(url), headers: init.headers });
    return new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  };
  return {
    daGui,
    thoi: () => {
      globalThis.fetch = that;
    },
  };
}

test("không có phiên: gửi X-Actor-ID như hôm nay", async () => {
  datPhienBearer(null);
  const { daGui, thoi } = batHeader();
  try {
    await docSoDu(CONTEXT, NGUOI).catch(() => {});
  } finally {
    thoi();
  }
  assert.equal(daGui.length, 1);
  assert.equal(daGui[0].headers["X-Actor-ID"], NGUOI);
  assert.equal("Authorization" in daGui[0].headers, false);
});

test("có phiên: X-Actor-ID KHÔNG rời khỏi máy", async () => {
  // The whole point of prod mode is that the server stops taking the client's
  // word for who this is. Sending the header anyway would hand it a second,
  // self-asserted answer to the same question.
  datPhienBearer("bearer-cua-may-chu");
  const { daGui, thoi } = batHeader();
  try {
    await docSoDu(CONTEXT, NGUOI).catch(() => {});
  } finally {
    thoi();
    datPhienBearer(null);
  }
  assert.equal(daGui.length, 1);
  assert.equal(daGui[0].headers.Authorization, "Bearer bearer-cua-may-chu");
  assert.equal("X-Actor-ID" in daGui[0].headers, false, "person id vẫn rời máy");
  assert.equal("X-Actor-Roles" in daGui[0].headers, false, "roles vẫn do client tự khai");
  assert.equal("X-Actor-Contexts" in daGui[0].headers, false, "contexts vẫn do client tự khai");
});

test("401 khi đang giữ phiên: bỏ token và báo ra ngoài, không phải sự cố máy chủ", async () => {
  datPhienBearer("token-het-han");
  let daBao = 0;
  datXuLyMatPhien(() => {
    daBao += 1;
  });
  const { thoi } = batHeader(401, { code: "unauthorized", detail: "nope" });
  try {
    await docSoDu(CONTEXT, NGUOI).catch(() => {});
  } finally {
    thoi();
    datXuLyMatPhien(null);
  }
  assert.equal(dangCoPhien(), false, "token hết hạn vẫn còn nằm đó");
  assert.equal(daBao, 1, "màn không được báo là phiên đã mất");
});

test("401 khi KHÔNG có phiên không gọi nhầm đường mất phiên", async () => {
  // A 401 without a bearer is the app's own missing header, not an expired
  // session. Routing it to "you were logged out" would be a lie in the other
  // direction, and it is the state every request is in today.
  datPhienBearer(null);
  let daBao = 0;
  datXuLyMatPhien(() => {
    daBao += 1;
  });
  const { thoi } = batHeader(401, { code: "unauthorized" });
  try {
    await docSoDu(CONTEXT, NGUOI).catch(() => {});
  } finally {
    thoi();
    datXuLyMatPhien(null);
  }
  assert.equal(daBao, 0);
});

test("đường cấp phiên CHƯA CÓ, và đó là một sự thật có cổng gác", async () => {
  // When Codex ships the route, this test goes red. That is how it is meant to
  // be noticed: a comment saying "chưa làm" cannot do that.
  await assert.rejects(() => doiLoiMoiLayPhien("bi-mat-loi-moi"), ChuaCoRouteError);
  await assert.rejects(() => traLaiPhien("token"), ChuaCoRouteError);
  await assert.rejects(
    () => doiLoiMoiLayPhien("x"),
    (err) => err.message.includes("ADR-0014"),
    "câu lỗi phải chỉ thẳng vào quyết định đang chặn",
  );
});
