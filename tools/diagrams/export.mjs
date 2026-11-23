// Render .excalidraw files to PNG, light by default, using
// Excalidraw's own exporter in headless Chrome so the result matches the app.
//
//   node export.mjs OUT_DIR drawing.excalidraw [more.excalidraw ...]
//
// Writes NAME.png per drawing, plus NAME-dark.png with DARK=1. The dark version
// is Excalidraw's inverted look, which leaves coloured fills hard to read. Set
// SCALE (default 2) for the pixel density and PADDING (default 32) for the
// margin around the drawing.

import { readFile, writeFile, mkdir } from "node:fs/promises";
import { createServer } from "node:http";
import { basename, dirname, extname, join } from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const HERE = dirname(fileURLToPath(import.meta.url));
const CHROME = process.env.CHROME || "/usr/bin/google-chrome";
const SCALE = Number(process.env.SCALE || 2);
const PADDING = Number(process.env.PADDING || 32);
const MODES = process.env.DARK === "1" ? [false, true] : [false];

const [outDir, ...inputs] = process.argv.slice(2);
if (!outDir || inputs.length === 0) {
  console.error("usage: node export.mjs OUT_DIR drawing.excalidraw [...]");
  process.exit(1);
}

const TYPES = { ".js": "text/javascript", ".woff2": "font/woff2", ".html": "text/html" };

const PAGE = `<!doctype html><meta charset="utf-8"><body>
<script>window.EXCALIDRAW_ASSET_PATH = "/node_modules/@excalidraw/excalidraw/dist/";</script>
<script src="/node_modules/react/umd/react.production.min.js"></script>
<script src="/node_modules/react-dom/umd/react-dom.production.min.js"></script>
<script src="/node_modules/@excalidraw/excalidraw/dist/excalidraw.production.min.js"></script>
</body>`;

// Chrome will not load fonts for a file:// page, so everything is served from
// a throwaway local server instead.
const server = createServer(async (request, response) => {
  const path = decodeURIComponent(new URL(request.url, "http://x").pathname);
  if (path === "/") {
    response.writeHead(200, { "content-type": "text/html" }).end(PAGE);
    return;
  }
  try {
    const body = await readFile(join(HERE, path));
    response.writeHead(200, { "content-type": TYPES[extname(path)] || "application/octet-stream" });
    response.end(body);
  } catch {
    response.writeHead(404).end();
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const origin = `http://127.0.0.1:${server.address().port}/`;

const browser = await puppeteer.launch({ executablePath: CHROME, headless: true });
try {
  const page = await browser.newPage();
  page.on("pageerror", (error) => console.error("page:", error.message));
  await page.goto(origin, { waitUntil: "networkidle0" });
  await page.waitForFunction(() => window.ExcalidrawLib?.exportToBlob);

  await mkdir(outDir, { recursive: true });
  for (const input of inputs) {
    const scene = JSON.parse(await readFile(input, "utf8"));
    const name = basename(input, extname(input));
    for (const dark of MODES) {
      const dataUrl = await page.evaluate(
        async (scene, dark, scale, padding) => {
          const { exportToBlob } = window.ExcalidrawLib;
          const elements = scene.elements.filter((element) => !element.isDeleted);
          // The exporter draws on a canvas, so the hand-drawn font has to be
          // loaded before it runs or the text falls back to a system font.
          await Promise.all(
            ["Virgil", "Cascadia", "Assistant"].map((family) =>
              document.fonts.load(`20px ${family}`).catch(() => null),
            ),
          );
          const blob = await exportToBlob({
            elements,
            files: scene.files || {},
            appState: {
              ...scene.appState,
              exportBackground: true,
              exportWithDarkMode: dark,
              // Dark mode inverts the whole picture, background included, so
              // the background stays white here and comes out dark.
              viewBackgroundColor: "#ffffff",
            },
            exportPadding: padding,
            getDimensions: (width, height) => ({ width: width * scale, height: height * scale, scale }),
          });
          return await new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.readAsDataURL(blob);
          });
        },
        scene,
        dark,
        SCALE,
        PADDING,
      );
      const out = join(outDir, `${name}${dark ? "-dark" : ""}.png`);
      await writeFile(out, Buffer.from(dataUrl.split(",")[1], "base64"));
      console.log("wrote", out);
    }
  }
} finally {
  await browser.close();
  server.close();
}
