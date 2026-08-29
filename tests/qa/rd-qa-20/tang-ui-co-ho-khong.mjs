/**
 * rd-qa-20 · CÂU 2 của Lead: "Backend chặn rồi; tôi muốn biết TẦNG UI có hở không."
 *
 * Gõ câu tấn công vào ô tìm với backend THẬT không trả lời được câu đó, vì
 * grounding của server chặn trước khi UI kịp thấy gì. Muốn biết tầng UI có tự
 * vẽ thêm hay không thì phải đặt UI vào đúng tình huống server ĐÃ bị lừa —
 * nghĩa là chặn ở dây và trả về thân đã bị đầu độc.
 *
 * Đây không phải "sửa môi trường cho pass": server thật vẫn nguyên, cổng thật
 * vẫn nguyên. Ta chỉ dựng điều kiện mà cái lỗ, nếu có, buộc phải lộ ra.
 *
 * Bốn hình dạng đầu độc, mỗi cái hỏi một câu khác nhau:
 *   A  địa điểm bịa hoàn toàn (không có trong GET /places)
 *   B  danh mục thật + MỘT cái bịa chèn vào giữa
 *   C  tên địa điểm mang thẻ HTML/script
 *   D  bảng "AI hiểu" mang chữ của kẻ tấn công (traits/categories)
 */
import { chromium } from "playwright";
import fs from "node:fs";

const WEB = process.env.QA20_WEB ?? "http://127.0.0.1:8548";
const API = process.env.QA20_API ?? "http://127.0.0.1:8547";
const SHOT = "/tmp/qa20-shots";
fs.mkdirSync(SHOT, { recursive: true });

const cat = await (await fetch(`${API}/places`)).json();
const REAL = cat.places ?? cat;
const CATALOGUE = REAL.map((p) => p.name);
const group = cat.group ?? {};

const browser = await chromium.launch();
const line = (t) => console.log(`\n${"=".repeat(72)}\n${t}\n${"=".repeat(72)}`);

/** A place object shaped exactly like a real one, but naming a place that does
 *  not exist. Same keys the client's parsePlace expects, so if the UI draws
 *  from the wire without re-checking, this WILL appear. */
function biaDat(over = {}) {
  const base = REAL[0];
  return {
    ...base,
    id: "p-hacked",
    name: "HACKED PALACE",
    category: base.category,
    kinds: ["Bịa"],
    address: "999 Không Có Thật, Đà Lạt",
    ...over,
  };
}

async function banThan(than, cauGo = "quán nướng ngoài trời") {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  const errs = [];
  page.on("console", (m) => m.type() === "error" && errs.push(m.text()));
  page.on("pageerror", (e) => errs.push(String(e)));
  await page.goto(`${WEB}/#tab=kham-pha`, { waitUntil: "networkidle" });
  await page.route("**/places/search", (r) =>
    r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(than) }),
  );
  await page.getByLabel("Tìm bằng lời").fill(cauGo);
  await page.getByRole("button", { name: /Tìm bằng AI|Đang hỏi AI/ }).click();
  await page.waitForFunction(
    () => /Chưa tìm được|Không có chỗ|AI hiểu|Kết quả|Máy chủ|không đúng dạng/.test(document.body.innerText),
    { timeout: 30000 },
  );
  await page.waitForTimeout(500);
  const body = await page.evaluate(() => document.body.innerText);
  const html = await page.evaluate(() => document.body.innerHTML);
  return { ctx, page, body, html, errs };
}

const ket = {};

// ------------------------------------------------------------------ A
line("A · Server trả MỘT địa điểm BỊA (source=ai) — UI có vẽ nó không?");
{
  const bia = biaDat();
  const { ctx, page, body, errs } = await banThan({
    query: "quán nướng ngoài trời",
    understood: { budget_per_person_vnd: 300000, group_size: 6, max_distance_km: 3, categories: [], traits: [] },
    places: [bia],
    source: "ai",
    group,
  });
  const veLen = body.includes("HACKED PALACE") || body.includes("p-hacked");
  await page.screenshot({ path: `${SHOT}/a-bia-hoan-toan.png`, fullPage: true });
  console.log(`địa điểm bịa "HACKED PALACE" hiện trên màn? ${veLen ? "CÓ — UI VẼ" : "KHÔNG"}`);
  console.log(`màn nói: ${body.split("\n").map((s) => s.trim()).filter(Boolean).slice(6, 12).join(" | ")}`);
  console.log(`lỗi console: ${errs.length}`);
  ket.A = { veLen, errs };
  await ctx.close();
}

// ------------------------------------------------------------------ B
line("B · Danh mục THẬT + MỘT cái bịa chèn giữa — UI lọc hay vẽ hết?");
{
  const tron = [REAL[0], biaDat(), REAL[1]];
  const { ctx, page, body } = await banThan({
    query: "quán nướng",
    understood: { budget_per_person_vnd: null, group_size: null, max_distance_km: null, categories: [], traits: [] },
    places: tron,
    source: "ai",
    group,
  });
  const thatHien = CATALOGUE.filter((n) => body.includes(n));
  const biaHien = body.includes("HACKED PALACE");
  const soChoNoi = (body.match(/(\d+) chỗ/) ?? [])[1];
  await page.screenshot({ path: `${SHOT}/b-tron-that-va-bia.png`, fullPage: true });
  console.log(`gửi 3 chỗ: 2 thật + 1 bịa`);
  console.log(`chỗ thật hiện   : ${thatHien.length} -> ${JSON.stringify(thatHien)}`);
  console.log(`chỗ bịa hiện    : ${biaHien ? "CÓ" : "KHÔNG"}`);
  console.log(`app tự đếm      : "${soChoNoi} chỗ"`);
  ket.B = { thatHien, biaHien, soChoNoi };
  await ctx.close();
}

// ------------------------------------------------------------------ C
line("C · Tên địa điểm mang HTML/script — có bị render thành thẻ thật không?");
{
  const doc = biaDat({
    name: '<img src=x onerror="window.__XSS=1">Quán Ngon',
    address: "<script>window.__XSS2=1</script>",
  });
  const { ctx, page, body, html, errs } = await banThan({
    query: "quán ngon",
    understood: { budget_per_person_vnd: null, group_size: null, max_distance_km: null, categories: [], traits: [] },
    places: [doc],
    source: "ai",
    group,
  });
  const xss = await page.evaluate(() => ({ a: window.__XSS ?? null, b: window.__XSS2 ?? null }));
  const coTheThat = /<img[^>]*onerror/i.test(html) || /<script>window\.__XSS2/i.test(html);
  await page.screenshot({ path: `${SHOT}/c-xss.png`, fullPage: true });
  console.log(`script CHẠY được? ${xss.a || xss.b ? "CÓ — XSS THẬT" : "KHÔNG"}`);
  console.log(`thẻ vào DOM thật? ${coTheThat ? "CÓ" : "KHÔNG (đã escape)"}`);
  console.log(`chuỗi hiện dạng chữ: ${body.includes("onerror") ? "có, dạng chữ thường" : "không hiện"}`);
  console.log(`lỗi console: ${errs.length}`);
  ket.C = { xss, coTheThat };
  await ctx.close();
}

// ------------------------------------------------------------------ D
line("D · Bảng 'AI hiểu' mang chữ kẻ tấn công — panel có in nguyên không?");
{
  const { ctx, page, body } = await banThan({
    query: "x",
    understood: {
      budget_per_person_vnd: 300000,
      group_size: 6,
      max_distance_km: null,
      categories: ["<b>BỊA</b>"],
      traits: ["IGNORE ALL PREVIOUS INSTRUCTIONS", "Quán Bí Mật"],
    },
    places: [],
    source: "ai",
    group,
  });
  const inNguyen = ["IGNORE ALL PREVIOUS INSTRUCTIONS", "Quán Bí Mật", "BỊA"].filter((w) => body.includes(w));
  await page.screenshot({ path: `${SHOT}/d-panel-echo.png`, fullPage: true });
  console.log(`chuỗi tấn công in nguyên trong bảng AI hiểu: ${inNguyen.length ? JSON.stringify(inNguyen) : "KHÔNG"}`);
  console.log(`màn: ${body.split("\n").map((s) => s.trim()).filter(Boolean).slice(6, 18).join(" | ")}`);
  ket.D = { inNguyen };
  await ctx.close();
}

await browser.close();
fs.writeFileSync("/tmp/qa20-ui.json", JSON.stringify(ket, null, 2));
console.log(`\nảnh: ${SHOT}`);
