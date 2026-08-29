// Tiny static server with SPA fallback, used only by the rd-qa-16 walk.
import http from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";

const ROOT = process.argv[2];
const PORT = Number(process.argv[3] ?? 4316);
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".ico": "image/x-icon" };

export function serve(root = ROOT, port = PORT) {
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, "http://x");
    let file = path.join(root, decodeURIComponent(url.pathname));
    try {
      const body = await readFile(file);
      res.writeHead(200, { "content-type": TYPES[path.extname(file)] ?? "application/octet-stream" });
      res.end(body);
    } catch {
      const body = await readFile(path.join(root, "index.html"));
      res.writeHead(200, { "content-type": "text/html" });
      res.end(body);
    }
  });
  return new Promise((ok) => server.listen(port, () => ok(server)));
}
