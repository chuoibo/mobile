/** Match the walk's output against the 21 screens of the product mockup set.
 *
 * `do-canh-21-man.mjs` presses its way around the app and writes down every
 * screen it stood on, without deciding what any of them were. This file does
 * the deciding, and it is a separate file for that reason: a walk that knows
 * what it is looking for finds it, and a walk that finds what it expected has
 * measured its author.
 *
 * The 21 rows are the mockup set at
 * `/home/lakiet/mobile/product/RuDi_Mobile_Product_Mockups` -- 7 areas x 3
 * screens, which is the denominator the task fixes. Nothing here may add a row
 * or drop one; a screen this app does not have is a row that reads KHONG, not a
 * row that disappears.
 *
 * ## What a needle has to be
 *
 * A row matches when EVERY string in `kim` appears in that state's text. All,
 * not any: "Khám phá" alone appears in the tab bar of every screen in the shell,
 * so a one-word needle would mark all four tabs as the discovery screen. The
 * needles are taken from text the walk actually recorded, not from the mockup's
 * wording -- the mockup says "Trip total 3.840.000đ" and the app says "Quét để
 * thanh toán", and matching on the mockup's words would score the product
 * against a translation of itself.
 *
 * ## Reached, and reached-but-empty, are different columns
 *
 * A screen that opens and says "Máy chủ không có phần này" was reached: the
 * press worked, the route resolved, the screen mounted. It is also useless to
 * the person standing on it. Collapsing those two into one tick is how a
 * reachability number turns into a claim about a working product, so `rong`
 * is reported beside `toi` and never folded into it.
 *
 * Emptiness here is a fact about the FIXTURE as much as about the app: these
 * walks talk to a stub, and a screen whose route the stub does not answer shows
 * its refusal panel. So `rong` is evidence about what the screen does when the
 * server says nothing, and is labelled that way rather than as a product defect.
 *
 *     node tools/xep-21-man.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DATA = path.join(HERE, "..", "do-canh-21-man.json");

/** How this app says "there is nothing here".
 *
 * Collected from the screens themselves rather than guessed: each of these is a
 * refusal panel some screen in `src/screens/` renders when its route returns
 * nothing. A screen showing one of these was reached and is empty.
 */
const CAU_RONG = [
  "Chưa đọc được",
  "Chưa hiện được",
  "Chưa biết bạn là ai",
  "Chưa chọn người",
  "Không nối được máy chủ",
  "Máy chủ không có phần này",
  "Máy chủ không trả dữ liệu",
  "Máy chủ trả lỗi",
  "Máy chủ này chưa có",
  "chưa dựng",
  // Spelled out rather than shortened to "Chưa có". That prefix also opens
  // "18 ảnh · chưa có", which is a place card's photo count on a screen full
  // of content -- and with the short form every place detail scored RỖNG. An
  // empty-state marker that fires on a populated screen turns the one column
  // that was meant to separate "reached" from "reached and useless" into noise.
  "Chưa có ai trong nhóm",
  "Chưa có bài nào trên tường",
  "Chưa có bản đồ nhóm",
  "Chưa có chuyến nào",
  "Chưa có dữ liệu địa điểm",
  "Chưa có phiếu nào",
  "Chưa có ảnh nào trên tường nhóm",
];

/**
 * The 21 rows, in mockup order.
 *
 * `man` names the component in `src/` that the row is being scored against, so
 * a reader can check the mapping rather than trust it. Where one app screen
 * carries two mockup rows (`MoDau` is both the welcome hero and the three
 * sign-in buttons) both rows name it and the note says so -- merging them would
 * silently shrink the denominator, and dropping one would score the app for a
 * screen it deliberately combined.
 */
const MOCKUP = [
  {
    ma: "01.01",
    ten: "Welcome / màn chào",
    man: "screens/mo-dau/MoDau.tsx",
    kim: ["AI đi chơi, chia bill thông minh"],
    ghi: "app gộp 01.01 và 01.02 vào một màn: hero + tagline + ba nút đăng nhập",
  },
  {
    ma: "01.02",
    ten: "Đăng ký / đăng nhập",
    man: "screens/mo-dau/MoDau.tsx + screens/vao-cua/DangKy.tsx",
    kim: ["Đăng ký với Google", "Đăng ký với Apple", "Đăng nhập bằng số điện thoại"],
  },
  {
    ma: "01.03",
    ten: "Cá nhân hoá sở thích",
    man: "screens/vao-cua/CaNhanHoa.tsx",
    kim: ["Giúp Rủ Đi hiểu bạn hơn", "Sở thích đi chơi"],
  },
  {
    ma: "02.01",
    ten: "Khám phá địa điểm",
    man: "screens/kham-pha/KhamPha.tsx",
    kim: ["Khám phá", "AI chấm theo ngân sách"],
  },
  {
    ma: "02.02",
    ten: "AI Match / tìm bằng lời",
    man: "screens/kham-pha/KhamPha.tsx (ô tìm bằng lời + NhanAi)",
    kim: ["Tìm bằng lời", "AI đọc cả câu"],
  },
  {
    ma: "02.03",
    ten: "Chi tiết địa điểm",
    man: "screens/kham-pha/ChiTietDiaDiem.tsx",
    kim: ["Phù hợp với nhóm", "Người đi trước nói gì"],
  },
  {
    ma: "03.01",
    ten: "Nhóm chat",
    man: "screens/chat/TinNhan.tsx",
    kim: ["Team Đà Lạt", "Chat", "Plan", "Thành viên"],
  },
  {
    ma: "03.02",
    ten: "AI tạo lịch trình",
    man: "screens/chat/ChiTietKeHoach.tsx",
    kim: ["Kế hoạch"],
  },
  {
    ma: "03.03",
    ten: "Bình chọn & chốt plan",
    man: "screens/binh-chon/BinhChon.tsx + screens/chat/MoBinhChon.tsx",
    kim: ["Bình chọn của nhóm"],
  },
  {
    ma: "04.01",
    ten: "Tạo kèo đi chơi",
    man: "screens/len-plan/TaoBuoiDi.tsx",
    kim: ["Tạo chuyến"],
  },
  {
    ma: "04.02",
    ten: "Lịch trình chuyến đi",
    man: "screens/len-plan/DongThoiGian.tsx",
    kim: ["Thêm chặng"],
  },
  {
    ma: "04.03",
    ten: "Check-in & theo dõi nhóm",
    man: "screens/kham-pha/CheckIn.tsx",
    kim: ["Check-in"],
  },
  {
    ma: "05.01",
    ten: "Chụp bill / xem lại hoá đơn",
    man: "screens/ChupBill.tsx",
    kim: ["Chụp bill", "Đưa bill vào khung hình"],
  },
  {
    ma: "05.02",
    ten: "AI nhận diện món & gán người",
    man: "screens/KetQuaNhanDien.tsx + screens/GoiYChia.tsx",
    kim: ["Kết quả nhận diện"],
  },
  {
    ma: "05.03",
    ten: "Kết quả thanh toán / settlement",
    man: "screens/KetQuaThanhToan.tsx",
    kim: ["Quét để thanh toán"],
  },
  {
    ma: "06.01",
    ten: "Tường nhóm riêng tư",
    man: "screens/ky-niem/KyNiem.tsx",
    kim: ["Kỷ niệm của nhóm"],
  },
  {
    ma: "06.02",
    ten: "Album chuyến đi",
    man: "screens/album/AlbumChuyenDi.tsx",
    kim: ["Album chuyến đi"],
  },
  {
    ma: "06.03",
    ten: "Thả khoảnh khắc",
    man: "(không có màn nào trong src mang tên này)",
    kim: ["Thả khoảnh khắc"],
    // Declared absent, and the guard below CHECKS the declaration: if this
    // string ever appears in the source the run refuses, because that would
    // mean the screen exists and this row has been scoring it as missing.
    vangMat: true,
  },
  {
    ma: "07.01",
    ten: "Hồ sơ cá nhân",
    man: "screens/ca-nhan/CaNhan.tsx",
    kim: ["Ảnh đại diện", "Team Đà Lạt"],
  },
  {
    ma: "07.02",
    ten: "Tài chính cá nhân",
    man: "screens/ca-nhan/CaNhan.tsx (khối tài chính)",
    kim: ["Tổng quan tài chính", "Giao dịch gần đây"],
  },
  {
    ma: "07.03",
    ten: "Thành tích",
    man: "screens/thanh-tich/ThanhTich.tsx",
    kim: ["Thành tích của bạn"],
  },
];

/** Every file the app ships, as one string.
 *
 * `App.tsx` is included and was the reason for writing this: an earlier version
 * of the orphan check greped `src/` only, and `App.tsx` -- which is where the
 * shell renders half these screens -- sits beside it, not inside it. Two
 * screens were briefly recorded as rendered by nobody on the strength of that.
 */
function nguonApp() {
  const goc = path.join(HERE, "..");
  const files = [path.join(goc, "App.tsx")];
  const di = (d) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const f = path.join(d, e.name);
      if (e.isDirectory()) di(f);
      else if (/\.(ts|tsx)$/.test(e.name)) files.push(f);
    }
  };
  di(path.join(goc, "src"));
  return files.map((f) => fs.readFileSync(f, "utf8")).join("\n");
}

/** Refuse to report on a needle list that has drifted off the source.
 *
 * A needle that matches nothing scores its row KHONG for ever, and reads
 * exactly like a screen with no way in. That is the most damaging way this file
 * can be wrong, because the output it produces is the one somebody acts on --
 * "here is the dead screen, go delete it".
 *
 * Four of the first draft's needles were this: `Gu đi chơi`, `Vì sao AI gợi ý
 * chỗ này`, `Tiền của bạn`, `Lịch trình`. All four were plausible, none was in
 * the app, and all four would have reported a built and reachable screen as
 * dead. A hand-kept list does not know what it is missing, so the check has to
 * be mechanical.
 *
 * Both directions are errors. A needle absent from the source when the row does
 * not declare it absent means the needle is stale. A needle PRESENT when the row
 * declares it absent means the screen arrived and the row never noticed.
 */
function kiemKim(nguon) {
  const loi = [];
  for (const c of CAU_RONG) {
    if (!nguon.includes(c)) loi.push(`CAU_RONG: ${JSON.stringify(c)} không có trong nguồn app`);
  }
  for (const m of MOCKUP) {
    for (const k of m.kim) {
      const co = nguon.includes(k);
      if (!co && !m.vangMat) loi.push(`${m.ma}: kim ${JSON.stringify(k)} không có trong nguồn app`);
      if (co && m.vangMat) loi.push(`${m.ma}: kim ${JSON.stringify(k)} ĐÃ có trong nguồn, nhưng hàng khai là vắng mặt`);
    }
  }
  return loi;
}

function rong(chu) {
  return CAU_RONG.filter((c) => chu.includes(c));
}

function main() {
  const loiKim = kiemKim(nguonApp());
  if (loiKim.length) {
    console.error("Bảng kim đã trôi khỏi nguồn, từ chối in số:\n  " + loiKim.join("\n  "));
    process.exit(2);
  }

  const d = JSON.parse(fs.readFileSync(DATA, "utf8"));

  // Both passes are evidence of the same kind: a screen stood on after a
  // sequence of real presses. They are pooled, with the pass recorded, so a row
  // says which walk reached it.
  const canh = [
    ...d.trang_thai.map((s) => ({ pass: "A", duong: s.duong, chu: s.chu, sau: s.sau })),
    ...d.moc_duong_tien
      .filter((m) => m.dat)
      .map((m) => ({ pass: "B", duong: m.duong, chu: m.chu, sau: m.duong.length })),
  ];

  const bang = MOCKUP.map((m) => {
    const hop = canh.filter((c) => m.kim.every((k) => c.chu.includes(k)));
    hop.sort((a, b) => a.sau - b.sau);
    const tot = hop[0] ?? null;
    return {
      ...m,
      toi: tot !== null,
      pass: tot?.pass ?? null,
      sau: tot?.sau ?? null,
      duong: tot?.duong ?? null,
      rong: tot ? rong(tot.chu) : [],
      soTrangThai: hop.length,
    };
  });

  /* Negative control, and it is the pair to the walk's positive one.
   *
   * `Khám phá` coming back reached proves the instrument can see. It does not
   * prove the instrument can say NO -- a matcher loose enough to fire on any
   * screen would also report Khám phá reached, and both controls would pass.
   * 06.03's needle is declared absent from the source and checked to be absent
   * by `kiemKim`, so no state can legitimately contain it. A row that matches
   * anyway means the matching is wrong, and every other CÓ in the table is
   * worth nothing.
   */
  const gia = bang.filter((r) => r.vangMat && r.toi);
  if (gia.length) {
    console.error(
      "Đối chứng ÂM hỏng: " +
        gia.map((r) => r.ma).join(", ") +
        " khai là vắng mặt trong nguồn mà vẫn khớp một trạng thái. Phép so đang bắt bừa; từ chối in số.",
    );
    process.exit(2);
  }

  const toi = bang.filter((r) => r.toi);
  const rongRa = toi.filter((r) => r.rong.length > 0);

  console.log(`# Đo bằng CẠNH — ${toi.length}/21 màn bấm tới được\n`);
  console.log(`commit: ${d.commit}`);
  console.log(`khung nhìn: ${d.viewport.join("x")}   sâu tối đa pass A: ${d.sau_toi_da}`);
  console.log(`pass A: ${d.so_trang_thai} trạng thái / ${d.so_lan_tai} lần tải / ${d.con_lai_chua_di.length} cạnh chưa đi`);
  console.log(`đối chứng dương (Khám phá tới được): ${d.doi_chung_duong_kham_pha ? "ĐẠT" : "HỎNG"}`);
  console.log(`\n| # | Màn (mockup) | Tới được | Bước | Rỗng | #trạng thái khớp | Màn trong src |`);
  console.log(`|---|---|---|---|---|---|---|`);
  for (const r of bang) {
    console.log(
      `| ${r.ma} | ${r.ten} | ${r.toi ? `**CÓ** (pass ${r.pass})` : "**KHÔNG**"} | ${
        r.sau ?? "—"
      } | ${r.rong.length ? "RỖNG: " + r.rong.join(", ") : r.toi ? "có nội dung" : "—"} | ${r.soTrangThai} | \`${r.man}\` |`,
    );
  }
  console.log(`\n## Đường bấm của từng màn tới được\n`);
  for (const r of bang.filter((x) => x.toi)) {
    console.log(`- **${r.ma}** (${r.sau} bước): ${r.duong.join(" → ")}`);
  }
  console.log(`\n## Màn chết (không cạnh nào dẫn tới)\n`);
  for (const r of bang.filter((x) => !x.toi)) {
    console.log(`- **${r.ma} ${r.ten}** — \`${r.man}\`${r.ghi ? ` · ${r.ghi}` : ""}`);
  }
  console.log(
    `\nTổng: ${toi.length}/21 tới được, trong đó ${rongRa.length} màn RỖNG khi tới nơi.`,
  );
}

main();
