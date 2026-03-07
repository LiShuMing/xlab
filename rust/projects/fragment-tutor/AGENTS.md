# FragmentTutor - Agent Guide

> This file is intended for AI coding agents working on the FragmentTutor project (碎片时间学习助手).

## Project Overview

FragmentTutor is a macOS native desktop application designed for capturing and learning during fragmented time. It helps users capture URLs, analyze content with AI, review with spaced repetition, and track daily reflections.

### Core Features

1. **📥 Capture (采集)** - Save URLs and notes for offline reading
2. **🧠 Analyze (分析)** - AI-powered document analysis using Anthropic API (Quick Digest)
3. **🔄 Review (复习)** - Spaced repetition system (SRS) for vocabulary and insights
4. **🤔 Reflect (反省)** - Daily reflection cards with habit tracking (deep work, sleep, family time)

## Technology Stack

### Frontend
- **Framework**: React 18 + TypeScript 5.3
- **Build Tool**: Vite 5
- **Styling**: Tailwind CSS 3.4
- **State Management**: Zustand 4.5 (with persistence middleware)
- **Routing**: React Router DOM 6.22
- **Date Handling**: date-fns 3.6 (with zhCN locale)
- **AI SDK**: @anthropic-ai/sdk 0.71

### Backend (Rust)
- **Framework**: Tauri 2.0
- **Database**: SQLite with SQLx 0.7
- **HTTP Client**: Reqwest 0.11
- **HTML Parsing**: Scraper 0.25 + html2text 0.2
- **Async Runtime**: Tokio 1.35
- **Error Handling**: anyhow + thiserror
- **Minimum Rust Version**: 1.70

### Tauri Plugins
- `@tauri-apps/plugin-notification` - System notifications
- `@tauri-apps/plugin-sql` - Database operations
- `@tauri-apps/plugin-store` - Key-value storage

## Project Structure

```
fragment-tutor/
├── src/                          # Frontend source (React + TypeScript)
│   ├── components/               # React components
│   │   ├── Layout.tsx            # App shell layout (Header + Sidebar)
│   │   ├── Header.tsx            # Top navigation with capture/reflection buttons
│   │   ├── Sidebar.tsx           # Navigation sidebar
│   │   ├── CaptureModal.tsx      # URL/note capture modal
│   │   ├── ReflectionCard.tsx    # Quick reflection modal (60-second reflection)
│   │   ├── DocumentCard.tsx      # Document list item display
│   │   ├── FlashCard.tsx         # SRS review card component
│   │   └── ReaderView.tsx        # Document reader with analysis view
│   ├── pages/                    # Page components (main views)
│   │   ├── LibraryPage.tsx       # Document library with search
│   │   ├── TodayPage.tsx         # Today's tasks and overview
│   │   ├── ReviewPage.tsx        # SRS review queue interface
│   │   ├── ReflectionPage.tsx    # Reflection history and stats
│   │   └── SettingsPage.tsx      # App settings (API key, goals, shortcuts)
│   ├── hooks/                    # Custom React hooks
│   │   ├── useDocuments.ts       # Document CRUD and analysis operations
│   │   ├── useReviews.ts         # SRS queue and review operations
│   │   ├── useReflection.ts      # Reflection data operations
│   │   └── useShortcuts.ts       # Global keyboard shortcuts
│   ├── services/                 # API service layer (Tauri invoke wrappers)
│   │   ├── index.ts              # Service exports
│   │   ├── database.ts           # Document/review/reflection DB operations
│   │   ├── capture.ts            # URL capture and note creation
│   │   ├── anthropic.ts          # AI analysis service
│   │   └── settings.ts           # Settings management
│   ├── store/                    # State management
│   │   └── index.ts              # Zustand store with persistence
│   ├── types/                    # TypeScript type definitions
│   │   └── index.ts              # All shared types (Document, ReviewItem, etc.)
│   ├── utils/                    # Utility functions
│   │   └── date.ts               # Date formatting utilities (Chinese locale)
│   ├── App.tsx                   # Main app component with view routing
│   ├── main.tsx                  # React entry point
│   └── index.css                 # Global styles + Tailwind + custom components
├── src-tauri/                    # Rust backend
│   ├── src/
│   │   ├── main.rs               # Application entry point
│   │   ├── lib.rs                # Tauri app setup and command handlers
│   │   ├── models/               # Data models
│   │   │   └── mod.rs            # Rust struct definitions (Document, ReviewItem, etc.)
│   │   └── services/             # Business logic
│   │       ├── mod.rs            # Service exports
│   │       ├── database.rs       # SQLite schema and migrations
│   │       ├── anthropic.rs      # Anthropic API client (placeholder implementation)
│   │       └── scraper.rs        # Web scraping utilities
│   ├── Cargo.toml                # Rust dependencies
│   ├── tauri.conf.json           # Tauri configuration (window, bundle settings)
│   └── icons/                    # App icons
├── package.json                  # Node dependencies and scripts
├── tsconfig.json                 # TypeScript config (ES2020, path aliases)
├── vite.config.ts                # Vite configuration (port 3000, path aliases)
├── tailwind.config.js            # Tailwind CSS config (custom colors)
├── .eslintrc.cjs                 # ESLint rules (React hooks, TypeScript)
├── .prettierrc                   # Prettier config
└── index.html                    # HTML entry point
```

## Build & Development Commands

### Prerequisites
- macOS 11.0+ (primary target platform)
- Node.js 18+
- Rust 1.70+

### Install Dependencies

```bash
# Frontend dependencies
npm install

# Rust dependencies
cd src-tauri && cargo fetch && cd ..
```

### Development

```bash
# Start frontend dev server (port 3000)
npm run dev

# Start Tauri in development mode (in separate terminal)
npm run tauri dev
```

### Build for Production

```bash
# Build frontend assets
npm run build

# Build macOS application
npm run tauri build
```

### Code Quality

```bash
# Run ESLint
npm run lint

# Format code (TypeScript + Rust)
npm run format
```

## Code Style Guidelines

### TypeScript/React

- **Quote Style**: Single quotes (`'string'`)
- **Semicolons**: Required
- **Indent**: 2 spaces
- **Max Line Width**: 100 characters
- **Trailing Commas**: ES5 style (objects/arrays)
- **JSX Quotes**: Single quotes
- **Bracket Spacing**: Enabled

### Naming Conventions
- **Components**: PascalCase (e.g., `CaptureModal.tsx`)
- **Hooks**: camelCase, prefixed with `use` (e.g., `useDocuments.ts`)
- **Types/Interfaces**: PascalCase (e.g., `Document`, `ReviewItem`)
- **Services**: camelCase (e.g., `databaseService`)
- **Functions**: camelCase

### CSS/Tailwind

- Use Tailwind utility classes primarily
- Custom components in `index.css` with `@layer components`
- Custom utilities in `index.css` with `@layer utilities`
- Color palette: `primary` (sky blue) and `accent` (fuchsia) defined in tailwind.config.js
- Custom component classes available: `.btn`, `.btn-primary`, `.btn-secondary`, `.card`, `.input`, `.badge`, `.sidebar-item`

### Rust

- Follow standard Rust naming conventions (snake_case for functions/variables, PascalCase for types)
- Use `anyhow`/`thiserror` for error handling
- Async/await with Tokio runtime
- SQLx for database operations
- Commands return `Result<T, String>` for Tauri compatibility

## Data Models

### Document
Captured URL or note with metadata.
- `id`: string (UUID)
- `type`: 'url' | 'note'
- `title`: string
- `url`: optional string (for URL captures)
- `content`: optional string (clean text content)
- `capturedAt`: ISO date string
- `status`: 'captured' | 'ingested' | 'analyzing' | 'analyzed' | 'failed'
- `topics`: string[] (extracted topics)
- `entities`: string[] (named entities)
- `wordCount`: number

### ReviewItem (SRS Card)
Spaced repetition flashcard for vocabulary or insights.
- `id`: string
- `type`: 'vocab' | 'insight'
- `front`: string (question/prompt)
- `back`: string (answer)
- `context`: optional string (source context)
- `dueAt`: ISO date string
- `interval`: number (days until next review)
- `ease`: number (SM-2 ease factor, default 2.5)
- `lastScore`: 0-5 quality rating
- `streak`: consecutive correct reviews

### Reflection
Daily reflection entry.
- `id`: string
- `date`: ISO date string (YYYY-MM-DD)
- `keyWin`: string (today's key achievement)
- `avoidance`: string (what was avoided)
- `nextFix`: string (plan to fix)
- `deepWorkMin`: number (deep work minutes)
- `familyMin`: number (family time minutes)
- `sleepH`: number (sleep hours)
- `notes`: optional string

### QuickDigestResult
AI analysis output structure.
- `thesis`: string (one-sentence summary)
- `firstPrinciples`: string[] (3-5 fundamental concepts)
- `counterpoint`: string (thoughtful limitation)
- `microActions`: string[] (actionable items)
- `vocab`: VocabularyItem[] (extracted terms)
- `keyInsights`: string[] (surprising takeaways)
- `relatedTopics`: string[] (exploration topics)

## Frontend-Backend Communication

Frontend uses Tauri's `invoke` function to call Rust commands:

```typescript
import { invoke } from '@tauri-apps/api/core';

// Example: Get documents from database
const documents = await invoke('get_documents', { limit: 10 });
```

Rust commands are registered in `src-tauri/src/lib.rs` via `generate_handler![]`.

### Current Commands (lib.rs)
- `greet(name)` - Test command
- `get_app_version()` - Returns version string
- `get_data_dir()` - Returns app data directory path
- `initialize_app(state)` - Runs database migrations

### Service Commands (to be implemented)
The frontend services reference additional commands that need backend implementation:
- `capture_url`, `create_note` - Document capture
- `get_documents`, `get_document`, `delete_document`, `search_documents` - Document CRUD
- `get_review_queue`, `submit_review` - SRS operations
- `get_reflection`, `save_reflection` - Reflection operations
- `quick_digest`, `get_analysis` - AI analysis
- `get_settings`, `save_api_key` - Settings management

## State Management Pattern

Zustand store in `src/store/index.ts` with:
- **Persistent state** (localStorage): `apiKey`, `settings`
- **Non-persistent state**: Current view, modals, loaded data

State structure includes:
- Navigation (`currentView`: 'library' | 'today' | 'review' | 'reflection' | 'settings')
- Documents array and selected document
- Analysis state (`currentAnalysis`, `isAnalyzing`)
- Review queue
- Settings with defaults (daily goals, notification preferences)
- UI state (modal open/close)

## Database Schema

SQLite database with 4 main tables (defined in `src-tauri/src/services/database.rs`):

```sql
-- Documents table
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,  -- 'url' or 'note'
    title TEXT NOT NULL,
    url TEXT,
    content TEXT,
    captured_at TEXT NOT NULL,
    clean_text_path TEXT,
    raw_html_path TEXT,
    status TEXT DEFAULT 'captured',
    topics TEXT,  -- JSON array
    entities TEXT,  -- JSON array
    word_count INTEGER DEFAULT 0
);

-- Analysis results
CREATE TABLE analyses (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    mode TEXT NOT NULL,  -- 'quick' or 'deep'
    created_at TEXT NOT NULL,
    cost_ms INTEGER,
    result_json TEXT NOT NULL
);

-- SRS review schedule
CREATE TABLE review_schedule (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,  -- 'vocab' or 'insight'
    item_id TEXT NOT NULL,
    item_type TEXT NOT NULL,
    front TEXT NOT NULL,
    back TEXT NOT NULL,
    context TEXT,
    due_at TEXT NOT NULL,
    interval_days INTEGER DEFAULT 0,
    ease REAL DEFAULT 2.5,  -- SM-2 ease factor
    last_score INTEGER,
    streak INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

-- Daily reflections
CREATE TABLE reflections (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL UNIQUE,  -- YYYY-MM-DD
    key_win TEXT,
    avoidance TEXT,
    next_fix TEXT,
    deep_work_min INTEGER DEFAULT 0,
    family_min INTEGER DEFAULT 0,
    sleep_h REAL DEFAULT 7.0,
    notes TEXT,
    created_at TEXT NOT NULL
);
```

Database path: `~/Library/Application Support/FragmentTutor/fragment_tutor.db`

## Keyboard Shortcuts

Implemented in `src/hooks/useShortcuts.ts`:

| Shortcut | Action |
|----------|--------|
| `⌘⇧N` | Open capture modal |
| `⌘⇧R` | Open reflection card |
| `⌘1` | Navigate to Library |
| `⌘2` | Navigate to Today |
| `⌘3` | Navigate to Review |
| `⌘4` | Navigate to Reflection |
| `⌘,` | Navigate to Settings |
| `Esc` | Close modals |

## Configuration

### Environment Variables

Copy `.env.example` to `.env`:

```bash
ANTHROPIC_API_KEY=your-api-key-here
ANTHROPIC_BASE_URL=https://api.anthropic.com
```

### Settings Storage

User settings are persisted via Zustand to localStorage:
- Anthropic API key
- Notification preferences (review reminder, evening reminder, reflection reminder)
- Daily goals (review count, deep work minutes)
- Keyboard shortcut configuration

### Data Storage

Application data is stored locally:
- SQLite database: `~/Library/Application Support/FragmentTutor/fragment_tutor.db`
- Captured content stored as files in same directory
- All data remains on-device (privacy-focused)

## Development Conventions

### Adding New Features

1. **Data Model**: Define TypeScript interface in `src/types/index.ts`, Rust struct in `src-tauri/src/models/mod.rs`
2. **Database**: Add migration in `src-tauri/src/services/database.rs`
3. **Backend Commands**: Implement in appropriate service, register in `lib.rs` via `generate_handler![]`
4. **Frontend Service**: Create/update service in `src/services/`
5. **UI Components**: Build React components using existing patterns
6. **State**: Add to Zustand store if needed

### Error Handling

- **Frontend**: Use try/catch with user-friendly messages in Chinese
- **Backend**: Return `Result<T, String>` from Tauri commands
- **API Calls**: Handle network errors gracefully

### Testing Strategy

Currently minimal testing infrastructure. Recommended approach:
- Rust unit tests for business logic in `src-tauri/src/`
- React Testing Library for components
- Manual testing via `npm run tauri dev`

## Security Considerations

1. **API Keys**: Stored locally in SQLite and localStorage, never transmitted except to Anthropic API
2. **Data Privacy**: All user data stored locally in SQLite
3. **Content Security**: No inline scripts, CSP via Tauri
4. **Network**: Only outbound HTTPS requests for URL capture and AI API

## Known Issues & Limitations

1. **Backend Commands**: Currently minimal - full CRUD operations need implementation in Rust
2. **AI Analysis**: Placeholder implementation in `src-tauri/src/services/anthropic.rs` (returns mock data)
3. **Mobile**: iOS/Android support prepared but not fully implemented
4. **Sync**: No cloud sync capability yet
5. **Stronghold**: API key storage should migrate to Tauri Stronghold for better security

## UI Language

The application interface uses Chinese (简体中文) as the primary language:
- Navigation labels: "知识库", "今日", "复习", "反省", "设置"
- Button labels: "捕获", "60秒反省"
- Date formatting uses Chinese locale via date-fns

## Resources

- [Tauri 2.0 Documentation](https://tauri.app/)
- [React Documentation](https://react.dev/)
- [Tailwind CSS Documentation](https://tailwindcss.com/)
- [Anthropic API Documentation](https://docs.anthropic.com/)
