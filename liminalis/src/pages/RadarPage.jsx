import {
  CalendarDays,
  Database,
  ExternalLink,
  Plus,
  Search,
  ShieldCheck,
  X,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Header } from '../components/Header';
import { SectionLabel } from '../components/SectionLabel';
import { SiteFooter } from '../components/SiteFooter';
import { fetchJson } from '../lib/api';
import {
  fallbackRadarPayload,
  formatRadarDate,
  radarReadingSignal,
  radarTypeLabel,
} from '../lib/radar';

export function RadarPage({ radarItems, pyRadarFeed }) {
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
