/* Tab Tin nhắn phải mở được cho người TỰ ĐĂNG KÝ, không chỉ cho bảy người seed.
 *
 * bug-223337. Đo bằng Playwright trên máy demo 8099, bundle dựng từ main
 * ba510d8. Cửa "Đăng nhập bằng số điện thoại" (F01) là cửa vào duy nhất CÓ
 * THẬT: nhập số + tên ra `POST 200 /identity/person-id` rồi `PUT 201
 * /people/{id}`, và vào thẳng shell. Bấm tab "Tin nhắn" ngay sau đó:
 *
 *     Nhóm chat / Chưa vào được nhóm
 *     Không ghi được tên người
 *     Đã thử: http://127.0.0.1:8099/people
 *     Mã: 0
 *     Chi tiết: không có người "980ebea7-..." trong nhóm demo, không bịa một
 *               người khác
 *
 * Gõ tin nhắn rồi bấm Gửi: KHÔNG một lời gọi HTTP nào. Nút bấm được và không
 * xảy ra chuyện gì.
 *
 * Gốc của cả hai triệu chứng là một dòng, và nó nằm trước mạng chứ không sau:
 * `khoiDongNhom` nhận một *slug* rồi tra `personById` trong bảy người cứng của
 * `nhom-demo.ts`. Người vừa đăng ký có `id === personId === <UUID máy chủ
 * mint>`, không nằm trong bảy người đó, nên hàm trả `hong(...)` với `status: 0`
 * -- mã 0 nghĩa là "chưa hỏi ai cả". Màn vẽ thẻ hỏng, và mọi tay ghi trong
 * `TinNhan.tsx` (`gui`, `moBinhChon`, `boPhieu`, `tachTien`) đều mở đầu bằng
 * `if (!nguoi || nhom.kind !== "xong") return;`. Đó là nút Gửi không sinh
 * request: không phải mất `onPress`, mà là hàm thoát ở dòng đầu.
 *
 * Hậu quả không dừng ở một tab: F07 F08 F33 F16 F17 F24 đều sống trong chat.
 *
 * Vì sao bộ này ĐỎ được ở bản cũ: `khoiDongNhom` giữ nguyên tên và vẫn nhận
 * đúng một tham số định danh qua bản vá. Bản cũ nhận slug và tra bảng, bản mới
 * nhận chính người dùng. Nên cùng một lời gọi: bản cũ trả `hong` và **không
 * gửi byte nào**, bản mới trả `xong` sau các request thật. `import * as Nhom`
 * chứ không phải named import, vì `moNhomDaCo` và `moNhomChoMan` chỉ có ở bản
 * mới -- một named import làm cả file không parse được, biến bốn khẳng định
 * riêng biệt thành một lỗi cú pháp duy nhất.
 *
 * File này KHÔNG chứng minh: máy chủ thật chấp nhận chuỗi request này, hay màn
 * hình vẽ đúng sau đó. Nó chứng minh cái mà một lời gọi hàm thấy được -- người
 * tự đăng ký đi tới được một `contextId`, và có đường ra mạng.
 *
 * Chạy từ apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs \
 *       && node --test tests/nhom-cua-phien.test.mjs
 */
import assert from "node:assert/strict";
import test from "node:test";

import * as Nhom from "../dist-test/screens/chat/nhom.js";
import { guiTinNhan } from "../dist-test/screens/chat/tin-nhan.js";
import { DEMO_PEOPLE } from "../dist-test/navigation/nhom-demo.js";
import { khoaGhi } from "../dist-test/screens/chat/uuid5.js";

const { khoiDongNhom } = Nhom;

const BASE = "http://api.test.invalid";

/** Nhóm demo, như `POST /contexts` trả về khi khoá ghi được replay. */
const NHOM_DEMO = "7c9e6679-7425-40de-944b-e07fc1f90ae7";

/** Nhóm người dùng tự mở ở màn F03/F04, do `VoTab` giữ qua các tab. */
const NHOM_PHIEN = { id: "3f2a91c4-8d5e-4b17-ae60-c1d4f9b3e872", display_name: "Team Sài Gòn" };

/** Người vừa đăng ký bằng số điện thoại.
 *
 *  `id` và `personId` là cùng một UUID -- `DangKy.tsx` dựng đúng hình dạng đó
 *  từ id máy chủ mint ra -- và nó không nằm trong bảy người của `nhom-demo.ts`.
 *  Đây là toàn bộ điều kiện tái lập lỗi. */
const NGUOI_MOI = {
  id: "980ebea7-0f5e-4f7c-9a3f-1c2d3e4f5a6b",
  personId: "980ebea7-0f5e-4f7c-9a3f-1c2d3e4f5a6b",
  name: "Bảo",
  initials: "B",
};

const MINH = DEMO_PEOPLE.find((p) => p.id === "minh");

/* ------------------------------------------------------------ máy chủ giả --- */

/** Vừa đủ API để `khoiDongNhom` chạy hết bốn bước, và ghi lại từng lời gọi.
 *
 *  Ghi lại là nửa quan trọng: triệu chứng được báo không phải "sai kết quả" mà
 *  là "không có request nào", nên phép đo phải đếm được số không đó. */
function mayChuGia({ thanhVien = [] } = {}) {
  const goi = [];
  const soCoMat = new Set(thanhVien.map((t) => t.person_id));

  function traLoi(status, body) {
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
      text: async () => JSON.stringify(body),
    };
  }

  async function fetchGia(url, init = {}) {
    const method = init.method ?? "GET";
    const duong = new URL(url).pathname;
    goi.push({ method, duong, headers: init.headers ?? {}, body: init.body ?? null });

    if (method === "PUT" && duong.startsWith("/people/")) {
      return traLoi(200, { id: duong.slice("/people/".length), display_name: "x" });
    }
    if (method === "POST" && duong === "/contexts") {
      return traLoi(201, { id: NHOM_DEMO, display_name: "Team Đà Lạt" });
    }
    if (method === "POST" && /^\/contexts\/[^/]+\/members$/.test(duong)) {
      const than = JSON.parse(init.body ?? "{}");
      soCoMat.add(than.person_id);
      return traLoi(201, {
        id: `tv-${than.person_id}`,
        context_id: duong.split("/")[2],
        person_id: than.person_id,
        state: "invited",
        role: "member",
      });
    }
    if (method === "POST" && /^\/memberships\/[^/]+\/accept$/.test(duong)) {
      return traLoi(200, { id: duong.split("/")[2], state: "active", role: "member" });
    }
    if (method === "GET" && /^\/contexts\/[^/]+\/members$/.test(duong)) {
      const ctx = duong.split("/")[2];
      const members = [...soCoMat].map((pid) => ({
        id: `tv-${pid}`,
        context_id: ctx,
        person_id: pid,
        display_name: pid === NGUOI_MOI.personId ? NGUOI_MOI.name : "Minh",
        state: "active",
        role: pid === MINH.personId ? "admin" : "member",
      }));
      return traLoi(200, { members });
    }
    if (method === "POST" && /^\/contexts\/[^/]+\/messages$/.test(duong)) {
      return traLoi(201, {
        id: "tin-1",
        context_id: duong.split("/")[2],
        author_id: NGUOI_MOI.personId,
        kind: "text",
        body: JSON.parse(init.body ?? "{}").body,
        image_url: null,
        card: null,
        created_at: "2026-08-30T15:00:00Z",
        // `parseMessage` đòi cursor là chuỗi không rỗng. Máy chủ giả phải trả
        // đúng hình dạng máy chủ thật trả, nếu không thì ca này xanh/đỏ theo
        // fixture chứ không theo sản phẩm.
        cursor: "2026-08-30T15:00:00Z|tin-1",
      });
    }
    return traLoi(404, { detail: `máy chủ giả không biết ${method} ${duong}` });
  }

  return { fetchGia, goi };
}

/** Đổi transport toàn cục cho các module không nhận `fetchImpl`. */
async function voiFetch(vanChuyen, chay) {
  const cu = globalThis.fetch;
  globalThis.fetch = vanChuyen;
  try {
    return await chay();
  } finally {
    globalThis.fetch = cu;
  }
}

/* ------------------------------------------------------------------ ca đo --- */

test("người tự đăng ký mở được nhóm, và việc đó có đi ra mạng", async () => {
  const may = mayChuGia();
  const s = await voiFetch(may.fetchGia, () => khoiDongNhom(NGUOI_MOI, { base: BASE }));

  // Số không request là chính triệu chứng được báo, nên nó được đo trước:
  // `status: 0` trên màn nghĩa là hàm đã bỏ cuộc trước khi hỏi máy chủ.
  assert.ok(
    may.goi.length > 0,
    `người tự đăng ký không sinh lời gọi HTTP nào — bị từ chối trước khi hỏi máy chủ: ${JSON.stringify(s)}`,
  );
  assert.equal(
    s.kind,
    "xong",
    `khoiDongNhom từ chối người tự đăng ký: ${JSON.stringify(s)}`,
  );
  assert.ok(
    may.goi.some((g) => g.method === "PUT" && g.duong === `/people/${NGUOI_MOI.personId}`),
    "tên người tự đăng ký không được ghi lên máy chủ",
  );
  assert.ok(
    s.members.some((m) => m.personId === NGUOI_MOI.personId && m.state === "active"),
    `người tự đăng ký không có trong danh sách thành viên: ${JSON.stringify(s.members)}`,
  );
});

test("gửi tin nhắn của người tự đăng ký sinh ra POST /messages thật", async () => {
  const may = mayChuGia();
  await voiFetch(may.fetchGia, async () => {
    const s = await khoiDongNhom(NGUOI_MOI, { base: BASE });
    assert.equal(s.kind, "xong", `chưa mở được nhóm nên chưa gửi được: ${JSON.stringify(s)}`);

    // Đúng thân hàm `gui()` trong TinNhan.tsx: nó thoát ngay ở dòng đầu khi
    // `nhom.kind !== "xong"`, nên có `contextId` hay không là toàn bộ khác
    // biệt giữa "gửi được" và "bấm không xảy ra chuyện gì".
    const sent = await guiTinNhan({
      contextId: s.contextId,
      actorId: NGUOI_MOI.personId,
      body: "đi ăn không",
      idempotencyKey: "k-1",
      base: BASE,
    });
    assert.equal(sent.kind, "xong", `gửi hỏng: ${JSON.stringify(sent)}`);
    assert.ok(
      may.goi.some((g) => g.method === "POST" && g.duong === `/contexts/${s.contextId}/messages`),
      "không có POST /messages nào rời khỏi app",
    );
  });
});

test("nhóm của phiên được mở thẳng, không dựng lại nhóm demo", async () => {
  assert.equal(
    typeof Nhom.moNhomDaCo,
    "function",
    "chưa có đường mở nhóm mà phiên đã tự tạo — chat vẫn phân giải theo nhóm demo",
  );
  const may = mayChuGia({ thanhVien: [{ person_id: NGUOI_MOI.personId }] });
  const s = await voiFetch(may.fetchGia, () =>
    Nhom.moNhomDaCo(NHOM_PHIEN, NGUOI_MOI, { base: BASE }),
  );

  assert.equal(s.kind, "xong", `không mở được nhóm của phiên: ${JSON.stringify(s)}`);
  assert.equal(s.contextId, NHOM_PHIEN.id, "chat mở nhóm khác nhóm người dùng đang ở");
  assert.equal(s.tenNhom, NHOM_PHIEN.display_name);
  assert.ok(
    !may.goi.some((g) => g.method === "POST" && g.duong === "/contexts"),
    "đã dựng lại nhóm demo dù phiên đã có nhóm có thật",
  );
});

test("moNhomChoMan: có nhóm phiên thì dùng nó, không có thì mới tới nhóm demo", async () => {
  assert.equal(typeof Nhom.moNhomChoMan, "function", "màn chat chưa có chỗ chọn nhóm");

  const coPhien = mayChuGia({ thanhVien: [{ person_id: NGUOI_MOI.personId }] });
  const a = await voiFetch(coPhien.fetchGia, () =>
    Nhom.moNhomChoMan(NGUOI_MOI, NHOM_PHIEN, { base: BASE }),
  );
  assert.equal(a.kind, "xong");
  assert.equal(a.contextId, NHOM_PHIEN.id);

  const khongPhien = mayChuGia();
  const b = await voiFetch(khongPhien.fetchGia, () =>
    Nhom.moNhomChoMan(NGUOI_MOI, null, { base: BASE }),
  );
  assert.equal(b.kind, "xong");
  assert.equal(b.contextId, NHOM_DEMO, "không có nhóm phiên thì phải rơi về nhóm demo");
});

test("bảy người seed vẫn vào đúng nhóm demo, và khoá ghi không đổi", async () => {
  const may = mayChuGia();
  const s = await voiFetch(may.fetchGia, () => khoiDongNhom(MINH, { base: BASE }));

  assert.equal(s.kind, "xong", JSON.stringify(s));
  assert.equal(s.contextId, NHOM_DEMO);

  // Khoá ghi của `POST /contexts` là thứ duy nhất kéo được nhóm đã seed về --
  // không có `GET /contexts` để tra. Đổi nó là mọc ra một "Team Đà Lạt" thứ
  // hai bên cạnh cái đang giữ thành viên và lịch sử.
  const tao = may.goi.find((g) => g.method === "POST" && g.duong === "/contexts");
  assert.ok(tao, "không còn tạo/replay nhóm demo");
  assert.equal(tao.headers["Idempotency-Key"], khoaGhi("context"));
  assert.equal(tao.headers["X-Actor-ID"], MINH.personId, "nhóm demo phải do minh đứng tên");
});
