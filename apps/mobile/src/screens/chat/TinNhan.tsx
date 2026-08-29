/** Why the group-chat header is orange, not purple.
 *
 * The mockup paints this screen's header purple. That is the one deliberate
 * departure from the drawing, and it is written into
 * `DIRECTION_CONTRACT_NHOM_CHAT` rather than left in a commit message.
 * Purple (`ai`) has exactly one meaning in this palette: a machine made
 * this. Spending it on the header would say the whole conversation was
 * machine-written, which is the defect the direction contract exists to
 * prevent. The header is `accent` orange, like the tab shell. Purple is
 * spent on three things only: the AI avatar, the "Rủ Đi AI" label, and the
 * plan card.
 *
 * This file is the React that stands on the five logic modules. It does not
 * invent a member count, a plan, a total, or a day boundary. `khoiDongNhom`
 * is what makes the 403 go away; `napTinNhan` is what puts the oldest
 * message on top; `goiAiTurn` is what may come back as silence, and silence
 * is drawn as nothing. A canned itinerary in the Plan tab to fill a hole
 * would be indistinguishable from one the model wrote.
 *
 * The File chip is a shell. It says so, in the voice `ManVo` uses, because
 * an empty white pane is indistinguishable from a screen that failed to
 * load.
 */
import React, { useEffect, useRef, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { DEMO_PEOPLE, type DemoPerson } from "../../navigation/nhom-demo";
import { radius, space, type, usePalette } from "../../theme";
import { Card } from "../../ui/Kit";
import { goiAiTurn, type AiTurnState } from "./ai";
import { BongBong, type NguoiHienThi } from "./BongBong";
import { ChiTietKeHoach } from "./ChiTietKeHoach";
import { keHoachTuCard, type KeHoach } from "./ke-hoach";
import { khoiDongNhom, type NhomState, type ThanhVien } from "./nhom";
import { ONhap } from "./ONhap";
import {
  guiTinNhan,
  khuTrungTheoId,
  napTinCuHon,
  napTinNhan,
  type MessageWire,
  type TinNhanState,
} from "./tin-nhan";

type ChipId = "chat" | "plan" | "thanh-vien" | "file";

type NhomMan = { kind: "dang-tai" } | { kind: "chua-chon" } | NhomState;
type TinMan = { kind: "dang-tai" } | TinNhanState;

const CHIPS: { id: ChipId; label: string }[] = [
  { id: "chat", label: "Chat" },
  { id: "plan", label: "Plan" },
  { id: "thanh-vien", label: "Thành viên" },
  { id: "file", label: "File" },
];

export function TinNhan({ nguoi }: { nguoi: DemoPerson | null }) {
  const c = usePalette();
  const [nhom, setNhom] = useState<NhomMan>(nguoi ? { kind: "dang-tai" } : { kind: "chua-chon" });
  const [tin, setTin] = useState<TinMan>({ kind: "dang-tai" });
  const [chip, setChip] = useState<ChipId>("chat");
  const [nhap, setNhap] = useState("");
  const [dangGui, setDangGui] = useState(false);
  const [dangNapCu, setDangNapCu] = useState(false);
  const [thongBao, setThongBao] = useState<string | null>(null);
  const [aiYen, setAiYen] = useState<AiYen | null>(null);
  const [keHoachDangXem, setKeHoachDangXem] = useState<KeHoach | null>(null);

  const cuonRef = useRef<ScrollView>(null);
  const dangGoiAi = useRef(false);
  const messages = tin.kind === "co-tin" ? tin.messages : [];
  const cuoiTin = messages[messages.length - 1]?.id;
  const keHoachMoi = keHoachGanNhat(messages);

  useEffect(() => {
    if (!nguoi) {
      setNhom({ kind: "chua-chon" });
      return;
    }
    let huy = false;
    setNhom({ kind: "dang-tai" });
    khoiDongNhom(nguoi.id).then((s) => {
      if (!huy) setNhom(s);
    });
    return () => {
      huy = true;
    };
  }, [nguoi]);

  useEffect(() => {
    if (!nguoi || nhom.kind !== "xong") return;
    let huy = false;
    setTin({ kind: "dang-tai" });
    napTinNhan({ contextId: nhom.contextId, actorId: nguoi.personId, limit: 50 }).then((s) => {
      if (!huy) setTin(s);
    });
    return () => {
      huy = true;
    };
  }, [nguoi, nhom]);

  useEffect(() => {
    if (!cuoiTin) return;
    cuonRef.current?.scrollToEnd({ animated: true });
  }, [cuoiTin]);

  if (keHoachDangXem) {
    return <ChiTietKeHoach keHoach={keHoachDangXem} onBack={() => setKeHoachDangXem(null)} />;
  }

  if (chip === "plan" && keHoachMoi) {
    return <ChiTietKeHoach keHoach={keHoachMoi} onBack={() => setChip("chat")} />;
  }

  async function gui() {
    if (!nguoi || nhom.kind !== "xong") return;
    const body = nhap.trim();
    if (!body || dangGui) return;
    setDangGui(true);
    const sent = await guiTinNhan({
      contextId: nhom.contextId,
      actorId: nguoi.personId,
      body,
      idempotencyKey: taoKhoa(),
    });
    setDangGui(false);
    if (sent.kind !== "xong") {
      setThongBao(cauGuiHong(sent));
      return;
    }
    setNhap("");
    setTin((truoc) => noiTinMoi(truoc, sent.message, nhom.contextId));
    void goiAiSauKhiGui(nhom.contextId, nguoi.personId);
  }

  async function goiAiSauKhiGui(contextId: string, actorId: string) {
    if (dangGoiAi.current) return;
    dangGoiAi.current = true;
    try {
      const s = await goiAiTurn({ contextId, actorId, idempotencyKey: taoKhoa() });
      xuLyAi(s);
    } finally {
      dangGoiAi.current = false;
    }
  }

  function xuLyAi(s: AiTurnState) {
    if (s.kind === "im-lang") {
      setAiYen(null);
      return;
    }
    if (s.kind === "da-noi") {
      setAiYen(null);
      setTin((truoc) => noiTinMoi(truoc, s.message, s.message.context_id));
      return;
    }
    if (s.kind === "chua-noi-duoc" || s.kind === "khong-tra-loi-duoc") {
      setAiYen({ giong: "binh-tinh", cau: s.cau });
      return;
    }
    setAiYen({ giong: "loi", cau: `Máy chủ trả lỗi ${s.status}. ${s.detail}` });
  }

  async function xemTinCuHon() {
    if (!nguoi || nhom.kind !== "xong" || tin.kind !== "co-tin" || dangNapCu) return;
    setDangNapCu(true);
    const s = await napTinCuHon({
      contextId: nhom.contextId,
      actorId: nguoi.personId,
      dangGiu: tin.messages,
      hasMore: tin.hasMore,
    });
    setDangNapCu(false);
    if (s.kind === "co-tin" || s.kind === "rong") {
      setTin(s);
      return;
    }
    setThongBao(cauTinHong(s));
  }

  return (
    <View style={{ flex: 1, backgroundColor: c.ground }}>
      <DauMan nhom={nhom} />
      <HangChip chip={chip} onDoi={setChip} />

      <View style={{ flex: 1 }}>
        {chip === "chat" ? (
          <DongTin
            nhom={nhom}
            tin={tin}
            nguoi={nguoi}
            cuonRef={cuonRef}
            dangNapCu={dangNapCu}
            onXemCuHon={xemTinCuHon}
            onXemKeHoach={setKeHoachDangXem}
            aiYen={aiYen}
          />
        ) : null}
        {chip === "plan" ? <TabPlan dangTai={tin.kind === "dang-tai"} /> : null}
        {chip === "thanh-vien" ? <TabThanhVien nhom={nhom} /> : null}
        {chip === "file" ? <TabFile /> : null}
      </View>

      {thongBao ? <BangThongBao text={thongBao} onClose={() => setThongBao(null)} /> : null}

      {chip === "chat" ? (
        <ONhap
          value={nhap}
          onChangeText={setNhap}
          onGui={() => {
            void gui();
          }}
          dangGui={dangGui}
          onChuaDung={setThongBao}
        />
      ) : null}
    </View>
  );
}

type AiYen = { giong: "binh-tinh" | "loi"; cau: string };

function DauMan({ nhom }: { nhom: NhomMan }) {
  const c = usePalette();
  const ten = nhom.kind === "xong" ? nhom.tenNhom : "Nhóm chat";
  const chu = ten.trim().charAt(0) || "?";
  const phu =
    nhom.kind === "xong"
      ? `${nhom.members.length} thành viên`
      : nhom.kind === "dang-tai"
        ? "Đang mở nhóm…"
        : nhom.kind === "chua-chon"
          ? "Chưa chọn người"
          : "Chưa vào được nhóm";
  return (
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        gap: space.sm,
        paddingHorizontal: space.md,
        paddingTop: space.md,
        paddingBottom: space.sm,
      }}
    >
      <View
        style={{
          width: 44,
          height: 44,
          borderRadius: radius.pill,
          backgroundColor: c.accentSoft,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Text style={{ ...type.title, color: c.accent }}>{chu}</Text>
      </View>
      <View style={{ flex: 1, gap: 2 }}>
        <Text numberOfLines={1} style={{ ...type.h1, color: c.ink }}>
          {ten}
        </Text>
        <Text numberOfLines={1} style={{ ...type.label, color: c.inkSoft }}>
          {phu}
        </Text>
      </View>
    </View>
  );
}

function HangChip({ chip, onDoi }: { chip: ChipId; onDoi: (id: ChipId) => void }) {
  const c = usePalette();
  return (
    <View
      accessibilityRole="tablist"
      style={{
        flexDirection: "row",
        gap: space.xs,
        paddingHorizontal: space.md,
        paddingBottom: space.sm,
      }}
    >
      {CHIPS.map((m) => {
        const chon = m.id === chip;
        return (
          <Pressable
            key={m.id}
            onPress={() => onDoi(m.id)}
            accessibilityRole="tab"
            accessibilityLabel={m.label}
            aria-selected={chon}
            style={({ pressed }) => ({
              flex: 1,
              minHeight: 44,
              borderRadius: radius.pill,
              borderWidth: 1,
              borderColor: chon ? c.accent : c.lineStrong,
              backgroundColor: chon ? c.accentSoft : "transparent",
              alignItems: "center",
              justifyContent: "center",
              paddingHorizontal: space.xs,
              opacity: pressed ? 0.85 : 1,
            })}
          >
            <Text style={{ ...type.label, fontWeight: chon ? "700" : "400", color: chon ? c.accent : c.ink }}>
              {m.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function DongTin({
  nhom,
  tin,
  nguoi,
  cuonRef,
  dangNapCu,
  onXemCuHon,
  onXemKeHoach,
  aiYen,
}: {
  nhom: NhomMan;
  tin: TinMan;
  nguoi: DemoPerson | null;
  cuonRef: React.RefObject<ScrollView | null>;
  dangNapCu: boolean;
  onXemCuHon: () => void;
  onXemKeHoach: (k: KeHoach) => void;
  aiYen: AiYen | null;
}) {
  const c = usePalette();

  if (nhom.kind === "chua-chon") {
    return (
      <View style={{ padding: space.md }}>
        <Card>
          <Text style={{ ...type.body, color: c.ink }}>Chưa chọn người, nên không mở được nhóm chat.</Text>
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Quay lại màn mở đầu và chọn một người trong nhóm. Không có người thì không có
            thành viên để hỏi máy chủ.
          </Text>
        </Card>
      </View>
    );
  }

  if (nhom.kind === "dang-tai") {
    return (
      <View style={{ padding: space.md }}>
        <Card>
          <Text style={{ ...type.body, color: c.inkSoft }}>Đang mở nhóm…</Text>
        </Card>
      </View>
    );
  }

  if (nhom.kind === "hong") {
    return (
      <View style={{ padding: space.md }}>
        <TheHong
          tieuDe={cauBuocNhom(nhom.buoc)}
          than="Không phải mạng lúc nào cũng là nguyên nhân. Bước đứng và địa chỉ đã thử nằm dưới."
          url={nhom.url}
          status={nhom.status}
          detail={nhom.detail}
        />
      </View>
    );
  }

  if (tin.kind === "dang-tai") {
    return (
      <View style={{ padding: space.md }}>
        <Card>
          <Text style={{ ...type.body, color: c.inkSoft }}>Đang tải tin nhắn của nhóm…</Text>
        </Card>
      </View>
    );
  }

  if (tin.kind !== "co-tin" && tin.kind !== "rong") {
    return (
      <View style={{ padding: space.md }}>
        <TheHongTin state={tin} />
      </View>
    );
  }

  const messages = tin.kind === "co-tin" ? tin.messages : [];
  const hasMore = tin.kind === "co-tin" ? tin.hasMore : false;

  return (
    <ScrollView
      ref={cuonRef}
      style={{ flex: 1 }}
      contentContainerStyle={{
        paddingHorizontal: space.md,
        paddingBottom: space.md,
        gap: space.sm,
      }}
    >
      {hasMore ? (
        <Pressable
          onPress={onXemCuHon}
          disabled={dangNapCu}
          accessibilityRole="button"
          accessibilityLabel="Xem tin cũ hơn"
          aria-disabled={dangNapCu}
          style={({ pressed }) => ({
            minHeight: 44,
            borderRadius: radius.control,
            borderWidth: 1,
            borderColor: dangNapCu ? c.line : c.lineStrong,
            backgroundColor: dangNapCu ? c.line : "transparent",
            alignItems: "center",
            justifyContent: "center",
            opacity: pressed && !dangNapCu ? 0.85 : 1,
          })}
        >
          <Text style={{ ...type.body, fontWeight: "600", color: dangNapCu ? c.inkSoft : c.accent }}>
            {dangNapCu ? "Đang tải tin cũ hơn…" : "Xem tin cũ hơn"}
          </Text>
        </Pressable>
      ) : null}

      {tin.kind === "rong" ? (
        <Card>
          <Text style={{ ...type.body, color: c.ink }}>Chưa có tin nào trong nhóm này.</Text>
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Gửi một câu ở ô dưới. AI sẽ tự lên tiếng khi nhóm bàn đủ rõ, không cần gọi tên nó.
          </Text>
        </Card>
      ) : null}

      <View
        accessibilityLiveRegion="polite"
        aria-live="polite"
        style={{ gap: space.sm }}
      >
        {messages.map((m, i) => (
          <BongBong
            key={m.id}
            message={m}
            nguoiGui={nguoiTheoAuthor(m.author_id)}
            cuaMinh={Boolean(nguoi && m.author_id === nguoi.personId)}
            dauChuoi={i === 0 || messages[i - 1]!.author_id !== m.author_id}
            onXemKeHoach={onXemKeHoach}
          />
        ))}
      </View>

      {aiYen ? <BangAiYen yen={aiYen} /> : null}
    </ScrollView>
  );
}

function TabPlan({ dangTai }: { dangTai: boolean }) {
  const c = usePalette();
  if (dangTai) {
    return (
      <View style={{ padding: space.md }}>
        <Card>
          <Text style={{ ...type.body, color: c.inkSoft }}>Đang tải tin nhắn của nhóm…</Text>
        </Card>
      </View>
    );
  }
  return (
    <View style={{ padding: space.md }}>
      <Card>
        <Text style={{ ...type.body, color: c.ink }}>Chưa có kế hoạch nào trong nhóm này.</Text>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          AI sẽ tự lên tiếng khi nhóm bàn đủ rõ chỗ đi và thời gian. Không có kế hoạch nào
          được bịa sẵn.
        </Text>
      </Card>
    </View>
  );
}

function TabThanhVien({ nhom }: { nhom: NhomMan }) {
  const c = usePalette();
  if (nhom.kind !== "xong") {
    return (
      <View style={{ padding: space.md }}>
        <Card>
          <Text style={{ ...type.body, color: c.inkSoft }}>
            {nhom.kind === "dang-tai"
              ? "Đang đọc danh sách thành viên…"
              : nhom.kind === "chua-chon"
                ? "Chưa chọn người, nên chưa có thành viên để hiện."
                : "Chưa đọc được danh sách thành viên."}
          </Text>
        </Card>
      </View>
    );
  }
  return (
    <ScrollView contentContainerStyle={{ padding: space.md, gap: space.sm }}>
      {nhom.members.map((m) => (
        <DongThanhVien key={m.id} tv={m} />
      ))}
    </ScrollView>
  );
}

function DongThanhVien({ tv }: { tv: ThanhVien }) {
  const c = usePalette();
  const nguoi = DEMO_PEOPLE.find((p) => p.personId === tv.personId) ?? null;
  const ten = nguoi?.name ?? tv.personId.slice(0, 8);
  const initials = nguoi?.initials ?? "?";
  return (
    <Card>
      <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
        <View
          style={{
            width: 44,
            height: 44,
            borderRadius: radius.pill,
            backgroundColor: c.accentSoft,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Text style={{ ...type.label, fontWeight: "700", color: c.accent }}>{initials}</Text>
        </View>
        <View style={{ flex: 1, gap: 2 }}>
          <Text style={{ ...type.body, fontWeight: "700", color: c.ink }}>{ten}</Text>
          <Text style={{ ...type.label, color: c.inkSoft }}>
            {nhanVaiTro(tv.role)} · {nhanTrangThai(tv.state)}
          </Text>
        </View>
      </View>
    </Card>
  );
}

function TabFile() {
  const c = usePalette();
  return (
    <View style={{ padding: space.md }}>
      <Card>
        <View style={{ flexDirection: "row", alignItems: "center", gap: space.xs }}>
          <View
            style={{
              paddingHorizontal: space.xs,
              paddingVertical: 2,
              borderRadius: radius.small,
              backgroundColor: c.ground,
              borderColor: c.line,
              borderWidth: 1,
            }}
          >
            <Text style={{ ...type.micro, color: c.inkSoft }}>vỏ</Text>
          </View>
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Mục này chưa dựng, mới có chỗ đứng trong hàng chip.
          </Text>
        </View>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Chưa có route nào cho tệp của nhóm. Việc còn nợ nằm ở lane frontend, chưa xếp.
        </Text>
      </Card>
    </View>
  );
}

function TheHongTin({
  state,
}: {
  state: Exclude<TinNhanState, { kind: "co-tin" } | { kind: "rong" }>;
}) {
  if (state.kind === "khong-noi-duoc") {
    return (
      <TheHong
        tieuDe="Không nối được máy chủ"
        than="Không kết nối được tới API. Đây là mạng hoặc máy chủ chưa mở, không phải quyền."
        url={state.url}
        detail={state.detail}
      />
    );
  }
  if (state.kind === "bi-cam") {
    return (
      <TheHong
        tieuDe="Chưa phải thành viên nhóm"
        than="Máy chủ từ chối vì người đang chọn chưa ở trong nhóm. Đây là quyền, không phải mạng."
        url={state.url}
        status={state.status}
        detail={state.detail}
      />
    );
  }
  if (state.kind === "may-chu-loi") {
    return (
      <TheHong
        tieuDe={`Máy chủ trả lỗi ${state.status}`}
        than="Máy chủ nhận yêu cầu nhưng không trả tin được."
        url={state.url}
        status={state.status}
        detail={state.detail}
      />
    );
  }
  return (
    <TheHong
      tieuDe="Dữ liệu tin nhắn không đúng dạng"
      than="App từ chối hiển thị thay vì vẽ ra một đoạn chat sai."
      url={state.url}
      detail={state.detail}
    />
  );
}

function TheHong({
  tieuDe,
  than,
  url,
  status,
  detail,
}: {
  tieuDe: string;
  than: string;
  url: string;
  status?: number;
  detail?: string;
}) {
  const c = usePalette();
  return (
    <Card>
      <Text style={{ ...type.title, color: c.ink }}>{tieuDe}</Text>
      <Text style={{ ...type.body, color: c.inkSoft }}>{than}</Text>
      <Text style={{ ...type.micro, color: c.inkFaint }}>Đã thử: {url}</Text>
      {status !== undefined ? (
        <Text style={{ ...type.micro, color: c.inkFaint }}>Mã: {status}</Text>
      ) : null}
      {detail ? <Text style={{ ...type.micro, color: c.inkFaint }}>Chi tiết: {detail}</Text> : null}
    </Card>
  );
}

function BangAiYen({ yen }: { yen: AiYen }) {
  const c = usePalette();
  const loi = yen.giong === "loi";
  return (
    <View
      style={{
        // Same ground either way. Only the edge changes: a missing route is
        // not a fault to paint red, it is work that has not landed.
        backgroundColor: c.card,
        borderColor: loi ? c.warn : c.line,
        borderWidth: 1,
        borderRadius: radius.base,
        padding: space.sm,
        gap: space.xs,
      }}
    >
      {loi ? null : (
        <View
          style={{
            alignSelf: "flex-start",
            paddingHorizontal: space.xs,
            paddingVertical: 2,
            borderRadius: radius.small,
            backgroundColor: c.ground,
            borderColor: c.line,
            borderWidth: 1,
          }}
        >
          <Text style={{ ...type.micro, color: c.inkSoft }}>còn nợ</Text>
        </View>
      )}
      <Text style={{ ...type.body, color: loi ? c.warn : c.inkSoft }}>{yen.cau}</Text>
    </View>
  );
}

function BangThongBao({ text, onClose }: { text: string; onClose: () => void }) {
  const c = usePalette();
  return (
    <View
      accessibilityRole="alert"
      style={{
        marginHorizontal: space.md,
        marginBottom: space.sm,
        padding: space.sm,
        borderRadius: radius.control,
        backgroundColor: c.card,
        borderColor: c.line,
        borderWidth: 1,
        flexDirection: "row",
        alignItems: "center",
        gap: space.sm,
      }}
    >
      <Text style={{ ...type.label, color: c.inkSoft, flex: 1 }}>{text}</Text>
      <Text
        accessibilityRole="button"
        onPress={onClose}
        style={{
          ...type.label,
          fontWeight: "700",
          color: c.accent,
          paddingHorizontal: space.xs,
          minHeight: 44,
          textAlignVertical: "center",
        }}
      >
        Ẩn
      </Text>
    </View>
  );
}

function keHoachGanNhat(messages: MessageWire[]): KeHoach | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    const k = keHoachTuCard(messages[i]!.card);
    if (k) return k;
  }
  return null;
}

function nguoiTheoAuthor(authorId: string | null): NguoiHienThi | null {
  if (!authorId) return null;
  const p = DEMO_PEOPLE.find((x) => x.personId === authorId);
  return p ? { name: p.name, initials: p.initials } : null;
}

function nhanVaiTro(role: ThanhVien["role"]): string {
  return role === "admin" ? "Quản trị" : "Thành viên";
}

function nhanTrangThai(state: ThanhVien["state"]): string {
  if (state === "invited") return "Đã mời";
  if (state === "left") return "Đã rời";
  return "Đang trong nhóm";
}

function cauBuocNhom(buoc: string): string {
  if (buoc === "dat-ten") return "Không ghi được tên người";
  if (buoc === "tao-nhom") return "Không tạo được nhóm";
  if (buoc === "moi") return "Không mời được vào nhóm";
  if (buoc === "chap-nhan") return "Không nhận lời mời được";
  if (buoc === "doc-thanh-vien") return "Không đọc được danh sách thành viên";
  return "Không vào được nhóm";
}

function cauTinHong(s: Exclude<TinNhanState, { kind: "co-tin" } | { kind: "rong" }>): string {
  if (s.kind === "khong-noi-duoc") return `Không nối được máy chủ. Đã thử: ${s.url}`;
  if (s.kind === "bi-cam") return `Chưa phải thành viên nhóm. Đã thử: ${s.url}`;
  if (s.kind === "may-chu-loi") return `Máy chủ trả lỗi ${s.status}. Đã thử: ${s.url}`;
  return `Dữ liệu tin nhắn không đúng dạng. Đã thử: ${s.url}`;
}

function cauGuiHong(
  s: Exclude<import("./tin-nhan").GuiTinState, { kind: "xong" }>,
): string {
  if (s.kind === "khong-noi-duoc") return `Không gửi được, không nối được máy chủ. Đã thử: ${s.url}`;
  if (s.kind === "may-chu-loi") return `Không gửi được, máy chủ trả lỗi ${s.status}. Đã thử: ${s.url}`;
  return `Không gửi được, dữ liệu trả về không đúng dạng. Đã thử: ${s.url}`;
}

function noiTinMoi(truoc: TinMan, message: MessageWire, contextId: string): TinMan {
  if (truoc.kind === "co-tin") {
    return { ...truoc, messages: khuTrungTheoId([...truoc.messages, message]) };
  }
  if (truoc.kind === "rong") {
    return { kind: "co-tin", messages: [message], hasMore: false, contextId };
  }
  return { kind: "co-tin", messages: [message], hasMore: false, contextId };
}

/** Minted on the press, not inside a retry. A new key on the same bytes is
 *  a second write. Prefer the platform UUID; fall back to a v4 assembled
 *  here so this file does not grow an npm dependency. */
function taoKhoa(): string {
  const web = globalThis.crypto;
  if (web && typeof web.randomUUID === "function") return web.randomUUID();
  const bytes = new Uint8Array(16);
  if (web && typeof web.getRandomValues === "function") {
    web.getRandomValues(bytes);
  } else {
    for (let i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256);
  }
  bytes[6] = (bytes[6]! & 0x0f) | 0x40;
  bytes[8] = (bytes[8]! & 0x3f) | 0x80;
  const h = [...bytes].map((n) => n.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20, 32)}`;
}
