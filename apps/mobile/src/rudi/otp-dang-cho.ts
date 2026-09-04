/**
 * The challenge the OTP screen is waiting on, handed over in memory.
 *
 * Same shape as `loi-moi-den.ts`, same reason: a telephone number and a
 * challenge id must not ride in navigation state, where they would be logged,
 * restored and deep-linkable. The login screen sets it, the OTP screen reads
 * it, and a cold start finds nothing here -- which is correct, because a code
 * requested by a previous launch is a code that should be requested again.
 */
export type OtpDangCho = {
  challengeId: string;
  /** As typed, so the screen can echo it back to the person who typed it. */
  phone: string;
  /** Epoch milliseconds after which the server accepts a resend. */
  guiLaiLuc: number;
};

/**
 * The number as the OTP screen shows it: last three digits, the rest hidden.
 *
 * The person typed it a moment ago, so this is not secrecy from them; it is so
 * a screenshot, a screen recording or somebody reading over a shoulder gets
 * three digits and not a phone number.
 */
export function cheSo(phone: string): string {
  const so = phone.replace(/\D/g, "");
  if (so.length < 4) return "số của bạn";
  return "••• ••• " + so.slice(-3);
}

let dangCho: OtpDangCho | null = null;

export function datOtpDangCho(moi: OtpDangCho): void {
  dangCho = moi;
}

export function layOtpDangCho(): OtpDangCho | null {
  return dangCho;
}

export function xoaOtpDangCho(): void {
  dangCho = null;
}
