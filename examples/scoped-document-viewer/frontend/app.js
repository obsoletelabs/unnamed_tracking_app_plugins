const documents = document.querySelector("#documents");
const viewer = document.querySelector("#viewer");
const status = document.querySelector("#status");
const heading = document.querySelector("#document-title");
const metadata = document.querySelector("#document-meta");
const refreshButton = document.querySelector("#refresh");
const moreButton = document.querySelector("#more");
const downloadButton = document.querySelector("#download");
const settingsButton = document.querySelector("#settings-button");
const settingsPanel = document.querySelector("#settings-panel");
const maxPreviewInput = document.querySelector("#max-preview-mb");
const saveSettingsButton = document.querySelector("#save-settings");
const cancelSettingsButton = document.querySelector("#cancel-settings");
const settingsStatus = document.querySelector("#settings-status");
let currentDocument = null;
let generation = 0;
let controller = null;
let pdfTask = null;
let renderTask = null;
let nextOffset = 0;
let listGeneration = 0;
const MAX_BYTES = Number.MAX_SAFE_INTEGER;
const CHUNK_BYTES = 24 * 1024;
let maxPreviewMiB = 0;

class DocumentError extends Error {
  constructor(kind, message) {
    super(message);
    this.kind = kind;
  }
}

function transportError(statusCode) {
  if (statusCode === 401 || statusCode === 403)
    return new DocumentError(
      "forbidden",
      "You are not authorized to view this document. Check the plugin permissions.",
    );
  if (statusCode === 404)
    return new DocumentError("missing", "Document not found.");
  if (statusCode >= 500)
    return new DocumentError(
      "server",
      "The server could not load this document.",
    );
  return new DocumentError(
    "network",
    "The host could not complete this request. Refresh or check the connection.",
  );
}

function pluginRequest(method, payload = {}, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Cancelled", "AbortError"));
      return;
    }
    const requestId =
      crypto.randomUUID?.() ??
      [...crypto.getRandomValues(new Uint8Array(16))]
        .map((byte) => byte.toString(16).padStart(2, "0"))
        .join("");
    const cleanup = () => {
      clearTimeout(timer);
      window.removeEventListener("message", onMessage);
      signal?.removeEventListener("abort", onAbort);
    };
    const onAbort = () => {
      cleanup();
      reject(new DOMException("Cancelled", "AbortError"));
    };
    const onMessage = (event) => {
      if (
        event.source !== window.parent ||
        event.data?.type !== "plugin-api-response" ||
        event.data.requestId !== requestId
      )
        return;
      cleanup();
      if (event.data.error) {
        reject(transportError(event.data.status_code));
        return;
      }
      const result = event.data.result;
      if (!result || typeof result !== "object") {
        reject(
          new DocumentError(
            "unsupported",
            "The host returned an invalid response.",
          ),
        );
        return;
      }
      if (result.error) {
        reject(
          new DocumentError(
            result.error.kind || "server",
            result.error.message || "Document unavailable.",
          ),
        );
        return;
      }
      resolve(result);
    };
    const timer = setTimeout(() => {
      cleanup();
      reject(new DocumentError("network", "The request timed out. Try again."));
    }, 30000);
    signal?.addEventListener("abort", onAbort, { once: true });
    window.addEventListener("message", onMessage);
    window.parent.postMessage(
      { type: "plugin-api-request", requestId, method, payload },
      "*",
    );
  });
}

async function loadSettings() {
  const result = await pluginRequest("plugin.run-action", { actionId: "load-settings", values: {} });
  const value = result?.value;
  maxPreviewMiB =
    typeof value === "number" && Number.isFinite(value) && value >= 0
      ? Math.floor(value)
      : 0;
  maxPreviewInput.value = String(maxPreviewMiB);
}

function setSettingsPanel(open) {
  settingsPanel.hidden = !open;
  if (open) {
    maxPreviewInput.value = String(maxPreviewMiB);
    settingsStatus.textContent = "";
    maxPreviewInput.focus();
  }
}

function displayName(filename) {
  return filename.split("_").slice(1).join("_") || filename;
}
function sizeLabel(bytes) {
  return bytes < 1024
    ? `${bytes} B`
    : bytes < 1024 * 1024
      ? `${(bytes / 1024).toFixed(1)} KiB`
      : `${(bytes / 1024 / 1024).toFixed(1)} MiB`;
}
function state(message, error = false) {
  const element = document.createElement("p");
  element.className = error ? "state error" : "state";
  element.textContent = message;
  viewer.replaceChildren(element);
}
function clearViewer() {
  generation++;
  controller?.abort();
  controller = new AbortController();
  renderTask?.cancel();
  renderTask = null;
  pdfTask?.destroy();
  pdfTask = null;
  viewer.replaceChildren();
  document.querySelector("#pdf-tools").hidden = true;
  document.querySelector("#source-toggle").hidden = true;
  return generation;
}

function validateChunk(result, item, offset, previous) {
  const doc = result.document;
  if (
    result.encoding !== "base64" ||
    !doc ||
    doc.id !== item.id ||
    (item.game_id && doc.game_id !== item.game_id) ||
    !/^[a-f0-9-]{36}$/i.test(doc.game_id) ||
    typeof doc.filename !== "string" ||
    typeof doc.game_title !== "string" ||
    typeof doc.media_type !== "string" ||
    !Number.isSafeInteger(doc.size_bytes) ||
    doc.size_bytes < 0 ||
    doc.size_bytes > MAX_BYTES ||
    result.offset !== offset ||
    typeof result.content !== "string" ||
    result.content.length > 32768 ||
    !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(
      result.content,
    ) ||
    !/^[a-f0-9]{64}$/.test(result.content_sha256)
  ) {
    throw new DocumentError(
      "unsupported",
      "The host returned a malformed or oversized document representation.",
    );
  }
  if (
    previous &&
    (result.content_sha256 !== previous.content_sha256 ||
      doc.size_bytes !== previous.document.size_bytes ||
      doc.media_type !== previous.document.media_type ||
      result.format !== previous.format)
  )
    throw new DocumentError("changed", "Document changed. Open it again.");
  const bytes = Uint8Array.from(atob(result.content), (char) =>
    char.charCodeAt(0),
  );
  if (
    bytes.length > CHUNK_BYTES ||
    result.next_offset !== offset + bytes.length ||
    result.next_offset > doc.size_bytes ||
    result.complete !== (result.next_offset === doc.size_bytes) ||
    (!result.complete && !bytes.length)
  )
    throw new DocumentError(
      "unsupported",
      "The host returned an invalid document chunk.",
    );
  if (!(
    (doc.media_type === "application/pdf" && result.format === "pdf") ||
    (doc.media_type === "text/plain" &&
      ["text", "html"].includes(result.format)) ||
    OfficeDocumentViewer.types[result.format] === doc.media_type
  ))
    throw new DocumentError(
      "unsupported",
      "The host returned an unsupported content type.",
    );
  return bytes;
}

async function loadDocument(item, token) {
  let offset = 0;
  let previous = null;
  const chunks = [];
  do {
    const values = { document_id: item.id, chunk_bytes: CHUNK_BYTES, offset, max_bytes: maxPreviewMiB * 1024 * 1024 };
    if (previous) values.content_sha256 = previous.content_sha256;
    const result = await pluginRequest(
      "plugin.run-action",
      { actionId: "read-document", values },
      controller.signal,
    );
    if (token !== generation) throw new DOMException("Cancelled", "AbortError");
    chunks.push(validateChunk(result, item, offset, previous));
    currentDocument = result.document;
    heading.textContent = displayName(currentDocument.filename);
    metadata.textContent = `${currentDocument.game_title} · ${sizeLabel(currentDocument.size_bytes)} · ${currentDocument.media_type}`;
    offset = result.next_offset;
    previous = result;
    status.textContent = `Loading ${displayName(item.filename)} · ${sizeLabel(offset)} / ${sizeLabel(result.document.size_bytes)}`;
  } while (!previous.complete);
  const bytes = new Uint8Array(offset);
  let position = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, position);
    position += chunk.length;
  }
  const hash = crypto.subtle
    ? [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))]
        .map((byte) => byte.toString(16).padStart(2, "0"))
        .join("")
    : sha256(bytes);
  if (hash !== previous.content_sha256)
    throw new DocumentError(
      "changed",
      "Document integrity check failed. Open it again.",
    );
  return { bytes, format: previous.format };
}

function renderText(bytes, html) {
  if (bytes.some((byte) => byte < 32 && ![9, 10, 13].includes(byte)))
    throw new DocumentError(
      "unsupported",
      "Binary files cannot be displayed as text.",
    );
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    throw new DocumentError(
      "unsupported",
      "Only UTF-8 text documents can be displayed.",
    );
  }
  const pre = document.createElement("pre");
  pre.textContent = text;
  if (!html) {
    viewer.replaceChildren(pre);
    return;
  }
  const article = document.createElement("article");
  article.className = "document-html";
  article.innerHTML = DOMPurify.sanitize(text, {
    USE_PROFILES: { html: true },
    FORBID_TAGS: [
      "audio",
      "base",
      "embed",
      "form",
      "iframe",
      "img",
      "input",
      "link",
      "meta",
      "object",
      "script",
      "source",
      "style",
      "textarea",
      "track",
      "video",
    ],
    FORBID_ATTR: ["style", "srcset", "ping", "target"],
  });
  // Uploaded links cannot navigate the iframe or trigger a network request.
  for (const link of article.querySelectorAll("a"))
    link.removeAttribute("href");
  viewer.replaceChildren(article);
  const toggle = document.querySelector("#source-toggle");
  toggle.hidden = false;
  toggle.textContent = "Show source";
  let source = false;
  toggle.onclick = () => {
    source = !source;
    viewer.replaceChildren(source ? pre : article);
    toggle.textContent = source ? "Show formatted HTML" : "Show source";
  };
}

async function renderPdf(bytes, token) {
  if (new TextDecoder().decode(bytes.slice(0, 5)) !== "%PDF-")
    throw new DocumentError("unsupported", "This document is not a valid PDF.");
  pdfTask = pdfjsLib.getDocument({
    data: bytes,
    isEvalSupported: false,
    enableXfa: false,
    useWorkerFetch: false,
    useWasm: false,
    disableFontFace: true,
    useSystemFonts: true,
    isOffscreenCanvasSupported: false,
  });
  pdfTask.onPassword = () => {
    pdfTask?.destroy();
  };
  let pdf;
  try {
    pdf = await pdfTask.promise;
  } catch {
    throw new DocumentError(
      "unsupported",
      "This PDF is malformed or password protected and cannot be displayed.",
    );
  }
  if (token !== generation) return;
  let pageNumber = 1;
  let zoom = 1;
  let rendering = false;
  const tools = document.querySelector("#pdf-tools");
  const previous = document.querySelector("#previous");
  const next = document.querySelector("#next");
  const scale = document.querySelector("#zoom");
  const pageLabel = document.querySelector("#page-label");
  const canvas = document.createElement("canvas");
  canvas.setAttribute("role", "img");
  viewer.replaceChildren(canvas);
  tools.hidden = false;
  scale.value = "1";
  const render = async () => {
    if (rendering || token !== generation) return;
    rendering = true;
    previous.disabled = next.disabled = scale.disabled = true;
    viewer.setAttribute("aria-busy", "true");
    try {
      const page = await pdf.getPage(pageNumber);
      if (token !== generation) return;
      const natural = page.getViewport({ scale: 1 });
      // Bound each canvas to keep malicious page dimensions from allocating huge buffers.
      const pageScale = Math.min(
        zoom *
          Math.min(1.5, Math.max(300, viewer.clientWidth - 40) / natural.width),
        2400 / Math.max(natural.width, natural.height),
      );
      const viewport = page.getViewport({ scale: pageScale });
      canvas.width = Math.max(1, Math.ceil(viewport.width));
      canvas.height = Math.max(1, Math.ceil(viewport.height));
      canvas.setAttribute(
        "aria-label",
        `PDF page ${pageNumber} of ${pdf.numPages}`,
      );
      renderTask = page.render({
        canvasContext: canvas.getContext("2d"),
        viewport,
        annotationMode: pdfjsLib.AnnotationMode.DISABLE,
      });
      await renderTask.promise;
      page.cleanup();
      pageLabel.textContent = `Page ${pageNumber} of ${pdf.numPages}`;
    } catch (error) {
      if (token === generation && error.name !== "RenderingCancelledException")
        state("This PDF page could not be rendered.", true);
    } finally {
      rendering = false;
      if (token === generation) {
        previous.disabled = pageNumber <= 1;
        next.disabled = pageNumber >= pdf.numPages;
        scale.disabled = false;
        viewer.setAttribute("aria-busy", "false");
      }
    }
  };
  previous.onclick = () => {
    if (pageNumber > 1 && !rendering) {
      pageNumber--;
      void render();
    }
  };
  next.onclick = () => {
    if (pageNumber < pdf.numPages && !rendering) {
      pageNumber++;
      void render();
    }
  };
  scale.onchange = () => {
    zoom = Number(scale.value);
    void render();
  };
  await render();
}

async function openDocument(item) {
  const token = clearViewer();
  currentDocument = item;
  downloadButton.hidden = false;
  heading.textContent = displayName(item.filename);
  metadata.textContent = `${item.game_title} · ${sizeLabel(item.size_bytes)} · ${item.media_type}`;
  state("Loading document…");
  viewer.setAttribute("aria-busy", "true");
  for (const button of documents.querySelectorAll("button"))
    button.setAttribute("aria-pressed", String(button.dataset.id === item.id));
  try {
    const { bytes, format } = await loadDocument(item, token);
    if (token !== generation) return;
    if (format === "pdf") await renderPdf(bytes, token);
    else if (OfficeDocumentViewer.types[format]) {
      try {
        OfficeDocumentViewer.render(bytes, format, viewer);
      } catch (error) {
        throw new DocumentError(
          "unsupported",
          error.message || "Malformed office document.",
        );
      }
    } else renderText(bytes, format === "html");
    if (token === generation)
      status.textContent = `${displayName(currentDocument.filename)} opened${format === "html" ? " · sanitized HTML, links disabled" : ""}.`;
  } catch (error) {
    if (token !== generation || error.name === "AbortError") return;
    const labels = {
      missing: "Document not found",
      forbidden: "Access denied",
      oversized: "Document too large",
      unsupported: "Unsupported document",
      changed: "Document changed",
      invalid: "Invalid document",
      server: "Server error",
      network: "Unable to load document",
    };
    state(
      `${labels[error.kind] || "Unable to load document"}. ${error.message || "Try refreshing the document list."}`,
      true,
    );
    status.textContent = "Document could not be opened.";
  } finally {
    if (token === generation) viewer.setAttribute("aria-busy", "false");
  }
}

async function loadList(reset = false) {
  const token = ++listGeneration;
  if (reset) {
    clearViewer();
    documents.replaceChildren();
    heading.textContent = "Your game documents";
    metadata.textContent = "Choose a document to open it.";
    state("Select a document from the library.");
    nextOffset = 0;
    currentDocument = null;
    downloadButton.hidden = true;
  }
  refreshButton.disabled = moreButton.disabled = true;
  status.textContent = "Loading documents…";
  documents.setAttribute("aria-busy", "true");
  try {
    const result = await pluginRequest("plugin.run-action", {
      actionId: "list-documents",
      values: { limit: 32, offset: nextOffset },
    });
    if (token !== listGeneration) return;
    if (
      !Array.isArray(result.documents) ||
      (result.next_offset !== null &&
        (!Number.isSafeInteger(result.next_offset) ||
          result.next_offset <= nextOffset))
    )
      throw new DocumentError(
        "server",
        "The host returned an invalid document list.",
      );
    for (const item of result.documents) {
      if (
        !item ||
        typeof item.filename !== "string" ||
        typeof item.game_title !== "string" ||
        typeof item.id !== "string" ||
        !Number.isSafeInteger(item.size_bytes)
      )
        throw new DocumentError(
          "server",
          "The host returned invalid document metadata.",
        );
      const row = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.id = item.id;
      button.setAttribute("aria-pressed", "false");
      const name = document.createElement("strong");
      name.textContent = displayName(item.filename);
      const game = document.createElement("span");
      game.textContent = item.game_title;
      const details = document.createElement("small");
      details.textContent = `${sizeLabel(item.size_bytes)} · ${item.media_type} · ${new Date(item.created_at * 1000).toLocaleDateString()}`;
      button.append(name, game, details);
      button.onclick = () => {
        void openDocument(item);
      };
      row.append(button);
      documents.append(row);
    }
    nextOffset = result.next_offset;
    moreButton.hidden = nextOffset === null;
    if (!documents.children.length && nextOffset === null) {
      const empty = document.createElement("li");
      empty.className = "state";
      empty.textContent =
        "No documents yet. Add files in a game's Docs tab, then refresh.";
      documents.append(empty);
    }
    status.textContent = `${documents.querySelectorAll("button").length} documents${nextOffset === null ? "" : " · more available"}. Unsupported files stay in the library; opening them shows an explicit error.`;
  } catch (error) {
    if (token === listGeneration) {
      status.textContent = error.message || "Documents unavailable.";
      moreButton.hidden = true;
    }
  } finally {
    if (token === listGeneration) {
      refreshButton.disabled = moreButton.disabled = false;
      documents.setAttribute("aria-busy", "false");
    }
  }
}
refreshButton.onclick = () => {
  document.body.classList.remove("single-document");
  refreshButton.textContent = "Refresh library";
  void loadList(true);
};
downloadButton.onclick = async () => {
  if (!currentDocument) return;
  downloadButton.disabled = true;
  try {
    await pluginRequest("plugin.download-document", {
      document_id: currentDocument.id,
    });
    status.textContent = "Original download started.";
  } catch (error) {
    status.textContent = error.message || "Download could not be started.";
  } finally {
    downloadButton.disabled = false;
  }
};
settingsButton.onclick = () => {
  setSettingsPanel(settingsPanel.hidden);
};
cancelSettingsButton.onclick = () => {
  setSettingsPanel(false);
};
saveSettingsButton.onclick = async () => {
  const value = Number(maxPreviewInput.value);
  if (!Number.isSafeInteger(value) || value < 0) {
    settingsStatus.textContent = "Enter a non-negative whole number of MiB.";
    return;
  }
  saveSettingsButton.disabled = true;
  settingsStatus.textContent = "Saving…";
  try {
    await pluginRequest("plugin.save-settings", { max_preview_mb: value });
    maxPreviewMiB = value;
    settingsStatus.textContent =
      value === 0
        ? "Saved. Preview size is unlimited."
        : `Saved. Preview size is limited to ${value} MiB.`;
  } catch (error) {
    settingsStatus.textContent = error.message || "Settings could not be saved.";
  } finally {
    saveSettingsButton.disabled = false;
  }
};
moreButton.onclick = () => {
  void loadList();
};
window.addEventListener("beforeunload", clearViewer);
async function initialize() {
  try {
    // A settings failure keeps the default (unlimited) preview limit instead of disabling the reader.
    await loadSettings().catch(() => {});
    const context = await pluginRequest("plugin.context");
    if (context.document_id) {
      if (
        !/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(
          context.document_id,
        )
      )
        throw new DocumentError("invalid", "Invalid document identifier.");
      document.body.classList.add("single-document");
      refreshButton.textContent = "Browse library";
      await openDocument({
        id: context.document_id,
        game_id: context.game_id,
        filename: "Document",
        game_title: "Loading…",
        size_bytes: 0,
        media_type: "",
      });
    } else await loadList(true);
  } catch (error) {
    state(error.message || "Unable to initialize document reader.", true);
    status.textContent = "Reader unavailable.";
  }
}
void initialize();
