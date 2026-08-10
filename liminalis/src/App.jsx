import { Brain, Compass, Sparkles, Zap } from 'lucide-react';
import { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import pyRadarFeed from './data/pyRadarFeed';
import {
  basename,
  bookIdFromPath,
  buildDocumentCollection,
  chapterOrder,
  compareChapters,
  isBookMetadataPath,
  relativeBookPath,
  titleizeSlug,
} from './lib/docs';
import { shouldHandleInternalLink } from './lib/routes';

const HomePage = lazy(() => import('./pages/HomePage').then((m) => ({ default: m.HomePage })));
const CodexPage = lazy(() => import('./pages/CodexPage').then((m) => ({ default: m.CodexPage })));
const KnowledgeCollectionPage = lazy(() =>
  import('./pages/KnowledgeCollectionPage').then((m) => ({ default: m.KnowledgeCollectionPage })),
);
const RadarPage = lazy(() => import('./pages/RadarPage').then((m) => ({ default: m.RadarPage })));
const InvestPage = lazy(() => import('./pages/InvestPage').then((m) => ({ default: m.InvestPage })));
const AiChatPage = lazy(() => import('./pages/AiChatPage').then((m) => ({ default: m.AiChatPage })));
const EgoShellPage = lazy(() => import('./pages/ego/EgoShellPage').then((m) => ({ default: m.EgoShellPage })));
const EgoLoginPage = lazy(() => import('./pages/ego/EgoLoginPage').then((m) => ({ default: m.EgoLoginPage })));
const EgoRecordPage = lazy(() => import('./pages/ego/EgoRecordPage').then((m) => ({ default: m.EgoRecordPage })));
const EgoChatPage = lazy(() => import('./pages/ego/EgoChatPage').then((m) => ({ default: m.EgoChatPage })));
const EgoTimelinePage = lazy(() => import('./pages/ego/EgoTimelinePage').then((m) => ({ default: m.EgoTimelinePage })));
const EgoProfilePage = lazy(() => import('./pages/ego/EgoProfilePage').then((m) => ({ default: m.EgoProfilePage })));
const EgoRolePage = lazy(() => import('./pages/ego/EgoRolePage').then((m) => ({ default: m.EgoRolePage })));
const EgoRecordDetailPage = lazy(() => import('./pages/ego/EgoRecordDetailPage').then((m) => ({ default: m.EgoRecordDetailPage })));
const AboutPage = lazy(() => import('./pages/AboutPage').then((m) => ({ default: m.AboutPage })));
const WechatCallbackPage = lazy(() =>
  import('./pages/WechatCallbackPage').then((m) => ({ default: m.WechatCallbackPage })),
);

const bookModules = import.meta.glob('../../docs/books/**/*.md', {
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

const chapters = Object.entries(bookModules)
  .map(([path, loadMarkdown]) => {
    const relativePath = relativeBookPath(path);
    const fallbackTitle = titleizeSlug(basename(path).replace(/\.md$/, '').replace(/[_/]/g, '-'));
    return {
      bookId: bookIdFromPath(path),
      id: path,
      filename: basename(path),
      relativePath,
      order: chapterOrder(path),
      title: fallbackTitle,
      excerpt: '点击后加载章节内容，保持书架轻量。',
      loadMarkdown,
      minutes: null,
    };
  })
  .filter((chapter) => chapter.bookId && !isBookMetadataPath(chapter.relativePath))
  .sort(compareChapters);

const bookSeriesList = Object.values(
  chapters.reduce((books, chapter) => {
    const book = books[chapter.bookId] ?? {
      id: chapter.bookId,
      title: titleizeSlug(chapter.bookId),
      subtitle: 'Markdown based open book.',
      location: `docs/books/${chapter.bookId}`,
      minutes: null,
      chapters: [],
    };

    book.chapters.push(chapter);
    if (!books[chapter.bookId]) {
      book.subtitle = chapter.excerpt;
    }

    books[chapter.bookId] = book;
    return books;
  }, {}),
)
  .map((book) => ({ ...book, chapters: book.chapters.sort(compareChapters) }))
  .sort((a, b) => a.id.localeCompare(b.id));

const reportDocuments = buildDocumentCollection(reportModules, 'reports', 'Reports');
const blogDocuments = buildDocumentCollection(blogModules, 'blogs', 'Blogs');

const radarItems = pyRadarFeed.items ?? [];

function PageLoader() {
  return (
    <div style={{ minHeight: '60vh', display: 'grid', placeItems: 'center', opacity: 0.5 }}>
      <span>载入中…</span>
    </div>
  );
}

function RouterEffects() {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const handleClick = (event) => {
      const anchor = event.target.closest?.('a[href]');
      if (!shouldHandleInternalLink(anchor, event)) return;
      event.preventDefault();
      const url = new URL(anchor.href, window.location.href);
      navigate(`${url.pathname}${url.search}${url.hash}`);
    };

    document.addEventListener('click', handleClick);
    return () => document.removeEventListener('click', handleClick);
  }, [navigate]);

  useEffect(() => {
    if (!location.hash) {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }

    requestAnimationFrame(() => {
      document.getElementById(location.hash.slice(1))?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }, [location.pathname, location.hash]);

  return null;
}

function AppRoutes() {
  const codex = <CodexPage bookSeriesList={bookSeriesList} />;
  const reports = (
    <KnowledgeCollectionPage type="reports" reportDocuments={reportDocuments} blogDocuments={blogDocuments} />
  );
  const blogs = (
    <KnowledgeCollectionPage type="blogs" reportDocuments={reportDocuments} blogDocuments={blogDocuments} />
  );
  const home = <HomePage tags={tags} pillars={pillars} stats={stats} />;

  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/" element={home} />
        <Route path="/logos" element={codex} />
        <Route path="/codex" element={codex} />
        <Route path="/reports" element={reports} />
        <Route path="/blogs" element={blogs} />
        <Route path="/radar" element={<RadarPage radarItems={radarItems} pyRadarFeed={pyRadarFeed} />} />
        <Route path="/invest" element={<InvestPage />} />
        <Route path="/ai-chat" element={<AiChatPage />} />
        <Route path="/ego/login" element={<EgoLoginPage />} />
        <Route path="/wechat/callback" element={<WechatCallbackPage />} />
        <Route path="/ego" element={<EgoShellPage />}>
          <Route index element={<EgoRecordPage />} />
          <Route path="record" element={<EgoRecordPage />} />
          <Route path="record/:recordId" element={<EgoRecordDetailPage />} />
          <Route path="chat" element={<EgoChatPage />} />
          <Route path="chat/:roleId" element={<EgoChatPage />} />
          <Route path="timeline" element={<EgoTimelinePage />} />
          <Route path="me" element={<EgoProfilePage />} />
          <Route path="roles" element={<EgoRolePage />} />
        </Route>
        <Route path="/about" element={<AboutPage />} />
        <Route path="*" element={home} />
      </Routes>
    </Suspense>
  );
}

function App() {
  return (
    <BrowserRouter>
      <RouterEffects />
      <AppRoutes />
    </BrowserRouter>
  );
}

export default App;
