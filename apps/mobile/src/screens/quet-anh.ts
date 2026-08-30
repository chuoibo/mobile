/** Labels for a screenshot reading. No people, no line items.
 *
 * Kept out of the React file so a test can pin the four source names without
 * compiling a screen. The card imports these; it does not invent a fifth.
 */
import type { ScreenshotScanWire } from "../api";

export const CAU_CHUA_GHI_QUET_ANH =
  "Chưa ghi khoản chi nào. Chốt thì số này vào form nhập tay, chưa vào sổ.";

export function tenNguonQuetAnh(source: ScreenshotScanWire["source"]): string {
  if (source === "grab") return "Grab";
  if (source === "shopeefood") return "ShopeeFood";
  if (source === "banking") return "Chuyển khoản";
  return "Hoá đơn";
}

/**
 * `occurred_on` as a person writes a date, or "" when the server sent none.
 *
 * String surgery, not `Date`. `occurred_on` is a calendar date -- the server
 * declares it `date`, not `datetime` -- and a bare date has no instant and no
 * zone. Handing "2026-08-29" to `new Date()` invents one (UTC midnight), so
 * every reader that then shifts it, as `ngayNgan` in `ca-nhan/tai-chinh.ts`
 * legitimately must for real timestamps, is shifting something that was never
 * on a clock. That is how a purchase silently changes day for anyone west of
 * UTC, and it would only ever show up on a machine whose zone disagrees.
 *
 * `ngayNgan` is also the wrong shape here for a second reason: it drops the
 * year, and a screenshot can be of a receipt from any month.
 */
export function ngayQuetAnh(occurredOn: string | null): string {
  if (!occurredOn) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(occurredOn.trim());
  if (!m) return "";
  return `${m[3]}/${m[2]}/${m[1]}`;
}
