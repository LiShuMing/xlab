import { build, context } from "esbuild";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import process from "node:process";

const watch = process.argv.includes("--watch");
await rm("dist", { recursive: true, force: true });
await mkdir("dist/assets", { recursive: true });

const options = {
  entryPoints: ["src/main.tsx"],
  bundle: true,
  outfile: "dist/assets/app.js",
  sourcemap: true,
  minify: !watch,
  target: ["es2020"],
  loader: { ".tsx": "tsx", ".ts": "ts", ".css": "css" },
  define: { "process.env.NODE_ENV": JSON.stringify(watch ? "development" : "production") },
};

const source = await readFile("index.html", "utf8");
const html = source
  .replace('<script type="module" src="/src/main.tsx"></script>', '<script type="module" src="/assets/app.js"></script>')
  .replace("</head>", '    <link rel="stylesheet" href="/assets/app.css" />\n  </head>');
await writeFile("dist/index.html", html, "utf8");

if (watch) {
  const buildContext = await context(options);
  await buildContext.watch();
  console.log("Watching Tech Radar web sources...");
} else {
  await build(options);
}
