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
import React, { useRef, useState } from "react";
import { Pressable, SafeAreaView, Text, View, useColorScheme } from "react-native";
import { AppRoot } from "./src/navigation/AppRoot";
import {
  attemptFor,
  confirmExpense,
  confirmReceipt,
  loadBoard,
  openBatch,
  proposeSplit,
  publishBatch,
  registerPeople,
  scanReceipt,
  type Attempt,
  type PendingProposal,
  BASE_URL,
  type PublishGates,
} from "./src/api";
import {
  HAS_CAMERA,
  nativeBackend,
  openAppSettings,
  readAccess,
  withBillPhoto,
} from "./src/camera";
import { itemsTotalVnd, readingFromWire, type BillReading } from "./src/receipt";
import { ChupBill } from "./src/screens/ChupBill";
import { KetQuaNhanDien } from "./src/screens/KetQuaNhanDien";
import { ChiaSe, type Envelope } from "./src/screens/ChiaSe";
import { DeXuat, type Proposal } from "./src/screens/DeXuat";
import { DotThu, type Obligation } from "./src/screens/DotThu";
import { Draft, NhapKhoanChi } from "./src/screens/NhapKhoanChi";
import { EMPTY_FORM, makeIdFactory, type DraftForm } from "./src/participants";
import { space, type, usePalette } from "./src/theme";

type Step = "chup-bill" | "ket-qua" | "nhap" | "de-xuat" | "dot-thu" | "chia-se";

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
 * paid or who is in, and this is a different write that must not replay the
 * answer to the previous one.
 */
function expenseIntent(d: Draft): string {
  const who = d.participants.map((person) => person.id).join(",");
  return `khoan-chi:${d.advancerId}:${d.totalVnd}:${d.occasion}:${who}`;
}

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
  // Spec section 8.3. Reported by the batch, never assumed by the screen.
  const [gates, setGates] = useState<PublishGates>({ payerAcknowledged: false });
  const [error, setError] = useState<string | null>(null);
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
  // Bumped on every accepted scan, and used as the result screen's `key`.
  // That screen keeps per-row drafts of half-typed numbers; without a new key
  // React reuses the mounted instance, and a rescan showed the previous bill's
  // rejected "12x" still sitting in row three of a completely different bill.
  const [scanSeq, setScanSeq] = useState(0);
  const access = readAccess(permission, HAS_CAMERA);

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
      const wire = await withBillPhoto(nativeBackend(cameraRef), source, (photo) =>
        scanReceipt(photo, SCAN_ACTOR_ID),
      );
      if (wire === null) return;
      setReading(readingFromWire(wire));
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
    } finally {
      setBusy(false);
    }
  }

  // The viewfinder is the one screen that owns the whole pane. Left on the
  // cream page ground, the shell painted a light strip under a black screen
  // and the server line sat in it, which read as the camera screen failing to
  // reach the bottom of the phone.
  const dark = step === "chup-bill";
  const tuVe = TOAN_MAN.includes(step);

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
            //
            // Who ate what does not travel yet. Per-item assignment is the
            // next screen in the mockup and it is not built, so the honest
            // handover is the total and nothing more.
            setForm((f) => ({ ...f, amount: String(itemsTotalVnd(reading)) }));
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
            setProposal(
              await proposeSplit(d, attemptFor(attempts.current, expenseIntent(d))),
            );
            setStep("de-xuat");
          })}
        />
      )}

      {step === "de-xuat" && proposal && (
        <DeXuat
          proposal={proposal}
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
            setEnvelopes(
              await publishBatch(
                batchId!,
                gates,
                proposal!.advancerId,
                attemptFor(attempts.current, `phat:${batchId}`),
                proposal!.participants,
              ),
            );
            setPublished(true);
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

      {step === "chia-se" && (
        <ChiaSe envelopes={envelopes} onDone={() => setStep("dot-thu")} />
      )}

      {error && (
        <View style={{ padding: space.md, backgroundColor: c.card, borderTopColor: c.warn, borderTopWidth: 2 }}>
          <Text style={{ ...type.label, color: c.warn }}>{error}</Text>
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
 * The app root: the opening screen, then the five-tab shell.
 *
 * The flow above is passed down rather than imported by the shell, so the
 * import graph stays one-directional (`App` → `navigation`, never back) and
 * this file remains the only place that knows both halves exist.
 */
export default function App() {
  return <AppRoot renderKhoanChi={(onExit) => <LuongKhoanChi onExit={onExit} />} />;
}
