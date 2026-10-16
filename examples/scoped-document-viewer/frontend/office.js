/* Read-only Office/OpenDocument reading previews. No uploaded markup or CSS executes. */
(() => {
  const TYPES = {
    docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    odt: "application/vnd.oasis.opendocument.text",
    odp: "application/vnd.oasis.opendocument.presentation",
  };
  function unpack(bytes) {
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    let end = bytes.length - 22;
    while (
      end >= Math.max(0, bytes.length - 65557) &&
      view.getUint32(end, true) !== 0x06054b50
    )
      end--;
    if (
      end < 0 ||
      view.getUint16(end + 4, true) ||
      view.getUint16(end + 6, true)
    )
      throw new Error("Invalid office archive.");
    const count = view.getUint16(end + 10, true);
    let position = view.getUint32(end + 16, true),
      total = 0;
    const names = new Set();
    if (!count || count > 1024)
      throw new Error("Too many office archive entries.");
    for (let index = 0; index < count; index++) {
      if (view.getUint32(position, true) !== 0x02014b50)
        throw new Error("Malformed office archive.");
      const flags = view.getUint16(position + 8, true),
        method = view.getUint16(position + 10, true);
      const compressed = view.getUint32(position + 20, true),
        size = view.getUint32(position + 24, true);
      const length = view.getUint16(position + 28, true);
      const name = new TextDecoder("utf-8", { fatal: true }).decode(
        bytes.subarray(position + 46, position + 46 + length),
      );
      const decoded = decodeURIComponent(name).replaceAll("\\", "/");
      const parts = decoded.toLowerCase().split("/");
      if (
        flags & 1 ||
        ![0, 8].includes(method) ||
        decoded.startsWith("/") ||
        /[:\0]/.test(decoded) ||
        parts.includes("..") ||
        names.has(name.toLowerCase()) ||
        parts.some((part) =>
          ["vbaproject.bin", "scripts", "basic", "activex"].includes(part),
        ) ||
        // Charts keep their data in a macro-free embedded package, which is
        // never opened; OLE objects and macro-enabled packages stay refused.
        (parts.includes("embeddings") &&
          !/\.(xlsx|docx|pptx)$/i.test(decoded))
      )
        throw new Error("Active or unsafe office archive.");
      names.add(name.toLowerCase());
      total += size;
      if (
        size > (/\.(xml|rels)$/i.test(name) ? 2 : 5) * 1024 * 1024 ||
        total > 20 * 1024 * 1024 ||
        size > Math.max(1024, compressed * 100)
      )
        throw new Error("Office archive exceeds safe expansion limits.");
      position +=
        46 +
        length +
        view.getUint16(position + 30, true) +
        view.getUint16(position + 32, true);
      if (position > end) throw new Error("Malformed office archive index.");
    }
    // fflate's synchronous ZIP inflater uses each checked original size as its fixed output buffer.
    const files = fflate.unzipSync(bytes);
    for (const name of Object.keys(files).filter((name) =>
      /\.(xml|rels)$/i.test(name),
    )) {
      const document = xml(files, name);
      if (
        [...document.getElementsByTagName("*")].some(
          (node) =>
            ["script", "event-listener", "encryption-data"].includes(
              node.localName,
            ) ||
            (node.getAttribute("ContentType") || "")
              .toLowerCase()
              .includes("macroenabled"),
        )
      )
        throw new Error("Active office content is unsupported.");
    }
    return files;
  }
  function xml(files, name) {
    if (!files[name]) throw new Error(`Missing office document part: ${name}`);
    const bytes = files[name];
    const encoding =
      bytes[0] === 255 && bytes[1] === 254
        ? "utf-16le"
        : bytes[0] === 254 && bytes[1] === 255
          ? "utf-16be"
          : "utf-8";
    const text = new TextDecoder(encoding, { fatal: true }).decode(bytes);
    if (/<!\s*(DOCTYPE|ENTITY)/i.test(text))
      throw new Error("XML entities are unsupported.");
    const document = new DOMParser().parseFromString(text, "application/xml");
    if (
      document.querySelector("parsererror") ||
      document.getElementsByTagName("*").length > 50000
    )
      throw new Error("Malformed office XML.");
    return document;
  }
  const children = (node) => [...node.children];
  const descendants = (node, local) =>
    [...node.getElementsByTagName("*")].filter(
      (child) => child.localName === local,
    );
  const attribute = (node, local) =>
    [...node.attributes].find((attr) => attr.localName === local)?.value;
  function pathFor(base, relative) {
    if (/^(?:[a-z]+:|\/|\\)/i.test(relative)) return null;
    const result = base.split("/").slice(0, -1);
    for (const part of decodeURIComponent(relative)
      .replaceAll("\\", "/")
      .split("/")) {
      if (part === "..") {
        if (!result.length) return null;
        result.pop();
      } else if (part && part !== ".") result.push(part);
    }
    return result.join("/");
  }
  function relationships(files, source) {
    const parts = source.split("/"),
      filename = parts.pop();
    const name = [...parts, "_rels", filename + ".rels"].join("/");
    if (!files[name]) return new Map();
    return new Map(
      descendants(xml(files, name), "Relationship")
        .filter((node) => node.getAttribute("TargetMode") !== "External")
        .map((node) => [
          node.getAttribute("Id"),
          pathFor(source, node.getAttribute("Target") || ""),
        ]),
    );
  }
  function raster(bytes) {
    if (!bytes) return null;
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    let width = 0,
      height = 0,
      type;
    if (
      bytes.length >= 24 &&
      view.getUint32(0) === 0x89504e47 &&
      view.getUint32(4) === 0x0d0a1a0a
    ) {
      width = view.getUint32(16);
      height = view.getUint32(20);
      type = "image/png";
    } else if (bytes[0] === 255 && bytes[1] === 216) {
      type = "image/jpeg";
      let position = 2;
      while (position + 9 < bytes.length) {
        if (bytes[position] !== 255) break;
        const marker = bytes[position + 1],
          length = view.getUint16(position + 2);
        if ([192, 193, 194].includes(marker)) {
          height = view.getUint16(position + 5);
          width = view.getUint16(position + 7);
          break;
        }
        if (length < 2) break;
        position += 2 + length;
      }
    }
    if (
      !width ||
      !height ||
      width * height > 16000000 ||
      width > 10000 ||
      height > 10000
    )
      return null;
    let binary = "";
    for (let offset = 0; offset < bytes.length; offset += 8192)
      binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
    return `data:${type};base64,${btoa(binary)}`;
  }
  function image(files, path, target) {
    const source = path && raster(files[path]);
    if (!source) return;
    const image = document.createElement("img");
    image.src = source;
    image.alt = "Embedded document image";
    image.loading = "lazy";
    target.append(image);
  }
  function placeholders(node, target) {
    const objects =
      descendants(node, "chart").length +
      descendants(node, "OLEObject").length +
      descendants(node, "oleObj").length;
    for (let index = 0; index < objects; index++) {
      const note = document.createElement("span");
      note.className = "office-object";
      note.textContent = "Chart or embedded object not shown in preview";
      target.append(note);
    }
  }
  function wordBlocks(node, target, files, links) {
    for (const child of children(node)) {
      if (child.localName === "p") {
        const style = descendants(child, "pStyle")[0];
        const heading = /^(?:Heading|Title)(\d)?$/i.exec(
          style ? attribute(style, "val") || "" : "",
        );
        const paragraph = document.createElement(
          heading ? `h${Math.min(6, Number(heading[1] || 1))}` : "p",
        );
        for (const run of descendants(child, "r")) {
          const span = document.createElement("span");
          if (descendants(run, "b").length) span.classList.add("office-bold");
          if (descendants(run, "i").length) span.classList.add("office-italic");
          for (const value of children(run)) {
            if (value.localName === "t")
              span.append(document.createTextNode(value.textContent));
            if (value.localName === "tab")
              span.append(document.createTextNode("\t"));
            if (value.localName === "br")
              span.append(document.createElement("br"));
          }
          paragraph.append(span);
        }
        for (const blip of descendants(child, "blip"))
          image(files, links.get(attribute(blip, "embed")), paragraph);
        placeholders(child, paragraph);
        target.append(paragraph);
      } else if (child.localName === "tbl") {
        const table = document.createElement("table");
        for (const row of children(child).filter(
          (node) => node.localName === "tr",
        )) {
          const tr = document.createElement("tr");
          for (const cell of children(row).filter(
            (node) => node.localName === "tc",
          )) {
            const td = document.createElement("td");
            wordBlocks(cell, td, files, links);
            tr.append(td);
          }
          table.append(tr);
        }
        target.append(table);
      } else if (child.localName === "sdt" || child.localName === "sdtContent")
        wordBlocks(child, target, files, links);
    }
  }
  function openBlocks(node, target, files) {
    for (const child of children(node)) {
      const local = child.localName;
      if (["p", "h"].includes(local)) {
        const paragraph = document.createElement(local === "h" ? "h2" : "p");
        const walk = (value) => {
          for (const item of value.childNodes) {
            if (item.nodeType === Node.TEXT_NODE)
              paragraph.append(document.createTextNode(item.textContent));
            else if (item.nodeType === Node.ELEMENT_NODE) {
              if (item.localName === "line-break")
                paragraph.append(document.createElement("br"));
              else if (item.localName === "s")
                paragraph.append(
                  document.createTextNode(
                    " ".repeat(
                      Math.min(100, Number(attribute(item, "c") || 1)),
                    ),
                  ),
                );
              else if (item.localName === "tab")
                paragraph.append(document.createTextNode("\t"));
              else walk(item);
            }
          }
        };
        walk(child);
        target.append(paragraph);
      } else if (local === "image")
        image(
          files,
          pathFor("content.xml", attribute(child, "href") || ""),
          target,
        );
      else if (
        ["table", "table-row", "table-cell", "list", "list-item"].includes(
          local,
        )
      ) {
        const mapping = {
          table: "table",
          "table-row": "tr",
          "table-cell": "td",
          list: "ul",
          "list-item": "li",
        };
        const block = document.createElement(mapping[local]);
        openBlocks(child, block, files);
        target.append(block);
      } else if (!["scripts", "event-listeners", "binary-data"].includes(local))
        openBlocks(child, target, files);
    }
  }
  function presentation(files, target) {
    const source = "ppt/presentation.xml";
    const links = relationships(files, source);
    const slides = descendants(xml(files, source), "sldId");
    if (!slides.length || slides.length > 500)
      throw new Error("Unsupported slide count.");
    for (const [index, reference] of slides.entries()) {
      const path = links.get(
        [...reference.attributes].find(
          (attr) => attr.localName === "id" && attr.namespaceURI,
        )?.value,
      );
      if (!path) throw new Error("Missing slide relationship.");
      const slide = xml(files, path),
        section = document.createElement("section");
      section.className = "office-slide";
      const label = document.createElement("h2");
      label.textContent = `Slide ${index + 1} of ${slides.length}`;
      section.append(label);
      for (const paragraph of descendants(slide, "p")) {
        const text = document.createElement("p");
        for (const run of descendants(paragraph, "t"))
          text.append(document.createTextNode(run.textContent));
        if (text.textContent) section.append(text);
      }
      const media = relationships(files, path);
      for (const blip of descendants(slide, "blip"))
        image(files, media.get(attribute(blip, "embed")), section);
      placeholders(slide, section);
      target.append(section);
    }
  }
  function render(bytes, format, target) {
    const files = unpack(bytes),
      content = document.createElement("article");
    content.className = "office-document";
    if (format === "docx") {
      const source = "word/document.xml",
        body = descendants(xml(files, source), "body")[0];
      if (!body) throw new Error("Missing Word document body.");
      wordBlocks(body, content, files, relationships(files, source));
    } else if (format === "pptx") presentation(files, content);
    else {
      if (new TextDecoder().decode(files.mimetype) !== TYPES[format])
        throw new Error("Incorrect OpenDocument type.");
      const source = xml(files, "content.xml");
      if (format === "odp") {
        const pages = descendants(source, "page");
        if (!pages.length || pages.length > 500)
          throw new Error("Unsupported slide count.");
        for (const [index, page] of pages.entries()) {
          const section = document.createElement("section"),
            title = document.createElement("h2");
          section.className = "office-slide";
          title.textContent = `Slide ${index + 1} of ${pages.length}`;
          section.append(title);
          openBlocks(page, section, files);
          content.append(section);
        }
      } else {
        const body = descendants(source, "text")[0];
        if (!body) throw new Error("Missing OpenDocument body.");
        openBlocks(body, content, files);
      }
    }
    const note = document.createElement("p");
    note.className = "preview-note";
    note.textContent =
      "Reading preview: text, basic tables and PNG/JPEG images. Complex layout, charts, animations and embedded objects may differ. Download the original for full fidelity.";
    target.replaceChildren(note, content);
  }
  window.OfficeDocumentViewer = { render, types: TYPES };
})();
