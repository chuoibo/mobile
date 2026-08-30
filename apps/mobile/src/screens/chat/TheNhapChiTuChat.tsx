/** The purple draft card that grows under one chat bubble.
 *
 * Lead tone is `ai`: the machine produced this and a person can still change
 * it. Teal touches only the amount. The card never says an expense was
 * written -- `CAU_CHUA_GHI_KHOAN_CHI` sits inside the card, above the
 * buttons, because that sentence is the condition for acting, not a
 * footnote about the control.
 *
 * The confirm button is `primary` accent, not teal, and that follows
 * `DIRECTION_CONTRACT_BA_ROUTE` rather than the Kit default for money screens:
 * on this surface teal is spent on the amount and nothing else, and pressing
 * this button is a PERSON acting on a machine reading. A teal fill here would
 * flood a card whose whole subject is that the machine has not decided
 * anything yet.
 */
import React from "react";
import { Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { Button } from "../../ui/Kit";
import { dinhDangTienVnd } from "./ke-hoach";
import {
  CAU_CHUA_GHI_KHOAN_CHI,
  CAU_DA_GHI_KHOAN_CHI,
  type TrangGhiKhoanChi,
  type TrangNhapTuChat,
} from "./nhap-tu-chat";

export function TheNhapChiTuChat({
  trang,
  ghi,
  onGhi,
  onDong,
}: {
  trang: TrangNhapTuChat;
  ghi: TrangGhiKhoanChi;
  onGhi: () => void;
  onDong: () => void;
}) {
  const c = usePalette();

  if (trang.kind === "chua-goi") return null;

  const daGhi = ghi.kind === "da-ghi";
  const dangGhi = ghi.kind === "dang-ghi";

  return (
    // Two blocks, not one list. Every line in this card used to sit the same
    // `sm` distance from the next, so the title, the amount, the roster and
    // the sentence about the ledger all read as one undifferentiated column --
    // and adding the confirm button made that worse, which the detector caught
    // as `monotonous-spacing` (~16px, 86% of gaps). The reading and the
    // decision are different things and now sit `lg` apart, with the facts
    // pulled tight at `xs` so they cohere as one paragraph.
    <View
      style={{
        backgroundColor: c.aiSoft,
        borderColor: c.ai,
        borderWidth: 1,
        borderRadius: radius.base,
        padding: space.md,
        gap: space.lg,
      }}
    >
      {trang.kind === "dang-doc" ? (
        <Text style={{ ...type.body, color: c.inkSoft }}>Đang đọc tin nhắn…</Text>
      ) : null}

      {trang.kind === "hong" ? (
        <Text style={{ ...type.body, color: c.ink }}>{trang.loi}</Text>
      ) : null}

      {trang.kind === "khong-thay" ? (
        <Text style={{ ...type.body, color: c.ink }}>{trang.reason}</Text>
      ) : null}

      {trang.kind === "co-nhap" ? (
        <>
          {/* What the machine read. One tight group, because these four lines
              are a single fact about one message. */}
          <View style={{ gap: space.xs }}>
            <Text style={{ ...type.title, color: c.ink }}>{trang.title}</Text>
            <Text
              style={{
                ...type.amountSmall,
                color: c.split,
                fontVariant: ["tabular-nums"],
              }}
            >
              {dinhDangTienVnd(trang.amountVnd)}
            </Text>
            <Text style={{ ...type.body, color: c.ink }}>
              Người trả: {trang.tenNguoiTra}
            </Text>
            <Text style={{ ...type.body, color: c.ink }}>
              Người chia: {trang.tenNguoiChia.join(", ")}
            </Text>
            {trang.canXemLai && !daGhi ? (
              <Text style={{ ...type.label, fontWeight: "700", color: c.ai }}>
                Cần xem lại
              </Text>
            ) : null}
          </View>

          {/* The claim about the ledger, and what answers it. The sentence
              changes when the ledger does, and it stays above the buttons in
              both states: before the write it is the condition for pressing,
              after it is what the per-person rows are the answer to. */}
          <View style={{ gap: space.xs }}>
            <Text style={{ ...type.body, color: c.ink }}>
              {daGhi ? CAU_DA_GHI_KHOAN_CHI : CAU_CHUA_GHI_KHOAN_CHI}
            </Text>

            {ghi.kind === "da-ghi"
              ? ghi.dong.map((d, i) => (
                  <View
                    key={`${d.ten}-${i}`}
                    style={{
                      flexDirection: "row",
                      justifyContent: "space-between",
                      gap: space.sm,
                    }}
                  >
                    <Text style={{ ...type.body, color: c.ink, flexShrink: 1 }}>{d.ten}</Text>
                    <Text
                      style={{
                        ...type.body,
                        fontWeight: "600",
                        color: c.split,
                        fontVariant: ["tabular-nums"],
                      }}
                    >
                      {dinhDangTienVnd(d.soTien)}
                    </Text>
                  </View>
                ))
              : null}

            {/* A refusal from the write, kept beside the draft rather than
                replacing it: the numbers somebody was looking at when they
                pressed are what they need in order to decide about pressing
                again. */}
            {ghi.kind === "ghi-hong" ? (
              <Text style={{ ...type.body, color: c.ink }}>{ghi.loi}</Text>
            ) : null}
          </View>
        </>
      ) : null}

      {/* Đóng is never disabled, not even mid-write. No request here carries a
          timeout, so a hung write would otherwise leave a card nobody can
          dismiss. Dismissing is safe: the attempt key is derived from the
          proposal body, so reading the same message again and pressing again
          replays that write rather than making a second one. */}
      {trang.kind !== "dang-doc" ? (
        <View style={{ gap: space.sm }}>
          {trang.kind === "co-nhap" && !daGhi ? (
            <Button
              label={dangGhi ? "Đang ghi…" : ghi.kind === "ghi-hong" ? "Ghi lại" : "Ghi khoản chi"}
              tone="primary"
              disabled={dangGhi}
              onPress={onGhi}
            />
          ) : null}
          <Button label="Đóng" tone="quiet" onPress={onDong} />
        </View>
      ) : null}
    </View>
  );
}
