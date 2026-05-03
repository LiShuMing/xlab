import {
  ArrowRight,
  BookOpenText,
  Brain,
  ChevronRight,
  Clock3,
  Compass,
  FlaskConical,
  ListTree,
  Menu,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Sparkles,
  Sun,
  X,
  Zap,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

const bookModules = import.meta.glob('../../docs/books/**/*.md', {
  eager: true,
  query: '?raw',
  import: 'default',
});

const navItems = [
  {
    label: 'Logos · 理解世界',
    href: '/logos',
    tone: 'blue',
    children: [{ label: '代码实验室', href: '/logos', description: 'Markdown 开源书籍阅读仓库' }],
  },
  { label: 'Praxis · 改变世界', href: '/#praxis', tone: 'violet' },
  { label: '了解我们', href: '/about', cta: true },
];

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
  const match = relativePath.match(/(?:^|\/)(?:ch|chapter-)(\d+)/i);
  return match ? Number(match[1]) : 999;
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
  .sort((a, b) => a.order - b.order || a.relativePath.localeCompare(b.relativePath));

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

    if (chapter.relativePath === 'README.md') {
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
  chapters: book.chapters.sort((a, b) => a.order - b.order || a.relativePath.localeCompare(b.relativePath)),
})).sort((a, b) => a.id.localeCompare(b.id));

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
                <div key={item.label} className="nav-menu">
                  <button
                    type="button"
                    className="nav-link"
                    aria-expanded={expanded}
                    onClick={() => setActiveMenu((value) => (value === item.label ? null : item.label))}
                  >
                    <span className={`nav-dot ${item.tone}`} />
                    {item.label}
                    <ChevronRight size={13} className={expanded ? 'nav-arrow open' : 'nav-arrow'} />
                  </button>
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
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);

  return parts.map((part, index) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={index}>{part.slice(1, -1)}</code>;
    }
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
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

    if (!trimmed || trimmed === '---') {
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
      !lines[index].trim().match(/^(#|>|- |\||```|---)/)
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
        if (block.type === 'table') {
          const rows = block.rows
            .filter((row) => !/^\|\s*-+/.test(row))
            .map((row) =>
              row
                .split('|')
                .slice(1, -1)
                .map((cell) => cell.trim()),
            );
          return (
            <div key={idx} className="table-frame">
              <table>
                <tbody>
                  {rows.map((row, rowIndex) => (
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
  if (window.location.pathname === '/logos' || window.location.pathname === '/codex') return <CodexPage />;
  if (window.location.pathname === '/about') return <AboutPage />;
  return <HomePage />;
}

export default App;
