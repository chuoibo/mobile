#!/usr/bin/env node
/* Dựng thế giới demo «Team Đà Lạt» cho vỏ RuDi qua đúng những lời gọi client
 * mà app gửi -- không có hình dạng wire thứ hai để trôi dạt.
 *
 *   npm run seed:rudi -- --api http://127.0.0.1:PORT --otp-code 000000 [--fresh] [--model]
 *
 * Máy chủ phải chạy chế độ `prod` với SMS sender `log` và MOBILE_OTP_DEBUG_CODE
 * (như scripts/e2e_slice.sh dựng). Chạy lần hai trên cùng máy chủ là no-op:
 * mỗi bước đọc trạng thái trước rồi mới ghi. Không in số điện thoại hay token.
 *
 * Tám người tổng hợp, một nhóm, đồ thị bạn bè, 12 tin + một bình chọn, một kèo
 * ba ngày với chặng trong danh mục và check-in, hóa đơn «Tiệm Nướng Xóm Lèo»
 * 1.280.000đ -> khoản chi -> đợt thu đã phát, ba check-in và hai ảnh trên
 * tường với tim và bình luận. AI chỉ được gọi khi --model (tốn quota).
 */
import { setTimeout as sleep } from "node:timers/promises";

import { HOA_DON_XOM_LEO, ROSTER, conPhaiLam, pngMau, soDienThoai, tongHoaDon } from "./seed-rudi-world-lib.mjs";

function doc(args) {
  const out = { api: null, otpCode: process.env.MOBILE_OTP_DEBUG_CODE ?? null, fresh: false, model: false };
  for (let i = 0; i < args.length; i += 1) {
    const a = args[i];
    if (a === "--api") out.api = args[++i];
    else if (a === "--otp-code") out.otpCode = args[++i];
    else if (a === "--fresh") out.fresh = true;
    else if (a === "--model") out.model = true;
    else throw new Error(`Không hiểu tham số ${a}`);
  }
  if (!out.api) throw new Error("Thiếu --api http://host:port");
  if (!out.otpCode) throw new Error("Thiếu --otp-code (hoặc MOBILE_OTP_DEBUG_CODE)");
  return out;
}

const opts = doc(process.argv.slice(2));
process.env.EXPO_PUBLIC_API_URL = opts.api;
const API = opts.api.replace(/\/$/, "");

// Import after the env is set: `api.ts` reads EXPO_PUBLIC_API_URL when it loads.
const api = await import("../dist-test/api.js");
const danhTinh = await import("../dist-test/danh-tinh.js");
const congApi = await import("../dist-test/screens/vao-cua/cong-api.js");
const banBe = await import("../dist-test/screens/ca-nhan/ban-be.js");
const tinSong = await import("../dist-test/rudi/chat/tin-song.js");
const keo = await import("../dist-test/rudi/keo/keo.js");
const diaDiem = await import("../dist-test/rudi/kham-pha/dia-diem.js");
const receipt = await import("../dist-test/receipt.js");
const assignment = await import("../dist-test/assignment.js");
const hoaDon = await import("../dist-test/rudi/chia-bill/hoa-don.js");
const dotThu = await import("../dist-test/rudi/dot-thu/dot-thu.js");
const kyNiem = await import("../dist-test/rudi/ky-niem/ky-niem.js");

const attempts = {};
const attempt = (name) => api.attemptFor(attempts, name);
const log = (s) => console.log(s);
const suffix = opts.fresh ? ` (${new Date().toISOString().slice(0, 16).replace("T", " ")})` : "";
const TEN_NHOM = `Team Đà Lạt${suffix}`;
const TEN_KEO = "Đà Lạt cuối tuần";

/* ------------------------------------------------------------- đăng nhập */

async function postJson(path, body) {
  const res = await fetch(API + path, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(body) });
  const text = await res.text();
  let json = null;
  try {
    json = JSON.parse(text);
  } catch {
    json = null;
  }
  return { status: res.status, json };
}

async function dangNhap(phone) {
  const yeuCau = await postJson("/auth/otp/request", { phone });
  if (yeuCau.status === 429) {
    log("  nhịp OTP: đợi 66 s");
    await sleep(66_000);
    return dangNhap(phone);
  }
  if (yeuCau.status !== 202) throw new Error(`OTP request HTTP ${yeuCau.status} ${yeuCau.json?.code ?? ""}`);
  const xacMinh = await postJson("/auth/otp/verify", { challenge_id: yeuCau.json.challenge_id, phone, code: opts.otpCode });
  if (xacMinh.status !== 201) throw new Error(`OTP verify HTTP ${xacMinh.status} ${xacMinh.json?.code ?? ""}`);
  return { token: xacMinh.json.token, personId: xacMinh.json.person_id };
}

/** Run `fn` as this person: the client modules read one global bearer. */
async function la(nguoi, fn) {
  api.datTokenPhien(nguoi.token);
  try {
    return await fn(nguoi.personId);
  } finally {
    api.datTokenPhien(null);
  }
}

async function docNhomCua(personId) {
  return api.translatedAsActor({}, "/people/me/contexts", { method: "GET", actorId: personId });
}

/* --------------------------------------------------------------- dựng */

log(`Dựng «${TEN_NHOM}» trên ${API}`);
const nguoi = [];
for (let i = 0; i < ROSTER.length; i += 1) {
  const phone = soDienThoai(i, opts.fresh ? Date.now() % 997 : 0);
  const phien = await dangNhap(phone);
  const p = { ...ROSTER[i], phone, ...phien };
  await la(p, (id) => api.translatedAsActor({}, "/people/me", { method: "PATCH", body: { display_name: p.name }, actorId: id, attempt: api.newAttempt() }));
  nguoi.push(p);
  log(`  ${p.name}: đăng nhập, tên đã đặt`);
  if (i < ROSTER.length - 1) await sleep(6_500); // 10 lời gọi/phút/IP
}
const [toChuc, ...conLai] = nguoi;

// Nhóm: tìm theo tên trước, tạo sau.
let nhom = await la(toChuc, async (id) => {
  const ds = await docNhomCua(id);
  return ds.contexts.find((c) => c.display_name === TEN_NHOM) ?? null;
});
const ctx = nhom === null ? (await la(toChuc, (id) => congApi.taoNhom(TEN_NHOM, id, attempt(`nhom:${TEN_NHOM}`)))).id : nhom.id;
log(nhom === null ? `  nhóm tạo mới: ${TEN_NHOM}` : `  nhóm đã có: ${TEN_NHOM}`);

// Thành viên: mời theo số, người được mời tự nhận.
const thanhVien = await la(toChuc, (id) => congApi.danhSachThanhVien(ctx, id));
const daCo = new Set(thanhVien.filter((tv) => tv.state !== "left").map((tv) => tv.person_id));
for (const p of conLai) {
  if (daCo.has(p.personId)) continue;
  await la(toChuc, (id) => congApi.moiVaoNhom(ctx, p.personId, id, attempt(`moi:${ctx}:${p.personId}`)));
  const loiMoi = await la(p, async (id) => (await docNhomCua(id)).contexts.find((c) => c.id === ctx && c.my_state === "invited"));
  if (loiMoi) await la(p, (id) => congApi.nhanLoiMoi(loiMoi.membership_id, id, attempt(`nhan:${loiMoi.membership_id}`)));
  log(`  ${p.name}: vào nhóm`);
}

// Bạn bè: người tổ chức là bạn của mọi người.
const banHienCo = new Set((await la(toChuc, (id) => banBe.docDanhSachBan(id, id))).map((b) => b.person_id ?? b.other_person_id));
for (const p of conLai) {
  if (banHienCo.has(p.personId)) continue;
  const lm = await la(toChuc, (id) => banBe.guiLoiMoi(p.personId, id, attempt(`ban:${p.personId}`)));
  await la(p, (id) => banBe.traLoiLoiMoi(lm.id, "accept", id, attempt(`ban-nhan:${lm.id}`)));
  log(`  ${p.name}: đã là bạn của ${toChuc.name}`);
}

// Tin nhắn: một cuộc trò chuyện ngắn và một bình chọn do máy chủ dựng thẻ.
const TIN = [
  [0, "Cuối tuần này Đà Lạt không mọi người?"],
  [1, "Đi! Tối thứ sáu xuất phát cho kịp sáng thứ bảy."],
  [2, "Mình đặt xe 16 chỗ nhé, 8 người vừa."],
  [3, "Ở homestay gần Hồ Xuân Hương cho tiện đi bộ."],
  [4, "Tối thứ bảy ăn Tiệm Nướng Xóm Lèo, nhớ đặt bàn trước."],
  [5, "Sáng chủ nhật cà phê rồi chợ Đà Lạt mua đồ về."],
  [6, "Ai mang loa? Tối đốt lửa hát hò."],
  [7, "Mình mang, kèm dây đèn cho đẹp ảnh."],
  [0, "Ngân sách mỗi người khoảng 2 triệu rưỡi, ổn không?"],
  [1, "Ổn. Ăn uống mình ứng trước rồi chia sau."],
  [2, "/vote Tối thứ sáu ăn gì trước khi đi? Bánh mì | Phở | Cơm tấm"],
  [3, "Chốt lịch trình rồi lên plan trong app nhé."],
];
const trangTin = await la(toChuc, (id) => tinSong.docTrangTin(ctx, id, { limit: 50 }));
const soTin = trangTin.messages.length;
if (soTin < TIN.length) {
  for (const [k, body] of TIN.slice(soTin)) {
    await la(nguoi[k], (id) => tinSong.guiTin(ctx, id, body, attempt(`tin:${k}:${body}`)));
  }
  log(`  ${TIN.length - soTin} tin nhắn gửi (trong đó một /vote)`);
} else log("  tin nhắn đã có");
if (opts.model) {
  await la(toChuc, (id) => tinSong.guiTin(ctx, id, "/plan tối thứ bảy quanh Hồ Xuân Hương cho 8 người", attempt("tin:plan")));
  log("  /plan gửi (mô hình)");
}

// Kèo ba ngày với chặng trong danh mục và check-in.
const danhMuc = await diaDiem.docDanhMuc();
const cho = (q) => danhMuc.places.find((p) => p.name.toLowerCase().includes(q)) ?? danhMuc.places[0];
let cacKeo = await la(toChuc, (id) => keo.docKeoCuaNhom(ctx, id));
let keoChinh = cacKeo.find((k) => k.title === TEN_KEO) ?? null;
if (keoChinh === null) {
  keoChinh = await la(toChuc, (id) => keo.taoKeo(ctx, id, { title: TEN_KEO, starts_on: "2026-10-17", ends_on: "2026-10-19", headcount: nguoi.length, budget_per_person_vnd: 2_500_000 }, attempt(`keo:${TEN_KEO}`)));
  const chang = [
    { at: "08:30", label: "Cà phê sáng", place_name: cho("cafe").name, place_id: cho("cafe").id },
    { at: "12:00", label: "Ăn trưa", place_name: cho("ốc").name, place_id: cho("ốc").id },
    { at: "18:30", label: "Tối nướng", place_name: cho("xóm lào").name, place_id: cho("xóm lào").id },
  ];
  keoChinh = await la(toChuc, (id) => keo.luuLichTrinh(keoChinh, chang, id, attempt(`lich:${keoChinh.id}`)));
  for (const p of nguoi.slice(0, 3)) {
    await la(p, (id) => keo.danhDauToi(keoChinh.stops[0].id, ctx, id, attempt(`toi:${keoChinh.stops[0].id}:${id}`)));
  }
  log(`  kèo «${TEN_KEO}» tạo với ${chang.length} chặng, 3 check-in`);
} else log(`  kèo «${TEN_KEO}» đã có`);

// Hóa đơn Xóm Lèo -> khoản chi -> đợt thu đã phát.
const roster = nguoi.map((p) => ({ id: p.personId, name: p.name }));
const dotDaCo = await la(toChuc, (id) => dotThu.docDotThuCuaNhom(ctx, id));
if (dotDaCo.length === 0) {
  let reading = hoaDon.hoaDonTrong();
  HOA_DON_XOM_LEO.forEach(([ten, vnd], i) => {
    reading = hoaDon.themMon(reading);
    const id = reading.lines[i].id;
    reading = receipt.renameLine(reading, id, ten);
    reading = receipt.setLineTotal(reading, id, String(vnd)).reading;
  });
  const ids = roster.map((r) => r.id);
  const gan = assignment.everyoneShares(reading.lines, ids);
  const bill = await la(toChuc, (id) => hoaDon.taoBillTrenMayChu(reading, ctx, gan, id, attempt("bill:xom-leo")));
  await la(toChuc, (id) => hoaDon.luuGanMonTrenMayChu(bill.id, reading, gan, id, ctx, attempt(`gan:${bill.id}`)));
  const chia = await la(toChuc, (id) => hoaDon.chiaTrenMayChu(bill.id, id, ctx, attempt(`chia:${bill.id}`)));
  if (chia.totalAmountVnd !== tongHoaDon()) throw new Error(`Máy chủ chia ${chia.totalAmountVnd}, hóa đơn ${tongHoaDon()}`);
  await la(toChuc, (id) => hoaDon.ghiVaoSo({ reading, assignment: gan, roster, contextId: ctx, payerId: id, occasion: "Tối nướng Xóm Lèo", attempts }));
  const dot = await la(toChuc, (id) => dotThu.moDotThu({ contextId: ctx, actorId: id, expenseVersionIds: null, attempt: attempt("dot:xom-leo") }));
  const links = await la(toChuc, (id) => dotThu.phatDotThu(dot.batchId, id, attempt(`phat:${dot.batchId}`), roster));
  log(`  hóa đơn ${tongHoaDon()}đ ghi vào sổ, đợt thu phát cho ${links.length} người (link không in)`);
} else log("  đợt thu đã có");

// Tường: ba check-in, hai ảnh, tim và bình luận.
const tuong = await la(toChuc, (id) => kyNiem.docTuongNhom(ctx, id));
if (tuong.kyNiem.length < 5) {
  const cacCheckIn = [];
  for (const [k, q, cau] of [[1, "cafe", "Cà phê view đồi, lạnh vừa đủ"], [2, "ốc", "Ốc ở đây ngon thật"], [3, "xóm lào", "Bò nướng đúng gu cả nhóm"]]) {
    cacCheckIn.push(await la(nguoi[k], (id) => kyNiem.checkInKyNiem(ctx, cho(q).id, cau, id, attempt(`ci:${k}:${q}`))));
  }
  const anh = [];
  for (const [k, cau, mau] of [[0, "Đà Lạt về đêm", [0, 117, 107]], [4, "Sáng sớm bên hồ", [194, 65, 12]]]) {
    const daTai = await la(nguoi[k], async (id) => {
      const form = new FormData();
      form.append("file", new Blob([pngMau(96, 72, mau)], { type: "image/png" }), "khoanh-khac.png");
      const { "Content-Type": _bo, ...headers } = danhTinh.headerNguoiGoi(id, { roles: "member", contexts: ctx });
      const res = await fetch(`${API}/contexts/${ctx}/photos`, { method: "POST", headers, body: form });
      if (res.status !== 201) throw new Error(`upload HTTP ${res.status}`);
      return res.json();
    });
    anh.push(await la(nguoi[k], (id) => api.themKyNiemAnh(ctx, daTai.url, cau, id, attempt(`anh:${daTai.url}`))));
  }
  const dau = cacCheckIn[1];
  for (const p of nguoi.slice(3, 6)) await la(p, (id) => kyNiem.doiTim(dau, ctx, id));
  await la(nguoi[6], (id) => kyNiem.guiBinhLuanCho(ctx, dau.id, "Lần sau đi lại nhé", id, attempts));
  await la(nguoi[7], (id) => kyNiem.guiBinhLuanCho(ctx, dau.id, "Đặt bàn sớm là đúng", id, attempts));
  log(`  tường: ${cacCheckIn.length} check-in, ${anh.length} ảnh, 3 tim, 2 bình luận`);
} else log("  tường đã có kỷ niệm");

// Đọc lại và in tóm tắt: số máy chủ, không phải số tự đếm.
const tomTat = await la(toChuc, async (id) => ({
  thanhVien: (await congApi.danhSachThanhVien(ctx, id)).filter((tv) => tv.state === "active").length,
  tin: (await tinSong.docTrangTin(ctx, id, { limit: 50 })).messages.length,
  keo: (await keo.docKeoCuaNhom(ctx, id)).length,
  dot: (await dotThu.docDotThuCuaNhom(ctx, id)).length,
  kyNiem: (await kyNiem.docTuongNhom(ctx, id)).kyNiem.length,
}));
log(`Xong. «${TEN_NHOM}»: ${tomTat.thanhVien} thành viên · ${tomTat.tin} tin · ${tomTat.keo} kèo · ${tomTat.dot} đợt thu · ${tomTat.kyNiem} kỷ niệm`);
log("Đăng nhập trên máy bằng số của một người trong ROSTER (soDienThoai(i) trong seed-rudi-world-lib.mjs) và mã debug; số không in ra đây.");
console.log(JSON.stringify(conPhaiLam({ nhom: {}, soNguoi: nguoi.length, soThanhVien: tomTat.thanhVien, soBan: nguoi.length - 1, soTin: tomTat.tin, soTinMuon: TIN.length, coKeo: tomTat.keo > 0, coDotThu: tomTat.dot > 0, coKhoanChi: true, soKyNiem: tomTat.kyNiem, soKyNiemMuon: 5 })));
