# TO-FIX

## Known Issues

### Current Limitations
- [ ] No email threading UI in web interface
- [ ] Limited search functionality (only date-based)
- [ ] No email archiving/organization features
- [ ] Digest generation is manual (not automatic)
- [ ] No mobile-responsive design for web UI
- [ ] LLM calls can be slow with large emails
- [ ] No support for attachments
- [ ] SQLite may not scale to 100k+ emails

### Technical Debt
- [ ] Some async functions could be better parallelized
- [ ] Error handling could be more granular
- [ ] Need more comprehensive test coverage
- [ ] Logging could be more structured

## Planned Improvements

### Features
- [ ] **Automatic digest scheduling**
  - Cron-like scheduler for daily digests
  - Email delivery of digests
  - Configurable digest frequency (daily/weekly)

- [ ] **Enhanced search**
  - Full-text search across email content
  - Semantic search with embeddings
  - Filter by sender, topic, date range
  - Search within digests

- [ ] **Email organization**
  - Auto-labeling based on topics
  - Archive old emails
  - Star/favorite important emails
  - Custom folders

- [ ] **Web UI improvements**
  - Email threading view
  - Mobile-responsive design
  - Dark mode
  - Keyboard shortcuts
  - Infinite scroll for inbox

- [ ] **LLM improvements**
  - Support for more models (Claude, Gemini)
  - Streaming summaries
  - Custom summarization prompts
  - Multi-language support

- [ ] **Analytics dashboard**
  - Email volume trends
  - Topic evolution over time
  - Sender statistics
  - Reading patterns

### Technical Improvements
- [ ] **Database migration**
  - PostgreSQL support for scale
  - Migration scripts
  - Connection pooling

- [ ] **Caching layer**
  - Redis for frequent queries
  - Cache digests
  - Cache LLM responses

- [ ] **Background workers**
  - Celery or RQ for async tasks
  - Parallel email processing
  - Queue-based LLM calls

- [ ] **API enhancements**
  - GraphQL API
  - WebSocket for real-time updates
  - Rate limiting
  - API keys for access

### Integrations
- [ ] **More email providers**
  - Outlook/Exchange support
  - IMAP generic support
  - ProtonMail

- [ ] **Notification channels**
  - Slack notifications
  - Discord webhooks
  - Telegram bot
  - WeChat integration

- [ ] **Export options**
  - PDF export
  - Markdown export
  - Notion integration
  - Obsidian export

## Research Areas

- **Embedding-based clustering** for better topic discovery
- **LLM fine-tuning** for email-specific summarization
- **Federated search** across multiple email accounts
- **Privacy-preserving** on-device LLM inference

---

# FIXED

- ✅ Gmail API OAuth integration
- ✅ Incremental sync with historyId
- ✅ HTML to text cleaning
- ✅ SQLite database with WAL mode
- ✅ LLM summarization with structured output
- ✅ Daily digest generation
- ✅ CLI interface with Click
- ✅ Web server with FastAPI
- ✅ Topic tracking and clustering
- ✅ Project discovery from email patterns
- ✅ Jinja2 HTML templates
- ✅ Comprehensive documentation

---

# NOTES

## Design Decisions

### Why SQLite?
- Zero configuration
- Single-file database
- Easy to backup
- Good enough for personal use (< 100k emails)
- Easy to migrate to PostgreSQL later

### Why Ollama/Local LLM?
- Privacy (emails stay local)
- No API costs
- Works offline
- Fast for small models

### Why Gmail API over IMAP?
- OAuth2 is more secure
- History ID for incremental sync
- Better rate limits
- Official SDK support

## Performance Tips

### Database
- Use WAL mode for better concurrency
- Index on frequently queried columns
- Batch inserts for sync

### LLM
- Batch multiple emails for summarization
- Use smaller models for faster inference
- Cache summaries

### Web UI
- Paginate large result sets
- Lazy load email content
- Cache rendered templates

## Scaling Considerations

Current limits:
- SQLite: ~100k emails comfortably
- Single-user design
- Local LLM: depends on hardware

Future scaling:
- PostgreSQL for multi-user
- Redis for caching
- Background workers for processing

## Security Considerations

- Gmail tokens stored in local file
- Database is local SQLite
- LLM calls are local (Ollama) or to configured API
- No data leaves the system except to Gmail API and configured LLM endpoint
