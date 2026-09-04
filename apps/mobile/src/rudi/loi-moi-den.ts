/**
 * The invitation a link arrived with, held between the router and the screen.
 *
 * ## Why this is not a route param
 *
 * The obvious shape is `router.replace({ pathname: "/moi", params: { ma } })`.
 * That puts a bearer secret into navigation state: into the history stack, into
 * whatever the router logs, and into a crash report if one is ever sent. The
 * secret is single-use and spending it is irreversible -- once redeemed, the
 * row's digest is cleared and the person is locked out until a member rotates
 * it for them -- so it is worth keeping out of every place a string can be
 * copied to by accident.
 *
 * So the link hands it here and the screen takes it. It never becomes part of
 * an address.
 *
 * ## Why reading clears it
 *
 * A code that stayed would be offered again the next time somebody opened the
 * screen, after it had already been spent. That reads as "your invitation is
 * invalid" for a person who did nothing wrong. One read, then gone.
 */

let dangCho: string | null = null;

export function datLoiMoiDen(ma: string): void {
  dangCho = ma === "" ? null : ma;
}

/** Take the pending code, if any. Reading consumes it. */
export function layLoiMoiDen(): string | null {
  const ma = dangCho;
  dangCho = null;
  return ma;
}

/**
 * The sentence after an invitation is accepted. Signing in and joining are
 * two different things and the screen must not merge them: somebody redeeming
 * their first invitation is signed in AND still waiting; somebody signing back
 * in on a new phone is signed in and waiting on nobody. Moved here from App
 * B's `NhanLoiMoi.tsx` so the shell owns its own sentences.
 */
export function cauSauKhiNhan(
  state: "invited" | "active",
  qua: "lien-ket" | "phien" = "lien-ket",
): string {
  if (qua === "phien") {
    if (state === "active") return "Đã đăng nhập. Bạn đã ở trong nhóm.";
    // NOT "the group still has to approve you": this door is only ever reached
    // by a NAMED invitation, so the only thing left is the person's own yes.
    return "Đã đăng nhập. Bạn được mời đích danh, nên chỉ cần bạn đồng ý là vào nhóm.";
  }
  if (state === "active") return "Bạn đã vào buổi đi.";
  return "Lời mời đã nhận, nhưng nhóm còn phải duyệt thì bạn mới vào được.";
}
