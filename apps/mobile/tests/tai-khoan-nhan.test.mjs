/* The screen that gives the money somewhere to land, and the two rules on it.
 *
 * Both rules are about money rather than about UI, and neither can be checked
 * by reading the source:
 *
 *   1. **The client's shape rules are the server's shape rules.** A second copy
 *      of a validator is a second thing to drift, and the drift is silent in
 *      the direction that hurts: a client that accepts what the server rejects
 *      sends somebody back to a four-field form with "Bank destination is
 *      malformed" and no indication of which field. So the regexes are read out
 *      of `app/domain/bank_account.py` and compared, the same arrangement
 *      `banks.test.mjs` uses for the bank directory.
 *
 *      Both halves of that are asserted: each rule against its opposite number,
 *      *and* the inventory of rules itself. Comparing three pairs cannot notice
 *      a fourth rule appearing on the server, and "the server grew a rule the
 *      client never heard about" is drift that reads as three green checks.
 *   2. **A full account number never reaches a screen the group reads.** That
 *      is a fact about markup, so these render through react-native-web -- the
 *      substitution Expo's web build performs -- and read the DOM. Asserting
 *      that `maskAccount` is called somewhere proves nothing about what is on
 *      the page.
 *
 * The one place a full number is *supposed* to appear is the review step, and
 * that is asserted too. A masking test that would also pass if the review step
 * silently stopped showing the number would be endorsing a screen on which
 * nobody can check their own typing.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  FORM_TRONG,
  NGAN_HANG,
  TEN_TOI_DA,
  chuanHoaSoTaiKhoan,
  chuanHoaTen,
  locNganHang,
  trungSoTaiKhoan,
  vanDeCuaForm,
  vanDeSoTaiKhoan,
  vanDeTenChuTaiKhoan,
} from "../dist-test/screens/tai-khoan/kiem-tra.js";
import { TaiKhoanNhan, nhomBon } from "../dist-test/screens/tai-khoan/TaiKhoanNhan.js";
import { DeXuat } from "../dist-test/screens/DeXuat.js";
import { maskAccount } from "../dist-test/ui/vietqr.js";
import { saveBankRecipient, isBankRecipientMissing, ApiError } from "../dist-test/api.js";

const MOBILE = dirname(dirname(fileURLToPath(import.meta.url)));
const REPO = dirname(dirname(MOBILE));

/* Invented, and the repo guard is right to ask about a long digit run. Nobody's
 * money is behind it; the exemption is per line and says so rather than the
 * whole file being allowlisted. Same convention as `thanh-toan.test.mjs`. */
// repo-guard: allow=long-number reason=synthetic-test-account-number
const SO_THAT = "1904567890123";

/** The same account as a banking app displays it. Derived, so there is exactly
 *  one account-number literal in this file to keep honest. */
const SO_CO_CACH = SO_THAT.replace(/(\d{4})(?=\d)/g, "$1 ");
/** The same account with the last two digits swapped: one slip of a thumb. */
const SO_LECH = SO_THAT.slice(0, -2) + SO_THAT.slice(-1) + SO_THAT.slice(-2);

/** A syntactically valid idempotency key. Letters on purpose: a run of digits
 *  long enough to look like an account number has no business being in a
 *  fixture, and a UUID does not need to be all-digits to be a UUID. */
const KHOA = "3f1c8d2a-b4e5-4f60-9a71-c2d3e4f50617";

// ---------------------------------------------------------------------------
// 1. The two copies of the shape rules
// ---------------------------------------------------------------------------

/** Pull a named regex literal out of the Python source. */
function pythonRegex(name) {
  const source = readFileSync(
    join(REPO, "services", "api", "app", "domain", "bank_account.py"),
    "utf8",
  );
  const found = source.match(new RegExp(`^${name} = re\\.compile\\(r"([^"]+)"\\)$`, "m"));
  assert.ok(
    found !== null,
    `could not find \`${name} = re.compile(r"...")\` in bank_account.py; the ` +
      "two copies of the shape rules can no longer be compared, which is the " +
      "thing this test exists to notice",
  );
  return found[1];
}

/** Pull the same literal out of the TypeScript source.
 *
 *  Trailing flags are matched but discarded: `/\s+/g` and `re.compile(r"\s+")`
 *  are the same rule, and `g` only says the client calls `.replace` on it.
 */
function clientRegex(name) {
  const source = readFileSync(
    join(MOBILE, "src", "screens", "tai-khoan", "kiem-tra.ts"),
    "utf8",
  );
  const found = source.match(new RegExp(`^const ${name} = /([^/]+)/[a-z]*;$`, "m"));
  assert.ok(found !== null, `could not find \`const ${name} = /.../\` in kiem-tra.ts`);
  return found[1];
}

test("the client's account-number rule is the server's, character for character", () => {
  assert.equal(clientRegex("SO_TAI_KHOAN"), pythonRegex("_ACCOUNT_NUMBER"));
});

test("the client's bank-code rule is the server's", () => {
  assert.equal(clientRegex("BANK_BIN"), pythonRegex("_BANK_BIN"));
});

test("the name length cap matches the server's ACCOUNT_NAME_MAX", () => {
  const source = readFileSync(
    join(REPO, "services", "api", "app", "domain", "bank_account.py"),
    "utf8",
  );
  const found = source.match(/^ACCOUNT_NAME_MAX = (\d+)$/m);
  assert.ok(found !== null, "could not find ACCOUNT_NAME_MAX in bank_account.py");
  assert.equal(TEN_TOI_DA, Number(found[1]));
});

test("the client strips the same whitespace the server strips", () => {
  // The fourth copied rule, and the one whose drift is hardest to see. Both
  // sides normalise before validating, so this regex decides which characters
  // are invisible rather than which are legal -- and a client that erases more
  // than the server erases sends a number the server then refuses.
  //
  // Not hypothetical: a number copied out of a banking app or a web page
  // routinely carries U+00A0. `\s+` eats it, `[ ]+` does not.
  assert.equal(clientRegex("KHOANG_TRANG"), pythonRegex("_WHITESPACE"));
});

/* Everything above compares a rule this file already knows the name of, which
 * leaves the case nobody notices: the server grows a *new* rule and the client
 * never hears about it. Three passing comparisons look identical whether the
 * server has three rules or four.
 *
 * So the inventory itself is asserted. Adding a rule to `bank_account.py` now
 * fails here until somebody either mirrors it in `kiem-tra.ts` or writes down
 * why the client does not need it. That is a deliberate speed bump on the
 * server's file, and it is the cheaper end of the trade: the alternative is a
 * form that accepts what the API refuses, and a person retyping a correct
 * account number to find out which of four boxes is wrong.
 */
const LUAT_DA_BIET = {
  regexes: {
    _BANK_BIN: "BANK_BIN",
    _ACCOUNT_NUMBER: "SO_TAI_KHOAN",
    _WHITESPACE: "KHOANG_TRANG",
  },
  // Module-level integer constants. `_account_name` reads this one as a cap.
  hangSo: ["ACCOUNT_NAME_MAX"],
};

test("the server declares no shape rule the client has not mirrored", () => {
  const source = readFileSync(
    join(REPO, "services", "api", "app", "domain", "bank_account.py"),
    "utf8",
  );
  const found = [...source.matchAll(/^(\w+) = re\.compile\(/gm)].map((m) => m[1]);
  assert.deepEqual(
    found.sort(),
    Object.keys(LUAT_DA_BIET.regexes).sort(),
    "bank_account.py declares a different set of regexes than this test mirrors. " +
      "If a rule was added, mirror it in kiem-tra.ts and add it to LUAT_DA_BIET; " +
      "if one was removed or renamed, the client is validating against a rule " +
      "the server no longer has",
  );
});

test("every mirrored regex still agrees, by name, in both directions", () => {
  // The per-rule tests above name their pairs one at a time and would keep
  // passing if a pair were quietly dropped from this file. This one is driven
  // by the inventory, so a rule cannot fall out of the comparison silently.
  for (const [python, client] of Object.entries(LUAT_DA_BIET.regexes)) {
    assert.equal(
      clientRegex(client),
      pythonRegex(python),
      `${client} in kiem-tra.ts and ${python} in bank_account.py have drifted`,
    );
  }
});

test("the server declares no numeric cap the client has not mirrored", () => {
  const source = readFileSync(
    join(REPO, "services", "api", "app", "domain", "bank_account.py"),
    "utf8",
  );
  const found = [...source.matchAll(/^([A-Z][A-Z0-9_]*) = \d+$/gm)].map((m) => m[1]);
  assert.deepEqual(
    found.sort(),
    [...LUAT_DA_BIET.hangSo].sort(),
    "bank_account.py declares a different set of numeric caps than this test " +
      "mirrors; a cap the client does not know about is a length the form will " +
      "accept and the API will refuse",
  );
});

// ---------------------------------------------------------------------------
// 2. What the form accepts and refuses
// ---------------------------------------------------------------------------

test("spaces are dropped, not refused — banking apps display them", () => {
  // `_account_number` on the server does exactly this. Refusing a pasted
  // "0000 0000 00TE ST" teaches people to fight a form whose digits were right.
  assert.equal(chuanHoaSoTaiKhoan(SO_CO_CACH), SO_THAT);
  assert.equal(vanDeSoTaiKhoan(SO_CO_CACH), null);
});

test("two boxes holding the same number in different spacing agree", () => {
  assert.ok(trungSoTaiKhoan(SO_CO_CACH, SO_THAT));
});

test("a transposed digit is caught by the second box", () => {
  assert.ok(!trungSoTaiKhoan(SO_THAT, SO_LECH));
});

test("an account number is refused for the reasons the server refuses it", () => {
  assert.equal(vanDeSoTaiKhoan(""), "trong");
  assert.equal(vanDeSoTaiKhoan("   "), "trong");
  // Letters are legal; punctuation is not. Both mirror `^[A-Za-z0-9]{1,19}$`.
  assert.equal(vanDeSoTaiKhoan("00TEST99"), null);
  assert.equal(vanDeSoTaiKhoan("1904-5678"), "sai-dinh-dang");
  assert.equal(vanDeSoTaiKhoan("1".repeat(19)), null);
  assert.equal(vanDeSoTaiKhoan("1".repeat(20)), "qua-dai");
});

test("a holder name is required here even though the API allows null", () => {
  // Section 8.5: the holder name the sender's own bank app shows is the only
  // check that exists. An envelope with no name on it has nothing to compare.
  assert.equal(vanDeTenChuTaiKhoan(""), "trong");
  assert.equal(vanDeTenChuTaiKhoan("   "), "trong");
  assert.equal(vanDeTenChuTaiKhoan("a".repeat(TEN_TOI_DA + 1)), "qua-dai");
  assert.equal(vanDeTenChuTaiKhoan("Nguyễn Văn A"), null);
});

test("diacritics are kept, runs of whitespace are collapsed", () => {
  // `_account_name` keeps accents rather than transliterating: whatever the
  // bank shows is what the sender compares against.
  assert.equal(chuanHoaTen("  Nguyễn   Văn  A "), "Nguyễn Văn A");
});

test("an empty form names the first thing wrong with it, not just 'invalid'", () => {
  const problems = vanDeCuaForm(FORM_TRONG);
  assert.ok(problems.length > 0);
  assert.equal(problems[0], "Chưa chọn ngân hàng.");
});

test("the mismatch complaint stays quiet while the first box is still bad", () => {
  // Telling somebody the two boxes disagree while the first one is empty is
  // noise, and noise on a money form is how people learn to ignore warnings.
  const problems = vanDeCuaForm({
    bin: "970436",
    soTaiKhoan: "",
    nhapLai: "123",
    tenChuTaiKhoan: "NGUYEN VAN A",
  });
  assert.deepEqual(problems, ["Chưa nhập số tài khoản."]);
});

test("a complete form has nothing wrong with it", () => {
  assert.deepEqual(
    vanDeCuaForm({
      bin: "970436",
      soTaiKhoan: SO_CO_CACH,
      nhapLai: SO_THAT,
      tenChuTaiKhoan: "NGUYEN VAN A",
    }),
    [],
  );
});

// ---------------------------------------------------------------------------
// 3. The bank picker
// ---------------------------------------------------------------------------

test("the picker offers the shared directory, sorted by name", () => {
  assert.ok(NGAN_HANG.length > 10, "parsed suspiciously few banks");
  const names = NGAN_HANG.map((bank) => bank.ten);
  assert.deepEqual(names, [...names].sort((a, b) => a.localeCompare(b, "vi")));
  assert.ok(NGAN_HANG.every((bank) => /^[0-9]{6}$/.test(bank.bin)));
});

test("searching is case- and accent-tolerant", () => {
  assert.deepEqual(
    locNganHang("vietcom").map((b) => b.bin),
    ["970436"],
  );
  assert.equal(locNganHang("").length, NGAN_HANG.length);
  assert.deepEqual(locNganHang("khong-co-ngan-hang-nao"), []);
});

// ---------------------------------------------------------------------------
// 4. Where a full number may appear, and where it may not
// ---------------------------------------------------------------------------

test("the review step shows the number in full, grouped for reading", () => {
  // The positive half, and it comes first on purpose: a masking test that also
  // passed when the review step stopped showing anything would be endorsing a
  // screen on which nobody can check their own typing.
  assert.equal(nhomBon(SO_THAT), SO_CO_CACH);
});

test("the proposal screen names the account without printing it", () => {
  const markup = renderToStaticMarkup(
    React.createElement(DeXuat, {
      proposal: {
        participants: [
          { id: "p1", name: "Hà" },
          { id: "p2", name: "Nam" },
        ],
        allocations: { p1: 50000, p2: 50000 },
        roundingGainers: [],
        totalVnd: 100000,
        advancerId: "p1",
        occasion: "bữa tối",
      },
      // Everyone here is on the bill, so the group adds nothing; it is passed
      // because the prop is required, which is what stops a real call site
      // from quietly falling back to printing ids.
      nhom: [],
      taiKhoanNhan: `Vietcombank ${maskAccount(SO_THAT)}`,
      onConfirm: () => {},
      onBack: () => {},
    }),
  );
  assert.ok(
    !markup.includes(SO_THAT),
    "the full account number reached the proposal screen, which is the screen " +
      "an organiser holds up to the table",
  );
  assert.ok(markup.includes("0123"), "the last four digits are missing, so the " +
    "recipient cannot recognise their own account");
  assert.ok(markup.includes("Vietcombank"));
});

test("the form itself does show what is being typed", () => {
  // The one screen where the full number belongs. Without this the masking
  // rule could be satisfied by a form nobody can proofread.
  const markup = renderToStaticMarkup(
    React.createElement(TaiKhoanNhan, {
      nguoiNhan: { id: "p1", name: "Hà" },
      onLuu: () => {},
      onBack: () => {},
    }),
  );
  assert.ok(markup.includes("Tài khoản nhận tiền"));
  assert.ok(markup.includes("Nhập lại số tài khoản"), "the second box is gone, " +
    "so a transposed digit has nothing to catch it");
  // Every bank in the directory is offered as a radio, not typed.
  assert.ok(markup.includes("Vietcombank"));
  assert.ok(markup.includes('role="radio"'));
});

// ---------------------------------------------------------------------------
// 5. The call itself
// ---------------------------------------------------------------------------

/** Stand in for one HTTP round trip, recording what was actually sent. */
function stubFetch(reply) {
  const seen = [];
  const real = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    seen.push({ url, init });
    return {
      ok: reply.ok ?? true,
      status: reply.status ?? 201,
      json: async () => reply.body,
    };
  };
  return { seen, restore: () => { globalThis.fetch = real; } };
}

test("saveBankRecipient addresses the person and acts as them", async () => {
  const stub = stubFetch({
    body: {
      id: "r1",
      recipient_id: "p1",
      bank_bin: "970436",
      bank_name: "Vietcombank",
      bank_recognised: true,
      account_number: SO_THAT,
      account_name: "NGUYEN VAN A",
      confirmed_at: "2026-08-29T00:00:00Z",
    },
  });
  try {
    const saved = await saveBankRecipient(
      "p1",
      { bankBin: "970436", accountNumber: SO_THAT, accountName: "NGUYEN VAN A" },
      "p1",
      { key: KHOA, at: 0 },
    );

    const [call] = stub.seen;
    assert.equal(call.init.method, "PUT");
    assert.ok(call.url.endsWith("/people/p1/bank-recipient"));
    // The subject is in the address, so the body must not carry a second
    // opinion about who this is for. `extra="forbid"` on the server makes a
    // stray `recipient_id` a 422 rather than a silently ignored field.
    assert.deepEqual(JSON.parse(call.init.body), {
      bank_bin: "970436",
      account_number: SO_THAT,
      account_name: "NGUYEN VAN A",
    });
    // Section 9.2: only the account's owner may write it, so the actor header
    // has to be the person in the path.
    assert.equal(call.init.headers["X-Actor-ID"], "p1");
    // Without this header the server's idempotency middleware passes the
    // request straight through, and a double-tap becomes two writes.
    assert.equal(
      call.init.headers["Idempotency-Key"],
      KHOA,
    );

    assert.equal(saved.accountMasked, maskAccount(SO_THAT));
    assert.ok(
      !JSON.stringify(saved).includes(SO_THAT),
      "saveBankRecipient handed the full account number back to its caller; " +
        "the value is supposed to stop at this function",
    );
  } finally {
    stub.restore();
  }
});

test("a malformed destination comes back in Vietnamese, naming the box", async () => {
  const stub = stubFetch({
    ok: false,
    status: 422,
    // Upper-cased, the way `app/domain/bank_account.py` raises it.
    body: { code: "INVALID_ACCOUNT_NUMBER", detail: "Bank destination is malformed" },
  });
  try {
    await assert.rejects(
      () =>
        saveBankRecipient(
          "p1",
          { bankBin: "970436", accountNumber: "!!", accountName: "A" },
          "p1",
          { key: "k", at: 0 },
        ),
      (problem) => {
        assert.ok(problem instanceof ApiError);
        assert.equal(problem.code, "INVALID_ACCOUNT_NUMBER");
        assert.match(problem.message, /Số tài khoản sai định dạng/);
        assert.ok(
          !/Bank destination is malformed/.test(problem.message),
          "the server's English reached the screen",
        );
        return true;
      },
    );
  } finally {
    stub.restore();
  }
});

// ---------------------------------------------------------------------------
// 6. Which refusals earn a way out
// ---------------------------------------------------------------------------

test("the two 'no destination on file' refusals are recognised", () => {
  // Both casings, because the server mixes conventions: a domain transition
  // raises upper-cased, the API raises lower-cased.
  assert.ok(isBankRecipientMissing(new ApiError(409, "UNREADY_RECIPIENT_CHOICE_REQUIRED", "x")));
  assert.ok(isBankRecipientMissing(new ApiError(409, "recipient_setup_incomplete", "x")));
});

test("a frozen snapshot is not offered the same door", () => {
  // `valid_bank_recipient_snapshot_required` is also about a bank account and
  // also happens near money, but the destination it complains about is frozen
  // into a published round. Editing the live account does not thaw it, so
  // offering this door there would be offering one that does not open.
  assert.ok(
    !isBankRecipientMissing(
      new ApiError(409, "valid_bank_recipient_snapshot_required", "x"),
    ),
  );
  assert.ok(!isBankRecipientMissing(new ApiError(409, "no_obligations", "x")));
  assert.ok(!isBankRecipientMissing(new Error("network")));
});
