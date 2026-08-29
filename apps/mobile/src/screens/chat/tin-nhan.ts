/** Why the cursor is the part this file exists to get right.
 *
 * Group messages are real (`POST`/`GET /contexts/{id}/messages`, rd-be-02).
 * The trap is not the payload, it is the direction of the page, and it is
 * the same field doing two opposite jobs:
 *
 *   * no cursor, or `before` set -> the server returns NEWEST FIRST
 *     (descending). `next_cursor` is then the OLDEST row in that page,
 *     because it is always the cursor of the last element of the array.
 *   * `after` set -> the server returns OLDEST FIRST (ascending).
 *     `next_cursor` is then the NEWEST row in that page. Same field name,
 *     opposite end of the thread, depending on which way you asked.
 *
 * The screen wants oldest on top, newest at the bottom. So the first load
 * has to reverse the array before anything is drawn, and "load older" has
 * to reverse its page before prepending. "Load newer" must not reverse.
 * Reusing `next_cursor` blindly as `before` after an `after` fetch is how
 * the thread jumps to the wrong end and then quietly duplicates.
 *
 * Dedup is by `id`, not by cursor. A page that overlaps the rows already
 * held (retries, a race with a send) must not draw the same bubble twice.
 * The synthetic `CONTEXT_ID` in `api.ts` has never had a row in `contexts`;
 * using it here is a guaranteed 403. Membership is a real database lookup,
 * not the actor header. This file talks about messages; `nhom.ts` is what
 * makes the 403 go away.
 *
 * Deliberately free of React so the order, the merge and the refusal to
 * invent a thread are checked by `tests/tin-nhan.test.mjs` rather than by
 * looking at a phone.
 */

declare const process: { env: Record<string, string | undefined> };

export const TIN_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8099";

/**
 * What to call somebody whose name this client does not have.
 *
 * The client resolves names out of `DEMO_PEOPLE`, and nothing else can: today
 * `MembershipResponse` and `MessageResponse` both carry `person_id` /
 * `author_id` and no name, and there is no `GET /people/{id}` to ask. So for
 * anybody who joined through "Tạo nhóm" or a friend QR card -- which is every
 * real person -- the name is genuinely unknown here.
 *
 * The previous answer was `id.slice(0, 8)`, which printed `2bb00000` in the
 * place a human name goes. That is worse than saying nothing: it looks like an
 * identifier the reader ought to recognise, it leaks a database key onto the
 * screen, and it is the same class of mistake as showing a server error code
 * to somebody trying to split a bill.
 *
 * One shared constant rather than a literal at each site, so the member list
 * and the chat bubble cannot drift into two different words for one state.
 */
export const TEN_CHUA_BIET = "Thành viên";

export type MessageKind = "text" | "image" | "ai_card";

export type MessageWire = {
  id: string;
  context_id: string;
  author_id: string | null;
  kind: MessageKind;
  body: string | null;
  image_url: string | null;
  card: unknown | null;
  created_at: string;
  cursor: string;
};

export type MessageListWire = {
  context_id: string;
  messages: MessageWire[];
  next_cursor: string | null;
  has_more: boolean;
};

/**
 * Everything the thread can be showing.
 *
 * Failures are split because "không nối được" and "máy chủ từ chối vì chưa
 * phải thành viên" send a person to two different places.
 */
export type TinNhanState =
  | { kind: "co-tin"; messages: MessageWire[]; hasMore: boolean; contextId: string }
  | { kind: "rong"; contextId: string }
  | { kind: "khong-noi-duoc"; url: string; detail: string }
  | { kind: "bi-cam"; url: string; status: number; detail: string }
  | { kind: "may-chu-loi"; url: string; status: number; detail: string }
  | { kind: "du-lieu-sai"; url: string; detail: string };

export type GuiTinState =
  | { kind: "xong"; message: MessageWire }
  | { kind: "khong-noi-duoc"; url: string; detail: string }
  | { kind: "may-chu-loi"; url: string; status: number; detail: string }
  | { kind: "du-lieu-sai"; url: string; detail: string };

const KINDS: ReadonlySet<string> = new Set(["text", "image", "ai_card"]);

function str(v: unknown, field: string): string {
  if (typeof v !== "string" || v.trim() === "") {
    throw new Error(`${field} phải là chuỗi không rỗng`);
  }
  return v;
}

function strOrNull(v: unknown, field: string): string | null {
  if (v === null || v === undefined) return null;
  if (typeof v !== "string") {
    throw new Error(`${field} phải là chuỗi hoặc null`);
  }
  return v;
}

export function parseMessage(raw: unknown, field: string): MessageWire {
  const m = raw as Record<string, unknown>;
  const kind = m?.kind;
  if (typeof kind !== "string" || !KINDS.has(kind)) {
    throw new Error(`${field}.kind phải là text|image|ai_card, nhận được ${JSON.stringify(kind)}`);
  }
  const author = m.author_id;
  if (author !== null && author !== undefined && typeof author !== "string") {
    throw new Error(`${field}.author_id phải là UUID hoặc null`);
  }
  return {
    id: str(m.id, `${field}.id`),
    context_id: str(m.context_id, `${field}.context_id`),
    author_id: author === undefined ? null : (author as string | null),
    kind: kind as MessageKind,
    body: strOrNull(m.body, `${field}.body`),
    image_url: strOrNull(m.image_url, `${field}.image_url`),
    card: m.card ?? null,
    created_at: str(m.created_at, `${field}.created_at`),
    cursor: str(m.cursor, `${field}.cursor`),
  };
}

export function parseMessageList(raw: unknown): MessageListWire {
  const b = raw as Record<string, unknown>;
  if (!Array.isArray(b?.messages)) throw new Error("thiếu mảng `messages`");
  if (typeof b.has_more !== "boolean") throw new Error("`has_more` phải là boolean");
  const next = b.next_cursor;
  if (next !== null && next !== undefined && typeof next !== "string") {
    throw new Error("`next_cursor` phải là chuỗi hoặc null");
  }
  return {
    context_id: str(b.context_id, "context_id"),
    messages: b.messages.map((m, i) => parseMessage(m, `messages[${i}]`)),
    next_cursor: next ?? null,
    has_more: b.has_more,
  };
}

/**
 * First load: server sent newest-first. Display wants oldest on top.
 *
 * A slice-reverse rather than a mutation, because the same array is what
 * `next_cursor` was computed from and we do not want those two to disagree
 * after a later in-place sort.
 */
export function tinHienThiLanDau(messages: MessageWire[]): MessageWire[] {
  return messages.slice().reverse();
}

export function khuTrungTheoId(messages: MessageWire[]): MessageWire[] {
  const seen = new Set<string>();
  const out: MessageWire[] = [];
  for (const m of messages) {
    if (seen.has(m.id)) continue;
    seen.add(m.id);
    out.push(m);
  }
  return out;
}

/**
 * An older page is also newest-first. Reverse it, then put it in front of
 * what is already on screen. Dedup keeps a retry from doubling the seam.
 */
export function noiTinCuHon(dangGiu: MessageWire[], trangGiamDan: MessageWire[]): MessageWire[] {
  return khuTrungTheoId([...tinHienThiLanDau(trangGiamDan), ...dangGiu]);
}

/**
 * A newer page is already oldest-first. Append, and drop ids we already have
 * so a send that races with a poll cannot draw two copies of one bubble.
 */
export function noiTinMoiHon(dangGiu: MessageWire[], trangTangDan: MessageWire[]): MessageWire[] {
  return khuTrungTheoId([...dangGiu, ...trangTangDan]);
}

/** Cursor of the oldest message on screen. That is what `before` wants. */
export function cursorCuNhat(messages: MessageWire[]): string | null {
  return messages[0]?.cursor ?? null;
}

/** Cursor of the newest message on screen. That is what `after` wants. */
export function cursorMoiNhat(messages: MessageWire[]): string | null {
  if (messages.length === 0) return null;
  return messages[messages.length - 1]!.cursor;
}

function headers(actorId: string, contextId: string, key?: string): Record<string, string> {
  const h: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
    "X-Actor-ID": actorId,
    "X-Actor-Roles": "group_admin,member",
    "X-Actor-Contexts": contextId,
  };
  if (key) h["Idempotency-Key"] = key;
  return h;
}

export function messagesUrl(
  base: string,
  contextId: string,
  opts: { limit?: number; before?: string; after?: string } = {},
): string {
  const params = new URLSearchParams();
  params.set("limit", String(opts.limit ?? 50));
  if (opts.before) params.set("before", opts.before);
  if (opts.after) params.set("after", opts.after);
  return `${base.replace(/\/$/, "")}/contexts/${contextId}/messages?${params.toString()}`;
}

async function docLoi(res: { status: number; json: () => Promise<unknown>; text: () => Promise<string> }): Promise<string> {
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

export type NapOpts = {
  contextId: string;
  actorId: string;
  before?: string;
  after?: string;
  limit?: number;
  dangGiu?: MessageWire[];
  hasMore?: boolean;
  base?: string;
};

/**
 * Ask the server for a page, and turn every way that can go wrong into a
 * state the screen knows how to say out loud.
 *
 * Never throws. A rejected promise here would surface as a blank tab.
 *
 * `before` and `after` are taken from `cursorCuNhat` / `cursorMoiNhat` of
 * the messages already held, never from the previous page's `next_cursor`
 * by habit: that field flips meaning with direction.
 */
export async function napTinNhan(opts: NapOpts): Promise<TinNhanState> {
  const base = opts.base ?? TIN_BASE_URL;
  const url = messagesUrl(base, opts.contextId, {
    limit: opts.limit,
    before: opts.before,
    after: opts.after,
  });

  let res: Response;
  try {
    res = await fetch(url, { headers: headers(opts.actorId, opts.contextId) });
  } catch (e) {
    return { kind: "khong-noi-duoc", url, detail: (e as Error).message };
  }

  if (res.status === 403) {
    return { kind: "bi-cam", url, status: 403, detail: await docLoi(res) };
  }
  if (!res.ok) {
    return { kind: "may-chu-loi", url, status: res.status, detail: await docLoi(res) };
  }

  try {
    const page = parseMessageList(await res.json());
    const dangGiu = opts.dangGiu ?? [];
    let merged: MessageWire[];
    let hasMore: boolean;
    if (opts.after) {
      merged = noiTinMoiHon(dangGiu, page.messages);
      // An `after` page's has_more is about newer rows. The "load older"
      // button still cares about the older direction, so keep what we had.
      hasMore = opts.hasMore ?? false;
    } else if (opts.before) {
      merged = noiTinCuHon(dangGiu, page.messages);
      hasMore = page.has_more;
    } else {
      merged = tinHienThiLanDau(page.messages);
      hasMore = page.has_more;
    }
    if (merged.length === 0) return { kind: "rong", contextId: opts.contextId };
    return { kind: "co-tin", messages: merged, hasMore, contextId: opts.contextId };
  } catch (e) {
    return { kind: "du-lieu-sai", url, detail: (e as Error).message };
  }
}

export async function napTinCuHon(opts: NapOpts & { dangGiu: MessageWire[] }): Promise<TinNhanState> {
  const before = cursorCuNhat(opts.dangGiu);
  if (!before) return napTinNhan({ ...opts, before: undefined, after: undefined, dangGiu: undefined });
  return napTinNhan({ ...opts, before, after: undefined });
}

export async function napTinMoiHon(opts: NapOpts & { dangGiu: MessageWire[] }): Promise<TinNhanState> {
  const after = cursorMoiNhat(opts.dangGiu);
  if (!after) return napTinNhan({ ...opts, before: undefined, after: undefined, dangGiu: undefined });
  return napTinNhan({ ...opts, after, before: undefined });
}

/**
 * Post one text message. `image_url` and `card` are sent as null because the
 * server 422s `message_payload_invalid` when a text carries either.
 *
 * The idempotency key is the caller's. Mint it on the press, not inside a
 * retry: the server fingerprints method + path + body, and a new key on the
 * same bytes is a second write.
 */
export async function guiTinNhan(opts: {
  contextId: string;
  actorId: string;
  body: string;
  idempotencyKey: string;
  base?: string;
}): Promise<GuiTinState> {
  const base = opts.base ?? TIN_BASE_URL;
  const url = `${base.replace(/\/$/, "")}/contexts/${opts.contextId}/messages`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: headers(opts.actorId, opts.contextId, opts.idempotencyKey),
      body: JSON.stringify({ kind: "text", body: opts.body, image_url: null, card: null }),
    });
  } catch (e) {
    return { kind: "khong-noi-duoc", url, detail: (e as Error).message };
  }
  if (!res.ok) {
    return { kind: "may-chu-loi", url, status: res.status, detail: await docLoi(res) };
  }
  try {
    return { kind: "xong", message: parseMessage(await res.json(), "message") };
  } catch (e) {
    return { kind: "du-lieu-sai", url, detail: (e as Error).message };
  }
}

/**
 * Post one `ai_card`. This is how F17 opens a poll and how it casts a ballot,
 * because there is no `/polls` route to post either one to.
 *
 * `body` and `image_url` are sent as null: the server 422s
 * `message_payload_invalid` when an `ai_card` carries either, the mirror of
 * the rule `guiTinNhan` obeys above.
 *
 * Naming it "ai_card" while a person is the author reads wrong, and it is
 * worth being precise about why it is not: `ai_card` is the wire's name for
 * "this message is a structured card rather than prose". Authorship is a
 * separate field, and the server fills it in from the actor header --
 * `author_id=actor.id`, never from anything sent here. A ballot posted this
 * way is attributed to the person who pressed the button and to nobody else,
 * which is the property the vote count is built on.
 */
export async function guiTheAi(opts: {
  contextId: string;
  actorId: string;
  card: Record<string, unknown>;
  idempotencyKey: string;
  base?: string;
}): Promise<GuiTinState> {
  const base = opts.base ?? TIN_BASE_URL;
  const url = `${base.replace(/\/$/, "")}/contexts/${opts.contextId}/messages`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: headers(opts.actorId, opts.contextId, opts.idempotencyKey),
      body: JSON.stringify({ kind: "ai_card", body: null, image_url: null, card: opts.card }),
    });
  } catch (e) {
    return { kind: "khong-noi-duoc", url, detail: (e as Error).message };
  }
  if (!res.ok) {
    return { kind: "may-chu-loi", url, status: res.status, detail: await docLoi(res) };
  }
  try {
    return { kind: "xong", message: parseMessage(await res.json(), "message") };
  } catch (e) {
    return { kind: "du-lieu-sai", url, detail: (e as Error).message };
  }
}
