/** What the client does when the photo route answers 200 with zero bytes.
 *
 * The server half of this question is measured in `do-dieu-kien-anh-chet.py`:
 * a photo whose file has been truncated is served as `200`, `content-length:
 * 0`, `content-type: image/jpeg`. This file asks the other half -- what the app
 * does with that answer -- against the SAME live API, driving the same
 * `taiAnhCoQuyen` the screens import rather than a re-description of it.
 *
 * The distinction that matters: `taiAnhCoQuyen` branches on `response.ok`, and
 * `ok` is true for a 200 no matter how many bytes followed. So the interesting
 * measurement is not "does it throw" -- it is what a caller receives when it
 * does not, because `Anh.tsx` treats a resolved promise as "the photograph
 * arrived" and paints it.
 *
 * Usage: ANH_API=http://127.0.0.1:PORT ANH_MEDIA=/path node do-client-nhan-200-rong.mjs
 *
 * Requires `apps/mobile/dist-test/api.js`, which `scripts/e2e_slice.sh` builds.
 */

import { randomUUID } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const BASE = (process.env.ANH_API ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
const MEDIA = process.env.ANH_MEDIA;
if (!MEDIA) {
  console.error("Dat ANH_MEDIA = MOBILE_MEDIA_ROOT cua stack dang do.");
  process.exit(2);
}

// `api.ts` reads this once at module load, so it must be set before the import.
process.env.EXPO_PUBLIC_API_URL = BASE;

const here = path.dirname(fileURLToPath(import.meta.url));
const api = await import(
  path.join(here, "..", "..", "..", "apps", "mobile", "dist-test", "api.js")
);

const failures = [];
function check(name, ok, detail = "") {
  console.log(`[${ok ? "PASS" : "FAIL"}] ${name}${detail ? ` -- ${detail}` : ""}`);
  if (!ok) failures.push(`${name}: ${detail}`);
}

function headers(actor, contexts) {
  const h = { "X-Actor-ID": actor, "X-Actor-Roles": "member" };
  if (contexts) h["X-Actor-Contexts"] = contexts;
  return h;
}

async function call(method, p, { actor, contexts, body } = {}) {
  const h = actor ? headers(actor, contexts) : {};
  if (body) h["Content-Type"] = "application/json";
  const r = await fetch(BASE + p, {
    method,
    headers: h,
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  let parsed = {};
  try {
    parsed = JSON.parse(text);
  } catch {
    /* not JSON */
  }
  return { status: r.status, body: parsed };
}

/** A 320x240 JPEG built byte by byte would be a second image encoder in this
 *  repo. Instead: ask the API for one it already made. */
async function seedPhoto(group, actor) {
  const before = new Set(listMedia());
  const png = Buffer.from(
    // 1x1 red PNG. Small on purpose: the point is the file's existence, not
    // its pixels -- the pixels are asserted on the Python side.
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
    "base64",
  );
  const form = new FormData();
  form.append("file", new Blob([png], { type: "image/png" }), "anh.png");
  const r = await fetch(`${BASE}/contexts/${group}/photos`, {
    method: "POST",
    headers: headers(actor, group),
    body: form,
  });
  if (r.status !== 201 && r.status !== 200) {
    throw new Error(`upload that bai: ${r.status} ${await r.text()}`);
  }
  const wire = await r.json();
  const after = listMedia().filter((f) => !before.has(f));
  if (after.length !== 1) throw new Error(`mong doi 1 file moi, thay ${after.length}`);
  return { wire, file: after[0] };
}

function listMedia() {
  const out = [];
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else out.push(full);
    }
  };
  if (fs.existsSync(MEDIA)) walk(MEDIA);
  return out;
}

const stem = String(Math.floor(Math.random() * 1000000)).padStart(6, "0");
const idr = await call("POST", "/identity/person-id", { body: { phone: `094${stem}1` } });
const an = idr.body.person_id;
await call("PUT", `/people/${an}`, { actor: an, body: { display_name: "An" } });
const grp = await call("POST", "/contexts", {
  actor: an,
  body: { display_name: "Nhom do client" },
});
const group = grp.body.id;

console.log(`\n== bo du lieu ==\napi=${BASE}\nnhom=${group}\n`);

// --- positive control, first ------------------------------------------------
const healthy = await seedPhoto(group, an);
let control = null;
let controlErr = null;
try {
  control = await api.taiAnhCoQuyen(BASE + healthy.wire.url, an, group);
} catch (e) {
  controlErr = e;
}
check(
  "H DOI CHUNG DUONG: anh lanh -> taiAnhCoQuyen tra ve mot nguon",
  controlErr === null && typeof control === "string" && control.length > 0,
  controlErr ? `nem ${controlErr.code ?? controlErr.message}` : `nguon=${String(control).slice(0, 40)}`,
);

// --- the 404 path, to prove the client CAN see a refusal --------------------
let notFound = null;
try {
  await api.taiAnhCoQuyen(`${BASE}/contexts/${group}/photos/${randomUUID()}`, an, group);
} catch (e) {
  notFound = e;
}
check(
  "DOI CHUNG AM: 404 -> taiAnhCoQuyen NEM ApiError co cau chu cho nguoi doc",
  notFound !== null && notFound.status === 404,
  notFound ? `status=${notFound.status} code=${notFound.code} message=${JSON.stringify(notFound.message)}` : "khong nem",
);

// --- the measurement: 200 with zero bytes ----------------------------------
const dead = await seedPhoto(group, an);
const declared = dead.wire.byte_size;
fs.writeFileSync(dead.file, Buffer.alloc(0));

const raw = await fetch(BASE + dead.wire.url, { headers: headers(an, group) });
const rawBlob = await raw.blob();
check(
  "may chu VAN tra 200 khi client tu fetch",
  raw.status === 200 && rawBlob.size === 0,
  `status=${raw.status} size=${rawBlob.size} type=${rawBlob.type}` +
    ` content-length=${raw.headers.get("content-length")} (DB khai ${declared})`,
);

let got = null;
let threw = null;
try {
  got = await api.taiAnhCoQuyen(BASE + dead.wire.url, an, group);
} catch (e) {
  threw = e;
}
check(
  "LO HONG: taiAnhCoQuyen coi 200-rong la THANH CONG, khong nem gi",
  threw === null,
  threw ? `nem status=${threw.status} code=${threw.code}` : `tra ve ${JSON.stringify(String(got).slice(0, 60))}`,
);
check(
  "LO HONG: cai no tra ve la mot nguon anh HOP LE ve mat kieu -- Anh.tsx se ve no",
  threw === null && typeof got === "string" && got.length > 0,
  `kieu=${typeof got} gia tri=${JSON.stringify(String(got).slice(0, 60))}`,
);

// What the bytes behind that source actually are, since `Anh.tsx` hands the
// string to an <Image> and nothing else looks inside it again.
if (typeof got === "string") {
  let payload = null;
  if (got.startsWith("blob:")) {
    const { resolveObjectURL } = await import("node:buffer");
    const b = resolveObjectURL(got);
    payload = b ? { size: b.size, type: b.type, kind: "blob:" } : { kind: "blob: khong giai duoc" };
  } else if (got.startsWith("data:")) {
    const comma = got.indexOf(",");
    payload = {
      kind: "data:",
      prefix: got.slice(0, comma + 1),
      size: got.length - comma - 1,
    };
  }
  console.log(`    nguon Anh.tsx nhan duoc: ${JSON.stringify(payload)}`);
}

// --- the same shape one layer up: does the wall hand out that url? ----------
// A broken photo only reaches a person if a screen asks for it. The wall is
// the screen that does, so this is what turns "a route can answer badly" into
// "a person sees it".
await call("POST", `/contexts/${group}/memories`, {
  actor: an,
  contexts: group,
  body: { image_url: dead.wire.url, caption: "Ky niem co anh chet" },
});
const wall = await call("GET", `/contexts/${group}/memories`, { actor: an, contexts: group });
const listed = (wall.body.memories ?? []).some((m) => m.image_url === dead.wire.url);
check(
  "tuong ky niem VAN liet ke ky niem tro vao anh chet",
  wall.status === 200 && listed,
  `status=${wall.status} n=${(wall.body.memories ?? []).length} co url chet=${listed}`,
);

console.log(`\n${failures.length} dong FAIL`);
for (const f of failures) console.log(`  - ${f}`);
process.exit(failures.length ? 1 : 0);
