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
import { openBatch, proposeSplit, publishBatch, OFFLINE } from "./src/api";
import { ChiaSe, type Envelope } from "./src/screens/ChiaSe";
import { DeXuat, type Proposal } from "./src/screens/DeXuat";
import { DotThu, type Obligation } from "./src/screens/DotThu";
import { Draft, NhapKhoanChi } from "./src/screens/NhapKhoanChi";
import { space, type, usePalette } from "./src/theme";

type Step = "nhap" | "de-xuat" | "dot-thu" | "chia-se";

export default function App() {
  const c = usePalette();
  const scheme = useColorScheme();
  const [step, setStep] = useState<Step>("nhap");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [envelopes, setEnvelopes] = useState<Envelope[]>([]);
  const [published, setPublished] = useState(false);
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

      {step === "nhap" && (
        <NhapKhoanChi
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
            setObligations(await openBatch(proposal));
            setPublished(false);
            setStep("dot-thu");
          })}
        />
      )}

      {step === "dot-thu" && (
        <DotThu
          obligations={obligations}
          published={published}
          onPublish={() => guard(async () => {
            setEnvelopes(await publishBatch(obligations));
            setPublished(true);
          })}
          onShare={() => setStep("chia-se")}
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
