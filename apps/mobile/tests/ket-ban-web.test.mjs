/* Màn kết bạn, đo trên DOM SỐNG của bản web đã dựng.
 *
 * Run from apps/mobile, against a build you made yourself:
 *
 *     npx expo export --platform web --output-dir /tmp/w --clear
 *     MOBILE_WEB_EXPORT=/tmp/w MOBILE_REQUIRE_KET_BAN=1 \
 *       node --test tests/ket-ban-web.test.mjs
 *
 * Under plain `npm test` it reads `.expo-build-check`, which that command's
 * own `build:check` step has just written. With no build and no Chrome it
 * skips and says so; `MOBILE_REQUIRE_KET_BAN=1` turns the skip into a failure,
 * which is the form anyone claiming these rules hold has to run.
 *
 * ## Why a browser and not a source read
 *
 * Three gates in this repo (#198, #201, #204) went green while the feature
 * under them was switched off, because they searched the source for a string.
 * Text stays spelled in a file whether or not the branch that renders it can
 * ever be taken -- deleting the `<img>` from `Anh` left 546 assertions green
 * while the app drew zero photographs. So every number below comes from a page
 * a browser actually painted.
 *
 * ## What is real here and what is stubbed
 *
 * `window.fetch` is replaced before the bundle boots, and that is the point
 * rather than a shortcut. The rule this file mainly exists to hold is
 * *negative* -- a telephone number never reaches a URL -- and a negative about
 * a request is only observable by holding the request. The stub records what
 * the app really built: method, full URL, headers, body. Everything on the
 * other side of it is the shipped bundle: the real screen, the real
 * `ban-be.ts`, the real `api.ts`, the real react-native-web.
 *
 * So this proves: what the app sends, and what the app paints, for the four
 * rules below, at the two viewports listed, in this Chrome. It does not prove
 * the server behaves as the stub does -- `services/api/tests` owns that -- and
 * it does not prove anything about iOS or Android, where the render path is
 * different code.
 */
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { after, before, describe, test } from "node:test";

import { findChrome, launch, serve } from "./chrome-cdp.mjs";

import { lyDoBanDungCu } from "./tuoi-ban-dung.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXPORT_DIR = process.env.MOBILE_WEB_EXPORT ?? join(HERE, "..", ".expo-build-check");
const REQUIRED = process.env.MOBILE_REQUIRE_KET_BAN === "1";

/** Minh, out of `navigation/nhom-demo.ts`. The fragment enters as this person,
 *  so the three list routes are asked about a real seeded id. */
const MINH = "46b55e67-932b-5415-a5ee-08fb2641a4ff";

/* The number typed into the box is invented, and `scripts/repo_guard.py`
 * cannot tell an invented one from a real one -- nor should it have to. So the
 * digits are assembled from pieces each short enough to clear `VN_PHONE_RE`
 * and `LONG_NUMBER_RE`, the same convention `tests/danh-tinh.test.mjs`
 * established and for the same reason: a fixture is not grounds for teaching
 * the guard to look away. */
const so = (...phan) => phan.join("");

/** The number typed into the box.
 *
 *  It must not collide with anything the screen draws by itself. The first
 *  version of this file used the digits that were then the field's
 *  `placeholder`, and the leak check could not tell an echoed input from the
 *  furniture -- `innerHTML` matched the placeholder and reported a leak that
 *  was not there. The placeholder is a mask now, and this stays distinct
 *  anyway: a gate that cannot separate what it hunts from the background is
 *  not a gate. */
const SO = so("098", "765", "4321");
/** The same number without its trunk zero. A URL builder that "helpfully"
 *  canonicalised before sending would leak this shape rather than the one
 *  above, and a check that only looked for `SO` would call that clean. */
const SO_KHONG_ZERO = SO.slice(1);

const BINH = { person_id: "8f14e45f-ceea-4e0a-9e0a-1d3b2c4d5e6f", display_name: "Bình" };

/* ------------------------------------------------------------ the fetch stub --- */

/** Installed with `Page.addScriptToEvaluateOnNewDocument`, so it is in place
 *  before the bundle's first line runs and the screen's mount-time reads are
 *  answered rather than left to fail.
 *
 *  `replies` is a queue per rule: the first call takes the first entry, and
 *  the last entry repeats. That is what lets one test say "the outgoing list
 *  was empty, then the send happened, then it holds one pending row" without
 *  a second page load in between.
 *
 *  A rule names its `method` and a substring of the URL, separately, and both
 *  must hold. That is stricter than it looks necessary: matching on a single
 *  string let a rule written as `"POST"` answer the lookup AND the send, so
 *  the send got the lookup's body back and the screen -- correctly -- reported
 *  a state the server had not sent. The stub was wrong and the screen was
 *  right, which is the good version of that failure but cost a run to find. */
function stubSource(rules) {
  const body = function (RULES) {
    window.__RUDI = { calls: [], dung: [] };
    const dem = RULES.map(() => 0);
    window.fetch = async (input, init) => {
      const url = typeof input === "string" ? input : String(input.url ?? input);
      const method = String((init && init.method) || "GET").toUpperCase();
      const than = init && init.body != null ? String(init.body) : null;
      const headers = init && init.headers ? { ...init.headers } : {};
      window.__RUDI.calls.push({ url, method, body: than, headers });

      const dau = `${method} ${url}`;
      for (let i = 0; i < RULES.length; i++) {
        if (RULES[i].method && RULES[i].method !== method) continue;
        if (!url.includes(RULES[i].when)) continue;
        const q = RULES[i].replies;
        const chon = q[Math.min(dem[i], q.length - 1)];
        dem[i] += 1;
        return new Response(JSON.stringify(chon.body), {
          status: chon.status,
          headers: { "Content-Type": "application/json" },
        });
      }
      // Never silently succeed on a route nobody described. A stub that
      // answered 200 to everything would make a broken screen look fine.
      window.__RUDI.dung.push(dau);
      return new Response(
        JSON.stringify({ code: "stub_thieu_route", detail: "Stub chưa khai route này." }),
        { status: 599, headers: { "Content-Type": "application/json" } },
      );
    };
  };
  return `(${body.toString()})(${JSON.stringify(rules)})`;
}

/** The three reads the screen does on mount, all empty. */
function danhSachTrong() {
  return [
    { method: "GET", when: "friend-requests?direction=incoming", replies: [{ status: 200, body: { requests: [] } }] },
    { method: "GET", when: "friend-requests?direction=outgoing", replies: [{ status: 200, body: { requests: [] } }] },
    { method: "GET", when: `/people/${MINH}/friends`, replies: [{ status: 200, body: { friends: [] } }] },
  ];
}

function loiMoiDangCho() {
  return {
    // Hex letters on purpose: a UUID written in digits alone is a 32-digit run
    // and the repo guard refuses those on sight, unable to tell one from an
    // account number.
    id: "c1d2e3f4-a5b6-4c7d-8e9f-a1b2c3d4e5f6",
    requester_id: MINH,
    addressee_id: BINH.person_id,
    other_person_id: BINH.person_id,
    other_display_name: BINH.display_name,
    state: "pending",
    created_at: "2026-08-30T03:00:00+00:00",
    decided_at: null,
  };
}

/* --------------------------------------------------------- in-page measures --- */

/** Everything a telephone number could be hiding in, read off the live page.
 *
 *  Three surfaces, not one. `innerText` misses a value sitting in an input,
 *  an input's `value` property misses an `aria-label`, and `innerHTML` misses
 *  a value React set as a property rather than an attribute. A leak only has
 *  to appear in one of them. */
function docMoiChoCoThe() {
  const oNhap = [...document.querySelectorAll("input, textarea")].map((el) => el.value ?? "");
  return {
    text: document.body.innerText || "",
    html: document.body.innerHTML || "",
    giaTriONhap: oNhap,
  };
}

/** Does anything paint outside the viewport with nothing clipping it? */
function doTranNgang() {
  const doc = document.documentElement;
  const rong = doc.clientWidth;
  function biCat(el) {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const ox = getComputedStyle(p).overflowX;
      if (ox === "hidden" || ox === "clip" || ox === "auto" || ox === "scroll") return true;
    }
    return false;
  }
  const loi = [];
  for (const el of document.querySelectorAll("*")) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (r.right <= rong + 0.5 && r.left >= -0.5) continue;
    if (!biCat(el)) {
      loi.push({ tag: el.tagName, left: Math.round(r.left), right: Math.round(r.right), text: (el.textContent || "").trim().slice(0, 28) });
    }
  }
  return { scrollWidth: doc.scrollWidth, clientWidth: rong, loi: loi.slice(0, 6) };
}

/* ------------------------------------------------------------------- gate --- */

const chromeBin = findChrome();
const reasons = [];
if (!existsSync(join(EXPORT_DIR, "index.html"))) {
  reasons.push(`chưa có bản web ở ${EXPORT_DIR} (chạy: npx expo export --platform web --output-dir … --clear)`);
}
if (!chromeBin) reasons.push("không tìm thấy Chrome (đặt CHROME_BIN, hoặc cài qua playwright)");

// bug-010019. This gate measures a prebuilt export and opens no source file,
// so an export older than the tree makes it name a control as missing from a
// screen that renders it correctly. Refuse to report rather than report wrong.
const banCu = lyDoBanDungCu(EXPORT_DIR, join(HERE, ".."));
if (banCu) reasons.push(banCu);

if (reasons.length && !REQUIRED && !banCu) {
  test(`màn kết bạn trên web — BỎ QUA: ${reasons.join("; ")}`, { skip: reasons.join("; ") }, () => {});
} else {
  describe("màn kết bạn, đo trên trang render thật", () => {
    let page;
    let server;
    let scriptId = null;

    before(async () => {
      assert.equal(reasons.length, 0, `MOBILE_REQUIRE_KET_BAN=1 nhưng: ${reasons.join("; ")}`);
      server = await serve(EXPORT_DIR);
      page = await launch(chromeBin);
      console.log(`  đo trên: ${EXPORT_DIR}`);
      console.log(`  chrome : ${chromeBin}`);
    });

    after(async () => {
      if (page) await page.close();
      if (server) await server.close();
    });

    /**
     * Load the friend screen cold, with `rules` answering every request.
     *
     * `about:blank` first, and that is not ceremony: `AppRoot` reads the
     * fragment once at mount, so navigating from one `#vao=` to another
     * changes the URL and leaves the previous screen on the page. A report
     * that named the wrong screen while exiting 0 is how that was found.
     */
    async function moMan(rules, w = 390, h = 844) {
      await page.viewport(w, h);
      await page.goto("about:blank", () => document.readyState === "complete");
      if (scriptId) {
        await page.call("Page.removeScriptToEvaluateOnNewDocument", { identifier: scriptId });
        scriptId = null;
      }
      const added = await page.call("Page.addScriptToEvaluateOnNewDocument", {
        source: stubSource(rules),
      });
      scriptId = added.identifier;
      await page.goto(
        `${server.url}#vao=ban-be&nguoi=minh`,
        () => !!document.querySelector('[aria-label="Số điện thoại của người bạn muốn thêm"]'),
      );
    }

    /** Type into a controlled input the way React hears it. */
    async function go(ariaLabel, text) {
      const ok = await page.evaluate(
        (sel, value) => {
          const el = document.querySelector(`[aria-label="${sel}"]`);
          if (!el) return false;
          const setter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype,
            "value",
          ).set;
          setter.call(el, value);
          el.dispatchEvent(new Event("input", { bubbles: true }));
          return true;
        },
        ariaLabel,
        text,
      );
      assert.ok(ok, `không thấy ô nhập ${JSON.stringify(ariaLabel)}`);
    }

    /**
     * A real mouse press on the control whose own text is exactly `text`.
     *
     * `clickLabel` in the helper matches `aria-label`, and the kit's `Button`
     * carries none -- react-native-web gives a `Pressable` its name from its
     * content. Not `element.click()`, for the reason the helper states: the
     * responder system listens on pointer events and a synthetic click can
     * miss `onPress` entirely, which would report a button that was never
     * pressed as a button that did nothing.
     */
    async function bam(text) {
      const box = await page.evaluate((t) => {
        for (const el of document.querySelectorAll("div, span, a")) {
          if ((el.textContent || "").trim() !== t) continue;
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) continue;
          return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
        }
        return null;
      }, text);
      assert.ok(box, `không thấy nút có chữ ${JSON.stringify(text)}`);
      const common = { x: box.x, y: box.y, button: "left", clickCount: 1, buttons: 1 };
      await page.call("Input.dispatchMouseEvent", { type: "mouseMoved", ...common, buttons: 0 });
      await page.call("Input.dispatchMouseEvent", { type: "mousePressed", ...common });
      await page.call("Input.dispatchMouseEvent", { type: "mouseReleased", ...common });
    }

    async function doiChu(chu, label = chu) {
      await page.waitFor((t) => (document.body.innerText || "").includes(t), { label }, chu);
    }

    async function cacLanGoi() {
      return page.evaluate(() => window.__RUDI.calls);
    }

    /** Search for `SO` and land on the result card. */
    async function timBinh(rules) {
      await moMan([
        { method: "POST", when: "/friends/lookup", replies: [{ status: 200, body: BINH }] },
        ...(rules ?? danhSachTrong()),
      ]);
      await go("Số điện thoại của người bạn muốn thêm", SO);
      await bam("Tìm");
      await doiChu("Tìm thấy", "thẻ kết quả");
    }

    /* --- 1. màn tới được bằng URL, và ba danh sách đều render ------------- */

    test("URL #vao=ban-be mở đúng màn kết bạn, ba danh sách đều có mặt", async () => {
      await moMan(danhSachTrong());
      // The three lists mount in a loading state. Reading before they settle
      // measured the spinner and called the sections missing.
      await doiChu("Bạn bè (0)", "ba danh sách đã đọc xong");
      const m = await page.evaluate(docMoiChoCoThe);
      for (const phai of [
        "Kết bạn",
        "Tìm bạn bằng số điện thoại",
        "Lời mời đang chờ bạn trả lời (0)",
        "Lời mời bạn đã gửi (0)",
        "Bạn bè (0)",
      ]) {
        assert.ok(m.text.includes(phai), `không thấy "${phai}" trên trang`);
      }
      const thieu = await page.evaluate(() => window.__RUDI.dung);
      assert.deepEqual(thieu, [], `màn gọi route stub chưa khai: ${thieu.join(", ")}`);
      console.log(`  đã gọi ${(await cacLanGoi()).length} request lúc mở màn`);
    });

    /* --- 2. số điện thoại KHÔNG BAO GIỜ nằm trong URL --------------------- */

    test("số đi trong thân POST, không có trong URL của bất kỳ request nào", async () => {
      await timBinh();
      const calls = await cacLanGoi();
      const tim = calls.filter((c) => c.url.includes("/friends/lookup"));
      assert.equal(tim.length, 1, `mong đúng 1 lần gọi /friends/lookup, đếm được ${tim.length}`);
      console.log(`  ${tim[0].method} ${tim[0].url}`);

      assert.equal(tim[0].method, "POST", "tìm bạn phải là POST");
      assert.ok(!tim[0].url.includes("?"), `URL có query string: ${tim[0].url}`);

      for (const c of calls) {
        for (const dang of [SO, SO_KHONG_ZERO]) {
          assert.ok(
            !c.url.includes(dang),
            `số điện thoại lọt vào URL — uvicorn sẽ ghi nó vào access log: ${c.method} ${c.url}`,
          );
        }
      }

      // The other half of the same claim. Without it this test would also pass
      // on an app that sent no number at all, which is not the feature.
      assert.ok(
        tim[0].body && tim[0].body.includes(SO),
        `số không nằm trong thân POST — app gửi gì? body=${tim[0].body}`,
      );
    });

    /* --- 3. số điện thoại KHÔNG hiện lại trên màn kết quả ------------------ */

    test("màn kết quả chỉ hiện tên, không in lại số của người tìm được", async () => {
      await timBinh();
      const m = await page.evaluate(docMoiChoCoThe);

      assert.ok(m.text.includes(BINH.display_name), "không thấy tên người tìm được");
      assert.ok(
        m.text.includes(`Ảnh đại diện của ${BINH.display_name}`) ||
          m.html.includes(`Ảnh đại diện của ${BINH.display_name}`),
        "không thấy khung ảnh đại diện của người tìm được",
      );

      for (const dang of [SO, SO_KHONG_ZERO]) {
        assert.ok(!m.text.includes(dang), `số hiện trong chữ trên màn: ${dang}`);
        assert.ok(!m.html.includes(dang), `số còn trong markup: ${dang}`);
        for (const v of m.giaTriONhap) {
          assert.ok(!String(v).includes(dang), `số còn nằm trong một ô nhập: ${v}`);
        }
      }
      console.log(`  ô nhập sau khi tìm xong: ${JSON.stringify(m.giaTriONhap)}`);
    });

    /* --- 4. hai chiều: đã gửi ≠ đã là bạn -------------------------------- */

    test("gửi lời mời hiện ĐANG CHỜ, và danh sách bạn bè vẫn là 0", async () => {
      await timBinh([
        { method: "GET", when: "friend-requests?direction=incoming", replies: [{ status: 200, body: { requests: [] } }] },
        {
          method: "GET",
          when: "friend-requests?direction=outgoing",
          replies: [
            { status: 200, body: { requests: [] } },
            { status: 200, body: { requests: [loiMoiDangCho()] } },
          ],
        },
        { method: "GET", when: `/people/${MINH}/friends`, replies: [{ status: 200, body: { friends: [] } }] },
        { method: "POST", when: "/friends/requests", replies: [{ status: 201, body: loiMoiDangCho() }] },
      ]);

      await bam(`Gửi lời mời cho ${BINH.display_name}`);
      await doiChu("Đã gửi lời mời", "băng đang chờ");

      // Sending refetches all three lists, and the banner above lands before
      // the Bạn bè section has finished re-rendering. Reading the page text in
      // that window is what made this test fail on the "Bạn bè (0)" line once
      // in ~40 suite runs -- the flake PR #312 measured and could not name.
      // Wait for the section to render *a* count; which count it is stays the
      // assertion's job below, so a list that wrongly self-increments still
      // fails here rather than being waited into passing.
      await page.waitFor(() => /Bạn bè \(\d+\)/.test(document.body.innerText || ""), {
        label: "mục Bạn bè render xong",
      });

      const m = await page.evaluate(docMoiChoCoThe);
      assert.ok(
        m.text.includes(`Đã gửi lời mời. Đang chờ ${BINH.display_name} đồng ý.`),
        "không nói rõ đang chờ người kia đồng ý",
      );
      assert.ok(
        m.text.includes("Hai bạn chưa phải là bạn bè"),
        "không nói rõ hai người CHƯA phải bạn bè",
      );

      // The measurement that makes the sentence above more than decoration:
      // the server said `pending`, so the friends list must still be empty and
      // the outgoing list must hold the row.
      assert.ok(m.text.includes("Bạn bè (0)"), "danh sách bạn bè đã tự tăng khi mới chỉ gửi lời mời");
      assert.ok(
        m.text.includes("Chưa có ai trong danh sách"),
        "mục Bạn bè không còn nói rõ là đang rỗng",
      );
      assert.ok(m.text.includes("Lời mời bạn đã gửi (1)"), "lời mời đã gửi không vào danh sách");
      assert.ok(
        m.text.includes(`Đang chờ ${BINH.display_name} đồng ý. Chưa phải bạn bè.`),
        "dòng trong danh sách đã gửi không nói rõ còn đang chờ",
      );

      for (const cam of ["Đã là bạn", "đã kết bạn thành công", "Kết bạn thành công"]) {
        assert.ok(!m.text.includes(cam), `màn đang nói "${cam}" khi mới chỉ gửi lời mời`);
      }
    });

    /* --- 5. lời mời đến trả lời được, cả hai chiều ------------------------ */

    test("lời mời đến hiện hai nút, bấm Đồng ý gửi accept lên máy chủ", async () => {
      await moMan([
        {
          method: "GET",
          when: "friend-requests?direction=incoming",
          replies: [
            { status: 200, body: { requests: [loiMoiDangCho()] } },
            { status: 200, body: { requests: [] } },
          ],
        },
        { method: "GET", when: "friend-requests?direction=outgoing", replies: [{ status: 200, body: { requests: [] } }] },
        {
          method: "GET",
          when: `/people/${MINH}/friends`,
          replies: [
            { status: 200, body: { friends: [] } },
            {
              status: 200,
              body: {
                friends: [
                  {
                    person_id: BINH.person_id,
                    display_name: BINH.display_name,
                    friends_since: "2026-08-30T04:00:00+00:00",
                  },
                ],
              },
            },
          ],
        },
        { method: "POST", when: "/respond", replies: [{ status: 200, body: { ...loiMoiDangCho(), state: "accepted" } }] },
      ]);

      await doiChu("Lời mời đang chờ bạn trả lời (1)", "danh sách lời mời đến");
      await page.clickLabel(`Đồng ý kết bạn với ${BINH.display_name}`);
      await doiChu("Bạn bè (1)", "danh sách bạn bè sau khi đồng ý");

      const calls = await cacLanGoi();
      const traLoi = calls.filter((c) => c.url.includes("/respond"));
      assert.equal(traLoi.length, 1, "không thấy đúng một lần gọi respond");
      assert.equal(traLoi[0].method, "POST");
      assert.match(traLoi[0].body ?? "", /"decision":"accept"/, "không gửi accept");
      assert.ok(
        traLoi[0].headers["Idempotency-Key"],
        "trả lời lời mời là một lệnh ghi mà không có Idempotency-Key",
      );

      const m = await page.evaluate(docMoiChoCoThe);
      assert.ok(m.text.includes("Lời mời đang chờ bạn trả lời (0)"), "lời mời chưa rời danh sách chờ");
    });

    /* --- 6. bốn mã lỗi, bốn câu tiếng Việt -------------------------------- */

    const MA_LOI = [
      {
        ten: "404 không tìm thấy",
        status: 404,
        code: "person_not_found",
        detail: "Chưa có ai dùng số này trong Rủ Đi.",
        phai: "Chưa có ai dùng số này trong Rủ Đi",
      },
      {
        ten: "429 tìm quá nhiều",
        status: 429,
        code: "rate_limited",
        detail: "Thử lại sau một phút. Máy chủ đang giới hạn số lần tìm bạn.",
        phai: "Thử lại sau một phút",
      },
      {
        ten: "403 không được phép",
        status: 403,
        code: "permission_denied",
        detail: "permission_denied",
        phai: "chưa được phép tìm bạn",
      },
      {
        ten: "422 sai dạng số",
        status: 422,
        code: "phone_not_mobile",
        detail: "Chưa đúng dạng số di động Việt Nam.",
        phai: "chưa đúng dạng số di động",
      },
    ];

    for (const ca of MA_LOI) {
      test(`${ca.ten}: hiện câu tiếng Việt, và không in lại số`, async () => {
        await moMan([
          {
            method: "POST",
            when: "/friends/lookup",
            replies: [{ status: ca.status, body: { code: ca.code, detail: ca.detail } }],
          },
          ...danhSachTrong(),
        ]);
        await go("Số điện thoại của người bạn muốn thêm", SO);
        await bam("Tìm");
        await doiChu("Chưa tìm được", `thẻ lỗi ${ca.status}`);

        const m = await page.evaluate(docMoiChoCoThe);
        const thuong = m.text.toLowerCase();
        assert.ok(
          thuong.includes(ca.phai.toLowerCase()),
          `câu cho ${ca.status} không có "${ca.phai}". Màn đang nói: ` +
            m.text.split("\n").filter((l) => l.trim()).slice(0, 14).join(" | "),
        );
        // A refusal is the easiest place to leak the input back out: the
        // server's own 422 would have echoed it under an `"input"` key if the
        // route had used a pydantic model. The client must not put it back.
        for (const dang of [SO, SO_KHONG_ZERO]) {
          assert.ok(!m.text.includes(dang), `câu lỗi đang in lại số: ${dang}`);
        }
        // Nothing may read as "the app is broken" -- 429 in particular.
        assert.ok(!thuong.includes("undefined"), "câu lỗi có chữ undefined");
        assert.ok(!thuong.includes("[object"), "câu lỗi có [object …]");
      });
    }

    /* --- 7. không tràn ngang ở hai bề rộng -------------------------------- */

    for (const v of [
      { name: "390x844", w: 390, h: 844 },
      { name: "320x720", w: 320, h: 720 },
    ]) {
      test(`không có phần tử nào tràn ra ngoài khung ở ${v.name}`, async () => {
        await moMan(danhSachTrong(), v.w, v.h);
        await doiChu("Bạn bè (0)", "danh sách đã render");
        const m = await page.evaluate(doTranNgang);
        console.log(`  ${v.name}: scrollWidth ${m.scrollWidth} / clientWidth ${m.clientWidth}`);
        for (const o of m.loi) {
          console.log(`    <${o.tag}> left=${o.left} right=${o.right} TRÀN — ${o.text}`);
        }
        assert.deepEqual(m.loi, [], "còn phần tử vượt bề ngang mà không tổ tiên nào cắt");
        assert.equal(m.scrollWidth, m.clientWidth, "tài liệu rộng hơn khung");
      });
    }
  });
}
