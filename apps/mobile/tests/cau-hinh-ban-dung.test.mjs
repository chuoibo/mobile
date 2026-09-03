/* What a build profile must say before it can reach anybody's phone.
 *
 * ## The hole
 *
 * `src/api.ts` reads `process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8099"`.
 * `EXPO_PUBLIC_*` is inlined at bundle time, so a build that does not set it
 * ships the fallback -- and on a phone `localhost` is the phone. An installed
 * app would dial itself, get nothing, and report it as a server fault.
 *
 * Measured on the emulator: the settlement screen only reached a real API after
 * `adb reverse tcp:8106`, which is a laptop cable, not a product.
 *
 * `eas.json` declares four profiles and none of them set the variable. Nothing
 * in the repo noticed, because a missing environment variable is not a type
 * error, not a failing request in a test with a stubbed `fetch`, and not
 * visible in `expo export --platform web` where `localhost` happens to be the
 * developer's own machine.
 *
 * ## Why this file pins the gap instead of filling it
 *
 * There is nowhere to point the variable AT. `docs/architecture/01-duong-toi-
 * production.md` B3 measured it: no `fly.toml`, no `render.yaml`, no `*.tf` --
 * the API has never run anywhere but a laptop. Writing a plausible URL here
 * would be the same class of defect this whole branch is removing: a config
 * that looks shipped and is not.
 *
 * So the gap is recorded, exactly, and the recording is what goes red. Adding a
 * profile without a URL is red. Setting a URL while the profile is still listed
 * as having none is red. Shipping `http://` without saying so in `app.json` is
 * red, because Android blocks cleartext on API 28+ and the app would fail on a
 * real device while every gate here stayed green.
 *
 * When it is fixed: the API gets deployed, `production` and `preview` set
 * `EXPO_PUBLIC_API_URL` to the https URL, and their names come out of
 * `CHUA_CO_MAY_CHU` below.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const eas = JSON.parse(readFileSync(fileURLToPath(new URL("../eas.json", import.meta.url)), "utf8"));
const app = JSON.parse(readFileSync(fileURLToPath(new URL("../app.json", import.meta.url)), "utf8"));

/** Profiles with no server to point at, and why. B3 in docs/architecture/01. */
const CHUA_CO_MAY_CHU = {
  development: "dev client nói chuyện với Metro trên máy người dựng",
  "development-simulator": "như trên, chạy trong simulator",
  preview: "B3 -- API chưa từng chạy ở đâu ngoài laptop",
  production: "B3 -- API chưa từng chạy ở đâu ngoài laptop",
};

function apiUrlOf(profile) {
  return eas.build[profile]?.env?.EXPO_PUBLIC_API_URL ?? null;
}

test("mọi profile build đều được kể tên, không profile nào lọt qua im lặng", () => {
  // A new profile is a new way to ship, so it has to arrive through here.
  assert.deepEqual(Object.keys(eas.build).sort(), Object.keys(CHUA_CO_MAY_CHU).sort());
});

test("profile đã ghi nhận là chưa có máy chủ thì không được lặng lẽ mọc URL", () => {
  for (const [profile, reason] of Object.entries(CHUA_CO_MAY_CHU)) {
    assert.equal(
      apiUrlOf(profile),
      null,
      `${profile} giờ có EXPO_PUBLIC_API_URL (${reason}) -- xoá nó khỏi CHUA_CO_MAY_CHU`,
    );
  }
});

test("profile không nằm trong danh sách phải khai địa chỉ, và phải là https", () => {
  for (const profile of Object.keys(eas.build)) {
    if (profile in CHUA_CO_MAY_CHU) continue;
    const url = apiUrlOf(profile);
    assert.notEqual(url, null, `${profile} dựng ra một app không biết gọi máy chủ nào`);
    assert.match(url, /^https:\/\//, `${profile} gọi ${url}: Android chặn cleartext từ API 28`);
  }
});

test("nếu có profile đi http thì app.json phải khai cleartext, không để mặc định quyết", () => {
  const httpProfiles = Object.keys(eas.build).filter((p) => apiUrlOf(p)?.startsWith("http://"));
  const declared = app.expo.android?.usesCleartextTraffic;
  if (httpProfiles.length === 0) {
    // Nothing ships http today, so nothing may claim it needs cleartext either.
    assert.equal(
      declared,
      undefined,
      "app.json mở cleartext trong khi không profile nào đi http",
    );
    return;
  }
  assert.equal(
    declared,
    true,
    `${httpProfiles.join(", ")} đi http nhưng app.json chưa khai usesCleartextTraffic`,
  );
});

/* `EXPO_PUBLIC_RUDI_ACTOR` / `EXPO_PUBLIC_RUDI_CONTEXT` pin the app to ONE
 * person in ONE group. They exist so a developer can point the RuDi screens at
 * a seeded group on their own machine (`src/rudi/nguon.ts`), and they are
 * inlined at bundle time -- so a build profile carrying them ships an app that
 * shows everybody the same stranger's money.
 *
 * There is no legitimate value for them in a shippable profile, so unlike the
 * API URL above this is not a "recorded gap" but a flat refusal. */
test("không profile nào được ghim danh tính dev vào bản dựng", () => {
  for (const profile of Object.keys(eas.build)) {
    const env = eas.build[profile]?.env ?? {};
    for (const bien of ["EXPO_PUBLIC_RUDI_ACTOR", "EXPO_PUBLIC_RUDI_CONTEXT"]) {
      assert.equal(
        bien in env,
        false,
        `${profile} ghim ${bien}: bản dựng sẽ hiện tiền của một người lạ cho mọi người`,
      );
    }
  }
});
