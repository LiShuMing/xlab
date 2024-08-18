import { ArrowRight, Clock3 } from 'lucide-react';
import { useState } from 'react';
import { Header } from '../components/Header';
import { MarkdownReader } from '../components/MarkdownReader';
import { SectionLabel } from '../components/SectionLabel';
import { SiteFooter } from '../components/SiteFooter';

export function KnowledgeCollectionPage({ type, reportDocuments, blogDocuments }) {
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
  const location = isReports ? 'docs/reports' : 'docs/blogs';

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
                <strong>{activeDocument.xlabPath}</strong>
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
                <span>{item.xlabPath}</span>
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
