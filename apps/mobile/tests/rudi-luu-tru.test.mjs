/* What survives closing the app, and what a corrupt blob is allowed to do.
 *
 * Until this branch the app wrote nothing anywhere -- `grep -rn
 * "AsyncStorage|SecureStore" src app` was empty -- while four sentences on
 * five screens told people their choices were saved on the device. A Maestro
 * flow measured it: change the 18:00 slot, kill the process, come back, the
 * edit is gone.
 *
 * Now that there IS a disk, the interesting failure moves. What comes back is
 * not this build's data: it is whatever some earlier build wrote, possibly
 * half-written, possibly shaped differently. And `assignments` is not
 * cosmetic -- it feeds `draftPicture`, which throws `DraftMoneyError` on a
 * person index outside the roster. One bad index in a stored blob would crash
 * the settlement screen on every launch, with no way past it.
 *
 * So the last test here is the one that matters most: take a blob that is
 * corrupt in every field at once, restore it, and hand the result to the real
 * money function. It must not throw.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { dongGoi, moGoi, noiLuu, noiLuuNgan, PHIEN_BAN_LUU } from "../dist-test/rudi/luu-tru.js";
import { sharesByPerson } from "../dist-test/rudi/money.js";

const IDS = ["minh-anh", "tuan-kiet", "thu-trang", "quang-huy"];

/** Small stand-in for the RuDi seed. `fixtures.ts` cannot be imported here: it
 *  `require`s image assets, which bare node has no loader for. */
function seed() {
  return {
    displayName: "Minh Anh",
    bio: "Đi để nhớ",
    interests: ["Ăn ngon"],
    vibes: ["Ngoài trời"],
    savedPlaceIds: ["still-cafe"],
    itinerary: [
      {
        day: "Ngày 1",
        items: [
          { time: "07:00", title: "Khởi hành", icon: "car-outline", color: "#F97316" },
          { time: "18:00", title: "BBQ bên hồ", icon: "flame-outline", color: "#E11D48", placeId: "ho" },
        ],
      },
    ],
    tripName: "Đà Lạt cuối tuần",
    destination: "Đà Lạt",
    startDate: "17/10/2026",
    endDate: "19/10/2026",
    selectedMemberIds: IDS,
    aiSuggest: true,
    chatMessages: [],
    voteChoice: null,
    voteConfirmed: false,
    assignments: [
      [0, 1, 2, 3],
      [1, 3],
    ],
    paidFromIndexes: [1, 2],
    remindedPending: false,
    checkedInIds: ["minh-anh"],
    locationSharing: true,
    receiptPicked: false,
  };
}

const LINES = [
  { amount: 450_000, personIndexes: [] },
  { amount: 560_000, personIndexes: [] },
];

/** The real money call the settlement screen makes, over restored assignments. */
function tinhTien(phien) {
  return sharesByPerson(
    LINES.map((line, i) => ({ amount: line.amount, personIndexes: phien.assignments[i] })),
    IDS,
    0,
  );
}

test("what somebody changed comes back", () => {
  const goc = seed();
  goc.displayName = "NGUOI LA KHAC";
  goc.savedPlaceIds = ["still-cafe", "puppy-farm"];
  goc.itinerary[0].items[1].title = "Still Cafe Đà Lạt";
  goc.assignments = [
    [0, 1],
    [1, 3, 0],
  ];
  goc.voteChoice = 2;
  goc.voteConfirmed = true;
  const ve = moGoi(dongGoi(goc), seed());
  assert.equal(ve.displayName, "NGUOI LA KHAC");
  assert.deepEqual(ve.savedPlaceIds, ["still-cafe", "puppy-farm"]);
  assert.equal(ve.itinerary[0].items[1].title, "Still Cafe Đà Lạt");
  assert.deepEqual(ve.assignments, [
    [0, 1],
    [1, 3, 0],
  ]);
  assert.equal(ve.voteChoice, 2);
  assert.equal(ve.voteConfirmed, true);
});

test("an open panel is not somebody's data and does not reach the disk", () => {
  // Restoring these would reopen a sheet somebody closed, days later, and show
  // a notice about something that happened in another session.
  const goc = { ...seed(), profileNotice: "Đã lưu hồ sơ", inboxOpen: true, itineraryEditing: true, enteredAsDemo: true };
  const luu = JSON.parse(dongGoi(goc));
  assert.equal(luu.v, PHIEN_BAN_LUU);
  for (const khoa of ["profileNotice", "inboxOpen", "itineraryEditing", "enteredAsDemo"]) {
    assert.equal(khoa in luu.phien, false, `${khoa} đã lọt xuống đĩa`);
  }
});

test("nothing readable on disk means the seed, not a crash", () => {
  for (const raw of [null, undefined, "", "khong-phai-json", "[]", '"chuoi"', "null"]) {
    assert.deepEqual(moGoi(raw, seed()), seed(), String(raw));
  }
});

test("an older shape is dropped whole rather than half-migrated", () => {
  const cu = JSON.stringify({ v: PHIEN_BAN_LUU + 1, phien: { ...seed(), displayName: "Cũ" } });
  assert.equal(moGoi(cu, seed()).displayName, "Minh Anh");
  const khongCoVersion = JSON.stringify({ phien: { ...seed(), displayName: "Cũ" } });
  assert.equal(moGoi(khongCoVersion, seed()).displayName, "Minh Anh");
});

test("a corrupt field loses that field, not the session", () => {
  const hong = JSON.stringify({
    v: PHIEN_BAN_LUU,
    phien: {
      ...seed(),
      displayName: "Tên vẫn tốt",
      // Every one of these is a shape the validator has to refuse.
      assignments: [[0, 99], [1]],
      itinerary: [{ day: "Ngày 1", items: [{ time: "07:00", title: "x", icon: "khong-co-icon-nay", color: "#000" }] }],
      savedPlaceIds: ["ok", 7],
      aiSuggest: "co",
      voteChoice: "hai",
    },
  });
  const ve = moGoi(hong, seed());
  // Kept: the field that was fine.
  assert.equal(ve.displayName, "Tên vẫn tốt");
  // Replaced by the seed, each for its own reason.
  assert.deepEqual(ve.assignments, seed().assignments, "chỉ số 99 ngoài roster");
  assert.deepEqual(ve.itinerary, seed().itinerary, "icon build này không có");
  assert.deepEqual(ve.savedPlaceIds, seed().savedPlaceIds, "mảng lẫn số");
  assert.equal(ve.aiSuggest, true, "chuỗi thay cho boolean");
  assert.equal(ve.voteChoice, null, "voteChoice không phải số");
});

test("a line assigned to nobody is refused before it reaches the allocator", () => {
  // `sharesByPerson` throws on this, and a throw at launch is unrecoverable
  // because every relaunch reads the same blob back.
  const trong = JSON.stringify({ v: PHIEN_BAN_LUU, phien: { ...seed(), assignments: [[0, 1], []] } });
  assert.deepEqual(moGoi(trong, seed()).assignments, seed().assignments);
  const saiSoDong = JSON.stringify({ v: PHIEN_BAN_LUU, phien: { ...seed(), assignments: [[0]] } });
  assert.deepEqual(moGoi(saiSoDong, seed()).assignments, seed().assignments);
});

test("no blob, however broken, makes the money screen throw", () => {
  const rac = [
    JSON.stringify({ v: PHIEN_BAN_LUU, phien: { assignments: [[-1], [999]] } }),
    JSON.stringify({ v: PHIEN_BAN_LUU, phien: { assignments: [[], []] } }),
    JSON.stringify({ v: PHIEN_BAN_LUU, phien: { assignments: [[1.5], ["0"]] } }),
    JSON.stringify({ v: PHIEN_BAN_LUU, phien: { assignments: "khong-phai-mang" } }),
    JSON.stringify({ v: PHIEN_BAN_LUU, phien: { assignments: [[0, 0, 0], [3]] } }),
    JSON.stringify({ v: PHIEN_BAN_LUU, phien: null }),
    "{",
  ];
  for (const raw of rac) {
    const ve = moGoi(raw, seed());
    const shares = tinhTien(ve);
    assert.equal(
      shares.reduce((sum, n) => sum + n, 0),
      1_010_000,
      `blob ${raw.slice(0, 40)} làm lệch tổng`,
    );
  }
});

test("the two durability sentences actually differ", () => {
  // A helper that returned the same string on both branches would let the
  // "saved on device" claim come back while the flag said otherwise.
  assert.notEqual(noiLuu(true), noiLuu(false));
  assert.notEqual(noiLuuNgan(true), noiLuuNgan(false));
  for (const s of [noiLuu(true), noiLuu(false), noiLuuNgan(true), noiLuuNgan(false)]) {
    assert.equal(s.length > 0, true);
  }
  // The false branch must not promise the device.
  assert.equal(noiLuu(false).includes("trên máy"), false);
  assert.equal(noiLuuNgan(false).includes("trên máy"), false);
});
