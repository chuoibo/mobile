/* The pieces around the OTP door that are not the wire: what the code screen
 * shows of a number, where the fixture door may exist, and what `nguon.ts`
 * says about a session that has no group yet.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node --test tests/rudi-cua-otp.test.mjs
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { CUA_FIXTURE_DEV } from "../dist-test/rudi/cua-fixture.js";
import { nguonHienTai } from "../dist-test/rudi/nguon.js";
import { cheSo } from "../dist-test/rudi/otp-dang-cho.js";

const doc = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

// Few digits on purpose: the repo guard reads nine in a row as a phone number.
test("cheSo giữ đúng ba số cuối và giấu phần còn lại", () => {
  assert.equal(cheSo("09 345 678"), "••• ••• 678");
  assert.equal(cheSo("+84 (9) 34-678"), "••• ••• 678");
  assert.ok(!cheSo("09 345 678").includes("345"));
  assert.equal(cheSo("12"), "số của bạn");
});

test("dưới node không có __DEV__ nên cửa fixture đóng, dù cờ có lên hay không", () => {
  assert.equal(CUA_FIXTURE_DEV, false);
});

test("cua-fixture đọc cờ bằng member expression thuần, để Expo inline được", () => {
  const src = doc("src/rudi/cua-fixture.ts");
  assert.match(src, /process\.env\.EXPO_PUBLIC_RUDI_FIXTURE/);
  assert.doesNotMatch(src, /process\?\.env|env\[/);
});

test("cửa «Vào bản trải nghiệm» có đúng MỘT chỗ, và chỗ đó nằm sau CUA_FIXTURE_DEV", () => {
  const login = doc("src/rudi/screens/auth/Login.tsx");
  const nhan = "Vào bản trải nghiệm Team Đà Lạt";
  const viTri = login.indexOf(nhan);
  assert.ok(viTri > 0, "màn đăng nhập không còn cửa dev: bảng Maestro mặc định mất đường vào");
  assert.equal(login.indexOf(nhan, viTri + 1), -1, "cửa dev xuất hiện hai lần trong Login.tsx");
  const dieuKien = login.lastIndexOf("CUA_FIXTURE_DEV ? (", viTri);
  assert.ok(dieuKien > 0, "nhãn cửa dev không nằm trong nhánh CUA_FIXTURE_DEV");
  assert.ok(login.indexOf(") : null}", viTri) > viTri);
  // And nowhere else on the RuDi shell.
  for (const tep of ["src/rudi/screens/Onboarding.tsx", "src/rudi/screens/Profile.tsx"]) {
    assert.equal(doc(tep).includes(nhan), false, `${tep} vẫn còn một cửa fixture`);
  }
});

test("phiên không có nhóm là trải nghiệm có lý do, không phải live với contextId rỗng", () => {
  const nguon = nguonHienTai(
    { person_id: "p", context_id: null, membership_state: null },
    {},
  );
  assert.equal(nguon.kieu, "trai-nghiem");
  assert.match(nguon.viSao, /chưa ở nhóm nào/);
});
