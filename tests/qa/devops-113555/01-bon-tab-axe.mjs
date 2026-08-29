/* Bốn tab + các trạng thái tương tác, axe WCAG 2.2 A/AA trên DOM đã render.
 *
 * Bộ rd-fe-11 đã quét bốn tab và ra 0 vi phạm. Bộ này hỏi thêm một câu mà bộ
 * đó không hỏi, và nó là câu quyết định của cả phiếu nợ a11y:
 *
 *   DẢI BẢN ĐỒ CÓ Ở TRÊN MÀN LÚC AXE CHẠY KHÔNG?
 *
 * `aria-prohibited-attr` là rule của 12 chấm bản đồ. Nó chỉ có việc để làm khi
 * 12 chấm đó thật sự đã render. Khám phá lấy dữ liệu từ `GET /places`; route
 * hỏng thì màn rơi vào trạng thái lỗi, dải bản đồ không tồn tại, và con số 0
 * của đúng rule đang được gác là MỘT SỐ 0 RỖNG — không phân biệt được với
 * "đã sửa". Đó đúng là cái bẫy README của rd-fe-11 gọi tên ở mục "số 0 rỗng",
 * và nó đã cắn repo này nhiều lần bằng nhiều hình dạng khác nhau.
 *
 * Nên mỗi lượt quét ở đây phải nói được nó đã NHÌN vào cái gì:
 *   - đúng bundle mình vừa dựng (cổng trên máy này hay bị lane khác chiếm),
 *   - axe còn sống (trồng lỗi, đòi số vi phạm tăng),
 *   - tab đã thật sự đổi (aria-selected), không phải quét một màn bốn lần,
 *   - trên Khám phá: dải bản đồ có mặt và đếm ĐỦ 12 chấm, nếu không thì ĐỎ,
 *   - số rule đã chạy in cạnh danh sách vi phạm rỗng.
 *
 * Cặp đôi của nó là `02-doi-chung-nham-rule.mjs`: xanh ở đây một mình chỉ là
 * một lời khai, vì nó không loại được khả năng bộ đo mù với chính hai rule này.
 *
 *     WEB_URL=http://127.0.0.1:8712 \
 *     EXPECT_BUNDLE=index-<hash>.js node 01-bon-tab-axe.mjs
 */
import AxeBuilder from "@axe-core/playwright";
import { chromium } from "playwright";

const WEB = process.env.WEB_URL;
const BUNDLE = process.env.EXPECT_BUNDLE;
const TAGS = ["wcag2a", "wcag2aa", "wcag22aa"];

if (!WEB) {
  console.error("Thiếu WEB_URL — xem README.md");
  process.exit(2);
}

const browser = await chromium.launch();
const failures = [];
const bang = [];

async function moTrang(hash) {
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    locale: "vi-VN",
  });
  const p = await ctx.newPage();
  p.setDefaultTimeout(20000);
  await p.goto(`${WEB}/index.html${hash}`, { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(3000);
  return p;
}

async function quet(p, nhan) {
  const r = await new AxeBuilder({ page: p }).withTags(TAGS).analyze();
  const nang = r.violations.filter((v) => ["critical", "serious"].includes(v.impact));
  console.log(
    `  ${nhan.padEnd(34)} ${String(r.violations.length).padStart(2)} vi phạm ` +
      `(${nang.length} crit/serious) · ${r.passes.length} rule pass · ${r.incomplete.length} incomplete`,
  );
  for (const v of r.violations) {
    console.log(`      ✗ [${v.impact}] ${v.id} ×${v.nodes.length} — ${v.help}`);
    console.log(`          ${(v.nodes[0]?.html ?? "").slice(0, 160)}`);
  }
  bang.push({ nhan, viPham: r.violations.length, rulePass: r.passes.length, rules: r.violations.map((v) => v.id) });
  return { tong: r.violations.length, rules: r.violations.map((v) => v.id) };
}

// ---- CỔNG 1: đúng bundle của mình không? ---------------------------------
{
  const p = await moTrang("");
  const html = await p.content();
  if (BUNDLE && !html.includes(BUNDLE)) {
    failures.push(`CỔNG BỊ CHIẾM: trang phục vụ không chứa ${BUNDLE}`);
    console.log("\n!! CỔNG BỊ CHIẾM — đang đo trang của người khác");
  } else {
    console.log(`\n✓ bundle khớp: ${BUNDLE ?? "(không ghim — nên ghim)"}`);
  }
  await p.close();
}

// ---- CỔNG 2: ĐỐI CHỨNG — axe còn sống không? -----------------------------
{
  const p = await moTrang("#tab=kham-pha&nguoi=minh");
  console.log("\nĐỐI CHỨNG");
  const truoc = await quet(p, "trước khi trồng lỗi");
  await p.evaluate(() => {
    const img = document.createElement("img");
    img.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='1' height='1'%3E%3C/svg%3E";
    document.body.appendChild(img);
    document.body.appendChild(document.createElement("button"));
  });
  const sau = await quet(p, "sau khi trồng img+button");
  if (sau.tong <= truoc.tong) {
    failures.push(`ĐỐI CHỨNG ĐỎ: axe không bắt được lỗi trồng vào (${truoc.tong} -> ${sau.tong}); mọi số 0 bên dưới là GIẢ`);
  } else {
    console.log(`      ✓ axe còn sống: ${truoc.tong} -> ${sau.tong}, bắt thêm: ${sau.rules.filter((r) => !truoc.rules.includes(r)).join(", ")}`);
  }
  await p.close();
}

// ---- BỐN TAB -------------------------------------------------------------
const MONG_DOI = {
  "kham-pha": "Khám phá",
  "len-plan": "Lên plan",
  "tin-nhan": "Tin nhắn",
  "ca-nhan": "Cá nhân",
};

console.log("\nBỐN TAB (mỗi tab một document mới, có dữ liệu, nguoi=minh)");
for (const tab of Object.keys(MONG_DOI)) {
  const p = await moTrang(`#tab=${tab}&nguoi=minh`);

  // `#tab=` chỉ đọc lúc nạp lần đầu. Không khẳng định lại chỗ này thì cả vòng
  // lặp là một màn quét bốn lần và gọi là bốn tab.
  const st = await p.evaluate(() => {
    const tl = document.querySelector('[role="tablist"]');
    return {
      chon: document.querySelector('[role="tab"][aria-selected="true"]')?.getAttribute("aria-label") ?? null,
      con: tl ? [...tl.children].map((c) => c.getAttribute("role") ?? "(khong role)") : null,
      nutTaoTrongTablist: tl
        ? [...tl.querySelectorAll("*")].some((e) => /Tạo mới|Đóng menu/.test(e.getAttribute("aria-label") ?? ""))
        : null,
    };
  });
  if (!st.chon || !st.chon.startsWith(MONG_DOI[tab])) {
    failures.push(`${tab}: tab đang chọn là ${JSON.stringify(st.chon)}, không phải ${MONG_DOI[tab]}`);
  }
  if (!st.con) failures.push(`${tab}: không tìm thấy role=tablist`);
  else {
    const conXau = st.con.filter((r) => r !== "tab");
    if (conXau.length) failures.push(`${tab}: tablist có con không phải tab: ${JSON.stringify(conXau)}`);
  }
  if (st.nutTaoTrongTablist) failures.push(`${tab}: nút [+] vẫn nằm trong tablist`);

  console.log(`\n  [${tab}] đang chọn=${JSON.stringify(st.chon)} · con-tablist=${JSON.stringify(st.con)}`);

  // Khám phá: rule aria-prohibited-attr chỉ có việc khi 12 chấm ĐANG ở trên màn.
  if (tab === "kham-pha") {
    const map = await p.evaluate(() => {
      const el = [...document.querySelectorAll('[role="img"]')].find((e) =>
        /Sơ đồ vị trí/.test(e.getAttribute("aria-label") ?? ""),
      );
      return {
        coDai: !!el,
        soCham: el ? el.children.length : 0,
        nhan: (el?.getAttribute("aria-label") ?? "").slice(0, 120),
        labelKhongRole: [...document.querySelectorAll("[aria-label]")]
          .filter((e) => !e.getAttribute("role") && !/^(a|button|input|select|textarea|img)$/i.test(e.tagName))
          .map((e) => ({ tag: e.tagName, label: (e.getAttribute("aria-label") ?? "").slice(0, 40) })),
      };
    });
    console.log(`      dải bản đồ: có=${map.coDai} · số chấm=${map.soCham} · nhãn="${map.nhan}…"`);
    console.log(`      aria-label trên phần tử KHÔNG role: ${map.labelKhongRole.length} ${JSON.stringify(map.labelKhongRole).slice(0, 180)}`);
    if (!map.coDai) {
      failures.push(
        "kham-pha: DẢI BẢN ĐỒ KHÔNG RENDER — số 0 của aria-prohibited-attr là số 0 rỗng, " +
          "không phải bằng chứng. Kiểm tra GET /places của API mà bundle đang trỏ tới.",
      );
    } else if (map.soCham !== 12) {
      failures.push(`kham-pha: dải bản đồ chỉ có ${map.soCham} chấm, chờ 12 — rule chưa nhìn đủ`);
    }
    if (map.labelKhongRole.length) {
      failures.push(`kham-pha: còn ${map.labelKhongRole.length} phần tử mang aria-label mà không có role`);
    }
  }

  await quet(p, `axe · ${tab}`);
  await p.close();
}

// ---- TRẠNG THÁI TƯƠNG TÁC: DOM khác, ARIA khác ---------------------------
console.log("\nTRẠNG THÁI TƯƠNG TÁC");
{
  const p = await moTrang("#tab=kham-pha&nguoi=minh");
  await p.getByRole("button", { name: /^Tạo mới$/ }).click();
  await p.waitForTimeout(900);
  const mo = await p.evaluate(() => ({
    expanded: document.querySelector('[aria-expanded="true"]')?.getAttribute("aria-label") ?? null,
  }));
  console.log(`  menu [+] mở: aria-expanded trên ${JSON.stringify(mo.expanded)}`);
  if (!mo.expanded) failures.push("menu [+]: không có phần tử nào aria-expanded=true sau khi mở");
  await quet(p, "axe · menu [+] đang mở");
  await p.close();
}
{
  const p = await moTrang("#tab=kham-pha&nguoi=minh");
  const the = p.getByRole("button", { name: /Tiệm Nướng Xóm Lào/ }).first();
  if (await the.count()) {
    await the.click();
    await p.waitForTimeout(1200);
    await quet(p, "axe · chi tiết địa điểm");
  } else {
    failures.push("không tìm thấy thẻ địa điểm để mở màn chi tiết");
  }
  await p.close();
}

// ---- BẢNG + KẾT LUẬN ------------------------------------------------------
console.log("\n" + "=".repeat(78));
console.log("  " + "trạng thái".padEnd(34) + "vi phạm  rule-pass  rule vi phạm");
for (const r of bang) {
  console.log(
    "  " + r.nhan.padEnd(34) + String(r.viPham).padStart(6) + String(r.rulePass).padStart(11) + "  " + (r.rules.join(", ") || "—"),
  );
}
if (failures.length) {
  console.log(`\n01-bon-tab-axe: FAIL — ${failures.length} vấn đề:`);
  for (const f of failures) console.log("  ✗ " + f);
} else {
  console.log("\n01-bon-tab-axe: PASS — và mỗi số 0 ở trên đã nói được nó nhìn vào cái gì.");
}
await browser.close();
process.exit(failures.length ? 1 : 0);
