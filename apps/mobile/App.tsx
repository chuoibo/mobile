/** Organiser flow: enter, review, collect, share.
 *
 * A plain state machine rather than a router. Spec section 14.3 says not to
 * build a Home screen or a tab shell before the actions are known, and this
 * flow is a line, not a graph. A router can arrive when there is a second
 * entry point to route to.
 *
 * That second entry point has now arrived. The flow below is unchanged and
 * still a line; what changed is that it is no longer the whole app. It is
 * reached from the shell's [+] menu as "Tạo khoản chi", and it is handed the
 * way back out as `onExit` rather than reaching for the shell itself -- the
 * shell knows about this flow, this flow does not know about the shell.
 *
 * The line now starts at the camera. "Tạo khoản chi" in the [+] menu says
 * "Chụp bill hoặc nhập tay", and this is the file where that sentence is kept
 * true: the flow opens on the viewfinder, and "Huỷ" there drops to the manual
 * form rather than out of the flow -- the two halves of that promise, in the
 * order the mockup puts them.
 */
import { useCameraPermissions, type CameraView } from "expo-camera";
import { StatusBar } from "expo-status-bar";
import React, { useEffect, useRef, useState } from "react";
import { Pressable, SafeAreaView, ScrollView, Text, View, useColorScheme } from "react-native";
import { AppRoot } from "./src/navigation/AppRoot";
import {
  attemptFor,
  confirmExpense,
  confirmReceipt,
  isBankRecipientMissing,
  loadBoard,
  openBatch,
  previewSplit,
  proposeSplit,
  publishBatch,
  registerPeople,
  saveBankRecipient,
  scanReceipt,
  thongDiepNguoiDoc,
  type Attempt,
  type PendingProposal,
  BASE_URL,
  type PublishGates,
  type SavedBankRecipient,
  type SplitPreview,
} from "./src/api";
import { CoLoi, DangTai, TrongRong } from "./src/ui/TrangThai";
import {
  HAS_CAMERA,
  nativeBackend,
  openAppSettings,
  readAccess,
  withBillPhoto,
  type GiaiDoanDocBill,
} from "./src/camera";
import { itemsTotalVnd, readingFromWire, type BillReading } from "./src/receipt";
import {
  addPersonToAll,
  alignToRoster,
  blockingProblem,
  dropPerson,
  everyoneShares,
  itemsForWire,
  signature,
  syncLines,
  toggle,
  type Assignment,
} from "./src/assignment";
import { ChupBill } from "./src/screens/ChupBill";
import { GoiYChia } from "./src/screens/GoiYChia";
import { KetQuaNhanDien } from "./src/screens/KetQuaNhanDien";
import { KetQuaThanhToan } from "./src/screens/KetQuaThanhToan";
import { MaVietQr } from "./src/ui/MaVietQr";
import { ChiaSe, type Envelope } from "./src/screens/ChiaSe";
import { DeXuat, type Proposal } from "./src/screens/DeXuat";
import { DotThu, type Obligation } from "./src/screens/DotThu";
import { Draft, NhapKhoanChi } from "./src/screens/NhapKhoanChi";
import { TaiKhoanNhan } from "./src/screens/tai-khoan/TaiKhoanNhan";
import { FORM_TRONG } from "./src/screens/tai-khoan/kiem-tra";
import {
  EMPTY_FORM,
  addParticipant,
  makeIdFactory,
  removeParticipant,
  type DraftForm,
} from "./src/participants";
import { space, type, usePalette } from "./src/theme";
import { Button } from "./src/ui/Kit";
import {
  DEMO_ADVANCER_ID,
  DEMO_ALLOCATIONS,
  DEMO_ENVELOPES,
  DEMO_ITEM_COUNT,
  DEMO_OBLIGATIONS,
  DEMO_ROSTER,
} from "./src/fixtures/thanh-toan-demo";

type Step =
  | "chup-bill"
  | "ket-qua"
  | "goi-y"
  | "nhap"
  | "de-xuat"
  // Not a step on the line. A detour off "de-xuat", reached only when the
  // server refuses to open a round for want of somewhere to send the money,
  // and it returns to exactly where it was called from.
  | "tai-khoan-nhan"
  | "dot-thu"
  | "ket-qua-tt"
  | "chia-se";

/**
 * Who the app says it is when it asks for a bill to be read.
 *
 * `POST /receipts/scan` wants an actor like every other route, and the bill is
 * read before anybody has typed a single name -- there is no roster yet to
 * borrow an id from. So one id is minted per launch and used for the scan
 * only. It never reaches an expense, an obligation or an envelope: nothing is
 * stored against it, because reading a photo writes nothing.
 *
 * Module-level rather than in state, so a re-render mid-upload cannot change
 * who is asking halfway through.
 */
const SCAN_ACTOR_ID = makeIdFactory()();

/**
 * The two screens that own their whole pane.
 *
 * Both draw their own top-left control -- "Huỷ" on the viewfinder, "Chụp lại"
 * on the reading -- so the flow's own "← Đóng" row is not drawn above them.
 * Two back-controls in the same corner is one too many, and on the viewfinder
 * the row also painted a cream strip along the top of a black screen, which
 * read as the camera failing to reach the top of the phone.
 */
const TOAN_MAN: Step[] = ["chup-bill", "ket-qua"];

/**
 * What a press is trying to write, as a string.
 *
 * This is the name an attempt is filed under, so it decides when a key is
 * reused and when a fresh one is minted -- and the server's rule is that a key
 * may be reused only while the bytes stay identical. Every field the expense
 * body carries is in here for that reason: change the total, the occasion, who
 * paid, who is in, or which boxes are ticked, and this is a different write
 * that must not replay the answer to the previous one.
 *
 * The matrix signature used to be missing. Editing who ate what and sending
 * again reused the old key against a new body, which the server answers with
 * 422 `idempotency_key_reuse`.
 */
function expenseIntent(d: Draft, matrixSig: string): string {
  const who = d.participants.map((person) => person.id).join(",");
  return `khoan-chi:${d.advancerId}:${d.totalVnd}:${d.occasion}:${who}:${matrixSig}`;
}

/**
 * The id minted for a person added on the split screen.
 *
 * Separate from the scan actor above: that one says who is *asking* for a bill
 * to be read, this one names somebody who is going to *owe money*. Sharing a
 * factory between the two would let a scan id land in the roster.
 */
const NEXT_SPLIT_PERSON_ID = makeIdFactory();

function LuongKhoanChi({ onExit }: { onExit: () => void }) {
  const c = usePalette();
  const scheme = useColorScheme();
  // The bill comes first. This is the hero path: photograph the paper, let the
  // reader turn it into lines, correct what it misread, and only then talk
  // about who owes what. "Huỷ" on that first screen lands on the old manual
  // entry, which is still the whole flow for a group that has no paper bill.
  const [step, setStep] = useState<Step>("chup-bill");
  const [draft, setDraft] = useState<Draft | null>(null);
  // Held here, not inside the screen. "Sửa lại" unmounts the screen, and a
  // form owned by the screen goes with it -- which erased everything a
  // person had typed the moment they tried to change one number.
  const [form, setForm] = useState<DraftForm>(EMPTY_FORM);
  const [proposal, setProposal] = useState<PendingProposal | null>(null);
  // Held across attempts on purpose. Confirming writes a new expense version
  // every time it is called, and opening the batch right after it can fail --
  // it does today, when nobody owed money has a bank account on file. Without
  // this, pressing "Xác nhận" again wrote a second version of the same expense
  // into the ledger, and a third, each one indistinguishable from a real edit.
  const [written, setWritten] = useState<{
    expenseVersionId: string;
    acknowledged: boolean;
  } | null>(null);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [envelopes, setEnvelopes] = useState<Envelope[]>([]);
  const [published, setPublished] = useState(false);
  // Whose code the settlement screen is showing. One at a time, on purpose:
  // a wall of codes is a wall of other people's bank accounts, and the person
  // holding the phone only ever needs their own.
  const [nguoiDangChon, setNguoiDangChon] = useState<string | null>(null);
  // Spec section 8.3. Reported by the batch, never assumed by the screen.
  const [gates, setGates] = useState<PublishGates>({ payerAcknowledged: false });
  const [error, setError] = useState<string | null>(null);
  // Whether the failure on screen is the one a person can actually do something
  // about from here. Kept beside `error` rather than parsed out of it: the
  // sentence is written for a reader and will be reworded, and a screen that
  // decides whether to offer a way out by matching words in a message breaks
  // the next time somebody improves the wording.
  const [thieuTaiKhoanNhan, setThieuTaiKhoanNhan] = useState(false);
  // Set once the destination is stored, and shown back masked. Only so the
  // proposal screen can say the blocker is gone -- pressing the same button
  // again with no acknowledgement reads as pressing it and hoping.
  const [taiKhoanNhan, setTaiKhoanNhan] = useState<SavedBankRecipient | null>(null);
  const [busy, setBusy] = useState(false);
  // One attempt per thing being written, minted on the first press and kept.
  //
  // A fresh key on every press is the obvious version and it is wrong in the
  // one case that matters: the request reached the server, the reply did not
  // reach us, the person presses again. A new key makes that a second arrival
  // -- a second expense in the ledger, or an obligation pushed to
  // `over_confirmed`, which reads as somebody having paid more than they owed.
  //
  // This covers every write, not just receipts. It used to hold receipt keys
  // alone, which was the only route whose key the server ever saw, because no
  // route sent the header at all.
  //
  // Kept in a ref rather than state so a re-render between the press and the
  // reply cannot lose it. State would be restored asynchronously, and the gap
  // is exactly when a person presses again.
  const attempts = useRef<Record<string, Attempt>>({});

  // --- reading a bill -------------------------------------------------
  const cameraRef = useRef<CameraView | null>(null);
  const [permission, requestPermission] = useCameraPermissions();
  const [reading, setReading] = useState<BillReading | null>(null);
  // Which half of the read is running. Reported by `withBillPhoto` as it
  // crosses each boundary, never inferred from a clock: a stage line driven by
  // a timer says "đang gửi" while compression is still going on a slow phone,
  // which is the screen making something up.
  const [giaiDoan, setGiaiDoan] = useState<GiaiDoanDocBill | null>(null);
  // Bumped on every accepted scan, and used as the result screen's `key`.
  // That screen keeps per-row drafts of half-typed numbers; without a new key
  // React reuses the mounted instance, and a rescan showed the previous bill's
  // rejected "12x" still sitting in row three of a completely different bill.
  const [scanSeq, setScanSeq] = useState(0);
  const access = readAccess(permission, HAS_CAMERA);
  // Held here, not inside the screen. The screen unmounts on every step
  // change; a roster or a matrix owned there would vanish the moment someone
  // pressed back, and they would have to name everybody again.
  const [assignment, setAssignment] = useState<Assignment>({});
  const [preview, setPreview] = useState<{
    signature: string;
    split: SplitPreview;
  } | null>(null);

  /**
   * Take (or pick) one photo, have it read, and show what came back.
   *
   * `withBillPhoto` owns the file: it compresses, hands the bytes to the
   * upload, and deletes both the capture and the compressed copy afterwards --
   * including when the upload throws. Nothing here ever holds a uri, which is
   * the point. A `null` result is somebody backing out of the picker, and
   * backing out is not an error to shout about.
   */
  function scan(source: "camera" | "thu-vien") {
    return guard(async () => {
      // Cleared in `finally` rather than after a success. A failed read that
      // left the stage set would put "AI đang đọc" under an error message.
      let wire;
      try {
        wire = await withBillPhoto(
          nativeBackend(cameraRef),
          source,
          (photo) => scanReceipt(photo, SCAN_ACTOR_ID),
          setGiaiDoan,
        );
      } finally {
        setGiaiDoan(null);
      }
      if (wire === null) return;
      setReading(readingFromWire(wire));
      setAssignment({});
      setPreview(null);
      setScanSeq((n) => n + 1);
      setStep("ket-qua");
    });
  }

  /**
   * Re-read the board from the server.
   *
   * Nothing here polls. A guest reporting a transfer changes the server, not
   * this screen, and a screen that quietly went stale would show an organiser
   * "chưa chuyển" next to money that arrived an hour ago. The button says out
   * loud that looking is an action.
   */
  async function refreshBoard() {
    if (!batchId || !proposal) return;
    const board = await loadBoard(batchId, proposal.advancerId, proposal.participants);
    setObligations(board.obligations);
  }

  async function guard(work: () => Promise<void>) {
    setError(null);
    setThieuTaiKhoanNhan(false);
    setBusy(true);
    try {
      await work();
    } catch (problem) {
      // Say what failed and what to do. "Something went wrong" is not an
      // error message, it is an apology.
      // `api.ts` already turns an unreachable server into an ApiError whose
      // message names the address it tried, so there is nothing to add here.
      // The branch that used to sit here looked for "fetch" in the message and
      // could never match -- a fallback that reads as careful and never runs.
      setError(problem instanceof Error ? problem.message : String(problem));
      // A sentence explaining a refusal is not the same as a way past it. This
      // is the one refusal on the flow whose fix is a screen in this app, so it
      // is the one that gets a button -- see `isBankRecipientMissing`.
      setThieuTaiKhoanNhan(isBankRecipientMissing(problem));
    } finally {
      setBusy(false);
    }
  }

  /**
   * Preview the split ~450ms after the last tick.
   *
   * The attempt is filed under `xem-truoc:` + the matrix signature. The same
   * ticks produce the same key *and* the same body, so the server replays
   * instead of inserting another expense. Ticking back and forth does not
   * fill the ledger with junk.
   *
   * `paid_by_id` is `participantIds[0]`. Nobody has chosen who paid yet --
   * that is the next screen -- and the allocator still needs somewhere to
   * park the leftover dong. That is why the rounding_gainers line is on
   * this screen: the 1đ assignment here is provisional.
   *
   * The timeout is cleared on unmount and on every change. A reply for a
   * signature that is no longer current is dropped, so a slow round-trip
   * cannot overwrite a newer one.
   */
  useEffect(() => {
    if (step !== "goi-y" || reading === null) return;
    const ids = form.roster.participants.map((person) => person.id);
    const blocked = blockingProblem(reading, ids, assignment);
    if (blocked !== null || ids.length === 0) return;
    const sig = signature(reading, ids, assignment);
    let cancelled = false;
    const timer = setTimeout(() => {
      const payerId = ids[0];
      if (payerId === undefined) return;
      previewSplit(
        {
          participantIds: ids,
          totalVnd: itemsTotalVnd(reading),
          items: itemsForWire(reading, assignment),
          payerId,
          occasion: "xem trước chia",
        },
        attemptFor(attempts.current, `xem-truoc:${sig}`),
      )
        .then((split) => {
          if (cancelled) return;
          setPreview({ signature: sig, split });
        })
        .catch((problem) => {
          if (cancelled) return;
          setError(problem instanceof Error ? problem.message : String(problem));
        });
    }, 450);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [step, reading, form.roster, assignment]);

  // The viewfinder is the one screen that owns the whole pane. Left on the
  // cream page ground, the shell painted a light strip under a black screen
  // and the server line sat in it, which read as the camera screen failing to
  // reach the bottom of the phone.
  const dark = step === "chup-bill";
  const tuVe = TOAN_MAN.includes(step);
  // Who the money is owed to, by name. Falls back to a role rather than to the
  // id: an id on a button reads as a bug, and this button is offered at the
  // exact moment somebody is already looking at a refusal.
  const tenNguoiUngTien =
    proposal?.participants.find((person) => person.id === proposal.advancerId)?.name ??
    "người ứng tiền";

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: dark ? "#000" : c.ground }}>
      <StatusBar style={dark || scheme === "dark" ? "light" : "dark"} />

      {/* The way back to the tabs. The flow keeps its own "Sửa lại" for moving
          between steps; this is the separate question of leaving entirely, so
          it sits above the steps rather than inside any one of them.

          Not drawn over the two screens that already carry a top-left control
          of their own -- see `TOAN_MAN`. From those, the way out of the flow
          is one step further along: "Huỷ" reaches the manual form, and the
          row is there. */}
      {tuVe ? null : (
        <View style={{ paddingHorizontal: space.md, paddingTop: space.sm }}>
          <Pressable
            onPress={onExit}
            accessibilityRole="button"
            accessibilityLabel="Đóng khoản chi, quay lại các tab"
            style={({ pressed }) => ({
              alignSelf: "flex-start",
              minHeight: 44,
              justifyContent: "center",
              paddingRight: space.sm,
              opacity: pressed ? 0.6 : 1,
            })}
          >
            <Text style={{ ...type.body, color: c.accent }}>← Đóng</Text>
          </Pressable>
        </View>
      )}

      {step === "chup-bill" && (
        <ChupBill
          access={access}
          cameraRef={cameraRef}
          busy={busy}
          giaiDoan={giaiDoan}
          error={error}
          onShutter={() => scan("camera")}
          onPickImage={() => scan("thu-vien")}
          onRequestPermission={() => guard(async () => {
            await requestPermission();
          })}
          onOpenSettings={() => guard(openAppSettings)}
          // Not every group has a paper bill, and not every phone will open a
          // camera. Cancelling drops into the manual form rather than into a
          // dead end -- and the manual form is where "← Đóng" lives, so this
          // is also the way back out to the tabs.
          onCancel={() => { setError(null); setStep("nhap"); }}
        />
      )}

      {step === "ket-qua" && reading !== null && (
        <KetQuaNhanDien
          key={scanSeq}
          reading={reading}
          onChange={setReading}
          onRetake={() => { setError(null); setStep("chup-bill"); }}
          onContinue={() => {
            // The bill total becomes the expense total, as text, because that
            // is what the form holds -- `parseAmountVnd` reads it back on the
            // other side. Nothing is divided here: the allocator on the server
            // is still the only thing in this product that splits money.
            const ids = form.roster.participants.map((person) => person.id);
            setForm((f) => ({ ...f, amount: String(itemsTotalVnd(reading)) }));
            setAssignment((a) => syncLines(a, reading.lines, ids));
            setStep("goi-y");
          }}
        />
      )}

      {step === "goi-y" && reading !== null && (
        <GoiYChia
          reading={reading}
          roster={form.roster}
          assignment={assignment}
          preview={preview}
          onBack={() => { setError(null); setStep("ket-qua"); }}
          onReset={() => {
            setAssignment(
              everyoneShares(
                reading.lines,
                form.roster.participants.map((person) => person.id),
              ),
            );
          }}
          onToggle={(lineId, personId) => {
            setAssignment((a) => toggle(a, lineId, personId));
          }}
          onAddPerson={(name) => {
            const next = addParticipant(form.roster, name, NEXT_SPLIT_PERSON_ID);
            const added = next.participants[next.participants.length - 1];
            if (added === undefined) return;
            setForm((f) => ({ ...f, roster: next }));
            setAssignment((a) =>
              addPersonToAll(a, reading.lines.map((line) => line.id), added.id),
            );
          }}
          onRemovePerson={(id) => {
            setForm((f) => ({ ...f, roster: removeParticipant(f.roster, id) }));
            setAssignment((a) => dropPerson(a, id));
          }}
          onSeeResults={() => {
            setForm((f) => ({
              ...f,
              amount: String(itemsTotalVnd(reading)),
            }));
            setStep("nhap");
          }}
        />
      )}

      {step === "nhap" && (
        <NhapKhoanChi
          form={form}
          onForm={setForm}
          onNext={(d) => guard(async () => {
            setDraft(d);
            // A new proposal makes any previously written version stale: it
            // belongs to the numbers on the last screen, not these.
            setWritten(null);
            // Names first, and before anything refers to these ids. The server
            // stores participants as ids; the only place a name ever reaches it
            // is this call. Skip it and every screen here still reads correctly
            // off `form.roster`, while the guest page -- the one screen someone
            // outside the group sees, asking them for money -- prints a UUID
            // where the person should be.
            await registerPeople(d.participants, d.advancerId, attempts.current);
            // Pressing again after a failed send reuses the key, so the server
            // replays rather than writing a second expense. Editing a number
            // first changes the intent, so it mints a new one instead of
            // colliding with the old body and earning a 422.
            const ids = d.participants.map((person) => person.id);
            const aligned = reading === null
              ? assignment
              : alignToRoster(assignment, reading.lines, ids);
            const items = reading === null ? [] : itemsForWire(reading, aligned);
            const matrixSig = reading === null ? "" : signature(reading, ids, aligned);
            setProposal(
              await proposeSplit(
                d,
                attemptFor(attempts.current, expenseIntent(d, matrixSig)),
                items,
              ),
            );
            setStep("de-xuat");
          })}
        />
      )}

      {step === "de-xuat" && proposal && (
        <DeXuat
          proposal={proposal}
          taiKhoanNhan={
            taiKhoanNhan === null
              ? null
              : `${taiKhoanNhan.bankName} ${taiKhoanNhan.accountMasked}`
          }
          onBack={() => setStep("nhap")}
          onConfirm={() => guard(async () => {
            // Confirm writes the split into the ledger and tells us whether
            // the advancer acknowledged; the batch gate reads that answer
            // rather than assuming it. Written once: if opening the batch
            // fails, pressing the button again reuses the version already in
            // the ledger instead of writing another one beside it.
            const ledger =
              written ??
              (await confirmExpense(
                proposal,
                attemptFor(attempts.current, `xac-nhan:${proposal.expenseId}`),
              ));
            setWritten(ledger);
            const batch = await openBatch(
              proposal,
              ledger.expenseVersionId,
              ledger.acknowledged,
              attemptFor(attempts.current, `mo-dot-thu:${ledger.expenseVersionId}`),
            );
            setBatchId(batch.batchId);
            setObligations(batch.obligations);
            setGates(batch.gates);
            setPublished(false);
            setStep("dot-thu");
          })}
        />
      )}

      {step === "dot-thu" && (
        <DotThu
          obligations={obligations}
          published={published}
          gates={gates}
          onPublish={() => guard(async () => {
            const sent = await publishBatch(
              batchId!,
              gates,
              proposal!.advancerId,
              attemptFor(attempts.current, `phat:${batchId}`),
              proposal!.participants,
            );
            setEnvelopes(sent);
            setPublished(true);
            // Publishing is the moment the codes come into existence, so it is
            // the first moment the settlement screen has anything to draw.
            // Landing on the first envelope rather than on nothing: the common
            // case is one person owing one person, and asking them to pick
            // themselves out of a list of one is a step for the sake of it.
            setNguoiDangChon(sent[0]?.senderId ?? null);
            setStep("ket-qua-tt");
          })}
          onShare={() => setStep("chia-se")}
          busy={busy}
          onRefresh={() => guard(refreshBoard)}
          onConfirmReceipt={(o) => guard(async () => {
            await confirmReceipt(
              o.id,
              o.amountVnd,
              proposal!.advancerId,
              attemptFor(attempts.current, `bao-tien-ve:${o.id}`),
            );
            await refreshBoard();
          })}
        />
      )}

      {step === "ket-qua-tt" && proposal && (
        <KetQuaThanhToan
          roster={form.roster}
          // Straight from the server's allocator, not from anything this file
          // added up. `proposal.allocations` is what `POST /expenses` returned
          // and what `confirm` was checked against.
          allocations={proposal.allocations}
          obligations={obligations}
          envelopes={envelopes}
          advancerId={proposal.advancerId}
          itemCount={reading === null ? 0 : reading.lines.length}
          nguoiDangChon={nguoiDangChon}
          onChonNguoi={setNguoiDangChon}
          renderMaQr={(senderId) => {
            const envelope = envelopes.find((e) => e.senderId === senderId);
            if (envelope === undefined) return null;
            // One card per debt. A sender with two recipients gets two codes,
            // each labelled with who it pays, because scanning the wrong one
            // sends the right amount to the wrong person.
            return envelope.obligations.map((debt) => (
              <MaVietQr
                key={debt.obligationId}
                payload={debt.vietqrPayload}
                // The amount from the obligation list, not from the payload.
                // Passing the payload's own number would make the check inside
                // `MaVietQr` compare a value against itself and always agree.
                expectedAmountVnd={debt.amountVnd}
                recipientName={
                  obligations.find((o) => o.id === debt.obligationId)?.recipient ??
                  "người nhận"
                }
              />
            ));
          }}
          onShare={() => setStep("chia-se")}
          onDone={() => setStep("dot-thu")}
          onBack={() => setStep("dot-thu")}
        />
      )}

      {step === "chia-se" && (
        <ChiaSe envelopes={envelopes} onDone={() => setStep("dot-thu")} />
      )}

      {/* The detour. `actorId` is the advancer's own id, because the server
          only ever lets a person write their own destination -- section 9.2,
          and the one rule in the spec with no exception for an admin. On this
          phone the organiser and the advancer are the same person; the day
          they stop being, this call starts failing loudly rather than quietly
          writing into somebody else's row. */}
      {step === "tai-khoan-nhan" && proposal && (
        <TaiKhoanNhan
          nguoiNhan={{ id: proposal.advancerId, name: tenNguoiUngTien }}
          busy={busy}
          onBack={() => { setError(null); setStep("de-xuat"); }}
          onLuu={(dichDen) => guard(async () => {
            const saved = await saveBankRecipient(
              proposal.advancerId,
              dichDen,
              proposal.advancerId,
              // Filed under the destination, not under the person. Re-sending
              // the same digits after a dropped reply has to reuse the key so
              // the server replays; correcting a typo and sending again is a
              // different write and must mint a new one, or it collides with
              // the old body and earns a 422.
              attemptFor(
                attempts.current,
                `tai-khoan-nhan:${proposal.advancerId}:${dichDen.bankBin}:${dichDen.accountNumber}`,
              ),
            );
            setTaiKhoanNhan(saved);
            // Back to where the refusal happened, with the button that was
            // refused still under the thumb.
            setStep("de-xuat");
          })}
        />
      )}

      {error && (
        <View style={{ padding: space.md, backgroundColor: c.card, borderTopColor: c.warn, borderTopWidth: 2, gap: space.sm }}>
          <Text style={{ ...type.label, color: c.warn }}>{error}</Text>
          {/* The half that was missing. The sentence above was already right
              about why the round could not open; what QA found was that every
              control still on screen led back into the same wall. A refusal
              this app can fix gets a door next to it. */}
          {thieuTaiKhoanNhan && proposal ? (
            <Button
              label={`Ghi tài khoản nhận cho ${tenNguoiUngTien}`}
              onPress={() => { setError(null); setThieuTaiKhoanNhan(false); setStep("tai-khoan-nhan"); }}
            />
          ) : null}
        </View>
      )}

      {/* The address is on screen at all times, and that is the point. The
          banner used to read "dữ liệu giả, API chưa nối" -- true then, and the
          kind of line that stays after it stops being true. Naming the server
          cannot go stale: either the app is talking to it or it is not. */}
      <View style={{ paddingHorizontal: space.md, paddingBottom: space.sm }}>
        {/* `inkSoft` is measured on the cream ground and is unreadable on the
            viewfinder's black. Measured: white at 0.62 alpha composites to
            #9e9e9e, 7.84:1 on #000. */}
        <Text
          style={{
            ...type.label,
            color: dark ? "rgba(255, 255, 255, 0.62)" : c.inkSoft,
            textAlign: "center",
          }}
        >
          Máy chủ: {BASE_URL}
        </Text>
      </View>
    </SafeAreaView>
  );
}

/**
 * The settlement screen on frozen data, reachable from a URL, web only.
 *
 * Same reason as `tabTuUrl` in `AppRoot`, which the comment there spells out:
 * a detector renders a URL and cannot press anything. The real screen is eight
 * presses and a live server past the opening screen, so without this it never
 * gets scanned, and "the app was checked" quietly means "the opening screen
 * was checked".
 *
 * Narrow on purpose. One exact parameter value, nothing on native, no writes,
 * and every number comes from a fixture that says out loud it is one. It is
 * not a demo mode and not a way into the product: there is no route from here
 * to anything that touches a server.
 */
function manDo(): boolean {
  return manThamSo() === "ket-qua-thanh-toan";
}

function manThamSo(): string | null {
  const loc = (globalThis as { location?: { search?: string } }).location;
  if (!loc?.search) return null;
  return new URLSearchParams(loc.search).get("man");
}

/**
 * The three states, on one page, web only, for the detector and the camera.
 *
 * Same reason as `XemKetQuaThanhToan` above, and the same narrowness: one exact
 * parameter value, nothing on native, no writes, no route from here into the
 * product. What is new is *why* it has to exist for rd-fe-08 specifically.
 *
 * An empty state needs no data, a waiting state lasts about two seconds, and an
 * error state needs the server to be down. None of the three survives long
 * enough for a scan to catch it on the live flow, so without this page "the
 * states were checked" would quietly mean "the states were read in the source",
 * and `imp detect` on a `.tsx` file is close to blind -- it cannot compute
 * contrast or line length on markup it never rendered.
 *
 * These are the real components with the real copy, not mock-ups of them. If
 * the wording here looks wrong, it is wrong on the screens too.
 */
function XemTrangThai() {
  const c = usePalette();
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={{ padding: space.md, gap: space.md }}>
        <Text style={{ ...type.h1, color: c.ink }}>Ba trạng thái</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Trang để soi và chụp ảnh. Không phải một màn của sản phẩm.
        </Text>

        <Text style={{ ...type.title, color: c.ink }}>Đang tải</Text>
        <DangTai
          noiDung="Đang hỏi máy chủ chỗ nào hợp với nhóm"
          phu="Thường mất một, hai giây."
        />

        <Text style={{ ...type.title, color: c.ink }}>Rỗng</Text>
        <TrongRong
          tieuDe="Chưa có ai phải chuyển tiền"
          than="Khoản chi này không sinh nghĩa vụ nào. Thường là vì chỉ có một người trong nhóm, hoặc người ứng tiền cũng là người duy nhất phải trả."
        />
        <TrongRong
          tieuDe="Chưa có lời nhắn nào để gửi"
          than="Đợt thu chưa được phát nên chưa sinh mã cho ai. Quay lại đợt thu, bấm phát, rồi mở lại màn này."
          hanhDong={{ nhan: "Quay lại đợt thu", onPress: () => {} }}
        />

        <Text style={{ ...type.title, color: c.ink }}>Lỗi</Text>
        {/* The exact sentences `thongDiepNguoiDoc` produces, so this page shows
            what a person really reads rather than a friendlier rewrite of it. */}
        <CoLoi
          tieuDe="Không mở được máy chủ"
          than={thongDiepNguoiDoc(0, null)}
          viecTiepTheo="Kiểm tra máy chủ đang chạy chưa, rồi bấm thử lại."
          diaChi={BASE_URL}
          onThuLai={() => {}}
        />
        <CoLoi
          tieuDe="Máy chủ đang gặp sự cố"
          than={thongDiepNguoiDoc(500, { detail: "Internal Server Error" })}
          viecTiepTheo="Chờ một chút rồi bấm thử lại. Không cần chụp lại bill."
          onThuLai={() => {}}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

function XemKetQuaThanhToan() {
  const c = usePalette();
  const [nguoiDangChon, setNguoiDangChon] = useState<string | null>(
    DEMO_ENVELOPES[0]?.senderId ?? null,
  );
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
      <StatusBar style="dark" />
      <KetQuaThanhToan
        roster={DEMO_ROSTER}
        allocations={DEMO_ALLOCATIONS}
        obligations={DEMO_OBLIGATIONS}
        envelopes={DEMO_ENVELOPES}
        advancerId={DEMO_ADVANCER_ID}
        itemCount={DEMO_ITEM_COUNT}
        nguoiDangChon={nguoiDangChon}
        onChonNguoi={setNguoiDangChon}
        renderMaQr={(senderId) => {
          const envelope = DEMO_ENVELOPES.find((e) => e.senderId === senderId);
          if (envelope === undefined) return null;
          return envelope.obligations.map((debt) => (
            <MaVietQr
              key={debt.obligationId}
              payload={debt.vietqrPayload}
              expectedAmountVnd={debt.amountVnd}
              recipientName={
                DEMO_OBLIGATIONS.find((o) => o.id === debt.obligationId)?.recipient ??
                "người nhận"
              }
            />
          ));
        }}
        onShare={() => {}}
        onDone={() => {}}
        onBack={() => {}}
      />
    </SafeAreaView>
  );
}

/**
 * The app root: the opening screen, then the five-tab shell.
 *
 * The flow above is passed down rather than imported by the shell, so the
 * import graph stays one-directional (`App` → `navigation`, never back) and
 * this file remains the only place that knows both halves exist.
 */
/**
 * The bill-reading wait, held still so it can be seen.
 *
 * The real `ChupBill` with `busy` pinned on, not a drawing of it: same
 * component, same props the flow passes, same copy. On the live flow this state
 * lasts about as long as a model takes to read a photo, which is too short to
 * scan and too dependent on a camera to reach in a headless browser at all.
 *
 * `giaiDoan` comes from the query string so both halves are reachable, since
 * they say different things and only one of them can be on screen at a time.
 */
function XemDocBill() {
  const giaiDoan: GiaiDoanDocBill =
    manThamSo() === "doc-bill-chuan-bi" ? "chuan-bi-anh" : "dang-gui";
  // Hoisted out of the JSX below: a hook called in a prop position still runs
  // unconditionally, but it reads like a conditional one and lint treats it so.
  const cameraRef = useRef<CameraView | null>(null);
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: "#000" }}>
      <StatusBar style="light" />
      <ChupBill
        access={{
          state: "cho-phep",
          nextAction: "mo-camera",
          message: "Camera đã sẵn sàng.",
        }}
        cameraRef={cameraRef}
        busy
        giaiDoan={giaiDoan}
        error={null}
        onShutter={() => {}}
        onPickImage={() => {}}
        onRequestPermission={() => {}}
        onOpenSettings={() => {}}
        onCancel={() => {}}
      />
    </SafeAreaView>
  );
}

/* A destination that is not one. Invented digits, no bank behind them, and the
 * only place they are ever rendered is a scan target that writes nothing. */
// repo-guard: allow=long-number reason=synthetic-scan-fixture-account-number
const SO_TAI_KHOAN_DO = "1904567890123";

/**
 * The bank-destination screen at both of its steps, from a URL, web only.
 *
 * Same reason as `XemTrangThai` above, and the sharper version of it. This
 * screen is where somebody commits money to a destination that cannot be
 * verified by anybody, and it sits four fields and a press past a live server,
 * a 409, and eight presses of the flow. Without this it never gets scanned,
 * and the review step -- the half that actually guards the money -- never gets
 * scanned at all.
 *
 * `?man=tai-khoan-nhan` is the empty form, `?man=tai-khoan-nhan-duyet` is the
 * review step. Nothing here writes: `onLuu` and `onBack` are empty, and there
 * is no route from this page to anything that touches a server.
 */
function XemTaiKhoanNhan() {
  const c = usePalette();
  const duyet = manThamSo() === "tai-khoan-nhan-duyet";
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
      <StatusBar style="dark" />
      <TaiKhoanNhan
        nguoiNhan={{ id: "p1", name: "Hà" }}
        banDau={{
          dangDuyet: duyet,
          form: duyet
            ? {
                bin: "970436",
                soTaiKhoan: SO_TAI_KHOAN_DO,
                nhapLai: SO_TAI_KHOAN_DO,
                tenChuTaiKhoan: "NGUYEN THI HA",
              }
            : FORM_TRONG,
        }}
        onLuu={() => {}}
        onBack={() => {}}
      />
    </SafeAreaView>
  );
}

export default function App() {
  if (manDo()) return <XemKetQuaThanhToan />;
  if (manThamSo() === "trang-thai") return <XemTrangThai />;
  if (manThamSo()?.startsWith("doc-bill")) return <XemDocBill />;
  if (manThamSo()?.startsWith("tai-khoan-nhan")) return <XemTaiKhoanNhan />;
  return <AppRoot renderKhoanChi={(onExit) => <LuongKhoanChi onExit={onExit} />} />;
}
