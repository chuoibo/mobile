import React from "react";
import { ScrollView, Text, View } from "react-native";
import { radius, space, type, usePalette } from "../../theme";
import { Button, Card, Row, Screen } from "../../ui/Kit";
import { themChiTiet } from "../../ui/loi-may-chu";
import { tienVnd } from "../len-plan/ngan-sach";
import {
  khoangGia,
  laNhanAi,
  nhanLyDo,
  nhanTietMuc,
  nhanVerdictNganSach,
  type AiHieuNhomState,
  type ContextualSuggestionResponse,
  type GroupBudgetResponse,
  type GroupSuggestionResponse,
  type PreferenceProfileResponse,
  type SuggestionStop,
} from "./ai-hieu-nhom";

export function AiHieuNhom({
  state,
  onDong,
}: {
  state: AiHieuNhomState;
  onDong: () => void;
}) {
  if (state.kind !== "xong") {
    return <TrangThaiAiHieuNhom state={state} onDong={onDong} />;
  }

  return (
    <Screen
      title="AI hiểu nhóm"
      hint="Bốn góc nhìn được đọc trực tiếp từ dữ liệu của nhóm."
      footer={<Button label="Đóng" onPress={onDong} tone="quiet" />}
    >
      <ScrollView contentContainerStyle={{ gap: space.md, paddingBottom: space.sm }}>
        <KhoiHoSo hoSo={state.hoSo} />
        <KhoiGoiY goiY={state.goiY} />
        <KhoiTheoChat theoChat={state.theoChat} />
        <KhoiNganSach nganSach={state.nganSach} />
      </ScrollView>
    </Screen>
  );
}

function TrangThaiAiHieuNhom({
  state,
  onDong,
}: {
  state: Exclude<AiHieuNhomState, { kind: "xong" }>;
  onDong: () => void;
}) {
  let tieuDe = "Đang đọc dữ liệu nhóm…";
  let than = "App đang hỏi bốn địa chỉ của nhóm cùng lúc.";
  let url: string | null = null;

  if (state.kind === "chua-biet-la-ai") {
    tieuDe = "Chưa biết bạn là ai";
    than = "Chọn lại người đang dùng app trước khi đọc dữ liệu riêng của nhóm.";
  } else if (state.kind === "bi-tu-choi") {
    tieuDe = "Máy chủ chưa cho đọc";
    than = "App có gửi danh tính nhưng máy chủ từ chối yêu cầu này.";
    url = state.url;
  } else if (state.kind === "khong-noi-duoc") {
    tieuDe = "Không nối được máy chủ";
    than = themChiTiet("Không kết nối được tới API.", state.detail);
    url = state.url;
  } else if (state.kind === "may-chu-loi") {
    tieuDe = "Máy chủ không trả dữ liệu";
    than = themChiTiet("Máy chủ nhận yêu cầu nhưng không trả được màn này.", state.detail);
    url = state.url;
  }

  return (
    <Screen
      title="AI hiểu nhóm"
      footer={<Button label="Đóng" onPress={onDong} tone="quiet" />}
    >
      <Card>
        <TieuDeKhoi>{tieuDe}</TieuDeKhoi>
        <ChuThan>{than}</ChuThan>
        {url ? <ChuDiaChi url={url} /> : null}
      </Card>
    </Screen>
  );
}

function KhoiHoSo({ hoSo }: { hoSo: PreferenceProfileResponse }) {
  const c = usePalette();
  return (
    <Card>
      <TieuDeKhoi>Hồ sơ sở thích</TieuDeKhoi>
      {!hoSo.has_profile ? (
        <ChuThan>{nhanLyDo(hoSo.reason)}</ChuThan>
      ) : (
        <>
          {hoSo.sections.map((section) => (
            <View key={section.section} style={{ gap: space.xs }}>
              <Text style={{ ...type.body, fontWeight: "700", color: c.ink }}>
                {nhanTietMuc(section.section)} · {section.taste_count} sở thích
              </Text>
              {section.tastes.map((taste) => (
                <Row
                  key={taste.label}
                  left={taste.label}
                  right={`${taste.checkin_count} check-in`}
                  muted
                />
              ))}
            </View>
          ))}
          <View style={{ gap: space.xs }}>
            <Text style={{ ...type.label, fontWeight: "700", color: c.inkSoft }}>
              Dữ liệu đứng sau hồ sơ
            </Text>
            <Row left="Lượt check-in" right={String(hoSo.checkin_count)} muted />
            <Row left="Buổi đi đã ghi nhận" right={String(hoSo.outing_count)} muted />
            <Row left="Tổng đã chia" right={tienVnd(hoSo.split_total_vnd)} />
            <Row
              left="Trung bình mỗi người"
              right={
                hoSo.avg_per_person_vnd === null
                  ? "Chưa có"
                  : tienVnd(hoSo.avg_per_person_vnd)
              }
            />
          </View>
        </>
      )}
    </Card>
  );
}

function KhoiGoiY({ goiY }: { goiY: GroupSuggestionResponse }) {
  const c = usePalette();
  return (
    <Card>
      <TieuDeKhoi>Gợi ý cho nhóm</TieuDeKhoi>
      <NoiDungGoiY goiY={goiY} />
      {goiY.suggested && laNhanAi(goiY.source) ? (
        <View style={{ gap: space.xs }}>
          <Text style={{ ...type.label, fontWeight: "700", color: c.inkSoft }}>
            Căn cứ từ lịch sử
          </Text>
          <Row left="Buổi đi" right={String(goiY.basis.outing_count)} muted />
          <Row left="Tổng đã chia" right={tienVnd(goiY.basis.split_total_vnd)} muted />
          <Row
            left="Trung bình mỗi người"
            right={
              goiY.basis.avg_per_person_vnd === null
                ? "Chưa có"
                : tienVnd(goiY.basis.avg_per_person_vnd)
            }
            muted
          />
        </View>
      ) : null}
    </Card>
  );
}

function KhoiTheoChat({ theoChat }: { theoChat: ContextualSuggestionResponse }) {
  const c = usePalette();
  return (
    <Card>
      <TieuDeKhoi>Gợi ý theo đoạn chat</TieuDeKhoi>
      <NoiDungGoiY goiY={theoChat} />
      {theoChat.suggested && laNhanAi(theoChat.source) ? (
        <View style={{ gap: space.xs }}>
          <Text style={{ ...type.label, fontWeight: "700", color: c.inkSoft }}>
            Căn cứ từ cuộc trò chuyện
          </Text>
          <Row left="Tin nhắn đã đọc" right={String(theoChat.basis.message_count)} muted />
          <Row left="Người đã nói" right={String(theoChat.basis.speaker_count)} muted />
          <Row
            left="Thành viên đang hoạt động"
            right={String(theoChat.basis.member_count)}
            muted
          />
        </View>
      ) : null}
    </Card>
  );
}

function NoiDungGoiY({
  goiY,
}: {
  goiY: GroupSuggestionResponse | ContextualSuggestionResponse;
}) {
  const c = usePalette();
  if (!goiY.suggested || !laNhanAi(goiY.source)) {
    return <ChuThan>{nhanLyDo(goiY.reason)}</ChuThan>;
  }

  return (
    <View style={{ gap: space.sm }}>
      <NhanAi />
      {goiY.title ? (
        <Text style={{ ...type.title, color: c.ai }}>{goiY.title}</Text>
      ) : null}
      {goiY.when_text ? <ChuThan>{goiY.when_text}</ChuThan> : null}
      {goiY.stops.map((stop, index) => (
        <ChangGoiY key={`${stop.place.id}-${index}`} stop={stop} />
      ))}
    </View>
  );
}

function ChangGoiY({ stop }: { stop: SuggestionStop }) {
  const c = usePalette();
  return (
    <View
      style={{
        gap: space.xs,
        paddingTop: space.sm,
        borderTopColor: c.line,
        borderTopWidth: 1,
      }}
    >
      <Text style={{ ...type.label, fontWeight: "700", color: c.inkSoft }}>
        {stop.time_text}
      </Text>
      <Text style={{ ...type.body, fontWeight: "700", color: c.ink }}>
        {stop.place.name}
      </Text>
      <Text style={{ ...type.label, color: c.inkSoft }}>{stop.place.address}</Text>
      <Row left="Khoảng giá" right={khoangGia(stop.place)} />
      <Row left="Đánh giá" right={String(stop.place.rating)} muted />
      <Row left="Khoảng cách" right={`${stop.place.distance_km} km`} muted />
      <Row left="Mở cửa" right={stop.place.open_hours} muted />
      <Text style={{ ...type.body, color: c.ai }}>{stop.note}</Text>
      {stop.reason ? <Text style={{ ...type.label, color: c.ai }}>{stop.reason}</Text> : null}
      {stop.verdict ? (
        <Text style={{ ...type.micro, color: c.ai }}>{nhanVerdictGoiY(stop.verdict)}</Text>
      ) : null}
    </View>
  );
}

function KhoiNganSach({ nganSach }: { nganSach: GroupBudgetResponse }) {
  const c = usePalette();
  return (
    <Card>
      <TieuDeKhoi>Ngân sách nhóm</TieuDeKhoi>
      <Row left="Buổi đi đã ghi nhận" right={String(nganSach.outing_count)} muted />
      <Row left="Thành viên đang hoạt động" right={String(nganSach.active_member_count)} muted />
      <Row
        left="Trung bình mỗi người"
        right={
          nganSach.avg_per_person_vnd === null
            ? "Chưa có"
            : tienVnd(nganSach.avg_per_person_vnd)
        }
      />
      {nganSach.in_progress.length === 0 ? (
        <ChuThan>Không có buổi đi nào đang diễn ra.</ChuThan>
      ) : (
        nganSach.in_progress.map((outing) => (
          <View
            key={outing.outing_id}
            style={{
              gap: space.xs,
              paddingTop: space.sm,
              borderTopColor: c.line,
              borderTopWidth: 1,
            }}
          >
            <Text style={{ ...type.body, fontWeight: "700", color: c.ink }}>
              {outing.title}
            </Text>
            <Row left="Số người" right={String(outing.headcount)} muted />
            <Row left="Ngân sách mỗi người" right={tienVnd(outing.budget_per_person_vnd)} />
            <Row left="Đã tiêu mỗi người" right={tienVnd(outing.spent_per_person_vnd)} />
            <Row
              left="Còn lại mỗi người"
              right={tienVndCoDau(outing.remaining_per_person_vnd)}
            />
            <Text style={{ ...type.label, color: outing.over_budget ? c.warn : c.inkSoft }}>
              {outing.over_budget ? "Đã vượt ngân sách." : "Đang trong ngân sách."}
            </Text>
          </View>
        ))
      )}
      {nganSach.comparison ? (
        <View style={{ gap: space.xs }}>
          <Text style={{ ...type.label, fontWeight: "700", color: c.inkSoft }}>
            So với mức thường chi
          </Text>
          <Row
            left="Mức đang cân nhắc mỗi người"
            right={tienVnd(nganSach.comparison.candidate_per_person_vnd)}
          />
          <Row
            left="Chênh lệch"
            right={tienVndCoDau(nganSach.comparison.delta_vnd)}
            muted
          />
          <ChuThan>{nhanVerdictNganSach(nganSach.comparison.verdict)}</ChuThan>
        </View>
      ) : null}
    </Card>
  );
}

function TieuDeKhoi({ children }: { children: React.ReactNode }) {
  const c = usePalette();
  return <Text style={{ ...type.title, color: c.ink }}>{children}</Text>;
}

function ChuThan({ children }: { children: React.ReactNode }) {
  const c = usePalette();
  return <Text style={{ ...type.body, color: c.inkSoft }}>{children}</Text>;
}

function ChuDiaChi({ url }: { url: string }) {
  const c = usePalette();
  return <Text style={{ ...type.micro, color: c.inkFaint }}>Đã thử: {url}</Text>;
}

function NhanAi() {
  const c = usePalette();
  return (
    <View
      style={{
        alignSelf: "flex-start",
        borderRadius: radius.pill,
        backgroundColor: c.aiSoft,
        paddingHorizontal: space.sm,
        paddingVertical: space.xs,
      }}
    >
      <Text style={{ ...type.micro, color: c.ai }}>AI gợi ý</Text>
    </View>
  );
}

function nhanVerdictGoiY(verdict: NonNullable<SuggestionStop["verdict"]>): string {
  if (verdict === "hop") return "Hợp với nhóm";
  if (verdict === "tam") return "Có thể cân nhắc";
  return "Chưa hợp với nhóm";
}

/** Keep the server's sign while delegating all digit grouping to the shared formatter. */
function tienVndCoDau(vnd: number): string {
  return vnd < 0 ? `-${tienVnd(-vnd)}` : tienVnd(vnd);
}
