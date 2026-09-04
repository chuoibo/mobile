/** Why this screen cannot use the group id already sitting in `api.ts`.
 *
 * `CONTEXT_ID` there (`1aa00000-aaaa-…`) was minted so the expense flow had
 * *a* group to agree on across screens. It has never had a row in the
 * `contexts` table. Membership is not the actor header either: the server
 * computes `is_group_member` with `repository.is_member(context_id, actor.id)`,
 * a real query. Posting a chat message under that synthetic id is a 403
 * `permission_denied` with certainty, and the thread would then look empty
 * for a reason the empty-state copy could not name.
 *
 * That is the story of `khoiDongNhom`, which is now the *fallback*. When the
 * session has already opened a group of its own on F03/F04, `moNhomChoMan`
 * hands that one to the screen instead and only step 4 runs: the id is in
 * hand, so none of the reconstruction below is needed or wanted.
 *
 * So this file builds the group the way `scripts/seed_demo_data.py` does,
 * through the HTTP API, in four steps that are stable under retry:
 *
 *   1. `PUT /people/{id}` for the person signed in, and for `minh` (the
 *      creator). Without a people row, `POST /contexts` is a 500 on a
 *      foreign key, which is how this product used to greet every caller.
 *   2. `POST /contexts` as `minh`, idempotency key `uuid5(ns, "write:context")`.
 *      If the seed already ran, the middleware replays the original group.
 *      If it did not, this creates it and makes `minh` the admin. One call,
 *      two circumstances, one stable id.
 *   3. If the signed-in person is not `minh`: invite (as `minh`) then accept
 *      (as themselves). A 409 on accept is SUCCESS -- they are already in.
 *      Treating it as a fault would strand a seeded member behind a
 *      "could not join" banner on every launch.
 *   4. `GET /contexts/{id}/members` for the list the header prints. The
 *      number of members is this list's length, never a fixture.
 *
 * Every write carries a derived idempotency key, so pressing again replays
 * instead of doubling. Every failure names the step that died and the
 * address that was tried, because "không vào được nhóm" without either is
 * how an afternoon gets spent restarting a server that was fine.
 *
 * ---------------------------------------------------------------------------
 * The replay in step 2 is byte-fragile, and the bytes are not ours to choose.
 *
 * The server fingerprints an idempotent write as
 * `sha256(method + path + query + RAW BODY BYTES)` -- see
 * `services/api/app/api/idempotency.py`, `request_fingerprint`. Raw bytes, not
 * parsed JSON. Two encoders that agree on the value disagree on the bytes:
 *
 *   Python  json.dumps  -> {"display_name": "Team Đà Lạt"}
 *   JS      JSON.stringify -> {"display_name":"Team Đà Lạt"}
 *
 * Same key, same meaning, different digest, so the second one is rejected
 * `422 idempotency_key_reuse`. The seed script gets there first on every demo
 * machine, which meant this screen could never open the group: it showed a
 * raw English server string where the member list belongs. Measured, not
 * guessed -- posting both byte strings under one key returns 201 and 422.
 *
 * Exactly one write is exposed: the group create. It is the only key both
 * programs derive the same way -- `write:context` on each side. The seed keys
 * a person by `write:person:<uuid>` where this file uses `write:<slug>`, and
 * an invite by `write:invite:<uuid>` against `write:invite:<slug>`, so those
 * never meet and keep `JSON.stringify`. Narrow the workaround to the write
 * that needs it; a project-wide encoder swap would be a much larger claim
 * than the evidence supports.
 *
 * There is no `GET /contexts`, so replay is the only route to the seeded
 * group -- inventing a fresh key would create a SECOND "Team Đà Lạt" beside
 * the one holding the members and the history. So the idempotent writes below
 * are serialised by `thanNhuSeed`, which reproduces Python's default
 * `json.dumps` output byte for byte.
 *
 * This is a workaround wearing its reason on its sleeve, not a design. The
 * durable fix is server-side (fingerprint canonical JSON, or expose a way to
 * look a context up) and has been reported to the backend lane. When that
 * lands, `thanNhuSeed` should go and `JSON.stringify` should come back.
 */

import { headerNguoiGoi } from "../../danh-tinh";
import { chiTietLoi } from "../../ui/loi-tren-man";
import {
  DEMO_GROUP_NAME,
  DEMO_PEOPLE,
  type NguoiDung,
  personById,
} from "../../rudi/nhom-demo";
import { KHONG_GIAN_DEMO, idNguoi, khoaGhi } from "./uuid5";

declare const process: { env: Record<string, string | undefined> };

export const NHOM_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8099";

export type BuocNhom = "dat-ten" | "tao-nhom" | "moi" | "chap-nhan" | "doc-thanh-vien";

export type ThanhVien = {
  id: string;
  contextId: string;
  personId: string;
  /** The name the server holds for this person.
   *
   *  `MembershipResponse.display_name` is `NOT NULL` on the server because
   *  `people.display_name` is, so a live reply always carries it. Optional
   *  here anyway: the fixtures in this repo's own tests predate the field, and
   *  a parser that throws on a member without a name would turn "an old fake"
   *  into "the group could not be opened". Callers fall back to the demo
   *  roster and then to a neutral label. */
  displayName?: string;
  state: "invited" | "active" | "left";
  role: "member" | "admin";
};

export type NhomState =
  | {
      kind: "xong";
      contextId: string;
      tenNhom: string;
      members: ThanhVien[];
    }
  | {
      kind: "hong";
      buoc: BuocNhom;
      url: string;
      status: number;
      detail: string;
    };

/** The group as a screen sees it, including the two states that are not the
 *  server's answer: nobody signed in yet, and the request still in flight.
 *  Shared rather than redeclared per screen -- chat, Lên plan and the expense
 *  flow all hold exactly this. */
export type NhomMan = { kind: "dang-tai" } | { kind: "chua-chon" } | NhomState;

/** Which step of opening the group failed, in a sentence.
 *
 * Exported so the expense flow says the same thing chat says. It was private
 * to `TinNhan.tsx` until a second screen needed it, and a second copy is a
 * copy that drifts the day a step is renamed. */
export function cauBuocNhom(buoc: string): string {
  if (buoc === "dat-ten") return "Không ghi được tên người";
  if (buoc === "tao-nhom") return "Không tạo được nhóm";
  if (buoc === "moi") return "Không mời được vào nhóm";
  if (buoc === "chap-nhan") return "Không nhận lời mời được";
  if (buoc === "doc-thanh-vien") return "Không đọc được danh sách thành viên";
  return "Không vào được nhóm";
}

const MINH_SLUG = "minh";

function headers(actorId: string, contextId?: string, key?: string): Record<string, string> {
  // This module used to attach the bearer itself, with a comment saying that a
  // module building its own headers has to. It was right, and it was the only
  // one of nine that did -- so eight others answered 401 on a production host
  // while this path worked. `headerNguoiGoi` is that comment turned into one
  // place, and `tests/mot-cho-dung-danh-tinh.test.mjs` keeps it the only one.
  // `|| undefined`, not `contextId`: the version this replaced wrote the
  // header under `if (contextId)`, so an empty string sent nothing. Passing it
  // straight through would send `X-Actor-Contexts: ""` -- a claim of membership
  // in no group, which is a different sentence from making no claim.
  return headerNguoiGoi(actorId, {
    roles: "group_admin,member",
    contexts: contextId || undefined,
    key,
  });
}

function goc(base: string): string {
  return base.replace(/\/$/, "");
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

function hong(buoc: BuocNhom, url: string, status: number, detail: string): NhomState {
  return { kind: "hong", buoc, url, status, detail };
}

type CallOk = { ok: true; status: number; body: unknown };
type CallFail = { ok: false; state: NhomState };

async function goi(
  buoc: BuocNhom,
  url: string,
  init: RequestInit,
  { choPhep409 = false }: { choPhep409?: boolean } = {},
): Promise<CallOk | CallFail> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch (e) {
    return { ok: false, state: hong(buoc, url, 0, chiTietLoi(e)) };
  }
  if (choPhep409 && res.status === 409) {
    return { ok: true, status: 409, body: null };
  }
  if (!res.ok) {
    return { ok: false, state: hong(buoc, url, res.status, await docLoi(res)) };
  }
  if (res.status === 204) return { ok: true, status: 204, body: null };
  try {
    const text = await res.text();
    const body = text.trim() ? (JSON.parse(text) as unknown) : null;
    return { ok: true, status: res.status, body };
  } catch (e) {
    return { ok: false, state: hong(buoc, url, res.status, chiTietLoi(e)) };
  }
}

function docThanhVien(raw: unknown, field: string): ThanhVien {
  const m = raw as Record<string, unknown>;
  const state = m?.state;
  const role = m?.role;
  if (state !== "invited" && state !== "active" && state !== "left") {
    throw new Error(`${field}.state lạ: ${JSON.stringify(state)}`);
  }
  if (role !== "member" && role !== "admin") {
    throw new Error(`${field}.role lạ: ${JSON.stringify(role)}`);
  }
  if (typeof m.id !== "string" || typeof m.context_id !== "string" || typeof m.person_id !== "string") {
    throw new Error(`${field} thiếu id/context_id/person_id`);
  }
  return {
    id: m.id,
    contextId: m.context_id,
    personId: m.person_id,
    ...(typeof m.display_name === "string" && m.display_name.length > 0
      ? { displayName: m.display_name }
      : {}),
    state,
    role,
  };
}

/**
 * Serialise a flat string object the way Python's `json.dumps` does by
 * default, so an idempotent write from this client digests to the same
 * fingerprint as the same write from `scripts/seed_demo_data.py`.
 *
 * Two differences from `JSON.stringify`, and both matter because the server
 * hashes raw bytes:
 *
 *   - separators. Python writes `", "` between pairs and `": "` after a key;
 *     `JSON.stringify` writes neither space.
 *   - `ensure_ascii=True`. Python escapes every code point above U+007F as
 *     `\uXXXX`; `JSON.stringify` emits it as UTF-8.
 *
 * Escaping walks UTF-16 code units, so an astral character becomes its two
 * surrogates -- which is exactly what Python emits for one.
 *
 * Only for the idempotent writes. Anything without an `Idempotency-Key` is
 * not fingerprinted and should keep using `JSON.stringify`.
 */
export function thanNhuSeed(obj: Record<string, string>): string {
  const pairs = Object.entries(obj).map(([k, v]) => `${chuoiAscii(k)}: ${chuoiAscii(v)}`);
  return `{${pairs.join(", ")}}`;
}

/** One JSON string literal, ASCII only. `JSON.stringify` already agrees with
 *  Python on quotes, backslashes and the short control escapes, so the only
 *  work left is pushing the non-ASCII code units into `\uXXXX`. */
function chuoiAscii(s: string): string {
  const chuan = JSON.stringify(s);
  let ra = "";
  for (const ch of chuan) {
    const ma = ch.charCodeAt(0);
    ra += ma > 0x7f ? `\\u${ma.toString(16).padStart(4, "0")}` : ch;
  }
  return ra;
}

async function datTen(
  base: string,
  slug: string,
  personId: string,
  name: string,
): Promise<CallOk | CallFail> {
  const url = `${goc(base)}/people/${personId}`;
  return goi("dat-ten", url, {
    method: "PUT",
    headers: headers(personId, undefined, khoaGhi(slug)),
    body: JSON.stringify({ display_name: name }),
  });
}

/** A group this session already opened, as `screens/vao-cua/cong-api.ts`
 *  returns it. Only the two fields a screen needs are named, so `TinNhan` can
 *  take the handle without importing the entry door's wire types. */
export type NhomPhien = { id: string; display_name: string };

/**
 * Read the members of a group the session already holds a handle to.
 *
 * The three writes `khoiDongNhom` performs exist to *reach* the demo group:
 * there is no `GET /contexts`, so replaying `POST /contexts` under a derived
 * key is the only route back to it. A group the person opened themselves on
 * F03/F04 needs none of that -- the id is in hand and they are already its
 * admin -- so this is step 4 alone.
 *
 * Sending the create anyway would be worse than wasteful: it would name a
 * second group beside the one they are looking at.
 */
export async function moNhomDaCo(
  nhom: NhomPhien,
  nguoi: NguoiDung,
  opts: { base?: string } = {},
): Promise<NhomState> {
  const base = opts.base ?? NHOM_BASE_URL;
  return docRoster(base, nhom.id, nhom.display_name, nguoi);
}

/**
 * The group a screen should show, given who is signed in and whether this
 * session has already opened one of its own.
 *
 * Order matters and it is the whole of bug-223337. Chat used to resolve the
 * group one way only -- rebuild the seeded demo group -- so the group on
 * screen was never the group the person was in. A session that opened its own
 * group was ignored, and a person who registered themselves was refused
 * outright.
 *
 * The demo group stays as the fallback rather than being dropped: somebody who
 * signs in and taps Tin nhắn without first creating a group still has to land
 * in a conversation, and joining Team Đà Lạt happens through the real invite
 * and accept routes, not by asserting membership the server never granted.
 */
export async function moNhomChoMan(
  nguoi: NguoiDung,
  nhomPhien: NhomPhien | null,
  opts: { base?: string } = {},
): Promise<NhomState> {
  return nhomPhien ? moNhomDaCo(nhomPhien, nguoi, opts) : khoiDongNhom(nguoi, opts);
}

/**
 * Open (or replay) the demo group under the signed-in person, then return the
 * real members. Never throws.
 *
 * Takes the person rather than a slug to look up. It used to take a slug and
 * resolve it through `personById`, which meant the seven names in
 * `nhom-demo.ts` were the only identities that could open a chat at all --
 * everyone else got `status: 0`, a refusal minted on the device before a
 * single byte left it. `DangKy.tsx` has been registering real people since
 * F01, and their `id` is their own UUID, so the roster lookup answered `null`
 * for the one door in this app that is not a shell (bug-223337).
 *
 * Nothing about the seeded seven changes: their `id` is still the slug the
 * write keys are derived from, so `khoaGhi(nguoi.id)` digests exactly as
 * before and the seeded group still replays instead of doubling.
 */
export async function khoiDongNhom(
  nguoi: NguoiDung,
  opts: { base?: string } = {},
): Promise<NhomState> {
  const base = opts.base ?? NHOM_BASE_URL;
  const slug = nguoi.id;

  const minh = personById(MINH_SLUG)!;
  const minhDat = await datTen(base, MINH_SLUG, minh.personId, minh.name);
  if (!minhDat.ok) return minhDat.state;
  if (slug !== MINH_SLUG) {
    const minhNguoi = await datTen(base, slug, nguoi.personId, nguoi.name);
    if (!minhNguoi.ok) return minhNguoi.state;
  }

  const taoUrl = `${goc(base)}/contexts`;
  const tao = await goi("tao-nhom", taoUrl, {
    method: "POST",
    headers: headers(minh.personId, undefined, khoaGhi("context")),
    body: thanNhuSeed({ display_name: DEMO_GROUP_NAME }),
  });
  if (!tao.ok) return tao.state;
  const taoBody = tao.body as { id?: unknown; display_name?: unknown } | null;
  if (!taoBody || typeof taoBody.id !== "string") {
    return hong("tao-nhom", taoUrl, tao.status, "máy chủ không trả id nhóm");
  }
  const contextId = taoBody.id;
  const tenNhom = typeof taoBody.display_name === "string" ? taoBody.display_name : DEMO_GROUP_NAME;

  if (slug !== MINH_SLUG) {
    const moiUrl = `${goc(base)}/contexts/${contextId}/members`;
    const moi = await goi(
      "moi",
      moiUrl,
      {
        method: "POST",
        headers: headers(minh.personId, contextId, khoaGhi(`invite:${slug}`)),
        body: JSON.stringify({ person_id: nguoi.personId }),
      },
      { choPhep409: true },
    );
    if (!moi.ok) return moi.state;
    if (moi.status !== 409) {
      const membershipId = (moi.body as { id?: unknown } | null)?.id;
      if (typeof membershipId !== "string") {
        return hong("moi", moiUrl, moi.status, "máy chủ không trả id lời mời");
      }
      const chapUrl = `${goc(base)}/memberships/${membershipId}/accept`;
      const chap = await goi(
        "chap-nhan",
        chapUrl,
        {
          method: "POST",
          headers: headers(nguoi.personId, contextId, khoaGhi(`accept:${slug}`)),
          body: JSON.stringify({}),
        },
        { choPhep409: true },
      );
      if (!chap.ok) return chap.state;
    }
  }

  return docRoster(base, contextId, tenNhom, nguoi);
}

/** Step 4, on its own, because two entry points now need exactly it.
 *
 *  The member list is read as the signed-in person, never as `minh`: the
 *  server answers `GET /contexts/{id}/members` from `X-Actor-ID`, so asking on
 *  somebody else's behalf would report a roster this phone has no right to
 *  see. A 403 here is the honest answer for a group the person is not in, and
 *  it arrives as `hong` with the address on it rather than as an empty list. */
async function docRoster(
  base: string,
  contextId: string,
  tenNhom: string,
  nguoi: NguoiDung,
): Promise<NhomState> {
  const dsUrl = `${goc(base)}/contexts/${contextId}/members`;
  const ds = await goi("doc-thanh-vien", dsUrl, {
    method: "GET",
    headers: headers(nguoi.personId, contextId),
  });
  if (!ds.ok) return ds.state;
  try {
    const body = ds.body as { members?: unknown };
    if (!Array.isArray(body?.members)) throw new Error("thiếu mảng `members`");
    const members = body.members.map((m, i) => docThanhVien(m, `members[${i}]`));
    return { kind: "xong", contextId, tenNhom, members };
  } catch (e) {
    return hong("doc-thanh-vien", dsUrl, ds.status, chiTietLoi(e));
  }
}

export { DEMO_GROUP_NAME, DEMO_PEOPLE, KHONG_GIAN_DEMO, idNguoi, khoaGhi };
