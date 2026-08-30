/* F14. The rules deciding which invite control may exist on a trip.
 *
 * These run under bare node against the compiled `moi-vao-chuyen.ts`. What
 * they prove is that the screen offers a button exactly when the server would
 * accept the request behind it. What they do NOT prove is that the server
 * still behaves that way -- every rule here is a claim about
 * `create_outing_invite`, and the evidence for those claims is a walk against
 * the live API, recorded in the PR. A green file here with a changed server is
 * a screen that offers a button earning a 409.
 */
import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { MoiVaoChuyen } from "../dist-test/screens/len-plan/MoiVaoChuyen.js";

const {
  danhSachMoiDuoc,
  gopLoiMoi,
  loiMoiCuaNguoi,
  tenLoiMoi,
  tomTatLoiMoi,
} = await import("../dist-test/screens/len-plan/moi-vao-chuyen.js");

const TOI = "p-toi";
const QUYEN = "p-quyen";
const HA = "p-ha";

function thanhVien(personId, over = {}) {
  return {
    id: `m-${personId}`,
    context_id: "c1",
    person_id: personId,
    display_name: personId,
    state: "active",
    role: "member",
    invited_by_id: null,
    joined_at: "2026-08-01T00:00:00Z",
    left_at: null,
    created_at: "2026-08-01T00:00:00Z",
    ...over,
  };
}

function loiMoi(over = {}) {
  return {
    id: "i1",
    outing_id: "o1",
    source: "group",
    invited_person_id: QUYEN,
    invited_by_id: TOI,
    created_at: "2026-08-31T00:00:00Z",
    expires_at: "2026-09-07T00:00:00Z",
    revoked_at: null,
    invite_token: null,
    invite_path: null,
    ...over,
  };
}

const BAY_GIO = Date.parse("2026-08-31T01:00:00Z");

test("một thành viên đang hoạt động, chưa mời, thì mời được", () => {
  const ds = danhSachMoiDuoc([thanhVien(QUYEN)], TOI, []);
  assert.equal(ds.length, 1);
  assert.equal(ds[0].moiDuoc, true);
  assert.equal(ds[0].vi, null);
});

test("chính mình không hiện nút mời", () => {
  const ds = danhSachMoiDuoc([thanhVien(TOI)], TOI, []);
  assert.equal(ds[0].moiDuoc, false);
  assert.equal(ds[0].vi, "Đây là bạn.");
});

/* The server builds its roster from `state == "active"` only
 * (service.py:3620), so a `group` invite naming an `invited` row is a 422
 * `participant_not_in_context`. Offering the button would earn a refusal whose
 * wording is about the group when the real answer is "they have not accepted
 * yet". */
test("người chưa nhận lời vào nhóm thì chưa mời vào chuyến được", () => {
  const ds = danhSachMoiDuoc([thanhVien(QUYEN, { state: "invited" })], TOI, []);
  assert.equal(ds[0].moiDuoc, false);
  assert.match(ds[0].vi, /Chưa nhận lời vào nhóm/);
});

test("người đã rời nhóm thì không mời được, và nói rõ vì sao", () => {
  const ds = danhSachMoiDuoc([thanhVien(QUYEN, { state: "left" })], TOI, []);
  assert.equal(ds[0].moiDuoc, false);
  assert.equal(ds[0].vi, "Đã rời nhóm.");
});

test("đã mời trong lượt này thì không mời lại", () => {
  const ds = danhSachMoiDuoc([thanhVien(QUYEN)], TOI, [loiMoi()]);
  assert.equal(ds[0].moiDuoc, false);
  assert.equal(ds[0].vi, "Đã mời vào chuyến này.");
});

/* The one that is easy to get wrong, and the reason `loiMoiCuaNguoi` does not
 * filter revoked rows. `uq_outing_invites_person` is unique on
 * `(outing_id, invited_person_id)` with no clause about revocation
 * (models.py:1323) and `find_outing_invite_for_person` does not filter either
 * (repository.py:2160), so the second invite is a 409. Thu hồi is a one-way
 * door for that person on that trip, and the screen has to say so BEFORE the
 * button rather than after the refusal. */
test("thu hồi rồi vẫn không mời lại người đó vào chuyến này được", () => {
  const ds = danhSachMoiDuoc(
    [thanhVien(QUYEN)],
    TOI,
    [loiMoi({ revoked_at: "2026-08-31T00:30:00Z" })],
  );
  assert.equal(ds[0].moiDuoc, false);
  assert.match(ds[0].vi, /Đã thu hồi/);
  assert.match(ds[0].vi, /không mời lại/);
});

test("lời mời bằng link không chiếm chỗ của ai", () => {
  const link = loiMoi({ id: "i-link", source: "link", invited_person_id: null });
  assert.equal(loiMoiCuaNguoi([link], QUYEN), null);
  const ds = danhSachMoiDuoc([thanhVien(QUYEN)], TOI, [link]);
  assert.equal(ds[0].moiDuoc, true);
});

test("hàng nào cũng còn trong danh sách, không ai bị giấu đi", () => {
  const ds = danhSachMoiDuoc(
    [thanhVien(TOI), thanhVien(QUYEN), thanhVien(HA, { state: "left" })],
    TOI,
    [loiMoi()],
  );
  assert.deepEqual(
    ds.map((h) => h.personId),
    [TOI, QUYEN, HA],
  );
  assert.deepEqual(
    ds.map((h) => h.moiDuoc),
    [false, false, false],
  );
});

/* The revoke reply carries `invite_token: null` on purpose. Replacing instead
 * of merging would drop the link out of the list at the exact moment somebody
 * wants to check WHICH of three links they just pulled back. */
test("gộp bản thu hồi giữ lại token của bản tạo", () => {
  const tao = loiMoi({
    id: "i-link",
    source: "link",
    invited_person_id: null,
    invite_token: "tok",
    invite_path: "/outing-invites/tok",
  });
  const sau = gopLoiMoi([tao], {
    ...tao,
    revoked_at: "2026-08-31T00:30:00Z",
    invite_token: null,
    invite_path: null,
  });
  assert.equal(sau.length, 1);
  assert.equal(sau[0].invite_token, "tok");
  assert.equal(sau[0].invite_path, "/outing-invites/tok");
  assert.equal(sau[0].revoked_at, "2026-08-31T00:30:00Z");
});

test("lời mời mới nằm trên đầu, không đè lên cái cũ", () => {
  const a = loiMoi({ id: "a" });
  const b = loiMoi({ id: "b", invited_person_id: HA });
  const sau = gopLoiMoi([a], b);
  assert.deepEqual(sau.map((m) => m.id), ["b", "a"]);
});

test("tên lời mời đọc từ sổ thành viên, không in ra uuid", () => {
  const roster = [thanhVien(QUYEN, { display_name: "Quyên" })];
  assert.equal(tenLoiMoi(loiMoi(), roster), "Lời mời cho Quyên");
  // Không có hàng nào khớp: nói bằng chữ, tuyệt đối không in id ra màn hình.
  const la = tenLoiMoi(loiMoi({ invited_person_id: "p-la" }), roster);
  assert.equal(la, "Lời mời cho một người");
  assert.ok(!la.includes("p-la"));
  assert.equal(
    tenLoiMoi(loiMoi({ source: "link", invited_person_id: null }), roster),
    "Lời mời bằng link",
  );
});

/* ---------------------------------------------------------------- màn vẽ ra
 *
 * Rendered through react-native-web, the same substitution Expo's web build
 * performs, so what is asserted is the markup a browser really gets.
 *
 * The reason to render at all rather than read the source: `moi-man-co-duong-
 * do.test.mjs` proves `?man=moi-vao-chuyen` is an address `App.tsx` routes. It
 * does NOT prove anything renders at that address, and a screen that throws on
 * mount would keep that gate green -- the address is still spelled in the
 * file. These three cases are the part a source read cannot reach.
 */
function ve(props) {
  return renderToStaticMarkup(
    React.createElement(MoiVaoChuyen, {
      buoi: {
        id: "o1",
        context_id: "c1",
        created_by_id: TOI,
        title: "Đà Lạt cuối tuần",
        starts_on: "2026-10-17",
        ends_on: "2026-10-19",
        headcount: 8,
        budget_per_person_vnd: 2500000,
        created_at: "2026-08-31T00:00:00Z",
        stops: [],
      },
      roster: { kind: "xong", ds: [thanhVien(TOI), thanhVien(QUYEN)] },
      toiId: TOI,
      daMoi: [],
      bayGio: BAY_GIO,
      onMoiThanhVien: () => {},
      onTaoLink: () => {},
      onThuHoi: () => {},
      onTaiLaiRoster: () => {},
      onQuayLai: () => {},
      ...props,
    }),
  );
}

test("màn mở được và in tên chuyến cùng nút mời", () => {
  const html = ve();
  assert.match(html, /Đà Lạt cuối tuần/);
  assert.match(html, /Người trong nhóm/);
  // Hàng của người mời được phải có nút; hàng của chính mình thì không.
  assert.match(html, /Mời vào chuyến/);
  assert.match(html, /Đây là bạn/);
  assert.match(html, /Tạo link mời/);
});

/* The sentence this screen exists to say. It has to be ON the markup, under
 * the button, not merely written in a source file somebody trusts. */
test("câu 'thu hồi là cửa một chiều' thật sự nằm trên màn", () => {
  const link = loiMoi({
    id: "i-link",
    source: "link",
    invited_person_id: null,
    invite_token: "tok",
    invite_path: "/outing-invites/tok",
  });
  const html = ve({ daMoi: [link] });
  assert.match(html, /Thu hồi/);
  assert.match(html, /không mời lại người đó vào chuyến này được nữa/);
  // Và câu nói rõ danh sách chỉ là của lượt này, không phải của chuyến.
  assert.match(html, /trống ở đây không có nghĩa là chuyến chưa mời ai/);
});

/* A UUID is not a name, and this screen holds four of them: the trip, the
 * group, the inviter, and the invited person. None may reach a person's
 * screen. This is the assertion that would have caught printing an id as a
 * fallback label, which is the easy mistake when a roster lookup misses. */
test("không một uuid nào rơi ra màn", () => {
  const la = "9f9f9f9f-abcd-4abc-8abc-9f9f9f9f9f9f";
  const html = ve({
    daMoi: [loiMoi({ id: "i9", invited_person_id: la })],
  });
  assert.ok(!html.includes(la), "id của người không có trong sổ đã lọt ra màn");
  assert.match(html, /Lời mời cho một người/);
});

test("tóm tắt đếm đúng cái còn hiệu lực", () => {
  assert.equal(tomTatLoiMoi([], BAY_GIO), "Chưa tạo lời mời nào trong lượt này.");
  const ds = [
    loiMoi({ id: "a" }),
    loiMoi({ id: "b", revoked_at: "2026-08-31T00:30:00Z" }),
    loiMoi({ id: "c", expires_at: "2026-08-30T00:00:00Z" }),
  ];
  assert.equal(tomTatLoiMoi(ds, BAY_GIO), "3 lời mời tạo trong lượt này, 1 còn hiệu lực.");
});
