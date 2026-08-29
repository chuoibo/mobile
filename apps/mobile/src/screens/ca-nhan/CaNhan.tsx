/** Cá nhân — profile, finance overview, journey.
 *
 * Placeholder for rd-do-fe-09. It does show the one thing the shell genuinely
 * knows today, which is who you picked on the opening screen: that is real
 * state, it came from a real choice, and printing it here is what makes the
 * sign-in on the first screen mean anything at all.
 */
import React from "react";
import { Text, View } from "react-native";
import { space, type, usePalette } from "../../theme";
import { Card } from "../../ui/Kit";
import { ManVo } from "../../navigation/ManVo";
import { DEMO_GROUP_NAME, type DemoPerson } from "../../navigation/nhom-demo";

export function CaNhan({ nguoi }: { nguoi: DemoPerson | null }) {
  const c = usePalette();
  return (
    <ManVo
      title="Cá nhân"
      hint="Hồ sơ, tài chính và hành trình của bạn"
      screen="CaNhan"
      owner="devops"
      work="rd-do-fe-09"
    >
      {nguoi ? (
        <Card>
          <View style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
            <View
              style={{
                width: 52,
                height: 52,
                borderRadius: 999,
                backgroundColor: c.accentSoft,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Text style={{ ...type.title, color: c.accent }}>{nguoi.initials}</Text>
            </View>
            <View style={{ flex: 1, gap: 2 }}>
              <Text style={{ ...type.title, color: c.ink }}>{nguoi.name}</Text>
              <Text style={{ ...type.label, color: c.inkSoft }}>{DEMO_GROUP_NAME}</Text>
            </View>
          </View>
          <Text style={{ ...type.label, color: c.inkSoft }}>
            Đang xem app với tư cách {nguoi.name} — chọn ở màn mở đầu, chưa có đăng nhập thật.
          </Text>
        </Card>
      ) : null}
    </ManVo>
  );
}
