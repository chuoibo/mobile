/* What a cold-start URL is allowed to make the app do.
 *
 * The defect: on Expo Go 57 / SDK 57 every deep link into an inner route
 * landed on the welcome screen. Measured 4 times out of 4 with
 * `exp://localhost:8095/--/settlements/team-da-lat`, and an A/B that removed
 * one line from `app/_layout.tsx` made the same link open the settlement
 * screen. With the shipping `rudi://` scheme that is every invite, share and
 * push-notification link.
 *
 * The cause was a synchronous guard in front of an asynchronous redirect, so
 * no assertion about the router could have caught it -- the router was doing
 * the right thing and being overwritten a frame later. What IS assertable is
 * the decision itself, once it stops living inside a `useEffect`. That is what
 * `diemVaoTuUrl` is and what this file gates.
 *
 * The first test is the one that keeps the rest honest: it is the exact URL
 * from the reproduction, and it must come back `giu-nguyen`.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { diemVaoTuUrl } from "../dist-test/rudi/duong-vao.js";

test("the reproduced link is left alone", () => {
  assert.deepEqual(diemVaoTuUrl("exp://localhost:8095/--/settlements/team-da-lat"), {
    kieu: "giu-nguyen",
  });
});

test("every shape that names a route is left alone", () => {
  const named = [
    "exp://localhost:8095/--/settlements/team-da-lat",
    "exp://127.0.0.1:8081/--/explore",
    "exp://localhost:8095/--/trips/team-da-lat/itinerary",
    "rudi://settlements/team-da-lat",
    "rudi://votes/diem-den",
    "rudi:///finance",
    // A route AND a fragment: the route wins, because the router already
    // honoured it. This is the combination the old code got wrong.
    "exp://localhost:8095/--/settlements/team-da-lat#explore",
  ];
  for (const url of named) {
    assert.deepEqual(diemVaoTuUrl(url), { kieu: "giu-nguyen" }, url);
  }
});

test("a bare fragment still reaches its screen", () => {
  // This is the adapter's only job, and it has to keep working: the legacy web
  // harness addresses screens this way and native has no fragment router.
  assert.deepEqual(diemVaoTuUrl("exp://localhost:8095#explore"), {
    kieu: "doi-huong",
    toi: "/explore",
  });
  assert.deepEqual(diemVaoTuUrl("rudi://#tin-nhan"), { kieu: "doi-huong", toi: "/messages" });
  assert.deepEqual(diemVaoTuUrl("rudi://#/ca-nhan"), { kieu: "doi-huong", toi: "/profile" });
  assert.deepEqual(diemVaoTuUrl("exp://localhost:8095#lap-ke-hoach"), {
    kieu: "doi-huong",
    toi: "/plan",
  });
});

test("an entry that names no route still lands on welcome", () => {
  // Measured, not assumed. A draft of this dropped the /welcome fallback on the
  // reasoning that `app/index.tsx` redirects `/` there anyway -- and on the
  // emulator `IndexRoute` never rendered at all, because expo-router does not
  // route `exp://localhost:8095` through `/`. A pathless start landed on the
  // Khám phá tab and the welcome screen became unreachable.
  for (const url of [null, undefined, "", "exp://localhost:8095", "rudi://"]) {
    assert.deepEqual(diemVaoTuUrl(url), { kieu: "doi-huong", toi: "/welcome" }, String(url));
  }
  // An unknown fragment names no screen, so it is an entry like any other.
  assert.deepEqual(diemVaoTuUrl("rudi://#khong-co-man-nay"), {
    kieu: "doi-huong",
    toi: "/welcome",
  });
});

test("một link mang lời mời thì mang được mã đi nguyên vẹn", () => {
  // This is how a real person gets in: somebody sends them a link. It only
  // works at all because the previous round fixed the swallow that sent every
  // deep link to /welcome.
  for (const url of [
    "rudi://moi/abc123",
    "exp://localhost:8095/--/moi/abc123",
    "rudi:///moi/abc123",
  ]) {
    assert.deepEqual(diemVaoTuUrl(url), { kieu: "loi-moi", ma: "abc123" }, url);
  }
});

test("mã lời mời không bị cắt bởi ký tự cần thoát", () => {
  // `secrets.token_urlsafe` yields `-` and `_`, and a link that has been
  // through a chat app may arrive percent-encoded. A token silently truncated
  // is a person who cannot sign in and no sentence saying why.
  assert.deepEqual(diemVaoTuUrl("rudi://moi/aB-9_x.Y~z"), {
    kieu: "loi-moi",
    ma: "aB-9_x.Y~z",
  });
  assert.deepEqual(diemVaoTuUrl("rudi://moi/a%2Fb"), { kieu: "loi-moi", ma: "a/b" });
});

test("một link KHÔNG mang lời mời thì không dựng ra màn nhận rỗng", () => {
  // The failure this refuses: a screen that asks somebody to accept an
  // invitation it does not have.
  for (const url of [
    "rudi://moi",
    "rudi://moi/",
    "rudi://settlements/team-da-lat",
    "exp://localhost:8095",
    "rudi://",
  ]) {
    assert.notEqual(diemVaoTuUrl(url).kieu, "loi-moi", url);
  }
});

test("phần sau dấu gạch chéo thứ hai không lọt vào mã", () => {
  // A token is one opaque string. Accepting `moi/<token>/anything` would take
  // a malformed link and send its first half to the server as though it were
  // whole.
  assert.deepEqual(diemVaoTuUrl("rudi://moi/abc123/them"), {
    kieu: "loi-moi",
    ma: "abc123",
  });
});

test("the web QA harness's own addresses are not touched", () => {
  for (const url of [
    "http://localhost:8081/?man=quyet-toan",
    "http://localhost:8081/#tab=explore&nguoi=minh",
    "rudi://#tab=explore",
  ]) {
    assert.deepEqual(diemVaoTuUrl(url), { kieu: "giu-nguyen" }, url);
  }
});
