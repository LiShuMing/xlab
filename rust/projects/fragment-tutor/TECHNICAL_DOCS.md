# FragmentTutor Technical Documentation

## Project Overview


FragmentTutor is a macOS native desktop application for capturing and learning during fragmented time. Built with Tauri 2.0 (Rust + React).

## Architecture

### Frontend (React + TypeScript)

- **Location**: `src/`
- **Framework**: React 18 with Vite 5
- **Styling**: Tailwind CSS 3.4
- **State Management**: Zustand 4.5
- **Routing**: React Router DOM 6.22

### Backend
 (Rust)

- **Location**: `src-tauri/src/`
- **Framework**: Tauri 2.0
- **Database**: SQLite with SQLx
- **HTTP**: Reqwest
- **HTML Parsing**: Scraper 0.25

## Data Models

### Document

```rust
struct Document {
    id: String,
    type_: String,  // "url" or "note"
    title: String,
    url: Option<String>,
    content: Option<String>,
    captured_at: String,
    status: String,
    topics: Vec<String>,
    entities: Vec<String>,
    word_count: i32,
}
```

### ReviewItem (SRS)

```rust
struct ReviewItem {
    id: String,
    type_: String,  // "vocab" or "insight"
    front: String,
    back: String,
    due_at: String,
    interval: i64,  // Days until next review
    ease: f64,      // SM-2 ease factor
    streak: i32,
}
```

### Reflection

```rust
struct Reflection {
    id: String,
    date: String,
    key_win: Option<String>,
    avoidance: Option<String>,
    next_fix: Option<String>,
    deep_work_min: i32,
    family_min: i32,
    sleep_h: f64,
}
```

## Spaced Repetition System (SRS)


Simplified SM-2 Algorithm:
- Intervals: [1, 3, 7, 14, 30] days
- Quality scores: 0-5
- Ease factor adjustment: EF' = EF + (0.1 - (5-Q) × (0.08 + (5-Q) × 0.02))

## Quick Digest Analysis


Anthropic API integration for document analysis:
- **Thesis**: One-sentence summary
- **First Principles**: 3-5 fundamental concepts
- **Counterpoint**: Thoughtful limitation
- **Micro-Actions**: 3-5 actionable items
- **Vocabulary**: 5-10 terms with definitions
- **Key Insights**: 3-5 surprising takeaways
- **Related Topics**: 5-8 topics for exploration

## Database Schema


```sql
-- Documents table
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    content TEXT,
    captured_at TEXT NOT NULL,
    status TEXT DEFAULT 'captured',
    topics TEXT,
    entities TEXT,
    word_count INTEGER DEFAULT 0
);

-- Analysis results
CREATE TABLE analyses (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    created_at TEXT NOT NULL,
    cost_ms INTEGER,
    result_json TEXT NOT NULL
);

-- SRS review schedule
CREATE TABLE review_schedule (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    item_id TEXT NOT NULL,
    item_type TEXT NOT NULL,
    front TEXT NOT NULL,
    back TEXT NOT NULL,
    context TEXT,
    due_at TEXT NOT NULL,
    interval_days INTEGER DEFAULT 0,
    ease REAL DEFAULT 2.5,
    last_score INTEGER,
    streak INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

-- Daily reflections
CREATE TABLE reflections (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL UNIQUE,
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

## Keyboard Shortcuts


| Shortcut | Action |
|----------|--------|
| `⌘⇧N` | Open capture modal |
| `⌘⇧R` | Open reflection card |
| `⌘1` | Navigate to Library |
| `⌘2` | Navigate to Today |
| `⌘3` | Navigate to Review |
| `⌘4` | Navigate to Reflection |
| `⌘,` | Navigate to Settings |

## Build Status

### Frontend

✅ Successfully built
- Location: `dist/`
- Output: Static assets (HTML, JS, CSS)

### Backend (Known Issues)

⚠️ Requires fixes for Tauri 2.0 integration:
1. Command registration conflicts
2. SQLx prepare offline mode
3. Database path resolution

## Configuration

### Environment Variables

```bash
# Optional: Set Anthropic API key
ANTHROPIC_API_KEY=sk-...
```

### Tauri Configuration

- **Window**: 1200x800, resizable, centered
- **Bundle**: macOS .dmg, Windows .msi, Linux .deb
- **Permissions**: Core defaults + notifications

## Dependencies

### Frontend

```json
{
  "react": "^18.2.0",
  "react-router-dom": "^6.22.0",
  "zustand": "^4.5.0",
  "tailwindcss": "^3.4.0",
  "date-fns": "^3.6.0",
  "lucide-react": "^0.344.0"
}
```

### Backend
```toml
[dependencies]
tauri = "2.0.0"
sqlx = "0.7"
reqwest = "0.11"
scraper = "0.25"
chrono = "0.4"
uuid = "1.6"
```

## API Commands (Tauri)

### Document Commands

- `capture_url(url, title)` - Capture URL content
- `create_note(title, content)` - Create manual note
- `get_documents(limit, offset)` - List documents
- `delete_document(id)` - Remove document
- `search_documents(query)` - Search by content

### Analysis Commands

- `quick_digest(document_id, api_key)` - Analyze document
- `get_analysis(document_id)` - Retrieve analysis

### Review Commands

- `get_review_queue()` - Get due reviews
- `submit_review(item_id, score)` - Record review result
- `create_vocab_card(word, definition, context)` - Add vocabulary
- `create_insight_card(insight, context)` - Add insight

### Reflection Commands

- `get_reflection(date)` - Get reflection for date
- `save_reflection(input)` - Save daily reflection
- `get_reflection_stats()` - Get reflection statistics

### Settings Commands

- `get_settings()` - Retrieve settings
- `save_api_key(api_key)` - Store API key

## Known Issues & Solutions

### Issue: SQLx Offline Mode

**Problem**: `cargo sqlx prepare` requires database connection
**Solution**: Set `DATABASE_URL` environment variable before building

### Issue: Duplicate Command Registration

**Problem**: Commands registered multiple times
**Solution**: Ensure single invocation of `generate_handler![]`

### Issue: Tauri Plugin Imports

**Problem**: Plugin crates not found
**Solution**: Use only core Tauri features for MVP

## Future Enhancements (V1)


1. **Stronghold** for secure API key storage
2. **Full CRUD** for all entities
3. **Web content extraction** improvements
4. **iOS/Android** mobile apps (Tauri mobile)
5. **Sync** across devices via cloud storage
6. **Export** to Anki, Obsidian, etc.
7. **Tags** and folder organization
8. **Full-text search** with ranking
9. **Reading time** estimates
10. **Bookmarklets** for browser capture

## License


MIT License - See LICENSE file

## Contributing


1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request
