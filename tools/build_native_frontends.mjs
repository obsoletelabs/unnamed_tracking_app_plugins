// Compile plugin-owned Vue SFCs independently, using the documented host runtime.
import { mkdir, readFile, readdir, unlink, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { build } from "esbuild";
import { parse, compileScript, compileStyle } from "@vue/compiler-sfc";
import * as Vue from "vue";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const source = path.join(root, "official/collectors-archive");
const styles = new Map();
const modules = {
  "@unnamed/plugin-vue": Object.keys(Vue).filter(key => /^[A-Za-z_$][\w$]*$/.test(key)),
  "@unnamed/plugin-ui": ["PageHeader", "UiModal", "AppIcon", "AccountChip", "PasswordInput"],
};
const results = await build({
  absWorkingDir: root,
  entryPoints: [path.join(source, "ui/app.ts")], bundle: true, write: false,
  splitting: true, outdir: path.join(source, "native"),
  entryNames: "app", chunkNames: "chunks/[name]-[hash]",
  format: "esm", target: "es2022", minify: false, legalComments: "none",
  define: { "import.meta.env.VITE_USE_MOCK_DATA": "false" },
  plugins: [{ name: "public-native-vue", setup(builder) {
    builder.onResolve({ filter: /^(vue|@unnamed\/plugin-(vue|ui))$/ }, () => ({ path: "bindings", namespace: "public-runtime" }));
    builder.onLoad({ filter: /.*/, namespace: "public-runtime" }, args => {
      // Vue and host UI bindings share one small module across lazy pages.
      // Keeping them together avoids an extra serial bootstrap asset request.
      const vueKeys = modules["@unnamed/plugin-vue"], uiKeys = modules["@unnamed/plugin-ui"];
      return { contents: `export let ${[...vueKeys, ...uiKeys].join(",")};\nexport function configure(context) { ({${vueKeys.join(",")}} = context.vue); ({${uiKeys.join(",")}} = context.ui); }`, loader: "js" };
    });
    builder.onLoad({ filter: /\.vue$/ }, async args => {
      const code = (await readFile(args.path, "utf8")).replaceAll("\r\n", "\n");
      const { descriptor, errors } = parse(code, { filename: args.path });
      if (errors.length) throw errors[0];
      const scope = "data-v-" + createHash("sha256").update(path.relative(source, args.path).replaceAll("\\", "/")).digest("hex").slice(0, 8);
      const script = compileScript(descriptor, { id: scope, inlineTemplate: true, templateOptions: { compilerOptions: { scopeId: scope } } });
      const compiled = descriptor.styles.map(style => {
        const result = compileStyle({ source: style.content, filename: args.path, id: scope, scoped: style.scoped });
        if (result.errors.length) throw result.errors[0];
        return result.code;
      }).join("\n");
      styles.set(path.relative(source, args.path).replaceAll("\\", "/"), compiled);
      const contents = script.content.replace("export default", "const component =") + `\ncomponent.__scopeId = ${JSON.stringify(scope)};\nexport default component;`;
      return { contents, loader: "ts", resolveDir: path.dirname(args.path) };
    });
  } }],
});
const css = "/* Generated from plugin-owned UI; rebuild with npm run build:native. */\n" +
  [...styles.entries()].sort(([a], [b]) => a.localeCompare(b, "en")).map(([, code]) => code).join("\n") +
  "\n.collector-import{padding:var(--ui-space-6);margin-bottom:var(--ui-space-6)}.collector-import p{margin:12px 0;color:var(--ui-dim)}.collector-error{color:var(--ui-error)}.collector-archive{min-width:0}.collector-archive .page{padding:0}\n";
const outputs = Object.fromEntries(results.outputFiles.map(file =>
  [path.relative(source, file.path).replaceAll("\\", "/"), file.text]));
outputs["native/style.css"] = css;
// Only this generated chunk directory belongs to the builder. Published .utp
// histories are independent and remain immutable.
const chunkDirectory = path.join(source, "native/chunks");
for (const name of await readdir(chunkDirectory).catch(error => {
  if (error.code === "ENOENT") return [];
  throw error;
})) {
  const relative = "native/chunks/" + name;
  if (!outputs[relative] && /^[A-Za-z0-9_-]+-[A-Z0-9]{8}\.js$/.test(name)) {
    if (process.argv.includes("--check")) throw new Error(`${relative} is stale; run npm run build:native`);
    await unlink(path.join(chunkDirectory, name));
  }
}
for (const [name, content] of Object.entries(outputs)) {
  const filename = path.join(source, name);
  if (process.argv.includes("--check")) {
    if ((await readFile(filename, "utf8")).replaceAll("\r\n", "\n") !== content) throw new Error(`${name} is stale; run npm run build:native`);
  } else {
    await mkdir(path.dirname(filename), { recursive: true });
    await writeFile(filename, content);
  }
}
console.log("Collector's Archive native UI compiled against the public runtime");
