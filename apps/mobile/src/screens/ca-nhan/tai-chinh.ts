/** Reading one person's money off the API, and shaping it for the screen.
 *
 * Nothing here computes money. `settled + outstanding == spend` is guaranteed
 * by the ledger query that answers this route, and the screen renders the
 * three numbers it is given -- deriving even one of them here would be a
 * second implementation of the same arithmetic, which is exactly how two
 * screens end up showing two different totals for one dinner.
 *
 * Formatting is not computing. Grouping digits and naming a direction change
 * how a number reads, never what it is.
 *
 * Split out of the component so the parts worth testing can be tested without
 * rendering anything: the money formatter, the sign, and the failure text.
 */
import { BASE_URL, headerNguoiGoi } from "../../api";

/** One confirmed arrival, as the server describes it. */
export type Movement = {
  obligation_id: string;
  /** `out` when this person sent it, `in` when they collected it. */
  direction: "in" | "out";
  /** Always positive. The sign lives in `direction`. */
  amount_vnd: number;
  counterparty_id: string;
  counterparty_name: string | null;
  context_id: string;
  context_name: string | null;
  occasion: string | null;
  occurred_at: string;
};

export type Finance = {
  person_id: string;
  display_name: string | null;
  spend_vnd: number;
  settled_vnd: number;
  outstanding_vnd: number;
  /** What other people still owe this person for shares they fronted.
   *
   *  Deliberately outside `settled + outstanding == spend`: money advanced
   *  for somebody else was never this person's spend, so adding it to the
   *  total would show an amount nobody owes. */
  receivable_vnd: number;
  expense_count: number;
  group_count: number;
  movements: Movement[];
};

/** The five states mockup 07.02 asks the finance screen to support. */
export type TinhTrangNo =
  | "khong-no"
  | "duoc-nhan"
  | "phai-tra"
  | "hai-chieu";

/**
 * Which of the mockup's five states this person is in, and the sentence for it.
 *
 * A sentence rather than two numbers alone, because the numbers are the answer
 * to a question the reader has to assemble themselves: two coloured tiles
 * reading `530.000đ` and `120.000đ` do not say, in three seconds, whether this
 * is a good month. The colours cannot carry it either -- the mockup's own rule
 * is that state is never distinguished by colour alone.
 *
 * No arithmetic. `receivable` and `outstanding` arrive from the ledger already
 * clamped at zero, and this only reads whether each is above it: subtracting
 * one from the other here would be a net position this product has never
 * defined, computed in the one layer that must not compute money.
 *
 * `Settled` from the mockup's list is not a fourth branch. A person who has
 * paid everything and been paid back reads as `khong-no`, which is the same
 * sentence and the same truth -- inventing a separate "đã tất toán" wording
 * would claim the screen can tell "settled up" apart from "never split
 * anything", and it cannot: both are two zeroes.
 */
export function tinhTrangNo(finance: {
  receivable_vnd: number;
  outstanding_vnd: number;
}): { tinhTrang: TinhTrangNo; cau: string } {
  const nhan = finance.receivable_vnd > 0;
  const tra = finance.outstanding_vnd > 0;
  if (nhan && tra) {
    return {
      tinhTrang: "hai-chieu",
      cau: `Bạn còn nợ ${tienVnd(finance.outstanding_vnd)} và người khác nợ bạn ${tienVnd(finance.receivable_vnd)}.`,
    };
  }
  if (nhan) {
    return {
      tinhTrang: "duoc-nhan",
      cau: `Người khác đang nợ bạn ${tienVnd(finance.receivable_vnd)}.`,
    };
  }
  if (tra) {
    return {
      tinhTrang: "phai-tra",
      cau: `Bạn còn nợ ${tienVnd(finance.outstanding_vnd)}.`,
    };
  }
  return {
    tinhTrang: "khong-no",
    cau: "Bạn không nợ ai, và không ai nợ bạn.",
  };
}

/**
 * Money as Vietnamese writes it: `860.000đ`.
 *
 * `Intl` is not used. Hermes ships without full ICU unless the app opts into a
 * larger binary, and `toLocaleString` there silently falls back to the C
 * locale -- which groups with commas. A demo in front of Vietnamese viewers
 * showing `860,000đ` is a small thing that reads as a foreign product, and the
 * failure is invisible on the web build, where Intl works fine.
 */
export function tienVnd(amount: number): string {
  const negative = amount < 0;
  const digits = Math.abs(Math.trunc(amount)).toString();
  let grouped = "";
  for (let i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 === 0) grouped += ".";
    grouped += digits[i];
  }
  return `${negative ? "-" : ""}${grouped}đ`;
}

/** A movement with its sign shown, the way the mockup prints it. */
export function tienCoDau(movement: Movement): string {
  return `${movement.direction === "in" ? "+" : "-"}${tienVnd(movement.amount_vnd)}`;
}

/** Vietnam is a fixed UTC+7: no DST, and none since 1975. */
const PHUT_LECH_VN = 7 * 60;

/**
 * `20/05`, from the ISO instant the server sent, always as Vietnam reads it.
 *
 * `getDate()`/`getMonth()` were used here first, and they answer in *the
 * device's* timezone -- so one transaction rendered `02/01` on a phone in Hà
 * Nội and `01/01` on a laptop in UTC. A shared expense has one date: the date
 * it happened for the group that ate the meal. Whose airport a member is
 * standing in must not move it.
 *
 * That bug is invisible to whoever writes the test, because it only shows up
 * where the machine's clock disagrees -- it passed locally at +07 and failed in
 * CI at UTC, which is the only reason it was ever seen.
 *
 * Shifting the instant and reading its UTC parts is the whole conversion.
 * `Intl`/`toLocaleString` with a `timeZone` would be the obvious tool and is
 * refused for the reason at the top of this file: Hermes ships without full ICU
 * and would silently answer in the wrong zone on a phone while looking correct
 * on web.
 */
export function ngayNgan(iso: string): string {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return "";
  const vn = new Date(at.getTime() + PHUT_LECH_VN * 60_000);
  const dd = `${vn.getUTCDate()}`.padStart(2, "0");
  const mm = `${vn.getUTCMonth() + 1}`.padStart(2, "0");
  return `${dd}/${mm}`;
}

/** What a movement was for, without ever printing a bare id. */
export function moTaGiaoDich(movement: Movement): string {
  const who = movement.counterparty_name;
  if (movement.direction === "in") {
    return who ? `${who} đã chuyển cho bạn` : "Bạn nhận được";
  }
  return who ? `Bạn đã trả ${who}` : "Bạn đã thanh toán";
}

/**
 * How many movements the server will ever send back in one read.
 *
 * `ApiService.FINANCE_MOVEMENT_LIMIT`, copied because the response carries no
 * total and no cursor -- so a full page is the only signal the client gets
 * that there may be more. Duplicating a server constant is a drift risk and
 * the honest one to take: the alternative is a screen that silently presents
 * twenty rows as the whole history.
 */
export const SO_GIAO_DICH_TOI_DA = 20;

/**
 * The line under a full page, or nothing.
 *
 * Mockup 07.02 puts *Xem tất cả* beside this list. There is no route behind
 * it -- `GET /people/{id}/finance` takes no offset -- so the screen says what
 * it is showing instead of drawing a link that opens nothing. A truncated
 * list presented as a complete one is the reading a person would use to
 * conclude a transfer never happened.
 */
export function ghiChuGioiHan(movements: readonly Movement[]): string | null {
  if (movements.length < SO_GIAO_DICH_TOI_DA) return null;
  return `Đây là ${SO_GIAO_DICH_TOI_DA} giao dịch gần nhất. Máy chủ chưa có đường đọc phần cũ hơn.`;
}

export class FinanceError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "FinanceError";
  }
}

/**
 * Ask the server what this person's money looks like right now.
 *
 * Self-only at the server, so the actor header and the path id are the same
 * person by construction rather than by the caller remembering. Passing a
 * different pair is a 403, which is the rule working.
 *
 * No caching and no fallback data. This screen exists to show that the numbers
 * moved; a stale copy served while the network is down would show that they
 * did not.
 */
export async function layTaiChinh(
  personId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<Finance> {
  let response: Response;
  try {
    response = await fetchImpl(`${BASE_URL}/people/${personId}/finance`, {
      headers: headerNguoiGoi(personId, { roles: "member" }),
    });
  } catch {
    // Names the address it tried. "Không kết nối được" on its own sends
    // somebody to check their wifi when the real answer is that the phone is
    // pointed at the laptop's localhost.
    throw new FinanceError(0, `Không gọi được ${BASE_URL}`);
  }
  if (!response.ok) {
    let code = "";
    try {
      code = ((await response.json()) as { code?: string }).code ?? "";
    } catch {
      code = "";
    }
    throw new FinanceError(response.status, loiTaiChinh(response.status, code));
  }
  return (await response.json()) as Finance;
}

/** Refusals in words the person reading them can act on. */
export function loiTaiChinh(status: number, code: string): string {
  if (code === "not_your_finances") return "Chỉ chính chủ xem được phần tài chính này.";
  if (status === 401) return "Chưa đăng nhập nên chưa hỏi được máy chủ.";
  if (status >= 500) return "Máy chủ đang lỗi, chưa đọc được sổ.";
  return `Máy chủ trả lỗi ${status}.`;
}
