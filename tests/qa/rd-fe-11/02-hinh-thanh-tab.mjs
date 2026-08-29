/* rd-fe-11 · thanh tab có còn NHÌN như cũ sau khi tách nút [+] ra khỏi tablist.
 *
 * Bản sửa đổi cách dựng thanh: nút [+] không còn là ô thứ ba trong hàng, nó
 * được đặt tuyệt đối đè lên ô giữa. Ngữ nghĩa đúng lên mà bố cục lệch đi thì
 * vẫn là hỏng, và đó là kiểu hỏng axe không bao giờ thấy — axe đọc role, không
 * đọc toạ độ.
 *
 * Nên đo bằng SỐ, không bằng mắt: tâm nút so với tâm màn, đỉnh nút so với mép
 * trên thanh, và bốn tab có còn bấm được ở đúng chỗ chúng vẽ ra không. Ca cuối
 * là quan trọng nhất: một lớp đặt tuyệt đối phủ lên hàng là cách kinh điển để
 * làm chết vùng bấm của thứ nằm dưới, và màn hình vẫn trông hoàn toàn bình
 * thường trong ảnh chụp.
 *
 *     WEB_URL=http://127.0.0.1:PORT ANH=/tmp/x.png node 02-hinh-thanh-tab.mjs
 */
import { chromium } from "playwright";

const WEB = process.env.WEB_URL ?? "http://127.0.0.1:8652";
const ANH = process.env.ANH ?? null;
const NHAN = process.env.NHAN ?? "thanh tab";

const browser = await chromium.launch();
const page = await (
  await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
  })
).newPage();
page.setDefaultTimeout(20000);

await page.goto(`${WEB}/index.html?man=kham-pha`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(1800);

const do_ = await page.evaluate(() => {
  const nut = document.querySelector('[aria-label="Tạo mới"]');
  const tablist = document.querySelector('[role="tablist"]');
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  if (!nut || !tablist) return { thieu: true };
  const r = (el) => {
    const b = el.getBoundingClientRect();
    return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) };
  };
  return {
    nut: r(nut),
    hang: r(tablist),
    tabs: tabs.map((t) => ({ ten: t.getAttribute("aria-label")?.split(" — ")[0], ...r(t) })),
    manRong: document.documentElement.clientWidth,
    // Ai nhận cú chạm ở tâm mỗi tab: nếu lớp [+] phủ lên thì đây ra phần tử khác.
    chamTrungTab: tabs.map((t) => {
      const b = t.getBoundingClientRect();
      const el = document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2);
      return el?.closest('[role="tab"]')?.getAttribute("aria-label")?.split(" — ")[0] ?? "KHÔNG PHẢI TAB";
    }),
    chamTrungNut: (() => {
      const b = nut.getBoundingClientRect();
      const el = document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2);
      return el?.closest('[aria-label="Tạo mới"]') ? "nút [+]" : "KHÔNG PHẢI NÚT";
    })(),
  };
});

if (ANH) {
  await page.screenshot({ path: ANH, clip: { x: 0, y: 844 - 120, width: 390, height: 120 } });
}
await browser.close();

const loi = [];
if (do_.thieu) {
  loi.push("không tìm thấy nút [+] hoặc role=tablist trên trang");
} else {
  const tamNut = do_.nut.x + do_.nut.w / 2;
  const tamMan = do_.manRong / 2;
  // Đo nút so với hàng tab, không so với thẻ cha: bản sửa đổi chính cái cây
  // cha đó, nên một mốc dựa vào nó không so được hai bản với nhau. Đỉnh tab là
  // mốc chung, có ở cả hai bản, và NHO_LEN trong nguồn nói đúng con số này.
  const nhoLen = do_.tabs.length ? do_.tabs[0].y - do_.nut.y : NaN;
  console.log(`\n———— ${NHAN} ————`);
  console.log(`  màn rộng      : ${do_.manRong}`);
  console.log(`  nút [+]       : ${JSON.stringify(do_.nut)}  tâm x=${tamNut} (tâm màn ${tamMan})`);
  console.log(`  nhô trên tab  : ${nhoLen}pt`);
  for (const t of do_.tabs) console.log(`  tab ${String(t.ten).padEnd(10)}: x=${t.x} y=${t.y} w=${t.w} h=${t.h}`);
  console.log(`  chạm tâm tab  : ${JSON.stringify(do_.chamTrungTab)}`);
  console.log(`  chạm tâm [+]  : ${do_.chamTrungNut}`);

  if (Math.abs(tamNut - tamMan) > 1) loi.push(`nút [+] lệch tâm: ${tamNut} ≠ ${tamMan}`);
  if (do_.nut.w !== 54 || do_.nut.h !== 54) loi.push(`nút [+] sai cỡ: ${do_.nut.w}x${do_.nut.h}, phải 54x54`);
  if (nhoLen !== 22) loi.push(`nút [+] nhô ${nhoLen}pt trên đỉnh tab, phải 22pt (NHO_LEN)`);
  if (do_.tabs.length !== 4) loi.push(`đếm được ${do_.tabs.length} tab, phải 4`);
  // Bốn tab chia đều bốn phần năm màn, ô giữa để trống cho nút.
  for (const t of do_.tabs) {
    if (Math.abs(t.w - do_.manRong / 5) > 1) loi.push(`tab ${t.ten} rộng ${t.w}, phải ~${do_.manRong / 5}`);
    if (t.h < 44) loi.push(`tab ${t.ten} cao ${t.h}pt, dưới ngưỡng chạm 44pt`);
  }
  for (const [i, ai] of do_.chamTrungTab.entries()) {
    if (ai !== do_.tabs[i].ten) loi.push(`chạm giữa tab ${do_.tabs[i].ten} lại trúng "${ai}"`);
  }
  if (do_.chamTrungNut !== "nút [+]") loi.push(`chạm giữa nút [+] không trúng nút`);
}

if (loi.length === 0) {
  console.log("\n0 vấn đề bố cục");
  process.exit(0);
}
for (const f of loi) console.log("  ✗ " + f);
process.exit(1);
