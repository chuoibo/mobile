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
