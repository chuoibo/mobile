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
const API_BASE = "http://api.build-check.invalid";

/** `minh` is one of the seven demo people in `navigation/nhom-demo`. Naming one
 *  in the fragment is the same act as tapping their button on `MoDau`. */
const NGUOI = "minh";

/**
 * The screens, each with a string that only appears once the screen has its
 * data.
 *
 * The needle is the whole safety mechanism. It has to be text the *loaded*
 * screen prints and the empty, loading and error states do not -- a needle
 * like "Khám phá" appears in the tab bar of every screen including the broken
 * ones, so it would wave through exactly the failure it exists to catch.
 */
const SCREENS = [
  { step: "kham-pha", tab: "kham-pha", needle: "Tiệm Nướng Xóm Lào" },
  { step: "len-plan", tab: "len-plan", needle: "Đà Lạt cuối tuần" },
  { step: "tin-nhan", tab: "tin-nhan", needle: "Tối nay ăn gì?" },
  { step: "ca-nhan", tab: "ca-nhan", needle: "Giao dịch gần đây" },
];

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
    if (route.endsWith("/messages")) {
      if (method === "POST") return json(fixtures.messages[0], 201);
      return json({
        context_id: fixtures.contextId,
        messages: fixtures.messages,
        next_cursor: null,
        has_more: false,
      });
    }

    // Reached only by a route this file does not know about. Answering 404
    // rather than a plausible empty body keeps an unstubbed call loud.
    return json({ detail: `tab-snapshots: unstubbed ${method} ${route}` }, 404);
  };
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
  for (const { step } of SCREENS) {
    try {
      fs.unlinkSync(path.join(outDir, `${step}.html`));
    } catch (err) {
      if (err.code !== "ENOENT") throw err;
    }
  }

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
    places: [
      place(),
      place({
        id: "p-2",
        name: "Lẩu Gà Lá É Tao Ngộ",
        rating: 4.5,
        distance_km: 2.4,
        traits: ["Đông vui", "Giá mềm"],
        match: {
          score: 88,
          source: "ai",
          verdict: "hop",
          reason: "Hợp vì nhóm đông và ăn khuya.",
          factors: [],
        },
      }),
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
  };

  const server = createStaticServer(buildDir);
  let browser = null;
  try {
    const port = await listen(server);
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

    for (const { step, tab, needle } of SCREENS) {
      const page = await browser.newPage();
      page.setDefaultTimeout(30000);
      const pageErrors = [];
      page.on("pageerror", (err) => pageErrors.push(String(err)));
      await page.evaluateOnNewDocument(installTabStubs, API_BASE, fixtures);

      // `AppRoot` reads the fragment once, at mount. Navigating from one
      // fragment to another on a live page changes the URL and remounts
      // nothing, so every file after the first would be a copy of the first
      // screen under a different name. A fresh page per screen is what makes
      // the filename true.
      await page.goto(`http://127.0.0.1:${port}/index.html#tab=${tab}&nguoi=${NGUOI}`, {
        waitUntil: "domcontentloaded",
      });

      try {
        await waitForScreen(page, step, needle);
      } catch (err) {
        if (pageErrors.length) console.error(`Page errors:\n${pageErrors.join("\n")}`);
        throw err;
      }
      await snapshot(page, outDir, step);
      await page.close();
    }

    const missing = SCREENS.filter((s) => !fs.existsSync(path.join(outDir, `${s.step}.html`)));
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
