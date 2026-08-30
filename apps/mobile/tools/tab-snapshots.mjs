/** Snapshot the tab screens the organiser walk never reaches.
 *
 * `screen-snapshots.mjs` drives the expense flow -- camera to settlement --
 * and that is half the demo. The other half is the shell: Khám phá, Lên plan,
 * Tin nhắn, Cá nhân. `navigation/lien-ket.ts` was written precisely so those could be
 * reached by a URL, and its own header says why:
 *
 *     Every automated check of a screen -- the anti-pattern detector, a
 *     screenshot diff, an accessibility pass -- loads a URL cold and gets
 *     whatever the app opens on. Four of the five tabs were unreachable to
 *     all of them.
 *
 * The fragment landed; nothing ever used it to produce a scannable file. So
 * the four screens the demo actually opens on had never been through the
 * detector at all, while the eight expense screens had been through it
 * repeatedly. This file closes that gap and nothing more.
 *
 * Two things it deliberately reuses rather than reimplements, both from
 * `screen-snapshots.mjs`: the CSSOM read-back inside `snapshot` (react-native-web
 * inserts its rules through `sheet.insertRule`, which `outerHTML` does not
 * serialize -- lose them and the scan describes the UA's serif rather than the
 * screen), and `waitForScreen`, which throws when the app is showing an error.
 * That second one is the guard that matters here: a wrong fixture puts a
 * screen into its failure state, and a snapshot of a failure panel filed under
 * `ca-nhan.html` reads to anybody downstream as a scan of Cá nhân.
 *
 * Dev tool, not shipped code. Nothing in the app may import it.
 *
 *     cd apps/mobile && npm run build:check && node tools/tab-snapshots.mjs
 *
 * **Lên plan** used to be excluded here, on the argument that stubbing its
 * `POST /contexts` + outings + recap chain amounted to reimplementing the
 * server. That argument was wrong twice. The chain is two routes past what Tin
 * nhắn already stubs, and the cost of leaving it out was not "less coverage":
 * it was a tab shipping as `kind: "built"` that no detector had ever seen,
 * indistinguishable from a clean one in every report. It is covered now, and
 * `tests/quet-du-tab.test.mjs` fails if a future tab is dropped the same way.
 */
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { fileURLToPath, pathToFileURL } from "node:url";

import puppeteer from "file:///home/lakiet/.claude/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";

import {
  CHROME,
  closeServer,
  createStaticServer,
  listen,
  snapshot,
  waitForScreen,
} from "./screen-snapshots.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.resolve(HERE, "..");

/** Same sentinel `build:check` inlines. The stub keys off this prefix. */
export const API_BASE = "http://api.build-check.invalid";

/** `minh` is one of the seven demo people in `navigation/nhom-demo`. Naming one
 *  in the fragment is the same act as tapping their button on `MoDau`. */
export const NGUOI = "minh";

/**
 * The screens, each with a string that only appears once the screen has its
 * data.
 *
 * The needle is the whole safety mechanism. It has to be text the *loaded*
 * screen prints and the empty, loading and error states do not -- a needle
 * like "Khám phá" appears in the tab bar of every screen including the broken
 * ones, so it would wave through exactly the failure it exists to catch.
 */
export const SCREENS = [
  { step: "kham-pha", tab: "kham-pha", needle: "Tiệm Nướng Xóm Lào" },
  { step: "len-plan", tab: "len-plan", needle: "Đà Lạt cuối tuần" },
  { step: "tin-nhan", tab: "tin-nhan", needle: "Tối nay ăn gì?" },
  { step: "ca-nhan", tab: "ca-nhan", needle: "Giao dịch gần đây" },
];

/**
 * Screens that are reached by a link rather than by a tab.
 *
 * Kept as a second list rather than folded into `SCREENS`, because `SCREENS` is
 * checked against `tabs.ts` by `tests/quet-du-tab.test.mjs` in both directions:
 * every built tab is scanned, and every scanned row is a real tab. Kỷ niệm is
 * not a tab -- it is the `dang-ky-niem` create action, opened with `vao=ky-niem`
 * -- so putting it in `SCREENS` would make that second check fail while
 * teaching nobody anything.
 *
 * Every needle here names text that only the LOADED screen prints. That rule
 * is the whole value of the column and it is easy to break by picking the
 * heading, because on three of these four screens the heading is chrome drawn
 * in every state including the failed one. `Nhom` says so about itself -- "so
 * the way out never depends on the request having succeeded" -- which means
 * "Nhóm của bạn" is on screen when the members call 404s just as loudly as
 * when it succeeds. A needle like that turns the check into a no-op and the
 * scan reports on a refusal panel under the screen's own filename.
 *
 * So: the memory wall waits on the recap heading rather than the wall title,
 * because the title paints as soon as the group id resolves and would wave
 * through an empty wall. Kết bạn waits on "Bạn bè (" because that count only
 * renders once both friend reads have returned. Nhóm waits on "Lập hội mới",
 * the create form, which is honestly what a cold link opens: nothing passes a
 * group into `Nhom` from the fragment, so there is no member list to wait for
 * and claiming otherwise would be describing a screen this URL never shows.
 * Địa điểm waits on "Khoảng giá", which the detail card prints and the list
 * behind it does not.
 */
export const MAN_KHAC = [
  { step: "ky-niem", frag: `vao=ky-niem&nguoi=${NGUOI}`, needle: "Đã đi cùng nhau" },
  { step: "nhom", frag: `vao=nhom&nguoi=${NGUOI}`, needle: "Lập hội mới" },
  { step: "ban-be", frag: `vao=ban-be&nguoi=${NGUOI}`, needle: "Bạn bè (" },
  { step: "dia-diem", frag: `dia-diem=p-1&nguoi=${NGUOI}`, needle: "Khoảng giá" },
  // F01, and the one row here that must NOT name a person. `DangKy` renders
  // from `AppRoot`'s pre-shell branch, which only runs while `boQuaMoDau` is
  // false -- and `nguoi=` alone makes it true. So `vao=dang-ky&nguoi=minh`
  // walks straight past this screen into the default tab and would have
  // scanned Khám phá under the filename `dang-ky`. The frag is bare on
  // purpose; `tests/quet-man-sau-nut.test.mjs` holds that difference so it
  // cannot be "tidied" into consistency with the rows above.
  { step: "dang-ky", frag: "vao=dang-ky", needle: "Vào Rủ Đi" },

  /* rd-fe-33. The two map screens, and the reason they are here at all.
   *
   * `#ban-do=1` and `#ban-do=hen` shipped as URL-reachable in the same change
   * that built these screens, and the commit said so -- but neither step was
   * added to this list, so nothing measured them. Reachable by URL and
   * measured by URL are different claims, and for one merge the first was
   * being read as the second: ~780 lines of new screen, scanned by nothing,
   * under a table that printed a clean row for every screen it did visit.
   *
   * Both needles are loaded-state text, and each says what it proves.
   * "Nhóm hay tụ ở đâu" is the heatmap section heading, which needs `/heatmap`
   * to have returned AND parsed AND held at least one district -- and it is
   * the LAST section on the screen, so it cannot paint until everything above
   * it has laid out. It does not by itself prove the `/map` half loaded; that
   * half draws its own refusal panel independently. The two share one stub
   * block and one 404 fallthrough, so the realistic failure takes both down
   * together, and the els/chars columns move loudly when only one does.
   *
   * Điểm hẹn waits on "Ai xuất phát từ đâu", the origin picker, which renders
   * only in the `co-du-lieu` branch of the `/areas` read. It is honestly what
   * a cold link opens: the result cards need two origins chosen and a button
   * pressed, so they are NOT in this row. That state is scanned separately as
   * `diem-hen-ket-qua` in `quet-tab-url.mjs`; a needle here naming a
   * candidate would be naming text this URL never reaches.
   */
  { step: "ban-do", frag: `ban-do=1&nguoi=${NGUOI}`, needle: "Nhóm hay tụ ở đâu" },
  { step: "diem-hen", frag: `ban-do=hen&nguoi=${NGUOI}`, needle: "Ai xuất phát từ đâu" },
];

/** Every screen this tool visits, tabs and links alike, in one list. */
export function moiMan() {
  return [
    ...SCREENS.map((s) => ({ ...s, frag: `tab=${s.tab}&nguoi=${NGUOI}` })),
    ...MAN_KHAC,
  ];
}

/** One valid place row, the shape `screens/kham-pha/places.ts` validates.
 *
 * Copied from the wire row in `tests/kham-pha.test.mjs` rather than invented,
 * because that parser rejects on every field and a rejection renders the
 * "dữ liệu sai" panel instead of the list. */
function place(over = {}) {
  return {
    id: "p-1",
    name: "Tiệm Nướng Xóm Lào",
    category: "quan-an-local",
    kinds: ["BBQ", "Lào", "Local"],
    rating: 4.7,
    rating_count: 128,
    distance_km: 1.2,
    price_min_vnd: 200000,
    price_max_vnd: 250000,
    address: "27/1 Yersin, P.10, TP. Đà Lạt",
    open_now: true,
    open_hours: "10:00 – 22:30",
    travel_minutes: 25,
    photo_count: 18,
    traits: ["Chill", "View đẹp"],
    group_fit: { min_people: 4, max_people: 10, relation: "Bạn bè" },
    flag: null,
    lat: 11.9404,
    lng: 108.4383,
    match: {
      score: 95,
      source: "ai",
      verdict: "hop",
      reason: "Hợp vì ngân sách và đồ nướng.",
      factors: [],
    },
    ...over,
  };
}

/**
 * Everything the four screens ask the server for, keyed by path shape.
 *
 * Runs inside the page, installed before the app boots. Anything not matched
 * here falls through to the real fetch, which for `api.build-check.invalid`
 * fails to resolve -- so an endpoint this file forgot surfaces as the screen's
 * own error state and is caught by the needle rather than silently rendering
 * half a screen.
 */
export function installTabStubs(apiBase, fixtures) {
  const originalFetch = window.fetch.bind(window);
  window.__snapshotApiLog = [];

  const json = (body, status = 200) =>
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });

  /* ---- hearts and comments hold state, because the wall re-reads (rd-fe-33).
   *
   * A canned answer cannot test this feature. The heart sends POST or DELETE
   * and then asks the wall to re-read itself, and the whole claim being made
   * is that the number coming back moved. A stub that replays the fixture
   * would show 2 hearts before the press and 2 after, and the test would be
   * measuring the fixture instead of the code.
   *
   * Reactions are a set of actor ids rather than a counter, which is what makes
   * a second POST from the same person a 409 the way the contract says instead
   * of silently counting them twice. */
  const timTheoAnh = {};
  const binhLuanTheoAnh = {};
  for (const m of fixtures.kyNiem ?? []) {
    // Seeded so the count the feed already claims is a count this stub can
    // actually produce. `viewer_has_reacted` decides whether the viewer's own
    // id is one of the members, and the rest are anonymous filler ids -- the
    // route never reveals who they are, so they need no identity.
    const nguoiKhac = [];
    const rieng = m.viewer_has_reacted ? 1 : 0;
    for (let i = 0; i < (m.reaction_count ?? 0) - rieng; i += 1) nguoiKhac.push(`khach-${i}`);
    timTheoAnh[m.id] = { nguoiKhac, cuaMinh: m.viewer_has_reacted === true };
    binhLuanTheoAnh[m.id] = (fixtures.binhLuan?.[m.id] ?? []).slice();
  }
  const demTim = (id) =>
    (timTheoAnh[id]?.nguoiKhac.length ?? 0) + (timTheoAnh[id]?.cuaMinh ? 1 : 0);

  window.fetch = async (input, init) => {
    const url = typeof input === "string" ? input : input.url;
    if (!url.startsWith(apiBase)) return originalFetch(input, init);

    const method = (init?.method ?? (typeof input === "string" ? "GET" : input.method) ?? "GET")
      .toUpperCase();
    const route = url.slice(apiBase.length).split("?")[0];
    window.__snapshotApiLog.push(`${method} ${route}`);

    // Khám phá.
    if (route === "/places") {
      return json({ categories: fixtures.categories, places: fixtures.places });
    }

    // Kết bạn reads both directions of the invite list and then the friends
    // list. `route` has already had the query string cut off it, so the two
    // directions arrive here as the same path and have to be told apart on the
    // raw url -- answering one list for both would render the same names under
    // "đã nhận" and "đã gửi", which is a screen that looks populated and says
    // something false about who asked whom.
    if (route.startsWith("/people/") && route.endsWith("/friend-requests")) {
      const ra = url.includes("direction=outgoing");
      return json({ requests: ra ? fixtures.loiMoiRa : fixtures.loiMoiVao });
    }
    if (route.startsWith("/people/") && route.endsWith("/friends")) {
      return json({ friends: fixtures.banBe });
    }

    // Tin nhắn boots through `screens/chat/nhom.ts`: name the person, create
    // the group, add the members, read them back -- then fetch messages.
    if (route.startsWith("/people/") && route.endsWith("/finance")) {
      return json(fixtures.finance);
    }
    if (method === "PUT" && route.startsWith("/people/")) {
      return json({ id: fixtures.personId, display_name: "Minh" });
    }
    if (method === "POST" && route === "/contexts") {
      return json({ id: fixtures.contextId, name: "Hội Đà Lạt" }, 201);
    }
    if (route.endsWith("/members")) {
      if (method === "POST") return json({ ok: true }, 201);
      return json({ members: fixtures.members });
    }
    // Lên plan. The list is what the tab opens on; the recap is a second,
    // separate read for the "đã tiêu" half of the budget line. Both are
    // stubbed because a 404 on either renders a different screen than the one
    // this file claims to snapshot -- the list turns into "Chưa đọc được danh
    // sách chuyến", and the recap turns the budget row into its refusal text.
    // The needle only catches the first of those two.
    if (route.endsWith("/outings")) {
      return json({ context_id: fixtures.contextId, outings: fixtures.outings });
    }
    if (route.endsWith("/recap")) {
      return json(fixtures.recap);
    }
    // rd-fe-25. The memory wall reads this, and posts to it. The GET is what
    // makes the wall show photographs rather than its empty state, and the
    // empty state is what a 404 here would silently produce -- a scan of a
    // wall with nothing on it, filed under the same filename.
    // rd-fe-33's four routes, matched BEFORE the feed below: `/memories/{id}/
    // reactions` also "includes /memories", so the feed's looser test would
    // swallow every one of them and answer a photo list to a heart press.
    const xaHoi = route.match(/\/memories\/([^/]+)\/(reactions|comments)$/);
    if (xaHoi) {
      const [, memoryId, loai] = xaHoi;
      if (!(memoryId in timTheoAnh)) {
        return json({ code: "memory_not_found", detail: "không có ảnh này" }, 404);
      }
      if (loai === "reactions") {
        if (method === "POST") {
          if (timTheoAnh[memoryId].cuaMinh) {
            return json({ code: "already_reacted", detail: "thả rồi" }, 409);
          }
          timTheoAnh[memoryId].cuaMinh = true;
          return json({ memory_id: memoryId, reaction_count: demTim(memoryId) }, 201);
        }
        if (method === "DELETE") {
          if (!timTheoAnh[memoryId].cuaMinh) {
            return json({ code: "reaction_not_found", detail: "chưa thả" }, 404);
          }
          timTheoAnh[memoryId].cuaMinh = false;
          // 204, with NO body. This is the shape that used to reach
          // `response.json()` and throw a raw SyntaxError past every refusal
          // table in `api.ts`; answering 200-with-a-body here would hide that.
          return new Response(null, { status: 204 });
        }
      }
      if (loai === "comments") {
        if (method === "POST") {
          const than = JSON.parse(init?.body ?? "{}");
          const chu = typeof than.body === "string" ? than.body : "";
          if (chu.trim() === "" || chu.length > 2000) {
            return json({ code: "invalid_body", detail: "1..2000" }, 422);
          }
          const moi = {
            id: `moi-${binhLuanTheoAnh[memoryId].length + 1}`,
            memory_id: memoryId,
            author_id: fixtures.personId,
            display_name: "Minh",
            body: chu,
            created_at: "2026-09-07T20:00:00+07:00",
          };
          binhLuanTheoAnh[memoryId].push(moi);
          return json(moi, 201);
        }
        return json({ memory_id: memoryId, comments: binhLuanTheoAnh[memoryId] });
      }
    }
    if (route.includes("/memories")) {
      if (method === "POST") return json(fixtures.kyNiem[0], 201);
      return json({
        context_id: fixtures.contextId,
        memories: fixtures.kyNiem.map((m) =>
          // Live counts overlay the fixture ONLY on rows that carried the
          // social fields to begin with. That is what lets a test strip the
          // three fields and get a server with no hearts table back, which is
          // the exact condition `coTuongTac` keys the buttons off.
          typeof m.reaction_count === "number"
            ? {
                ...m,
                reaction_count: demTim(m.id),
                comment_count: binhLuanTheoAnh[m.id].length,
                viewer_has_reacted: timTheoAnh[m.id].cuaMinh,
              }
            : m,
        ),
        next_cursor: null,
        has_more: false,
      });
    }
    if (route.endsWith("/messages")) {
      if (method === "POST") return json(fixtures.messages[0], 201);
      return json({
        context_id: fixtures.contextId,
        messages: fixtures.messages,
        next_cursor: null,
        has_more: false,
      });
    }

    /* ---- Bản đồ nhóm, nhiệt độ quận, điểm hẹn (rd-fe-33, F43/F44/F45).
     *
     * `/areas` is ungated on the server and is answered the same way here.
     * The other three are group-scoped, and the 404 fallthrough below is
     * exactly what they hit before this block existed: the client reads 404
     * as `chua-co-endpoint` and draws "Máy chủ này chưa có bản đồ nhóm", so
     * both screens rendered a refusal panel. A scan of a refusal panel is
     * short, quiet and scores zero findings, which is why the needle column
     * for these two rows names text only the loaded screen prints.
     *
     * `/meet` is POST and is answered without reading the body. That is a
     * deliberate limit and not an oversight: this stub photographs a screen,
     * it does not re-implement `app/places/meeting.py`. The arithmetic tying
     * origins to distances is the server's, and `tests/ban-do-nhom.test.mjs`
     * is where the client's half of it is held. What this answer has to be is
     * well-formed and stable, so the pixels under measurement are the app's.
     */
    if (route === "/areas") {
      return json(fixtures.khuVuc);
    }
    if (route.endsWith("/map")) {
      return json(fixtures.banDo);
    }
    if (route.endsWith("/heatmap")) {
      return json(fixtures.nhietDo);
    }
    if (method === "POST" && route.endsWith("/meet")) {
      // `origins` is ECHOED from the request, not replayed from the fixture.
      // The server echoes because every kilometre in `travel` is measured from
      // those centroids, and a screen that lists three districts the picker
      // never offered is a screen contradicting itself in the one place a
      // reader would check the arithmetic. `two_origin_inversion` is derived
      // here for the same reason: it is a property of what was sent, and a
      // hardcoded `false` would draw the answer on exactly the run that is
      // supposed to withhold it behind the inversion warning.
      let from = [];
      try {
        from = JSON.parse(init?.body ?? "{}").from_areas ?? [];
      } catch {
        /* no body, or not JSON; an empty origin list is the honest reading */
      }
      const bang = Object.fromEntries(fixtures.khuVuc.map((k) => [k.id, k]));
      const origins = from.map((id) => bang[id]).filter(Boolean);
      const candidates = fixtures.diemHen.candidates.map((ung) => {
        const travel = origins.map((o) => ({ ...o, km: ung.km_theo_khu[o.id] ?? 0 }));
        const kms = travel.map((t) => t.km);
        const r1 = (n) => Math.round(n * 10) / 10;
        return {
          place_id: ung.place_id,
          place_name: ung.place_name,
          category: ung.category,
          address: ung.address,
          lat: ung.lat,
          lng: ung.lng,
          fairness: {
            worst_km: r1(Math.max(0, ...kms)),
            total_km: r1(kms.reduce((a, b) => a + b, 0)),
            spread_km: r1(Math.max(0, ...kms) - Math.min(...(kms.length ? kms : [0]))),
          },
          travel,
        };
      });
      // Ranked on `worst_km`, the same key the server sorts on and the key the
      // screen's "Cân bằng nhất" badge is pinned to the first row by. Leaving
      // the fixture order would put that badge on whichever candidate happens
      // to be written first, which is the badge saying something false.
      candidates.sort((a, b) => a.fairness.worst_km - b.fairness.worst_km);
      return json({
        context_id: fixtures.contextId,
        origins,
        candidates,
        two_origin_inversion: new Set(from).size === 2,
      });
    }

    // Reached only by a route this file does not know about. Answering 404
    // rather than a plausible empty body keeps an unstubbed call loud.
    return json({ detail: `tab-snapshots: unstubbed ${method} ${route}` }, 404);
  };
}

/**
 * Write a real PNG next to the bundle, so one card in the snapshot holds an
 * actual photograph rather than the drawn stand-in.
 *
 * The point is not decoration. Until `ui/Anh.tsx` landed the app rendered no
 * images at all, and the easy way to "add images" is to write an `<Image>`
 * branch that nothing ever reaches: `photo_url` is null on every row the
 * server sends today, so the frame would draw its stand-in forever and a
 * screenshot could not tell a working image path from a dead one. Serving a
 * byte-real PNG to exactly one of the two fixture rows makes the snapshot show
 * both states side by side -- one photo, one stand-in -- which is the only
 * version of this evidence that can fail.
 *
 * Generated at scan time and written into `.expo-build-check`, never
 * committed. The repo guard refuses binaries on sight and it is right to; this
 * is a build artifact in an ignored directory, not an asset.
 *
 * Hand-rolled because there is no image library here and adding one for four
 * chunks would be worse. A PNG is a signature plus length/type/data/CRC
 * chunks; `zlib.crc32` and `zlib.deflateSync` do the two hard parts.
 */
function vietPngThu(file, w = 480, h = 360) {
  const raw = Buffer.alloc(h * (w * 3 + 1));
  let o = 0;
  for (let y = 0; y < h; y++) {
    raw[o++] = 0; // filter: none
    for (let x = 0; x < w; x++) {
      // A warm dusk wash with a lighter horizon band. Deliberately unlike the
      // drawn category marks, so nobody can mistake one for the other in a
      // screenshot.
      const t = (x / w) * 0.55 + (y / h) * 0.45;
      const band = Math.abs(y / h - 0.62) < 0.05 ? 42 : 0;
      raw[o++] = Math.min(255, Math.round(232 - t * 96 + band));
      raw[o++] = Math.min(255, Math.round(122 - t * 44 + band));
      raw[o++] = Math.min(255, Math.round(96 + t * 78 + band));
    }
  }

  const chunk = (type, data) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(zlib.crc32(body) >>> 0);
    return Buffer.concat([len, body, crc]);
  };

  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0);
  ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 2; // colour type: truecolour
  fs.writeFileSync(
    file,
    Buffer.concat([
      Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
      chunk("IHDR", ihdr),
      chunk("IDAT", zlib.deflateSync(raw)),
      chunk("IEND", Buffer.alloc(0)),
    ]),
  );
}

/**
 * Everything the four tabs need on the wire, as one object.
 *
 * Lifted out of `main()` so `quet-tab-url.mjs` can serve the SAME rows to the
 * detector that this file photographs. Two hand-kept copies would drift, and
 * the drift would be invisible in both directions: a scan reporting a screen
 * the snapshot never showed, and a snapshot of a screen nobody scanned.
 */
export function taoFixtures() {
  const contextId = "1aa0be7f-9c3d-4e1a-8b2f-a7c5d9e3f1b6";
  const personId = "2bb1cf8e-7d4a-4f2b-9c3e-b8d6e0f4a2c7";
  // Shared by the outings list and the recap: `LenPlan` keys spend by outing
  // id, so two different ids here would render "chưa tiêu gì" on a trip the
  // recap says has money in it, and nothing would fail.
  const outingId = "8ff7ad4c-9b0e-4d8f-8a7c-b2c0d4e8f6a1";
  const fixtures = {
    contextId,
    personId,
    categories: [
      { id: "quan-an-local", label: "Quán ăn" },
      { id: "cafe", label: "Cafe" },
    ],
    // Six, not two, and the extra four are not filler.
    //
    // Khám phá cuts its grid at `SO_THE_MAC_DINH` (4) and only draws "Xem tất
    // cả" when there is more than that, so a two-row fixture renders a
    // one-line grid with no link -- the lightest shape the screen has. Every
    // number the scanner then reports about that tab is a number about a
    // screen the demo never shows. Six gives the real 2x2, a live expand
    // control, and a second grid state behind it.
    //
    // The rows are copied from `services/api/app/places/catalog.py` rather
    // than invented, including the flags: `hot` and `new` are real values on
    // real catalogue rows, so the ribbons drawn here are ribbons production
    // draws. `p-5` is the shut door and `p-6` is the row with no model answer,
    // which are the two states that must NOT produce a badge. A fixture where
    // every place is open and every place scored 95 cannot tell a screen that
    // suppresses those correctly from one that has never met them.
    //
    // `photo_url` is deliberately absent from all six. `GET /places` has no
    // such field today -- only `photo_count` -- so a fixture that carried one
    // would scan an image path production cannot reach and would report the
    // stand-in frames as solved.
    places: [
      place(),
      place({
        id: "p-2",
        name: "Lẩu Gà Lá É Tao Ngộ",
        kinds: ["Lẩu", "Đặc sản", "Local"],
        rating: 4.5,
        rating_count: 204,
        distance_km: 2.8,
        traits: ["Đông vui", "Giá mềm"],
        match: {
          score: 88,
          source: "ai",
          verdict: "hop",
          reason: "Hợp vì nhóm đông và ăn khuya.",
          factors: [],
        },
      }),
      place({
        id: "p-3",
        name: "Chill Đêm Đà Lạt",
        category: "di-choi-dem",
        kinds: ["Bar", "Rooftop"],
        rating: 4.5,
        rating_count: 112,
        distance_km: 1.8,
        flag: "hot",
        lat: 11.9435,
        lng: 108.4372,
        match: {
          score: 74,
          source: "ai",
          verdict: "tam",
          reason: "Hợp giờ nhưng hơi quá ngân sách.",
          factors: [],
        },
      }),
      place({
        id: "p-4",
        name: "Khu vui chơi DREAMpark",
        category: "vui-choi",
        kinds: ["Giải trí", "Nhiều hoạt động"],
        rating: 4.6,
        rating_count: 118,
        distance_km: 2.3,
        flag: "new",
        lat: 11.9601,
        lng: 108.4498,
        match: {
          score: 69,
          source: "ai",
          verdict: "tam",
          reason: "Vui cho nhóm đông, xa hơn một chút.",
          factors: [],
        },
      }),
      // Shut. `RuyDongCua` takes the one ribbon slot from `flag`, so this row
      // is also the only place that pairing gets exercised.
      place({
        id: "p-5",
        name: "Nướng Ngói Trời Thông",
        kinds: ["BBQ", "Ngoài trời"],
        rating: 4.3,
        rating_count: 76,
        distance_km: 3.4,
        open_now: false,
        flag: "hot",
        lat: 11.9285,
        lng: 108.4451,
        match: {
          score: 55,
          source: "ai",
          verdict: "khong-hop",
          reason: "Tối nay đóng cửa.",
          factors: [],
        },
      }),
      // No model answer at all. `matchLabel` must draw nothing here; a
      // percentage on this card would be the exact lie rd-be-05 forbids.
      place({
        id: "p-6",
        name: "Cà Phê Vợt Hẻm 330",
        category: "cafe",
        kinds: ["Cafe", "Cổ", "Local"],
        rating: 4.5,
        rating_count: 142,
        distance_km: 6.1,
        lat: 10.7935,
        lng: 106.6801,
        match: null,
      }),
    ],
    // Kết bạn, three lists that must differ from each other. All three are
    // non-empty on purpose: each one has an empty-state sentence, and an
    // empty fixture would scan that sentence while the rows -- the avatar
    // frames, the two-button accept/decline pair, the wrapped names -- are
    // the part with layout in it and the part nothing has ever measured.
    //
    // `other_display_name` carries a long Vietnamese name with diacritics
    // rather than "Test User", because the row is a fixed-width strip with a
    // button pair on its right and short ASCII names never reach the edge
    // where it breaks.
    loiMoiVao: [
      {
        id: "9bb8cf5f-1e2a-4c9b-8d6e-a5c3f7b1d9e4",
        requester_id: "3cc2da9f-6e5b-4a3c-8d4f-c9e7f1a5b3d8",
        addressee_id: personId,
        other_person_id: "3cc2da9f-6e5b-4a3c-8d4f-c9e7f1a5b3d8",
        other_display_name: "Nguyễn Thị Hoàng Phượng",
        state: "pending",
        created_at: "2026-08-29T09:00:00Z",
        decided_at: null,
      },
    ],
    loiMoiRa: [
      {
        id: "0cc9da6a-2f3b-4d0c-9e7f-b6d4a8c2e0f5",
        requester_id: personId,
        addressee_id: "4dd3eb0b-7f6c-4b5d-8e6a-d1f9a3b7c5e0",
        other_person_id: "4dd3eb0b-7f6c-4b5d-8e6a-d1f9a3b7c5e0",
        other_display_name: "Trần Quốc Bảo",
        state: "pending",
        created_at: "2026-08-29T10:00:00Z",
        decided_at: null,
      },
    ],
    banBe: [
      {
        person_id: "5ee4fc1c-8a7d-4c6e-9f7b-e2a0b4c8d6f1",
        display_name: "Lê Minh Khoa",
        friends_since: "2026-08-20T08:00:00Z",
      },
      {
        person_id: "6ff5ad2d-9b8e-4d7f-8a8c-f3b1c5d9e7a2",
        display_name: "Phạm Hoàng Anh Thư",
        friends_since: "2026-08-22T08:00:00Z",
      },
    ],
    // `docThanhVien` rejects on every field, and `state` is the one a
    // hand-written fixture forgets: it is not in the display at all, so its
    // absence looks harmless right up until the members call throws and the
    // screen renders "Chưa vào được nhóm" instead of the thread.
    members: [
      {
        id: "6ff5ad2c-3b8e-4d6f-9a7c-f2b0c4d8e6a1",
        context_id: contextId,
        person_id: personId,
        state: "active",
        role: "admin",
      },
      {
        id: "7aa6be3d-2c9f-4e7a-8b8d-a3c1d5e9f7b2",
        context_id: contextId,
        person_id: "3cc2da9f-6e5b-4a3c-8d4f-c9e7f1a5b3d8",
        state: "active",
        role: "member",
      },
    ],
    messages: [
      {
        id: "4dd3eb0a-5f6c-4b4d-9e5a-d0f8a2b6c4e9",
        context_id: contextId,
        author_id: personId,
        kind: "text",
        body: "Tối nay ăn gì?",
        created_at: "2026-08-29T12:00:00Z",
        cursor: "c1",
      },
      {
        id: "5ee4fc1b-4a7d-4c5e-8f6b-e1a9b3c7d5f0",
        context_id: contextId,
        author_id: "3cc2da9f-6e5b-4a3c-8d4f-c9e7f1a5b3d8",
        kind: "text",
        body: "Tao đói rồi, chốt sớm đi.",
        created_at: "2026-08-29T12:01:00Z",
        cursor: "c2",
      },
    ],
    // Two outings so the list renders as a list. One carries a timeline and a
    // finished spend, the other is a bare trip nobody has planned yet: the
    // budget row draws differently for each, and a one-row fixture would only
    // ever exercise whichever branch it happened to land on.
    outings: [
      {
        id: outingId,
        context_id: contextId,
        created_by_id: personId,
        title: "Đà Lạt cuối tuần",
        starts_on: "2026-09-07",
        ends_on: "2026-09-08",
        headcount: 7,
        budget_per_person_vnd: 2_500_000,
        created_at: "2026-08-29T04:00:00Z",
        stops: [
          {
            id: "9cc8da5f-0e1b-4a9c-8d0f-c5e3f7a1b9d4",
            outing_id: outingId,
            position: 0,
            at: "09:30",
            label: "Cà phê sáng",
            place_name: "Cafe Túi Mơ To",
          },
          {
            id: "0dd9eb6a-1f2c-4b0d-9e1a-d6f4a8b2c0e5",
            outing_id: outingId,
            position: 1,
            at: "19:00",
            label: "Ăn tối",
            place_name: "Lẩu Gà Lá É Tao Ngộ",
          },
        ],
      },
      {
        id: "1ee0fc7b-2a3d-4c1e-8f2b-e7a5b9c3d1f6",
        context_id: contextId,
        created_by_id: personId,
        title: "Cắm trại Tà Năng",
        starts_on: "2026-10-03",
        ends_on: "2026-10-04",
        headcount: 5,
        budget_per_person_vnd: 1_200_000,
        created_at: "2026-08-29T05:00:00Z",
        stops: [],
      },
    ],
    // rd-fe-25's wall. Two rows on purpose, and the second one has no
    // `image_url` -- so the snapshot holds the loaded frame and the stand-in
    // frame side by side. A wall where every row is the same state cannot tell
    // a working image path from a dead one.
    //
    // The address is RELATIVE and points at this group, which is the only shape
    // that survives two separate gates: the server pins `image_url` to
    // `/contexts/{uuid}/photos/{uuid}`, and `nguonAnhAnToan` refuses anything
    // not on `EXPO_PUBLIC_API_URL` before an `<Image>` is ever built. An
    // absolute `http://127.0.0.1:<port>/...` would be declined by the second of
    // those and this scan would quietly become decoration.
    // The three social fields are on both rows, and they are set to OPPOSITE
    // states on purpose (rd-fe-33).
    //
    // `viewer_has_reacted` decides which verb the heart sends -- POST on false,
    // DELETE on true -- and a fixture where both rows read the same way
    // exercises exactly one of the two. The first row is the "chưa thả" case
    // and the second is the "đã thả" one, so a single render carries both a
    // hollow heart and a filled one, and pressing either is a different route.
    //
    // Counts differ from each other and from the comment counts, so a component
    // that renders the wrong number of the four still renders A number: 2 and 1
    // are not interchangeable and neither is 1 and 0.
    kyNiem: [
      {
        id: "5dd00000-dddd-4ddd-8ddd-0000d0000001",
        context_id: contextId,
        author_id: personId,
        kind: "photo",
        image_url: `/contexts/${contextId}/photos/5dd00000-dddd-4ddd-8ddd-0000d0000002`,
        caption: "Sáng Đà Lạt, sương chưa tan",
        place_id: null,
        place_name: null,
        lat: null,
        lng: null,
        created_at: "2026-09-07T07:12:00+07:00",
        cursor: "c1",
        reaction_count: 2,
        comment_count: 1,
        viewer_has_reacted: false,
      },
      {
        id: "5dd00000-dddd-4ddd-8ddd-0000d0000003",
        context_id: contextId,
        author_id: personId,
        kind: "photo",
        image_url: `/contexts/${contextId}/photos/5dd00000-dddd-4ddd-8ddd-0000d0000004`,
        caption: null,
        place_id: null,
        place_name: null,
        lat: null,
        lng: null,
        created_at: "2026-09-07T19:40:00+07:00",
        cursor: "c2",
        reaction_count: 1,
        comment_count: 0,
        viewer_has_reacted: true,
      },
    ],
    // Comments that already exist, keyed by the memory they hang under. Only
    // the first photograph has one, which is what makes its `comment_count: 1`
    // a claim the GET can be checked against rather than a number nobody reads.
    binhLuan: {
      "5dd00000-dddd-4ddd-8ddd-0000d0000001": [
        {
          id: "6ee00000-eeee-4eee-8eee-0000e0000001",
          memory_id: "5dd00000-dddd-4ddd-8ddd-0000d0000001",
          author_id: "3cc2d09f-8e5b-4a3c-ad4f-c9e7f1a5b3d8",
          display_name: "Quang Huy",
          body: "Chuyến này vui xỉu luôn",
          created_at: "2026-09-07T08:00:00+07:00",
        },
      ],
    },
    // F34, and only the first outing appears: the recap route lists trips the
    // ledger has money for, so the second one having no entry here is the
    // "chưa tiêu gì" case rather than a gap in the fixture.
    recap: {
      context_id: contextId,
      split_total_vnd: 4_260_000,
      outings: [
        {
          outing_id: outingId,
          title: "Đà Lạt cuối tuần",
          starts_on: "2026-09-07",
          ends_on: "2026-09-08",
          headcount: 7,
          stops: [],
          split_total_vnd: 4_260_000,
          expense_count: 3,
          memory_count: 2,
        },
      ],
    },
    finance: {
      person_id: personId,
      display_name: "Minh",
      spend_vnd: 860000,
      settled_vnd: 500000,
      outstanding_vnd: 360000,
      expense_count: 4,
      group_count: 2,
      movements: [
        {
          obligation_id: "8bb7cf4e-1d0a-4f8b-9c9e-b4d2e6f0a8c3",
          direction: "out",
          amount_vnd: 160000,
          counterparty_id: "3cc2da9f-6e5b-4a3c-8d4f-c9e7f1a5b3d8",
          counterparty_name: "Trang",
          context_id: contextId,
          context_name: "Hội Đà Lạt",
          occasion: "Lẩu gà lá é",
          occurred_at: "2026-08-28T13:00:00Z",
        },
      ],
    },

    /* ---- rd-fe-33. Bản đồ nhóm, nhiệt độ quận, điểm hẹn (F43/F44/F45).
     *
     * Three screens' worth of data, and the field names are the server's, not
     * a convenient paraphrase: `parseBanDoNhom`, `parseNhietDo` and
     * `parseDiemHen` in `screens/kham-pha/ban-do-nhom.ts` read `place_id`,
     * `share_percent`, `two_origin_inversion` and the rest by those exact
     * names and throw on anything missing. A misnamed key here does not
     * degrade quietly -- it renders the "Dữ liệu bản đồ không đúng dạng"
     * panel, the needle check below fails, and the run refuses to report.
     * That is the intended failure: a fixture that has drifted from the
     * schema cannot be mistaken for a screen that has a layout problem.
     *
     * The district ids are the real eight from `app/places/areas.py`, read off
     * that module rather than invented, because `POST /contexts/{id}/meet`
     * answers 422 for an id it does not know and the picker offers exactly
     * what `/areas` returns. Inventing ids here would build a fixture that
     * the real server would reject, which is the drift this stub exists to
     * avoid.
     */
    khuVuc: [
      { id: "da-lat", label: "Đà Lạt", lat: 11.9429, lng: 108.4428 },
      { id: "hcm-quan-1", label: "Quận 1, TP.HCM", lat: 10.7769, lng: 106.7009 },
      { id: "hcm-quan-3", label: "Quận 3, TP.HCM", lat: 10.784, lng: 106.687 },
      { id: "hcm-quan-4", label: "Quận 4, TP.HCM", lat: 10.759, lng: 106.705 },
    ],

    // `unavailable` carries a row on purpose. The "saved" layer is declared
    // rather than served, and `BanDoNhom` draws a card naming it -- an empty
    // array here would photograph a map that quietly has three layers instead
    // of one that says out loud which fourth it does not have.
    banDo: {
      context_id: contextId,
      visited: [
        {
          place_id: "p-1",
          place_name: "Tiệm Nướng Xóm Lào",
          lat: 11.9404,
          lng: 108.4419,
          visit_count: 6,
        },
        {
          place_id: "p-2",
          place_name: "Cà phê Vườn",
          lat: 11.9451,
          lng: 108.4382,
          visit_count: 3,
        },
      ],
      trending: [
        {
          place_id: "p-3",
          place_name: "Lẩu gà lá é Tao Ngộ",
          lat: 11.9388,
          lng: 108.4471,
          rating: 4.6,
          rating_count: 218,
        },
      ],
      recommended: [
        {
          place_id: "p-4",
          place_name: "Bánh căn Nhà Chung",
          lat: 11.9462,
          lng: 108.4395,
          rating: 4.4,
          rating_count: 91,
        },
      ],
      unavailable: [
        { layer: "saved", reason: "Chưa có chỗ nào được lưu, và màn lưu chỗ chưa dựng." },
      ],
      scanned_checkins: 42,
      truncated: false,
    },

    // `unknown_area_count` is not zero, because the sentence disclosing it is
    // a line of copy on the screen and a zero would hide it from every scan.
    nhietDo: {
      context_id: contextId,
      areas: [
        {
          id: "da-lat",
          label: "Đà Lạt",
          lat: 11.9429,
          lng: 108.4428,
          visit_count: 22,
          share_percent: 61,
        },
        {
          id: "hcm-quan-1",
          label: "Quận 1, TP.HCM",
          lat: 10.7769,
          lng: 106.7009,
          visit_count: 9,
          share_percent: 25,
        },
        {
          id: "hcm-quan-3",
          label: "Quận 3, TP.HCM",
          lat: 10.784,
          lng: 106.687,
          visit_count: 5,
          share_percent: 14,
        },
      ],
      resolved_checkins: 36,
      unknown_area_count: 6,
      scanned_checkins: 42,
      truncated: false,
    },

    /* The meeting-point answer, stored as distances PER DISTRICT rather than
     * as a finished `travel` list.
     *
     * The screen prints one leg per origin, and the origins are whatever the
     * picker was driven to choose -- which is not known when this fixture is
     * written. A canned `travel` list would therefore render legs for
     * districts nobody selected, on the one screen whose entire purpose is
     * showing that the distances are fair to the people present. That is a
     * fixture contradicting itself in the exact place a reader checks.
     *
     * So `km_theo_khu` is a lookup, and the stub builds `travel` and
     * `fairness` from it against the origins actually sent. That is arithmetic
     * over a table, not a second copy of `app/places/meeting.py`: no distance
     * is computed here, only selected, summed and ranged. The real geometry
     * stays on the server, where `tests/api/test_areas.py` holds it.
     */
    diemHen: {
      context_id: contextId,
      candidates: [
        {
          place_id: "p-5",
          place_name: "Quán Cơm Niêu Sài Gòn",
          category: "quan-an-local",
          address: "148 Nguyễn Đình Chiểu, Quận 3, TP.HCM",
          lat: 10.7825,
          lng: 106.6889,
          km_theo_khu: { "da-lat": 231.4, "hcm-quan-1": 4.0, "hcm-quan-3": 0.8, "hcm-quan-4": 3.1 },
        },
        {
          place_id: "p-6",
          place_name: "Cà phê Thềm Xưa",
          category: "cafe",
          address: "31 Lê Thánh Tôn, Quận 1, TP.HCM",
          lat: 10.7776,
          lng: 106.7015,
          km_theo_khu: { "da-lat": 233.9, "hcm-quan-1": 0.1, "hcm-quan-3": 4.6, "hcm-quan-4": 2.2 },
        },
      ],
    },
  };
  return fixtures;
}

async function main() {
  const buildDir = path.join(MOBILE_ROOT, ".expo-build-check");
  const outDir = path.join(MOBILE_ROOT, ".screen-snapshots");

  if (!fs.existsSync(path.join(buildDir, "index.html"))) {
    throw new Error(
      `No bundle at ${buildDir}/index.html. Run: cd apps/mobile && npm run build:check`,
    );
  }
  if (!fs.existsSync(CHROME)) throw new Error(`Chromium not found at ${CHROME}`);

  fs.mkdirSync(outDir, { recursive: true });
  for (const { step } of moiMan()) {
    try {
      fs.unlinkSync(path.join(outDir, `${step}.html`));
    } catch (err) {
      if (err.code !== "ENOENT") throw err;
    }
  }

  const fixtures = taoFixtures();

  const server = createStaticServer(buildDir);
  let browser = null;
  try {
    const port = await listen(server);

    // `photo_url` is a RELATIVE path, which is both the shape the photo route
    // actually returns and the only shape the app will now dial: `Anh` refuses
    // any address that is not on `EXPO_PUBLIC_API_URL`, so the old absolute
    // `http://127.0.0.1:<port>/...` would be declined and this card would draw
    // its stand-in -- turning this whole scan back into decoration without
    // changing a line of it. Serving the bytes on the API origin instead keeps
    // the scan honest AND makes it exercise the real resolution path.
    //
    // The first row gets a photograph and the second deliberately does not, so
    // `kham-pha.png` shows the loaded state and the waiting state in one frame.
    const anhThuFile = path.join(buildDir, "anh-thu-dia-diem.png");
    vietPngThu(anhThuFile);
    const anhThuBytes = fs.readFileSync(anhThuFile);
    const anhThuUrl = `${API_BASE}/anh-thu-dia-diem.png`;
    fixtures.places[0].photo_url = "/anh-thu-dia-diem.png";
    browser = await puppeteer.launch({
      executablePath: CHROME,
      headless: true,
      defaultViewport: {
        width: 390,
        height: 844,
        deviceScaleFactor: 2,
        isMobile: true,
        hasTouch: true,
      },
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
    });

    // rd-fe-25. The first wall row's bytes, so the memory grid holds a real
    // photograph. The second row's address is deliberately NOT served, so the
    // same grid also holds the stand-in -- both states in one snapshot.
    const anhKyNiemUrl = API_BASE + fixtures.kyNiem[0].image_url;

    for (const { step, frag, needle } of moiMan()) {
      const page = await browser.newPage();
      page.setDefaultTimeout(30000);
      const pageErrors = [];
      page.on("pageerror", (err) => pageErrors.push(String(err)));

      // The photograph is the one request that does NOT go through the fetch
      // stub: an <Image> loads it itself. `api.build-check.invalid` resolves
      // nowhere on purpose, so it is answered here instead.
      await page.setRequestInterception(true);
      page.on("request", (req) => {
        if (req.url() === anhThuUrl || req.url() === anhKyNiemUrl) {
          req.respond({ status: 200, contentType: "image/png", body: anhThuBytes });
          return;
        }
        req.continue();
      });

      await page.evaluateOnNewDocument(installTabStubs, API_BASE, fixtures);

      // `AppRoot` reads the fragment once, at mount. Navigating from one
      // fragment to another on a live page changes the URL and remounts
      // nothing, so every file after the first would be a copy of the first
      // screen under a different name. A fresh page per screen is what makes
      // the filename true.
      await page.goto(`http://127.0.0.1:${port}/index.html#${frag}`, {
        waitUntil: "domcontentloaded",
      });

      try {
        await waitForScreen(page, step, needle);
      } catch (err) {
        if (pageErrors.length) console.error(`Page errors:\n${pageErrors.join("\n")}`);
        throw err;
      }

      // Assert the photograph decoded, rather than trusting that it did.
      // A refused address, a broken resolution, or an <Image> that quietly
      // stopped rendering all leave a frame that looks exactly like the
      // stand-in state this scan is also supposed to show -- so without this
      // check the two are indistinguishable in the PNG and the scan reports
      // success either way. `naturalWidth > 0` is the browser saying it got
      // real pixels, not merely that an element exists.
      if (step === "kham-pha") {
        const daTai = await page.evaluate(async (src) => {
          const imgs = [...document.querySelectorAll("img")];
          const anh = imgs.find((i) => i.src === src || i.currentSrc === src);
          if (!anh) return { found: false, srcs: imgs.map((i) => i.src).slice(0, 5) };
          if (!anh.complete) await anh.decode().catch(() => {});
          return { found: true, width: anh.naturalWidth, height: anh.naturalHeight };
        }, anhThuUrl);
        if (!daTai.found) {
          throw new Error(
            `kham-pha: khong tim thay <img> cho ${anhThuUrl}. ` +
              `Cong origin tu choi dia chi nay, hoac <Image> khong con render. ` +
              `src dang co: ${JSON.stringify(daTai.srcs)}`,
          );
        }
        if (!daTai.width) {
          throw new Error(`kham-pha: <img> ${anhThuUrl} khong giai ma duoc (naturalWidth=0)`);
        }
        console.log(`  anh dia diem da tai that: ${daTai.width}x${daTai.height}`);
      }

      // rd-fe-25, and the same reasoning one screen over. The memory wall's
      // whole claim is that a photograph reaches the glass; a grid of
      // stand-ins looks identical in a PNG and would report success. So the
      // first row is asserted to have decoded AND the picker is asserted to be
      // on screen -- a wall nobody can add to is not the feature.
      if (step === "ky-niem") {
        const daTai = await page.evaluate(async (src) => {
          const imgs = [...document.querySelectorAll("img")];
          const anh = imgs.find((i) => i.src === src || i.currentSrc === src);
          const nut = [...document.querySelectorAll('[role="button"]')].map(
            (b) => b.getAttribute("aria-label") ?? b.textContent,
          );
          if (!anh) return { found: false, srcs: imgs.map((i) => i.src).slice(0, 5), nut };
          if (!anh.complete) await anh.decode().catch(() => {});
          return { found: true, width: anh.naturalWidth, height: anh.naturalHeight, nut };
        }, anhKyNiemUrl);
        if (!daTai.found) {
          throw new Error(
            `ky-niem: khong tim thay <img> cho ${anhKyNiemUrl}. ` +
              `Cong origin tu choi dia chi nay, hoac tuong anh khong con render. ` +
              `src dang co: ${JSON.stringify(daTai.srcs)}`,
          );
        }
        if (!daTai.width) {
          throw new Error(`ky-niem: <img> ${anhKyNiemUrl} khong giai ma duoc (naturalWidth=0)`);
        }
        const coNutThem = daTai.nut.some((n) => n && n.includes("ảnh"));
        if (!coNutThem) {
          throw new Error(
            `ky-niem: khong co nut chon anh nao tren man. ` +
              `role=button dang co: ${JSON.stringify(daTai.nut)}`,
          );
        }
        console.log(`  anh ky niem da tai that: ${daTai.width}x${daTai.height}, co nut chon anh`);
      }

      await snapshot(page, outDir, step);
      await page.close();
    }

    const missing = moiMan().filter((s) => !fs.existsSync(path.join(outDir, `${s.step}.html`)));
    if (missing.length) {
      throw new Error(`no snapshot written for: ${missing.map((s) => s.step).join(", ")}`);
    }
  } finally {
    if (browser) await browser.close();
    await closeServer(server);
  }
}

// Only when run as the command. `tuong-tac-snapshots.mjs` imports
// `installTabStubs` from here, and a bare `await main()` would make that import
// drive the whole tab suite as a side effect of loading a function.
if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}
