/* Read the server's refusal codes out of the server's own source.
 *
 * Not a copy of them. A copy is what the previous test did -- it took
 * `Object.keys(PUBLISH_REFUSALS)` and mocked the server into returning exactly
 * those keys, which proves the table agrees with itself and nothing else. All
 * four keys were wrong at the time and the test was green.
 *
 * Parsing Python from a Node test is ugly, and it is the only thing here that
 * can actually go red when the two sides drift. The alternative -- a shared
 * constants file -- only moves the question: something still has to prove the
 * Python reads it, and the Python is not ours to change.
 *
 * Every failure mode is loud on purpose. A missing file throws, an unparsable
 * block throws, a parser that reads fewer codes than the source contains
 * throws. Silence would be indistinguishable from agreement.
 */
import { readFileSync } from "node:fs";

const COLLECTION_PY = new URL(
  "../../../services/api/app/domain/collection.py",
  import.meta.url,
);
const SERVICE_PY = new URL("../../../services/api/app/api/service.py", import.meta.url);

function read(url, what) {
  try {
    return readFileSync(url, "utf8");
  } catch (cause) {
    throw new Error(
      `Khong doc duoc nguon may chu (${what}): ${url.pathname}. ` +
        `Test nay chi co nghia khi chay trong monorepo.`,
      { cause },
    );
  }
}

/**
 * Slice out one Python block by indentation.
 *
 * Indentation rather than "next line at column 0", because `publish_batch` is
 * a method: the block that follows it is indented four spaces, not zero, and a
 * column-0 scan would swallow the rest of the class.
 *
 * The signature is skipped first. `publish_batch` wraps its parameters across
 * several lines and closes on `) -> BatchPublishResponse:` at the *method's*
 * own indent, so a scan that started at the `def` line would read that closing
 * paren as the end of the block and return an empty body.
 */
function pythonBlock(source, header, where) {
  const lines = source.split("\n");
  const start = lines.findIndex((line) => line.includes(header));
  if (start === -1) {
    throw new Error(`Khong tim thay "${header}" trong ${where} -- may chu da doi ten?`);
  }
  const outer = lines[start].length - lines[start].trimStart().length;
  let signatureEnd = -1;
  for (let i = start; i < lines.length && i < start + 40; i++) {
    if (lines[i].trimEnd().endsWith(":")) {
      signatureEnd = i;
      break;
    }
  }
  if (signatureEnd === -1) {
    throw new Error(`Khong doc het chu ky cua "${header}" trong ${where} -- parser hong.`);
  }
  const body = [];
  for (let i = signatureEnd + 1; i < lines.length; i++) {
    const line = lines[i];
    if (line.trim() === "") {
      body.push(line);
      continue;
    }
    if (line.length - line.trimStart().length <= outer) break;
    body.push(line);
  }
  if (body.length === 0) {
    throw new Error(`Block "${header}" trong ${where} rong -- parser hong.`);
  }
  return body.join("\n");
}

/**
 * The three publish gates, straight out of `unmet_publish_gates()`.
 *
 * The count check is the load-bearing part. If the parser under-reads -- the
 * server switches to a constant, reformats, whatever -- the forward check
 * downstream would demand fewer codes than the server can send, which is
 * exactly the false green this whole file exists to kill. So: every
 * `unmet.append(` in the block must have yielded a literal.
 */
export function publishGateCodes() {
  const source = read(COLLECTION_PY, "collection.py");
  const block = pythonBlock(source, "def unmet_publish_gates(", "collection.py");
  const appends = block.match(/unmet\.append\(/g) ?? [];
  const codes = [...block.matchAll(/unmet\.append\(\s*"([a-z0-9_]+)"\s*\)/g)].map(
    (hit) => hit[1],
  );
  if (appends.length === 0) {
    throw new Error("unmet_publish_gates() khong con append nao -- parser hong.");
  }
  if (codes.length !== appends.length) {
    throw new Error(
      `Doc duoc ${codes.length}/${appends.length} ma trong unmet_publish_gates(). ` +
        `Co append khong phai chuoi literal; parser can cap nhat truoc khi tin ket qua.`,
    );
  }
  return codes;
}

/**
 * Codes `publish_batch()` raises itself, as literals.
 *
 * Two of its `ApiProblem` calls pass a variable (`unmet[0]`, `exc.code`) and
 * are deliberately not matched -- `unmet[0]` is covered above, and the domain
 * transition codes arrive upper-cased and fall through by design.
 *
 * Under-reading here is safe in the direction that matters: this list is used
 * as an allowlist, so a parser that finds too few makes the check stricter,
 * never looser.
 */
export function publishApiCodes() {
  const source = read(SERVICE_PY, "service.py");
  const block = pythonBlock(source, "def publish_batch(", "service.py");
  const codes = [...block.matchAll(/ApiProblem\(\s*\d+\s*,\s*"([a-z0-9_]+)"/g)].map(
    (hit) => hit[1],
  );
  if (codes.length === 0) {
    throw new Error("publish_batch() khong con ApiProblem literal nao -- parser hong.");
  }
  return codes;
}
