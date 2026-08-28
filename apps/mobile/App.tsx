/** Organiser flow: enter, review, collect, share.
 *
 * A plain state machine rather than a router. Spec section 14.3 says not to
 * build a Home screen or a tab shell before the actions are known, and this
 * flow is a line, not a graph. A router can arrive when there is a second
 * entry point to route to.
 */
import { StatusBar } from "expo-status-bar";
import React, { useRef, useState } from "react";
import { SafeAreaView, Text, View, useColorScheme } from "react-native";
import {
  attemptFor,
  confirmExpense,
  confirmReceipt,
  loadBoard,
  openBatch,
  proposeSplit,
  publishBatch,
  type Attempt,
  type PendingProposal,
  BASE_URL,
  type PublishGates,
} from "./src/api";
import { ChiaSe, type Envelope } from "./src/screens/ChiaSe";
import { DeXuat, type Proposal } from "./src/screens/DeXuat";
import { DotThu, type Obligation } from "./src/screens/DotThu";
import { Draft, NhapKhoanChi } from "./src/screens/NhapKhoanChi";
import { EMPTY_FORM, type DraftForm } from "./src/participants";
import { space, type, usePalette } from "./src/theme";

type Step = "nhap" | "de-xuat" | "dot-thu" | "chia-se";

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

export default function App() {
  const c = usePalette();
  const scheme = useColorScheme();
  const [step, setStep] = useState<Step>("nhap");
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

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
      <StatusBar style={scheme === "dark" ? "light" : "dark"} />


      {step === "nhap" && (
        <NhapKhoanChi
          form={form}
          onForm={setForm}
          onNext={(d) => guard(async () => {
            setDraft(d);
            // A new proposal makes any previously written version stale: it
            // belongs to the numbers on the last screen, not these.
            setWritten(null);
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
        <Text style={{ ...type.label, color: c.inkSoft, textAlign: "center" }}>
          Máy chủ: {BASE_URL}
        </Text>
      </View>
    </SafeAreaView>
  );
}
