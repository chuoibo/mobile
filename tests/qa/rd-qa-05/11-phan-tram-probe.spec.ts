import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * Probe for the main-is-red incident on 43ae65d (#81).
 *
 * The `receipt.test.mjs` guard added by #77 bans percentages by scanning .tsx
 * source. #81 added DaiBanDo.tsx, whose pin coordinates are `left: `${x}%``,
 * and the guard went red on main. This probe answers the question source
 * grepping cannot: what does the user actually SEE on Khám phá?
 *
 * `/places` is routed rather than served by a live API on purpose. The
 * question here is a pure client-render question -- given a known wire
 * payload, what reaches the screen -- so pinning the payload is what makes
 * the answer readable. This is NOT a substitute for the live hero-path run in
 * 02-rehearsal.spec.ts, which still talks to a real API and real Gemini.
 */

const CTX = "1aa00000-aaaa-4aaa-8aaa-0000a0000001";

function place(over: Record<string, unknown>) {
  return {
    id: "p1",
    name: "Quán Nướng Ngói",
    category: "an-uong",
    kinds: ["BBQ", "Local"],
    rating: 4.5,
    rating_count: 120,
    distance_km: 1.2,
    price_min_vnd: 150000,
    price_max_vnd: 250000,
    address: "12 Ngõ Nào Đó",
    open_now: true,
    open_hours: "10:00-22:00",
    travel_minutes: 8,
    photo_count: 3,
    traits: [],
    group_fit: null,
    flag: null,
    lat: 21.03,
    lng: 105.84,
    match: null,
    ...over,
  };
}

/** Three places with distinct coordinates so DaiBanDo draws three pins, and
 *  the first one carries a full AI verdict so `matchLabel` takes the
 *  `AI MATCH ${pct}%` branch -- the exact string #77's guard set out to ban. */
const CATALOGUE = {
  places: [
    place({
      id: "p1",
      name: "Quán Nướng Ngói",
      lat: 21.03,
      lng: 105.84,
      match: {
        score: 95,
        // Keep the two prices out of one string: back to back they form a
        // 12-digit run and the repo guard fails closed on it, correctly.
        reason: "Giá nằm trong ngân sách nhóm, cách 1,2km.",
        source: "ai",
        verdict: "hop",
        factors: [{ label: "Budget", detail: "trong ngưỡng" }],
      },
    }),
    place({
      id: "p2",
      name: "Lẩu Nấm Hồ Tây",
      lat: 21.07,
      lng: 105.81,
      match: {
        score: 72,
        reason: "Hợp số người nhưng hơi xa.",
        source: "ai",
        verdict: "tam",
        factors: [],
      },
    }),
    place({
      id: "p3",
      name: "Bún Chả Hàng Quạt",
      lat: 21.01,
      lng: 105.85,
      match: {
        score: 61,
        reason: "Điểm tính từ ngân sách và khoảng cách.",
        source: "none",
        verdict: null,
        factors: [],
      },
    }),
  ],
  categories: [{ id: "an-uong", label: "Ăn uống" }],
};

async function enterKhamPha(page: Page) {
  await page.route("**/places*", async (route) => {
    await route.fulfill({ json: CATALOGUE });
  });
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.getByRole("button", { name: /Đăng nhập bằng số điện thoại/ }).click();
  await page.getByRole("button", { name: "Vào app với tư cách Minh" }).click();
  await expect(page.getByRole("tablist")).toBeVisible();
  await expect(page.getByText("Quán Nướng Ngói").first()).toBeVisible({ timeout: 30_000 });
}

test("P1 — người dùng thấy phần trăm nào trên Khám phá", async ({ page }) => {
  await enterKhamPha(page);

  const body = await page.locator("body").innerText();
  const withPct = body
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.includes("%"));

  console.log(`  context_id bộ đo ghim: ${CTX}`);
  console.log("  === dòng CHỮ hiện ra có dấu % ===");
  for (const l of withPct) console.log("   ", JSON.stringify(l));
  if (withPct.length === 0) console.log("    (không có dòng nào)");

  // The pins are absolutely positioned with percentage offsets. Read them off
  // the rendered element so the difference between a *style* percentage and a
  // *text* percentage is measured, not argued.
  const pinStyles = await page.evaluate(() => {
    const out: string[] = [];
    for (const el of Array.from(document.querySelectorAll<HTMLElement>("div"))) {
      const s = el.style;
      if (s.position === "absolute" && s.left.endsWith("%") && s.borderRadius) {
        out.push(`left=${s.left} top=${s.top} label=${el.getAttribute("aria-label") ?? "(không có)"}`);
      }
    }
    return out;
  });
  console.log("  === chấm bản đồ: phần trăm nằm trong STYLE, không phải chữ ===");
  for (const p of pinStyles) console.log("   ", p);

  expect(pinStyles.length, "không dựng được chấm bản đồ nào — bộ đo sai, đừng đọc kết luận").toBeGreaterThan(0);
});

test("P2 — axe còn sống, rồi mới đọc vi phạm trên Khám phá", async ({ page }) => {
  await enterKhamPha(page);

  const tags = ["wcag2a", "wcag2aa", "wcag22aa"];
  const before = await new AxeBuilder({ page }).withTags(tags).analyze();
  console.log(`  trước khi trồng lỗi: ${before.violations.length} vi phạm`);
  for (const v of before.violations) {
    console.log(`   [${v.impact}] ${v.id} — ${v.help} (${v.nodes.length} node)`);
    for (const n of v.nodes.slice(0, 3)) console.log("      ", n.html.slice(0, 180));
  }

  await page.evaluate(() => {
    const img = document.createElement("img");
    img.src = "/favicon.ico";
    document.body.appendChild(img); // no alt -> WCAG 1.1.1
  });
  const after = await new AxeBuilder({ page }).withTags(tags).analyze();
  console.log(`  sau khi trồng lỗi:   ${after.violations.length} vi phạm`);
  expect(
    after.violations.length,
    "axe KHÔNG bắt được lỗi trồng sẵn => mọi con số ở trên là giả",
  ).toBeGreaterThan(before.violations.length);
});
