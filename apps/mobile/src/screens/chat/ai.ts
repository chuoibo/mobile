/** Why the AI turn has five outcomes and not two.
 *
 * THIS FILE WAS REWRITTEN AGAINST THE REAL CONTRACT. The first version was
 * written while rd-be-04 was unmerged and guessed the wire: it POSTed
 * `{after_message_id}`, read `{speak: false}`, and looked for `kind:
 * "ai_card"` at the top level of the body. rd-be-04 landed (main @ 7e1db9a)
 * and the route takes NO body and answers `CompanionTurnResponse`:
 * `{context_id, spoke, reason, message}`. Every field the guess read is
 * absent, so the guessed client would have classified every real answer as
 * `hong` while its tests stayed green against the guessed shape.
 *
 * The interesting part is `spoke: false`, which arrives for six different
 * reasons that are NOT the same event:
 *
 *   no_conversation · already_spoke_last · rate_limited · cooldown
 *       -- `plan_turn` decided not to speak. This is the ceiling working.
 *          An AI that answers every message is annoying, not clever. Show
 *          nothing at all; there is no news here.
 *
 *   unavailable
 *       -- the model call itself failed: no key, a network fault, a
 *          malformed answer. Folding this into silence is the tempting bug,
 *          and it is the dishonest one. A deployment with no GEMINI_API_KEY
 *          would then look exactly like an AI that read the thread and had
 *          nothing to add, forever, and nobody would ever find out.
 *
 *   ungrounded
 *       -- the model named a place that is not in the server catalogue, so
 *          `ground_card` threw away the WHOLE card (rd-be-04 QĐ-2: rejecting
 *          the card is observable, quietly dropping one stop is not). This is
 *          the anti-fabrication guard firing. It is the system behaving
 *          correctly, but it is still a reason the user saw no answer, so it
 *          gets its own calm sentence rather than being hidden.
 *
 * There is a ninth outcome that never arrives in `reason` at all: HTTP 429
 * from the per-person ceiling, 30 turns in 60 seconds, checked BEFORE the
 * cadence rules ever run. It is the same class of event as `rate_limited` and
 * is drawn the same way, so it lives in the sentence table beside them rather
 * than in the generic error path, whose only reason to exist is a status
 * nobody predicted.
 *
 * `chua-noi-duoc` survives from the first version for one honest reason: a
 * 404 still means this build of the API predates rd-be-04, and the app can be
 * pointed at an older server than the one on main today.
 *
 * Activation has TWO shapes, and the difference decides how silence is drawn.
 *
 * The original shape is "a new text just landed in the group": the client
 * offers a turn and the companion volunteers or does not. Nobody is waiting on
 * an answer, so `cooldown` and `already_spoke_last` draw nothing.
 *
 * The second shape is a person pressing "Hỏi Rủ Đi AI". That turn carries
 * `{"requested": true}`, which the server (PR 378) reads as permission to skip
 * the cadence rules -- not the per-window ceiling, which is the bill. And here
 * the same `spoke: false` means something else entirely: a question was asked
 * and dropped on the floor. So `hoiThang` turns every silence into a
 * `khong-tra-loi-duoc` with a sentence. The user pressed a button; a screen
 * that does not move afterwards is indistinguishable from a dead app, and that
 * is the exact defect this flag exists to fix.
 *
 * The flag is sent ONLY on the asked turn. Setting it on every turn would buy
 * nothing (the ceiling is unchanged) and cost the cadence: the companion would
 * answer every single line of a fast exchange.
 *
 * Nothing here ever renders a sentence this client wrote as though the model
 * wrote it. The only text that reaches a bubble comes from `message.card`.
 */

import { chiTietLoi } from "../../ui/loi-tren-man";
import { headerNguoiGoi } from "../../danh-tinh";
import { parseMessage, type MessageWire } from "./tin-nhan";

declare const process: { env: Record<string, string | undefined> };

export const AI_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8099";

/** Named in the UI so a 404 is attributable rather than mysterious. */
export const AI_WORK_ITEM = "rd-be-04";

/** The reasons `plan_turn` gives for staying quiet on purpose. Anything else
 *  with `spoke: false` is a failure to answer, not a decision not to. */
export const LY_DO_IM_LANG = [
  "no_conversation",
  "already_spoke_last",
  "rate_limited",
  "cooldown",
] as const;

/** The subset of those that are pure cadence: rules written for a companion
 *  that VOLUNTEERS. `requested: true` lifts exactly these on the server, so
 *  seeing one come back on an asked turn means the API predates PR 378. */
export const LY_DO_NHIP = ["already_spoke_last", "rate_limited", "cooldown"] as const;

/** The one reason that never arrives in `reason`.
 *
 *  The per-person ceiling on this route answers HTTP 429 with a body whose
 *  `code` is this string; the 200 vocabulary never mentions it. Named here so
 *  the sentence table has one key per outcome a person can hit, and so the
 *  status-code branch and the copy cannot drift apart. */
export const LY_DO_TRAN_PHUT = "companion_turn_rate_limited";

export type AiTurnState =
  /** The companion read the thread and chose not to speak. Draw nothing. */
  | { kind: "im-lang"; reason: string }
  /** A grounded card came back. Draw it. */
  | { kind: "da-noi"; message: MessageWire }
  /** Asked, but no usable answer: the model failed, or it tried to invent a
   *  place and the server refused the card. Say which, calmly. */
  | { kind: "khong-tra-loi-duoc"; reason: string; cau: string }
  /** This API build predates rd-be-04. Not an error; the app is ahead. */
  | { kind: "chua-noi-duoc"; url: string; cau: string }
  /** Anything else. Status and the server's own words. */
  | { kind: "hong"; url: string; status: number; detail: string };

/**
 * The calm sentence a 404/405 turns into.
 *
 * Kept as a function so the screen and the test assert the same words, and so
 * those words cannot drift into an error tone without the test noticing.
 * Names the work item and the address; does not say "lỗi".
 */
export function cauAiChuaNoiDuoc(url: string): string {
  return `AI chưa nối vào máy chủ này. Việc còn nợ là ${AI_WORK_ITEM}. Địa chỉ đã thử: ${url}.`;
}

/**
 * One sentence per outcome, and no two the same.
 *
 * Every silence used to collapse into three sentences: the three cadence
 * reasons shared one, and `unavailable` shared the catch-all with any name a
 * later server might invent. Two people hitting two different ceilings read
 * the same words, so neither could tell what to do next, and the one outcome
 * that means "the AI is down" was written in the same voice as the one that
 * means "keep chatting".
 *
 * Rules the wording follows, each of them load-bearing:
 *
 *  - **Say what unblocks it, in the unit that actually unblocks it.** The
 *    90-second rule is a clock, so its sentence gives seconds. The window
 *    ceiling is 3 companion turns inside the last 20 messages, which is a
 *    COUNT: waiting changes nothing there and only new messages push the old
 *    turns out of the window, so promising "thử lại sau N phút" would be a
 *    clock that does not exist. The per-person 429 is a real 60-second
 *    window, and that one does say a minute.
 *  - **Never print the server's own machine words.** The 429 body carries
 *    `companion_turn_rate_limited`; before this, that string reached the
 *    screen through the generic error path, under "Máy chủ trả lỗi 429".
 *  - **Never say why the model failed.** `unavailable` covers a missing key,
 *    a provider 429, a timeout and a malformed answer (PR 420), and the
 *    server drops the difference on purpose because the provider's error text
 *    can carry the API key and the group's own words. The sentence says the
 *    AI side is down and that the group did nothing wrong, which is the whole
 *    of what is known.
 *  - **No "lỗi", no status codes, no em dash.**
 *
 * The numbers 90, 3 and 20 are `DEFAULT_LIMITS` in `app/domain/companion.py`;
 * 60 is `RECEIPT_SCAN_WINDOW_SECONDS`, which the companion limiter reuses.
 * `cau-chu-im-lang.test.mjs` reads them back out of the Python and fails if
 * this copy still quotes an old number.
 */
export const CAU_THEO_LY_DO: Readonly<Record<string, string>> = {
  // Asked before anyone said anything. There is nothing to answer, and that is
  // the one silence a person can fix in one move.
  no_conversation:
    "Nhóm chưa có tin nhắn nào để Rủ Đi AI đọc. Gửi một tin trước rồi hỏi lại nhé.",
  // Cadence, reachable on an asked turn only against a server that predates
  // PR 378 and ignored the flag. Still gets a true sentence rather than a
  // sentence about the server's version: what the person can see is that the
  // companion spoke last, and that is what it says.
  already_spoke_last:
    "Rủ Đi AI là người nhắn sau cùng nên nó đang đợi nhóm đáp lại. Nhắn thêm một tin rồi hỏi lại nhé.",
  cooldown:
    "Rủ Đi AI vừa lên tiếng cách đây chưa tới 90 giây nên đang nhường lượt cho nhóm nói. Chờ đủ 90 giây kể từ lượt đó rồi hỏi lại nhé.",
  // Same ceiling as `asked_too_often`, different event: here the companion
  // chose not to volunteer, and nobody was waiting.
  rate_limited:
    "Rủ Đi AI đã nói 3 lượt trong 20 tin gần đây nên đang tạm nghỉ cho nhóm nói. Nhóm nhắn thêm vài tin rồi hỏi lại nhé.",
  // The per-window ceiling refusing under its own name because the turn was
  // asked for. It is the bill working, not a fault. Leads with the question
  // being the thing that was dropped, because to the person who pressed the
  // button that is the news.
  asked_too_often:
    "Câu vừa hỏi chưa tới lượt: Rủ Đi AI đã nói 3 lượt trong 20 tin gần đây. Nhóm nhắn thêm vài tin rồi hỏi lại nhé.",
  // The one outcome that is not the product working as designed.
  unavailable:
    "Rủ Đi AI đang không gọi được sang bên mô hình nên lượt này chưa có câu trả lời. Thử lại sau khoảng một phút; nếu vẫn vậy thì phần AI đang tắt chứ không phải nhóm làm gì sai.",
  // The anti-fabrication guard firing. Worth saying plainly, because "cả thẻ
  // bị bỏ" is the reason the screen is empty and it is a decision, not a fault.
  ungrounded:
    "Rủ Đi AI có trả lời nhưng nhắc tới một chỗ không có trong danh sách địa điểm của Rủ Đi, nên cả thẻ đã bị bỏ để không giới thiệu nhầm. Hỏi lại một lần nữa nhé.",
  // HTTP 429. The count is deliberately not quoted: 30 is a server constant
  // this client cannot read at runtime, and a stale number would be worse
  // than none. The minute is the part that tells a person what to do.
  [LY_DO_TRAN_PHUT]:
    "Bạn hỏi Rủ Đi AI hơi nhiều lượt trong một phút vừa rồi nên phần hỏi đang tạm nghỉ. Thử lại sau khoảng một phút nhé.",
  // Client-side only: a 204 or an empty 200 body. Not in the server vocabulary.
  no_content:
    "Máy chủ nhận câu hỏi nhưng trả về một lượt rỗng. Chưa có câu trả lời nào để hiện.",
};

/**
 * Pressed before the group finished opening.
 *
 * Client-side only, and deliberately not a `reason`: no request was made, so
 * the server never had an opinion. `hoiThangAi` returns early while `nhom` is
 * still loading, and measured in Chrome that early press sent NO request and
 * painted NOTHING: no turn, no banner, not even the "Đang hỏi…" label. A
 * button that answers a press with an unchanged screen is the exact defect the
 * asked turn exists to fix, so the early return says so instead.
 */
export const CAU_NHOM_CHUA_MO_XONG =
  "Nhóm chat còn đang mở. Chờ một chút cho nhóm hiện ra rồi hỏi lại nhé.";

/** The sentence shown for a `reason` this build has never heard of.
 *
 *  A later server adding a name lands here rather than on a blank screen. It
 *  promises nothing about why, because nothing is known. */
export const CAU_LY_DO_LA = "Rủ Đi AI chưa trả lời được lượt này. Thử nhắn thêm một tin rồi hỏi lại nhé.";

/**
 * The sentence for one reason.
 *
 * Kept as a function so the screen and the test assert the same words. Never
 * echoes anything the server sent: the reason is used as a key, never printed.
 */
export function cauKhongTraLoiDuoc(reason: string): string {
  return CAU_THEO_LY_DO[reason] ?? CAU_LY_DO_LA;
}

export function aiTurnUrl(base: string, contextId: string): string {
  return `${base.replace(/\/$/, "")}/contexts/${contextId}/ai-turn`;
}

function headers(actorId: string, contextId: string, key?: string): Record<string, string> {
  return headerNguoiGoi(actorId, {
    roles: "group_admin,member",
    contexts: contextId,
    key,
  });
}

async function docLoi(res: {
  status: number;
  json: () => Promise<unknown>;
  text: () => Promise<string>;
}): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown; code?: unknown };
    if (typeof body?.detail === "string" && body.detail.trim()) return body.detail;
    if (typeof body?.code === "string" && body.code.trim()) return body.code;
  } catch {
    /* not JSON */
  }
  try {
    const text = (await res.text()).slice(0, 200);
    if (text) return text;
  } catch {
    /* already consumed */
  }
  return `HTTP ${res.status}`;
}

/**
 * Silence, resolved against who was waiting for it.
 *
 * One function so the 204 path and the `spoke: false` path cannot drift into
 * answering the same question two ways.
 */
function yenHoacNoiRa(reason: string, hoiThang: boolean): AiTurnState {
  if (hoiThang) return { kind: "khong-tra-loi-duoc", reason, cau: cauKhongTraLoiDuoc(reason) };
  return { kind: "im-lang", reason };
}

/** Classify one 200 body. Exported so the test can drive it without a fetch. */
export function docThanAiTurn(
  raw: unknown,
  url: string,
  opts: { hoiThang?: boolean } = {},
): AiTurnState {
  const hoiThang = opts.hoiThang === true;
  const body = raw !== null && typeof raw === "object" && !Array.isArray(raw)
    ? (raw as Record<string, unknown>)
    : null;
  if (!body) {
    return {
      kind: "hong",
      url,
      status: 200,
      detail: "máy chủ trả về một thân không phải đối tượng",
    };
  }

  const reason = typeof body.reason === "string" ? body.reason : "";

  if (body.spoke === true) {
    try {
      return { kind: "da-noi", message: parseMessage(body.message, "ai-turn.message") };
    } catch (e) {
      return { kind: "hong", url, status: 200, detail: chiTietLoi(e) };
    }
  }

  if (body.spoke === false) {
    if ((LY_DO_IM_LANG as readonly string[]).includes(reason)) {
      // Only silent when nobody asked. A person who pressed the button gets a
      // sentence for the same body, because to them this IS the answer.
      return yenHoacNoiRa(reason, hoiThang);
    }
    // `unavailable`, `ungrounded`, and any reason a later server adds. An
    // unknown reason is treated as a failure to answer rather than as
    // silence, because silence is the state that hides things.
    return { kind: "khong-tra-loi-duoc", reason, cau: cauKhongTraLoiDuoc(reason) };
  }

  return {
    kind: "hong",
    url,
    status: 200,
    detail: "máy chủ trả lời nhưng không nói là đã nói hay chưa",
  };
}

/**
 * Call the AI turn once. Never throws.
 *
 * The route takes no body: the server reads the last 40 messages itself and
 * `plan_turn` decides from metadata alone. There is nothing for the client to
 * point at, and passing a message id would suggest the client picks the
 * window when it does not.
 */
export async function goiAiTurn(opts: {
  contextId: string;
  actorId: string;
  idempotencyKey?: string;
  base?: string;
  /** A person asked for this turn. Buys no permission and no extra data: same
   *  address, same headers, same membership check. It lifts the cadence only,
   *  and it changes how silence is drawn on this side. */
  hoiThang?: boolean;
}): Promise<AiTurnState> {
  const base = opts.base ?? AI_BASE_URL;
  const url = aiTurnUrl(base, opts.contextId);
  const hoiThang = opts.hoiThang === true;

  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: headers(opts.actorId, opts.contextId, opts.idempotencyKey),
      // Nothing at all on an offered turn. The route's body is optional and the
      // shipped client has always posted zero bytes under a JSON content type;
      // sending `{"requested": false}` here would be the same request with a
      // new way to fail on any server that has not taken PR 378 yet.
      ...(hoiThang ? { body: JSON.stringify({ requested: true }) } : {}),
    });
  } catch (e) {
    return { kind: "hong", url, status: 0, detail: chiTietLoi(e) };
  }

  if (res.status === 404 || res.status === 405) {
    return { kind: "chua-noi-duoc", url, cau: cauAiChuaNoiDuoc(url) };
  }
  // 204 is read as silence without touching the body: some stacks reject
  // `json()` on an empty response, and that rejection is not a server fault.
  if (res.status === 204) return yenHoacNoiRa("no_content", hoiThang);
  // The per-person ceiling, 30 turns in 60 seconds, and the only 429 this
  // route can produce. Handled here rather than by the generic error path for
  // two reasons. The body is `{code: "companion_turn_rate_limited", detail:
  // …}` and `docLoi` would put that English code on screen under "Máy chủ trả
  // lỗi 429", which is a machine word in front of a person. And it is a
  // ceiling, not a fault: same class as `rate_limited`, so it draws nothing on
  // a turn nobody asked for and a calm timed sentence on one that was asked.
  // The body is deliberately not read; the sentence must not depend on the
  // server's wording, and there is nothing in it this client would trust.
  if (res.status === 429) return yenHoacNoiRa(LY_DO_TRAN_PHUT, hoiThang);
  if (!res.ok) {
    return { kind: "hong", url, status: res.status, detail: await docLoi(res) };
  }

  let raw: unknown = null;
  try {
    const text = await res.text();
    if (!text.trim()) return yenHoacNoiRa("no_content", hoiThang);
    raw = JSON.parse(text) as unknown;
  } catch (e) {
    return { kind: "hong", url, status: res.status, detail: chiTietLoi(e) };
  }
  return docThanAiTurn(raw, url, { hoiThang });
}
