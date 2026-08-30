/** Snapshot the screens that only exist after somebody interacts.
 *
 * `tab-snapshots.mjs` closed the "four of five tabs were unreachable" hole by
 * driving `#tab=...`. It renders each tab in its *opening* state, which is all
 * a fragment can express. Two of this app's screens are not opening states:
 *
 *   * **F12** -- the answer to a typed sentence. Reaching it means typing into
 *     the box and pressing "Tìm bằng AI". No URL produces it.
 *   * **F46** -- the check-in card, which lives on a place's detail.
 *
 * `rd-qa-26` recorded both as unscanned, in the same words this file exists to
 * retire: "F46/F12 ở tầng giao diện: chỉ chạm tầng HTTP, chưa đi bộ bằng trình
 * duyệt, chưa `imp detect`". The HTTP layer was proven by QA; the pixels were
 * never looked at by anything.
 *
 * ## The needle is doing more work here than in `tab-snapshots.mjs`
 *
 * A tab either loaded or it did not. An interaction has a third outcome: the
 * click missed, nothing happened, and the screen is still sitting in its
 * opening state -- which renders perfectly, screenshots cleanly, and is the
 * wrong screen. So every needle here is text that only the *post-interaction*
 * state prints, and `tim-kiem-thay` goes further: its result rows are a place
 * name that is deliberately **absent from `GET /places`**. A file that scanned
 * the catalogue grid while claiming to scan search results cannot then contain
 * the needle.
 *
 * `assertCalled` is the same guard from the other side -- it fails when
 * `POST /places/search` was never sent, which is the shape a silently-disabled
 * submit button takes.
 *
 * ## What `dia-diem.html` does NOT contain, measured rather than assumed
 *
 * `lien-ket.ts` added `dia-diem=` so that "the check-in card lives on a place's
 * detail ... a screen no URL could name" would stop being true. It got half way:
 * the fragment does open the detail card, and this file scans it. But the
 * check-in card inside it renders its **refusal** -- "Chưa có nhóm nào đang mở
 * trong phiên này" -- because `VoTab` holds the group in `useState` and only
 * the "Tạo nhóm" flow ever sets it. A cold URL has no group, so F46's actual
 * card is still reachable by nothing but a hand.
 *
 * The fragment already parses `nhom=<uuid>`, and `VoTab` already receives it
 * and hands it to `KyNiem` -- but not to `KhamPha`. Closing the loop needs the
 * group's *name*, because the card's own sentence is "Ghi lại là nhóm {tên} đã
 * tới {chỗ}", and there is no `GET /contexts/{id}` on the server to read it
 * from. Reported to backend rather than worked around: a made-up group name on
 * a permanent group timeline is worse than a refusal that is at least true.
 *
 * Dev tool, not shipped code. Nothing in the app may import it.
 *
 *     cd apps/mobile && npm run build:check && node tools/tuong-tac-snapshots.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import puppeteer from "puppeteer-core";

import {
  CHROME,
  apiLog,
  closeServer,
  createStaticServer,
  listen,
  snapshot,
  visibleText,
  waitForScreen,
} from "./screen-snapshots.mjs";
import { installTabStubs } from "./tab-snapshots.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.resolve(HERE, "..");

const API_BASE = "http://api.build-check.invalid";
const NGUOI = "minh";

/** One valid place row. Same shape `places.ts` validates -- it rejects on every
 *  field, and a rejection renders the "dữ liệu sai" panel instead of a grid. */
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

/** The place the search returns and the catalogue does not have.
 *
 *  This asymmetry is the point: it is what makes "the search results rendered"
 *  distinguishable from "the opening grid rendered under a filename that says
 *  search". */
const CHI_TRONG_TIM_KIEM = "Nướng Ngói Ba Cây Thông";

const STATES = [
  {
    step: "tim-kiem-thay",
    // F12 answering with places. The needle is the search-only place.
    needle: CHI_TRONG_TIM_KIEM,
    mustCall: "POST /places/search",
    search: {
      source: "ai",
      understood: {
        budget_per_person_vnd: 300000,
        group_size: 6,
        max_distance_km: 5,
        categories: ["quan-an-local"],
        traits: ["Ngoài trời"],
      },
      places: [
        place({
          id: "p-9",
          name: CHI_TRONG_TIM_KIEM,
          traits: ["Ngoài trời", "Chill"],
          match: {
            score: 93,
            source: "ai",
            verdict: "hop",
            reason: "Nướng ngoài trời, đủ chỗ cho 6 người.",
            factors: [],
          },
        }),
      ],
    },
  },
  {
    step: "tim-kiem-khong-thay",
    // The state `tim-kiem.ts` singles out as "not a defect": a model answered,
    // the answer was grounded, and nothing in the catalogue fits. The reading
    // stays on screen precisely so this does not read as a broken feature --
    // which makes it a state worth looking at rather than one worth skipping.
    needle: "không có chỗ nào trong danh mục khớp",
    mustCall: "POST /places/search",
    search: {
      source: "ai",
      understood: {
        budget_per_person_vnd: 30000,
        group_size: 6,
        max_distance_km: null,
        categories: [],
        traits: ["Ngoài trời"],
      },
      places: [],
    },
  },
];

/** Type the sentence and press the button, then wait for the answer. */
async function timBangLoi(page, cau) {
  await page.waitForSelector("input", { timeout: 30000 });
  const o = await page.$("input");
  await o.click();
  await page.keyboard.type(cau, { delay: 8 });

  // Press the button by its label rather than by position: "Tìm bằng AI" is
  // disabled while the box is empty, and clicking a disabled control is a
  // no-op that leaves the opening screen up.
  const bam = await page.evaluate(() => {
    const els = [...document.querySelectorAll('[role="button"], button')];
    const nut = els.find((e) => (e.textContent || "").includes("Tìm bằng AI"));
    if (!nut) return "khong-thay-nut";
    if (nut.getAttribute("aria-disabled") === "true" || nut.disabled) return "nut-bi-khoa";
    nut.click();
    return "ok";
  });
  if (bam !== "ok") throw new Error(`"Tìm bằng AI": ${bam}`);
}

/** Fail when a request the state is defined by never went out.
 *
 *  Without this a search that silently no-ops still produces a file, and the
 *  file still shows a plausible Khám phá. */
async function assertCalled(page, step, route) {
  const calls = await apiLog(page);
  if (!calls.includes(route)) {
    throw new Error(`${step}: ${route} was never sent. Calls: ${calls.join(", ") || "(none)"}`);
  }
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
  const steps = [...STATES.map((s) => s.step), "dia-diem"];
  for (const step of steps) {
    try {
      fs.unlinkSync(path.join(outDir, `${step}.html`));
    } catch (err) {
      if (err.code !== "ENOENT") throw err;
    }
  }

  const contextId = "1aa0be7f-9c3d-4e1a-8b2f-a7c5d9e3f1b6";
  const personId = "2bb1cf8e-7d4a-4f2b-9c3e-b8d6e0f4a2c7";
  const base = {
    contextId,
    personId,
    categories: [
      { id: "quan-an-local", label: "Quán ăn" },
      { id: "cafe", label: "Cafe" },
    ],
    places: [place(), place({ id: "p-2", name: "Lẩu Gà Lá É Tao Ngộ" })],
    members: [],
    messages: [],
    finance: null,
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

    for (const { step, needle, mustCall, search } of STATES) {
      const page = await browser.newPage();
      page.setDefaultTimeout(30000);
      const pageErrors = [];
      page.on("pageerror", (err) => pageErrors.push(String(err)));
      await page.evaluateOnNewDocument(installTabStubs, API_BASE, base);
      // `POST /places/search` is per-state, so it is layered over the shared
      // stub rather than folded into it.
      await page.evaluateOnNewDocument(
        (apiBase, body) => {
          const chain = window.fetch;
          window.fetch = async (input, init) => {
            const url = typeof input === "string" ? input : input.url;
            if (url === `${apiBase}/places/search`) {
              window.__snapshotApiLog.push("POST /places/search");
              return new Response(JSON.stringify(body), {
                status: 200,
                headers: { "Content-Type": "application/json" },
              });
            }
            return chain(input, init);
          };
        },
        API_BASE,
        search,
      );

      await page.goto(`http://127.0.0.1:${port}/index.html#tab=kham-pha&nguoi=${NGUOI}`, {
        waitUntil: "domcontentloaded",
      });
      await waitForScreen(page, step, "Tiệm Nướng Xóm Lào");
      await timBangLoi(page, "quán nướng ngoài trời cho 6 người dưới 300k");

      try {
        await waitForScreen(page, step, needle);
      } catch (err) {
        if (pageErrors.length) console.error(`Page errors:\n${pageErrors.join("\n")}`);
        throw err;
      }
      await assertCalled(page, step, mustCall);
      await snapshot(page, outDir, step);
      await page.close();
    }

    // F46. `lien-ket.ts` added `diaDiem=` so the check-in card could be named
    // by a URL. Whether the card it opens is the check-in card is exactly what
    // has never been looked at, so this step reports the state it landed in
    // rather than assuming one.
    {
      const step = "dia-diem";
      const page = await browser.newPage();
      page.setDefaultTimeout(30000);
      await page.evaluateOnNewDocument(installTabStubs, API_BASE, base);
      await page.goto(
        // `dia-diem`, not `diaDiem`: the parser spells this key in kebab-case
        // while the parsed field is camelCase, and an unrecognised key is
        // dropped rather than guessed at -- so the wrong spelling opens the
        // catalogue grid, silently, which is a scan of the wrong screen.
        `http://127.0.0.1:${port}/index.html#tab=kham-pha&nguoi=${NGUOI}&dia-diem=p-1`,
        { waitUntil: "domcontentloaded" },
      );
      await waitForScreen(page, step, "Khoảng giá");
      await snapshot(page, outDir, step);

      // Which of the card's three states this file actually contains, named
      // out loud. `dia-diem.html` is a scan of the place *detail*; whether the
      // check-in card inside it is the feature or one of its two refusals is
      // the difference between "F46 was scanned" and "F46 was not", and a
      // reader of the filename cannot tell them apart. An unrecognised state
      // fails rather than prints, because the one thing worse than reporting
      // the refusal is reporting nothing while the card quietly changed.
      const text = await visibleText(page);
      const trangThai = text.includes("Chưa biết bạn là ai")
        ? "TU-CHOI: chưa có người"
        : text.includes("Chưa có nhóm nào đang mở")
          ? "TU-CHOI: chưa có nhóm — F46 KHÔNG nằm trong bản chụp này"
          : text.includes("Ghi lại là nhóm")
            ? "THE CHECK-IN THẬT"
            : null;
      if (trangThai === null) {
        throw new Error(
          `${step}: check-in card is in an unrecognised state; ` +
            `update this list before trusting the snapshot.\n${text.slice(0, 600)}`,
        );
      }
      console.log(`\n[${step}] thẻ check-in: ${trangThai}\n`);
      await page.close();
    }

    const missing = steps.filter((s) => !fs.existsSync(path.join(outDir, `${s}.html`)));
    if (missing.length) throw new Error(`no snapshot written for: ${missing.join(", ")}`);
    console.log(`Wrote: ${steps.join(", ")}`);
  } finally {
    if (browser) await browser.close();
    await closeServer(server);
  }
}

await main();
