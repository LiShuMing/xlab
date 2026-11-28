# lab-viewer：TypeScript 离线实验报告聚合与可视化工具

零第三方运行时依赖的 **TypeScript** 工具（仅使用 Node.js 24+ 内置模块），用于把 `xlab/labs/` 产出的 JSON 基准报告（如 `labs/slatedb-oss`、`duckdb-oss-compare`、`labs/cache`、`labs/hashmap`、`labs/infer-engine` 等）统一聚合为 Markdown 汇总表或单文件离线 HTML 对比面板（内嵌 SVG 柱状图，无外部 CDN）。

## 前置条件

- Node.js 24+、`tsc`、`tsx`（本机通过 `source "$HOME/.ENVS/env.sh"` 激活）。

## 使用与验证

```sh
source "$HOME/.ENVS/env.sh"

# 类型检查与单元测试（零外部依赖，离线可跑）
npm run typecheck
npm test

# 将多个 JSON 报告渲染为 Markdown 或单文件 HTML
tsx src/cli.ts --input /path/to/reports_dir --format markdown
tsx src/cli.ts --input report_a.json --input report_b.json --format html --out .local/dashboard.html
```
