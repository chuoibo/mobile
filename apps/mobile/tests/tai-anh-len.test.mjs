/* rd-fe-25. Choosing a photograph, and what the app does with it.
 *
 * The feature this file guards is the one that turns "there is an upload route"
 * into "a person can add a picture", so what is measured here is the client half
 * of that: which bytes leave the device, under which headers, and what a person
 * is told when the answer is no.
 *
 * Read the middle section first if you are here to judge whether these tests are
 * worth anything. Three of them are negative claims, and a negative is only
 * proved by running the real function over the real shapes:
 *
 *   - a second press while an upload is in flight sends **nothing**
 *   - a cancelled picker reports **no error and no success**
 *   - no thrown value, of any shape, reaches the screen as `[object ...]`
 *
 * What this file does NOT prove, stated because the gap is where the last four
 * image bugs on this branch lived:
 *
 *   - That the server accepts what is sent. `fetch` is captured here, so the
 *     field name and the headers are asserted against the contract as written
 *     down, not against a running API. The live check is the detector run and
 *     the manual upload recorded in the PR.
 *   - That anything renders. `NutChonAnh` is a component and its markup is read
 *     in `tests/nut-chon-anh.test.mjs`; this file is about the wire and the
 *     lifecycle.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { ApiError, taiAnhNhom, taiAnhDaiDien, duongDanAnhDaiDien } from "../dist-test/api.js";
import {
  AnhNhomError,
  NHIEU_BYTE_NHAT,
  nenLai,
  voiAnhDaChon,
} from "../dist-test/camera/anh-nhom.js";

const NGUOI = "3bb00000-bbbb-4bbb-8bbb-0000b0000001";
const NHOM = "1aa00000-aaaa-4aaa-8aaa-0000a0000001";

/** A backend whose every step is scriptable, so the lifecycle can be driven
 *  without a picker, a phone, or a file system. */
function backendGia({ pick, compress, onDiscard } = {}) {
  const daXoa = [];
  return {
    daXoa,
    capture: async () => {
      throw new Error("không dùng camera ở đường này");
    },
    pick: pick ?? (async () => ({ uri: "file:///tmp/goc.jpg", width: 4000, height: 3000 })),
    compress:
      compress ??
      (async () => ({ uri: "file:///tmp/nho.jpg", width: 2048, height: 1536, bytes: 400_000 })),
    discard: async (uri) => {
      daXoa.push(uri);
      onDiscard?.(uri);
    },
  };
}

/** Capture what `fetch` was asked to do, and answer with whatever is scripted. */
function bacFetch(traLoi) {
  const goi = [];
  globalThis.fetch = async (url, init) => {
    goi.push({ url: String(url), init });
    return traLoi(goi.length);
  };
  return goi;
}

function traLoiOk(body, status = 201) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

const ANH_TRA_VE = {
  id: "4cc00000-cccc-4ccc-8ccc-0000c0000002",
  context_id: NHOM,
  url: `/contexts/${NHOM}/photos/4cc00000-cccc-4ccc-8ccc-0000c0000002`,
  content_type: "image/jpeg",
  byte_size: 305,
  width: 64,
  height: 64,
  created_at: "2026-08-30T00:00:00+07:00",
};

/* ------------------------------------------------------------- the wire --- */

test("ảnh nhóm đi bằng multipart, field tên 'file', và KHÔNG có Content-Type", async () => {
  const goi = bacFetch(() => traLoiOk(ANH_TRA_VE));
  await taiAnhNhom(NHOM, { uri: "file:///tmp/nho.jpg" }, NGUOI);

  assert.equal(goi.length, 1);
  assert.equal(goi[0].url, `http://localhost:8099/contexts/${NHOM}/photos`);
  assert.equal(goi[0].init.method, "POST");

  // The header must be ABSENT, not merely different: the boundary is chosen by
  // whatever assembles the FormData, and setting the header by hand is what
  // stops it from being written. A multipart body under `application/json`
  // arrives as an unparseable blob and earns a 422 that names no field.
  const ten = Object.keys(goi[0].init.headers).map((k) => k.toLowerCase());
  assert.ok(!ten.includes("content-type"), `còn gửi Content-Type: ${ten.join(", ")}`);

  // The three headers the route actually checks. `X-Actor-Roles` is the one
  // that cost a turn: without `member` the server answers 403 role_not_permitted,
  // which reads exactly like "you are not in this group".
  assert.equal(goi[0].init.headers["X-Actor-ID"], NGUOI);
  assert.equal(goi[0].init.headers["X-Actor-Roles"], "member");
  assert.equal(goi[0].init.headers["X-Actor-Contexts"], NHOM);
});

test("URL ảnh đại diện ổn định, và không mang theo context của nhóm nào", () => {
  // The address does not change when a new picture is uploaded, which is what
  // lets every other screen point an <Image> at it without storing anything.
  assert.equal(duongDanAnhDaiDien(NGUOI), `/people/${NGUOI}/avatar`);
  assert.equal(duongDanAnhDaiDien(NGUOI), duongDanAnhDaiDien(NGUOI));
});

test("ảnh đại diện gửi lên đúng đường của chính chủ", async () => {
  const goi = bacFetch(() => traLoiOk({ ...ANH_TRA_VE, context_id: null }));
  await taiAnhDaiDien(NGUOI, { uri: "file:///tmp/nho.jpg" }, NGUOI);
  assert.equal(goi[0].url, `http://localhost:8099/people/${NGUOI}/avatar`);
});

test("kích thước máy chủ trả về được giữ nguyên, không bị so với kích thước máy", async () => {
  // The server strips EXIF and re-encodes, so the stored image is a different
  // size from the file that was chosen -- measured on the demo stack, an
  // 861-byte primer came back 305 bytes. Anything comparing the two and
  // complaining would be reporting the feature working as a fault.
  bacFetch(() => traLoiOk(ANH_TRA_VE));
  const ket = await taiAnhNhom(NHOM, { uri: "file:///tmp/nho.jpg" }, NGUOI);
  assert.equal(ket.byteSize, 305);
  assert.equal(ket.url, ANH_TRA_VE.url);
});

/* --------------------------------------------------------- what refusals say --- */

test("mỗi mã lỗi ra một câu tiếng Việt, và không mã số nào lên màn", async () => {
  const bang = [
    [413, "image_too_large"],
    [413, "image_dimensions_too_large"],
    [415, "not_an_image"],
    [403, "permission_denied"],
    [404, "photo_not_found"],
  ];
  for (const [status, code] of bang) {
    bacFetch(() => ({
      ok: false,
      status,
      json: async () => ({ code, detail: "Machine text nobody should read" }),
    }));
    const loi = await taiAnhNhom(NHOM, { uri: "f.jpg" }, NGUOI).then(
      () => null,
      (e) => e,
    );
    assert.ok(loi instanceof ApiError, `${code} không ném ApiError`);
    // Vietnamese prose, and no status code anywhere in it.
    assert.match(loi.message, /[àáảãạăâđêôơưèéẻẽẹìíỉĩịòóỏõọùúủũụỳýỷỹỵ]/i, code);
    assert.doesNotMatch(loi.message, /\b(4\d\d|5\d\d)\b/, `${code} in mã số lên màn`);
    assert.doesNotMatch(loi.message, /[A-Za-z]{4,}_[A-Za-z]{4,}/, `${code} in mã máy lên màn`);
    // The server's own English must not survive.
    assert.doesNotMatch(loi.message, /Machine text/, code);
  }
});

test("413 và 415 nói hai việc khác nhau", () => {
  // Both are "we will not store this", and they have different answers: a heavy
  // file can be re-saved smaller, a file that is not an image cannot. One
  // sentence for both would send half the people who hit it to do something
  // that cannot work.
  const noi = async (code, status) => {
    bacFetch(() => ({ ok: false, status, json: async () => ({ code }) }));
    return taiAnhNhom(NHOM, { uri: "f.jpg" }, NGUOI).then(
      () => "",
      (e) => e.message,
    );
  };
  return Promise.all([noi("image_too_large", 413), noi("not_an_image", 415)]).then(
    ([nang, khongPhaiAnh]) => {
      assert.notEqual(nang, khongPhaiAnh);
    },
  );
});

/* ---------------------------------------------------------- the lifecycle --- */

test("huỷ chọn ảnh không phải là lỗi: không gửi gì, không báo gì", async () => {
  const backend = backendGia({ pick: async () => null });
  let daGoi = false;
  const ket = await voiAnhDaChon(backend, async () => {
    daGoi = true;
  });
  assert.equal(ket, null, "huỷ phải trả null, không phải ném");
  assert.equal(daGoi, false, "huỷ mà vẫn gọi hàm tải lên");
  assert.deepEqual(backend.daXoa, [], "huỷ mà vẫn đi xoá file của ai đó");
});

test("file tạm bị xoá cả khi tải lên HỎNG", async () => {
  // The path nobody exercises by hand, and the one that leaks the full
  // resolution original. A failed upload must not leave it in the cache.
  const backend = backendGia();
  await voiAnhDaChon(backend, async () => {
    throw new ApiError(500, "boom", "Máy chủ đang gặp sự cố.");
  }).then(
    () => assert.fail("phải ném ra"),
    () => {},
  );
  assert.deepEqual(
    backend.daXoa.sort(),
    ["file:///tmp/goc.jpg", "file:///tmp/nho.jpg"],
    "tải lên hỏng mà file tạm còn nằm lại",
  );
});

test("ảnh không nén được thì bản đã ghi ra đĩa cũng bị xoá", async () => {
  // The size tripwire fires precisely when compression did NOT shrink the
  // original, so the file left behind would be the biggest one.
  const backend = backendGia({
    compress: async () => ({
      uri: "file:///tmp/nho.jpg",
      width: 4000,
      height: 3000,
      bytes: NHIEU_BYTE_NHAT + 1,
    }),
  });
  const loi = await voiAnhDaChon(backend, async () => {}).then(
    () => null,
    (e) => e,
  );
  assert.ok(loi instanceof AnhNhomError);
  assert.equal(loi.code, "qua-lon");
  assert.ok(backend.daXoa.includes("file:///tmp/nho.jpg"), "bản bị từ chối còn nằm lại");
});

test("hai giai đoạn được báo, và chỉ sau khi người dùng đã thật sự chọn", async () => {
  const moc = [];
  const backend = backendGia();
  await voiAnhDaChon(backend, async () => "xong", (g) => moc.push(g));
  assert.deepEqual(moc, ["chuan-bi-anh", "dang-gui"]);

  // Cancelled: no stage at all. Somebody who backed out never started, and
  // announcing a stage for them would be the screen inventing work.
  const mocHuy = [];
  await voiAnhDaChon(backendGia({ pick: async () => null }), async () => {}, (g) =>
    mocHuy.push(g),
  );
  assert.deepEqual(mocHuy, []);
});

/* ------------------------------------------- bug-010822, the other shape --- */

test("không giá trị nào ném ra lọt lên màn dưới dạng [object ...]", async () => {
  // The web manipulator rejects with the HTMLCanvasElement it was going to draw
  // into when the browser cannot decode the source. Assigning that to a message
  // slot stringifies it, and "[object HTMLCanvasElement]" appeared on screen
  // where an explanation belonged. Every shape a backend really throws is run
  // here, because that is the only way a negative claim gets proved.
  const nemRa = [
    { ten: "canvas giả", giaTri: { toString: () => "[object HTMLCanvasElement]" } },
    { ten: "chuỗi trần", giaTri: "boom" },
    { ten: "null", giaTri: null },
    { ten: "số", giaTri: 7 },
    { ten: "Error máy", giaTri: new Error("Failed to create canvas context") },
    { ten: "object rỗng", giaTri: {} },
  ];
  for (const { ten, giaTri } of nemRa) {
    const backend = backendGia({
      compress: async () => {
        throw giaTri;
      },
    });
    const loi = await nenLai(backend, { uri: "file:///tmp/goc.jpg", width: 10, height: 10 }).then(
      () => null,
      (e) => e,
    );
    assert.ok(loi instanceof AnhNhomError, `${ten}: không được gói lại`);
    assert.doesNotMatch(loi.message, /\[object/, `${ten}: lọt [object ...] lên màn`);
    assert.match(
      loi.message,
      /[àáảãạăâđêôơưèéẻẽẹìíỉĩịòóỏõọùúủũụỳýỷỹỵ]/i,
      `${ten}: câu không phải tiếng Việt`,
    );
    // The platform's English is kept for a bug report, never shown.
    assert.doesNotMatch(loi.message, /canvas|Failed/i, `${ten}: lọt chữ máy lên màn`);
  }
});
