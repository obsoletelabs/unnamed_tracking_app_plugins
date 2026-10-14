// Build the standalone Activity inside its verified package, with no runtime compiler.
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { build } from "esbuild";
import { parse, compileScript, compileStyle } from "@vue/compiler-sfc";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const source = path.join(root, "official/discord-social-activity");
const styles = new Map();
const result = await build({
  absWorkingDir: root, entryPoints: [path.join(source, "ui/main.js")], bundle: true,
  write: false, format: "esm", target: "es2022", minify: true, legalComments: "none",
  define: { "process.env.NODE_ENV": '"production"', __VUE_OPTIONS_API__: "false", __VUE_PROD_DEVTOOLS__: "false", __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: "false" },
  plugins: [{ name: "activity-vue", setup(builder) {
    builder.onLoad({ filter: /\.vue$/ }, async args => {
      const { descriptor, errors } = parse((await readFile(args.path, "utf8")).replaceAll("\r\n", "\n"), { filename: args.path });
      if (errors.length) throw errors[0];
      const script = compileScript(descriptor, { id: "activity", inlineTemplate: true });
      const css = descriptor.styles.map(style => {
        const compiled = compileStyle({ source: style.content, filename: args.path, id: "activity", scoped: false });
        if (compiled.errors.length) throw compiled.errors[0];
        return compiled.code;
      }).join("\n");
      styles.set(args.path, css);
      return { contents: script.content, loader: "js", resolveDir: path.dirname(args.path) };
    });
  } }],
});
const outputs = { "frontend/app.js": result.outputFiles[0].text,
  "frontend/style.css": [...styles.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([, css]) => css).join("\n") };
const revision = createHash("sha256").update(outputs["frontend/app.js"] + outputs["frontend/style.css"]).digest("hex").slice(0, 16);
outputs["frontend/index.html"] = (await readFile(path.join(source, "ui/index.html"), "utf8"))
  .replaceAll("\r\n", "\n")
  .replace("./style.css", `./style.css?v=${revision}`).replace("./app.js", `./app.js?v=${revision}`);
for (const [name, content] of Object.entries(outputs)) {
  const filename = path.join(source, name);
  if (process.argv.includes("--check")) {
    if ((await readFile(filename, "utf8")).replaceAll("\r\n", "\n") !== content) throw new Error(`${name} is stale`);
  } else await writeFile(filename, content);
}
console.log("Game Night Activity frontend compiled");
