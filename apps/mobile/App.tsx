/** Organiser flow: enter, review, collect, share.
 *
 * A plain state machine rather than a router. Spec section 14.3 says not to
 * build a Home screen or a tab shell before the actions are known, and this
 * flow is a line, not a graph. A router can arrive when there is a second
 * entry point to route to.
 */
import { StatusBar } from "expo-status-bar";
import React, { useState } from "react";
import { SafeAreaView, Text, View, useColorScheme } from "react-native";
import {
  openBatch,
  proposeSplit,
  publishBatch,
  OFFLINE,
  type PublishGates,
} from "./src/api";
import { ChiaSe, type Envelope } from "./src/screens/ChiaSe";
import { DeXuat, type Proposal } from "./src/screens/DeXuat";
import { DotThu, type Obligation } from "./src/screens/DotThu";
import { Draft, NhapKhoanChi } from "./src/screens/NhapKhoanChi";
import { EMPTY_FORM, type DraftForm } from "./src/participants";
import { TheDeXuat } from "./src/screens/TheDeXuat";
import { DEMO_THREADS } from "./src/fixtures/threads";
import { space, type, usePalette } from "./src/theme";

type Step = "nhap" | "the-de-xuat" | "de-xuat" | "dot-thu" | "chia-se";

export default function App() {
  const c = usePalette();
  const scheme = useColorScheme();
  const [step, setStep] = useState<Step>("nhap");
  const [draft, setDraft] = useState<Draft | null>(null);
  // Held here, not inside the screen. "Sửa lại" unmounts the screen, and a
  // form owned by the screen goes with it -- which erased everything a
  // person had typed the moment they tried to change one number.
  const [form, setForm] = useState<DraftForm>(EMPTY_FORM);
  // Which corpus case the proposal card is showing. Offline only: the
  // real thing arrives when money_skill runs against a live thread.
  const [threadIndex, setThreadIndex] = useState(0);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [envelopes, setEnvelopes] = useState<Envelope[]>([]);
  const [published, setPublished] = useState(false);
  // Spec section 8.3. Reported by the batch, never assumed by the screen.
  const [gates, setGates] = useState<PublishGates>({
    payerAcknowledged: false,
    recipientReady: false,
    recipientProblem: null,
  });
  const [error, setError] = useState<string | null>(null);

  async function guard(work: () => Promise<void>) {
    setError(null);
    try {
      await work();
    } catch (problem) {
      // Say what failed and what to do. "Something went wrong" is not an
      // error message, it is an apology.
      setError(
        problem instanceof Error && problem.message.includes("fetch")
          ? "Không nối được với máy chủ. Kiểm tra services/api có đang chạy không."
          : String(problem instanceof Error ? problem.message : problem)
      );
    }
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.ground }}>
      <StatusBar style={scheme === "dark" ? "light" : "dark"} />

      {step === "the-de-xuat" && (
        <TheDeXuat
          extraction={DEMO_THREADS[threadIndex].extraction}
          thread={DEMO_THREADS[threadIndex].messages}
          onAccept={() => {
            // Accepting a reading is not the same as splitting it. The next
            // step is the ordinary entry form, prefilled, so a person still
            // sees and confirms what goes into the ledger.
            setStep("nhap");
          }}
          onEdit={() => setStep("nhap")}
          onDismiss={() => {
            setThreadIndex((current) => (current + 1) % DEMO_THREADS.length);
          }}
        />
      )}

      {step === "nhap" && (
        <NhapKhoanChi
          form={form}
          onForm={setForm}
          onSeeProposal={OFFLINE ? () => setStep("the-de-xuat") : undefined}
          onNext={(d) => guard(async () => {
            setDraft(d);
            setProposal(await proposeSplit(d));
            setStep("de-xuat");
          })}
        />
      )}

      {step === "de-xuat" && proposal && (
        <DeXuat
          proposal={proposal}
          onBack={() => setStep("nhap")}
          onConfirm={() => guard(async () => {
            const batch = await openBatch(proposal);
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
            setEnvelopes(await publishBatch(obligations, gates));
            setPublished(true);
          })}
          onShare={() => setStep("chia-se")}
          // Offline, these stand in for actions the API will own: the advancer
          // acknowledging in their own session, and a recipient being set up
          // and confirmed. Local state is honest about being a stand-in --
          // what it must not do is let publish happen without them.
          onAcknowledge={() => setGates((g) => ({ ...g, payerAcknowledged: true }))}
          onSetRecipient={() =>
            setGates((g) => ({ ...g, recipientReady: true, recipientProblem: null }))
          }
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

      {OFFLINE && (
        <View style={{ paddingHorizontal: space.md, paddingBottom: space.sm }}>
          <Text style={{ ...type.label, color: c.inkSoft, textAlign: "center" }}>
            Dữ liệu giả. API chưa nối.
          </Text>
        </View>
      )}
    </SafeAreaView>
  );
}
