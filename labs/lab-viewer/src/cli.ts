import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

import { loadReports } from "./loader.ts";
import { renderHtml, renderMarkdown } from "./render.ts";

interface CliOptions {
  inputs: string[];
  format: "markdown" | "html";
  out?: string;
}

function parseCli(argv: readonly string[]): CliOptions {
  const inputs: string[] = [];
  let format: "markdown" | "html" = "markdown";
  let out: string | undefined;

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--input" && argv[i + 1]) {
      inputs.push(argv[++i]!);
    } else if (arg === "--format" && argv[i + 1]) {
      const f = argv[++i]!;
      if (f !== "markdown" && f !== "html") {
        throw new Error(`Unsupported format: ${f} (expected markdown or html)`);
      }
      format = f;
    } else if (arg === "--out" && argv[i + 1]) {
      out = argv[++i]!;
    } else if (arg === "--help" || arg === "-h") {
      console.log(
        "Usage: tsx src/cli.ts --input <file-or-dir> [--input ...] [--format markdown|html] [--out <path>]",
      );
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  if (inputs.length === 0) {
    throw new Error("Provide at least one --input <json-file-or-dir>");
  }

  return out !== undefined ? { inputs, format, out } : { inputs, format };
}

function main(): void {
  const opts = parseCli(process.argv.slice(2));
  const reports = loadReports(opts.inputs);
  const output = opts.format === "html" ? renderHtml(reports) : renderMarkdown(reports);

  if (opts.out) {
    mkdirSync(dirname(opts.out), { recursive: true });
    writeFileSync(opts.out, output, "utf8");
    console.log(`Wrote ${opts.format} report (${reports.length} sources) to ${opts.out}`);
  } else {
    process.stdout.write(output);
  }
}

main();
