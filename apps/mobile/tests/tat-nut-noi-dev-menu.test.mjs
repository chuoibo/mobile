/**
 * Nút nổi «Tools» của expo-dev-menu phải tắt mặc định trong bản dev build.
 *
 * Mọi ảnh chụp native từ khi có dev client đều mang một bánh răng xám nổi ở góc
 * phải trên, kể cả trên màn tiền (P0 của báo cáo UI 2026-09-05). Dev menu đọc
 * default của nút từ meta-data `EXDevMenuShowFloatingActionButton` trong
 * AndroidManifest, nên plugin này chỉ cần đặt nó thành "false". Test chứng
 * minh: plugin được khai trong app.json, biến đổi manifest đúng một mục, chạy
 * hai lần không nhân đôi, và không đụng meta-data khác.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

import plugin, { META_KEY, tatNutNoiDevMenu } from "../plugins/tat-nut-noi-dev-menu.js";

const app = JSON.parse(readFileSync(fileURLToPath(new URL("../app.json", import.meta.url)), "utf8"));

function manifestGia() {
  return {
    manifest: {
      $: { "xmlns:android": "http://schemas.android.com/apk/res/android" },
      application: [
        {
          $: { "android:name": ".MainApplication" },
          "meta-data": [{ $: { "android:name": "expo.modules.updates.ENABLED", "android:value": "false" } }],
          activity: [],
        },
      ],
    },
  };
}

function metaData(manifest) {
  return manifest.manifest.application[0]["meta-data"].map((m) => [m.$["android:name"], m.$["android:value"]]);
}

test("app.json khai plugin, nên prebuild nào cũng đi qua nó", () => {
  assert.ok(
    app.expo.plugins.includes("./plugins/tat-nut-noi-dev-menu"),
    "plugin không có trong app.json thì bản dựng sau vẫn mọc bánh răng",
  );
  assert.equal(typeof plugin, "function");
});

test("meta-data tắt nút nổi được thêm đúng một lần, kể cả khi chạy hai lần", () => {
  const m = tatNutNoiDevMenu(tatNutNoiDevMenu(manifestGia()));
  const rows = metaData(m);
  assert.deepEqual(rows.filter(([name]) => name === META_KEY), [[META_KEY, "false"]]);
  assert.equal(META_KEY, "EXDevMenuShowFloatingActionButton");
});

test("meta-data sẵn có của người khác không bị đụng", () => {
  const rows = metaData(tatNutNoiDevMenu(manifestGia()));
  assert.deepEqual(rows[0], ["expo.modules.updates.ENABLED", "false"]);
  assert.equal(rows.length, 2);
});
