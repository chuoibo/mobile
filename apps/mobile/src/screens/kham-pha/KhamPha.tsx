/** Khám phá — the tab the app opens on.
 *
 * A placeholder with its own name and its own address in the shell, so the
 * default tab is a real destination rather than a blank. rd-do-fe-06 builds
 * the actual thing (search, AI MATCH cards, the map strip); this file exists
 * so the shell can be finished and checked before that lands, and so the work
 * that replaces it has an obvious place to go.
 */
import React from "react";
import { ManVo } from "../../navigation/ManVo";

export function KhamPha() {
  return (
    <ManVo
      title="Khám phá"
      hint="AI gợi ý cho nhóm bạn"
      screen="KhamPha"
      owner="devops"
      work="rd-do-fe-06"
    />
  );
}
