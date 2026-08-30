/** The steps of the walk, kept apart from the driver.
 *
 * Split out because the driver is stable and the steps are not: the shape of
 * these screens is what the walk is discovering, so this file changes on every
 * pass while `di-bo.mjs` does not. Each step is a tap a thumb could make.
 */
export default async function buoc({ page, ghi, bam, nghi, ANH, SDT }) {
  // --- phone login ------------------------------------------------------
  // The welcome screen says outright that Google and Apple are shells and that
  // this is the real one. Taking the real one is the point of the walk.
  if (!(await bam(page, "Đăng nhập bằng số điện thoại"))) {
    throw new Error("không tìm thấy nút Đăng nhập bằng số điện thoại");
  }
  await nghi(800);
  await ghi(page, "02-man-so-dien-thoai");

  // The number is supplied by the caller and has no default written here. Repo
  // guard's `vn-phone` rule fails closed on a ten-digit literal in a tracked
  // file, and it is right to: a file cannot tell a synthetic number from a real
  // one, so the safe place for either is outside git. See --sdt in di-bo.mjs.
  await dien(page, "Số điện thoại", SDT);
  await dien(page, "Tên hiển thị", "Minh QA");
  await ghi(page, "03-da-dien-so");

  if (!(await bam(page, "Tiếp tục"))) throw new Error("không bấm được Tiếp tục");
  await nghi(2500);
  await ghi(page, "04-ca-nhan-hoa");

  // --- personalization --------------------------------------------------
  // Tap real choices rather than "Bỏ qua": skipping leaves the profile empty,
  // and an empty profile is the branch that makes the later suggestion screen
  // easy. Choosing is the ordinary path.
  await bam(page, "Ăn uống");
  await bam(page, "Món local");
  await bam(page, "100K–250K");
  await ghi(page, "05-da-chon-so-thich");

  if (!(await bam(page, "Hoàn tất"))) throw new Error("không bấm được Hoàn tất");
  await nghi(3000);
  await ghi(page, "06-vao-vo-tab");

  // --- Khám phá ---------------------------------------------------------
  // The tab lands on a spinner. Waiting for the spinner's OWN words to leave
  // is the check that matters: waiting for the screen's title instead would
  // pass instantly, because the title is already painted behind the spinner.
  await choMat(page, "Đang hỏi máy chủ", 45000);
  await ghi(page, "07-kham-pha-da-tai");

  // --- pick a place -----------------------------------------------------
  if (!(await bam(page, "Tiệm Nướng Xóm Lào"))) {
    throw new Error("không bấm được thẻ địa điểm đầu tiên");
  }
  await nghi(2500);
  await ghi(page, "08-chi-tiet-dia-diem");

  // --- group chat -------------------------------------------------------
  if (!(await bam(page, "Tin nhắn", { chinhXac: true }))) {
    throw new Error("không bấm được tab Tin nhắn");
  }
  await nghi(3000);
  await ghi(page, "09-tab-tin-nhan");

  // Say something a friend would say. The screen promises the AI speaks up on
  // its own once the group is clear enough, so this does NOT address it by
  // name -- naming it would test a different, easier path.
  await dien(page, "Ô nhập tin nhắn", "Tối nay 6 đứa mình đi ăn nướng đi, tầm 250k/người ok không?");
  await bam(page, "Gửi", { chinhXac: true });
  await nghi(9000);
  await ghi(page, "10-da-gui-tin");

  // --- the bill ---------------------------------------------------------
  if (!(await bam(page, "+", { chinhXac: true }))) {
    throw new Error("không bấm được nút + trong khung soạn tin");
  }
  await nghi(1500);
  await ghi(page, "11-menu-dinh-kem");

  // The attach sheet says in its own words that photos are not built yet, so
  // the bill does not enter through "+". It enters through "Tách tiền", the
  // affordance the thread grew after the group talked about money.
  await bam(page, "Ẩn", { chinhXac: true });
  await nghi(600);

  // The bill does not enter through the thread at all: "Tách tiền" on a message
  // reads the message TEXT. The photo flow is behind the "Tạo mới" button in
  // the tab bar, whose first step is `chup-bill`.
  if (!(await bam(page, "Tạo mới", { chinhXac: true }))) {
    throw new Error("không bấm được Tạo mới");
  }
  await nghi(2500);
  await ghi(page, "12-menu-tao-moi");

  if (!(await bam(page, "Tạo khoản chi"))) throw new Error("không bấm được Tạo khoản chi");
  await nghi(3000);
  await ghi(page, "13-chup-bill");

  // --- the photo --------------------------------------------------------
  // Chrome has no camera here and the screen says so, offering the library
  // instead. That is the same seam: both land in `scan()`.
  const [chonFile] = await Promise.all([
    page.waitForFileChooser({ timeout: 20000 }),
    bam(page, "Chọn ảnh bill", { chinhXac: true }),
  ]);
  await chonFile.accept([ANH]);

  // A real model call over a real photograph. Slow on purpose -- rushing this
  // wait is how a walk reports "no items" and blames the product.
  await choMat(page, "Đang", 120000);
  await nghi(1500);
  await ghi(page, "14-ket-qua-quet");

  // --- confirm the reading, then assign --------------------------------
  if (!(await bam(page, "Tiếp tục", { chinhXac: true }))) {
    throw new Error("không bấm được Tiếp tục ở màn kết quả nhận diện");
  }
  await nghi(3500);
  await ghi(page, "15-goi-y-chia");

  // Pick who ate. The screen refuses to split until somebody is chosen, and
  // that refusal is the thing being walked past, not around.
  for (const ai of ["Minh QA", "Trang", "Ngọc"]) {
    if (!(await bam(page, ai))) throw new Error(`không chọn được người ăn: ${ai}`);
  }
  await nghi(1200);
  await ghi(page, "16-da-chon-nguoi-an");

  // The five dish rows are in the DOM but the card looked empty in the shot.
  // Measure rather than argue with a picture: a row painted off its own
  // scroller's bottom edge is invisible to a thumb even though innerText
  // reports it present -- the exact way a screenshot and a text assert can
  // disagree and both be "right".
  const dong = await page.evaluate(() => {
    const ten = ["Cơm tấm sườn bì chả", "Bia Sài Gòn", "Canh chua cá lóc"];
    const out = [];
    for (const t of ten) {
      const el = [...document.querySelectorAll("*")].find(
        (e) => e.children.length === 0 && (e.textContent || "").trim() === t,
      );
      if (!el) {
        out.push({ ten: t, thay: "KHONG CO TRONG DOM" });
        continue;
      }
      const r = el.getBoundingClientRect();
      // Nearest ancestor that actually clips.
      let p = el.parentElement;
      let clip = null;
      while (p) {
        const s = getComputedStyle(p);
        if (s.overflow !== "visible" || s.overflowY !== "visible" || s.overflowX !== "visible") {
          clip = { the: p.tagName, box: p.getBoundingClientRect() };
          break;
        }
        p = p.parentElement;
      }
      out.push({
        ten: t,
        chu: { top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left), w: Math.round(r.width) },
        khungCat: clip
          ? { top: Math.round(clip.box.top), bottom: Math.round(clip.box.bottom), left: Math.round(clip.box.left), right: Math.round(clip.box.right) }
          : null,
        trongKhungNhin: r.top >= 0 && r.bottom <= window.innerHeight && r.width > 0,
      });
    }
    return { cao: window.innerHeight, dong: out };
  });
  console.log(`\n  [đo hình học hàng món] ${JSON.stringify(dong, null, 1)}`);

  // The rows measured below the clip edge. Before calling that "invisible",
  // scroll the way a thumb would and look again: a row you can reach by
  // scrolling is a layout note, a row you cannot reach is a broken screen.
  // `window.scrollTo` moves nothing here: react-native-web scrolls inside its
  // own ScrollView, not the document. So find the real scroller ABOVE the dish
  // row and drive that one; anything else measures the wrong box.
  const cuon = await page.evaluate(() => {
    const el = [...document.querySelectorAll("*")].find(
      (e) => e.children.length === 0 && (e.textContent || "").trim() === "Cơm tấm sườn bì chả",
    );
    if (!el) return { thay: "KHONG CO HANG MON TRONG DOM" };
    const chuoi = [];
    let p = el.parentElement;
    while (p) {
      if (p.scrollHeight > p.clientHeight + 1) {
        chuoi.push({
          the: p.tagName,
          clientH: p.clientHeight,
          scrollH: p.scrollHeight,
          scrollTop: p.scrollTop,
          conLai: p.scrollHeight - p.clientHeight,
        });
      }
      p = p.parentElement;
    }
    return { soKhungCuon: chuoi.length, khung: chuoi.slice(0, 4) };
  });
  console.log(`  [khung cuộn thật quanh hàng món] ${JSON.stringify(cuon, null, 1)}`);

  // Drive the innermost real scroller to the bottom and look again.
  await page.evaluate(() => {
    const el = [...document.querySelectorAll("*")].find(
      (e) => e.children.length === 0 && (e.textContent || "").trim() === "Cơm tấm sườn bì chả",
    );
    if (!el) return;
    let p = el.parentElement;
    while (p) {
      if (p.scrollHeight > p.clientHeight + 1) {
        p.scrollTop = p.scrollHeight;
        break;
      }
      p = p.parentElement;
    }
  });
  await nghi(1200);
  await ghi(page, "16b-cuon-xuong-bang-mon");

  const sau = await page.evaluate(() => {
    const el = [...document.querySelectorAll("*")].find(
      (e) => e.children.length === 0 && (e.textContent || "").trim() === "Cơm tấm sườn bì chả",
    );
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { top: Math.round(r.top), bottom: Math.round(r.bottom), cao: window.innerHeight };
  });
  console.log(`  [hàng món SAU khi cuộn] ${JSON.stringify(sau)}`);

  if (!(await bam(page, "Xem kết quả"))) throw new Error("không bấm được Xem kết quả");
  await nghi(4000);
  await ghi(page, "17-khoan-chi-moi");

  // --- settle -----------------------------------------------------------
  // "Chia tiền" stays disabled until a payer is chosen, and the payer radios
  // sit below the fold behind the pinned button. Scroll to them the way a
  // thumb would; clicking by label alone would hit the participant row of the
  // same name higher up the form.
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await nghi(800);
  await ghi(page, "17b-cuon-toi-ai-tra-truoc");

  if (!(await bamVai(page, "radio", "Minh QA"))) {
    throw new Error("không chọn được người trả trước");
  }
  await nghi(800);

  const tat = await page.evaluate(() => {
    const b = [...document.querySelectorAll("button, [role=button]")].find((e) =>
      (e.innerText || "").trim().includes("Chia tiền"),
    );
    return b ? { tat: b.disabled === true || b.getAttribute("aria-disabled") === "true" } : null;
  });
  console.log(`  [nút Chia tiền sau khi chọn người trả trước] ${JSON.stringify(tat)}`);

  if (!(await bam(page, "Chia tiền", { chinhXac: true }))) {
    throw new Error("không bấm được Chia tiền");
  }
  await nghi(6000);
  await ghi(page, "18-xem-truoc-chia");

  // Confirm into the ledger. Until this, nothing is written -- which is why
  // Cá nhân reads 0đ on a walk that stops one tap earlier, and why a report
  // that stopped there would have blamed the balance screen for it.
  if (!(await bam(page, "Đúng rồi, ghi vào sổ"))) {
    throw new Error("không bấm được Đúng rồi, ghi vào sổ");
  }
  await nghi(6000);
  await ghi(page, "18b-da-ghi-so");

  // --- Cá nhân: Còn nhận / Còn phải trả --------------------------------
  await bam(page, "← Đóng");
  await nghi(1500);
  if (!(await bam(page, "Cá nhân", { chinhXac: true }))) {
    throw new Error("không bấm được tab Cá nhân");
  }
  await nghi(4000);
  await ghi(page, "19-tab-ca-nhan");
}

/** Click by label WITHIN one role. The same name appears twice on the expense
 *  form -- once as a participant row, once as a payer radio -- so a label-only
 *  click lands on whichever comes first in the document, which is the wrong
 *  one. */
async function bamVai(page, vai, nhan) {
  const box = await page.evaluate(
    (v, n) => {
      const e = [...document.querySelectorAll(`[role=${v}]`)].find((x) =>
        (x.innerText || x.getAttribute("aria-label") || "").trim().includes(n),
      );
      if (!e) return null;
      e.scrollIntoView({ block: "center" });
      const r = e.getBoundingClientRect();
      return r.width > 0 ? { x: r.x + r.width / 2, y: r.y + r.height / 2 } : null;
    },
    vai,
    nhan,
  );
  if (!box) return false;
  await page.mouse.click(box.x, box.y);
  await new Promise((r) => setTimeout(r, 800));
  return true;
}

/** Wait for a string to LEAVE the page. */
async function choMat(page, chu, hanMs) {
  const het = Date.now() + hanMs;
  while (Date.now() < het) {
    const con = await page.evaluate(
      (c) => (document.body ? document.body.innerText.includes(c) : true),
      chu,
    );
    if (!con) return;
    await new Promise((r) => setTimeout(r, 700));
  }
  throw new Error(`sau ${hanMs}ms màn hình vẫn còn "${chu}"`);
}

/** Type into the field carrying a label, the way a thumb would: focus by
 * clicking the box, then send keystrokes. Setting `.value` directly skips the
 * change handlers React binds, so a screen can look filled and submit empty.
 *
 * Matches placeholder OR aria-label: react-native-web renders `placeholder` on
 * some fields and only `aria-label` on others, and a matcher that knows one of
 * the two reports a field as absent when it is on screen. */
async function dien(page, nhan, giaTri) {
  const box = await page.evaluate((ph) => {
    const e = [...document.querySelectorAll("input, textarea")].find(
      (x) =>
        (x.placeholder || "").includes(ph) ||
        (x.getAttribute("aria-label") || "").includes(ph),
    );
    if (!e) return null;
    e.scrollIntoView({ block: "center" });
    const r = e.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  }, nhan);
  if (!box) throw new Error(`không có ô nhập nào có nhãn chứa "${nhan}"`);
  await page.mouse.click(box.x, box.y);
  await page.keyboard.type(giaTri, { delay: 30 });
  await new Promise((r) => setTimeout(r, 300));
}
