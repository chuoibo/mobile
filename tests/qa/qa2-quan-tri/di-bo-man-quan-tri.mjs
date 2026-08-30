/* Drive the group-administration screen in a real browser against a real API.
 *
 * The walk in `di-bo-quan-tri.py` proves the five routes accept what the
 * client module builds. It says nothing about whether anybody can reach them
 * from the app -- a route with no screen in front of it is not a feature, and
 * this repository has shipped that shape before.
 *
 * So this file asserts the other half, and only the other half:
 *
 *   1. The screen is reachable BY TAPPING: [+] menu -> Tạo nhóm -> the group
 *      screen -> "Quản trị nhóm". Not by a fragment, which would prove only
 *      that a detector can open it.
 *   2. It is reachable by URL too (`#vao=quan-tri`), so a screenshot pass or an
 *      accessibility sweep can open it at all.
 *   3. Pressing its controls sends the routes it claims to send. Every fetch
 *      the page makes is recorded before the bundle runs, so the assertion is
 *      about what left the browser, not about what a comment says.
 *   4. What the server answered is on the screen: the group's name, the
 *      roster, the invite link.
 *
 * What it does NOT prove: iOS or Android layout (this is Chrome), that the
 * screen is legible or accessible (nothing here measures contrast or a tap
 * target), or anything about a group that predates the session.
 *
 * Usage:
 *   cd apps/mobile
 *   EXPO_PUBLIC_API_URL=<api> npx expo export --platform web --output-dir /tmp/w --clear
 *   API=<api> WEB=/tmp/w node ../../tests/qa/qa2-quan-tri/di-bo-man-quan-tri.mjs
 *
 * Point API at a disposable stack. This writes memberships, roles and invites.
 */
import { randomUUID } from "node:crypto";
import { existsSync } from "node:fs";
import { join } from "node:path";

import { findChrome, launch, serve } from "../../../apps/mobile/tests/chrome-cdp.mjs";

const API = (process.env.API ?? "http://127.0.0.1:8099").replace(/\/$/, "");
const WEB = process.env.WEB ?? "/tmp/qa2-quantri";
const MINH = "46b55e67-932b-5415-a5ee-08fb2641a4ff";
const TRANG = "49871dab-3bf9-5140-acf3-6c9736b31e8f";
const QUYEN_ADMIN = "group_admin,member,advancer,recipient,batch_owner";

const hong = [];
let dat = 0;
/** Lifted out of `main`'s try so the repair below can run even when an
 *  assertion threw. Leaving is the destructive step here; a run that dies
 *  after it leaves the next run unable to open the group at all, which reads
 *  as "the screen is broken" and is not. */
let contextId = null;

function can(nhan, ok, them = "") {
  console.log(`  ${ok ? "ĐẠT " : "HỎNG"} ${nhan}${them ? " — " + them : ""}`);
  if (ok) dat += 1;
  else hong.push(nhan + (them ? ` (${them})` : ""));
  return ok;
}

async function api(method, path, { actor, roles, contexts, body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (actor) {
    headers["X-Actor-ID"] = actor;
    headers["X-Actor-Roles"] = roles ?? "member,advancer,recipient,batch_owner";
  }
  if (contexts) headers["X-Actor-Contexts"] = contexts;
  headers["Idempotency-Key"] = randomUUID();
  const r = await fetch(API + path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await r.text();
  return { status: r.status, body: text ? JSON.parse(text) : null };
}

/** Record every fetch the page makes, installed before the bundle runs.
 *
 *  A wrapper set from a test after load would miss the reads the screen fires
 *  on mount, which are exactly the ones being asserted. */
const GHI_FETCH = `
  window.__goi = [];
  const that = window.fetch;
  window.fetch = function (input, init) {
    const url = typeof input === "string" ? input : input.url;
    const method = (init && init.method) || (input && input.method) || "GET";
    const row = { method, url, status: null };
    window.__goi.push(row);
    return that.apply(this, arguments).then(
      (res) => { row.status = res.status; return res; },
      (err) => { row.status = 0; throw err; },
    );
  };
`;

/** Press the control whose visible text is exactly `nhan`.
 *
 *  `clickLabel` in chrome-cdp keys on `aria-label`, which the shared `Button`
 *  in `ui/Kit.tsx` does not set -- it labels itself with its child text. So
 *  this finds the `role="button"` carrying that text and dispatches the same
 *  real mouse press, for the same reason: react-native-web's `Pressable`
 *  listens on pointer events and a synthetic `.click()` can miss `onPress`
 *  entirely, which would report a dead control as a live one. */
async function bam(page, nhan) {
  const box = await page.evaluate((t) => {
    const nut = [...document.querySelectorAll('[role="button"]')].find(
      (e) => (e.textContent || "").trim() === t,
    );
    if (!nut) return null;
    nut.scrollIntoView({ block: "center", inline: "nearest" });
    const r = nut.getBoundingClientRect();
    const x = r.left + r.width / 2;
    const y = r.top + r.height / 2;
    return { x, y, trongMan: x >= 0 && x <= innerWidth && y >= 0 && y <= innerHeight };
  }, nhan);
  if (!box) throw new Error(`không thấy nút có chữ ${JSON.stringify(nhan)}`);
  if (!box.trongMan) {
    throw new Error(
      `nút ${JSON.stringify(nhan)} nằm ngoài khung sau khi cuộn (tâm ${Math.round(box.x)},${Math.round(box.y)}) — bấm vào đó là bấm vào chỗ trống`,
    );
  }
  const chung = { x: box.x, y: box.y, button: "left", clickCount: 1, buttons: 1 };
  await page.call("Input.dispatchMouseEvent", { type: "mouseMoved", ...chung, buttons: 0 });
  await page.call("Input.dispatchMouseEvent", { type: "mousePressed", ...chung });
  await page.call("Input.dispatchMouseEvent", { type: "mouseReleased", ...chung });
}

/** Press the role control on ONE named person's row, and say which way it went.
 *
 *  Not `bam(page, "Đặt làm quản trị")`. That label is only on screen while
 *  somebody is a plain member, so a walk keyed on it works once and then
 *  reports a missing button on a screen that is rendering "Bỏ quyền quản trị"
 *  correctly -- which is what happened here after a re-run left all three
 *  members as admins. Naming the row instead means the walk asserts on the
 *  person it meant to change, whichever direction the button points today. */
async function bamVaiTro(page, ten) {
  // Measures and presses in one step, deliberately. Handing the LABEL back to
  // `bam` looked right and was not: `bam` re-finds by text and presses the
  // FIRST row carrying it, so asking for Ngọc's row and getting Trang's is a
  // silent swap -- the console then narrates a person the run never touched.
  const o = await page.evaluate((t) => {
    const nhanVaiTro = ["Đặt làm quản trị", "Bỏ quyền quản trị"];
    const nut = [...document.querySelectorAll('[role="button"]')]
      .filter((e) => nhanVaiTro.includes((e.textContent || "").trim()))
      .find((e) => {
        let p = e.parentElement;
        for (let i = 0; i < 6 && p; i += 1, p = p.parentElement) {
          if ((p.textContent || "").trim().startsWith(t)) return true;
        }
        return false;
      });
    if (!nut) return null;
    nut.scrollIntoView({ block: "center", inline: "nearest" });
    const r = nut.getBoundingClientRect();
    const x = r.left + r.width / 2;
    const y = r.top + r.height / 2;
    return {
      nhan: (nut.textContent || "").trim(),
      x,
      y,
      trongMan: x >= 0 && x <= innerWidth && y >= 0 && y <= innerHeight,
    };
  }, ten);
  if (!o) throw new Error(`không thấy nút đổi vai trò trên hàng của ${ten}`);
  if (!o.trongMan) throw new Error(`nút đổi vai trò của ${ten} nằm ngoài khung sau khi cuộn`);
  const chung = { x: o.x, y: o.y, button: "left", clickCount: 1, buttons: 1 };
  await page.call("Input.dispatchMouseEvent", { type: "mouseMoved", ...chung, buttons: 0 });
  await page.call("Input.dispatchMouseEvent", { type: "mousePressed", ...chung });
  await page.call("Input.dispatchMouseEvent", { type: "mouseReleased", ...chung });
  return o.nhan;
}

const coChu = (t) => document.body.innerText.includes(t);
/** The recorded calls as data, not as one string per row.
 *
 *  Written as a string first and matched with an anchored regex, which is how
 *  three assertions passed vacuously: `/contexts/<uuid>$` can never match
 *  `GET http://.../contexts/<uuid> -> 200`, so every check reported "không
 *  thấy" for calls the page had in fact made. Keeping method, url and status
 *  apart means an anchor anchors the thing it names. */
const goiCua = () => window.__goi.map((g) => ({ method: g.method, url: g.url, status: g.status }));

const inGoi = (ds) => ds.map((g) => `${g.method} ${g.url} -> ${g.status}`);

/** Open a URL, forcing a real document load.
 *
 *  `Page.navigate` to a URL that differs only in its fragment -- or not at all
 *  -- is a same-document navigation: no reload, no re-mount, no refetch. That
 *  cost a run here. Step 2 opened `#vao=quan-tri&nguoi=minh`, step 4 asked for
 *  the same address after seeding an outing, nothing reloaded, and the invite
 *  card was still rendering the empty state from before the outing existed --
 *  which reads exactly like a screen that cannot list outings. `about:blank`
 *  in between makes the second navigation a real one. */
async function moLai(page, url, ...args) {
  await page.goto("about:blank", () => document.readyState === "complete");
  await page.goto(url, ...args);
}

function khop(ds, method, re, status) {
  return ds.some(
    (g) => g.method === method && re.test(g.url) && (status === undefined || g.status === status),
  );
}

async function main() {
  if (!existsSync(join(WEB, "index.html"))) {
    console.error(`không có bản dựng web ở ${WEB}`);
    return 2;
  }
  const bin = findChrome();
  if (!bin) {
    console.error("không tìm thấy Chrome — không đo được gì cả, và im lặng thoát 0 là nói dối");
    return 2;
  }
  const healthz = await fetch(API + "/healthz").then((r) => r.status).catch(() => 0);
  if (healthz !== 200) {
    console.error(`API ${API} không trả lời /healthz (${healthz})`);
    return 2;
  }
  console.log(`# API = ${API}\n# web = ${WEB}\n`);

  const server = await serve(WEB);
  const page = await launch(bin);
  await page.viewport(390, 844);
  await page.call("Page.addScriptToEvaluateOnNewDocument", { source: GHI_FETCH });

  try {
    /* ---------------------------------------------- 1. đường bấm từ giao diện */
    console.log("## 1. tới được bằng cách BẤM, không phải bằng fragment");
    await moLai(page, server.url + "#vao=nhom&nguoi=minh", coChu, "Nhóm của bạn");
    await page.waitFor(coChu, { label: "nhóm mở xong", timeout: 30000 }, "Quản trị nhóm");
    can("màn Nhóm có nút 'Quản trị nhóm'", true);
    await bam(page, "Quản trị nhóm");
    await page.waitFor(coChu, { label: "màn quản trị mở", timeout: 20000 }, "Quản trị nhóm");
    const tieuDe = await page.evaluate(
      () => document.body.innerText.includes("Ai trong nhóm, ai được làm gì"),
    );
    can("bấm nút mở ra màn Quản trị nhóm", tieuDe);

    /* ---------------------------------------------- 2. tới được bằng URL */
    console.log("\n## 2. tới được bằng URL (#vao=quan-tri)");
    await moLai(page, server.url + "#vao=quan-tri&nguoi=minh", coChu, "Quản trị nhóm");
    await page.waitFor(coChu, { label: "đọc xong nhóm", timeout: 40000 }, "Thành viên");
    can("URL cold mở thẳng màn quản trị", true);

    /* ---------------------------------------------- 3. ba lệnh đọc lúc mở */
    console.log("\n## 3. mở màn là gọi ba route đọc");
    let ds = await page.evaluate(goiCua);
    const uuid = "[0-9a-f-]{36}";
    can(
      "GET /contexts/{id} trả 200",
      khop(ds, "GET", new RegExp(`/contexts/${uuid}$`), 200),
      inGoi(ds).find((d) => new RegExp(`^GET .*/contexts/${uuid} `).test(d)) ?? "không thấy",
    );
    can(
      "GET /contexts/{id}/members trả 200",
      khop(ds, "GET", new RegExp(`/contexts/${uuid}/members$`), 200),
    );
    can(
      "GET /contexts/{id}/outings trả 200",
      khop(ds, "GET", new RegExp(`/contexts/${uuid}/outings$`), 200),
    );

    contextId = ds
      .map((g) => g.url.match(new RegExp(`/contexts/(${uuid})$`))?.[1])
      .find(Boolean);
    if (!contextId) {
      can("đọc được context_id từ lệnh gọi", false);
      throw new Error("không lấy được context_id, không đi tiếp được");
    }
    console.log(`    context_id = ${contextId}`);

    const tenNhom = await page.evaluate(() => document.body.innerText.slice(0, 400));
    can(
      "tên nhóm máy chủ trả về có trên màn",
      tenNhom.includes("Team Đà Lạt"),
      JSON.stringify(tenNhom.split("\n").slice(0, 4).join(" | ")),
    );

    /* ------------------------------- nền: một người thứ hai và một chuyến đi */
    console.log("\n## nền cho hai thẻ sau: thêm Trang, thêm một chuyến");
    const moi = await api("POST", `/contexts/${contextId}/members`, {
      actor: MINH,
      roles: QUYEN_ADMIN,
      contexts: contextId,
      body: { person_id: TRANG },
    });
    if (moi.status === 201) {
      await api("POST", `/memberships/${moi.body.id}/accept`, { actor: TRANG });
    }
    console.log(`    mời Trang -> ${moi.status}`);
    const buoi = await api("POST", `/contexts/${contextId}/outings`, {
      actor: MINH,
      contexts: contextId,
      body: {
        title: "QA quản trị: chuyến thử",
        starts_on: "2026-09-07",
        ends_on: "2026-09-08",
        headcount: 2,
        budget_per_person_vnd: 500000,
      },
    });
    console.log(`    tạo chuyến -> ${buoi.status}`);

    /* ---------------------------------------------- 4. đổi vai trò */
    console.log("\n## 4. PUT .../members/{person_id}/role từ nút trên màn");
    await moLai(page, server.url + "#vao=quan-tri&nguoi=minh", coChu, "Quản trị nhóm");
    await page.waitFor(coChu, { label: "roster có Trang", timeout: 40000 }, "Trang");
    can("roster hiện tên người thật do máy chủ trả về", true, "thấy 'Trang'");

    // The control is gated on the DATABASE row, not on the header the app
    // writes for itself (`laQuanTri` reads the roster). So the assertion is
    // that what is on screen matches what the server says about this person --
    // stated as an equivalence rather than as "the button is there", which
    // would be a different claim on a re-run where the person came back as a
    // plain member. That is not hypothetical: it is what the previous run of
    // this file produced, and the screen was right both times.
    const truoc = await api("GET", `/contexts/${contextId}/members`, {
      actor: MINH,
      contexts: contextId,
    });
    const toiLaAdmin =
      truoc.body.members.find((m) => m.person_id === MINH)?.role === "admin";
    const soNutVaiTro = await page.evaluate(
      () =>
        [...document.querySelectorAll('[role="button"]')].filter((e) =>
          ["Đặt làm quản trị", "Bỏ quyền quản trị"].includes((e.textContent || "").trim()),
        ).length,
    );
    can(
      "nút đổi vai trò chỉ hiện đúng khi máy chủ nói mình là quản trị nhóm này",
      toiLaAdmin === soNutVaiTro > 0,
      `roster nói admin=${toiLaAdmin}, trên màn có ${soNutVaiTro} nút`,
    );

    if (!toiLaAdmin) {
      // Put the acting person back where the rest of this walk needs them.
      // Done through the product's own route, by somebody the product says may
      // do it -- never by editing a row.
      const admin = truoc.body.members.find(
        (m) => m.role === "admin" && m.state === "active" && m.person_id !== MINH,
      );
      if (!admin) throw new Error("không còn quản trị nào để trả lại quyền — dừng");
      const nang = await api("PUT", `/contexts/${contextId}/members/${MINH}/role`, {
        actor: admin.person_id,
        roles: QUYEN_ADMIN,
        contexts: contextId,
        body: { role: "admin" },
      });
      console.log(`    trả lại quyền quản trị cho người đang bấm -> ${nang.status}`);
      await moLai(page, server.url + "#vao=quan-tri&nguoi=minh", coChu, "Quản trị nhóm");
      await page.waitFor(coChu, { label: "roster đọc lại", timeout: 40000 }, "Thành viên");
    }

    // Ngọc rather than the person doing the pressing: demoting yourself is a
    // legal press and a terrible one to leave behind in a demo database.
    const nhanDaBam = await bamVaiTro(page, "Ngọc");
    const vaiMong = nhanDaBam === "Đặt làm quản trị" ? "admin" : "member";
    console.log(`    bấm "${nhanDaBam}" trên hàng của Ngọc, chờ vai trò -> ${vaiMong}`);
    await page.waitFor(
      coChu,
      { label: "máy chủ xác nhận đổi vai trò", timeout: 25000 },
      vaiMong === "admin" ? "giờ là quản trị viên" : "giờ là thành viên",
    );
    ds = await page.evaluate(goiCua);
    can(
      "PUT /contexts/{id}/members/{pid}/role đã bay đi và trả 200",
      khop(ds, "PUT", new RegExp(`/contexts/${uuid}/members/${uuid}/role$`), 200),
      inGoi(ds).filter((d) => d.includes("/role")).join(" ; ") || "không thấy",
    );
    // Read back the person the button ACTUALLY named, taken out of the URL
    // that was sent. Asserting on a hard-coded person is how this line passed
    // while the press had promoted somebody else: on a re-run Trang is already
    // an admin, so "Trang is admin" is true no matter what the button did.
    const duongPut = ds.find(
      (g) => g.method === "PUT" && new RegExp(`/members/${uuid}/role$`).test(g.url),
    );
    const aiDuocNang = duongPut?.url.match(new RegExp(`/members/(${uuid})/role$`))?.[1];
    const roster = await api("GET", `/contexts/${contextId}/members`, {
      actor: MINH,
      contexts: contextId,
    });
    const nguoiDo = roster.body.members.find((m) => m.person_id === aiDuocNang);
    can(
      "PUT trúng ĐÚNG người mà hàng được bấm nói tới",
      nguoiDo?.display_name === "Ngọc",
      `URL trỏ tới ${nguoiDo?.display_name ?? aiDuocNang}`,
    );
    can(
      "máy chủ đọc lại thấy người đó mang ĐÚNG vai trò nút hứa",
      nguoiDo?.role === vaiMong,
      `${nguoiDo?.display_name ?? aiDuocNang} -> role=${nguoiDo?.role}, nút hứa ${vaiMong}`,
    );

    /* ---------------------------------------------- 5. mời + thu hồi */
    console.log("\n## 5. POST /outings/{id}/invites và .../revoke từ nút trên màn");
    await bam(page, "Tạo link mời");
    await page.waitFor(
      coChu,
      { label: "link mời hiện ra", timeout: 25000 },
      "Đã tạo lời mời bằng link",
    );
    ds = await page.evaluate(goiCua);
    can(
      "POST /outings/{id}/invites trả 201",
      khop(ds, "POST", new RegExp(`/outings/${uuid}/invites$`), 201),
      inGoi(ds).filter((d) => d.includes("/invites")).join(" ; ") || "không thấy",
    );
    const coLink = await page.evaluate(() => /#moi=[\w-]{20,}/.test(document.body.innerText));
    can("đường dẫn mời có token hiện trên màn", coLink);

    await bam(page, "Thu hồi");
    await page.waitFor(coChu, { label: "thu hồi xong", timeout: 25000 }, "Đã thu hồi lời mời");
    ds = await page.evaluate(goiCua);
    can(
      "POST /outings/{id}/invites/{iid}/revoke trả 200",
      khop(ds, "POST", new RegExp(`/outings/${uuid}/invites/${uuid}/revoke$`), 200),
      inGoi(ds).filter((d) => d.includes("revoke")).join(" ; ") || "không thấy",
    );
    const daThuHoi = await page.evaluate(() => document.body.innerText.includes("Đã thu hồi"));
    can("thẻ lời mời đổi sang 'Đã thu hồi'", daThuHoi);

    /* ---------------------------------------------- 6. rời nhóm */
    console.log("\n## 6. DELETE .../members/{person_id} — chỉ trên hàng của chính mình");
    const nhanNut = await page.evaluate(() =>
      [...document.querySelectorAll('[role="button"]')].map((e) => (e.textContent || "").trim()),
    );
    can(
      "chỉ có MỘT nút 'Rời nhóm' dù roster có hai người",
      nhanNut.filter((n) => n === "Rời nhóm").length === 1,
      `đếm được ${nhanNut.filter((n) => n === "Rời nhóm").length}`,
    );
    can(
      "không có nút nào nhận là xoá thành viên khác",
      !nhanNut.some((n) => /xo[áa]\s*th[àa]nh vi[êe]n/i.test(n)),
    );
    await bam(page, "Rời nhóm");
    await page.waitFor(coChu, { label: "rời nhóm xong", timeout: 25000 }, "Bạn đã rời nhóm");
    ds = await page.evaluate(goiCua);
    can(
      "DELETE /contexts/{id}/members/{pid} trả 204",
      khop(ds, "DELETE", new RegExp(`/contexts/${uuid}/members/${uuid}$`), 204),
      inGoi(ds).filter((d) => d.startsWith("DELETE")).join(" ; ") || "không thấy",
    );
    const khongDoLai = !(await page.evaluate(() =>
      document.body.innerText.includes("Chỉ thành viên của nhóm mới xem được"),
    ));
    can("không in lời từ chối 403 đè lên thông báo đã rời", khongDoLai);

    console.log("\n## toàn bộ lệnh gọi màn này đã bắn");
    for (const d of inGoi(await page.evaluate(goiCua))) console.log("   " + d.replace(API, ""));
  } finally {
    // Runs even when an assertion threw, and that is the point: leaving is the
    // destructive step, and a run that dies after it leaves the demo group
    // without the person the next run signs in as. Measured -- that failure
    // looked exactly like a broken screen for two runs in a row.
    if (contextId) {
      try {
        const cuoi = await api("GET", `/contexts/${contextId}/members`, {
          actor: TRANG,
          contexts: contextId,
        });
        const conTrong =
          cuoi.status === 200 &&
          cuoi.body.members.some((m) => m.person_id === MINH && m.state === "active");
        if (!conTrong && cuoi.status === 200) {
          const admin = cuoi.body.members.find(
            (m) => m.role === "admin" && m.state === "active" && m.person_id !== MINH,
          );
          if (admin) {
            const lai = await api("POST", `/contexts/${contextId}/members`, {
              actor: admin.person_id,
              roles: QUYEN_ADMIN,
              contexts: contextId,
              body: { person_id: MINH },
            });
            if (lai.status === 201) {
              await api("POST", `/memberships/${lai.body.id}/accept`, { actor: MINH });
            }
            await api("PUT", `/contexts/${contextId}/members/${MINH}/role`, {
              actor: admin.person_id,
              roles: QUYEN_ADMIN,
              contexts: contextId,
              body: { role: "admin" },
            });
            console.log(`\n# trả nhóm về chỗ cũ: mời lại -> ${lai.status}`);
          } else {
            console.log("\n# KHÔNG trả lại được: nhóm không còn quản trị nào khác");
          }
        }
      } catch (e) {
        console.log("\n# trả nhóm về chỗ cũ thất bại: " + e.message);
      }
    }
    await page.close();
    await server.close();
  }

  console.log();
  if (hong.length) {
    console.log(`HỎNG ${hong.length} / ĐẠT ${dat}`);
    for (const h of hong) console.log("  - " + h);
    return 1;
  }
  console.log(`ĐẠT ${dat}/${dat}`);
  return 0;
}

main().then(
  (m) => process.exit(m),
  (e) => {
    console.error(e);
    process.exit(1);
  },
);
