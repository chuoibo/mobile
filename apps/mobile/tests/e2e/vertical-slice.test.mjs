/* The whole slice against a running API, using the client the app uses.
 *
 * Every other test in this repo proves a piece. This one proves the pieces
 * connect: propose, confirm, open a batch, publish, and read the guest page
 * that comes out the other end -- through `src/api.ts`, not through hand-rolled
 * requests, so a client that drifts from the contract fails here.
 *
 * Needs a live server. Skips when there is not one, because a developer with
 * no Postgres should still be able to run the rest of the suite.
 *
 *     cd services/api && MOBILE_DATABASE_URL=... uvicorn app.api.main:app --port 8099
 *     cd apps/mobile && npm run test:e2e
 *
 * A skip is not a pass, and this file exists precisely to catch what the fakes
 * cannot -- so the skip has to be refusable. `MOBILE_REQUIRE_E2E=1` turns a
 * missing server into a failure, which is the form anyone claiming "the app
 * runs against the real API" has to run. Same convention as the backend's
 * `MOBILE_REQUIRE_POSTGRES_TESTS`, deliberately: one thing to remember rather
 * than two. Without it, the honest report of this suite is "39 passed, 1
 * skipped" -- and a skipped end-to-end reads exactly like a green one in a
 * summary line, which is how the slice sat unproven for a week.
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  attemptFor,
  BASE_URL,
  newAttempt,
  confirmExpense,
  confirmReceipt,
  loadBoard,
  openBatch,
  proposeSplit,
  publishBatch,
  registerPeople,
  saveBankRecipient,
} from "../../dist-test/api.js";
import { khoiDongNhom } from "../../dist-test/screens/chat/nhom.js";
import { DEMO_PEOPLE, personById } from "../../dist-test/navigation/nhom-demo.js";

/* Ba người này là thành viên THẬT của một nhóm THẬT, không phải id bịa ra.
 *
 * Trước bug-053800 file này mint ba id bằng `makeIdFactory` rồi `registerPeople`
 * cho chúng có tên. Đủ để `POST /expenses` trả lời -- nó chỉ chia tiền chứ
 * không ghi gì -- nhưng `confirm` thì không: `_require_participants_are_members`
 * đòi mọi người bị ghi nợ phải là thành viên ACTIVE của chính nhóm đó. Người
 * lạ trong một nhóm không tồn tại là hai lần sai một lúc, và lát cắt dừng ở
 * đúng chỗ ấy với `422 participant_not_in_context`.
 *
 * Nên nhóm được mở bằng đúng đường app mở: `khoiDongNhom`, cùng hàm màn chat
 * và Lên plan gọi. Gọi nhiều lần với các slug khác nhau vì nó tạo-hoặc-phát-lại
 * MỘT nhóm rồi mời thêm đúng người đang đăng nhập; ba lần là ba thành viên
 * trong cùng một nhóm, chứ không phải ba nhóm.
 */
const SLUGS = ["minh", "trang", "ngoc"];

function tenCuaNguoi(personId, displayName) {
  return (
    displayName ??
    DEMO_PEOPLE.find((p) => p.personId === personId)?.name ??
    personId
  );
}

/**
 * Open the demo group and return the three people this bill is split between.
 *
 * Throws rather than returning a failure state: every assertion below depends
 * on this, and a slice that carried on with an empty roster would report a
 * green split of nothing among nobody.
 *
 * The three are picked BY NAME out of the roster, not taken as "whatever the
 * roster happens to hold". That distinction is the difference between a test
 * that runs on this machine and a test that runs on the machine the demo
 * happens on:
 *
 *   - `khoiDongNhom` creates-or-REPLAYS one group under a fixed idempotency
 *     key, by design, so that chat, Lên plan and the expense flow all land in
 *     the same "Team Đà Lạt". On a database where `seed_demo_data.py` has run,
 *     that group already holds the seeded seven. Asking the roster for its
 *     length there answers 7, or 9 once anyone has invited a friend.
 *   - A bill is split between the people ON the bill, never between everyone
 *     in the group. `_require_participants_are_members` agrees: it asks that
 *     each participant BE an active member, not that the two sets be equal.
 *     A test that demanded equality was asserting a rule the server does not
 *     have, and the only way to keep it true was an empty database.
 *
 * So the count assertion is gone and a per-person one replaced it, which is
 * strictly the stronger check: three active members who are the WRONG three
 * satisfied `length === 3` and fail here. The old assertion's real content --
 * that the invite-and-accept round actually put `trang` and `ngoc` in the
 * group -- is still enforced, one named person at a time, and now says which
 * one is missing instead of printing a number.
 */
async function moNhom() {
  let state = null;
  for (const slug of SLUGS) {
    // `khoiDongNhom` takes the person, not the slug (bug-223337): a slug has no
    // `.personId`, so passing one addresses `PUT /people/undefined` and the run
    // dies at `dat-ten` on `X-Actor-ID must be a UUID`. `.mjs` is not typed, so
    // only a live run says so.
    const nguoi = personById(slug);
    assert.ok(nguoi, `khong co nguoi "${slug}" trong nhom demo`);
    state = await khoiDongNhom(nguoi, { base: BASE_URL });
    if (state.kind !== "xong") {
      assert.fail(
        `khong mo duoc nhom o buoc "${state.buoc}" (${state.status}) ${state.url}: ${state.detail}`,
      );
    }
  }
  const active = new Map(
    state.members.filter((m) => m.state === "active").map((m) => [m.personId, m]),
  );
  const nguoi = SLUGS.map((slug) => {
    const person = personById(slug);
    assert.ok(person, `khong co nguoi "${slug}" trong nhom demo`);
    const thanhVien = active.get(person.personId);
    assert.ok(
      thanhVien,
      `${person.name} (${person.personId}) khong phai thanh vien ACTIVE cua nhom ` +
        `${state.contextId} -- roster active dang co ${active.size} nguoi. ` +
        `May chu se tu choi ghi tien cho ho voi participant_not_in_context.`,
    );
    return { id: person.personId, name: tenCuaNguoi(person.personId, thanhVien.displayName) };
  });
  return { contextId: state.contextId, nguoi };
}

/* Invented, and the repo guard is right to ask about a long digit run. Not a
 * real bank, not a real account, nobody's money behind it. */
// repo-guard: allow=long-number reason=synthetic-test-account-number
const SO_TAI_KHOAN = "0000000000TEST";

async function serverIsUp() {
  try {
    const response = await fetch(`${BASE_URL}/healthz`);
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Whether this person already has a bank destination on the server.
 *
 * Read rather than assumed: the tail of the slice below depends on the answer
 * and the two kinds of database this file can be pointed at disagree about it.
 * A fresh one says no; one where `scripts/seed_demo_data.py` has run says yes.
 */
async function daCoTaiKhoanNhan(personId) {
  const res = await fetch(`${BASE_URL}/people/${personId}/bank-recipient`, {
    headers: { "X-Actor-ID": personId, "X-Actor-Roles": "group_admin,member" },
  });
  if (res.status === 404) return false;
  if (!res.ok) {
    assert.fail(`khong doc duoc nguoi nhan cua ${personId}: HTTP ${res.status}`);
  }
  return true;
}

/**
 * Refuse to run against a database that already holds somebody's data.
 *
 * Said out loud here, before the first write, rather than discovered 200 lines
 * later. Two steps below only hold on a database nobody has used:
 *
 *   - the server's refusal to open a batch for an advancer with no bank
 *     destination (section 8.4). Where the advancer already has one, that
 *     assertion stops testing anything at all;
 *   - `saveBankRecipient`, which REPLACES the destination already on file. On
 *     the seeded demo group that overwrites a real demo account
 *     ("MINH - DU LIEU DEMO", VietinBank) with this file's synthetic one --
 *     a test quietly damaging the demo somebody else is about to give.
 *
 * `scripts/e2e_slice.sh` provisions a throwaway PostgreSQL for exactly this
 * reason, and is how `make gate ONLY=e2e` runs this file, so the gate always
 * takes the fresh-database branch and the refusal above is always exercised
 * there. Pointing `EXPO_PUBLIC_API_URL` at the shared 8099 stack by hand is
 * the case this guard catches.
 *
 * A failure and not a skip, on this file's own rule: a skip reads like a pass.
 */
async function doiDatabaseSach(nguoiUngTien) {
  if (!(await daCoTaiKhoanNhan(nguoiUngTien.id))) return;
  assert.fail(
    `${nguoiUngTien.name} da co tai khoan nhan tien tren ${BASE_URL}, nen day la ` +
      `mot database DA CO DU LIEU. Lat cat doc se ghi de len tai khoan do va ` +
      `bo qua cong "nguoi nhan chua san sang". Chay 'scripts/e2e_slice.sh' ` +
      `(hoac 'make gate ONLY=e2e') -- no tu dung mot PostgreSQL dung mot lan.`,
  );
}

/** Set to anything non-empty when a skip must be read as a failure. */
const REQUIRED = Boolean(process.env.MOBILE_REQUIRE_E2E);

/**
 * Decide whether this test can run, honouring the refusal flag.
 *
 * Shared rather than inlined per test, because the flag is only worth having
 * if it covers every test in the file. One ungated skip left here would let
 * `MOBILE_REQUIRE_E2E=1` report success while quietly running nothing, which
 * is the exact failure the flag exists to make impossible.
 *
 * @returns true when the caller should return early.
 */
async function skipWithoutServer(t) {
  if (await serverIsUp()) return false;
  if (REQUIRED) {
    // Thrown rather than skipped: the caller said out loud that a run
    // without a server is a failed run, and honouring that is the only way
    // this file can back the claim it is cited for.
    assert.fail(
      `MOBILE_REQUIRE_E2E dat roi nhung khong co server tai ${BASE_URL}. ` +
        `Chay uvicorn tren cong do roi chay lai.`,
    );
  }
  t.skip(`khong co server tai ${BASE_URL} — chay uvicorn roi chay lai`);
  return true;
}

test("một khoản chi đi hết đường tới link của khách", async (t) => {
  if (await skipWithoutServer(t)) return;

  const { contextId, nguoi } = await moNhom();
  // The advancer is the group's admin, which is who `khoiDongNhom` makes the
  // creator. Named off the roster rather than hard-coded so this keeps working
  // if the demo group's first member ever changes.
  const ungTien = nguoi.find((n) => n.name === "Minh") ?? nguoi[0];
  await doiDatabaseSach(ungTien);
  const draft = {
    participants: nguoi,
    totalVnd: 300_000,
    advancerId: ungTien.id,
    occasion: "bữa lẩu tối thứ bảy",
  };
  const conLai = nguoi.filter((n) => n.id !== ungTien.id);
  const tenConLai = conLai.map((n) => n.name);

  // Filed the way App.tsx files them, so this exercises the client's real
  // retry behaviour rather than a shape invented for the test.
  const lanBam = {};

  // Names before anything refers to the ids, which is the order App.tsx uses.
  // `PUT /people/{id}` is the only way a name enters this product, and it
  // shipped as a route with no caller: the server had it, the client never
  // called it, and the guest page went on printing UUIDs while every screen in
  // the app still showed the typed name. Asserted at the bottom of this test
  // against the rendered page rather than here, because a 201 from this call
  // proves the request was accepted, not that a reader ever sees the name.
  await registerPeople(draft.participants, ungTien.id, lanBam);

  const proposal = await proposeSplit(contextId, draft, attemptFor(lanBam, "khoan-chi"));

  // Money rule 2, checked against what the server actually returned rather
  // than against anything computed here.
  const total = Object.values(proposal.allocations).reduce((a, b) => a + b, 0);
  assert.equal(total, draft.totalVnd, "phần chia không cộng lại thành tổng");
  assert.equal(Object.keys(proposal.allocations).length, 3);
  for (const amount of Object.values(proposal.allocations)) {
    assert.ok(Number.isInteger(amount), `${amount} không phải số nguyên đồng`);
  }

  const written = await confirmExpense(proposal, attemptFor(lanBam, "xac-nhan"));
  assert.ok(written.expenseVersionId, "confirm không trả về version");
  assert.equal(written.acknowledged, true, "người ứng tiền chưa được ghi nhận");

  // Before the recipient exists the server refuses, and refusing is correct:
  // section 8.4 says an unready recipient is a decision somebody has to make
  // out loud. Asserted rather than assumed -- if this ever stops refusing, a
  // batch can freeze with nowhere to send the money.
  await assert.rejects(
    () => openBatch(proposal, written.expenseVersionId, written.acknowledged, attemptFor(lanBam, "mo-dot-thu")),
    (error) => error.code === "UNREADY_RECIPIENT_CHOICE_REQUIRED",
    "may chu phai doi hoi quyet dinh ve nguoi nhan chua san sang",
  );

  // The half that used to be missing, and it is now the app doing it.
  //
  // This line was `seedBankRecipient(NAM.id)`: a Python script that reached
  // past the API and INSERTed the row, because nothing the app could do
  // produced a bank destination. The route existed the whole time; what did
  // not exist was any screen calling it, so the end-to-end test had to fake
  // the one step a person would actually perform. It now goes over the same
  // HTTP as every other call in this file, through the same client the screen
  // uses -- which means a client that drifts from the contract fails here
  // rather than at a demo.
  const saved = await saveBankRecipient(
    ungTien.id,
    { bankBin: "970418", accountNumber: SO_TAI_KHOAN, accountName: "NGUOI UNG TIEN" },
    // The actor is the subject. Section 9.2 has no exception for an admin, so
    // passing anybody else here is a 403 rather than a convenience.
    ungTien.id,
    attemptFor(lanBam, "tai-khoan-nhan"),
  );
  assert.equal(saved.bankName, "BIDV", "máy chủ gọi tên ngân hàng khác app");
  assert.ok(saved.bankRecognised);
  assert.ok(
    !JSON.stringify(saved).includes(SO_TAI_KHOAN),
    "số tài khoản đầy đủ đi ngược về phía client",
  );

  // The same attempt as the refused call above, deliberately. The server
  // releases a key when its handler errors, so the retry after seeding must be
  // allowed to run -- and this is the app's own behaviour, since `attemptFor`
  // returns one attempt per thing being written.
  const batch = await openBatch(
    proposal,
    written.expenseVersionId,
    written.acknowledged,
    attemptFor(lanBam, "mo-dot-thu"),
  );
  assert.ok(batch.batchId);
  // Two people owe the advancer; the advancer does not owe themselves.
  assert.equal(batch.obligations.length, 2);
  assert.ok(!batch.obligations.some((o) => o.senderId === ungTien.id));

  // Gate 1 is the server's answer, carried through confirm. Gate 2 is the
  // server's to enforce and is not modelled here at all.
  assert.equal(batch.gates.payerAcknowledged, true);
  await assert.rejects(
    () => publishBatch(batch.batchId, { payerAcknowledged: false }, ungTien.id, attemptFor(lanBam, "phat")),
    (error) => error.name === "GateNotPassedError",
    "phat duoc trong khi nguoi ung tien chua xac nhan",
  );

  const envelopes = await publishBatch(
    batch.batchId,
    batch.gates,
    ungTien.id,
    attemptFor(lanBam, "phat"),
    draft.participants,
  );
  assert.equal(envelopes.length, 2);

  // The organiser has to be able to tell which link goes to whom. Against a
  // real server this is where ids leak in, because ids are all it sends back.
  for (const envelope of envelopes) {
    assert.ok(
      tenConLai.includes(envelope.senderName),
      `phong bi ghi "${envelope.senderName}" thay vi ten nguoi`,
    );
  }

  // The link is the product. If it does not render, nothing else mattered.
  const page = await fetch(envelopes[0].url);
  assert.equal(page.status, 200, `link khách trả về ${page.status}`);
  const html = await page.text();
  assert.ok(html.includes("Phần của"), "trang khách không hiện phần của ai");

  // ...and it has to name a person, which the line above never checked. It
  // asserts the words "Phần của" are on the page; it stayed green for the
  // entire life of this file while the sentence underneath read "Phần của
  // a5b2c277-9b99-4699-a875-ed324e886237". The words were there. The person
  // was not.
  //
  // The guest page is the one screen somebody outside the group ever sees, and
  // it is asking them for money. A machine id in that sentence tells the reader
  // neither who is asking nor which of their own debts this is, so the two
  // things the page exists to say are exactly the two it fails to say. Checked
  // against the rendered page rather than against the view model, because the
  // ids reach the reader through the template and nothing in between was
  // looking.
  const nguoiNo = conLai[conLai.length - 1];
  const phongBi = envelopes.find((envelope) => envelope.senderId === nguoiNo.id);
  assert.ok(phongBi, `khong tim thay phong bi cua ${nguoiNo.name}`);
  const guestHtml = await (await fetch(phongBi.url)).text();
  // Script and style bodies survive tag-stripping and are not read by anyone,
  // so they are removed first; what is left is what a person actually sees.
  const visible = guestHtml
    .replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, " ")
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ");

  const strayId = visible.match(
    /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
  );
  assert.equal(
    strayId?.[0] ?? null,
    null,
    `trang khách hiện mã máy "${strayId?.[0]}" ở chỗ đáng lẽ là tên người`,
  );
  assert.ok(
    visible.includes(`Phần của ${nguoiNo.name}`),
    `trang khách không nói phần này của ai — không thấy "Phần của ${nguoiNo.name}"`,
  );
  assert.ok(
    visible.includes(`${ungTien.name} đã ghi`),
    `trang khách không nói ai ghi khoản chi — không thấy "${ungTien.name} đã ghi"`,
  );

  // The share is asserted present before the total is asserted absent, and the
  // order matters. "300.000 is not on the page" passes trivially if the page
  // prints no money at all, or prints it in some other format; finding this
  // person's own amount first proves the negative below is about a leak rather
  // than about a template that renders nothing.
  const share = envelopes[0].amountVnd.toLocaleString("vi-VN").replace(/,/g, ".");
  assert.ok(html.includes(share), `trang khách không hiện ${share}`);
  assert.ok(!html.includes("300.000"), "trang khách để lộ tổng của cả nhóm");

  // The other half of the round, which the app had no way to reach until now:
  // the money comes back. Publishing is not the end of anything -- an
  // organiser still has to see who paid and say it arrived.
  const before = await loadBoard(contextId, batch.batchId, ungTien.id, draft.participants);
  assert.equal(before.obligations.length, 2);
  assert.ok(
    before.obligations.every((o) => o.status === "outstanding"),
    "co nghia vu da xong truoc khi ai tra tien",
  );
  assert.ok(
    before.obligations.every((o) => tenConLai.includes(o.senderName)),
    "bang doc ra id thay vi ten",
  );

  const owed = before.obligations[0];
  const receipt = await confirmReceipt(
    owed.id,
    owed.amountVnd,
    ungTien.id,
    attemptFor(lanBam, `bao-tien-ve:${owed.id}`),
  );
  assert.equal(receipt.status, "confirmed");

  // Read it back rather than trusting the reply: the board is what an
  // organiser looks at, and it derives status from the ledger rather than
  // storing it. If those two ever disagree, this is where it shows.
  const after = await loadBoard(contextId, batch.batchId, ungTien.id, draft.participants);
  const settled = after.obligations.find((o) => o.id === owed.id);
  assert.equal(settled.status, "confirmed", "bang khong thay tien da ve");
  assert.equal(
    after.obligations.filter((o) => o.status === "outstanding").length,
    1,
    "xac nhan mot nghia vu lam doi trang thai nghia vu khac",
  );
});

test("bấm hai lần chỉ ghi một khoản chi", async (t) => {
  if (await skipWithoutServer(t)) return;

  // The reported bug, end to end. Two identical `POST /expenses` with no
  // `Idempotency-Key` left two rows in `expenses`; the client sent no such
  // header on any route, so the server-side protection was installed and never
  // engaged. Counted from the client here rather than from the database: two
  // presses that return one `expense_id` are one row, and that is the fact an
  // organiser's ledger depends on.
  const { contextId, nguoi } = await moNhom();
  const ungTien = nguoi.find((n) => n.name === "Minh") ?? nguoi[0];
  const draft = {
    participants: nguoi,
    totalVnd: 420_000,
    advancerId: ungTien.id,
    occasion: "bấm hai lần",
  };

  const lanBam = {};
  const attempt = attemptFor(lanBam, "khoan-chi");
  const first = await proposeSplit(contextId, draft, attempt);
  const again = await proposeSplit(contextId, draft, attempt);

  assert.equal(
    again.expenseId,
    first.expenseId,
    "bam lai sinh ra khoan chi thu hai; mot bua an dang nam hai lan trong so",
  );

  // The control, and it is not optional: without it this test also passes on a
  // server that returns the same id for everything. A genuinely different
  // press has to write a genuinely different expense.
  const khac = await proposeSplit(contextId, draft, newAttempt());
  assert.notEqual(
    khac.expenseId,
    first.expenseId,
    "hai lan bam that su khac nhau bi gop lam mot, mat mot khoan chi",
  );
});
