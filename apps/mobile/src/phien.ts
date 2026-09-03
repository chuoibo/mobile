/** Signing in, staying signed in, and signing out.
 *
 * Since ADR-0014 a production server does not believe `X-Actor-ID`. What it
 * believes is a bearer token it issued itself, and the only way to get one
 * without already having one is to exchange a **named** invitation: a row an
 * existing member wrote with somebody's `person_id` in it. The app therefore
 * never says who it is. It hands over a secret, and the server answers with
 * whose session that secret was.
 *
 * That asymmetry is the whole design and it is easy to undo by accident. A
 * body with a `person_id` in it, however well-meant, would put the client back
 * in charge of identity and reopen the hole the ADR closed. There is no such
 * field here and there must not be one.
 *
 * Three things live here rather than in `api.ts`:
 *
 * - **The native module.** `expo-secure-store` is imported dynamically, never
 *   at module scope. `api.ts` is loaded by the node test suite, which has no
 *   native modules at all, and a top-level import would make the entire API
 *   layer unloadable there.
 * - **The retry key.** A dropped response on `POST /sessions` is the worst
 *   failure this flow has: the invitation's secret is spent server-side, the
 *   token is lost in the network, and the person is locked out until somebody
 *   rotates the invitation for them. An `Idempotency-Key` turns that into a
 *   replay of the same answer.
 * - **The fallback store.** On web there is no SecureStore. The session is
 *   kept in memory for that session of the browser and nowhere else, which is
 *   the honest behaviour rather than quietly writing a credential to
 *   `localStorage`.
 */
import {
  datTokenPhien,
  newAttempt,
  tokenPhienHienTai,
  translatedAnonymous,
  translatedAsActor,
} from "./api";

/** What the server hands back once, and what we keep. */
export type Phien = {
  token: string;
  person_id: string;
  expires_at: string;
  /** Where this person stands in the group the invitation belonged to.
   *
   *  Signing in is not joining. A first invitation lands `invited` and still
   *  waits on a member; signing back in on a new phone is `active` and waits
   *  on nobody. Without this the screen would have to pick one sentence and be
   *  wrong for half the people reading it. */
  membership_state: "invited" | "active" | "left";
};

/** Where a secret is kept between launches. */
export type KhoAnToan = {
  doc(khoa: string): Promise<string | null>;
  ghi(khoa: string, giaTri: string): Promise<void>;
  xoa(khoa: string): Promise<void>;
};

const KHOA = "rudi.phien";

const LOI_DOI_LOI_MOI: Record<string, string> = {
  // 404 is every refusal this route makes: expired, revoked, already spent,
  // never existed. The server answers them identically on purpose, so the
  // sentence here must not pretend to know which one happened.
  http_404: "Lời mời này không dùng được nữa. Nhờ người trong nhóm mời lại.",
  http_422: "Mã lời mời không đúng định dạng.",
};

const LOI_DANG_XUAT: Record<string, string> = {
  http_401: "Phiên đã hết hiệu lực rồi.",
};

/** In memory only. The fallback, and what the web build always gets. */
export function khoTrongBoNho(): KhoAnToan {
  let giu: string | null = null;
  return {
    async doc() {
      return giu;
    },
    async ghi(_khoa, giaTri) {
      giu = giaTri;
    },
    async xoa() {
      giu = null;
    },
  };
}

let khoMacDinh: KhoAnToan | null = null;

/**
 * SecureStore when the platform has it, memory when it does not.
 *
 * Resolved once and remembered, because the answer cannot change inside one
 * run of the app, and because a failed dynamic import should not be retried on
 * every read.
 */
export async function khoAnToanMacDinh(): Promise<KhoAnToan> {
  if (khoMacDinh !== null) return khoMacDinh;
  try {
    const store = await import("expo-secure-store");
    // Touch the API before committing to it: the module resolves on web and
    // then throws from its methods, and finding that out on the first read
    // would lose a token that had already been issued.
    await store.getItemAsync(KHOA);
    khoMacDinh = {
      doc: (khoa) => store.getItemAsync(khoa),
      ghi: (khoa, giaTri) => store.setItemAsync(khoa, giaTri),
      xoa: (khoa) => store.deleteItemAsync(khoa),
    };
  } catch {
    khoMacDinh = khoTrongBoNho();
  }
  return khoMacDinh;
}

function docPhien(thoLuu: string | null): Phien | null {
  if (thoLuu === null) return null;
  try {
    const parsed = JSON.parse(thoLuu) as Partial<Phien>;
    if (typeof parsed.token !== "string" || parsed.token === "") return null;
    if (typeof parsed.person_id !== "string") return null;
    if (typeof parsed.expires_at !== "string") return null;
    if (typeof parsed.membership_state !== "string") return null;
    return {
      token: parsed.token,
      person_id: parsed.person_id,
      expires_at: parsed.expires_at,
      membership_state: parsed.membership_state,
    };
  } catch {
    // A corrupted record is a signed-out app, not a crashed one.
    return null;
  }
}

/**
 * Trade a named invitation for a session, and remember it.
 *
 * The body carries the secret and nothing else -- see the header of this file
 * for why there is no `person_id` in it.
 */
export async function doiLoiMoiLayPhien(
  maLoiMoi: string,
  kho?: KhoAnToan,
): Promise<Phien> {
  const phien = await translatedAnonymous<Phien>(LOI_DOI_LOI_MOI, "/sessions", {
    method: "POST",
    body: { invite_token: maLoiMoi },
    // Minted here, on the press. A retry of a dropped answer replays the same
    // session instead of spending a secret that is already gone.
    attempt: newAttempt(),
  });
  await ghiNho(phien, kho);
  return phien;
}

/** Put a session into force for this process, and onto the device. */
export async function ghiNho(phien: Phien, kho?: KhoAnToan): Promise<void> {
  datTokenPhien(phien.token);
  const store = kho ?? (await khoAnToanMacDinh());
  await store.ghi(KHOA, JSON.stringify(phien));
}

/**
 * Read the stored session at launch, if there is one.
 *
 * An expired record is dropped here rather than sent: the server would answer
 * 401 and the app would show a person a failure for something it already knew.
 */
export async function khoiPhucPhien(kho?: KhoAnToan): Promise<Phien | null> {
  const store = kho ?? (await khoAnToanMacDinh());
  const phien = docPhien(await store.doc(KHOA));
  if (phien === null) return null;
  if (Date.parse(phien.expires_at) <= Date.now()) {
    await store.xoa(KHOA);
    datTokenPhien(null);
    return null;
  }
  datTokenPhien(phien.token);
  return phien;
}

/**
 * Sign out on the server first, then forget locally.
 *
 * That order is the point. A session only the phone forgets is still a live
 * credential on the server, and a phone somebody else is holding is exactly
 * when that matters. The local record is cleared even when the call fails,
 * because a person who pressed sign-out has said what they want and the
 * server-side row will expire on its own.
 */
export async function dangXuat(personId: string, kho?: KhoAnToan): Promise<void> {
  const token = tokenPhienHienTai();
  try {
    if (token !== null) {
      await translatedAsActor<void>(LOI_DANG_XUAT, "/sessions/current", {
        method: "DELETE",
        actorId: personId,
      });
    }
  } finally {
    datTokenPhien(null);
    const store = kho ?? (await khoAnToanMacDinh());
    await store.xoa(KHOA);
  }
}
