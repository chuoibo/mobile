/** What a person is allowed to read when the server itself is the thing that failed.
 *
 * Three of the four dead ends on Khám phá already wrap the server's own words
 * in a Vietnamese sentence and keep them behind a "Chi tiết:" label. The 5xx
 * branch did not: it assigned `state.detail` straight into the body, so the
 * phone showed `<html>502 Bad Gateway</html>` or `{"detail":"rate limited"}`
 * where a sentence belongs (bug-185426).
 *
 * The sentence is the readable half. The excerpt is the safe half, and it is
 * why this is a module rather than two string literals: a 5xx body is the one
 * string on these screens the app does not author. Turn on FastAPI's debug
 * pages, or put a proxy in front, and that body becomes a traceback, an
 * internal hostname, or a SQL statement, rendered full width at body size to
 * whoever is holding the phone. `places.ts` and `tim-kiem.ts` already cut it to
 * 200 characters, which bounds the damage but does not decide what a person
 * should see. That decision lives here.
 *
 * Kept out of `Kit.tsx` on purpose: this is copy, not a component, and both
 * halves have to be assertable without rendering anything.
 */

/** Longest excerpt worth putting under a sentence on a phone screen. */
const TOI_DA_CHI_TIET = 120;

/**
 * The server's own words, reduced to something a person can read on one or two
 * lines: tags dropped, whitespace collapsed, length capped.
 *
 * Tags become a space rather than nothing, so `<p>502</p><p>Bad Gateway</p>`
 * reads as two words instead of one invented one.
 */
export function trichThanLoi(detail: string, toiDa: number = TOI_DA_CHI_TIET): string {
  const motDong = detail
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!motDong) return "";
  return motDong.length > toiDa ? `${motDong.slice(0, toiDa).trimEnd()}…` : motDong;
}

/**
 * The lead sentence for a request the server answered with a refusal.
 *
 * Three cases, because they send a person to three different places: being
 * throttled is something to wait out, a 5xx is somebody else's afternoon, and
 * any other refusal is a decision the server made on purpose.
 */
export function cauMayChuLoi(status: number): string {
  if (status === 429) {
    return "Đang gửi quá nhanh nên máy chủ tạm chặn bớt. Chờ một lát rồi thử lại.";
  }
  if (status >= 500) {
    return "Máy chủ nhận được yêu cầu nhưng không trả lời được. Đây là sự cố phía máy chủ. Thử lại sau ít phút.";
  }
  return "Máy chủ từ chối yêu cầu này.";
}

/**
 * The whole body copy for a `may-chu-loi` state: sentence first, the server's
 * words second and clearly labelled as an excerpt.
 *
 * `them` is an extra clause the calling screen owns. The search box uses it to
 * say the sentence the person typed is not at fault, which is the wrong thing
 * to say on a screen where nobody typed anything.
 */
export function thanLoiMayChu(status: number, detail: string, them: string = ""): string {
  const dau = them ? `${cauMayChuLoi(status)} ${them}` : cauMayChuLoi(status);
  const trich = trichThanLoi(detail);
  return trich ? `${dau} Chi tiết: ${trich}` : dau;
}
