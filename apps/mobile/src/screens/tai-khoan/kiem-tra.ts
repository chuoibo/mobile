/** Shape rules for a bank destination, decided before anything is sent.
 *
 * A deliberate second copy of `services/api/app/domain/bank_account.py`. The
 * server stays the authority -- it is the only side that can refuse for real --
 * but a person typing their own account number should be told about a typo
 * while their thumb is still on the keyboard, not after a round trip that comes
 * back as `INVALID_ACCOUNT_NUMBER`.
 *
 * The two copies are held together by `tests/tai-khoan-nhan.test.mjs`, which
 * parses the Python regexes out of that file and fails when they stop matching
 * the ones below. Same arrangement as `banks.test.mjs` and for the same reason:
 * a client that quietly accepts what the server rejects sends somebody back to
 * a form with no idea which field is wrong.
 *
 * That test also asserts the *inventory* of server rules, not just the ones
 * named below, so adding a rule to `bank_account.py` fails until it is mirrored
 * here or written off on purpose. If you are here because that test went red
 * after a server change, mirroring the new rule is the fix.
 *
 * Nothing here claims the account belongs to anybody. There is no verification
 * source to ask, and spec section 8.5 forbids the claim outright. The only real
 * check is the holder name the sender's own banking app shows them before they
 * press send, which is why `tenChuTaiKhoan` is required by this form even
 * though the API accepts it as null.
 */
import banks from "../../../../../packages/shared/banks.json";

/** Mirrors `_BANK_BIN` in bank_account.py. */
const BANK_BIN = /^[0-9]{6}$/;
/** Mirrors `_ACCOUNT_NUMBER`, whose upper bound is the String(19) column. */
const SO_TAI_KHOAN = /^[A-Za-z0-9]{1,19}$/;
const KHOANG_TRANG = /\s+/g;

/** Mirrors `ACCOUNT_NAME_MAX`. */
export const TEN_TOI_DA = 255;

export type NganHang = { bin: string; ten: string };

/**
 * The directory the picker offers, in the order it is read.
 *
 * Sorted by name rather than by BIN. A BIN is a routing code nobody recognises,
 * so a list ordered by it looks unordered to the person scrolling it.
 */
export const NGAN_HANG: NganHang[] = Object.entries(
  (banks as { banks: Record<string, string> }).banks,
)
  .map(([bin, ten]) => ({ bin, ten }))
  .sort((a, b) => a.ten.localeCompare(b.ten, "vi"));

/** Banks whose name contains the query, case- and accent-tolerantly. */
export function locNganHang(query: string): NganHang[] {
  const needle = boDau(query.trim());
  if (needle === "") return NGAN_HANG;
  return NGAN_HANG.filter((bank) => boDau(bank.ten).includes(needle));
}

/** Lower-case and strip Vietnamese diacritics, for matching only. */
function boDau(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/g, "d");
}

/**
 * The account number in the exact form storage will accept.
 *
 * Whitespace is dropped rather than refused. Vietnamese banking apps display
 * "0000 0000 00TE ST" and that is what gets copied; refusing it as malformed
 * teaches people to fight the form while the digits they pasted were right all
 * along. Same rule as `_account_number` on the server.
 */
export function chuanHoaSoTaiKhoan(raw: string): string {
  return raw.replace(KHOANG_TRANG, "");
}

/** Collapse runs of whitespace and trim, the way `_account_name` does. */
export function chuanHoaTen(raw: string): string {
  return raw.replace(KHOANG_TRANG, " ").trim();
}

export type VanDe = "trong" | "sai-dinh-dang" | "qua-dai";

/** What is wrong with the account number, or null when nothing is. */
export function vanDeSoTaiKhoan(raw: string): VanDe | null {
  const so = chuanHoaSoTaiKhoan(raw);
  if (so === "") return "trong";
  if (!SO_TAI_KHOAN.test(so)) {
    return so.length > 19 ? "qua-dai" : "sai-dinh-dang";
  }
  return null;
}

/** What is wrong with the holder name, or null when nothing is. */
export function vanDeTenChuTaiKhoan(raw: string): VanDe | null {
  const ten = chuanHoaTen(raw);
  if (ten === "") return "trong";
  if (ten.length > TEN_TOI_DA) return "qua-dai";
  return null;
}

export function binHopLe(bin: string): boolean {
  return BANK_BIN.test(bin.trim());
}

/**
 * Whether the two account-number boxes hold the same number.
 *
 * Compared after normalising, so "0011 2233" and "00112233" agree. They are the
 * same account, and a form that says otherwise is teaching people to distrust
 * the check that exists to protect them.
 */
export function trungSoTaiKhoan(a: string, b: string): boolean {
  return chuanHoaSoTaiKhoan(a) === chuanHoaSoTaiKhoan(b);
}

export type FormTaiKhoan = {
  bin: string | null;
  soTaiKhoan: string;
  nhapLai: string;
  tenChuTaiKhoan: string;
};

export const FORM_TRONG: FormTaiKhoan = {
  bin: null,
  soTaiKhoan: "",
  nhapLai: "",
  tenChuTaiKhoan: "",
};

/**
 * Every reason this form cannot be sent yet, in the order the fields appear.
 *
 * Returned as a list rather than as a boolean so the screen can say which box
 * is wrong. A single `sanSang` flag disables the button and leaves the person
 * to guess, which on a four-field form is a guess between four things.
 */
export function vanDeCuaForm(form: FormTaiKhoan): string[] {
  const out: string[] = [];
  if (form.bin === null || !binHopLe(form.bin)) out.push("Chưa chọn ngân hàng.");
  const so = vanDeSoTaiKhoan(form.soTaiKhoan);
  if (so === "trong") out.push("Chưa nhập số tài khoản.");
  if (so === "sai-dinh-dang") out.push("Số tài khoản chỉ gồm chữ và số.");
  if (so === "qua-dai") out.push("Số tài khoản dài hơn 19 ký tự.");
  // Only worth saying once the first box holds something valid: telling somebody
  // the two boxes disagree while the first one is still empty is noise.
  if (so === null && !trungSoTaiKhoan(form.soTaiKhoan, form.nhapLai)) {
    out.push("Hai ô số tài khoản chưa giống nhau.");
  }
  const ten = vanDeTenChuTaiKhoan(form.tenChuTaiKhoan);
  if (ten === "trong") out.push("Chưa nhập tên chủ tài khoản.");
  if (ten === "qua-dai") out.push(`Tên chủ tài khoản dài hơn ${TEN_TOI_DA} ký tự.`);
  return out;
}
