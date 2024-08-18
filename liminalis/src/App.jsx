import {
  ArrowRight,
  BookOpenText,
  Brain,
  CalendarDays,
  ChevronRight,
  Clock3,
  Compass,
  Database,
  ExternalLink,
  FlaskConical,
  HeartHandshake,
  ListTree,
  LineChart,
  Menu,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Sun,
  X,
  Zap,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import pyRadarFeed from './data/pyRadarFeed';

const bookModules = import.meta.glob('../../docs/books/**/*.md', {
  eager: true,
  query: '?raw',
  import: 'default',
});

const reportModules = import.meta.glob('../../docs/reports/**/*.md', {
  eager: true,
  query: '?raw',
  import: 'default',
});

const blogModules = import.meta.glob('../../docs/blogs/**/*.md', {
  eager: true,
  query: '?raw',
  import: 'default',
});

const navItems = [
  {
    label: 'Logos · 理解世界',
    href: '/logos',
    tone: 'blue',
    children: [
      { label: '代码实验室', href: '/logos', description: 'Markdown 开源书籍阅读仓库' },
      { label: '产品报告', href: '/reports', description: '数据库产品调研与深度报告' },
      { label: '博客', href: '/blogs', description: '技术随笔与阅读札记' },
      { label: '数据库动态', href: '/radar', description: '数据库领域动态' },
    ],
  },
  {
    label: 'Praxis · 改变世界',
    href: '/#praxis',
    tone: 'violet',
    children: [
      { label: '价值投资', href: '/invest', description: 'LLM 驱动的长期价值分析报告' },
      { label: '自我对话', href: '/ego', description: '记录、陪伴与长期记忆' },
    ],
  },
  { label: '了解我们', href: '/about', cta: true },
];

function getRouteSnapshot() {
  return {
    pathname: window.location.pathname,
    search: window.location.search,
    hash: window.location.hash,
  };
}

function isPlainLeftClick(event) {
  return event.button === 0 && !event.metaKey && !event.altKey && !event.ctrlKey && !event.shiftKey;
}

function shouldHandleInternalLink(anchor, event) {
  if (!anchor || !isPlainLeftClick(event)) return false;
  if (anchor.target && anchor.target !== '_self') return false;
  if (anchor.hasAttribute('download')) return false;

  const url = new URL(anchor.href, window.location.href);
  if (url.origin !== window.location.origin) return false;
  return (
    url.pathname !== window.location.pathname ||
    url.search !== window.location.search ||
    url.hash !== window.location.hash
  );
}

const tags = ['学习', '探索', '自我', '价值', '开源精神', '人文科技'];

const pillars = [
  {
    icon: Zap,
    number: '01 · 学习',
    title: '深度优先',
    text: '拒绝碎片化内容。我们提供经过筛选的技术深度资料，帮助你真正理解底层原理。',
  },
  {
    icon: Compass,
    number: '02 · 探索',
    title: '边界之外',
    text: '从内核源码到行业趋势，从工程实践到跨界思考，拓展你认知地图的边界。',
  },
  {
    icon: Brain,
    number: '03 · 自我',
    title: '向内生长',
    text: '技术之外，我们也关注内心的声音：情绪、关系、困惑，都值得被认真对待。',
  },
  {
    icon: Sparkles,
    number: '04 · 价值',
    title: '创造意义',
    text: '知识只有被使用才有价值。我们帮助你将所学转化为真实世界中的影响力。',
  },
];

const stats = [
  { value: '8+', label: '主流开源系统深度覆盖' },
  { value: '∞', label: '每一个自我值得被倾听' },
  { value: '0', label: '广告打扰，纯净阅读体验' },
];

const manifestoNotes = [
  {
    label: 'Culture',
    title: '慢下来，深下去',
    text: '我们珍视长期主义、开放笔记和可复用的知识结构。好的文化不是口号，而是一种允许人持续学习、诚实表达、互相启发的环境。',
  },
  {
    label: 'Value',
    title: '把知识变成行动',
    text: '价值不止来自答案，也来自提问、判断和创造。Logos 是理解世界，Praxis 是改变世界；Liminalis 鼓励把洞察转化为真实作品和长期行动。',
  },
  {
    label: 'Self',
    title: '看见更大的自己',
    text: '技术、认知、情绪和表达并不是彼此孤立的能力。我们相信自我成长发生在这些维度的交汇处，也发生在每一次认真面对内心的时候。',
  },
];

const growthDimensions = [
  {
    title: '技术',
    text: '理解系统如何工作，从源码、架构和工程经验中建立稳定的判断力。',
  },
  {
    title: '认知',
    text: '把信息整理成结构，把观点放回上下文，让复杂问题变得可以被反复思考。',
  },
  {
    title: '情绪',
    text: '承认人的脆弱、焦虑与迟疑，在长期成长中保留温度和自我照顾的能力。',
  },
  {
    title: '表达',
    text: '用写作、对话和创造把内在经验变成可分享、可连接、可沉淀的东西。',
  },
];

function basename(path) {
  return path.split('/').pop();
}

function titleizeSlug(slug) {
  return slug
    .split('-')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function bookIdFromPath(path) {
  const parts = path.split('/docs/books/')[1]?.split('/') ?? [];
  return parts.length > 1 ? parts[0] : null;
}

function relativeBookPath(path) {
  const parts = path.split('/docs/books/')[1]?.split('/') ?? [];
  return parts.slice(1).join('/');
}

function chapterOrder(path) {
  const relativePath = relativeBookPath(path);
  if (relativePath === 'README.md') return 0;
  if (isBookMetadataPath(relativePath)) return -1;
  const match = relativePath.match(/(?:^|\/)(?:ch-?|chapter-)(\d+)/i);
  return match ? Number(match[1]) : 999;
}

function isBookMetadataPath(relativePath) {
  return ['README.md', 'SPEC.md', 'TASK_SPEC.md'].includes(relativePath);
}

function compareChapters(a, b) {
  const appendixA = a.relativePath.toLowerCase().startsWith('appendix');
  const appendixB = b.relativePath.toLowerCase().startsWith('appendix');
  if (appendixA !== appendixB) return appendixA ? 1 : -1;
  return a.order - b.order || a.relativePath.localeCompare(b.relativePath);
}

function chapterLabel(chapter, index) {
  const number = chapter.order === 999 ? index + 1 : chapter.order;
  return String(number).padStart(2, '0');
}

function extractTitle(markdown, fallback) {
  return markdown.match(/^#\s+(.+)$/m)?.[1] ?? fallback.replace(/\.md$/, '');
}

function extractExcerpt(markdown) {
  const quote = markdown.match(/^>\s+(.+)$/m)?.[1];
  if (quote) return quote;

  const paragraph = markdown
    .split('\n')
    .map((line) => line.trim())
    .find((line) => line && !line.startsWith('#') && !line.startsWith('|') && !line.startsWith('-'));

  return paragraph ?? 'Markdown knowledge unit ready for structured reading.';
}

function readingMinutes(markdown) {
  const words = markdown.replace(/```[\s\S]*?```/g, '').split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.ceil(words / 380));
}

function normalizeMarkdownForReader(markdown, fallbackTitle) {
  const normalized = markdown.replace(/\r\n/g, '\n').replace(/\u00a0/g, ' ').trim();
  const lines = normalized.split('\n');
  const firstContentIndex = lines.findIndex((line) => line.trim());
  const firstHeadingIndex = lines.findIndex((line) => /^#\s+/.test(line.trim()));

  if (firstHeadingIndex > firstContentIndex) {
    return lines.slice(firstHeadingIndex).join('\n').trim();
  }

  if (firstHeadingIndex === -1 && fallbackTitle) {
    return `# ${fallbackTitle}\n\n${normalized}`;
  }

  return normalized;
}

function relativeDocsPath(path, collection) {
  return path.split(`/docs/${collection}/`)[1] ?? basename(path);
}

function documentCategory(relativePath, fallback = 'Notes') {
  const parts = relativePath.split('/');
  if (parts.length <= 1) return fallback;
  return titleizeSlug(parts[0]);
}

function documentDateSignal(relativePath) {
  return relativePath.match(/20\d{2}/)?.[0] ?? 'Evergreen';
}

function buildDocumentCollection(modules, collection, fallbackCategory) {
  return Object.entries(modules)
    .map(([path, markdown]) => {
      const relativePath = relativeDocsPath(path, collection);
      const fallbackTitle = titleizeSlug(relativePath.replace(/\.md$/, '').replace(/\//g, '-'));
      const readerMarkdown = normalizeMarkdownForReader(markdown, fallbackTitle);
      return {
        id: path,
        title: extractTitle(readerMarkdown, fallbackTitle),
        excerpt: extractExcerpt(readerMarkdown),
        markdown: readerMarkdown,
        relativePath,
        category: documentCategory(relativePath, fallbackCategory),
        filename: basename(path),
        minutes: readingMinutes(readerMarkdown),
        dateSignal: documentDateSignal(relativePath),
      };
    })
    .sort((a, b) => a.category.localeCompare(b.category) || a.title.localeCompare(b.title));
}

const chapters = Object.entries(bookModules)
  .map(([path, markdown]) => ({
    bookId: bookIdFromPath(path),
    id: path,
    filename: basename(path),
    relativePath: relativeBookPath(path),
    order: chapterOrder(path),
    title: extractTitle(markdown, basename(path)),
    excerpt: extractExcerpt(markdown),
    markdown,
    minutes: readingMinutes(markdown),
  }))
  .filter((chapter) => chapter.bookId)
  .sort(compareChapters);

const bookSeriesList = Object.values(
  chapters.reduce((books, chapter) => {
    const book = books[chapter.bookId] ?? {
      id: chapter.bookId,
      title: titleizeSlug(chapter.bookId),
      subtitle: 'Markdown based open book.',
      location: `/Users/lism/work/xlab/docs/books/${chapter.bookId}`,
      minutes: 0,
      chapters: [],
    };

    if (isBookMetadataPath(chapter.relativePath)) {
      book.title = chapter.title;
      book.subtitle = chapter.excerpt;
    } else {
      book.chapters.push(chapter);
      book.minutes += chapter.minutes;
      if (!books[chapter.bookId]) {
        book.subtitle = chapter.excerpt;
      }
    }

    books[chapter.bookId] = book;
    return books;
  }, {}),
).map((book) => ({
  ...book,
  chapters: book.chapters.sort(compareChapters),
})).sort((a, b) => a.id.localeCompare(b.id));

const reportDocuments = buildDocumentCollection(reportModules, 'reports', 'Reports');
const blogDocuments = buildDocumentCollection(blogModules, 'blogs', 'Blogs');

const radarItems = pyRadarFeed.items ?? [];

const radarTypeLabels = {
  release: '发布',
  benchmark: '基准',
  blog: '博客',
  news: '新闻',
  tutorial: '教程',
  engine: '引擎',
  paper: '论文',
  other: '文章',
};

function formatRadarDate(value) {
  if (!value) return 'Unknown';
  const dateValue = new Date(`${value}T00:00:00`);
  if (Number.isNaN(dateValue.getTime())) return value;
  return dateValue.toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
  });
}

function radarTypeLabel(type) {
  return radarTypeLabels[type] ?? type ?? '文章';
}

function radarReadingSignal(item) {
  const text = `${item.title} ${item.summary} ${item.tags?.join(' ') ?? ''}`.toLowerCase();
  if (text.includes('postgres') || text.includes('mysql') || text.includes('query')) return 'Query & Engine';
  if (text.includes('spark') || text.includes('lakehouse') || text.includes('warehouse')) return 'Analytics';
  if (text.includes('release') || text.includes('version') || text.includes('launch')) return 'Release Watch';
  if (text.includes('benchmark') || text.includes('performance')) return 'Performance';
  return 'DB Systems';
}

function fallbackRadarPayload() {
  return {
    items: pyRadarFeed.items ?? [],
    total_items: pyRadarFeed.totalItems ?? pyRadarFeed.items?.length ?? 0,
    products: pyRadarFeed.products ?? [],
    contentTypes: pyRadarFeed.contentTypes ?? [],
    latestSyncBatch: pyRadarFeed.latestSyncBatch,
  };
}

async function fetchJson(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers ?? {}) };
  const response = await fetch(path, {
    credentials: 'include',
    ...options,
    headers,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item) => `${item.loc?.join('.') ?? 'request'}: ${item.msg}`).join('; ')
      : data.detail || data.message || data.error;
    throw new Error(detail ? `Request failed: ${response.status} - ${detail}` : `Request failed: ${response.status}`);
  }
  return data;
}

function Logo({ small = false }) {
  return (
    <a href="/" className={small ? 'logo logo-small' : 'logo'}>
      <span className="logo-mark">L</span>
      <span>Liminalis</span>
    </a>
  );
}

function Header() {
  const [open, setOpen] = useState(false);
  const [activeMenu, setActiveMenu] = useState(null);

  return (
    <header className="site-header">
      <nav className="nav-shell">
        <Logo />
        <div className="nav-links">
          {navItems.map((item) => {
            if (item.children) {
              const expanded = activeMenu === item.label;
              return (
                <div
                  key={item.label}
                  className="nav-menu"
                  onMouseEnter={() => setActiveMenu(item.label)}
                  onMouseLeave={() => setActiveMenu(null)}
                >
                  <a
                    href={item.href}
                    className="nav-link"
                    aria-expanded={expanded}
                    onFocus={() => setActiveMenu(item.label)}
                  >
                    <span className={`nav-dot ${item.tone}`} />
                    {item.label}
                    <ChevronRight size={13} className={expanded ? 'nav-arrow open' : 'nav-arrow'} />
                  </a>
                  {expanded && (
                    <div className="nav-dropdown">
                      {item.children.map((child) => (
                        <a key={child.label} href={child.href} onClick={() => setActiveMenu(null)}>
                          <strong>{child.label}</strong>
                          <span>{child.description}</span>
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              );
            }

            return (
              <a key={item.label} href={item.href} className={item.cta ? 'nav-cta' : 'nav-link'}>
                {!item.cta && <span className={`nav-dot ${item.tone}`} />}
                {item.label}
              </a>
            );
          })}
        </div>
        <button
          type="button"
          className="mobile-menu"
          onClick={() => setOpen((value) => !value)}
          aria-label="Toggle navigation"
        >
          {open ? <X size={18} /> : <Menu size={18} />}
        </button>
      </nav>
      {open && (
        <div className="mobile-panel">
          {navItems.map((item) => (
            <div key={item.label} className="mobile-nav-group">
              <a href={item.href} onClick={() => setOpen(false)}>
                {item.label}
              </a>
              {item.children?.map((child) => (
                <a key={child.label} href={child.href} className="mobile-sub-link" onClick={() => setOpen(false)}>
                  {child.label}
                </a>
              ))}
            </div>
          ))}
        </div>
      )}
    </header>
  );
}

function SectionLabel({ children }) {
  return <p className="section-label">{children}</p>;
}

function renderInline(text) {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\))/g);

  return parts.map((part, index) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={index}>{part.slice(1, -1)}</code>;
    }
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={index}>{part.slice(1, -1)}</em>;
    }
    const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (link) {
      return (
        <a key={index} href={link[2]} target="_blank" rel="noreferrer">
          {link[1]}
        </a>
      );
    }
    return part;
  });
}

const codeKeywords = new Set([
  'async',
  'await',
  'boolean',
  'break',
  'class',
  'const',
  'continue',
  'else',
  'export',
  'extends',
  'false',
  'for',
  'from',
  'function',
  'if',
  'import',
  'interface',
  'let',
  'new',
  'null',
  'number',
  'return',
  'string',
  'true',
  'type',
  'undefined',
  'while',
]);

function highlightCodeLine(line) {
  const parts = [];
  let cursor = 0;
  const tokenPattern = /(\/\/.*|(['"`])(?:\\.|(?!\2).)*\2|\b\d+(?:\.\d+)?\b|\b[A-Za-z_$][\w$]*\b)/g;

  line.replace(tokenPattern, (match, token, quote, offset) => {
    if (offset > cursor) {
      parts.push(line.slice(cursor, offset));
    }

    let className = 'syntax-plain';
    if (match.startsWith('//')) {
      className = 'syntax-comment';
    } else if (quote) {
      className = 'syntax-string';
    } else if (/^\d/.test(match)) {
      className = 'syntax-number';
    } else if (codeKeywords.has(match)) {
      className = 'syntax-keyword';
    } else if (/^[A-Z]/.test(match)) {
      className = 'syntax-type';
    }

    parts.push(
      <span key={`${offset}-${match}`} className={className}>
        {match}
      </span>,
    );
    cursor = offset + match.length;
    return match;
  });

  if (cursor < line.length) {
    parts.push(line.slice(cursor));
  }

  return parts;
}

function HighlightedCode({ code }) {
  const lines = code.split('\n');

  return lines.map((line, index) => (
    <span key={index} className="code-line">
      {highlightCodeLine(line)}
      {index < lines.length - 1 ? '\n' : ''}
    </span>
  ));
}

function MarkdownReader({ markdown }) {
  const lines = markdown.split('\n');
  const blocks = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      blocks.push({ type: 'hr' });
      index += 1;
      continue;
    }

    if (trimmed.startsWith('```')) {
      const language = trimmed.replace('```', '').trim();
      const code = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith('```')) {
        code.push(lines[index]);
        index += 1;
      }
      blocks.push({ type: 'code', language, content: code.join('\n') });
      index += 1;
      continue;
    }

    if (trimmed.startsWith('|')) {
      const rows = [];
      while (index < lines.length && lines[index].trim().startsWith('|')) {
        rows.push(lines[index].trim());
        index += 1;
      }
      blocks.push({ type: 'table', rows });
      continue;
    }

    if (trimmed.startsWith('- ') || /^\d+\.\s+/.test(trimmed)) {
      const ordered = /^\d+\.\s+/.test(trimmed);
      const items = [];
      while (
        index < lines.length &&
        (ordered ? /^\d+\.\s+/.test(lines[index].trim()) : lines[index].trim().startsWith('- '))
      ) {
        items.push(lines[index].trim().replace(ordered ? /^\d+\.\s+/ : /^-\s+/, ''));
        index += 1;
      }
      blocks.push({ type: ordered ? 'ordered-list' : 'list', items });
      continue;
    }

    if (trimmed.startsWith('>')) {
      const quotes = [];
      while (index < lines.length && lines[index].trim().startsWith('>')) {
        quotes.push(lines[index].trim().replace(/^>\s?/, ''));
        index += 1;
      }
      blocks.push({ type: 'quote', content: quotes.join(' ') });
      continue;
    }

    if (/^\*\[[^\]]+\]:/.test(trimmed)) {
      const notes = [];
      while (index < lines.length && /^\*\[[^\]]+\]:/.test(lines[index].trim())) {
        notes.push(lines[index].trim().replace(/^\*/, ''));
        index += 1;
      }
      blocks.push({ type: 'footnotes', notes });
      continue;
    }

    if (trimmed.startsWith('#')) {
      const level = trimmed.match(/^#+/)?.[0].length ?? 1;
      blocks.push({ type: 'heading', level, content: trimmed.replace(/^#+\s*/, '') });
      index += 1;
      continue;
    }

    const paragraph = [trimmed];
    index += 1;
    while (
      index < lines.length &&
      lines[index].trim() &&
      !lines[index].trim().match(/^(#|>|\s*- |\s*\d+\.\s+|\||```|-{3,}|\*{3,}|_{3,})/)
    ) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    blocks.push({ type: 'paragraph', content: paragraph.join(' ') });
  }

  return (
    <article className="markdown-reader">
      {blocks.map((block, idx) => {
        if (block.type === 'heading') {
          const Tag = `h${Math.min(block.level, 3)}`;
          return <Tag key={idx}>{renderInline(block.content)}</Tag>;
        }
        if (block.type === 'quote') {
          return <blockquote key={idx}>{renderInline(block.content)}</blockquote>;
        }
        if (block.type === 'list' || block.type === 'ordered-list') {
          const Tag = block.type === 'ordered-list' ? 'ol' : 'ul';
          return (
            <Tag key={idx}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderInline(item)}</li>
              ))}
            </Tag>
          );
        }
        if (block.type === 'code') {
          return (
            <div key={idx} className="code-frame">
              {block.language && <span>{block.language}</span>}
              <pre>
                <code>
                  <HighlightedCode code={block.content} />
                </code>
              </pre>
            </div>
          );
        }
        if (block.type === 'footnotes') {
          return (
            <aside key={idx} className="footnote-block">
              {block.notes.map((note, noteIndex) => (
                <p key={noteIndex}>{renderInline(note)}</p>
              ))}
            </aside>
          );
        }
        if (block.type === 'hr') {
          return <hr key={idx} />;
        }
        if (block.type === 'table') {
          const rows = block.rows
            .filter((row) => !/^\|\s*:?-+/.test(row))
            .map((row) =>
              row
                .split('|')
                .slice(1, -1)
                .map((cell) => cell.trim()),
            );
          return (
            <div key={idx} className="table-frame">
              <table>
                {rows[0] && (
                  <thead>
                    <tr>
                      {rows[0].map((cell, cellIndex) => (
                        <th key={cellIndex}>{renderInline(cell)}</th>
                      ))}
                    </tr>
                  </thead>
                )}
                <tbody>
                  {rows.slice(1).map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {row.map((cell, cellIndex) => (
                        <td key={cellIndex}>{renderInline(cell)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        return <p key={idx}>{renderInline(block.content)}</p>;
      })}
    </article>
  );
}

function CodexLibrary() {
  const [activeBookId, setActiveBookId] = useState(bookSeriesList[0]?.id);
  const activeBook = bookSeriesList.find((book) => book.id === activeBookId) ?? bookSeriesList[0];
  const [activeId, setActiveId] = useState(activeBook?.chapters[0]?.id);
  const [readingOpen, setReadingOpen] = useState(false);
  const [tocOpen, setTocOpen] = useState(true);
  const [readerTheme, setReaderTheme] = useState('dark');
  const readerRef = useRef(null);
  const activeChapter = activeBook?.chapters.find((chapter) => chapter.id === activeId) ?? activeBook?.chapters[0];
  const chapterIndex = activeBook?.chapters.findIndex((chapter) => chapter.id === activeChapter?.id) ?? 0;
  const progress = activeBook?.chapters.length ? Math.round(((chapterIndex + 1) / activeBook.chapters.length) * 100) : 0;

  useEffect(() => {
    if (readerRef.current) {
      readerRef.current.scrollTop = 0;
    }
  }, [activeId]);

  useEffect(() => {
    if (activeBook?.chapters.length && !activeBook.chapters.some((chapter) => chapter.id === activeId)) {
      setActiveId(activeBook.chapters[0].id);
    }
  }, [activeBook, activeId]);

  if (!activeBook || !activeChapter) {
    return (
      <section id="codex" className="codex-section codex-shelf-section">
        <div className="codex-heading">
          <div>
            <SectionLabel>Logos · 理解世界</SectionLabel>
            <h2>书架暂时为空</h2>
          </div>
          <p>请在 /Users/lism/work/xlab/docs/books 下添加书籍目录和 Markdown 章节。</p>
        </div>
      </section>
    );
  }

  if (!readingOpen) {
    return (
      <section id="codex" className="codex-section codex-shelf-section">
        <div className="codex-heading">
          <div>
            <SectionLabel>Logos · 理解世界</SectionLabel>
            <h2>
              选择一本书，
              <span className="gradient-text">进入深度阅读</span>
            </h2>
          </div>
          <p>
            Logos 用书架组织开源书籍、技术资料与源码研究笔记。每个书目都来自可版本化的 Markdown 目录，先收藏，再展开为沉浸阅读。
          </p>
        </div>

        <div className="bookshelf">
          {bookSeriesList.map((book, index) => (
            <button
              type="button"
              key={book.id}
              className={index === 0 ? 'book-card featured' : 'book-card'}
              onClick={() => {
                setActiveBookId(book.id);
                setActiveId(book.chapters[0]?.id);
                setReadingOpen(true);
              }}
            >
              <span className="book-status">{index === 0 ? '当前可读' : 'Open book'}</span>
              <div className="book-cover">
                <p>Logos Series</p>
                <h3>{book.title}</h3>
                <span>{book.id}</span>
              </div>
              <div className="book-info">
                <div>
                  <p>书籍系列</p>
                  <h3>{book.title}</h3>
                </div>
                <p>{book.subtitle}</p>
                <div className="book-meta">
                  <span>{book.chapters.length} chapters</span>
                  <span>{book.minutes} min read</span>
                  <span>{book.location}</span>
                </div>
              </div>
              <span className="book-action">
                开始阅读 <ArrowRight size={16} />
              </span>
            </button>
          ))}
        </div>
      </section>
    );
  }

  return (
    <section
      id="codex"
      className={`codex-section codex-reading-section reader-${readerTheme}`}
    >
      <div className="reading-header">
        <div>
          <SectionLabel>Logos · 理解世界</SectionLabel>
          <h2>{activeBook.title}</h2>
        </div>
        <div className="reading-controls">
          <button
            type="button"
            onClick={() => setReaderTheme((value) => (value === 'dark' ? 'light' : 'dark'))}
          >
            {readerTheme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            {readerTheme === 'dark' ? '明亮模式' : '暗色模式'}
          </button>
          <button type="button" className="back-to-shelf" onClick={() => setReadingOpen(false)}>
            返回书架
          </button>
        </div>
      </div>

      <div className={tocOpen ? 'codex-workspace reading-workspace' : 'codex-workspace reading-workspace toc-collapsed'}>
        <aside className={tocOpen ? 'chapter-panel' : 'chapter-panel collapsed'}>
          <div className="panel-topline chapter-topline">
            <div>
              <ListTree size={17} />
              <span>Chapters</span>
            </div>
            <button type="button" onClick={() => setTocOpen((value) => !value)}>
              {tocOpen ? <PanelLeftClose size={15} /> : <PanelLeftOpen size={15} />}
              <span>{tocOpen ? '隐藏目录' : '显示目录'}</span>
            </button>
          </div>
          {tocOpen && (
            <div className="chapter-list">
              {activeBook.chapters.map((chapter, index) => (
                <button
                  type="button"
                  key={chapter.id}
                  className={chapter.id === activeChapter.id ? 'chapter-item active' : 'chapter-item'}
                  onClick={() => setActiveId(chapter.id)}
                >
                  <span>{chapterLabel(chapter, index)}</span>
                  <strong>{chapter.title}</strong>
                  <small>{chapter.relativePath}</small>
                  {chapter.id === activeChapter.id && <ChevronRight size={15} />}
                </button>
              ))}
            </div>
          )}
        </aside>

        <section className="reader-panel" ref={readerRef}>
          <div className="reader-toolbar">
            <div>
              <span>Markdown Reader</span>
              <strong>{activeChapter.relativePath}</strong>
            </div>
            <div className="reader-meta">
              <span>
                <Clock3 size={14} />
                {activeChapter.minutes} min
              </span>
              <span>{progress}%</span>
            </div>
          </div>
          <div className="progress-line">
            <span style={{ width: `${progress}%` }} />
          </div>
          <div className="reader-intro">
            <p>Selected Chapter</p>
            <h3>{activeChapter.title}</h3>
            <span>{activeChapter.excerpt}</span>
          </div>
          <MarkdownReader markdown={activeChapter.markdown} />
        </section>
      </div>
    </section>
  );
}

function SiteFooter() {
  return (
    <footer>
      <Logo small />
      <div className="footer-links">
        <a href="/logos">Logos 理解世界</a>
        <a href="/#praxis">Praxis 改变世界</a>
        <a href="/about">关于我们</a>
        <a href="mailto:ming.moriarty@gmail.com">联系</a>
      </div>
      <p>© 2026 Liminalis. 为自驱者而建。</p>
    </footer>
  );
}

function AboutContent({ compact = false }) {
  return (
    <section id="manifesto" className={compact ? 'manifesto manifesto-preview' : 'manifesto about-manifesto'}>
      <div className="manifesto-inner">
        <SectionLabel>了解我们 · About Liminalis</SectionLabel>
        <h2 className="manifesto-quote">
          Liminalis is a space for
          <br />
          <span className="gradient-text">knowledge, self-discovery,</span>
          <br />
          and meaningful growth.
        </h2>
        <p className="manifesto-body manifesto-lead">
          Liminalis 是一个面向知识、探索与自我成长的空间。
          <br />
          我们帮助个体在技术、认知、情绪和表达中持续成长，发现更大的自我价值。
          <br />
          Logos 是理解世界，Praxis 是改变世界。
        </p>

        {!compact && (
          <>
            <h3 className="manifesto-subquote">
              我们活在一个<span className="gradient-text">信息过剩</span>、
              <br />
              <span className="gradient-text">意义匮乏</span>的时代。
            </h3>
            <p className="manifesto-body">
              工程师需要的不只是文档，而是能够激发思考的视角；
              <br />
              每个人需要的不只是答案，而是理解问题的勇气。
              <br />
              <br />
              Liminalis 不做流量的搬运工。
              <br />
              我们是一群相信「慢即是快」的建造者，
              <br />
              致力于打造一个让你愿意停下来、真正思考的空间。
            </p>
            <div className="name-pair">
              <article>
                <p>Logos</p>
                <h4>理解世界</h4>
                <span>知识、语言、理性与结构。它帮助我们读懂技术系统，也帮助我们整理经验、建立判断。</span>
              </article>
              <article>
                <p>Praxis</p>
                <h4>改变世界</h4>
                <span>实践、行动、表达与创造。它让理解不止停留在脑中，而是先改变自己，再进入生活、关系和真实作品。</span>
              </article>
            </div>
          </>
        )}

        <div className="manifesto-grid">
          {manifestoNotes.map((note) => (
            <article key={note.label} className="manifesto-card">
              <p>{note.label}</p>
              <h4>{note.title}</h4>
              <span>{note.text}</span>
            </article>
          ))}
        </div>

        {!compact && (
          <div className="growth-panel">
            <div>
              <SectionLabel>成长维度</SectionLabel>
              <h3>技术、认知、情绪和表达，应该共同长大。</h3>
            </div>
            <div className="growth-grid">
              {growthDimensions.map((item) => (
                <article key={item.title}>
                  <h4>{item.title}</h4>
                  <p>{item.text}</p>
                </article>
              ))}
            </div>
          </div>
        )}

        {compact && (
          <a href="/about" className="manifesto-link">
            阅读完整介绍 <ArrowRight size={15} />
          </a>
        )}
      </div>
    </section>
  );
}

function RadarPage() {
  const [query, setQuery] = useState('');
  const [activeType, setActiveType] = useState('all');
  const [activeProduct, setActiveProduct] = useState('all');
  const [feedPayload, setFeedPayload] = useState(fallbackRadarPayload);
  const [feedLoading, setFeedLoading] = useState(true);
  const [feedError, setFeedError] = useState('');
  const [adminOpen, setAdminOpen] = useState(false);
  const [adminUser, setAdminUser] = useState(null);
  const [loginForm, setLoginForm] = useState({ username: 'admin', password: '' });
  const [linkForm, setLinkForm] = useState({ url: '', product: '', source: '', tags: '', note: '' });
  const [job, setJob] = useState(null);
  const [adminError, setAdminError] = useState('');
  const typeFilters = ['all', ...new Set((feedPayload.contentTypes ?? []).map((item) => item.name).filter(Boolean))].slice(0, 7);
  const productFilters = (feedPayload.products ?? []).slice(0, 10);
  const visibleItems = feedPayload.items ?? [];

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({
      page: '1',
      per_page: '80',
      type: activeType,
      product: activeProduct,
      q: query,
    });

    setFeedLoading(true);
    fetchJson(`/api/radar/items?${params.toString()}`)
      .then((data) => {
        if (!cancelled) {
          setFeedPayload({
            ...data,
            latestSyncBatch: data.latestSyncBatch ?? pyRadarFeed.latestSyncBatch,
          });
          setFeedError('');
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setFeedPayload(fallbackRadarPayload());
          setFeedError(error.message);
        }
      })
      .finally(() => {
        if (!cancelled) setFeedLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeType, activeProduct, query]);

  useEffect(() => {
    fetchJson('/api/admin/me')
      .then((data) => {
        if (data.authenticated) setAdminUser(data.user);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!job || ['completed', 'failed', 'duplicate'].includes(job.status) || !adminUser) return undefined;
    const timer = window.setInterval(() => {
      fetchJson(`/api/admin/radar/jobs/${job.id}`)
        .then((data) => {
          setJob(data.job);
          if (['completed', 'duplicate'].includes(data.job.status)) {
            setActiveType('all');
            setActiveProduct('all');
            setQuery('');
          }
        })
        .catch((error) => setAdminError(error.message));
    }, 1600);
    return () => window.clearInterval(timer);
  }, [job, adminUser]);

  async function refreshFeed() {
    const data = await fetchJson('/api/radar/items?page=1&per_page=80&type=all&product=all&q=');
    setFeedPayload({
      ...data,
      latestSyncBatch: data.latestSyncBatch ?? pyRadarFeed.latestSyncBatch,
    });
  }

  async function handleLogin(event) {
    event.preventDefault();
    setAdminError('');
    try {
      const data = await fetchJson('/api/admin/login', {
        method: 'POST',
        body: JSON.stringify(loginForm),
      });
      setAdminUser(data.user);
    } catch (error) {
      setAdminError(error.message);
    }
  }

  async function handleSubmitLink(event) {
    event.preventDefault();
    setAdminError('');
    try {
      const tags = linkForm.tags
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean);
      const data = await fetchJson('/api/admin/radar/links', {
        method: 'POST',
        body: JSON.stringify({ ...linkForm, tags }),
      });
      setJob(data.job);
    } catch (error) {
      setAdminError(error.message);
    }
  }

  return (
    <main className="radar-page">
      <Header />
      <section className="radar-hero">
        <div className="radar-hero-copy">
          <SectionLabel>Logos · 理解世界</SectionLabel>
          <h1>
            数据库动态
          </h1>
          <p>
            把数据库世界里值得停下来的变化，整理成一条安静的研究流：新版本、架构文章、性能讨论和工程实践，都可以按主题与来源慢慢读。
          </p>
          {feedError && <p className="radar-api-note">当前使用本地快照，服务端暂不可用：{feedError}</p>}
        </div>
        <div className="radar-hero-panel">
          <div>
            <Database size={18} />
            <span>动态收录</span>
          </div>
          <strong>{feedPayload.total_items ?? pyRadarFeed.totalItems}</strong>
          <p>条内容</p>
          <small>更新批次 · {feedPayload.latestSyncBatch ?? pyRadarFeed.latestSyncBatch}</small>
        </div>
      </section>

      <section className="radar-shell">
        <aside className="radar-sidebar">
          <div className="radar-search">
            <Search size={17} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索产品、主题或关键词"
            />
          </div>

          <div className="radar-filter-group">
            <p>Content type</p>
            <div className="radar-type-tabs">
              {typeFilters.map((type) => (
                <button
                  type="button"
                  key={type}
                  className={activeType === type ? 'active' : ''}
                  onClick={() => setActiveType(type)}
                >
                  {type === 'all' ? '全部' : radarTypeLabel(type)}
                </button>
              ))}
            </div>
          </div>

          <div className="radar-filter-group">
            <p>Top sources</p>
            <button
              type="button"
              className={activeProduct === 'all' ? 'radar-source active' : 'radar-source'}
              onClick={() => setActiveProduct('all')}
            >
              <span>All sources</span>
              <small>{pyRadarFeed.totalItems}</small>
            </button>
            {productFilters.map((product) => (
              <button
                type="button"
                key={product.name}
                className={activeProduct === product.name ? 'radar-source active' : 'radar-source'}
                onClick={() => setActiveProduct(product.name)}
              >
                <span>{product.name}</span>
                <small>{product.count}</small>
              </button>
            ))}
          </div>
        </aside>

        <section className="radar-feed">
          <div className="radar-feed-top">
            <div>
              <SectionLabel>Feed</SectionLabel>
              <h2>{feedPayload.total_items ?? visibleItems.length} 条数据库动态</h2>
            </div>
            <button type="button" className="radar-admin-button" onClick={() => setAdminOpen(true)}>
              <Plus size={15} />
              添加动态
            </button>
          </div>

          <div className="radar-feed-list">
            {feedLoading && <div className="radar-loading">正在同步数据库动态...</div>}
            {visibleItems.map((item) => (
              <article key={item.id} className="radar-item">
                <div className="radar-item-date">
                  <CalendarDays size={15} />
                  <span>{formatRadarDate(item.publishedDate)}</span>
                </div>
                <div className="radar-item-main">
                  <div className="radar-item-meta">
                    <span>{item.product}</span>
                    <span>{radarTypeLabel(item.contentType)}</span>
                    <span>{radarReadingSignal(item)}</span>
                  </div>
                  <h3>
                    <a href={item.url} target="_blank" rel="noreferrer">
                      {item.title}
                    </a>
                  </h3>
                  {item.originalTitle !== item.title && <p className="radar-original">{item.originalTitle}</p>}
                  <p className="radar-summary">{item.summary || '暂无摘要，保留原始链接以便继续阅读。'}</p>
                  <div className="radar-tags">
                    {(item.tags?.length ? item.tags : [item.site]).slice(0, 5).map((tag) => (
                      <span key={`${item.id}-${tag}`}>{tag}</span>
                    ))}
                  </div>
                </div>
                <a className="radar-open" href={item.url} target="_blank" rel="noreferrer" aria-label="Open source">
                  <ExternalLink size={16} />
                </a>
              </article>
            ))}
          </div>
        </section>
      </section>

      {adminOpen && (
        <div className="radar-admin-overlay">
          <aside className="radar-admin-drawer">
            <div className="radar-admin-head">
              <div>
                <SectionLabel>Admin</SectionLabel>
                <h2>添加动态</h2>
              </div>
              <button type="button" onClick={() => setAdminOpen(false)} aria-label="Close admin">
                <X size={18} />
              </button>
            </div>

            {!adminUser ? (
              <form className="radar-admin-form" onSubmit={handleLogin}>
                <label>
                  管理员
                  <input
                    value={loginForm.username}
                    onChange={(event) => setLoginForm({ ...loginForm, username: event.target.value })}
                  />
                </label>
                <label>
                  密码
                  <input
                    type="password"
                    value={loginForm.password}
                    onChange={(event) => setLoginForm({ ...loginForm, password: event.target.value })}
                  />
                </label>
                <button type="submit">
                  <ShieldCheck size={15} />
                  登录
                </button>
              </form>
            ) : (
              <form className="radar-admin-form" onSubmit={handleSubmitLink}>
                <label>
                  URL
                  <input
                    required
                    value={linkForm.url}
                    placeholder="https://..."
                    onChange={(event) => setLinkForm({ ...linkForm, url: event.target.value })}
                  />
                </label>
                <label>
                  产品，可选
                  <input
                    value={linkForm.product}
                    onChange={(event) => setLinkForm({ ...linkForm, product: event.target.value })}
                  />
                </label>
                <label>
                  来源，可选
                  <input
                    value={linkForm.source}
                    onChange={(event) => setLinkForm({ ...linkForm, source: event.target.value })}
                  />
                </label>
                <label>
                  标签，可选
                  <input
                    value={linkForm.tags}
                    placeholder="optimizer, storage"
                    onChange={(event) => setLinkForm({ ...linkForm, tags: event.target.value })}
                  />
                </label>
                <label>
                  备注，可选
                  <textarea
                    value={linkForm.note}
                    onChange={(event) => setLinkForm({ ...linkForm, note: event.target.value })}
                  />
                </label>
                <button type="submit">
                  <Plus size={15} />
                  开始分析
                </button>
              </form>
            )}

            {adminError && <p className="radar-admin-error">{adminError}</p>}
            {job && (
              <div className="radar-job-card">
                <p>处理状态</p>
                <h3>{job.status}</h3>
                <span>{job.url}</span>
                {job.error && <strong>{job.error}</strong>}
                {['completed', 'duplicate'].includes(job.status) && (
                  <button type="button" onClick={refreshFeed}>
                    刷新动态
                  </button>
                )}
              </div>
            )}
          </aside>
        </div>
      )}

      <SiteFooter />
    </main>
  );
}

function AboutPage() {
  return (
    <main className="about-page">
      <Header />
      <AboutContent />
      <SiteFooter />
    </main>
  );
}

function CodexPage() {
  return (
    <main className="codex-page">
      <Header />
      <CodexLibrary />
      <SiteFooter />
    </main>
  );
}

function KnowledgeCollectionPage({ type }) {
  const isReports = type === 'reports';
  const documents = isReports ? reportDocuments : blogDocuments;
  const [activeCategory, setActiveCategory] = useState('all');
  const [activeId, setActiveId] = useState(null);
  const activeDocument = documents.find((item) => item.id === activeId);
  const categories = ['all', ...new Set(documents.map((item) => item.category))];
  const visibleDocuments =
    activeCategory === 'all' ? documents : documents.filter((item) => item.category === activeCategory);
  const pageTitle = isReports ? '产品报告' : '博客';
  const pageCopy = isReports
    ? '围绕数据库与数据基础设施产品，沉淀调研报告、版本演进、架构分析和竞品观察。'
    : '保留一些更松弛的技术随笔、阅读笔记和阶段性思考，让理解不只停在正式报告里。';
  const location = isReports ? '/Users/lism/work/xlab/docs/reports' : '/Users/lism/work/xlab/docs/blogs';

  if (activeDocument) {
    return (
      <main className="knowledge-page">
        <Header />
        <section className="knowledge-reader">
          <div className="reading-header">
            <div>
              <SectionLabel>Logos · {pageTitle}</SectionLabel>
              <h2>{activeDocument.title}</h2>
            </div>
            <div className="reading-controls">
              <button type="button" className="back-to-shelf" onClick={() => setActiveId(null)}>
                返回列表
              </button>
            </div>
          </div>
          <section className="reader-panel knowledge-reader-panel">
            <div className="reader-toolbar">
              <div>
                <span>Markdown Reader</span>
                <strong>{activeDocument.relativePath}</strong>
              </div>
              <div className="reader-meta">
                <span>
                  <Clock3 size={14} />
                  {activeDocument.minutes} min
                </span>
                <span>{activeDocument.category}</span>
              </div>
            </div>
            <div className="reader-intro">
              <p>{activeDocument.dateSignal}</p>
              <span>{activeDocument.excerpt}</span>
            </div>
            <MarkdownReader markdown={activeDocument.markdown} />
          </section>
        </section>
        <SiteFooter />
      </main>
    );
  }

  return (
    <main className="knowledge-page">
      <Header />
      <section className="knowledge-hero">
        <div>
          <SectionLabel>Logos · 理解世界</SectionLabel>
          <h1>{pageTitle}</h1>
          <p>{pageCopy}</p>
        </div>
        <aside>
          <span>{documents.length}</span>
          <p>{isReports ? 'research notes' : 'essays'}</p>
          <small>{location}</small>
        </aside>
      </section>

      <section className="knowledge-shell">
        <div className="knowledge-filter">
          {categories.map((category) => (
            <button
              type="button"
              key={category}
              className={activeCategory === category ? 'active' : ''}
              onClick={() => setActiveCategory(category)}
            >
              {category === 'all' ? '全部' : category}
            </button>
          ))}
        </div>

        <div className={isReports ? 'knowledge-grid reports-grid' : 'knowledge-grid blogs-grid'}>
          {visibleDocuments.map((item) => (
            <button type="button" key={item.id} className="knowledge-card" onClick={() => setActiveId(item.id)}>
              <div className="knowledge-card-top">
                <span>{item.category}</span>
                <small>{item.minutes} min</small>
              </div>
              <h2>{item.title}</h2>
              <p>{item.excerpt}</p>
              <div className="knowledge-card-bottom">
                <span>{item.relativePath}</span>
                <ArrowRight size={16} />
              </div>
            </button>
          ))}
        </div>
      </section>
      <SiteFooter />
    </main>
  );
}

function InvestPage() {
  const [stock, setStock] = useState('');
  const [query, setQuery] = useState('请从长期价值投资角度，分析商业模式、护城河、财务质量、估值安全边际、主要风险与合理买入区间。');
  const [analysisMode, setAnalysisMode] = useState('fast');
  const [report, setReport] = useState(null);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');

  const submitAnalysis = async (event) => {
    event.preventDefault();
    if (!stock.trim()) return;

    setStatus('loading');
    setError('');
    setReport(null);

    try {
      const data = await fetchJson('/invest-api/analyze-stock', {
        method: 'POST',
        body: JSON.stringify({
          stock: stock.trim(),
          query,
          lang: 'zh',
          mode: analysisMode,
          use_cache: analysisMode === 'fast',
        }),
      });
      setReport(data);
      setStatus('done');
    } catch (err) {
      setError(err.message);
      setStatus('error');
    }
  };

  const examples = ['AAPL', 'MSFT', 'sh600519', '00700.HK'];

  return (
    <main className="invest-page">
      <Header />
      <section className="invest-hero">
        <div className="invest-hero-copy">
          <SectionLabel>Praxis · 价值投资</SectionLabel>
          <h1>
            把理解，
            <span>转化为判断</span>
          </h1>
          <p>
            复用 py-invest 的数据采集与多 Agent 分析管线，围绕一家企业生成长期价值投资报告。它关注商业模式、财务质量、估值、安全边际与风险，而不是短期交易噪音。
          </p>
        </div>
        <aside className="invest-method">
          <span>Value Lens</span>
          <p>Data collection → specialist agents → synthesis report</p>
          <small>powered by /Users/lism/work/xlab/python/projects/py-invest</small>
        </aside>
      </section>

      <section className="invest-shell">
        <form className="invest-console" onSubmit={submitAnalysis}>
          <div className="invest-console-head">
            <div>
              <LineChart size={22} />
              <h2>价值投资报告生成器</h2>
            </div>
            <span>{status === 'loading' ? '分析中' : 'ready'}</span>
          </div>

          <label>
            股票名称或代码
            <input
              value={stock}
              onChange={(event) => setStock(event.target.value)}
              placeholder="例如 AAPL / MSFT / sh600519 / 00700.HK"
            />
          </label>

          <div className="invest-examples">
            {examples.map((item) => (
              <button type="button" key={item} onClick={() => setStock(item)}>
                {item}
              </button>
            ))}
          </div>

          <label>
            分析重点
            <textarea value={query} onChange={(event) => setQuery(event.target.value)} rows={4} />
          </label>

          <div className="invest-mode">
            <button
              type="button"
              className={analysisMode === 'fast' ? 'active' : ''}
              onClick={() => setAnalysisMode('fast')}
            >
              快速
              <span>一次综合 LLM，适合交互</span>
            </button>
            <button
              type="button"
              className={analysisMode === 'deep' ? 'active' : ''}
              onClick={() => setAnalysisMode('deep')}
            >
              深度
              <span>多 Agent + 长报告，默认重新生成</span>
            </button>
          </div>

          <button type="submit" className="btn-primary invest-submit" disabled={status === 'loading' || !stock.trim()}>
            <Sparkles size={16} />
            {status === 'loading' ? '正在生成报告...' : '生成价值投资报告'}
          </button>

          {error && <p className="invest-error">分析失败：{error}</p>}
          <p className="invest-note">报告由 AI 生成，仅用于研究和思考，不构成投资建议。</p>
        </form>

        <div className="invest-preview">
          {!report && status !== 'loading' && (
            <div className="invest-empty">
              <SectionLabel>Output</SectionLabel>
              <h2>输入股票后，这里会展开完整报告。</h2>
              <p>
                快速模式会采集价格、K 线、财务指标和新闻后直接生成一份价值投资报告；深度模式会再进入技术面、基本面、风险和行业 Agent 并行分析。
              </p>
            </div>
          )}

          {status === 'loading' && (
            <div className="invest-loading">
              <span />
              <h2>正在生成投资报告</h2>
              <p>LLM 分析通常需要几十秒，请保持 py-invest server 运行。</p>
            </div>
          )}

          {report?.markdown && (
            <section className="reader-panel invest-report">
              <div className="reader-toolbar">
                <div>
                  <span>Investment Report</span>
                  <strong>{report.stock}</strong>
                </div>
                <div className="reader-meta">
                  {report.cached && <span>cached</span>}
                  {report.mode && <span>{report.mode}</span>}
                  {report.rating && <span>{report.rating}</span>}
                  {report.duration && <span>{report.duration}s</span>}
                </div>
              </div>
              <MarkdownReader markdown={report.markdown} />
            </section>
          )}
        </div>
      </section>
      <SiteFooter />
    </main>
  );
}

function EgoPage() {
  const [roles, setRoles] = useState([]);
  const [roleStatus, setRoleStatus] = useState('loading');
  const [roleError, setRoleError] = useState('');
  const [jumpingRoleId, setJumpingRoleId] = useState('');

  useEffect(() => {
    let active = true;
    fetchJson('/ego-api/roles')
      .then((data) => {
        if (!active) return;
        setRoles(Array.isArray(data) ? data : []);
        setRoleStatus('ready');
      })
      .catch((err) => {
        if (!active) return;
        setRoleError(err.message);
        setRoleStatus('offline');
      });

    return () => {
      active = false;
    };
  }, []);

  function openPyEgoRole(role) {
    setJumpingRoleId(role.id);
    const pyEgoOrigin = import.meta.env.VITE_PYEGO_H5_ORIGIN || 'http://localhost:5174';
    const roleParam = encodeURIComponent(role.id);
    window.location.href = `${pyEgoOrigin}/#/pages/chat/index?role_id=${roleParam}`;
  }

  const practices = [
    {
      title: '每日记录',
      text: '把情绪、事件和想法沉淀成可回看的素材，让自我理解有连续性。',
    },
    {
      title: '角色陪伴',
      text: '在陪伴者、研究者、咨询师等角色之间切换，用不同视角照亮同一个问题。',
    },
    {
      title: '长期记忆',
      text: '让重要片段被记住、被检索、被重新组织，形成个人成长的第二大脑。',
    },
  ];

  return (
    <main className="ego-page">
      <Header />
      <section className="ego-hero">
        <div className="ego-hero-copy">
          <SectionLabel>Praxis · 自我对话</SectionLabel>
          <h1>
            改变世界前，
            <span>先理解自己</span>
          </h1>
          <p>
            Ego 是 Praxis 的内向维度：它把每日记录、AI 陪伴和长期记忆组织成一套自我实践系统。这里关注的不是效率工具本身，而是一个人如何持续看见自己、整理自己，并把混乱变成行动。
          </p>
          <div className="ego-actions">
            <a href="/invest" className="btn-ghost">
              <LineChart size={16} />
              价值投资
            </a>
            <a href="#ego-roles" className="btn-primary">
              <HeartHandshake size={16} />
              查看角色
            </a>
          </div>
        </div>
        <aside className="ego-panel">
          <span>Ego</span>
          <p>Daily record · AI companion · long memory</p>
          <small>/Users/lism/work/xlab/python/projects/py-ego</small>
        </aside>
      </section>

      <section className="ego-shell">
        <div className="ego-practices">
          {practices.map((item, index) => (
            <article key={item.title}>
              <small>{String(index + 1).padStart(2, '0')}</small>
              <h2>{item.title}</h2>
              <p>{item.text}</p>
            </article>
          ))}
        </div>

        <section id="ego-roles" className="ego-roles">
          <div className="ego-section-head">
            <div>
              <SectionLabel>py-ego roles</SectionLabel>
              <h2>选择一种对话姿态</h2>
            </div>
            <span>{roleStatus === 'ready' ? `${roles.length} roles` : roleStatus}</span>
          </div>

          {roleStatus === 'offline' && (
            <div className="ego-offline">
              <h3>py-ego 后端暂未连接</h3>
              <p>请启动 py-ego-miniapp 服务，Liminalis 会通过 /ego-api 读取角色与后续对话能力。</p>
              <code>{roleError}</code>
            </div>
          )}

          {roleStatus === 'loading' && (
            <div className="ego-loading">
              <span />
              <p>正在读取 py-ego 角色...</p>
            </div>
          )}

          {roleStatus === 'ready' && (
            <div className="ego-role-grid">
              {roles.map((role) => (
                <button
                  type="button"
                  key={role.id}
                  className={jumpingRoleId === role.id ? 'ego-role-card active' : 'ego-role-card'}
                  onClick={() => openPyEgoRole(role)}
                >
                  <div>
                    <span>{role.icon || 'E'}</span>
                    <small>{role.id}</small>
                  </div>
                  <h3>{role.name}</h3>
                  <p>{role.description}</p>
                  <strong>{jumpingRoleId === role.id ? '正在打开 py-ego...' : '进入角色'}</strong>
                </button>
              ))}
            </div>
          )}
        </section>
      </section>
      <SiteFooter />
    </main>
  );
}

function HomePage() {
  return (
    <main id="home">
      <Header />
      <section className="hero">
        <div className="hero-eyebrow reveal">
          <span />
          探索 · 成长 · 创造价值
        </div>
        <h1 className="reveal delay-1">
          每一次学习
          <br />
          都是<span className="gradient-text">向内的发现</span>
        </h1>
        <p className="hero-sub reveal delay-2">
          Liminalis 是一个为自驱者而建的平台：
          <br />
          技术的深度，与人性的温度，在这里并行生长。
        </p>
        <div className="hero-actions reveal delay-3">
          <a href="/logos" className="btn-primary">
            开始探索
          </a>
          <a href="/about" className="btn-ghost">
            我们的理念 <ArrowRight size={15} />
          </a>
        </div>
        <div className="hero-tags reveal delay-3">
          {tags.map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </div>
        <div className="scroll-hint">
          <span />
          scroll
        </div>
      </section>

      <div className="divider" />

      <section className="section">
        <SectionLabel>核心主张</SectionLabel>
        <h2 className="section-title">
          我们相信：<span>真正的成长，从不只发生在屏幕前。</span>
        </h2>
        <div className="pillars">
          {pillars.map((pillar) => {
            const Icon = pillar.icon;
            return (
              <article key={pillar.number} className="pillar">
                <Icon size={28} className="pillar-icon" />
                <p className="pillar-num">{pillar.number}</p>
                <h3>{pillar.title}</h3>
                <p>{pillar.text}</p>
              </article>
            );
          })}
        </div>
      </section>

      <div className="divider" />

      <AboutContent compact />

      <div className="divider" />

      <section id="praxis" className="section section-compact">
        <div className="praxis-heading">
          <div>
            <SectionLabel>Praxis · 改变世界</SectionLabel>
            <h2>
              把洞察，
              <span className="gradient-text">变成行动工具</span>
            </h2>
          </div>
          <p>Praxis 承载那些从理解走向实践的产品：分析、判断、表达与创造。价值投资是第一个实验入口。</p>
        </div>
        <div className="praxis-products">
          <a href="/invest" className="praxis-product-card">
            <div>
              <LineChart size={24} />
              <span>价值投资</span>
            </div>
            <h3>基于 LLM 的企业长期价值分析报告</h3>
            <p>输入股票名称或代码，生成涵盖商业模式、护城河、估值、安全边际和风险的 Markdown 报告。</p>
            <small>
              进入分析页
              <ArrowRight size={14} />
            </small>
          </a>
          <a href="/ego" className="praxis-product-card">
            <div>
              <HeartHandshake size={24} />
              <span>自我对话</span>
            </div>
            <h3>基于记录、角色与长期记忆的自我实践空间</h3>
            <p>把每日片段沉淀下来，与不同 AI 角色对话，让理解自己成为一种可以持续练习的能力。</p>
            <small>
              进入 Ego
              <ArrowRight size={14} />
            </small>
          </a>
        </div>
        <div className="stats-row">
          {stats.map((stat) => (
            <article key={stat.label} className="stat">
              <div>{stat.value}</div>
              <p>{stat.label}</p>
            </article>
          ))}
        </div>
      </section>

      <div className="divider" />

      <section className="cta-band">
        <div className="cta-inner">
          <h2>准备好了吗？</h2>
          <p>
            无论你在寻找技术的深度，
            <br />
            还是内心的宽度：这里都有你的位置。
          </p>
          <div className="cta-actions">
            <a href="/logos" className="btn-primary">
              <BookOpenText size={16} />
              进入 Logos
            </a>
            <a href="#praxis" className="btn-ghost">
              <FlaskConical size={16} />
              探索 Praxis
            </a>
          </div>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
}

function App() {
  const [route, setRoute] = useState(getRouteSnapshot);

  useEffect(() => {
    const syncRoute = () => setRoute(getRouteSnapshot());

    const handleClick = (event) => {
      const anchor = event.target.closest?.('a[href]');
      if (!shouldHandleInternalLink(anchor, event)) return;

      event.preventDefault();
      const url = new URL(anchor.href, window.location.href);
      window.history.pushState({}, '', `${url.pathname}${url.search}${url.hash}`);
      syncRoute();
    };

    document.addEventListener('click', handleClick);
    window.addEventListener('popstate', syncRoute);
    window.addEventListener('hashchange', syncRoute);

    return () => {
      document.removeEventListener('click', handleClick);
      window.removeEventListener('popstate', syncRoute);
      window.removeEventListener('hashchange', syncRoute);
    };
  }, []);

  useEffect(() => {
    if (!route.hash) {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }

    requestAnimationFrame(() => {
      document.getElementById(route.hash.slice(1))?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }, [route.pathname, route.hash]);

  if (route.pathname === '/logos' || route.pathname === '/codex') return <CodexPage />;
  if (route.pathname === '/reports') return <KnowledgeCollectionPage type="reports" />;
  if (route.pathname === '/blogs') return <KnowledgeCollectionPage type="blogs" />;
  if (route.pathname === '/radar') return <RadarPage />;
  if (route.pathname === '/invest') return <InvestPage />;
  if (route.pathname === '/ego') return <EgoPage />;
  if (route.pathname === '/about') return <AboutPage />;
  return <HomePage />;
}

export default App;
