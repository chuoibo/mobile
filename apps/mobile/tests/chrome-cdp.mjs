/* A headless Chrome, driven over a pipe, with no dependencies.
 *
 * Not a test file. `tests/*.test.mjs` is what the gate runs; this is the
 * helper those files import.
 *
 * Three of the shell's defects are things only a browser can see: how wide the
 * document scrolls, which ARIA attributes react-native-web actually emits, and
 * where the Tab key goes. `tsc` sees none of it and `expo export` succeeding
 * says only that a bundle was written. So there has to be a real render in the
 * loop, and the question is what drives it.
 *
 * Not puppeteer or playwright: neither is a dependency of this app, both pull
 * a browser download into `npm ci`, and adding ~300 MB to the mobile CI job to
 * assert three numbers is a bad trade. What is actually needed is small.
 * Chrome speaks the DevTools Protocol over a plain pipe -- `--remote-debugging-pipe`,
 * newline-free JSON delimited by NUL on fd 3 and fd 4 -- which needs nothing
 * but `child_process`. That also keeps this runnable on Node 20, which is what
 * CI pins; the WebSocket transport would have needed Node 22's global
 * `WebSocket` and would have passed locally and died in CI.
 *
 * The page is served from an ephemeral port (`listen(0)`), which is not a
 * detail. A fixed port is how a gate ends up measuring some other worktree's
 * dev server and reporting on a page this commit never built.
 */
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { existsSync, readdirSync, readFileSync, rmSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { join, normalize } from "node:path";

/* ------------------------------------------------------------- the binary --- */

const SYSTEM_NAMES = [
  "/usr/bin/google-chrome",
  "/usr/bin/google-chrome-stable",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
  "/snap/bin/chromium",
];

/**
 * Find a Chrome. Returns null rather than throwing: the caller decides whether
 * a missing browser is a skip or a failure, and that decision belongs to the
 * gate, not here.
 *
 * The Playwright cache is searched because that is where a browser most often
 * already exists on these machines -- the detector's own puppeteer has no
 * bundled Chromium and reads the same directory. A scan that finds no browser
 * returns `[]` and exit 0, which looks exactly like a clean scan; that is the
 * failure this function exists to make impossible to hit silently.
 */
export function findChrome() {
  if (process.env.CHROME_BIN) {
    return existsSync(process.env.CHROME_BIN) ? process.env.CHROME_BIN : null;
  }

  const cache = join(homedir(), ".cache", "ms-playwright");
  if (existsSync(cache)) {
    // Newest build number first, so a stale 2023 build is not preferred over
    // the one that was installed this week.
    const dirs = readdirSync(cache)
      .filter((d) => d.startsWith("chromium"))
      .sort((a, b) => buildNumber(b) - buildNumber(a));
    for (const dir of dirs) {
      for (const rel of [
        ["chrome-linux", "chrome"],
        ["chrome-linux64", "chrome"],
        ["chrome-linux", "headless_shell"],
        ["chrome-mac", "Chromium.app", "Contents", "MacOS", "Chromium"],
      ]) {
        const bin = join(cache, dir, ...rel);
        if (existsSync(bin)) return bin;
      }
    }
  }

  for (const bin of SYSTEM_NAMES) if (existsSync(bin)) return bin;
  return null;
}

function buildNumber(dir) {
  const m = /-(\d+)$/.exec(dir);
  return m ? Number(m[1]) : 0;
}

/* -------------------------------------------------------------- the server --- */

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".ico": "image/x-icon",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".ttf": "font/ttf",
};

/** Serve one exported build on a port nobody else can be holding. */
export async function serve(root) {
  const server = createServer((req, res) => {
    const path = decodeURIComponent(new URL(req.url, "http://x").pathname);
    let file = join(root, normalize(path).replace(/^(\.\.[/\\])+/, ""));
    if (!existsSync(file) || statSync(file).isDirectory()) file = join(root, "index.html");
    if (!existsSync(file)) {
      res.writeHead(404).end("no");
      return;
    }
    const ext = file.slice(file.lastIndexOf("."));
    res.writeHead(200, { "content-type": MIME[ext] ?? "application/octet-stream" });
    res.end(readFileSync(file));
  });
  await new Promise((ok) => server.listen(0, "127.0.0.1", ok));
  const { port } = server.address();
  return { url: `http://127.0.0.1:${port}/`, close: () => new Promise((ok) => server.close(ok)) };
}

/* --------------------------------------------------------------- the pipe --- */

/**
 * Measure where a press should land, running inside the page.
 *
 * Module scope, not inline, because `evaluate` stringifies whatever it is
 * given: a closure would arrive in the browser with its free variables gone
 * and throw `ReferenceError` on a line nobody is looking at. Both `clickLabel`
 * and `clickChu` hand it to `evaluate`, so the scroll-then-measure rule below
 * is written once.
 *
 * `kieu` is `"nhan"` (exact `aria-label`) or `"chu"` (exact visible words of a
 * button, whitespace collapsed). Returns `null` when nothing matched and
 * `{ trung }` when more than one did -- the caller turns both into an error
 * naming itself, rather than pressing nothing and failing three steps later.
 */
function doHopBam(kieu, khoa) {
  const els =
    kieu === "nhan"
      ? [...document.querySelectorAll("[aria-label]")].filter(
          (e) => e.getAttribute("aria-label") === khoa,
        )
      : [...document.querySelectorAll("button, [role='button']")].filter(
          (e) => e.textContent.replace(/\s+/g, " ").trim() === khoa,
        );
  if (els.length === 0) return null;
  if (els.length > 1) return { trung: els.length };
  const el = els[0];
  // Scroll it into view BEFORE measuring. `Input.dispatchMouseEvent`
  // takes viewport coordinates, so a control below the fold is clicked
  // at a y the window does not contain and the press lands on nothing --
  // no error, no handler, an entirely silent no-op. Measured here: the
  // comment composer's "Gửi" button sits at y 837-881 on a 390x844
  // screen, `elementFromPoint` at its centre returned null, and the test
  // failed much later at "the comment never appeared" while pointing at
  // the product rather than at this function.
  //
  // `nearest` rather than `center`: it scrolls only when it has to, so
  // tests that assert on scroll position are not moved out from under.
  el.scrollIntoView({ block: "nearest", inline: "nearest" });
  const r = el.getBoundingClientRect();
  const x = r.left + r.width / 2;
  const y = r.top + r.height / 2;
  return { x, y, trongMan: x >= 0 && x <= innerWidth && y >= 0 && y <= innerHeight };
}

/**
 * Launch Chrome and attach to one page.
 *
 * `--headless=new` is the mode that renders like the real browser; the old
 * headless had its own layout quirks, which would make every number below a
 * measurement of the wrong thing.
 */
export async function launch(bin) {
  // Named here rather than inline in the args so `close()` can delete it. A
  // profile dir is ~4 MB and every test file makes one; left behind they had
  // reached 2421 dirs / 9.9 GB of /tmp on this machine, which is a slow way to
  // take down every lane sharing it.
  const profileDir = join(process.env.TMPDIR ?? "/tmp", `cdp-${process.pid}`);
  const chrome = spawn(
    bin,
    [
      "--headless=new",
      "--remote-debugging-pipe",
      "--no-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      "--force-device-scale-factor=1",
      "--no-first-run",
      "--no-default-browser-check",
      "--user-data-dir=" + profileDir,
      "about:blank",
    ],
    { stdio: ["ignore", "ignore", "pipe", "pipe", "pipe"] },
  );

  const write = chrome.stdio[3];
  const read = chrome.stdio[4];
  const pending = new Map();
  let nextId = 0;
  let buffer = Buffer.alloc(0);
  let stderr = "";

  chrome.stdio[2].on("data", (d) => {
    stderr += d.toString();
  });

  read.on("data", (chunk) => {
    buffer = Buffer.concat([buffer, chunk]);
    let end;
    // NUL is the frame delimiter on this transport, not a newline.
    while ((end = buffer.indexOf(0)) !== -1) {
      const message = JSON.parse(buffer.subarray(0, end).toString());
      buffer = buffer.subarray(end + 1);
      const waiter = pending.get(message.id);
      if (!waiter) continue;
      pending.delete(message.id);
      if (message.error) waiter.reject(new Error(`${message.error.message} (${waiter.method})`));
      else waiter.resolve(message.result);
    }
  });

  function send(method, params = {}, sessionId) {
    const id = ++nextId;
    const frame = JSON.stringify(sessionId ? { id, method, params, sessionId } : { id, method, params });
    return new Promise((resolve, reject) => {
      pending.set(id, { resolve, reject, method });
      write.write(frame + "\0");
    });
  }

  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
  const call = (method, params) => send(method, params, sessionId);

  await call("Page.enable");
  await call("Runtime.enable");
  await call("Page.bringToFront");

  return {
    call,
    stderr: () => stderr,

    /** Set the viewport. Every measurement below is width-dependent. */
    async viewport(width, height) {
      await call("Emulation.setDeviceMetricsOverride", {
        width,
        height,
        deviceScaleFactor: 1,
        mobile: false,
      });
    },

    /** Run an arrow function in the page and get its value back. */
    async evaluate(fn, ...args) {
      const expression = `(${fn.toString()})(${args.map((a) => JSON.stringify(a)).join(",")})`;
      const result = await call("Runtime.evaluate", {
        expression,
        returnByValue: true,
        awaitPromise: true,
      });
      if (result.exceptionDetails) {
        throw new Error("page threw: " + JSON.stringify(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text));
      }
      return result.result.value;
    },

    /** Navigate, then wait until the app has actually put something on screen.
     *  `load` firing only means the bundle arrived, not that React ran.
     *
     *  `readyFn` runs inside the page, so it cannot see anything from this
     *  module's scope -- pass what it needs as `args`. A predicate that closes
     *  over a Node constant throws `ReferenceError` on every poll and times
     *  out looking exactly like a page that never rendered. */
    async goto(url, readyFn, ...args) {
      await call("Page.navigate", { url });
      await this.waitFor(
        readyFn ?? (() => document.readyState === "complete"),
        { label: "trang render xong" },
        ...args,
      );
    },

    /** Poll a predicate. Deliberately not a fixed sleep: a timeout tuned on
     *  this machine is a flake on a slower one. */
    async waitFor(fn, { timeout = 15000, label = "condition" } = {}, ...args) {
      const deadline = Date.now() + timeout;
      for (;;) {
        let ok = false;
        try {
          ok = await this.evaluate(fn, ...args);
        } catch {
          ok = false;
        }
        if (ok) return;
        if (Date.now() > deadline) throw new Error(`timed out waiting for ${label}`);
        await new Promise((r) => setTimeout(r, 60));
      }
    },

    /** A real mouse press at an element's centre.
     *
     *  Not `element.click()`. react-native-web's `Pressable` listens on
     *  pointer events, so a synthetic click can miss `onPress` entirely and
     *  the gate would report a menu that never opened as a menu with nothing
     *  in it. */
    async clickLabel(label) {
      await this.bamVaoHop(await this.evaluate(doHopBam, "nhan", label), `aria-label ${JSON.stringify(label)}`);
    },

    /** The same real press, on the control whose visible words are `chu`.
     *
     *  `Button` in `ui/Kit.tsx` sets `accessibilityRole="button"` and no
     *  `accessibilityLabel`: its name comes from the `<Text>` inside it, so
     *  react-native-web emits `role="button"` with no `aria-label` attribute
     *  at all and `clickLabel` cannot find it. Most buttons in this app are
     *  that one -- pressing them by their words is what a person does anyway.
     *
     *  Exact match after whitespace collapse, and two matches is an error
     *  rather than "take the first". A test that silently pressed a different
     *  control with the same words would report on a screen nobody asked for. */
    async clickChu(chu) {
      await this.bamVaoHop(await this.evaluate(doHopBam, "chu", chu), `chữ ${JSON.stringify(chu)}`);
    },

    /** Dispatch at a box `doHopBam` measured, or say why it refused to.
     *
     *  Separate from the two finders so "scroll it in, take the centre, refuse
     *  if it is still off screen" has one spelling. Both finders can return
     *  `null` (nothing matched) or `{ trung: n }` (ambiguous); neither is a
     *  press, and both have to name themselves rather than fail later at
     *  "the screen never changed". */
    async bamVaoHop(box, moTa) {
      if (!box) throw new Error(`no element with ${moTa}`);
      if (box.trung !== undefined) {
        throw new Error(`${box.trung} elements match ${moTa}; refusing to guess which one to press`);
      }
      // Refusing to dispatch is the point. Clicking into empty space and
      // returning normally is how a dead control passes for a live one.
      if (!box.trongMan) {
        throw new Error(
          `element with ${moTa} is outside the viewport even ` +
            `after scrolling (centre ${Math.round(box.x)},${Math.round(box.y)}); a click there hits nothing`,
        );
      }
      const common = { x: box.x, y: box.y, button: "left", clickCount: 1, buttons: 1 };
      await call("Input.dispatchMouseEvent", { type: "mouseMoved", ...common, buttons: 0 });
      await call("Input.dispatchMouseEvent", { type: "mousePressed", ...common });
      await call("Input.dispatchMouseEvent", { type: "mouseReleased", ...common });
    },

    /** Type into the control carrying this `aria-label`, the way a person does.
     *
     *  Not `el.value = text`. A react-native-web `TextInput` is controlled, so
     *  React overwrites a directly assigned value on its very next render and
     *  the component never sees the keystrokes -- a test written that way
     *  asserts on text that only ever existed in the DOM. `Input.insertText`
     *  goes in through the same path the keyboard does, so `onChangeText` runs.
     *
     *  The click first is what focuses it; `insertText` goes to whatever has
     *  focus, and with nothing focused it silently goes nowhere. */
    async typeInto(label, text) {
      await this.clickLabel(label);
      await call("Input.insertText", { text });
    },

    /** Press Tab once and let focus settle. */
    async pressTab() {
      const key = { windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9, key: "Tab", code: "Tab" };
      await call("Input.dispatchKeyEvent", { type: "rawKeyDown", ...key });
      await call("Input.dispatchKeyEvent", { type: "keyUp", ...key });
    },

    async close() {
      try {
        await send("Browser.close");
      } catch {
        chrome.kill("SIGKILL");
      }
      await new Promise((ok) => chrome.once("exit", ok));
      // Only after the process is gone: deleting the profile under a live
      // Chrome makes it rewrite parts of it on the way out.
      try {
        rmSync(profileDir, { recursive: true, force: true });
      } catch {
        /* A profile we cannot delete is not worth failing a passing test over. */
      }
    },
  };
}
