/* Walk the bill-splitting hero path against the shared demo stack on :8099.
 *
 * Why this file exists at all, given `tests/e2e/` already walks this path:
 * both files in `apps/mobile/tests/e2e/` REFUSE to run against 8099, on
 * purpose. `vertical-slice.test.mjs` fails with "day la mot database DA CO
 * DU LIEU" because `saveBankRecipient` would overwrite the demo's real
 * destination, and `duong-bill.test.mjs` fails its roster precondition
 * (`nhom co 9 thanh vien active, cho doi 3`) because the demo group has
 * accumulated members. Both refusals are correct. Their consequence is that
 * the shipped suite cannot answer "does the hero path still work on the
 * machine we are about to demo", which is the question this file answers.
 *
 * How it stays safe on a shared stack: every identity is minted fresh per
 * run, so the group, the people and the bank destination are this run's own.
 * The advancer starts with NO bank recipient, which is what makes the
 * UNREADY_RECIPIENT_CHOICE_REQUIRED gate a real observation here rather than
 * a step skipped because the demo already had one on file.
 *
 * Calls go through `dist-test/api.js` -- the same compiled client the app
 * screens use -- so a client that has drifted from the server contract fails
 * here rather than in front of somebody being shown the product.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { randomUUID } from "node:crypto";

import {
  attemptFor,
  BASE_URL,
  confirmExpense,
  confirmReceipt,
  docBill,
  loadBoard,
  luuGanMon,
  openBatch,
  proposeSplit,
  publishBatch,
  registerPeople,
  saveBankRecipient,
  scanReceipt,
  taoBill,
  translated,
} from "../../../apps/mobile/dist-test/api.js";
import { readingFromWire } from "../../../apps/mobile/dist-test/receipt.js";

const ANH_BILL = process.argv[2] ?? "/tmp/qa2-bill/ro.jpg";
/* Synthetic throughout: a generated bill image, a landmark-free group name and
 * a test account number. Repo rules forbid real bill photos, real account
 * numbers and real participant names from ever reaching this tree. */
/* The same invented value `vertical-slice.test.mjs` uses, and for its reason:
 * not a real bank, not a real account, nobody's money behind it. Carrying no
 * long digit run also means the repo guard has nothing to ask about. */
const SO_TAI_KHOAN = "0000000000TEST";

const buoc = [];
let batDau = 0;

async function chang(ten, fn) {
  const t0 = Date.now();
  try {
    const ket = await fn();
    buoc.push({ ten, ok: true, ms: Date.now() - t0 });
    console.log(`  DAT   ${ten} (${Date.now() - t0}ms)`);
    return ket;
  } catch (error) {
    buoc.push({ ten, ok: false, ms: Date.now() - t0, loi: String(error?.message ?? error) });
    console.log(`  HONG  ${ten} (${Date.now() - t0}ms)\n        ${error?.message ?? error}`);
    throw error;
  }
}

/* Same header set `src/screens/chat/nhom.ts` sends. `X-Actor-Roles` is not
 * optional: without `member` in it the server answers 403 role_not_permitted,
 * which is what this walk hit on its first run. */
function headers(actorId, contexts) {
  const h = {
    "Content-Type": "application/json",
    Accept: "application/json",
    "X-Actor-ID": actorId,
    "X-Actor-Roles": "group_admin,member",
  };
  if (contexts) h["X-Actor-Contexts"] = contexts;
  return h;
}

async function json(path, options) {
  const response = await fetch(BASE_URL + path, options);
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(`${options?.method ?? "GET"} ${path} -> ${response.status} ${JSON.stringify(body)}`);
  }
  return body;
}

async function main() {
  batDau = Date.now();
  console.log(`Di bo duong hero tren ${BASE_URL}`);
  console.log(`Anh bill: ${ANH_BILL}\n`);

  const nguoi = [
    { id: randomUUID(), name: "An QA0031" },
    { id: randomUUID(), name: "Binh QA0031" },
    { id: randomUUID(), name: "Cuong QA0031" },
  ];
  const [a, b, c] = nguoi;
  const lanBam = {};

  await chang("dat ten ba nguoi moi (PUT /people/{id})", () =>
    registerPeople(nguoi, a.id, lanBam),
  );

  const context = await chang("tao nhom moi (POST /contexts)", () =>
    json("/contexts", {
      method: "POST",
      headers: { ...headers(a.id), "Idempotency-Key": randomUUID() },
      body: JSON.stringify({ display_name: "Nhom hau kiem qa-tt-0031" }),
    }),
  );
  const contextId = context.id;
  console.log(`        contextId=${contextId}`);

  await chang("moi va nhan hai thanh vien con lai", async () => {
    for (const m of [b, c]) {
      const moi = await json(`/contexts/${contextId}/members`, {
        method: "POST",
        headers: { ...headers(a.id, contextId), "Idempotency-Key": randomUUID() },
        body: JSON.stringify({ person_id: m.id }),
      });
      const membershipId = moi.id ?? moi.membership_id;
      await json(`/memberships/${membershipId}/accept`, {
        method: "POST",
        headers: { ...headers(m.id), "Idempotency-Key": randomUUID() },
      });
    }
    const roster = await json(`/contexts/${contextId}/members`, { headers: headers(a.id, contextId) });
    const active = (roster.members ?? roster).filter((m) => m.state === "active");
    assert.equal(active.length, 3, `nhom co ${active.length} thanh vien active, cho doi 3`);
  });

  /* Step 1 of the hero path: the photo reaches Gemini and comes back as lines.
   * Asserted on the SHAPE the assignment screen needs, not on the model's
   * wording -- the model is allowed to read "Lau thai" or "Lẩu Thái", and a
   * test that pins its exact string is testing the model, not the product. */
  const reading = await chang("QUET BILL: anh -> mon (POST /receipts/scan)", async () => {
    const bytes = readFileSync(ANH_BILL);
    /* Assembled at runtime from a file under /tmp -- no image bytes are in
     * this tree, and the generator that made it (`tests/qa/rd-qa-37/`) writes
     * only synthetic bills. The guard matches the shape of the string, not its
     * provenance, so the annotation says where the provenance is. */
    // repo-guard: allow=data-uri-base64 reason=runtime-encoded-synthetic-bill-from-tmp
    const uri = `data:image/jpeg;base64,${bytes.toString("base64")}`;
    /* `scanReceipt` hands back the raw wire shape; `readingFromWire` is the
     * step that turns it into what the assignment screen consumes, and it is
     * where the field checking lives. Walking the path without it would be
     * testing a shape no screen ever sees. */
    const doc = readingFromWire(await scanReceipt({ uri }, a.id));
    assert.ok(Array.isArray(doc.lines), "scan khong tra ve mang lines");
    assert.ok(doc.lines.length > 0, "scan tra ve 0 mon — man gan mon se trong");
    for (const line of doc.lines) {
      assert.ok(Number.isInteger(line.lineTotalVnd), `${line.lineTotalVnd} khong phai so nguyen dong`);
    }
    console.log(
      `        model doc ${doc.lines.length} mon, tong in tren bill=${doc.printedTotalVnd}, needsReview=${doc.needsReview}`,
    );
    for (const line of doc.lines) {
      console.log(`          - ${line.name} x${line.quantity} = ${line.lineTotalVnd}`);
    }
    return doc;
  });

  const tongMon = reading.lines.reduce((s, l) => s + l.lineTotalVnd, 0);

  /* Step 2: the AI's guess is filed as a GUESS. The screen draws
   * `ai_suggested` differently from `nguoi_chot`, so this distinction is the
   * product, not an implementation detail. */
  const goiY = Object.fromEntries(reading.lines.map((l, i) => [l.id, i === 0 ? [a.id, b.id, c.id] : [c.id]]));
  const bill = await chang("GAN MON: bill + goi y cua AI (POST /bills)", async () => {
    const created = await taoBill(reading, contextId, goiY, a.id, attemptFor(lanBam, "tao-bill"));
    assert.ok(created.id, "POST /bills khong tra ve id");
    assert.equal(created.context_id, contextId);
    assert.equal(created.items_total_vnd, tongMon, "tong dong khong khop tong cac mon");
    assert.equal(created.assignment_state, "ai_suggested", "chua ai bam ma da khong con la phong doan");
    return created;
  });

  await chang("GAN MON: nguoi sua lai roi chot (PUT /bills/{id}/assignments)", async () => {
    const daChot = Object.fromEntries(reading.lines.map((l) => [l.id, [a.id, b.id, c.id]]));
    const sau = await luuGanMon(bill.id, reading, daChot, a.id, contextId, attemptFor(lanBam, "gan-mon"));
    assert.notEqual(sau.assignment_state, "ai_suggested", "bam chot roi ma van con nhan ai_suggested");
    const doc = await docBill(bill.id, a.id, contextId);
    assert.equal(doc.items_total_vnd, tongMon);
    console.log(`        assignment_state=${sau.assignment_state}`);
  });

  /* Step 3: money. Every number below is the SERVER's answer; nothing here
   * re-divides the bill, because a second allocator in a test only proves two
   * bugs agree. Money law 2 (sum == total) and law 1 (integers) are asserted
   * as invariants over what came back. */
  const draft = {
    participants: nguoi,
    totalVnd: tongMon,
    advancerId: a.id,
    occasion: "hau kiem qa-tt-0031",
  };
  const proposal = await chang("TAO KHOAN CHI: allocator chia (POST /expenses)", async () => {
    const p = await proposeSplit(contextId, draft, attemptFor(lanBam, "khoan-chi"));
    const tong = Object.values(p.allocations).reduce((x, y) => x + y, 0);
    assert.equal(tong, draft.totalVnd, "luat tien 2: phan chia khong cong lai thanh tong");
    assert.equal(Object.keys(p.allocations).length, 3);
    for (const v of Object.values(p.allocations)) {
      assert.ok(Number.isInteger(v), `luat tien 1: ${v} khong phai so nguyen dong`);
    }
    console.log(`        tong=${tong}, phan chia=${JSON.stringify(p.allocations)}`);
    return p;
  });

  const written = await chang("TAO KHOAN CHI: ghi vao so (POST /expenses/{id}/confirm)", async () => {
    const w = await confirmExpense(proposal, attemptFor(lanBam, "xac-nhan"));
    assert.ok(w.expenseVersionId, "confirm khong tra ve version");
    assert.equal(w.acknowledged, true);
    return w;
  });

  /* The gate this run can actually observe because the advancer is new: a
   * batch must refuse to open while there is nowhere to send the money. */
  await chang("DOT THU: tu choi khi nguoi nhan chua san sang", async () => {
    await assert.rejects(
      () => openBatch(proposal, written.expenseVersionId, written.acknowledged, attemptFor(lanBam, "mo-dot-thu")),
      (error) => error.code === "UNREADY_RECIPIENT_CHOICE_REQUIRED",
      "may chu phai doi hoi quyet dinh ve nguoi nhan chua san sang",
    );
  });

  await chang("DOT THU: luu tai khoan nhan cua CHINH nguoi ung tien", async () => {
    const saved = await saveBankRecipient(
      a.id,
      { bankBin: "970418", accountNumber: SO_TAI_KHOAN, accountName: "NGUOI UNG TIEN" },
      a.id,
      attemptFor(lanBam, "tai-khoan-nhan"),
    );
    assert.ok(saved.bankRecognised, "may chu khong nhan ra ngan hang");
    assert.ok(
      !JSON.stringify(saved).includes(SO_TAI_KHOAN),
      "so tai khoan day du di nguoc ve phia client",
    );
    console.log(`        bankName=${saved.bankName}`);
  });

  const batch = await chang("DOT THU: mo dot thu (POST /batches)", async () => {
    const bt = await openBatch(proposal, written.expenseVersionId, written.acknowledged, attemptFor(lanBam, "mo-dot-thu"));
    assert.ok(bt.batchId);
    assert.equal(bt.obligations.length, 2, "hai nguoi no nguoi ung tien");
    assert.ok(!bt.obligations.some((o) => o.senderId === a.id), "nguoi ung tien tu no chinh minh");
    assert.equal(bt.gates.payerAcknowledged, true);
    return bt;
  });

  const envelopes = await chang("DOT THU: phat envelope + VietQR (POST /batches/{id}/publish)", async () => {
    const env = await publishBatch(batch.batchId, batch.gates, a.id, attemptFor(lanBam, "phat"), nguoi);
    assert.equal(env.length, 2);
    for (const e of env) {
      assert.ok(e.url, "envelope khong co duong dan cho khach");
      assert.ok(Number.isInteger(e.amountVnd), "so tien envelope khong phai so nguyen");
      /* VietQR is the last mile of the hero path, so its presence and its
       * EMVCo shape are asserted here. What is NOT asserted -- and cannot be
       * from any agent -- is whether a real banking app scans it. */
      for (const ob of e.obligations) {
        assert.ok(ob.vietqrPayload, "nghia vu khong co payload VietQR");
        assert.ok(ob.vietqrPayload.startsWith("000201"), "payload khong mo dau bang EMVCo 000201");
        assert.ok(/6304[0-9A-F]{4}$/.test(ob.vietqrPayload), "payload khong ket thuc bang CRC 6304xxxx");
      }
    }
    console.log(`        VietQR: ${env[0].obligations[0].vietqrPayload.slice(0, 24)}... (${env[0].obligations[0].vietqrPayload.length} ky tu)`);
    return env;
  });

  /* Step 4: the guest page. Assert the person's OWN share is on the page
   * BEFORE asserting the group total is not -- a blank page passes the
   * negative on its own, which is how a leak check quietly stops checking. */
  const trangKhach = await chang("TRANG KHACH: GET /g/{token} render va khong lo tong nhom", async () => {
    const e = envelopes[0];
    const url = e.url;
    const response = await fetch(url);
    assert.equal(response.status, 200, `trang khach tra ${response.status}`);
    const html = await response.text();
    const phanCuaMinh = e.amountVnd.toLocaleString("vi-VN").replace(/,/g, ".");
    assert.ok(html.includes(phanCuaMinh), `khong thay phan cua chinh khach (${phanCuaMinh}) tren trang`);
    const tongNhom = draft.totalVnd.toLocaleString("vi-VN").replace(/,/g, ".");
    assert.ok(!html.includes(tongNhom), `trang khach lo tong ca nhom (${tongNhom})`);
    const nguoiKhac = envelopes[1].amountVnd.toLocaleString("vi-VN").replace(/,/g, ".");
    if (nguoiKhac !== phanCuaMinh) {
      assert.ok(!html.includes(nguoiKhac), `trang khach lo phan cua nguoi khac (${nguoiKhac})`);
    }
    assert.ok(html.includes("An QA0031"), "trang khach khong in ten nguoi nhan tien");
    console.log(`        ${url}`);
    console.log(`        phan cua khach=${phanCuaMinh}, tong nhom (${tongNhom}) KHONG co tren trang`);
    return { html, url };
  });

  await chang("TRANG KHACH: khach bao da chuyen (POST /g/{token}/da-chuyen)", async () => {
    const e = envelopes[0];
    const token = e.url.split("/").filter(Boolean).pop();
    /* `obligation_id` is a required form field -- an empty body is a 422, and
     * correctly so: the page has to say WHICH debt was paid. */
    const response = await fetch(`${BASE_URL}/g/${token}/da-chuyen`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ obligation_id: e.obligations[0].obligationId }).toString(),
      redirect: "manual",
    });
    assert.ok([200, 201, 303, 302].includes(response.status), `da-chuyen tra ${response.status}`);
    console.log(`        khach bao da chuyen -> ${response.status}`);
  });

  await chang("NGUOI NHAN: confirm-receipt (POST /obligations/{id}/confirm-receipt)", async () => {
    /* The same obligation the guest just reported, so the two halves of the
     * handshake are about one debt rather than two unrelated ones. */
    const ob = envelopes[0].obligations[0];
    const done = await confirmReceipt(ob.obligationId, ob.amountVnd, a.id, attemptFor(lanBam, "nhan-tien"));
    assert.ok(done, "confirm-receipt khong tra ve gi");
    console.log(`        nguoi nhan xac nhan ${ob.amountVnd} dong`);
  });

  await chang("CA NHAN: so du cap nhat (GET /contexts/{id}/balances)", async () => {
    const board = await loadBoard(contextId, batch.batchId, a.id, nguoi);
    assert.ok(board, "khong doc duoc bang so du");
    console.log(`        doc duoc bang so du sau khi nhan tien`);
  });

  return { contextId, billId: bill.id, batchId: batch.batchId, tongMon, trangKhach: trangKhach.url };
}

main()
  .then((ket) => {
    const dat = buoc.filter((b) => b.ok).length;
    console.log(`\n===============================================`);
    console.log(`DAT ${dat}/${buoc.length} chang — ${((Date.now() - batDau) / 1000).toFixed(1)}s`);
    console.log(`contextId=${ket.contextId}`);
    console.log(`tong bill=${ket.tongMon} dong`);
    console.log(`===============================================`);
    process.exit(0);
  })
  .catch((error) => {
    const dat = buoc.filter((b) => b.ok).length;
    console.log(`\n===============================================`);
    console.log(`HONG o chang ${dat + 1}/${buoc.length}: ${buoc[buoc.length - 1]?.ten}`);
    console.log(String(error?.stack ?? error).split("\n").slice(0, 6).join("\n"));
    console.log(`===============================================`);
    process.exit(1);
  });
