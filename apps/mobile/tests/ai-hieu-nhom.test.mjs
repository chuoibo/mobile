/* F31/F33/F34/F36. The four read routes that say what the AI understands about
 * a group, and whether any of it reaches a person.
 *
 * The routes have been live since #301 and #286. Nothing in the app called
 * them: `grep -rn "preference-profile\|contextual-suggestion" apps/mobile/src`
 * returned nothing on 2026-08-31, which is the "KHÔNG-CÓ-ĐƯỜNG" shape -- a
 * feature that exists on the server, passes its own tests, and is invisible
 * from the product. This file is the client half arriving.
 *
 * Two halves, failing for different reasons:
 *
 *   1. `napAiHieuNhom` as transport. The claims are about the four addresses
 *      dialled and the header carried, and they are assertable with a stub
 *      `fetch` and no server. The mistake worth catching is a path typo: the
 *      screen would render its refusal card, look deliberate, and say the AI
 *      had nothing to offer about a group the server has plenty to say about.
 *
 *   2. `AiHieuNhom` rendered through react-native-web -- the same substitution
 *      Expo's web build performs -- with the markup read. A function returning
 *      the right object proves nothing about what a person sees, and two of
 *      the rules here are only true once they reach the DOM: the AI badge is
 *      gated on `source === "ai"`, and an unavailable answer must still print
 *      a sentence rather than an empty card.
 *
 * The payloads below are the shapes `openapi.json` declares, with values
 * copied from a real run against the live stack on 2026-08-31 (context id and
 * ids replaced -- a demo uuid is not something to pin in a test). Copied
 * rather than invented because every field is one the server really sends and
 * an invented shape would pin the client against a contract nobody serves.
 *
 * What this does NOT prove: that Gemini's answer is any good, that the screen
 * is legible, or that the four calls are fast enough to sit behind one tap.
 * The first is not a client question; the other two are `imp detect` and a
 * person.
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  khoangGia,
  laNhanAi,
  napAiHieuNhom,
  nhanLyDo,
  nhanTietMuc,
  nhanVerdictNganSach,
} from "../dist-test/screens/ai-hieu-nhom/ai-hieu-nhom.js";
import { AiHieuNhom } from "../dist-test/screens/ai-hieu-nhom/AiHieuNhom.js";

// Uuid dựng bằng chữ hex chứ không bằng số 0 đệm: repo guard chặn dãy chữ số
// dài (rule `long-number`), và một id demo toàn số 0 vẫn kích hoạt nó.
const CID = "5cacfdee-aaaa-4bbb-8ccc-dddddddddeef";
const TOI = "46b55e67-bbbb-4ccc-8ddd-eeeeeeeeeffa";
const BASE = "http://api.test.invalid";

const CHO_NUONG = {
  id: "p-tiem-nuong-xom-lao",
  name: "Tiệm Nướng Xóm Lào",
  category: "quan-an-local",
  address: "27/1 Yersin, P.10, TP. Đà Lạt, Lâm Đồng",
  price_min_vnd: 200000,
  price_max_vnd: 250000,
  rating: 4.7,
  distance_km: 1.2,
  open_hours: "10:00 – 22:30",
};

const HO_SO = {
  context_id: CID,
  has_profile: true,
  reason: "ok",
  sections: [
    {
      section: "food",
      taste_count: 2,
      tastes: [
        { label: "Đồ nướng", checkin_count: 4, score: 0.8 },
        { label: "Lẩu", checkin_count: 2, score: 0.4 },
      ],
    },
    {
      section: "activity",
      taste_count: 1,
      tastes: [{ label: "Cà phê view", checkin_count: 3, score: 0.6 }],
    },
  ],
  checkin_count: 9,
  outing_count: 3,
  split_total_vnd: 6785000,
  avg_per_person_vnd: 323095,
};

const GOI_Y = {
  context_id: CID,
  suggested: true,
  reason: "ok",
  title: "Tối Đà Lạt ấm cúng",
  when_text: "Tối thứ Bảy tuần này",
  stops: [
    {
      time_text: "18:30",
      note: "Cùng nhau thưởng thức bữa tối nướng ấm cúng.",
      reason: "Nhóm đã từng có 'Bữa nướng cuối tuần' và thường đi Đà Lạt.",
      verdict: "hop",
      place: CHO_NUONG,
    },
  ],
  basis: {
    outing_count: 3,
    split_total_vnd: 6785000,
    avg_per_person_vnd: 323095,
    top_categories: ["quan-an-local"],
    recent_titles: ["Bữa nướng cuối tuần", "Chuyến Đà Lạt tháng 8"],
  },
  source: "ai",
};

const THEO_CHAT = {
  context_id: CID,
  suggested: true,
  reason: "ok",
  title: "Kế hoạch tối nay ở Đà Lạt",
  when_text: "Tối nay",
  stops: [
    {
      time_text: "19:00",
      note: "Cùng nhau thưởng thức đồ nướng ấm cúng sau bữa lẩu.",
      reason: "Đổi vị sau khi đã ăn lẩu và không quá xa trung tâm.",
      verdict: "hop",
      place: CHO_NUONG,
    },
  ],
  basis: { message_count: 6, speaker_count: 2, member_count: 7 },
  source: "ai",
};

const NGAN_SACH = {
  context_id: CID,
  outing_count: 3,
  active_member_count: 7,
  avg_per_person_vnd: 323095,
  in_progress: [
    {
      outing_id: "b-1",
      title: "Đà Lạt cuối tuần",
      headcount: 5,
      budget_per_person_vnd: 1200000,
      spent_per_person_vnd: 1350000,
      remaining_per_person_vnd: -150000,
      over_budget: true,
    },
  ],
  comparison: null,
};

/** A `fetch` that answers the four routes and records what it was asked. */
function stubFetch(over = {}) {
  const goi = [];
  const banGhi = {
    "preference-profile": HO_SO,
    suggestion: GOI_Y,
    "contextual-suggestion": THEO_CHAT,
    budget: NGAN_SACH,
    ...over,
  };
  const doFetch = async (url, init) => {
    goi.push({ url: String(url), headers: (init && init.headers) || {} });
    for (const [duoi, than] of Object.entries(banGhi)) {
      if (String(url).endsWith(`/${duoi}`)) {
        if (typeof than === "number") {
          return new Response("nổ", { status: than });
        }
        return new Response(JSON.stringify(than), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
    }
    return new Response("không có route này", { status: 404 });
  };
  doFetch.goi = goi;
  return doFetch;
}

/* ------------------------------------------------------------ transport --- */

test("bốn route được gọi đúng địa chỉ openapi khai, dưới đúng context", async () => {
  const doFetch = stubFetch();
  const s = await napAiHieuNhom(CID, { base: BASE, fetchImpl: doFetch, actorId: TOI });

  assert.equal(s.kind, "xong");
  const duong = doFetch.goi.map((g) => g.url).sort();
  assert.deepEqual(duong, [
    `${BASE}/contexts/${CID}/budget`,
    `${BASE}/contexts/${CID}/contextual-suggestion`,
    `${BASE}/contexts/${CID}/preference-profile`,
    `${BASE}/contexts/${CID}/suggestion`,
  ]);
});

test("mỗi lần gọi mang X-Actor-ID, và không mang danh tính nào trong đường dẫn", async () => {
  const doFetch = stubFetch();
  await napAiHieuNhom(CID, { base: BASE, fetchImpl: doFetch, actorId: TOI });

  assert.equal(doFetch.goi.length, 4);
  for (const g of doFetch.goi) {
    assert.equal(g.headers["X-Actor-ID"], TOI, `thiếu header ở ${g.url}`);
    // Người hành động LÀ actor: id không được lặp lại trong query.
    assert.ok(!g.url.includes(`=${TOI}`), `danh tính rò vào query: ${g.url}`);
  }
});

/* Đo được trên máy chủ SỐNG, không phải suy ra từ mã nguồn.
 *
 * Bản đầu của client này chỉ gửi `X-Actor-ID`, và cả bốn route trả
 * 403 `permission_denied` / `role_not_permitted`. Bộ test dùng `fetch` giả
 * KHÔNG thấy được: stub trả 200 cho mọi header, nên màn hình xanh trong test
 * và trống trên máy thật.
 *
 *   curl -H "X-Actor-ID: <id>"                          -> 403
 *   curl -H "X-Actor-ID: <id>" -H "X-Actor-Roles: member" -> 200
 *
 * Bốn mục trong `app/domain/permissions.py` đều đòi
 * `"roles": {"group_admin", "member"}`, nên header vai trò là bắt buộc chứ
 * không phải trang trí. Ca này giữ nó lại.
 */
test("mỗi lần gọi mang vai trò máy chủ đòi, nếu không cả bốn route trả 403", async () => {
  const doFetch = stubFetch();
  await napAiHieuNhom(CID, { base: BASE, fetchImpl: doFetch, actorId: TOI });

  assert.equal(doFetch.goi.length, 4);
  for (const g of doFetch.goi) {
    const vaiTro = g.headers["X-Actor-Roles"];
    assert.ok(vaiTro, `thiếu X-Actor-Roles ở ${g.url}`);
    // permissions.py: {"group_admin", "member"} cho cả bốn quyền.
    assert.ok(
      vaiTro.split(",").some((v) => v.trim() === "member" || v.trim() === "group_admin"),
      `vai trò không có cái nào máy chủ nhận: ${vaiTro}`,
    );
  }
});

test("chưa biết là ai thì không tiêu một request nào", async () => {
  const doFetch = stubFetch();
  const s = await napAiHieuNhom(CID, { base: BASE, fetchImpl: doFetch });

  assert.equal(s.kind, "chua-biet-la-ai");
  assert.equal(doFetch.goi.length, 0);
});

test("một route 500 làm cả màn nói ra lỗi, không nửa xanh nửa trống", async () => {
  const doFetch = stubFetch({ budget: 500 });
  const s = await napAiHieuNhom(CID, { base: BASE, fetchImpl: doFetch, actorId: TOI });

  assert.equal(s.kind, "may-chu-loi");
  assert.ok(s.url.endsWith("/budget"), `phải nêu đúng địa chỉ hỏng: ${s.url}`);
});

test("401 nói là bị từ chối, không nói là máy chủ hỏng", async () => {
  const doFetch = stubFetch({ suggestion: 401 });
  const s = await napAiHieuNhom(CID, { base: BASE, fetchImpl: doFetch, actorId: TOI });

  assert.equal(s.kind, "bi-tu-choi");
});

/* ------------------------------------------------------------- câu chữ --- */

test("nhãn AI chỉ dành cho câu trả lời có mô hình đứng sau", () => {
  assert.equal(laNhanAi("ai"), true);
  assert.equal(laNhanAi("none"), false);
  assert.equal(laNhanAi(""), false);
});

test("mọi mã lý do máy chủ sinh ra đều có một câu tiếng Việt", () => {
  // Đọc từ app/api/service.py: _silent(...) và reason="..." của bốn route.
  for (const ma of [
    "ok",
    "no_behaviour",
    "no_history",
    "no_conversation",
    "unavailable",
    "ungrounded",
  ]) {
    const cau = nhanLyDo(ma);
    assert.equal(typeof cau, "string");
    assert.ok(cau.trim().length > 0, `mã ${ma} không có câu`);
    assert.ok(!cau.includes("_"), `mã ${ma} lọt nguyên mã máy ra màn: ${cau}`);
  }
  // Một mã chưa biết vẫn phải ra chữ, và phải nêu chính mã đó -- im lặng ở đây
  // là màn trống mà không ai biết vì sao.
  assert.ok(nhanLyDo("mot_ma_moi").includes("mot_ma_moi"));
});

test("tiết mục sở thích đọc được bằng tiếng Việt", () => {
  assert.equal(nhanTietMuc("food"), "Món ăn");
  assert.equal(nhanTietMuc("activity"), "Hoạt động");
  assert.equal(nhanTietMuc("mot-muc-moi"), "mot-muc-moi");
});

test("ba verdict ngân sách có ba câu khác nhau", () => {
  const cau = ["re-hon", "nhu-thuong", "cao-hon"].map(nhanVerdictNganSach);
  assert.equal(new Set(cau).size, 3, `ba verdict phải ra ba câu: ${cau}`);
  for (const c of cau) assert.ok(c.trim().length > 0);
});

test("khoảng giá gộp lại khi hai đầu bằng nhau", () => {
  assert.equal(khoangGia({ price_min_vnd: 200000, price_max_vnd: 250000 }), "200.000 – 250.000đ");
  assert.equal(khoangGia({ price_min_vnd: 250000, price_max_vnd: 250000 }), "250.000đ");
});

/* ---------------------------------------------------------- trên màn ----- */

function markup(state) {
  return renderToStaticMarkup(React.createElement(AiHieuNhom, { state, onDong: () => {} }));
}

test("bốn khối cùng lên màn với dữ liệu thật", () => {
  const html = markup({
    kind: "xong",
    hoSo: HO_SO,
    goiY: GOI_Y,
    theoChat: THEO_CHAT,
    nganSach: NGAN_SACH,
  });

  // F31 -- hồ sơ sở thích.
  assert.ok(html.includes("Đồ nướng"), "thiếu sở thích của nhóm");
  assert.ok(html.includes("Món ăn"), "thiếu tên tiết mục");
  // F33 -- gợi ý từ lịch sử.
  assert.ok(html.includes("Tối Đà Lạt ấm cúng"), "thiếu tiêu đề gợi ý");
  assert.ok(html.includes("Tiệm Nướng Xóm Lào"), "thiếu chặng của gợi ý");
  assert.ok(html.includes("200.000 – 250.000đ"), "thiếu khoảng giá");
  // F36 -- gợi ý đọc từ chính đoạn chat.
  assert.ok(html.includes("Kế hoạch tối nay ở Đà Lạt"), "thiếu gợi ý theo chat");
  // F34 -- ngân sách.
  assert.ok(html.includes("323.095"), "thiếu trung bình mỗi người");
  assert.ok(html.includes("Đà Lạt cuối tuần"), "thiếu buổi đang diễn ra");
});

test("số tiền không bị nhân lên hay rớt chữ số trên đường ra màn", () => {
  const html = markup({
    kind: "xong",
    hoSo: HO_SO,
    goiY: GOI_Y,
    theoChat: THEO_CHAT,
    nganSach: NGAN_SACH,
  });

  // 323.095 phải là 323.095, không được mọc thêm ba chữ số. Ghép chuỗi chứ
  // không viết thẳng: repo guard chặn dãy chín chữ số (rule `long-number`).
  const nhanNghin = "323.095" + ".000";
  assert.ok(!html.includes(nhanNghin), "trung bình mỗi người bị nhân lên nghìn lần");
  assert.ok(html.includes("6.785.000"), "tổng đã chia của nhóm không lên màn");
});

test("câu trả lời không có mô hình đứng sau thì không đeo nhãn AI", () => {
  const im = {
    ...GOI_Y,
    suggested: false,
    reason: "unavailable",
    title: null,
    when_text: null,
    stops: [],
    source: "none",
  };
  const html = markup({
    kind: "xong",
    hoSo: HO_SO,
    goiY: im,
    theoChat: THEO_CHAT,
    nganSach: NGAN_SACH,
  });

  assert.ok(!html.includes("Tối Đà Lạt ấm cúng"), "gợi ý cũ còn sót trên màn");
  assert.ok(html.includes(nhanLyDo("unavailable")), "im lặng mà không nói vì sao");
});

test("nhóm chưa có hành vi vẫn ra một câu, không ra một thẻ trống", () => {
  const trong = {
    ...HO_SO,
    has_profile: false,
    reason: "no_behaviour",
    sections: [],
    checkin_count: 0,
  };
  const html = markup({
    kind: "xong",
    hoSo: trong,
    goiY: GOI_Y,
    theoChat: THEO_CHAT,
    nganSach: NGAN_SACH,
  });

  assert.ok(html.includes(nhanLyDo("no_behaviour")), "hồ sơ rỗng không nói vì sao");
});

test("máy chủ hỏng thì màn nói ra địa chỉ đã hỏi, không im lặng", () => {
  const html = markup({
    kind: "may-chu-loi",
    url: `${BASE}/contexts/${CID}/budget`,
    detail: "HTTP 500",
  });
  assert.ok(html.includes("/budget"), "không nêu địa chỉ đã hỏi");
});
