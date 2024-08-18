import {
  ArrowRight,
  ChevronRight,
  Clock3,
  ListTree,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Sun,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { MarkdownReader } from '../components/MarkdownReader';
import { SectionLabel } from '../components/SectionLabel';
import { chapterLabel } from '../lib/docs';
import { extractExcerpt, extractTitle, normalizeMarkdownForReader, readingMinutes } from '../lib/markdown';

export function CodexLibrary({ bookSeriesList }) {
  const [activeBookId, setActiveBookId] = useState(bookSeriesList[0]?.id);
  const activeBook = bookSeriesList.find((book) => book.id === activeBookId) ?? bookSeriesList[0];
  const [activeId, setActiveId] = useState(activeBook?.chapters[0]?.id);
  const [readingOpen, setReadingOpen] = useState(false);
  const [tocOpen, setTocOpen] = useState(true);
  const [readerTheme, setReaderTheme] = useState('dark');
  const [loadedChapters, setLoadedChapters] = useState({});
  const [loadingChapterId, setLoadingChapterId] = useState(null);
  const [chapterError, setChapterError] = useState('');
  const readerRef = useRef(null);
  const activeChapterBase = activeBook?.chapters.find((chapter) => chapter.id === activeId) ?? activeBook?.chapters[0];
  const activeChapter = activeChapterBase
    ? { ...activeChapterBase, ...(loadedChapters[activeChapterBase.id] ?? {}) }
    : null;
  const chapterIndex = activeBook?.chapters.findIndex((chapter) => chapter.id === activeChapter?.id) ?? 0;
  const progress = activeBook?.chapters.length ? Math.round(((chapterIndex + 1) / activeBook.chapters.length) * 100) : 0;
  const isChapterLoading = Boolean(activeChapter?.id && loadingChapterId === activeChapter.id);

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

  useEffect(() => {
    if (!activeChapterBase?.id || loadedChapters[activeChapterBase.id]) return;

    let cancelled = false;
    setLoadingChapterId(activeChapterBase.id);
    setChapterError('');

    activeChapterBase
      .loadMarkdown()
      .then((markdown) => {
        if (cancelled) return;
        const readerMarkdown = normalizeMarkdownForReader(markdown, activeChapterBase.title);
        setLoadedChapters((chapters) => ({
          ...chapters,
          [activeChapterBase.id]: {
            title: extractTitle(readerMarkdown, activeChapterBase.title),
            excerpt: extractExcerpt(readerMarkdown),
            markdown: readerMarkdown,
            minutes: readingMinutes(readerMarkdown),
          },
        }));
      })
      .catch((error) => {
        if (cancelled) return;
        setChapterError(error instanceof Error ? error.message : '章节加载失败');
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingChapterId(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeChapterBase, loadedChapters]);

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
                  <span>Lazy loaded</span>
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
              {activeBook.chapters.map((chapter, index) => {
                const loadedChapter = loadedChapters[chapter.id];
                const chapterTitle = loadedChapter?.title ?? chapter.title;
                return (
                  <button
                    type="button"
                    key={chapter.id}
                    className={chapter.id === activeChapter.id ? 'chapter-item active' : 'chapter-item'}
                    onClick={() => setActiveId(chapter.id)}
                  >
                    <span>{chapterLabel(chapter, index)}</span>
                    <strong>{chapterTitle}</strong>
                    <small>{chapter.relativePath}</small>
                    {chapter.id === activeChapter.id && <ChevronRight size={15} />}
                  </button>
                );
              })}
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
                {activeChapter.minutes ? `${activeChapter.minutes} min` : '按需加载'}
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
          {isChapterLoading && (
            <div className="reader-loading">
              <span>正在加载章节…</span>
            </div>
          )}
          {chapterError && (
            <div className="reader-error">
              <strong>章节加载失败</strong>
              <span>{chapterError}</span>
            </div>
          )}
          {activeChapter.markdown && <MarkdownReader markdown={activeChapter.markdown} />}
        </section>
      </div>
    </section>
  );
}
