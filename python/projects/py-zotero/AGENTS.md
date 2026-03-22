# AGENTS.md - Development Guidelines for PapersGPT-for-Zotero

This document provides guidelines for AI agents working on this Zotero plugin project.

## Project Overview

PapersGPT is a Zotero plugin that enables AI-powered PDF chat using LLMs (ChatGPT, Gemini, Claude, DeepSeek, etc.). Built with TypeScript and the Zotero Plugin Toolkit.

## Build Commands

| Command | Description |
|---------|-------------|
| `npm run build` | Full production build (tsc + esbuild + minification) |
| `npm run build-dev` | Development build (no minification, faster) |
| `npm run build-prod` | Production build with minification |
| `npm run tsc` | TypeScript type checking only (`tsc --noEmit`) |
| `npm run start` | Start Zotero with plugin loaded (auto-detects version) |
| `npm run start-z6` | Start Zotero 6 with plugin |
| `npm run start-z7` | Start Zotero 7 with plugin |
| `npm run stop` | Stop running Zotero instance |
| `npm run restart-dev` | Rebuild dev, stop, restart Zotero |
| `npm run restart-prod` | Rebuild prod, stop, restart Zotero |
| `npm run release` | Create release with release-it |

**Single file compilation:** Use `node scripts/build.js` directly with environment variables for targeting specific files.

## TypeScript Configuration

- Target: ES2016
- Module: CommonJS
- Strict mode: enabled
- Experimental decorators: enabled (required for zotero-plugin-toolkit)
- Run `npm run tsc` before committing to catch type errors

## Code Style Guidelines

### General Principles

- Write clear, self-documenting code
- Keep functions small and single-purpose
- Use meaningful variable and function names
- Avoid clever tricks; prefer obvious solutions

### Naming Conventions

- **Classes**: PascalCase (e.g., `Addon`, `Views`)
- **Functions/variables**: camelCase (e.g., `onStartup`, `ztoolkit`)
- **Constants**: UPPER_SNAKE_CASE for configuration values (e.g., `DEFAULT_TIMEOUT`)
- **Files**: kebab-case for modules (e.g., `local-storage.ts`)
- **Interfaces**: PascalCase with `I` prefix optional (e.g., `ColumnOptions`)

### Imports

```typescript
// External packages
import { something } from "package-name";

// Relative imports (use explicit paths)
import hooks from "./hooks";
import { ColumnOptions } from "zotero-plugin-toolkit/dist/helpers/virtualizedTable";
```

### Types

- Enable strict TypeScript mode; avoid `any` when possible
- Use explicit types for function parameters and return values
- Use interfaces for object shapes, types for unions/primitives
- Use `@ts-ignore` sparingly only for Firefox/Zotero globals

### Error Handling

- Use try-catch blocks for async operations
- Display errors to users via `ztoolkit.ProgressWindow`
- Include context in error messages for debugging
- Never silently swallow exceptions

### Async Patterns

- Prefer `async/await` over raw promises
- Handle rejections explicitly
- Use appropriate timeouts for API calls

### File Organization

```
src/
├── index.ts              # Entry point
├── addon.ts              # Addon class
├── hooks.ts              # Lifecycle hooks
├── ztoolkit.ts           # Toolkit configuration
└── modules/
    ├── views.ts          # Main UI component
    ├── base.ts           # Prompts, tags, constants
    ├── utils.ts          # Utility functions
    ├── locale.ts         # Localization
    └── Meet/             # API integrations
```

### Zotero Integration

- Follow standard lifecycle hooks: `onStartup`, `onShutdown`, `onMainWindowLoad`, `onMainWindowUnload`
- Use `zotero-plugin-toolkit`'s UITool for DOM element creation
- Access Zotero APIs via `Zotero` global
- Use `ztoolkit.ProgressWindow` for user feedback

### UI Development

- Use toolkit's `VirtualizedTable` for data tables
- Use `PromptTemplate` literals from `base.ts` for LLM prompts
- Use `markdown-it` with `katex` for math rendering
- Use `react-markdown` for React-compatible markdown

### Linting & Formatting

No formal linting configured. Manually ensure:
- Consistent indentation (2 spaces)
- No trailing whitespace
- Use semicolons
- Quote property names consistently

## Before Committing

1. Run `npm run tsc` to verify no type errors
2. Run `npm run build-dev` to verify build succeeds
3. Check for `TODO` comments - add issue numbers
4. Review changes for clarity and correctness

## Common Patterns

```typescript
// Zotero lifecycle hook pattern
export const onStartup: typeof hooks.onStartup = async () => {
  await addon.data.ztoolkit.ui.dataTool.dataView();
};

// Template literal for prompts (stored in base.ts)
const PROMPT_TEMPLATE = `You are a helpful assistant...`;

// UI creation with toolkit
const element = await addon.data.ztoolkit.ui.createElement(...)
```

## Dependencies

Key libraries (do not duplicate functionality):
- `zotero-plugin-toolkit`: UI, data, lifecycle
- `langchain`: LLM integration
- `pdf-parse`/`pdfreader`: PDF processing
- `markdown-it`: Markdown rendering
- `chromadb`/`pinecone`: Vector storage

## Testing

No test framework configured. Manual testing via:
```bash
npm run restart-dev  # Build and launch Zotero
```
Test changes in running Zotero instance, then commit.
