/** Read a server-built VietQR payload back, for display only.
 *
 * The string comes from `POST /batches/{id}/publish`, which builds it with
 * `app/payments/vietqr.py`. Nothing here rebuilds it and nothing here does
 * arithmetic on money: this parses the payload the server already sent so the
 * card under the QR can name a bank and show the last four digits of an
 * account, rather than printing a 130-character EMVCo string at somebody.
 *
 * Why parse at all rather than ask for the fields: the publish response carries
 * `vietqr_payload` and nothing else about the recipient. Asking the API for a
 * second shape is a backend change; reading the string it already sent is not,
 * and it cannot drift from the QR, because it *is* the QR.
 *
 * The amount is read back for one reason only, and it is not display: the
 * screen compares it against the obligation amount the server reported
 * separately. Two numbers from the same server that disagree means the QR would
 * move a different sum than the row above it claims, and that is worth refusing
 * to draw rather than showing prettily.
 */
import banks from "../../../../packages/shared/banks.json";

export class VietQrReadError extends Error {
  constructor(readonly code: string) {
    super(code);
    this.name = "VietQrReadError";
  }
}

/** One level of EMVCo tag-length-value. Same shape as `parse_tlv` in Python. */
function parseTlv(payload: string): Record<string, string> {
  const out: Record<string, string> = {};
  let i = 0;
  while (i < payload.length) {
    if (i + 4 > payload.length) throw new VietQrReadError("TRUNCATED");
    const tag = payload.slice(i, i + 2);
    const length = Number(payload.slice(i + 2, i + 4));
    if (!Number.isInteger(length)) throw new VietQrReadError("BAD_LENGTH");
    const value = payload.slice(i + 4, i + 4 + length);
    if (value.length !== length) throw new VietQrReadError("TRUNCATED");
    out[tag] = value;
    i += 4 + length;
  }
  return out;
}

export type VietQrAccount = {
  bankBin: string;
  bankName: string;
  /** Full digits. Held so the amount check and the tests can see them; the
   *  screen renders `accountMasked`, never this. */
  accountNumber: string;
  accountMasked: string;
  /** Integer dong, or null when the payload is a static code with no amount. */
  amountVnd: number | null;
  transferNote: string | null;
};

/** Name if the BIN is known, otherwise the code labelled as a code.
 *
 * Same rule and same words as `bank_display_name` in `app/web/banks.py`: a
 * wrong bank name is worse than a raw code, because it sends somebody
 * confidently into the wrong app and only the transfer failing tells them.
 */
export function bankDisplayName(bankBin: string): string {
  const table: Record<string, string> = banks.banks;
  return table[bankBin] ?? `Mã ngân hàng ${bankBin}`;
}

/**
 * Show the last four digits and nothing else.
 *
 * An account number on a screen is somebody else's, and screens get
 * photographed and screen-shared. Four digits is enough for the recipient to
 * recognise their own account and not enough for a stranger to use it; the
 * machine-readable copy inside the QR is what actually moves the money.
 *
 * Short numbers are masked entirely rather than partly. An account of four
 * digits or fewer would otherwise be printed in full by a function whose name
 * promises the opposite.
 */
export function maskAccount(accountNumber: string): string {
  if (accountNumber.length <= 4) return "•".repeat(accountNumber.length);
  return "••••" + " " + accountNumber.slice(-4);
}

/** Pull the recipient's details out of a payload the server built. */
export function readVietQr(payload: string): VietQrAccount {
  const root = parseTlv(payload);

  const merchant = root["38"];
  if (merchant === undefined) throw new VietQrReadError("NO_MERCHANT_ACCOUNT");
  const beneficiaryBlock = parseTlv(merchant)["01"];
  if (beneficiaryBlock === undefined) throw new VietQrReadError("NO_BENEFICIARY");

  const beneficiary = parseTlv(beneficiaryBlock);
  const bankBin = beneficiary["00"];
  const accountNumber = beneficiary["01"];
  if (bankBin === undefined || accountNumber === undefined) {
    throw new VietQrReadError("NO_ACCOUNT");
  }

  // Tag 54 is a decimal string. `Number` on a non-integer or on something the
  // builder would never emit is a refusal, not a rounded guess: this value is
  // compared against an obligation, and a quietly wrong one defeats the check.
  const rawAmount = root["54"];
  let amountVnd: number | null = null;
  if (rawAmount !== undefined) {
    if (!/^\d+$/.test(rawAmount)) throw new VietQrReadError("AMOUNT_NOT_INTEGER");
    amountVnd = Number(rawAmount);
    if (!Number.isSafeInteger(amountVnd)) throw new VietQrReadError("AMOUNT_NOT_INTEGER");
  }

  const additional = root["62"];
  const transferNote = additional === undefined ? null : (parseTlv(additional)["08"] ?? null);

  return {
    bankBin,
    bankName: bankDisplayName(bankBin),
    accountNumber,
    accountMasked: maskAccount(accountNumber),
    amountVnd,
    transferNote,
  };
}
