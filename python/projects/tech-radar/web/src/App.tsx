import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type {
  ArticleDraft,
  Material,
  MaterialView,
  PublicationJob,
  WorkspaceSection,
} from "./types";

const viewLabels: Record<MaterialView, string> = {
  all: "全部",
  new: "新增",
  personal: "个人精选",
  needs_review: "待确认",
};

const platformLabel = (platform: string) => {
  if (platform === "twitter") return "X";
  if (platform === "reddit") return "R";
  if (platform === "github") return "G";
  return platform.slice(0, 1).toUpperCase();
};

const shortTime = (value: string | null) => {
  if (!value) return "时间未知";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
};

function App() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useUrlSearchParams();
  const section = (searchParams.get("section") as WorkspaceSection) || "materials";
  const view = (searchParams.get("view") as MaterialView) || "all";
  const topicId = searchParams.get("topic");
  const query = searchParams.get("q") || "";
  const [searchText, setSearchText] = useState(query);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [routeTopic, setRouteTopic] = useState("");
  const [draftMessage, setDraftMessage] = useState<string | null>(null);

  const overview = useQuery({ queryKey: ["overview"], queryFn: api.overview });
  const topics = useQuery({ queryKey: ["topics"], queryFn: api.topics });
  const materials = useQuery({
    queryKey: ["materials", view, query, topicId],
    queryFn: () => api.materials(view, query, topicId),
  });
  const articleList = useQuery({ queryKey: ["articles"], queryFn: api.articles });
  const publicationList = useQuery({
    queryKey: ["publications"],
    queryFn: api.publications,
  });

  useEffect(() => {
    const first = materials.data?.items[0]?.id ?? null;
    if (!selectedId || !materials.data?.items.some((item) => item.id === selectedId)) {
      setSelectedId(first);
    }
  }, [materials.data, selectedId]);

  const detail = useQuery({
    queryKey: ["material", selectedId],
    queryFn: () => api.material(selectedId!),
    enabled: selectedId !== null,
  });

  const routeMutation = useMutation({
    mutationFn: ({ materialId, topicName }: { materialId: string; topicName: string }) =>
      api.route(materialId, topicName),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["topics"] }),
        queryClient.invalidateQueries({ queryKey: ["materials"] }),
        queryClient.invalidateQueries({ queryKey: ["material", selectedId] }),
      ]);
      setRouteTopic("");
    },
  });
  const draftMutation = useMutation({
    mutationFn: (topic: string) => api.createDraft(topic),
    onSuccess: (draft) => {
      setDraftMessage(
        `${draft.reused ? "复用已有草稿" : "已生成规则草稿"}：${draft.title}\n${draft.artifact_path}`,
      );
    },
  });

  const counts: Record<MaterialView, number> = {
    all: overview.data?.materials ?? 0,
    new: overview.data?.new ?? 0,
    personal: overview.data?.personal ?? 0,
    needs_review: overview.data?.needs_review ?? 0,
  };

  const activeTopic = useMemo(
    () => topics.data?.find((topic) => topic.id === topicId),
    [topicId, topics.data],
  );

  const updateParams = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (value) next.set(key, value);
      else next.delete(key);
    });
    setSearchParams(next);
  };

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    updateParams({ q: searchText.trim() || null });
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">T</span>
          <div>
            <strong>Tech Radar</strong>
            <small>Content workspace</small>
          </div>
        </div>

        <nav className="main-nav" aria-label="主导航">
          <button><span>⌁</span>动态</button>
          <button
            className={section === "materials" ? "active" : ""}
            onClick={() => updateParams({ section: null })}
          ><span>▤</span>素材 <b>{counts.all}</b></button>
          <button><span>◇</span>专题</button>
          <button
            className={section === "articles" ? "active" : ""}
            onClick={() => updateParams({ section: "articles" })}
          ><span>▱</span>文章 <b>{articleList.data?.length ?? 0}</b></button>
          <button
            className={section === "distribution" ? "active" : ""}
            onClick={() => updateParams({ section: "distribution" })}
          ><span>↗</span>分发 <b>{publicationList.data?.length ?? 0}</b></button>
        </nav>

        <div className="nav-section">
          <div className="nav-heading"><span>专题空间</span><button>＋</button></div>
          <button
            className={!topicId ? "topic-link active" : "topic-link"}
            onClick={() => updateParams({ section: null, topic: null })}
          >
            <span>全部专题</span><b>{counts.all}</b>
          </button>
          {topics.data?.map((topic) => (
            <button
              className={topic.id === topicId ? "topic-link active" : "topic-link"}
              key={topic.id}
              onClick={() => updateParams({ section: null, topic: topic.id })}
            >
              <span>{topic.name}</span><b>{topic.material_count}</b>
            </button>
          ))}
        </div>

        <div className="sidebar-status">
          <span className={overview.data?.last_run?.status === "failed" ? "dot error" : "dot"} />
          <div>
            <strong>
              {overview.data?.last_run
                ? "最近采集已记录"
                : counts.all > 0
                  ? "历史素材已同步"
                  : "等待首次采集"}
            </strong>
            <small>
              {overview.data?.last_run
                ? shortTime(overview.data.last_run.started_at)
                : counts.all > 0
                  ? "下次 collect 开始记录 Run"
                  : "运行 CLI collect"}
            </small>
          </div>
        </div>
      </aside>

      <main className="main-area">
        {section === "articles" ? (
          <ArticleStudio />
        ) : section === "distribution" ? (
          <DistributionCenter />
        ) : (
          <>
        <header className="topbar">
          <div>
            <p className="eyebrow">素材 / {activeTopic?.name ?? "每日收件箱"}</p>
            <h1>Material Inbox</h1>
            <p>{counts.new} 条新增素材，{counts.personal} 条来自你的主动选择</p>
          </div>
          <form className="search" onSubmit={submitSearch}>
            <span>⌕</span>
            <input
              aria-label="搜索素材"
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="搜索标题、正文或作者"
            />
            <kbd>Enter</kbd>
          </form>
        </header>

        <section className="filters" aria-label="素材筛选">
          {(Object.keys(viewLabels) as MaterialView[]).map((item) => (
            <button
              key={item}
              className={view === item ? "active" : ""}
              onClick={() => updateParams({ view: item === "all" ? null : item })}
            >
              {viewLabels[item]} <span>{counts[item]}</span>
            </button>
          ))}
          <div className="filter-spacer" />
          <button className="secondary">筛选</button>
          <button className="secondary">按相关度</button>
        </section>

        <div className="workspace">
          <section className="material-list" aria-label="素材列表">
            <div className="list-heading">
              <span>{query ? `“${query}” 的结果` : "按相关度排序"}</span>
              <span>{materials.data?.items.length ?? 0} 条</span>
            </div>
            {materials.isLoading && <StateMessage title="正在加载素材" />}
            {materials.isError && <StateMessage title="无法读取素材" body={(materials.error as Error).message} />}
            {!materials.isLoading && materials.data?.items.length === 0 && (
              <StateMessage title="当前筛选没有素材" body="尝试切换筛选条件或先运行一次采集。" />
            )}
            {materials.data?.items.map((material) => (
              <MaterialRow
                key={material.id}
                material={material}
                selected={material.id === selectedId}
                onSelect={() => setSelectedId(material.id)}
              />
            ))}
          </section>

          <aside className="detail-panel" aria-live="polite">
            {detail.isLoading && <StateMessage title="正在读取详情" />}
            {detail.data && (
              <MaterialDetail
                material={detail.data}
                routeTopic={routeTopic}
                onRouteTopic={setRouteTopic}
                topicNames={topics.data?.map((topic) => topic.name) ?? []}
                routing={routeMutation.isPending}
                routeError={routeMutation.error as Error | null}
                draftMessage={draftMessage}
                drafting={draftMutation.isPending}
                draftError={draftMutation.error as Error | null}
                onRoute={() => {
                  if (selectedId && routeTopic.trim()) {
                    routeMutation.mutate({ materialId: selectedId, topicName: routeTopic.trim() });
                  }
                }}
                onDraft={() => {
                  const firstTopic = detail.data?.topic_ids[0];
                  if (firstTopic) draftMutation.mutate(firstTopic);
                }}
              />
            )}
          </aside>
        </div>
          </>
        )}
      </main>
    </div>
  );
}

function ArticleStudio() {
  const queryClient = useQueryClient();
  const articles = useQuery({ queryKey: ["articles"], queryFn: api.articles });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Pick<
    ArticleDraft,
    "title" | "summary" | "body_markdown" | "version"
  > | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedId && articles.data?.length) {
      setSelectedId(articles.data[0].article_id);
    }
  }, [articles.data, selectedId]);

  const article = useQuery({
    queryKey: ["article", selectedId],
    queryFn: () => api.article(selectedId!),
    enabled: selectedId !== null,
  });

  useEffect(() => {
    if (article.data) {
      setDraft({
        title: article.data.title,
        summary: article.data.summary,
        body_markdown: article.data.body_markdown,
        version: article.data.version,
      });
      setMessage(null);
    }
  }, [article.data]);

  const refresh = async (articleId: string) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["articles"] }),
      queryClient.invalidateQueries({ queryKey: ["article", articleId] }),
    ]);
  };
  const save = useMutation({
    mutationFn: () => api.saveArticle(selectedId!, draft!),
    onSuccess: async (value) => {
      await refresh(value.article_id);
      setMessage(`已保存版本 v${value.version}，进入 Review。`);
    },
  });
  const approve = useMutation({
    mutationFn: () => api.approveArticle(article.data!.version_id),
    onSuccess: async (value) => {
      await refresh(value.article_id);
      setMessage(`版本 v${value.version} 已批准，可以创建分发任务。`);
    },
  });
  const distribute = useMutation({
    mutationFn: () => api.createPublications(article.data!.version_id),
    onSuccess: async (jobs) => {
      await queryClient.invalidateQueries({ queryKey: ["publications"] });
      setMessage(`已创建 ${jobs.length} 个分发任务：Blog、小红书。`);
    },
  });
  const mutationError = save.error || approve.error || distribute.error;

  return (
    <>
      <header className="topbar">
        <div>
          <p className="eyebrow">ARTICLES / EVIDENCE-FIRST</p>
          <h1>Article Studio</h1>
          <p>编辑母稿、检查证据、批准版本，然后进入分发。</p>
        </div>
        <div className="header-metrics">
          <span><b>{articles.data?.length ?? 0}</b> drafts</span>
          <span><b>{articles.data?.filter((item) => item.status === "approved").length ?? 0}</b> approved</span>
        </div>
      </header>
      <section className="filters studio-filters">
        <span className="flow-step active">Draft</span>
        <span className="flow-arrow">→</span>
        <span className="flow-step">Review</span>
        <span className="flow-arrow">→</span>
        <span className="flow-step">Approved</span>
        <span className="flow-arrow">→</span>
        <span className="flow-step">Distributed</span>
      </section>
      <div className="article-workspace">
        <section className="article-list">
          <div className="list-heading"><span>Articles</span><span>{articles.data?.length ?? 0}</span></div>
          {articles.data?.map((item) => (
            <button
              className={item.article_id === selectedId ? "article-item active" : "article-item"}
              key={item.article_id}
              onClick={() => setSelectedId(item.article_id)}
            >
              <span className={`status-pill ${item.status}`}>{item.status}</span>
              <strong>{item.title}</strong>
              <small>{item.topic_name} · v{item.version} · {item.evidence_count} evidence</small>
            </button>
          ))}
          {!articles.isLoading && !articles.data?.length && (
            <StateMessage title="还没有文章" body="从 Material Inbox 的素材详情生成 Topic 草稿。" />
          )}
        </section>

        <section className="article-editor">
          {article.isLoading && <StateMessage title="正在加载文章" />}
          {article.data && draft && (
            <>
              <div className="editor-toolbar">
                <div>
                  <span className={`status-pill ${article.data.status}`}>{article.data.status}</span>
                  <span>Version {article.data.version}</span>
                </div>
                <div>
                  <button
                    className="secondary-action"
                    disabled={save.isPending}
                    onClick={() => save.mutate()}
                  >保存新版本</button>
                  <button
                    className="secondary-action"
                    disabled={article.data.status === "approved" || approve.isPending}
                    onClick={() => approve.mutate()}
                  >批准当前版本</button>
                  <button
                    className="primary-action"
                    disabled={article.data.status !== "approved" || distribute.isPending}
                    onClick={() => distribute.mutate()}
                  >创建分发任务</button>
                </div>
              </div>
              {message && <p className="success-banner">{message}</p>}
              {mutationError && <p className="error-banner">{(mutationError as Error).message}</p>}
              <label className="editor-field">
                <span>标题</span>
                <input
                  value={draft.title}
                  onChange={(event) => setDraft({ ...draft, title: event.target.value })}
                />
              </label>
              <label className="editor-field">
                <span>摘要</span>
                <textarea
                  className="summary-input"
                  value={draft.summary}
                  onChange={(event) => setDraft({ ...draft, summary: event.target.value })}
                />
              </label>
              <label className="editor-field body-editor">
                <span>Markdown 母稿</span>
                <textarea
                  value={draft.body_markdown}
                  onChange={(event) => setDraft({ ...draft, body_markdown: event.target.value })}
                />
              </label>
            </>
          )}
        </section>

        <aside className="evidence-panel">
          <div className="list-heading"><span>Evidence</span><span>{article.data?.evidence?.length ?? 0}</span></div>
          {article.data?.evidence?.map((item) => (
            <a href={item.canonical_url} target="_blank" rel="noreferrer" key={item.claim_id}>
              <span>{item.citation_order.toString().padStart(2, "0")}</span>
              <div><strong>{item.title}</strong><small>{item.author} · {item.platform} · {Math.round(item.quality_score)}</small></div>
            </a>
          ))}
        </aside>
      </div>
    </>
  );
}

function DistributionCenter() {
  const queryClient = useQueryClient();
  const publications = useQuery({
    queryKey: ["publications"],
    queryFn: api.publications,
  });
  const [message, setMessage] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: async ({ job, action }: { job: PublicationJob; action: string }) => {
      if (action === "prepare") return api.preparePublication(job.job_id);
      if (action === "preview") return api.previewPublication(job.job_id);
      if (action === "published") {
        const url = window.prompt("粘贴人工发布后的公开 URL：");
        if (!url) throw new Error("已取消记录发布");
        const note = window.prompt("填写人工确认说明：", "已人工检查可见性和最终内容");
        if (!note) throw new Error("必须填写人工确认说明");
        return api.recordPublication(job.job_id, url, note);
      }
      throw new Error(`unknown action: ${action}`);
    },
    onSuccess: async (job, variables) => {
      await queryClient.invalidateQueries({ queryKey: ["publications"] });
      setMessage(`${platformName(job.platform)} 已进入 ${job.status}。`);
      if (variables.action === "preview") {
        const preview = job.artifacts.find((item) => item.kind === "preview-html");
        if (preview) window.open(preview.url, "_blank", "noopener,noreferrer");
      }
    },
  });

  return (
    <>
      <header className="topbar">
        <div>
          <p className="eyebrow">DISTRIBUTION / HUMAN IN THE LOOP</p>
          <h1>Distribution Center</h1>
          <p>每个平台独立准备、预览和记账；系统不执行无人值守公开发布。</p>
        </div>
        <div className="header-metrics">
          <span><b>{publications.data?.length ?? 0}</b> jobs</span>
          <span><b>{publications.data?.filter((item) => item.status === "published").length ?? 0}</b> published</span>
        </div>
      </header>
      <section className="filters distribution-legend">
        <span><i className="legend-dot pending" />Pending</span>
        <span><i className="legend-dot prepared" />Prepared</span>
        <span><i className="legend-dot previewed" />Previewed</span>
        <span><i className="legend-dot published" />Published</span>
      </section>
      <section className="distribution-content">
        {message && <p className="success-banner">{message}</p>}
        {mutation.error && <p className="error-banner">{(mutation.error as Error).message}</p>}
        <div className="distribution-table">
          <div className="distribution-head">
            <span>Article / Platform</span><span>Artifacts</span><span>Status</span><span>Next action</span>
          </div>
          {publications.data?.map((job) => (
            <div className="distribution-row" key={job.job_id}>
              <div className="distribution-title">
                <span className={`platform-badge ${job.platform}`}>{platformName(job.platform)}</span>
                <div><strong>{job.article_title}</strong><small>{job.topic_name} · {job.adapter_id}</small></div>
              </div>
              <div className="artifact-links">
                {job.artifacts.slice(0, 4).map((artifact) => (
                  <a href={artifact.url} target="_blank" rel="noreferrer" key={artifact.id}>{artifact.kind}</a>
                ))}
                {!job.artifacts.length && <span>尚未生成</span>}
              </div>
              <div><span className={`status-pill ${job.status}`}>{job.status}</span>{job.last_error && <small className="job-error">{job.last_error}</small>}</div>
              <div className="job-actions">
                {(job.status === "pending" || job.status === "failed") && (
                  <button onClick={() => mutation.mutate({ job, action: "prepare" })}>Prepare</button>
                )}
                {job.status === "prepared" && (
                  <button onClick={() => mutation.mutate({ job, action: "preview" })}>Preview</button>
                )}
                {job.status === "previewed" && (
                  <button onClick={() => mutation.mutate({ job, action: "preview" })}>再次预览</button>
                )}
                {job.status === "previewed" && (
                  <button className="confirm" onClick={() => mutation.mutate({ job, action: "published" })}>记录已发布</button>
                )}
                {job.status === "published" && job.external_url && (
                  <a href={job.external_url} target="_blank" rel="noreferrer">打开发布页</a>
                )}
              </div>
            </div>
          ))}
        </div>
        {!publications.isLoading && !publications.data?.length && (
          <StateMessage title="还没有分发任务" body="在 Article Studio 批准文章后创建 Blog 与小红书任务。" />
        )}
      </section>
    </>
  );
}

function platformName(platform: PublicationJob["platform"]): string {
  return platform === "xiaohongshu" ? "小红书" : "Blog";
}

function useUrlSearchParams(): [URLSearchParams, (value: URLSearchParams) => void] {
  const [parameters, setParameters] = useState(
    () => new URLSearchParams(window.location.search),
  );

  useEffect(() => {
    const onPopState = () => setParameters(new URLSearchParams(window.location.search));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const update = (value: URLSearchParams) => {
    const query = value.toString();
    window.history.pushState(null, "", query ? `?${query}` : window.location.pathname);
    setParameters(new URLSearchParams(value));
  };
  return [parameters, update];
}

function MaterialRow({ material, selected, onSelect }: { material: Material; selected: boolean; onSelect: () => void }) {
  return (
    <button className={`material-row ${selected ? "selected" : ""}`} onClick={onSelect}>
      <div className={`source-mark ${material.platform}`}>{platformLabel(material.platform)}</div>
      <div className="material-copy">
        <div className="material-meta"><span>{material.author || "未知作者"}</span><time>{shortTime(material.published_at ?? material.first_seen_at)}</time></div>
        <strong>{material.title || material.excerpt.slice(0, 100)}</strong>
        <p>{material.excerpt}</p>
        <div className="tag-row">
          {material.personal && <span className="personal-tag">个人精选</span>}
          {material.topics.slice(0, 2).map((topic) => <span key={topic}>{topic}</span>)}
          {material.event_count > 0 && <span>Event · {material.event_count}</span>}
        </div>
      </div>
      <span className="score">{Math.round(material.quality_score)}</span>
    </button>
  );
}

type MaterialDetailProps = {
  material: Material;
  routeTopic: string;
  onRouteTopic: (value: string) => void;
  topicNames: string[];
  routing: boolean;
  routeError: Error | null;
  onRoute: () => void;
  draftMessage: string | null;
  drafting: boolean;
  draftError: Error | null;
  onDraft: () => void;
};

function MaterialDetail(props: MaterialDetailProps) {
  const { material } = props;
  return (
    <div className="detail-content">
      <div className="detail-kicker"><span>SELECTED MATERIAL</span><button aria-label="更多操作">•••</button></div>
      <h2>{material.title}</h2>
      <p className="detail-byline">{material.author} · {material.platform} · {shortTime(material.published_at ?? material.first_seen_at)}</p>
      <p className="detail-summary">{material.content || material.excerpt}</p>

      <dl className="detail-grid">
        <div><dt>Topic</dt><dd>{material.topics.join(" / ") || "未分类"}</dd></div>
        <div><dt>Relevance</dt><dd>{Math.round(material.quality_score)}</dd></div>
        <div><dt>Sources</dt><dd>{material.source_ids.length}</dd></div>
        <div><dt>Status</dt><dd>{material.status}</dd></div>
      </dl>

      <section className="detail-section">
        <h3>为什么进入候选池</h3>
        <ul>
          {material.personal && <li>来自你的点赞或主动收藏</li>}
          <li>被 {material.source_ids.length || 1} 个关注规则命中</li>
          <li>内容指纹已生成，可用于后续增量去重</li>
        </ul>
      </section>

      <section className="detail-section">
        <h3>来源证据</h3>
        {material.source_ids.map((source) => (
          <div className="evidence" key={source}>
            <span className={`source-mark small ${material.platform}`}>{platformLabel(material.platform)}</span>
            <div><strong>{source}</strong><small>{material.url || "无公开链接"}</small></div>
          </div>
        ))}
      </section>

      <section className="route-box">
        <label htmlFor="topic-route">加入 Topic</label>
        <div>
          <input
            id="topic-route"
            list="topic-options"
            value={props.routeTopic}
            onChange={(event) => props.onRouteTopic(event.target.value)}
            placeholder="选择或创建 Topic"
          />
          <datalist id="topic-options">
            {props.topicNames.map((name) => <option value={name} key={name} />)}
          </datalist>
          <button disabled={!props.routeTopic.trim() || props.routing} onClick={props.onRoute}>
            {props.routing ? "处理中" : "加入"}
          </button>
        </div>
        {props.routeError && <p className="inline-error">{props.routeError.message}</p>}
      </section>

      <div className="detail-actions">
        <a className="secondary-action" href={material.url} target="_blank" rel="noreferrer">查看原文</a>
        <button
          className="primary-action"
          disabled={!material.topic_ids.length || props.drafting}
          onClick={props.onDraft}
        >
          {props.drafting ? "生成中" : "生成 Topic 草稿"}
        </button>
      </div>
      {props.draftMessage && <p className="draft-result">{props.draftMessage}</p>}
      {props.draftError && <p className="inline-error">{props.draftError.message}</p>}
    </div>
  );
}

function StateMessage({ title, body }: { title: string; body?: string }) {
  return <div className="state-message"><strong>{title}</strong>{body && <p>{body}</p>}</div>;
}

export default App;
