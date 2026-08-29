import { defineConfig, devices } from "@playwright/test";

/** Demo rehearsal harness (rd-qa-05).
 *
 * Points at a web export of apps/mobile pinned to the rehearsal API on :8399.
 * Phone-first: the demo is given on a phone, so the default project is a real
 * 390x844 viewport, not a cropped desktop window.
 */
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 150_000,
  reporter: [["list"], ["json", { outputFile: "results.json" }]],
  use: {
    baseURL: process.env.WEB_URL ?? "http://127.0.0.1:4599",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "phone", use: { ...devices["Pixel 7"] } },
  ],
});
