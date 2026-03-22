# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PapersGPT is a Zotero plugin enabling AI-powered PDF chat with multiple LLM providers (ChatGPT, Gemini, Claude, DeepSeek, etc.). Features include single/multi-PDF chat, RAG, MCP server integration, and local LLM support via C++ backend.

**Platform**: Zotero browser extension (Firefox/XUL architecture)

## Build Commands

```bash
npm run build          # Full production build (tsc + esbuild + minification)
npm run build-dev      # Development build (faster, no minification)
npm run tsc            # TypeScript type checking only (tsc --noEmit)
npm run start          # Start Zotero with plugin (auto-detects version)
npm run restart-dev    # Rebuild dev + restart Zotero (primary dev workflow)
npm run release        # Create release with release-it
```

**Manual testing**: No test framework. Use `npm run restart-dev` to build and launch Zotero with the plugin.

## Architecture

```text
src/
├── index.ts           # Entry point - initializes addon and globals
├── addon.ts           # Addon class with lifecycle and data
├── hooks.ts           # Lifecycle hooks (onStartup, onShutdown, onMainWindowLoad/Unload)
├── ztoolkit.ts        # Toolkit configuration
└── modules/
    ├── views.ts       # Main UI component (largest file - chat interface)
    ├── base.ts        # Prompts, tags, constants
    ├── utils.ts       # Utility functions
    ├── localStorage.ts
    ├── locale.ts
    └── Meet/          # External integrations
        ├── papersgpt.ts     # PapersGPT API client
        ├── Zotero.ts        # Zotero integration helpers
        ├── integratellms.ts # LLM provider integrations
        ├── api.ts           # API utilities
        └── BetterNotes.ts   # Better Notes integration
```

**Build output**: `builds/addon/chrome/content/scripts/index.js` → packaged as `.xpi`

## Key Patterns

### Zotero Lifecycle Hooks (`hooks.ts`)

```typescript
export const onStartup: typeof hooks.onStartup = async () => { ... };
export const onMainWindowLoad: typeof hooks.onMainWindowLoad = async (win) => { ... };
```

### Common Patterns

- **UI creation**: Use `addon.data.ztoolkit.ui` methods
- **User feedback**: Use `ztoolkit.ProgressWindow` for notifications
- **Zotero APIs**: Access via global `Zotero` object (e.g., `Zotero.Items.get()`)

### MCP Server

Local C++ server runs on `http://localhost:9080`

## TypeScript Config

- Target: ES2016, Module: CommonJS
- Strict mode enabled
- Experimental decorators required for zotero-plugin-toolkit
- Use `@ts-ignore` sparingly for Firefox/Zotero globals

## Before Committing

1. `npm run tsc` - verify no type errors
2. `npm run build-dev` - verify build succeeds

## Key Dependencies

- `zotero-plugin-toolkit`: UI, data, lifecycle management
- `langchain`: LLM integration
- `pdf-parse`/`pdfreader`: PDF processing
- `markdown-it` + `katex`: Markdown/math rendering
- `chromadb`/`pinecone`: Vector storage for RAG
