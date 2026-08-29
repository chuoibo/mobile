/** The screen a tab shows before its screen exists.
 *
 * Every tab in this shell is reachable, and four of them currently arrive
 * here. That is the point of a shell -- but an empty white page is
 * indistinguishable from a screen that failed to load, and someone
 * demonstrating this app should never have to say "no, that part is fine, it
 * just hasn't been built". So the placeholder says which screen belongs here,
 * which work item builds it, and which lane owns that work.
 *
 * Deliberately not styled as an error. It is a plan, not a fault.
 */
import React from "react";
import { Text, View } from "react-native";
import { radius, space, type, usePalette } from "../theme";
import { Card, Screen } from "../ui/Kit";

export function ManVo({ title, hint, screen, owner, work, children }: {
  title: string;
  hint: string;
  /** Component name that will replace this one, so the note is greppable. */
  screen: string;
  owner: string;
  work: string;
  children?: React.ReactNode;
}) {
  const c = usePalette();
  return (
    <Screen title={title} hint={hint}>
      {children}
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
            Màn này chưa dựng, mới có chỗ đứng trong vỏ tab.
          </Text>
        </View>
        <Text style={{ ...type.label, color: c.inkSoft }}>
          Sẽ là <Text style={{ color: c.ink, fontWeight: "600" }}>{screen}</Text>, do lane{" "}
          <Text style={{ color: c.ink, fontWeight: "600" }}>{owner}</Text> dựng ở việc{" "}
          <Text style={{ color: c.ink, fontWeight: "600" }}>{work}</Text>.
        </Text>
      </Card>
    </Screen>
  );
}
