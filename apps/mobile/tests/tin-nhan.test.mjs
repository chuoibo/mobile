/* What the group-chat logic is allowed to get wrong, as assertions rather than as taps.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/tin-nhan.test.mjs
 *
 * Layout is not checkable here. What is checkable, and what this file exists
 * for, is the set of traps that look fine on a phone and are wrong: a uuid5
 * that does not match the seed, a cursor used in the wrong direction, a
 * duplicate bubble, a card that draws `undefined`, a canned AI itinerary, an
 * em-dash in Vietnamese copy, a hex colour that bypasses the palette.
 */
import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import test from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { DIRECTION_CONTRACT_NHOM_CHAT } from "../dist-test/ui/direction.js";
import { AI_WORK_ITEM, cauAiChuaNoiDuoc, goiAiTurn } from "../dist-test/screens/chat/ai.js";
import {
  dinhDangTienVnd,
  keHoachTuCard,
  khoangGia,
  theTuCard,
} from "../dist-test/screens/chat/ke-hoach.js";
import { khoiDongNhom, thanNhuSeed } from "../dist-test/screens/chat/nhom.js";
import {
  cursorCuNhat,
  cursorMoiNhat,
  messagesUrl,
  napTinCuHon,
  napTinMoiHon,
  napTinNhan,
  noiTinCuHon,
  noiTinMoiHon,
  tinHienThiLanDau,
} from "../dist-test/screens/chat/tin-nhan.js";
import { KHONG_GIAN_DEMO, KHONG_GIAN_DNS, khoaGhi, uuid5 } from "../dist-test/screens/chat/uuid5.js";

const CTX = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
const ACTOR = "46b55e67-932b-5415-a5ee-08fb2641a4ff";
const CHAT_SRC = join(dirname(fileURLToPath(import.meta.url)), "../src/screens/chat");

function msg(over = {}) {
  return {
    id: "m-1",
    context_id: CTX,
    author_id: ACTOR,
    kind: "text",
    body: "chào",
    image_url: null,
    card: null,
    created_at: "2026-08-29T04:00:00Z",
    cursor: "c-1",
    ...over,
  };
}

function res(body, { status = 200, ok } = {}) {
  const flag = ok ?? (status >= 200 && status < 300);
  const text = typeof body === "string" ? body : JSON.stringify(body);
  return {
    ok: flag,
    status,
    json: async () => (typeof body === "string" ? (body ? JSON.parse(body) : null) : body),
    text: async () => text,
  };
}

async function withFetch(impl, fn) {
  const previous = globalThis.fetch;
  globalThis.fetch = impl;
  try {
    return await fn();
  } finally {
    globalThis.fetch = previous;
  }
}

/* ------------------------------------------------ uuid5 ----------------- */

test("uuid5 khớp vector RFC 4122 và id person:minh của seed", () => {
  // Python's uuid.uuid5 is the independent oracle. These numbers are pinned
  // in the brief; recomputing them here would make the test agree with a
  // broken implementation.
  assert.equal(uuid5(KHONG_GIAN_DNS, "python.org"), "886313e1-3b8a-5372-9b90-0c9aee199e5d");
  assert.equal(uuid5(KHONG_GIAN_DEMO, "person:minh"), "46b55e67-932b-5415-a5ee-08fb2641a4ff");
  assert.equal(uuid5(KHONG_GIAN_DEMO, "person:trang"), "49871dab-3bf9-5140-acf3-6c9736b31e8f");
  assert.equal(uuid5(KHONG_GIAN_DEMO, "person:hai"), "be2389f9-62cb-5b28-8e5f-874768e9fb75");
  assert.equal(uuid5(KHONG_GIAN_DEMO, "person:ngoc"), "e3a44e25-4547-508a-8f4d-9b2495c3325f");
  assert.equal(uuid5(KHONG_GIAN_DEMO, "person:duc"), "4421b3f8-26a6-5827-a7e7-548c5a4a10f9");
  assert.equal(uuid5(KHONG_GIAN_DEMO, "person:linh"), "cdadf49b-b6a8-5631-8b9d-aee6a7d532de");
  assert.equal(uuid5(KHONG_GIAN_DEMO, "person:quan"), "93c153f7-042a-556d-b227-7b1e54f2d50b");
  assert.equal(uuid5(KHONG_GIAN_DEMO, "write:context"), "a871a4f2-6a3c-5202-9bba-a3120e1f4c76");
  assert.equal(khoaGhi("context"), "a871a4f2-6a3c-5202-9bba-a3120e1f4c76");
});

test("tên có dấu tiếng Việt băm UTF-8, không phải latin-1", () => {
  assert.equal(uuid5(KHONG_GIAN_DEMO, "person:Đức Ngọc"), "5ade38f8-8e92-5c36-b444-f4c39c203d55");
});

/* ------------------------------------------------ thứ tự cursor --------- */

test("nạp lần đầu trả giảm dần thì màn hiển thị tăng dần", () => {
  const server = [
    msg({ id: "moi", cursor: "c-moi", created_at: "2026-08-29T04:02:00Z" }),
    msg({ id: "giua", cursor: "c-giua", created_at: "2026-08-29T04:01:00Z" }),
    msg({ id: "cu", cursor: "c-cu", created_at: "2026-08-29T04:00:00Z" }),
  ];
  assert.deepEqual(
    tinHienThiLanDau(server).map((m) => m.id),
    ["cu", "giua", "moi"],
  );
});

test("before lấy cursor tin cũ nhất, after lấy cursor tin mới nhất", async () => {
  const trenMan = tinHienThiLanDau([
    msg({ id: "moi", cursor: "c-moi" }),
    msg({ id: "giua", cursor: "c-giua" }),
    msg({ id: "cu", cursor: "c-cu" }),
  ]);
  assert.equal(cursorCuNhat(trenMan), "c-cu");
  assert.equal(cursorMoiNhat(trenMan), "c-moi");

  const urls = [];
  await withFetch(async (url) => {
    urls.push(String(url));
    return res({ context_id: CTX, messages: [], next_cursor: null, has_more: false });
  }, async () => {
    await napTinCuHon({ contextId: CTX, actorId: ACTOR, dangGiu: trenMan, base: "http://x" });
    await napTinMoiHon({ contextId: CTX, actorId: ACTOR, dangGiu: trenMan, base: "http://x" });
  });
  assert.match(urls[0], /[?&]before=c-cu/);
  assert.doesNotMatch(urls[0], /[?&]after=/);
  assert.match(urls[1], /[?&]after=c-moi/);
  assert.doesNotMatch(urls[1], /[?&]before=/);
});

test("nối trang không nhân đôi tin đã có, khử trùng theo id", () => {
  const dangGiu = [
    msg({ id: "a", cursor: "ca" }),
    msg({ id: "b", cursor: "cb" }),
    msg({ id: "c", cursor: "cc" }),
  ];
  // Older page, newest-first, overlaps `a` the way a retry would.
  const cuHon = noiTinCuHon(dangGiu, [
    msg({ id: "a", cursor: "ca" }),
    msg({ id: "z", cursor: "cz" }),
  ]);
  assert.deepEqual(
    cuHon.map((m) => m.id),
    ["z", "a", "b", "c"],
  );
  const moiHon = noiTinMoiHon(dangGiu, [
    msg({ id: "c", cursor: "cc" }),
    msg({ id: "d", cursor: "cd" }),
  ]);
  assert.deepEqual(
    moiHon.map((m) => m.id),
    ["a", "b", "c", "d"],
  );
});

test("nạp lần đầu qua fetch đảo mảng server trước khi trả về", async () => {
  const s = await withFetch(
    async () =>
      res({
        context_id: CTX,
        messages: [msg({ id: "moi", cursor: "c-moi" }), msg({ id: "cu", cursor: "c-cu" })],
        next_cursor: "c-cu",
        has_more: true,
      }),
    () => napTinNhan({ contextId: CTX, actorId: ACTOR, base: "http://x" }),
  );
  assert.equal(s.kind, "co-tin");
  assert.deepEqual(
    s.messages.map((m) => m.id),
    ["cu", "moi"],
  );
  assert.equal(s.hasMore, true);
});

test("URL lần đầu không mang before hay after", () => {
  const url = messagesUrl("http://api/", CTX, { limit: 50 });
  assert.match(url, /^http:\/\/api\/contexts\/.*\/messages\?/);
  assert.match(url, /limit=50/);
  assert.doesNotMatch(url, /before=/);
  assert.doesNotMatch(url, /after=/);
});

/* ------------------------------------------------ ke hoach --------------
 *
 * Every case below feeds the shape rd-be-04 actually emits, `{kind, payload}`,
 * taken from docs/claude/2026-08-29/rd-be-04-hop-dong.md and from
 * `ground_card` in app/domain/companion.py. The first draft of these tests fed
 * a shape guessed from the mockup (`{tieuDe, ngay:[{nhan, chang}]}`) and
 * passed against a parser that read the same guess, which proved only that
 * two files agreed with each other.
 */

/** A catalogue place as `ground_card` copies it: server fields, snake_case. */
function place(over = {}) {
  return {
    id: "pl-1",
    name: "Quán Gió",
    address: "12 Trần Phú",
    price_min_vnd: 120000,
    price_max_vnd: 250000,
    rating: 4.5,
    distance_km: 1.2,
    open_hours: "07:00 - 22:00",
    category: "an-uong",
    ...over,
  };
}

test("theTuCard trả null với card rác, thiếu payload, kind lạ", () => {
  assert.equal(theTuCard(null), null);
  assert.equal(theTuCard(undefined), null);
  assert.equal(theTuCard("rác"), null);
  assert.equal(theTuCard([]), null);
  assert.equal(theTuCard({}), null);
  assert.equal(theTuCard({ kind: "text" }), null);
  assert.equal(theTuCard({ kind: "text", payload: "chuỗi" }), null);
  assert.equal(theTuCard({ kind: "text", payload: { text: "   " } }), null);
  // A kind this client has never heard of means the server is newer than the
  // app. There is no safe way to draw it, so it is refused rather than guessed.
  assert.equal(theTuCard({ kind: "poll", payload: { question: "đi đâu" } }), null);
  assert.equal(theTuCard({ kind: "places", payload: { places: [] } }), null);
  assert.equal(theTuCard({ kind: "itinerary", payload: { title: "Đà Lạt", stops: [] } }), null);
  assert.equal(theTuCard({ kind: "itinerary", payload: { stops: [{ time_text: "08:00", place: place() }] } }), null);
});

test("theTuCard đọc thẻ text và thẻ places", () => {
  assert.deepEqual(theTuCard({ kind: "text", payload: { text: "Nhóm mình đi Đà Lạt nhé" } }), {
    kind: "text",
    text: "Nhóm mình đi Đà Lạt nhé",
  });

  const t = theTuCard({
    kind: "places",
    payload: { intro: "Ba chỗ gần chỗ mình ở", places: [place(), place({ id: "pl-2", name: "Bếp Nhà" })] },
  });
  assert.equal(t.kind, "places");
  assert.equal(t.intro, "Ba chỗ gần chỗ mình ở");
  assert.deepEqual(t.diaDiem.map((d) => d.ten), ["Quán Gió", "Bếp Nhà"]);
  assert.equal(t.diaDiem[0].gioMo, "07:00 - 22:00");
  assert.equal(t.diaDiem[0].danhGia, 4.5);
});

test("keHoachTuCard bỏ chặng thiếu time_text hoặc place thay vì vẽ undefined", () => {
  const ke = keHoachTuCard({
    kind: "itinerary",
    payload: {
      title: "Đà Lạt 2N1Đ",
      stops: [
        { time_text: "08:00", note: "ăn sáng", place: place({ id: "a", name: "Ăn sáng" }) },
        { time_text: "09:00" },
        { place: place({ id: "b", name: "Thiếu giờ" }) },
        { time_text: "10:00", place: place({ id: "c", name: "Cafe" }) },
        { time_text: "11:00", place: { id: "d" } },
      ],
    },
  });
  assert.equal(ke.tieuDe, "Đà Lạt 2N1Đ");
  assert.deepEqual(ke.chang.map((c) => c.diaDiem.ten), ["Ăn sáng", "Cafe"]);
  assert.equal(ke.chang.some((c) => c.gio === undefined || c.diaDiem === undefined), false);
});

test("keHoachTuCard chỉ nhận kind itinerary, không nhận text hay places", () => {
  assert.equal(keHoachTuCard({ kind: "text", payload: { text: "chào" } }), null);
  assert.equal(keHoachTuCard({ kind: "places", payload: { places: [place()] } }), null);
});

test("định dạng tiền 17500000 thành 17.500.000đ, không float", () => {
  assert.equal(dinhDangTienVnd(17500000), "17.500.000đ");
  assert.equal(dinhDangTienVnd(0), "0đ");
  assert.equal(dinhDangTienVnd(999), "999đ");
  assert.ok(!dinhDangTienVnd(17500000).includes(","));
});

test("giá lẻ đồng bị bỏ, không làm tròn; khoảng giá không tự lấy trung bình", () => {
  // A fractional đồng is a server defect, not something to round into a figure
  // that looks fine. The field is dropped and the line disappears.
  const t = theTuCard({
    kind: "places",
    payload: { places: [place({ price_min_vnd: 120000.5, price_max_vnd: 250000 })] },
  });
  assert.equal(t.diaDiem[0].giaMinVnd, undefined);
  assert.equal(t.diaDiem[0].giaMaxVnd, 250000);
  assert.equal(khoangGia(t.diaDiem[0]), "tới 250.000đ");

  assert.equal(khoangGia({ id: "x", ten: "X", giaMinVnd: 120000, giaMaxVnd: 250000 }), "120.000đ - 250.000đ");
  assert.equal(khoangGia({ id: "x", ten: "X", giaMinVnd: 90000, giaMaxVnd: 90000 }), "90.000đ");
  assert.equal(khoangGia({ id: "x", ten: "X" }), null);
  // The midpoint of a range the server gave as a range is a number the server
  // never said. Nothing here may produce one.
  assert.ok(!khoangGia({ id: "x", ten: "X", giaMinVnd: 100000, giaMaxVnd: 200000 }).includes("150.000"));
});

/* ------------------------------------------------ AI turn ---------------
 *
 * The wire here is CompanionTurnResponse from rd-be-04:
 *   {context_id, spoke, reason, message: MessageResponse | null}
 * with 200 for every outcome, silence included, so the client never has to
 * read a status code to learn whether the companion spoke.
 */

function turn(over = {}) {
  return { context_id: CTX, spoke: false, reason: "cooldown", message: null, ...over };
}

test("ai-turn không gửi thân request: máy chủ tự chọn cửa sổ 40 tin", async () => {
  let seen;
  await withFetch(
    async (_url, init) => {
      seen = init;
      return res(turn());
    },
    () => goiAiTurn({ contextId: CTX, actorId: ACTOR, base: "http://x" }),
  );
  assert.equal(seen.method, "POST");
  assert.equal(seen.body, undefined);
});

test("ai-turn 404 là chua-noi-duoc và câu có nhắc rd-be-04", async () => {
  const s = await withFetch(
    async () => res("", { status: 404, ok: false }),
    () => goiAiTurn({ contextId: CTX, actorId: ACTOR, base: "http://x.invalid" }),
  );
  assert.equal(s.kind, "chua-noi-duoc");
  assert.match(s.cau, /rd-be-04/);
  assert.equal(AI_WORK_ITEM, "rd-be-04");
  assert.match(s.cau, /http:\/\/x\.invalid\/contexts\/.*\/ai-turn/);
  assert.ok(!s.cau.includes("—"), s.cau);
  assert.ok(!/lỗi/i.test(s.cau), s.cau);
});

test("ai-turn 405 cũng là chua-noi-duoc, cùng giọng", async () => {
  const s = await withFetch(
    async () => res("", { status: 405, ok: false }),
    () => goiAiTurn({ contextId: CTX, actorId: ACTOR, base: "http://x.invalid" }),
  );
  assert.equal(s.kind, "chua-noi-duoc");
  assert.equal(s.cau, cauAiChuaNoiDuoc(s.url));
});

test("ai-turn 204 là im-lang, màn không hiện gì", async () => {
  const s = await withFetch(
    async () => ({
      ok: true,
      status: 204,
      json: async () => {
        throw new Error("204 không có thân");
      },
      text: async () => "",
    }),
    () => goiAiTurn({ contextId: CTX, actorId: ACTOR, base: "http://x" }),
  );
  assert.equal(s.kind, "im-lang");
  assert.equal("cau" in s, false);
  assert.equal("message" in s, false);
});

test("bốn lý do của plan_turn đều là im-lang, không hiện gì", async () => {
  for (const reason of ["no_conversation", "already_spoke_last", "rate_limited", "cooldown"]) {
    const s = await withFetch(
      async () => res(turn({ reason })),
      () => goiAiTurn({ contextId: CTX, actorId: ACTOR, base: "http://x" }),
    );
    assert.equal(s.kind, "im-lang", reason);
    assert.equal(s.reason, reason);
    assert.equal("cau" in s, false, reason);
  }
});

test("unavailable KHÔNG được đọc thành im lặng: thiếu khoá phải nhìn thấy được", async () => {
  // The tempting bug. `spoke:false, reason:"unavailable"` means the model call
  // failed, most often because the deployment has no GEMINI_API_KEY. Folding
  // it into `im-lang` makes a permanently broken AI look exactly like an AI
  // that read the thread and had nothing to add, and nobody ever finds out.
  const s = await withFetch(
    async () => res(turn({ reason: "unavailable" })),
    () => goiAiTurn({ contextId: CTX, actorId: ACTOR, base: "http://x" }),
  );
  assert.equal(s.kind, "khong-tra-loi-duoc");
  assert.equal(s.reason, "unavailable");
  assert.ok(s.cau.length > 0);
  assert.ok(!s.cau.includes("—"), s.cau);
  // The server never sends the exception text because it could carry the API
  // key or the chat content, so nothing key-shaped can reach the sentence.
  assert.ok(!/AIza|key|api[_-]?key/i.test(s.cau), s.cau);
});

test("ungrounded nói rõ AI nhắc địa điểm ngoài danh mục nên cả thẻ bị bỏ", async () => {
  const s = await withFetch(
    async () => res(turn({ reason: "ungrounded" })),
    () => goiAiTurn({ contextId: CTX, actorId: ACTOR, base: "http://x" }),
  );
  assert.equal(s.kind, "khong-tra-loi-duoc");
  assert.match(s.cau, /địa điểm/);
  assert.ok(!s.cau.includes("—"), s.cau);
});

test("lý do lạ được coi là không trả lời được, không phải im lặng", async () => {
  const s = await withFetch(
    async () => res(turn({ reason: "chua_tung_thay" })),
    () => goiAiTurn({ contextId: CTX, actorId: ACTOR, base: "http://x" }),
  );
  assert.equal(s.kind, "khong-tra-loi-duoc");
});

test("spoke true dựng thẻ từ message, không phải từ thân ngoài", async () => {
  const card = { kind: "itinerary", payload: { title: "Đà Lạt 2N1Đ", stops: [{ time_text: "08:00", place: place() }] } };
  const s = await withFetch(
    async () =>
      res(turn({ spoke: true, reason: "ok", message: msg({ id: "m-ai", kind: "ai_card", author_id: null, body: null, card }) })),
    () => goiAiTurn({ contextId: CTX, actorId: ACTOR, base: "http://x" }),
  );
  assert.equal(s.kind, "da-noi");
  assert.equal(s.message.kind, "ai_card");
  // author_id null is deliberate on the server: the AI is not a Person.
  assert.equal(s.message.author_id, null);
  const ke = keHoachTuCard(s.message.card);
  assert.equal(ke.tieuDe, "Đà Lạt 2N1Đ");
  assert.equal(ke.chang.length, 1);
});

test("spoke true nhưng message rác là hong, không phải da-noi", async () => {
  const s = await withFetch(
    async () => res(turn({ spoke: true, reason: "ok", message: null })),
    () => goiAiTurn({ contextId: CTX, actorId: ACTOR, base: "http://x" }),
  );
  assert.equal(s.kind, "hong");
});

/* ------------------------------------------------ nhóm 409 -------------- */

test("409 khi accept là thành công, không phải lỗi", async () => {
  const calls = [];
  const s = await withFetch(async (url, init) => {
    const u = String(url);
    const method = init?.method ?? "GET";
    calls.push({ method, url: u, key: init?.headers?.["Idempotency-Key"] });
    if (method === "PUT" && u.includes("/people/")) return res({ id: "p", display_name: "X" }, { status: 201 });
    if (method === "POST" && u.endsWith("/contexts")) {
      return res({ id: CTX, display_name: "Team Đà Lạt", created_by_id: ACTOR, created_at: "2026-08-01T00:00:00Z" }, { status: 201 });
    }
    if (method === "POST" && u.endsWith("/members")) {
      return res({ id: "mem-1", context_id: CTX, person_id: "p", state: "invited", role: "member" }, { status: 201 });
    }
    if (method === "POST" && u.includes("/accept")) return res({ code: "membership_not_invited" }, { status: 409, ok: false });
    if (method === "GET" && u.endsWith("/members")) {
      return res({
        context_id: CTX,
        members: [
          {
            id: "mem-0",
            context_id: CTX,
            person_id: ACTOR,
            state: "active",
            role: "admin",
          },
        ],
      });
    }
    return res("unexpected", { status: 500, ok: false });
  }, () => khoiDongNhom("trang", { base: "http://x" }));
  assert.equal(s.kind, "xong", s.kind === "hong" ? `${s.buoc} ${s.url} ${s.detail}` : "");
  assert.equal(s.contextId, CTX);
  assert.equal(s.members.length, 1);
  assert.ok(calls.some((c) => c.method === "POST" && c.url.endsWith("/accept")));
});

test("bước hỏng nói rõ bước nào và địa chỉ đã thử", async () => {
  const s = await withFetch(async (url, init) => {
    if ((init?.method ?? "GET") === "PUT") return res({ id: "p", display_name: "Minh" }, { status: 201 });
    return res("boom", { status: 500, ok: false });
  }, () => khoiDongNhom("minh", { base: "http://x.invalid" }));
  assert.equal(s.kind, "hong");
  assert.equal(s.buoc, "tao-nhom");
  assert.match(s.url, /http:\/\/x\.invalid\/contexts$/);
  assert.equal(s.status, 500);
});

test("POST /contexts gửi đúng khoá write:context", async () => {
  const keys = [];
  await withFetch(async (url, init) => {
    if ((init?.method ?? "GET") === "POST" && String(url).endsWith("/contexts")) {
      keys.push(init?.headers?.["Idempotency-Key"]);
      return res("nope", { status: 500, ok: false });
    }
    return res({ id: "p", display_name: "Minh" }, { status: 201 });
  }, () => khoiDongNhom("minh", { base: "http://x" }));
  assert.deepEqual(keys, ["a871a4f2-6a3c-5202-9bba-a3120e1f4c76"]);
});

/* The server fingerprints an idempotent write over RAW BODY BYTES
 * (`app/api/idempotency.py`, `request_fingerprint`), so replaying the seed's
 * `POST /contexts` requires reproducing the seed's bytes, not its meaning.
 * The expectations below are not hand-typed: they are what
 * `python3 -c "import json; json.dumps(...)"` actually printed. If Python
 * ever changes its default separators or `ensure_ascii`, this goes red here
 * rather than as a 422 on a demo machine. */
test("thanNhuSeed dựng đúng byte mà json.dumps của Python in ra", () => {
  assert.equal(
    thanNhuSeed({ display_name: "Team Đà Lạt" }),
    '{"display_name": "Team \\u0110\\u00e0 L\\u1ea1t"}',
  );
  // A space after the colon and after the comma; JSON.stringify writes neither.
  assert.equal(thanNhuSeed({ a: "x", b: "ý" }), '{"a": "x", "b": "\\u00fd"}');
  // Quotes and backslashes keep the escaping both encoders already agree on.
  assert.equal(
    thanNhuSeed({ display_name: 'Ngọc "quoted" \\ back' }),
    '{"display_name": "Ng\\u1ecdc \\"quoted\\" \\\\ back"}',
  );
  // Pure ASCII is the case that hid this defect: both encoders agree except
  // for the separators, so a name like "Minh" replays and "Ngọc" does not.
  assert.equal(thanNhuSeed({ display_name: "Minh" }), '{"display_name": "Minh"}');
});

test("POST /contexts gửi thân theo byte của seed, không phải JSON.stringify", async () => {
  const bodies = [];
  await withFetch(async (url, init) => {
    if ((init?.method ?? "GET") === "POST" && String(url).endsWith("/contexts")) {
      bodies.push(init?.body);
      return res("nope", { status: 500, ok: false });
    }
    return res({ id: "p", display_name: "Minh" }, { status: 201 });
  }, () => khoiDongNhom("minh", { base: "http://x" }));
  assert.deepEqual(bodies, ['{"display_name": "Team \\u0110\\u00e0 L\\u1ea1t"}']);
  assert.notEqual(bodies[0], JSON.stringify({ display_name: "Team Đà Lạt" }));
});

/* ------------------------------------------------ copy + palette -------- */

const VIET = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ]/;

function trichChuoi(src) {
  const out = [];
  const re = /(["'`])((?:\\.|(?!\1).)*)\1/g;
  let m;
  while ((m = re.exec(src))) out.push(m[2]);
  return out;
}

test("không file nào trong screens/chat chứa chuỗi tiếng Việt có em-dash", async () => {
  const files = (await readdir(CHAT_SRC)).filter((n) => /\.(ts|tsx)$/.test(n));
  assert.ok(files.length >= 5, `thiếu file logic: ${files.join(", ")}`);
  const bad = [];
  for (const name of files) {
    const src = await readFile(join(CHAT_SRC, name), "utf8");
    for (const s of trichChuoi(src)) {
      if (s.includes("—") && VIET.test(s)) bad.push(`${name}: ${s}`);
    }
  }
  assert.deepEqual(bad, []);
});

test("không file nào trong screens/chat hardcode mã màu hex", async () => {
  const files = (await readdir(CHAT_SRC)).filter((n) => /\.(ts|tsx)$/.test(n));
  const bad = [];
  for (const name of files) {
    const src = await readFile(join(CHAT_SRC, name), "utf8");
    const hits = src.match(/#[0-9A-Fa-f]{3,8}\b/g) ?? [];
    if (hits.length) bad.push(`${name}: ${hits.join(", ")}`);
  }
  assert.deepEqual(bad, []);
});

/* ------------------------------------------------ hướng thiết kế -------- */

test("hợp đồng nhóm chat còn đủ sáu khối THESIS/OWN-WORLD/STORY/FIRST VIEWPORT/FORM/FINISH", () => {
  for (const block of ["THESIS:", "OWN-WORLD:", "STORY:", "FIRST VIEWPORT:", "FORM:", "FINISH:"]) {
    assert.ok(DIRECTION_CONTRACT_NHOM_CHAT.includes(block), `thiếu khối ${block}`);
  }
});
