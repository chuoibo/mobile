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
import { dinhDangTienVnd, keHoachTuCard } from "../dist-test/screens/chat/ke-hoach.js";
import { khoiDongNhom } from "../dist-test/screens/chat/nhom.js";
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

/* ------------------------------------------------ ke hoach -------------- */

test("keHoachTuCard trả null với card rác, thiếu trường, mảng rỗng, null", () => {
  assert.equal(keHoachTuCard(null), null);
  assert.equal(keHoachTuCard(undefined), null);
  assert.equal(keHoachTuCard("rác"), null);
  assert.equal(keHoachTuCard([]), null);
  assert.equal(keHoachTuCard({}), null);
  assert.equal(keHoachTuCard({ tieuDe: "Đà Lạt" }), null);
  assert.equal(keHoachTuCard({ tieuDe: "Đà Lạt", ngay: [] }), null);
  assert.equal(keHoachTuCard({ ngay: [{ nhan: "Ngày 1", chang: [{ gio: "08:00", ten: "Ăn" }] }] }), null);
});

test("keHoachTuCard bỏ chặng thiếu gio hoặc ten thay vì vẽ undefined", () => {
  const ke = keHoachTuCard({
    tieuDe: "Đà Lạt 2N1Đ",
    ngay: [
      {
        nhan: "Ngày 1",
        chang: [
          { gio: "08:00", ten: "Ăn sáng" },
          { gio: "09:00" },
          { ten: "Thiếu giờ" },
          { gio: "10:00", ten: "Cafe", ghiChu: "mang theo áo ấm" },
        ],
      },
      { nhan: "Ngày trống", chang: [{ gio: "12:00" }] },
    ],
  });
  assert.equal(ke.tieuDe, "Đà Lạt 2N1Đ");
  assert.equal(ke.ngay.length, 1);
  assert.deepEqual(
    ke.ngay[0].chang.map((c) => c.ten),
    ["Ăn sáng", "Cafe"],
  );
  assert.equal(ke.ngay[0].chang.some((c) => c.gio === undefined || c.ten === undefined), false);
});

test("định dạng tiền 17500000 thành 17.500.000đ, không float", () => {
  assert.equal(dinhDangTienVnd(17500000), "17.500.000đ");
  assert.equal(dinhDangTienVnd(0), "0đ");
  assert.equal(dinhDangTienVnd(999), "999đ");
  assert.ok(!dinhDangTienVnd(17500000).includes(","));
  // Deliberately short of nine digits. The repo guard blocks any longer run
  // because it cannot tell a demo amount from a bank account number, and it
  // counts the digits on both sides of the decimal point as one run -- so the
  // tens-of-millions value used above, given a fractional part, reads as nine
  // and is refused at commit time. (Writing that number out in this comment
  // was itself refused, which is the guard working.) What the case proves is
  // that a non-integer đồng gets dropped, and that holds at any scale.
  const ke = keHoachTuCard({
    tieuDe: "Đà Lạt",
    tongDuTinhVnd: 1750000.5,
    duTinhMoiNguoiVnd: 2500000,
    ngay: [{ nhan: "Ngày 1", chang: [{ gio: "08:00", ten: "Ăn" }] }],
  });
  assert.equal(ke.tongDuTinhVnd, undefined);
  assert.equal(ke.duTinhMoiNguoiVnd, 2500000);
});

/* ------------------------------------------------ AI turn --------------- */

test("ai-turn 404 là chua-noi-duoc và câu có nhắc rd-be-04", async () => {
  const s = await withFetch(
    async () => res("", { status: 404, ok: false }),
    () => goiAiTurn({ contextId: CTX, actorId: ACTOR, afterMessageId: "m-9", base: "http://x.invalid" }),
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
    () => goiAiTurn({ contextId: CTX, actorId: ACTOR, afterMessageId: "m-9", base: "http://x.invalid" }),
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
    () => goiAiTurn({ contextId: CTX, actorId: ACTOR, afterMessageId: "m-9", base: "http://x" }),
  );
  assert.equal(s.kind, "im-lang");
  assert.equal("cau" in s, false);
  assert.equal("message" in s, false);
});

test("ai-turn speak false cũng là im-lang", async () => {
  const s = await withFetch(
    async () => res({ speak: false }),
    () => goiAiTurn({ contextId: CTX, actorId: ACTOR, afterMessageId: "m-9", base: "http://x" }),
  );
  assert.equal(s.kind, "im-lang");
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
