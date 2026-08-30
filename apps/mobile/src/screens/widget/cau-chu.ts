/** F38. The parts of the home widget worth testing without rendering anything.
 *
 * Same split `ca-nhan/tai-chinh.ts` and `ky-niem/ky-uc.ts` make, for the same
 * reason: the moment-line and the refusal words are where this screen can be
 * wrong in a way a screenshot cannot see, and both are pure functions of their
 * inputs here.
 *
 * Nothing in this file talks to the network. `api.ts` owns the request, because
 * the widget must go through the same `translated` refusal table every other
 * photo route goes through -- a second fetch with its own error handling is the
 * shape that ends up showing an English error code on a Vietnamese screen.
 */

/** How long ago, in the words a Vietnamese widget uses.
 *
 * `now` is a parameter and not `Date.now()`. Two reasons, and the second is the
 * one that has bitten this repo: a frozen clock inside a formatter makes every
 * mutation of the window boundaries invisible, because the test and the code
 * read the same standing value and agree with each other about a moment that
 * never moves. Passing it in means a test can stand at 11:59 and at 12:01 of
 * the same boundary and get two different answers.
 *
 * `Intl` / `toLocaleString` are refused for the reason `ky-uc.ts` states: Hermes
 * ships without full ICU unless the app opts in, so the fallback is the C locale
 * and the failure is invisible on the web build where Intl works fine.
 *
 * A timestamp in the future is not an error and is not clamped to a negative
 * count: clocks disagree by seconds all the time, and "trong 0 phút nữa" on a
 * photograph somebody just posted would read as a bug in the product rather
 * than as a two-second skew between a phone and a server. It reads "vừa xong".
 */
export function batDauTu(createdAt: string, now: number): string {
  const at = Date.parse(createdAt);
  // An unparseable timestamp says nothing rather than printing "NaN phút
  // trước". The caller draws the name alone, which is still true.
  if (Number.isNaN(at)) return "";

  const giay = Math.floor((now - at) / 1000);
  if (giay < 60) return "vừa xong";

  const phut = Math.floor(giay / 60);
  if (phut < 60) return `${phut} phút trước`;

  const gio = Math.floor(phut / 60);
  if (gio < 24) return `${gio} giờ trước`;

  const ngay = Math.floor(gio / 24);
  if (ngay === 1) return "hôm qua";
  if (ngay < 7) return `${ngay} ngày trước`;

  // Past a week the elapsed count stops helping -- "23 ngày trước" is arithmetic
  // somebody has to do in their head to get back to a date -- so it becomes the
  // date. Read in UTC+7 rather than in the device zone, because this product's
  // days are Vietnam's days and a phone left on US time would print the 22nd for
  // a photograph taken on the evening of the 23rd.
  return ngayVietNam(at);
}

/** `23/08/2026`, on Vietnam's calendar, from an instant. */
export function ngayVietNam(at: number): string {
  // +07:00 has no daylight saving and has not moved since 1975, so a fixed
  // offset is exact here rather than an approximation of a real timezone.
  const d = new Date(at + 7 * 3600 * 1000);
  const hai = (n: number) => String(n).padStart(2, "0");
  return `${hai(d.getUTCDate())}/${hai(d.getUTCMonth() + 1)}/${d.getUTCFullYear()}`;
}

/**
 * The one line under the photograph: who, and when.
 *
 * Built here rather than in JSX so the empty-timestamp case has a test. When
 * `batDauTu` returns "" the separator has to go with it, or the widget prints
 * "Nam · " and the trailing middot reads as a value that failed to load.
 */
export function dongTacGia(authorName: string, createdAt: string, now: number): string {
  const ten = authorName.trim();
  const luc = batDauTu(createdAt, now);
  if (!ten) return luc;
  if (!luc) return ten;
  return `${ten} · ${luc}`;
}

/**
 * Refusals in words the person holding the phone can act on.
 *
 * Never the server's `code`, and never the status number on its own. A widget
 * is the surface most likely to be read by somebody who did not press anything,
 * so "permission_denied" there is a machine talking to itself.
 *
 * 404 is a group this person is not in OR a group that does not exist, and the
 * server refuses to tell the two apart on purpose. So this sentence must not
 * either -- wording it as "nhóm không tồn tại" would hand back the distinction
 * the service went out of its way not to leak.
 */
export function loiWidget(status: number, code: string): string {
  if (code === "permission_denied" || status === 403) {
    return "Ảnh của nhóm chỉ thành viên xem được. Nhờ người tạo nhóm mời bạn vào rồi thử lại.";
  }
  if (status === 401) return "Chưa đăng nhập nên chưa hỏi được máy chủ.";
  if (status === 404) return "Không mở được nhóm này.";
  if (status === 0) return "Không nối được máy chủ. Kiểm tra mạng rồi thử lại.";
  if (status >= 500) return "Máy chủ đang lỗi, chưa đọc được ảnh mới nhất.";
  return "Chưa đọc được ảnh mới nhất của nhóm.";
}

/** What a screen reader is told the picture is.
 *
 * The caption when there is one, because that is what the person who posted it
 * chose to say about it. Otherwise the fact, which is more use than "ảnh": a
 * blind reader learns whose photograph it is and roughly when, which is the
 * whole content of this screen.
 */
export function moTaAnh(authorName: string, caption: string | null): string {
  const chu = caption?.trim();
  if (chu) return chu;
  const ten = authorName.trim();
  return ten ? `Ảnh ${ten} vừa đăng` : "Ảnh mới nhất của nhóm";
}
