/** Reading a group's finished trips off the API, and shaping them for the wall.
 *
 * Nothing here computes money. `split_total_vnd` arrives already summed from
 * `confirmed_allocations`, and the total across trips arrives summed too --
 * adding the trips up in this file would be a second implementation of the one
 * arithmetic this product cannot afford to have two of. The screen renders what
 * it is given.
 *
 * Formatting is not computing. Grouping digits and writing a date range change
 * how a number reads, never what it is.
 *
 * Split out of the component for the same reason `ca-nhan/tai-chinh.ts` is: the
 * parts worth testing -- the date range, the stop summary, the failure text --
 * are testable here without rendering anything.
 */
import { BASE_URL } from "../../api";
import { headerNguoiGoi } from "../../danh-tinh";
import { DEMO_GROUP_NAME } from "../../rudi/nhom-demo";
// Read from the chat lane's module, never edited here. It is the one place the
// seed's `uuid5` key derivation is implemented on this side, and a second copy
// is a copy that drifts the day the namespace changes.
import { khoaGhi } from "../chat/uuid5";

/** One stop on a trip's timeline, in the order the group built it. */
export type Chang = {
  position: number;
  /** Wall-clock `HH:MM`. Never a timestamp: a stop has no timezone. */
  at: string;
  label: string;
  place_name: string | null;
};

/** One finished trip, as the server describes it. */
export type BuoiDiChoi = {
  outing_id: string;
  title: string;
  /** `YYYY-MM-DD`, Vietnam's calendar days. */
  starts_on: string;
  ends_on: string;
  headcount: number;
  stops: Chang[];
  /** Đồng, integer, recomputed from the ledger on the request that asked. */
  split_total_vnd: number;
  expense_count: number;
  memory_count: number;
};

export type KyUc = {
  context_id: string;
  outings: BuoiDiChoi[];
  split_total_vnd: number;
};

/**
 * Money as Vietnamese writes it: `860.000đ`.
 *
 * Duplicated from `ca-nhan/tai-chinh.ts` rather than imported across screens,
 * and the reason it is not shared is worth stating: the two screens belong to
 * different lanes, and a shared formatter is a file two people edit for two
 * different reasons. `Intl` is refused for both of them -- Hermes ships without
 * full ICU, `toLocaleString` falls back to the C locale, and a demo showing
 * `860,000đ` to Vietnamese viewers reads as a foreign product. That failure is
 * invisible on web, where Intl works fine.
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

/**
 * `21 – 23/08/2030`, or `23/08/2030` when the trip was a single evening.
 *
 * The strings are parsed by hand rather than through `new Date(...)`. A bare
 * `YYYY-MM-DD` is parsed as UTC midnight by the ECMAScript spec, and reading it
 * back with `getDate()` answers in the *device's* zone -- so a trip that ended
 * on the 23rd renders as the 22nd on any phone west of Greenwich. These are
 * calendar days that were never instants; turning them into one to print them
 * is the whole bug.
 */
export function khoangNgay(startsOn: string, endsOn: string): string {
  const start = ngay(startsOn);
  const end = ngay(endsOn);
  if (!start || !end) return "";
  if (startsOn === endsOn) return `${end.d}/${end.m}/${end.y}`;
  if (start.y === end.y && start.m === end.m) {
    return `${start.d} – ${end.d}/${end.m}/${end.y}`;
  }
  if (start.y === end.y) return `${start.d}/${start.m} – ${end.d}/${end.m}/${end.y}`;
  return `${start.d}/${start.m}/${start.y} – ${end.d}/${end.m}/${end.y}`;
}

function ngay(iso: string): { d: string; m: string; y: string } | null {
  const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!parts) return null;
  return { y: parts[1], m: parts[2], d: parts[3] };
}

/** How many nights the trip ran, for the caption under its title. */
export function soNgay(startsOn: string, endsOn: string): number {
  const start = ngay(startsOn);
  const end = ngay(endsOn);
  if (!start || !end) return 1;
  // Both are calendar days, so building a UTC instant from each and
  // subtracting is exact -- no zone is involved on either side.
  const from = Date.UTC(+start.y, +start.m - 1, +start.d);
  const to = Date.UTC(+end.y, +end.m - 1, +end.d);
  return Math.max(1, Math.round((to - from) / 86_400_000) + 1);
}

/**
 * The places a trip actually went, for the one-line summary on the card.
 *
 * A stop without a `place_name` is a real stop -- "Đi chợ", "Nướng sân thượng"
 * -- so it contributes its label rather than being dropped. Dropping it would
 * make a trip with three unnamed stops read as a trip that went nowhere.
 */
export function tomTatChang(stops: Chang[]): string {
  const names = stops.map((s) => s.place_name ?? s.label).filter((s) => s.length > 0);
  if (names.length === 0) return "";
  if (names.length <= 3) return names.join(" · ");
  return `${names.slice(0, 3).join(" · ")} · +${names.length - 3}`;
}

/**
 * Which group's wall to read, when the URL did not name one.
 *
 * There is no route that answers "which groups am I in", so the demo group is
 * found the way the rest of the demo already finds it: `POST /contexts` under
 * the seed's own idempotency key, which replays and hands back the group the
 * seed created rather than making a second one. `khoaGhi` derives that key with
 * the same `uuid5` the seed script uses.
 *
 * The replay header is read, and that is the point of doing it this way rather
 * than firing the request and taking the id. On a stack nobody seeded there is
 * nothing to replay, so this call *creates* an empty group -- and an empty wall
 * for a group that never existed reads exactly like a group that has been
 * nowhere. `daCoSan` carries that difference up to the screen so it can say
 * which one happened instead of showing eight silent zeroes.
 */
export async function timNhomDemo(
  personId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<{ contextId: string; daCoSan: boolean }> {
  let response: Response;
  try {
    response = await fetchImpl(`${BASE_URL}/contexts`, {
      method: "POST",
      headers: headerNguoiGoi(personId, {
        roles: "group_admin,member",
        key: khoaGhi("context"),
      }),
      body: JSON.stringify({ display_name: DEMO_GROUP_NAME }),
    });
  } catch {
    throw new KyUcError(0, `Không gọi được ${BASE_URL}`);
  }
  if (!response.ok) {
    throw new KyUcError(response.status, loiKyUc(response.status, ""));
  }
  const body = (await response.json()) as { id?: unknown };
  if (typeof body.id !== "string") {
    throw new KyUcError(response.status, "Máy chủ không trả id nhóm.");
  }
  return {
    contextId: body.id,
    daCoSan: response.headers.get("Idempotency-Replayed") === "true",
  };
}

export class KyUcError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "KyUcError";
  }
}

/**
 * Ask the server what this group has been through.
 *
 * Group-private at the server: a non-member gets 403 whatever roles the header
 * claims. No caching and no fallback data -- a stale wall served while the
 * network is down would say the group has done nothing since, which is a
 * different statement from "we could not ask".
 */
export async function layKyUc(
  contextId: string,
  personId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<KyUc> {
  let response: Response;
  try {
    response = await fetchImpl(`${BASE_URL}/contexts/${contextId}/recap`, {
      headers: headerNguoiGoi(personId, { roles: "member", contexts: contextId }),
    });
  } catch {
    // Names the address it tried. "Không kết nối được" on its own sends
    // somebody to check their wifi when the real answer is that the phone is
    // pointed at the laptop's localhost.
    throw new KyUcError(0, `Không gọi được ${BASE_URL}`);
  }
  if (!response.ok) {
    let code = "";
    try {
      code = ((await response.json()) as { code?: string }).code ?? "";
    } catch {
      code = "";
    }
    throw new KyUcError(response.status, loiKyUc(response.status, code));
  }
  return (await response.json()) as KyUc;
}

/** Refusals in words the person reading them can act on. */
export function loiKyUc(status: number, code: string): string {
  if (code === "permission_denied" || status === 403) {
    return "Kỷ niệm là của riêng nhóm. Bạn cần là thành viên mới xem được.";
  }
  if (status === 401) return "Chưa đăng nhập nên chưa hỏi được máy chủ.";
  if (status === 404) return "Không tìm thấy nhóm này.";
  if (status >= 500) return "Máy chủ đang lỗi, chưa đọc được sổ.";
  return `Máy chủ trả lỗi ${status}.`;
}
