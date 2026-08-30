/* F39 + F42: bài đăng và bốn mức người đọc, phía app.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/tuong.test.mjs
 *
 * Bốn route đã lên máy chủ từ PR #308 mà không màn nào gọi. File này ghim
 * đúng những chỗ app từng gửi sai trên các lát cắt khác: author_id trong
 * body, context_id đi kèm audience không phải group, mã lỗi tiếng Anh ra
 * màn hình, và bốn mức vẽ như một cái thang.
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { dangBai, docBai, docBangTin, docTuongNguoi } from "../dist-test/api.js";
import { cauMayChuLoi } from "../dist-test/ui/loi-may-chu.js";
import {
  AUDIENCES,
  MAC_DINH_NGUOI_DOC,
  MUC_NGUOI_DOC,
  coTheDang,
  loiTuong,
  thanDangBai,
} from "../dist-test/screens/ca-nhan/bai-dang.js";
import { Tuong } from "../dist-test/screens/ca-nhan/Tuong.js";

const ACTOR = "46b55e67-932b-5415-a5ee-08fb2641a4ff";
const NHOM = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
const BAI = "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff";
const LAN = { key: "a1b2c3d4-e5f6-4a1b-8c2d-e3f4a5b6c7d8", at: 0 };

const WIRE = {
  id: BAI,
  author_id: ACTOR,
  audience: "only_me",
  context_id: null,
  body: "Một câu trên tường",
  image_url: null,
  created_at: "2026-08-30T03:00:00Z",
};

function res(body, { status = 200 } = {}) {
  const ok = status >= 200 && status < 300;
  return {
    ok,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
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

async function batLoi(work) {
  try {
    await work();
  } catch (problem) {
    return problem;
  }
  throw new Error("gọi xong mà không ném lỗi, test này không đo được gì");
}

function words(el) {
  return renderToStaticMarkup(el)
    .replace(/<[^>]*>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();
}

function markup(props) {
  return renderToStaticMarkup(
    React.createElement(Tuong, {
      nguoi: { personId: ACTOR },
      ...props,
    }),
  );
}

/* ------------------------------------------------------------- the body --- */

test("POST /posts gửi đúng body, không có author_id", async () => {
  const goi = [];
  await withFetch(async (url, init) => {
    goi.push({
      url: String(url),
      method: init?.method,
      headers: init?.headers,
      body: init?.body ? JSON.parse(init.body) : null,
    });
    return res(WIRE, { status: 201 });
  }, () =>
    dangBai({ body: "Chào tường", audience: "only_me" }, ACTOR, LAN));

  assert.equal(goi.length, 1);
  assert.equal(goi[0].method, "POST");
  assert.equal(new URL(goi[0].url).pathname, "/posts");
  assert.equal(goi[0].headers["X-Actor-ID"], ACTOR);
  assert.equal(goi[0].headers["Idempotency-Key"], LAN.key);
  assert.deepEqual(goi[0].body, { body: "Chào tường", audience: "only_me" });
  assert.equal("author_id" in goi[0].body, false);
});

test("audience group gửi kèm context_id; ba audience kia không gửi", async () => {
  for (const audience of ["only_me", "friends", "public"]) {
    const than = thanDangBai({ body: "x", audience, contextId: NHOM });
    assert.equal("context_id" in than, false, `${audience} vẫn mang context_id`);
    assert.equal("author_id" in than, false, `${audience} mang author_id`);
  }
  const group = thanDangBai({ body: "x", audience: "group", contextId: NHOM });
  assert.equal(group.context_id, NHOM);
  assert.equal("author_id" in group, false);

  const goi = [];
  await withFetch(async (_url, init) => {
    goi.push(JSON.parse(init.body));
    return res({ ...WIRE, audience: "group", context_id: NHOM }, { status: 201 });
  }, () => dangBai({ body: "Cho nhóm", audience: "group", contextId: NHOM }, ACTOR, LAN));
  assert.equal(goi[0].context_id, NHOM);
  assert.equal("author_id" in goi[0], false);
});

test("ba audience không-group không gửi context_id dù caller đưa id", async () => {
  const goi = [];
  await withFetch(async (_url, init) => {
    goi.push(JSON.parse(init.body));
    return res(WIRE, { status: 201 });
  }, async () => {
    await dangBai({ body: "a", audience: "friends", contextId: NHOM }, ACTOR, LAN);
    await dangBai({ body: "b", audience: "public", contextId: NHOM }, ACTOR, LAN);
    await dangBai({ body: "c", audience: "only_me", contextId: NHOM }, ACTOR, LAN);
  });
  for (const body of goi) {
    assert.equal("context_id" in body, false, JSON.stringify(body));
  }
});

test("bốn hàm gọi đúng bốn route, actor đi trên header", async () => {
  const goi = [];
  await withFetch(async (url, init) => {
    goi.push({
      path: new URL(String(url)).pathname,
      method: init?.method ?? "GET",
      actor: init?.headers?.["X-Actor-ID"],
    });
    const path = new URL(String(url)).pathname;
    if (path === "/posts" && (init?.method ?? "GET") === "GET") {
      return res({ posts: [WIRE] });
    }
    if (path.startsWith("/people/") && path.endsWith("/posts")) {
      return res({ person_id: ACTOR, posts: [WIRE] });
    }
    return res(WIRE);
  }, async () => {
    await docBangTin(ACTOR);
    await docBai(BAI, ACTOR);
    await docTuongNguoi(ACTOR, ACTOR);
  });
  assert.deepEqual(
    goi.map((g) => `${g.method} ${g.path}`),
    ["GET /posts", `GET /posts/${BAI}`, `GET /people/${ACTOR}/posts`],
  );
  assert.ok(goi.every((g) => g.actor === ACTOR));
});

/* ---------------------------------------------------------- the form --- */

test("mặc định là only_me, không phải public", () => {
  assert.equal(MAC_DINH_NGUOI_DOC, "only_me");
  assert.deepEqual([...AUDIENCES], ["only_me", "friends", "group", "public"]);
});

test("nút Đăng khoá khi chọn Một nhóm mà chưa chọn nhóm", () => {
  assert.equal(
    coTheDang({ body: "Có chữ", audience: "group", contextId: null }),
    false,
  );
  assert.equal(
    coTheDang({ body: "Có chữ", audience: "group", contextId: "" }),
    false,
  );
  assert.equal(
    coTheDang({ body: "Có chữ", audience: "group", contextId: NHOM }),
    true,
  );
  assert.equal(
    coTheDang({ body: "Có chữ", audience: "only_me", contextId: null }),
    true,
  );
});

test("nút Đăng trên markup bị disabled khi group chưa có nhóm", () => {
  const html = markup({
    khoiDau: {
      moSoan: true,
      body: "Một câu đã viết",
      audience: "group",
      contextId: null,
      trang: { pha: "xong", bai: [] },
    },
    nhom: [{ id: NHOM, name: "Team Đà Lạt" }],
  });
  assert.match(html, /Đăng/);
  assert.match(html, /aria-disabled="true"/);
});

test("nút Đăng không khoá khi only_me đã có chữ", () => {
  const html = markup({
    khoiDau: {
      moSoan: true,
      body: "Một câu đã viết",
      audience: "only_me",
      contextId: null,
      trang: { pha: "xong", bai: [] },
    },
  });
  assert.match(html, /Đăng/);
  assert.doesNotMatch(html, /aria-disabled="true"/);
});

test("mặc định trên màn là only_me: chưa hiện chỗ chọn nhóm", () => {
  const html = markup({
    khoiDau: {
      moSoan: true,
      audience: MAC_DINH_NGUOI_DOC,
      trang: { pha: "xong", bai: [] },
    },
    nhom: [{ id: NHOM, name: "Team Đà Lạt" }],
  });
  assert.match(html, /Chỉ mình tôi/);
  assert.doesNotMatch(html, /Team Đà Lạt/);
  assert.doesNotMatch(html, /role="slider"/);
  assert.doesNotMatch(html, /type="range"/);
});

test("bốn radio xếp dọc, không dựa aria-checked", () => {
  const html = markup({
    khoiDau: {
      moSoan: true,
      audience: "only_me",
      trang: { pha: "xong", bai: [] },
    },
  });
  const radios = [...html.matchAll(/role="radio"/g)];
  assert.equal(radios.length, 4, `phải đúng 4 radio, đang có ${radios.length}`);
  assert.match(html, /role="radiogroup"/);
  for (const muc of Object.values(MUC_NGUOI_DOC)) {
    assert.ok(html.includes(muc.nhan), `thiếu nhãn ${muc.nhan}`);
    assert.ok(html.includes(muc.giaiThich), `thiếu câu ${muc.giaiThich}`);
  }
});

/* ---------------------------------------------------- the four sets --- */

test("bốn câu giải thích nói đúng tập người, không phải bậc thang", () => {
  const chiMinh = MUC_NGUOI_DOC.only_me.giaiThich;
  const banBe = MUC_NGUOI_DOC.friends.giaiThich;
  const motNhom = MUC_NGUOI_DOC.group.giaiThich;
  const congKhai = MUC_NGUOI_DOC.public.giaiThich;

  assert.match(chiMinh, /Không ai khác/);
  assert.match(chiMinh, /bạn bè/);
  assert.match(chiMinh, /nhóm/);

  assert.match(banBe, /kết bạn/);
  assert.match(banBe, /không đọc được/);
  assert.match(banBe, /nhóm/);

  assert.match(motNhom, /thành viên nhóm/);
  assert.match(motNhom, /Bạn bè ngoài nhóm không đọc được/);

  assert.match(congKhai, /Ai mở app/);

  assert.equal(MUC_NGUOI_DOC.only_me.nhan, "Chỉ mình tôi");
  assert.equal(MUC_NGUOI_DOC.friends.nhan, "Bạn bè");
  assert.equal(MUC_NGUOI_DOC.group.nhan, "Một nhóm");
  assert.equal(MUC_NGUOI_DOC.public.nhan, "Công khai");

  for (const muc of Object.values(MUC_NGUOI_DOC)) {
    assert.equal(muc.giaiThich.includes("—"), false, `em-dash: ${muc.giaiThich}`);
    assert.equal(muc.nhan.includes("—"), false, `em-dash: ${muc.nhan}`);
  }
});

/* ---------------------------------------------------------- refusals --- */

test("lỗi máy chủ ra câu tiếng Việt, không lộ mã tiếng Anh", () => {
  const pairs = [
    [422, "unknown_audience"],
    [422, "group_audience_needs_context"],
    [422, "context_not_addressable"],
    [404, "post_not_found"],
    [403, "permission_denied"],
    [500, "internal_error"],
    [502, ""],
  ];
  const DAU = /[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụỳýỷỹỵ]/i;
  for (const [status, code] of pairs) {
    const cau = loiTuong(status, code, "Internal Server Error");
    assert.match(cau, DAU, `${code}: không phải tiếng Việt: ${cau}`);
    if (code) {
      assert.equal(cau.includes(code), false, `lộ mã ${code}: ${cau}`);
    }
    assert.equal(cau.toLowerCase().includes("unknown_audience"), false, cau);
    assert.equal(cau.includes("Internal Server Error"), false, cau);
    assert.equal(cau.includes("—"), false, cau);
  }
  assert.equal(loiTuong(500, "internal_error", "<html>502</html>"), cauMayChuLoi(500));
});

test("dangBai không đưa mã tiếng Anh ra Error.message", async () => {
  const loi = await batLoi(() =>
    withFetch(
      () =>
        res(
          { code: "unknown_audience", detail: "Post visibility must be one of the four known levels" },
          { status: 422 },
        ),
      () => dangBai({ body: "x", audience: "only_me" }, ACTOR, LAN),
    ),
  );
  assert.match(loi.message, /[ăâđêôơưàáảãạ]/i);
  assert.equal(loi.message.includes("unknown_audience"), false, loi.message);
  assert.equal(loi.message.includes("Post visibility"), false, loi.message);
});

/* ------------------------------------------------------- empty / list --- */

test("rỗng là câu mời viết, không phải ô trống", () => {
  const chu = words(
    React.createElement(Tuong, {
      nguoi: { personId: ACTOR },
      khoiDau: { trang: { pha: "xong", bai: [] } },
    }),
  );
  assert.match(chu, /Chưa có bài/);
  assert.match(chu, /Viết/);
});

test("bài trên tường hiện nhãn người đọc", () => {
  const chu = words(
    React.createElement(Tuong, {
      nguoi: { personId: ACTOR },
      khoiDau: {
        trang: {
          pha: "xong",
          bai: [{ ...WIRE, body: "Sương đèo Pren chưa tan", audience: "friends" }],
        },
      },
    }),
  );
  assert.match(chu, /Sương đèo Pren chưa tan/);
  assert.match(chu, /Bạn bè/);
});
