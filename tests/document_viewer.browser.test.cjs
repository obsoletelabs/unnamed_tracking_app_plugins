const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { chromium } = require("playwright");
const { PDFDocument, StandardFonts } = require("pdf-lib");
const {
  zipSync,
  strToU8,
} = require("../examples/scoped-document-viewer/frontend/vendor/fflate.min.js");
const root = path.resolve(
  __dirname,
  "../examples/scoped-document-viewer/frontend",
);
// The reviewed builder places these public SDK files in each themed package.
// Source checkouts intentionally keep one SDK copy; serve those exact bytes here.
function assetPath(file) {
  if (file === "appearance.css" || file === "appearance.js")
    return path.resolve(__dirname, "../sdk", `frontend_${file}`);
  return path.resolve(root, file);
}
const csp =
  "default-src 'self'; script-src 'self' https://unpkg.com; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; frame-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'self'";
let server, browser, base;
const id = "c9119470-90d5-477e-97c7-3bd8dba11111";
const gameId = "c9119470-90d5-477e-97c7-3bd8dba22222";
let active;
before(async () => {
  server = http.createServer((req, res) => {
    const url = new URL(req.url, "http://local");
    if (url.pathname === "/") {
      res.setHeader("Content-Type", "text/html");
      res.setHeader(
        "Set-Cookie",
        "session=fixture; HttpOnly; SameSite=Lax; Path=/",
      );
      res.end(
        `<!doctype html><iframe title="Plugin" sandbox="allow-scripts" src="/frontend/index.html?inline=${url.searchParams.get("plain") ? "0" : "1"}" style="width:100%;height:950px;border:0"></iframe>`,
      );
      return;
    }
    if (!(req.headers.cookie || "").includes("session=fixture")) {
      res.writeHead(401);
      res.end("Authentication required");
      return;
    }
    const pathname = decodeURIComponent(
      new URL(req.url, "http://local").pathname,
    );
    const relative = pathname.replace(/^\/frontend\//, "");
    const target = assetPath(relative);
    const sdkAsset = relative === "appearance.css" || relative === "appearance.js";
    if ((!sdkAsset && !target.startsWith(root + path.sep)) || !fs.existsSync(target)) {
      res.writeHead(404);
      res.end();
      return;
    }
    let content = fs.readFileSync(target);
    let policy = csp;
    if (
      target.endsWith("index.html") &&
      url.searchParams.get("inline") === "1"
    ) {
      // Mirrors the documented host response; host tests exercise the actual inliner and scope checks.
      content = content
        .toString()
        .replace(
          /<link rel="stylesheet" href="\.\/([^"]+)"\s*\/>/g,
          (_, file) =>
            `<style nonce="fixture">${fs.readFileSync(assetPath(file), "utf8")}</style>`,
        )
        .replace(
          /<script src="\.\/([^"]+)"(?: defer)?><\/script>/g,
          (_, file) =>
            `<script nonce="fixture">${fs.readFileSync(assetPath(file), "utf8").replace(/<\/script/gi, "<\\/script")}</script>`,
        );
      policy = policy.replace(
        "script-src 'self'",
        "script-src 'nonce-fixture' 'self'",
      );
    }
    res.setHeader("Content-Security-Policy", policy);
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader("Cache-Control", "private, no-store");
    res.setHeader(
      "Content-Type",
      target.endsWith(".js")
        ? "text/javascript"
        : target.endsWith(".css")
          ? "text/css"
          : "text/html",
    );
    res.end(content);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  base = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch({ headless: true });
});
after(async () => {
  await browser?.close();
  await new Promise((resolve) => server?.close(resolve));
});

async function openFixture({
  filename = "abcdefgh_notes.txt",
  bytes = Buffer.from("café <script>literal</script>"),
  mediaType = "text/plain",
  format = "text",
  error = null,
  mutate = null,
  delay = 0,
  empty = false,
  legacyCrypto = false,
  timeout = false,
  context = {},
  plainAssets = false,
  noWait = false,
  maxPreviewMiB = 0,
} = {}) {
  const page = await browser.newPage({
    viewport: { width: 1280, height: 1000 },
    timezoneId: "Australia/Perth",
  });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const requests = [];
  page.on("request", (req) => requests.push(req.url()));
  const item = {
    id,
    game_id: gameId,
    game_title: "Hollow Knight",
    filename,
    media_type: mediaType,
    size_bytes: bytes.length,
    created_at: Date.parse("2026-10-01T04:00:00Z") / 1000,
  };
  const digest = crypto.createHash("sha256").update(bytes).digest("hex");
  const calls = [];
  await page.exposeFunction("bridge", async (envelope) => {
    calls.push(envelope);
    if (envelope.method === "plugin.theme")
      return { api_contract_version: "1.1.0", mode: "light", high_contrast: false, reduce_motion: false, tokens: {} };
    if (envelope.method === "plugin.resize") return {};
    if (envelope.payload.actionId === "load-settings")
      return { value: maxPreviewMiB };
    if (envelope.method === "plugin.save-settings") {
      maxPreviewMiB = envelope.payload.max_preview_mb;
      return {};
    }
    if (envelope.method === "plugin.context") return context;
    if (envelope.method === "plugin.download-document")
      return { download_started: true };
    if (envelope.payload.actionId === "list-documents")
      return { documents: empty ? [] : [item], next_offset: null };
    if (delay) await new Promise((resolve) => setTimeout(resolve, delay));
    if (error) return error;
    const offset = envelope.payload.values.offset;
    let result = {
      document: item,
      encoding: "base64",
      content: bytes.subarray(offset, offset + 24576).toString("base64"),
      format,
      offset,
      next_offset: Math.min(offset + 24576, bytes.length),
      complete: offset + 24576 >= bytes.length,
      content_sha256: digest,
    };
    if (mutate) result = mutate(result);
    return result;
  });
  await page.addInitScript(
    ({ legacyCrypto, timeout }) => {
      if (window === window.top) return;
      if (legacyCrypto) {
        Object.defineProperty(window.crypto, "randomUUID", {
          value: undefined,
        });
        Object.defineProperty(window.crypto, "subtle", { value: undefined });
      }
      if (timeout) {
        const original = window.setTimeout;
        window.setTimeout = (handler, delay, ...args) =>
          original(handler, delay === 30000 ? 100 : delay, ...args);
      }
    },
    { legacyCrypto, timeout },
  );
  await page.addInitScript(() => {
    if (window !== window.top) return;
    window.addEventListener("message", async (event) => {
      if (
        event.data?.type !== "plugin-api-request" ||
        event.source !== document.querySelector("iframe").contentWindow
      )
        return;
      const result = await window.bridge(event.data);
      if (result.ignore) return;
      const response = result.transportError
        ? { error: "Request rejected", status_code: result.transportError }
        : { result };
      event.source.postMessage(
        {
          type: "plugin-api-response",
          requestId: event.data.requestId,
          ...response,
        },
        "*",
      );
    });
  });
  await page.goto(base + (plainAssets ? "/?plain=1" : "/"));
  const frame = page.frameLocator("iframe");
  if (noWait) await frame.locator("body").waitFor();
  else if (context.document_id) await frame.locator("#download").waitFor();
  else if (empty) await frame.locator("#documents .state").waitFor();
  else {
    await frame.locator("#documents button").waitFor();
    await frame.locator("#documents button").click();
  }
  active = { page, frame, errors, requests, calls };
  return active;
}

test("text is literal UTF-8; iframe stays opaque and uses only the declared bridge", async () => {
  const { page, frame, errors, calls } = await openFixture();
  await frame.locator("#viewer pre").waitFor();
  assert.equal(
    await frame.locator("#viewer pre").textContent(),
    "café <script>literal</script>",
  );
  assert.equal(await frame.locator("#viewer script").count(), 0);
  assert.equal(
    await frame
      .locator("#documents small")
      .textContent()
      .then((s) => s.includes("text/plain")),
    true,
  );
  const isolated = await page.frames()[1].evaluate(() => {
    try {
      return window.parent.document.title;
    } catch {
      return "isolated";
    }
  });
  assert.equal(isolated, "isolated");
  assert.equal(
    calls.find((call) => call.payload.actionId === "read-document").payload
      .values.chunk_bytes,
    24576,
  );
  assert.deepEqual(errors, []);
  await page.close();
});

test("HTTP crypto fallback still verifies complete document integrity", async () => {
  const text = "café\n".repeat(12000);
  const { page, frame, errors } = await openFixture({
    legacyCrypto: true,
    bytes: Buffer.from(text),
  });
  await frame.locator("#viewer pre").waitFor();
  assert.equal(await frame.locator("#viewer pre").textContent(), text);
  assert.deepEqual(errors, []);
  await page.close();
});

test("empty library explains how to add documents", async () => {
  const { page, frame } = await openFixture({ empty: true });
  assert.ok(
    (await frame.locator("#documents .state").textContent()).includes(
      "game's Docs tab",
    ),
  );
  assert.equal(await frame.locator("#more").isVisible(), false);
  await page.close();
});

test("a missing bridge response produces a network timeout state", async () => {
  const { page, frame } = await openFixture({
    timeout: true,
    error: { ignore: true },
  });
  await frame.locator("#viewer .error").waitFor();
  assert.ok(
    (await frame.locator("#viewer .error").textContent()).includes("timed out"),
  );
  await page.close();
});

test("HTML sanitizer removes active HTML/SVG/MathML, forms, images, clobbering and links", async () => {
  const html =
    '<h1>Manual</h1><script>parent.pwned=true</script><img src="https://evil.test/leak" onerror="alert(1)"><svg onload="alert(1)"><a xlink:href="javascript:alert(1)">x</a></svg><math><mtext><img src=x onerror=alert(1)></mtext></math><iframe srcdoc="evil"></iframe><form id="documents"><input name="innerHTML"></form><a href="javascript:alert(1)" onclick="alert(1)" style="color:red">unsafe</a><a href="https://evil.test" ping="https://evil.test">external</a><base href="https://evil.test"><meta http-equiv="refresh" content="0;url=https://evil.test">';
  const { page, frame, requests, errors } = await openFixture({
    filename: "page.xhtml",
    bytes: Buffer.from(html),
    format: "html",
  });
  await frame.locator("#viewer h1").waitFor();
  assert.equal(await frame.locator("#viewer h1").textContent(), "Manual");
  assert.equal(
    await frame
      .locator(
        "#viewer script, #viewer img, #viewer svg, #viewer math, #viewer iframe, #viewer form, #viewer input, #viewer meta, #viewer base",
      )
      .count(),
    0,
  );
  assert.equal(
    await frame
      .locator(
        "#viewer [onclick], #viewer [style], #viewer [href], #viewer [ping]",
      )
      .count(),
    0,
  );
  assert.equal(
    requests.some((url) => url.includes("evil.test")),
    false,
  );
  assert.equal(await page.evaluate(() => window.pwned), undefined);
  await frame.locator("#source-toggle").click();
  assert.equal(await frame.locator("#viewer pre").textContent(), html);
  assert.deepEqual(errors, []);
  await page.close();
});

test("PDF renders real pages in sandbox, with page and zoom controls", async () => {
  const pdf = await PDFDocument.create();
  const font = await pdf.embedFont(StandardFonts.Helvetica);
  for (const text of ["Manual page one", "Manual page two"])
    pdf.addPage([400, 500]).drawText(text, { x: 35, y: 400, font, size: 24 });
  const { page, frame, errors, requests } = await openFixture({
    filename: "abcdefgh_manual.pdf",
    bytes: Buffer.from(await pdf.save()),
    mediaType: "application/pdf",
    format: "pdf",
  });
  await frame
    .locator("#page-label")
    .filter({ hasText: "Page 1 of 2" })
    .waitFor({ timeout: 15000 });
  const pixels = await page.frames()[1].evaluate(() => {
    const c = document.querySelector("canvas");
    return c
      .getContext("2d")
      .getImageData(0, 0, c.width, c.height)
      .data.some((value, index) => index % 4 !== 3 && value < 180);
  });
  assert.equal(pixels, true);
  await frame.locator("#next").click();
  await frame
    .locator("#page-label")
    .filter({ hasText: "Page 2 of 2" })
    .waitFor();
  await frame.locator("#zoom").selectOption("1.5");
  assert.equal(
    await frame
      .locator("#viewer iframe, #viewer object, #viewer embed")
      .count(),
    0,
  );
  assert.deepEqual(errors, []);
  assert.equal(
    requests.every((url) => url.startsWith(base)),
    true,
  );
  if (process.env.DOCUMENT_VIEWER_SCREENSHOT)
    await page.screenshot({
      path: process.env.DOCUMENT_VIEWER_SCREENSHOT,
      fullPage: true,
    });
  await page.close();
});

for (const [label, options, expected] of [
  [
    "missing",
    { error: { error: { kind: "missing", message: "Document not found." } } },
    "Document not found",
  ],
  ["unauthorized", { error: { transportError: 403 } }, "Access denied"],
  ["server", { error: { transportError: 500 } }, "Server error"],
  [
    "oversized",
    { error: { error: { kind: "oversized", message: "5 MiB limit" } } },
    "Document too large",
  ],
  [
    "SVG type",
    { mediaType: "image/svg+xml", format: "html" },
    "unsupported content type",
  ],
  ["invalid UTF-8", { bytes: Buffer.from([255]) }, "Only UTF-8"],
  ["binary text", { bytes: Buffer.from([0]) }, "Binary files"],
  [
    "malformed PDF",
    {
      bytes: Buffer.from("%PDF-broken"),
      mediaType: "application/pdf",
      format: "pdf",
    },
    "malformed or password protected",
  ],
  [
    "unexpected encoding",
    { mutate: (r) => ({ ...r, encoding: "utf-8" }) },
    "malformed",
  ],
  ["bad base64", { mutate: (r) => ({ ...r, content: "!!!!" }) }, "malformed"],
  [
    "wrong document ID",
    { mutate: (r) => ({ ...r, document: { ...r.document, id: "other" } }) },
    "malformed",
  ],
  [
    "bad range",
    { mutate: (r) => ({ ...r, next_offset: 9999 }) },
    "invalid document chunk",
  ],
  [
    "integrity mismatch",
    { mutate: (r) => ({ ...r, content_sha256: "0".repeat(64) }) },
    "integrity check failed",
  ],
])
  test(label + " has an explicit error state", async () => {
    const { page, frame, errors } = await openFixture(options);
    await frame.locator("#viewer .error").waitFor({ timeout: 15000 });
    assert.ok(
      (await frame.locator("#viewer .error").textContent()).includes(expected),
    );
    assert.deepEqual(errors, []);
    await page.close();
  });

test("multiple chunks preserve UTF-8 boundaries; replacement is rejected", async () => {
  const text = "é".repeat(30000);
  const { page, frame, calls } = await openFixture({
    bytes: Buffer.from(text),
  });
  await frame.locator("#viewer pre").waitFor();
  assert.equal(await frame.locator("#viewer pre").textContent(), text);
  assert.equal(
    calls.filter((c) => c.payload.actionId === "read-document").length,
    3,
  );
  await page.close();
  const next = await openFixture({
    bytes: Buffer.from(text),
    mutate: (r) => (r.offset ? { ...r, content_sha256: "f".repeat(64) } : r),
  });
  await next.frame.locator("#viewer .error").waitFor();
  assert.ok(
    (await next.frame.locator("#viewer .error").textContent()).includes(
      "Document changed",
    ),
  );
  await next.page.close();
});

test("refresh cancels a pending open and does not render a stale response", async () => {
  const { page, frame } = await openFixture({ delay: 300 });
  await frame.locator("#refresh").click();
  await frame.locator("#documents button").waitFor();
  await page.waitForTimeout(400);
  assert.equal(await frame.locator("#viewer pre").count(), 0);
  assert.equal(
    await frame.locator("#document-title").textContent(),
    "Your game documents",
  );
  await page.close();
});

test("authenticated opaque sandbox reproduces missing CSS; inline package assets restore it", async () => {
  const broken = await openFixture({ plainAssets: true, noWait: true });
  await broken.page.waitForTimeout(150);
  assert.notEqual(
    await broken.frame
      .locator("body")
      .evaluate((node) => getComputedStyle(node).margin),
    "0px",
  );
  assert.equal(await broken.frame.locator("#documents button").count(), 0);
  await broken.page.close();
  const fixed = await openFixture();
  await fixed.frame.locator("#viewer pre").waitFor();
  assert.equal(
    await fixed.frame
      .locator("body")
      .evaluate((node) => getComputedStyle(node).margin),
    "0px",
  );
  assert.equal(
    await fixed.frame
      .locator(".document-panel")
      .evaluate((node) => getComputedStyle(node).borderTopStyle),
    "solid",
  );
  assert.equal(
    fixed.requests.some((url) => url.endsWith(".css") || url.endsWith(".js")),
    false,
  );
  assert.deepEqual(fixed.errors, []);
  await fixed.page.close();
});

test("game document context opens directly without listing; download uses only the host bridge", async () => {
  const { page, frame, calls } = await openFixture({
    context: { document_id: id, game_id: gameId },
  });
  await frame.locator("#viewer pre").waitFor();
  assert.equal(
    calls.some((call) => call.payload.actionId === "list-documents"),
    false,
  );
  assert.equal(
    await frame
      .locator("body")
      .evaluate((node) => node.classList.contains("single-document")),
    true,
  );
  assert.equal(
    await frame.locator("#document-title").textContent(),
    "notes.txt",
  );
  await frame.locator("#download").click();
  await frame
    .locator("#status")
    .filter({ hasText: "Original download started" })
    .waitFor();
  assert.deepEqual(
    calls.find((call) => call.method === "plugin.download-document").payload,
    { document_id: id },
  );
  await frame.locator("#refresh").click();
  await frame.locator("#documents button").waitFor();
  assert.equal(
    await frame
      .locator("body")
      .evaluate((node) => node.classList.contains("single-document")),
    false,
  );
  await page.close();
});

const W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
const P = "http://schemas.openxmlformats.org/presentationml/2006/main";
const A = "http://schemas.openxmlformats.org/drawingml/2006/main";
const R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
const O = "urn:oasis:names:tc:opendocument:xmlns:office:1.0";
const T = "urn:oasis:names:tc:opendocument:xmlns:text:1.0";
const D = "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0";
function officeFixture(format, additions = {}) {
  let files = { "[Content_Types].xml": "<Types/>" };
  if (format === "docx")
    files["word/document.xml"] =
      `<w:document xmlns:w="${W}"><w:body><w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Manual heading</w:t></w:r></w:p><w:p><w:r><w:rPr><w:b/></w:rPr><w:t>café &lt;script&gt;literal&lt;/script&gt;</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Table cell</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>`;
  else if (format === "pptx") {
    files["ppt/presentation.xml"] =
      `<p:presentation xmlns:p="${P}" xmlns:r="${R}"><p:sldIdLst><p:sldId id="1" r:id="second"/><p:sldId id="2" r:id="first"/></p:sldIdLst></p:presentation>`;
    files["ppt/_rels/presentation.xml.rels"] =
      '<Relationships><Relationship Id="first" Target="slides/slide1.xml"/><Relationship Id="second" Target="slides/slide2.xml"/></Relationships>';
    for (const number of [1, 2])
      files[`ppt/slides/slide${number}.xml`] =
        `<p:sld xmlns:p="${P}" xmlns:a="${A}"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Slide text ${number}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>`;
  } else {
    files.mimetype =
      format === "odt"
        ? "application/vnd.oasis.opendocument.text"
        : "application/vnd.oasis.opendocument.presentation";
    files["content.xml"] =
      `<office:document-content xmlns:office="${O}" xmlns:text="${T}" xmlns:draw="${D}"><office:body>${format === "odt" ? "<office:text><text:h>OpenDocument heading</text:h><text:p>café &lt;script&gt;literal&lt;/script&gt;</text:p></office:text>" : "<office:presentation><draw:page><text:p>OpenDocument slide one</text:p></draw:page><draw:page><text:p>OpenDocument slide two</text:p></draw:page></office:presentation>"}</office:body></office:document-content>`;
  }
  files = { ...files, ...additions };
  return Buffer.from(
    zipSync(
      Object.fromEntries(
        Object.entries(files).map(([name, text]) => [
          name,
          typeof text === "string" ? strToU8(text) : text,
        ]),
      ),
      { level: 0 },
    ),
  );
}
const OFFICE_TYPES = {
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  odt: "application/vnd.oasis.opendocument.text",
  odp: "application/vnd.oasis.opendocument.presentation",
};
for (const format of ["docx", "pptx", "odt", "odp"])
  test(`${format} displays a local reading preview safely`, async () => {
    const { page, frame, errors, requests } = await openFixture({
      context: { document_id: id, game_id: gameId },
      filename: `abcdefgh_manual.${format}`,
      bytes: officeFixture(format),
      format,
      mediaType: OFFICE_TYPES[format],
    });
    await frame.locator(".office-document").waitFor();
    const text = await frame.locator(".office-document").textContent();
    if (format === "docx") {
      assert.ok(
        text.includes("Manual heading") &&
          text.includes("café <script>literal</script>") &&
          text.includes("Table cell"),
      );
      assert.equal(await frame.locator(".office-document table td").count(), 1);
      assert.equal(await frame.locator(".office-bold").count(), 1);
      if (process.env.OFFICE_VIEWER_SCREENSHOT)
        await page.screenshot({ path: process.env.OFFICE_VIEWER_SCREENSHOT });
    } else if (format === "odt")
      assert.ok(
        text.includes("OpenDocument heading") &&
          text.includes("café <script>literal</script>"),
      );
    else {
      assert.equal(await frame.locator(".office-slide").count(), 2);
      if (format === "pptx")
        assert.ok(text.indexOf("Slide text 2") < text.indexOf("Slide text 1"));
    }
    assert.equal(
      await frame
        .locator(".office-document script, .office-document iframe")
        .count(),
      0,
    );
    assert.equal(
      requests.some((url) => !url.startsWith(base)),
      false,
    );
    assert.deepEqual(errors, []);
    await page.close();
  });

for (const [label, addition] of [
  ["traversal", { "../escape.xml": "<evil/>" }],
  ["macros", { "word/vbaProject.bin": "macro" }],
  [
    "DTD",
    {
      "word/document.xml":
        '<!DOCTYPE x [<!ENTITY evil SYSTEM "https://evil.test/x">]><x>&evil;</x>',
    },
  ],
  ["malformed XML", { "word/document.xml": "<broken" }],
  ["OLE objects", { "word/embeddings/oleObject1.bin": "object" }],
  [
    "macro-enabled embedded packages",
    { "word/embeddings/Microsoft_Excel_Macro-Enabled.xlsm": "object" },
  ],
])
  test(`office ${label} is rejected without active rendering`, async () => {
    const { page, frame, requests } = await openFixture({
      filename: "manual.docx",
      bytes: officeFixture("docx", addition),
      format: "docx",
      mediaType: OFFICE_TYPES.docx,
    });

    await frame.locator("#viewer .error").waitFor();
    assert.equal(await frame.locator(".office-document").count(), 0);
    assert.equal(
      requests.some((url) => !url.startsWith(base)),
      false,
    );
    await page.close();
  });

test("Word embeds bounded raster images and never fetches external relationships", async () => {
  const png = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jXioAAAAASUVORK5CYII=",
    "base64",
  );
  const bytes = officeFixture("docx", {
    "word/document.xml": `<w:document xmlns:w="${W}" xmlns:a="${A}" xmlns:r="${R}"><w:body><w:p><w:r><w:t>Picture</w:t></w:r><a:blip r:embed="local"/><a:blip r:embed="remote"/></w:p></w:body></w:document>`,
    "word/_rels/document.xml.rels":
      '<Relationships><Relationship Id="local" Target="media/image.png"/><Relationship Id="remote" Target="https://evil.test/private" TargetMode="External"/></Relationships>',
    "word/media/image.png": png,
  });
  const { page, frame, requests } = await openFixture({
    filename: "manual.docx",
    bytes,
    format: "docx",
    mediaType: OFFICE_TYPES.docx,
  });
  await frame.locator(".office-document img").waitFor();
  assert.equal(await frame.locator(".office-document img").count(), 1);
  assert.ok(
    (
      await frame.locator(".office-document img").getAttribute("src")
    ).startsWith("data:image/png;base64,"),
  );
  assert.equal(
    requests.some((url) => url.startsWith("https://evil.test")),
    false,
  );
  await page.close();
});

test("a document from the wrong game context is rejected before rendering", async () => {
  const { page, frame } = await openFixture({
    context: { document_id: id, game_id: "other-game" },
  });
  await frame.locator("#viewer .error").waitFor();
  assert.equal(await frame.locator("#viewer pre").count(), 0);
  await page.close();
});

test("unsupported preview retains an original download in the direct reader", async () => {
  const { page, frame, calls } = await openFixture({
    context: { document_id: id, game_id: gameId },
    error: { error: { kind: "unsupported", message: "Unsupported preview" } },
  });
  await frame.locator("#viewer .error").waitFor();
  await frame.locator("#download").click();
  await frame
    .locator("#status")
    .filter({ hasText: "Original download started" })
    .waitFor();
  assert.equal(
    calls.find((call) => call.method === "plugin.download-document").payload
      .document_id,
    id,
  );
  await page.close();
});

test("configured finite preview limit reaches every document chunk", async () => {
  const { page, frame, calls } = await openFixture({
    bytes: Buffer.alloc(50000, 97),
    maxPreviewMiB: 2,
  });
  await frame.locator("#viewer pre").waitFor();
  const reads = calls.filter((call) => call.payload.actionId === "read-document");
  assert.ok(reads.length > 1);
  assert.ok(reads.every((call) => call.payload.values.max_bytes === 2 * 1024 * 1024));
  await frame.locator("#settings-button").click();
  await frame.locator("#max-preview-mb").fill("0");
  await frame.locator("#save-settings").click();
  await frame.locator("#settings-status").filter({ hasText: "unlimited" }).waitFor();
  assert.deepEqual(calls.find((call) => call.method === "plugin.save-settings").payload, { max_preview_mb: 0 });
  await page.close();
});

test("unlimited previews render text beyond the legacy five MiB ceiling", async () => {
  const bytes = Buffer.alloc(5 * 1024 * 1024 + 1, 97);
  const { page, frame, calls } = await openFixture({ bytes, maxPreviewMiB: 0 });
  await frame.locator("#viewer pre").waitFor();
  assert.equal((await frame.locator("#viewer pre").textContent()).length, bytes.length);
  const reads = calls.filter((call) => call.payload.actionId === "read-document");
  assert.ok(reads.length > 200);
  assert.ok(reads.every((call) => call.payload.values.max_bytes === 0));
  await page.close();
});

for (const format of ["docx", "pptx"])
  test(`${format} charts keep their embedded workbook and show a placeholder`, async () => {
    const C = "http://schemas.openxmlformats.org/drawingml/2006/chart";
    const chart = `<a:graphic xmlns:a="${A}"><a:graphicData><c:chart xmlns:c="${C}" r:id="chart"/></a:graphicData></a:graphic>`;
    const additions =
      format === "docx"
        ? {
            "word/document.xml": `<w:document xmlns:w="${W}" xmlns:r="${R}"><w:body><w:p><w:r><w:t>Sales</w:t></w:r><w:r><w:drawing>${chart}</w:drawing></w:r></w:p></w:body></w:document>`,
            "word/charts/chart1.xml": "<chartSpace/>",
            "word/embeddings/Microsoft_Excel_Worksheet.xlsx": "workbook",
          }
        : {
            "ppt/slides/slide1.xml": `<p:sld xmlns:p="${P}" xmlns:a="${A}" xmlns:r="${R}"><p:cSld><p:spTree><p:graphicFrame>${chart}</p:graphicFrame></p:spTree></p:cSld></p:sld>`,
            "ppt/charts/chart1.xml": "<chartSpace/>",
            "ppt/embeddings/Microsoft_Excel_Worksheet.xlsx": "workbook",
          };
    const { page, frame, errors } = await openFixture({
      filename: `charts.${format}`,
      bytes: officeFixture(format, additions),
      format,
      mediaType: OFFICE_TYPES[format],
    });
    await frame.locator(".office-document").waitFor();
    assert.equal(await frame.locator(".office-object").count(), 1);
    assert.match(
      await frame.locator(".office-object").textContent(),
      /Chart or embedded object not shown/,
    );
    assert.deepEqual(errors, []);
    await page.close();
  });
