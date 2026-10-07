import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowUpRight,
  BookOpen,
  Bookmark,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Clock3,
  FileText,
  FolderOpen,
  Hash,
  History,
  Layers3,
  LayoutDashboard,
  Lightbulb,
  Link2,
  Menu,
  MessageSquare,
  MoreHorizontal,
  NotebookPen,
  Plus,
  Search,
  Settings2,
  Sparkles,
  Sun,
  Upload,
  X,
  Rss,
  Github,
  ExternalLink,
  PencilLine,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api, upload, ApiError, sourceRef } from "./api";
import { DraftStore, downloadLocal } from "./drafts";
import { DigestCard, ProcessingView } from "./processing";
import type { Draft, DraftBase } from "./drafts";
import type {
  Blog,
  Entry,
  Material,
  Proposal,
  Report,
  SourceRef,
  State,
  DigestOptions,
} from "./api";
import "./styles.css";

const nav: [string, string, LucideIcon][] = [
  ["today", "今日", Sun],
  ["materials", "素材", FolderOpen],
  ["reports", "每日 Report", FileText],
  ["jobs", "消化任务", Sparkles],
  ["topics", "主题", Hash],
  ["studio", "写作台", NotebookPen],
  ["library", "图书馆", BookOpen],
  ["sources", "关注来源", Rss],
];
const kinds: Record<string, string> = {
  user_note: "随手笔记",
  markdown: "Markdown",
  ai_conversation: "AI 对话",
  web_page: "网页链接",
  video_reference: "视频链接",
};
const topicColors: Record<string, string> = {
  database: "yellow",
  ai: "blue",
  thinking: "pink",
};
const feedbackLabels: Record<string, string> = {
  unread: "待阅读",
  useful: "有价值",
  known: "已知",
  later: "稍后读",
};
const kindIcons: Record<string, LucideIcon> = {
  user_note: PencilLine,
  markdown: FileText,
  ai_conversation: MessageSquare,
  web_page: Link2,
  video_reference: Link2,
};
const emptyState: State = {
  today: "",
  topics: [],
  materials: [],
  reports: [],
  blogs: [],
  entries: [],
  proposals: [],
  sources: [],
  jobs: [],
  digests: [],
  processing: {
    provider: "mock",
    external_calls_enabled: false,
    profiles: [],
    config_error: null,
    budget: {
      day: "",
      limit: 500000,
      reserved: 0,
      used: 0,
      remaining: 500000,
      cost: 0,
    },
  },
  settings: {
    display_name: "我的工作空间",
    report_time: "21:30",
    timezone: "Asia/Shanghai",
  },
};
function navigate(route: string) {
  window.location.hash = `#/${route}`;
}
function dayLabel(day: string) {
  return new Date(`${day}T12:00:00`).toLocaleDateString("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long",
  });
}
function timeLabel(value: string) {
  return new Date(value).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Shanghai",
  });
}
function TopicBadge({ topic, state }: { topic: string; state: State }) {
  return (
    <span className={`badge ${topicColors[topic] || "gray"}`}>
      {state.topics.find((t) => t.id === topic)?.name || topic}
    </span>
  );
}
function Markdown({
  children,
  sources = [],
}: {
  children: string;
  sources?: Material[];
}) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          img: () => <span className="muted">[外部图片未加载]</span>,
          a: ({ href, children }) => {
            const match = href?.match(/^#\/materials\/([^?]+)$/);
            const frozen = match
              ? sources.find((m) => m.id === match[1])
              : undefined;
            const target = frozen
              ? `${href}?revision=${frozen.revision}`
              : href;
            return (
              <a
                href={target}
                target={target?.startsWith("#") ? undefined : "_blank"}
                rel="noreferrer"
              >
                {children}
              </a>
            );
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
function Button({
  icon: Icon,
  children,
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { icon?: LucideIcon }) {
  return (
    <button className={`button ${className}`} {...props}>
      {Icon && <Icon size={16} />}
      {children}
    </button>
  );
}
function Empty({
  icon: Icon = FolderOpen,
  title,
  text,
  action,
}: {
  icon?: LucideIcon;
  title: string;
  text: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Icon size={30} />
      </div>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}

function App() {
  const [state, setState] = useState<State>(emptyState);
  const [route, setRoute] = useState(
    () => window.location.hash.slice(2) || "today",
  );
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState("");
  const [captureOpen, setCaptureOpen] = useState(false);
  const [captureMode, setCaptureMode] = useState("note");
  const [search, setSearch] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedDate, setSelectedDate] = useState("");
  const [selectedTopic, setSelectedTopic] = useState("all");
  const [materialView, setMaterialView] = useState<Material | null>(null);
  const [history, setHistory] = useState<Report[] | null>(null);
  const [historicalReport, setHistoricalReport] = useState<Report | null>(null);
  const [proposalView, setProposalView] = useState<Proposal | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const page = route.split("/")[0];
  const objectId = route.split("/")[1]?.split("?")[0];
  const routeRevision = new URLSearchParams(route.split("?")[1] || "").get(
    "revision",
  );
  const reload = useCallback(async () => {
    const data = await api<State>("/bootstrap");
    setState({
      ...emptyState,
      ...data,
      processing: { ...emptyState.processing, ...data.processing },
    });
    setSelectedDate((d) => d || data.today);
    setLoadError("");
  }, []);
  useEffect(() => {
    reload()
      .catch((e) => setLoadError(e.message))
      .finally(() => setLoading(false));
  }, [reload]);
  useEffect(() => {
    if (
      page !== "jobs" &&
      !state.jobs.some((j) => ["queued", "running"].includes(j.state))
    )
      return;
    let disposed = false;
    const timer = setInterval(() => {
      api<Pick<State, "jobs" | "digests" | "processing">>("/processing")
        .then((data) => {
          if (!disposed)
            setState((s) => ({
              ...s,
              ...data,
              processing: { ...emptyState.processing, ...data.processing },
            }));
        })
        .catch(() => {
          if (!disposed)
            setToast("任务状态暂时无法刷新，记录仍保留；请检查服务连接");
        });
    }, 2000);
    return () => {
      disposed = true;
      clearInterval(timer);
    };
  }, [page, state.jobs]);
  useEffect(() => {
    const hash = () => {
      setRoute(window.location.hash.slice(2) || "today");
      setSidebarOpen(false);
      setHistoricalReport(null);
      setSearch("");
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", hash);
    return () => window.removeEventListener("hashchange", hash);
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 4500);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    const keys = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        searchRef.current?.focus();
      }
      if (
        (e.metaKey || e.ctrlKey) &&
        e.shiftKey &&
        e.key.toLowerCase() === "n"
      ) {
        e.preventDefault();
        setCaptureOpen(true);
      }
    };
    document.addEventListener("keydown", keys);
    return () => document.removeEventListener("keydown", keys);
  }, []);
  useEffect(() => {
    let cancelled = false;
    if (page === "materials" && objectId) {
      if (routeRevision) {
        api<Material>(
          `/objects/${objectId}?revision=${encodeURIComponent(routeRevision)}`,
        )
          .then((m) => {
            if (!cancelled) setMaterialView(m);
          })
          .catch((e) => {
            if (!cancelled) {
              setMaterialView(null);
              setToast(e.message);
            }
          });
      } else
        setMaterialView(state.materials.find((m) => m.id === objectId) || null);
    }
    return () => {
      cancelled = true;
    };
  }, [page, objectId, routeRevision, state.materials]);
  async function action<T>(
    work: () => Promise<T>,
    message = "",
    callback?: (value: T) => void,
  ) {
    if (busy) return;
    setBusy(true);
    try {
      const result = await work();
      await reload();
      if (message) setToast(message);
      callback?.(result);
      return result;
    } catch (e) {
      setToast(e instanceof Error ? e.message : "操作失败，请重试");
    } finally {
      setBusy(false);
    }
  }
  const dailyMaterials = state.materials.filter((m) => m.day === selectedDate);
  const todayReport = state.reports.find((r) => r.day === selectedDate);
  const coveredBefore = new Set(
    state.reports
      .filter((r) => r.day < selectedDate)
      .flatMap((r) =>
        r.sources
          .filter((s) => s.parse_state === "ready")
          .map((s) => `${s.id}:${s.blob_hash}`),
      ),
  );
  const lateCount = todayReport
    ? state.materials.filter(
        (m) =>
          (m.day === selectedDate ||
            (m.day < selectedDate &&
              !coveredBefore.has(`${m.id}:${m.blob_hash}`))) &&
          !todayReport.sources.some(
            (s) => s.id === m.id && s.blob_hash === m.blob_hash,
          ),
      ).length
    : 0;
  const report =
    historicalReport ||
    (objectId
      ? state.reports.find((r) => r.id === objectId || r.day === objectId)
      : undefined);
  const entry = state.entries.find((e) => e.id === objectId);
  const blog = state.blogs.find((b) => b.id === objectId);
  const nextWriting =
    state.blogs.find((b) => b.lifecycle === "draft") || state.blogs[0];
  const unread = dailyMaterials.filter((m) => m.feedback === "unread").length;
  const due = state.entries.filter((e) => e.due_day <= state.today);
  const demoCount = state.materials.filter((m) => m.is_demo).length;
  const materialFilter = state.materials.filter(
    (m) =>
      (!!search || selectedTopic === "all" || m.topic === selectedTopic) &&
      `${m.title} ${m.content}`.toLowerCase().includes(search.toLowerCase()),
  );
  function newBlog(
    materials: string[],
    title: string,
    reportId?: string,
    reportRevision?: number,
    refs?: ReturnType<typeof sourceRef>[],
  ) {
    action(
      () =>
        api<Blog>("/blogs", {
          title,
          material_ids: materials,
          report_id: reportId,
          report_revision: reportRevision,
          source_refs: refs,
        }),
      "写作框架已保存，可以开始加入自己的理解",
      (value) => navigate(`studio/${value.id}`),
    );
  }
  function generate() {
    action(
      () => api<Report>("/reports/runs", { date: selectedDate }),
      "报告已保存，原始素材与历史版本均保留",
      (value) => navigate(`reports/${value.id}`),
    );
  }
  function submitDigest(
    refs: SourceRef[],
    options: DigestOptions = { provider: "mock" },
  ) {
    action(
      () => api("/digest/jobs", { source_refs: refs, ...options }),
      "任务已登记，相同版本复用原记录",
      () => {
        setMaterialView(null);
        navigate("jobs");
      },
    );
  }
  function openEvidence(ref: SourceRef) {
    action(
      () =>
        api<Material>(
          `/objects/${ref.material_id}?revision=${ref.material_revision}`,
        ),
      "已打开引用时的素材版本",
      setMaterialView,
    );
  }
  function feedback(material: Material, value: string) {
    action(
      () => api<Material>(`/materials/${material.id}/feedback`, { value }),
      "阅读状态已保存",
    );
  }
  function closeMaterial() {
    setMaterialView(null);
    if (page === "materials" && objectId) navigate("materials");
  }
  const stats = [
    {
      label: "今日输入",
      count: dailyMaterials.length,
      icon: FolderOpen,
      color: "yellow",
    },
    { label: "待阅读", count: unread, icon: Bookmark, color: "blue" },
    {
      label: "写作中的博客",
      count: state.blogs.filter((b) => b.lifecycle === "draft").length,
      icon: NotebookPen,
      color: "pink",
    },
    {
      label: "知识条目",
      count: state.entries.length,
      icon: BookOpen,
      color: "green",
    },
  ];

  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <a href="#/today" className="brand">
          <span className="brand-mark">
            <Layers3 size={24} strokeWidth={2.7} />
          </span>
          <span>
            <strong>盘铭</strong>
            <small>PANMING</small>
          </span>
        </a>
        <button className="workspace-chip" onClick={() => navigate("settings")}>
          <span className="workspace-avatar">铭</span>
          <span>
            {state.settings.display_name}
            <small>个人知识工作空间</small>
          </span>
          <ChevronDown size={15} />
        </button>
        <div className="nav-caption">我的知识工作台</div>
        <nav aria-label="主导航">
          {nav.map(([path, label, Icon]) => (
            <a
              key={path}
              href={`#/${path}`}
              className={page === path ? "active" : ""}
            >
              <Icon size={19} />
              <span>{label}</span>
              {path === "materials" && <small>{state.materials.length}</small>}
              {path === "studio" && state.blogs.length > 0 && (
                <span className="nav-dot" />
              )}
            </a>
          ))}
        </nav>
        <div className="nav-caption topic-caption">正在探索</div>
        {state.topics.map((t) => (
          <a href={`#/topics/${t.id}`} className="topic-link" key={t.id}>
            <span className={`topic-dot ${t.color}`} />
            {t.name}
          </a>
        ))}
        <div className="sidebar-bottom">
          <div className="quiet-quote">
            苟日新，日日新，又日新。<span>让输入留下理解。</span>
          </div>
          <a
            href="#/settings"
            className={
              page === "settings" ? "active bottom-link" : "bottom-link"
            }
          >
            <Settings2 size={18} />
            设置与偏好
          </a>
          <div className="version-label">
            <span>本机运行</span>
            <span>v0.4.1</span>
          </div>
        </div>
      </aside>
      <div className="workspace-main">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            aria-label="展开导航"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            <Menu size={20} />
          </button>
          <div className="breadcrumb">
            我的工作空间<span>/</span>
            <strong>{nav.find((n) => n[0] === page)?.[1] || "设置"}</strong>
          </div>
          <div className="topbar-actions">
            <div className="search-box">
              <Search size={16} />
              <input
                ref={searchRef}
                aria-label="搜索知识"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="搜索素材与知识"
              />
              <kbd>⌘ K</kbd>
            </div>
            <Button
              icon={Plus}
              className="primary small"
              onClick={() => setCaptureOpen(true)}
            >
              收集素材
            </Button>
            <span className="profile-avatar">我</span>
          </div>
        </header>
        <main className="main-content">
          {loading ? (
            <Empty
              title="正在打开你的工作空间"
              text="加载已保存的素材和知识…"
            />
          ) : loadError ? (
            <Empty
              title="暂时无法连接盘铭"
              text={loadError}
              action={
                <Button
                  onClick={() => reload().catch((e) => setLoadError(e.message))}
                >
                  重新连接
                </Button>
              }
            />
          ) : (
            <>
              {search ? (
                <>
                  <PageHeading
                    eyebrow="SEARCH"
                    title={`搜索 “${search}”`}
                    subtitle="在你的素材、博客和知识条目中查找"
                  />
                  <section className="panel">
                    <MaterialList
                      materials={materialFilter}
                      state={state}
                      onOpen={setMaterialView}
                      onFeedback={feedback}
                    />
                    {[...state.blogs, ...state.entries]
                      .filter((x) =>
                        `${x.title} ${x.body}`
                          .toLowerCase()
                          .includes(search.toLowerCase()),
                      )
                      .map((x) => (
                        <button
                          key={x.id}
                          className="search-result"
                          onClick={() =>
                            navigate(
                              `${state.blogs.some((b) => b.id === x.id) ? "studio" : "library"}/${x.id}`,
                            )
                          }
                        >
                          <BookOpen size={20} />
                          <div>
                            <strong>{x.title}</strong>
                            <span>
                              {x.body.replace(/^#.*\n/, "").slice(0, 90)}
                            </span>
                          </div>
                          <ArrowUpRight size={17} />
                        </button>
                      ))}
                  </section>
                </>
              ) : (
                <>
                  {page === "today" && (
                    <>
                      <PageHeading
                        eyebrow="DAILY WORKSPACE"
                        title="今天，也向前一点。"
                        subtitle={
                          selectedDate
                            ? `${dayLabel(selectedDate)} · 每一次输入，都有沉淀的可能。`
                            : ""
                        }
                        action={
                          <div className="date-picker">
                            <Button
                              className="icon-only"
                              aria-label="前一天"
                              onClick={() =>
                                setSelectedDate(shiftDay(selectedDate, -1))
                              }
                              icon={ChevronLeft}
                            />
                            <input
                              aria-label="选择日期"
                              type="date"
                              max={state.today}
                              value={selectedDate}
                              onChange={(e) =>
                                e.target.value &&
                                setSelectedDate(e.target.value)
                              }
                            />
                            <Button
                              className="icon-only"
                              aria-label="后一天"
                              disabled={selectedDate >= state.today}
                              onClick={() =>
                                setSelectedDate(shiftDay(selectedDate, 1))
                              }
                              icon={ChevronRight}
                            />
                          </div>
                        }
                      />
                      <div className="stats-grid">
                        {stats.map((stat) => (
                          <div className="stat" key={stat.label}>
                            <div>
                              <span>{stat.label}</span>
                              <strong>
                                {stat.count}
                                <small>
                                  {stat.label.includes("博客") ? "篇" : "项"}
                                </small>
                              </strong>
                            </div>
                            <span className={`stat-icon ${stat.color}`}>
                              <stat.icon size={21} />
                            </span>
                          </div>
                        ))}
                      </div>
                      <div className="today-layout">
                        <div className="today-primary">
                          <section className="daily-card">
                            <div className="daily-card-top">
                              <span className="eyebrow">
                                <Sparkles size={14} /> YOUR DAILY REPORT
                              </span>
                              <span className="badge white">LAYER 1</span>
                            </div>
                            <div className="daily-card-body">
                              <div>
                                <h2>
                                  {todayReport
                                    ? "把今天的线索，连成理解。"
                                    : "把今天的输入，整理一下。"}
                                </h2>
                                <p>
                                  {todayReport
                                    ? `已整理 ${todayReport.ready_count} 份素材，留下 ${todayReport.briefs.length} 个可以继续写的问题。`
                                    : dailyMaterials.length
                                      ? "材料已经收下。从原文摘录开始，找到值得继续的问题。"
                                      : "先保存一份素材，再开始今天的整理。"}
                                </p>
                              </div>
                              <div className="report-symbol">
                                <FileText size={42} />
                                <span>
                                  <Sparkles size={19} />
                                </span>
                              </div>
                            </div>
                            {lateCount > 0 && (
                              <button
                                className="late-input-note"
                                disabled={busy}
                                onClick={generate}
                              >
                                <Plus size={13} />
                                {lateCount} 份新素材尚未纳入，更新 Report
                              </button>
                            )}
                            <div className="daily-card-bottom">
                              <div className="report-meta">
                                <Clock3 size={14} />
                                {todayReport
                                  ? `v${todayReport.revision} · 截止 ${timeLabel(todayReport.cutoff_at)} · 提取式整理`
                                  : "保存原文 · 保留来源 · 随时生成"}
                              </div>
                              <Button
                                className="ink"
                                icon={todayReport ? BookOpen : Sparkles}
                                disabled={
                                  busy ||
                                  (!todayReport && !dailyMaterials.length)
                                }
                                onClick={
                                  todayReport
                                    ? () =>
                                        navigate(`reports/${todayReport.id}`)
                                    : generate
                                }
                              >
                                {todayReport
                                  ? "阅读今日 Report"
                                  : "整理今日 Report"}
                              </Button>
                            </div>
                          </section>
                          <section className="panel material-panel">
                            <div className="section-heading">
                              <h2>
                                <FolderOpen size={18} />
                                今日素材
                                <span className="count-pill">
                                  {dailyMaterials.length}
                                </span>
                              </h2>
                              <button
                                className="text-button"
                                onClick={() => navigate("materials")}
                              >
                                全部素材 <ArrowUpRight size={15} />
                              </button>
                            </div>
                            <MaterialList
                              materials={dailyMaterials}
                              state={state}
                              onOpen={setMaterialView}
                              onFeedback={feedback}
                            />
                            {!dailyMaterials.length && (
                              <Empty
                                title="今天的第一份输入"
                                text="链接、Markdown、AI 对话或一个随手记下的想法。"
                                action={
                                  <Button
                                    icon={Plus}
                                    onClick={() => setCaptureOpen(true)}
                                  >
                                    收集素材
                                  </Button>
                                }
                              />
                            )}
                          </section>
                        </div>
                        <div className="today-secondary">
                          <section className="next-writing panel">
                            <div className="section-heading">
                              <h2>
                                <NotebookPen size={18} />
                                写作的下一步
                              </h2>
                              <span className="tiny-tag">LAYER 2</span>
                            </div>
                            {state.blogs.length ? (
                              <>
                                <div className="writing-stamp">
                                  {nextWriting.lifecycle === "draft"
                                    ? "WIP · 正在酝酿"
                                    : "READY · 已形成观点"}
                                </div>
                                <h3>{nextWriting.title}</h3>
                                <p>从证据出发，把自己的判断写进去。</p>
                                <div className="writing-sources">
                                  <FileText size={14} />
                                  {nextWriting.material_ids.length} 份关联素材
                                </div>
                                <Button
                                  icon={PencilLine}
                                  className="full pink-button"
                                  onClick={() =>
                                    navigate(`studio/${nextWriting.id}`)
                                  }
                                >
                                  继续写作
                                </Button>
                              </>
                            ) : (
                              <>
                                <p>
                                  从 Report 的一个中心问题开始，整理第一篇文章。
                                </p>
                                <Button
                                  className="full"
                                  onClick={() => navigate("studio")}
                                >
                                  打开写作台
                                </Button>
                              </>
                            )}
                          </section>
                          <section className="review-card">
                            <span className="eyebrow">LET KNOWLEDGE GROW</span>
                            <div className="review-heading">
                              <BookOpen size={24} />
                              <span>
                                {due.length
                                  ? `${due.length} 个概念，值得再想一遍。`
                                  : "让理解，慢慢成为知识。"}
                              </span>
                            </div>
                            <p>读过不等于消化。用自己的话解释，再回到来源。</p>
                            <button
                              className="text-button"
                              onClick={() => navigate("library")}
                            >
                              去图书馆 <ArrowUpRight size={16} />
                            </button>
                          </section>
                          <div className="mode-note">
                            <CircleHelp size={16} />
                            <div>
                              当前使用提取式整理
                              <span>
                                内容保存在本机
                                PostgreSQL。没有向外部模型发送资料。
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                      {demoCount > 0 && (
                        <div className="demo-note">
                          <Lightbulb size={16} />
                          <span>
                            工作空间含 {demoCount}{" "}
                            份内置体验资料，均标记为“体验素材”。你可以直接开始收集自己的内容。
                          </span>
                        </div>
                      )}
                      {!state.materials.length && (
                        <div className="onboarding">
                          <Button
                            icon={Lightbulb}
                            disabled={busy}
                            onClick={() =>
                              action(() => api("/demo", {}), "体验资料已添加")
                            }
                          >
                            用一组体验资料探索
                          </Button>
                        </div>
                      )}
                    </>
                  )}
                  {page === "materials" && (
                    <>
                      <PageHeading
                        eyebrow="LAYER 0 · INPUTS"
                        title="把输入，好好收下。"
                        subtitle={`${state.materials.length} 份原始素材 · 每一份都保留出处`}
                        action={
                          <Button
                            icon={Upload}
                            onClick={() => {
                              setCaptureMode("file");
                              setCaptureOpen(true);
                            }}
                          >
                            导入文件
                          </Button>
                        }
                      />
                      <TopicFilters
                        state={state}
                        selected={selectedTopic}
                        onChange={setSelectedTopic}
                      />
                      <section className="panel">
                        <div className="table-head">
                          <span>素材 / 标题</span>
                          <span>阅读状态</span>
                        </div>
                        <MaterialList
                          materials={materialFilter}
                          state={state}
                          onOpen={setMaterialView}
                          onFeedback={feedback}
                        />
                        {!materialFilter.length && (
                          <Empty
                            title="这里还没有素材"
                            text="保存一个链接或一段文字，让积累开始。"
                            action={
                              <Button
                                icon={Plus}
                                onClick={() => setCaptureOpen(true)}
                              >
                                收集素材
                              </Button>
                            }
                          />
                        )}
                      </section>
                    </>
                  )}
                  {page === "reports" && !report && (
                    <>
                      <PageHeading
                        eyebrow="LAYER 1 · DAILY REPORTS"
                        title="日日新，留下脉络。"
                        subtitle="以一天为单位整理输入，以主题连接不同的日子。"
                        action={
                          <Button
                            icon={Sparkles}
                            onClick={generate}
                            disabled={busy}
                          >
                            生成所选日期 Report
                          </Button>
                        }
                      />
                      <div className="report-grid">
                        {state.reports.map((r) => (
                          <button
                            className="report-list-card"
                            key={r.id}
                            onClick={() => navigate(`reports/${r.id}`)}
                          >
                            <div>
                              <span className="eyebrow">DAILY REPORT</span>
                              <span className="tiny-tag">v{r.revision}</span>
                            </div>
                            <h2>{dayLabel(r.day)}</h2>
                            <p>
                              {r.ready_count} 份已整理素材 · {r.briefs.length}{" "}
                              个写作方向
                            </p>
                            <div className="report-footer">
                              <span>
                                {r.coverage_state === "partial"
                                  ? "部分整理完成"
                                  : r.coverage_state === "no_updates"
                                    ? "本期无素材"
                                    : "已整理"}
                              </span>
                              <ArrowUpRight size={18} />
                            </div>
                          </button>
                        ))}
                      </div>
                      {!state.reports.length && (
                        <Empty
                          title="还没有每日 Report"
                          text="从收集一些素材开始，再整理一份可追溯的报告。"
                        />
                      )}
                    </>
                  )}
                  {page === "reports" && report && (
                    <>
                      <button
                        className="text-button back"
                        onClick={() => {
                          navigate("reports/all");
                          setHistoricalReport(null);
                        }}
                      >
                        <ArrowLeft size={16} />
                        全部 Report
                      </button>
                      <PageHeading
                        eyebrow="LAYER 1 · DAILY REPORT"
                        title={dayLabel(report.day)}
                        subtitle={`v${report.revision} · 截止 ${timeLabel(report.cutoff_at)} · Asia/Shanghai · ${report.evidence_digests?.some((d) => d.mode === "cloud_llm") ? "真实模型证据消化" : report.evidence_digests?.length ? "提取 + 本地 mock 消化" : "提取式整理"}`}
                        action={
                          <>
                            <Button
                              icon={History}
                              onClick={() =>
                                action(
                                  () =>
                                    api<Report[]>(
                                      `/objects/${report.id}/revisions`,
                                    ),
                                  "",
                                  setHistory,
                                )
                              }
                            >
                              版本
                            </Button>
                            <a
                              className="button"
                              href={`/api/v1/export/${report.id}?revision=${report.revision}`}
                            >
                              <ArrowDownToLine size={16} />
                              导出
                            </a>
                            <Button
                              disabled={busy || !!historicalReport}
                              className="primary"
                              icon={Sparkles}
                              onClick={() =>
                                action(
                                  () =>
                                    api<Report>("/reports/runs", {
                                      date: report.day,
                                    }),
                                  "新版本已生成",
                                  (value) => navigate(`reports/${value.id}`),
                                )
                              }
                            >
                              更新 Report
                            </Button>
                          </>
                        }
                      />
                      <ReportView
                        report={report}
                        state={state}
                        onOpen={setMaterialView}
                        onWrite={newBlog}
                      />
                    </>
                  )}
                  {page === "topics" && (
                    <>
                      <PageHeading
                        eyebrow="TOPICS · CONNECT THE DOTS"
                        title="围绕问题，建立脉络。"
                        subtitle="相同主题的输入、文章与知识，放在一起思考。"
                      />
                      <div className="topic-grid">
                        {state.topics.map((t) => (
                          <button
                            className={`topic-card ${t.color} ${objectId === t.id ? "chosen" : ""}`}
                            key={t.id}
                            onClick={() => {
                              setSelectedTopic(t.id);
                              navigate(`topics/${t.id}`);
                            }}
                          >
                            <span className="topic-card-icon">
                              <Hash size={24} />
                            </span>
                            <h2>{t.name}</h2>
                            <p>
                              {
                                state.materials.filter((m) => m.topic === t.id)
                                  .length
                              }{" "}
                              份素材 ·{" "}
                              {
                                state.blogs.filter((b) => b.topic === t.id)
                                  .length
                              }{" "}
                              篇博客 ·{" "}
                              {
                                state.entries.filter((e) => e.topic === t.id)
                                  .length
                              }{" "}
                              个概念
                            </p>
                            <ArrowUpRight size={20} />
                          </button>
                        ))}
                      </div>
                      {objectId && (
                        <section className="panel">
                          <div className="section-heading">
                            <h2>这个主题的输入</h2>
                          </div>
                          <MaterialList
                            materials={state.materials.filter(
                              (m) => m.topic === objectId,
                            )}
                            state={state}
                            onOpen={setMaterialView}
                            onFeedback={feedback}
                          />
                        </section>
                      )}
                    </>
                  )}
                  {page === "studio" && !blog && (
                    <>
                      <PageHeading
                        eyebrow="LAYER 2 · WRITING STUDIO"
                        title="从一个好问题，开始写。"
                        subtitle="素材是起点，你的理解才是文章的中心。"
                      />
                      <div className="studio-grid">
                        {state.blogs.map((b) => (
                          <button
                            className="blog-card"
                            key={b.id}
                            onClick={() => navigate(`studio/${b.id}`)}
                          >
                            <div>
                              <TopicBadge topic={b.topic} state={state} />
                              <span className="tiny-tag">
                                {b.lifecycle === "accepted" ? "已确认" : "草稿"}
                              </span>
                            </div>
                            <NotebookPen size={32} strokeWidth={1.3} />
                            <h2>{b.title}</h2>
                            <p>
                              {b.material_ids.length} 份来源 · v{b.revision}
                              {b.is_demo ? " · 体验文章" : ""}
                            </p>
                            <span className="text-button">
                              继续写作 <ArrowUpRight size={15} />
                            </span>
                          </button>
                        ))}
                      </div>
                      {todayReport?.briefs.length ? (
                        <section className="panel">
                          <div className="section-heading">
                            <h2>
                              <Lightbulb size={18} />
                              今日 Report 带来的选题
                            </h2>
                          </div>
                          {todayReport.briefs.map((brief, i) => (
                            <div
                              className="brief-row"
                              key={`${brief.topic}:${i}`}
                            >
                              <span className="brief-number">0{i + 1}</span>
                              <div>
                                <h3>{brief.title}</h3>
                                <p>{brief.question}</p>
                              </div>
                              <Button
                                disabled={busy}
                                icon={Plus}
                                onClick={() =>
                                  newBlog(
                                    brief.material_ids,
                                    brief.title,
                                    todayReport.id,
                                  )
                                }
                              >
                                开始写作
                              </Button>
                            </div>
                          ))}
                        </section>
                      ) : (
                        !state.blogs.length && (
                          <Empty
                            icon={NotebookPen}
                            title="第一篇文章，从素材出发"
                            text="先整理一份 Report，或在素材详情里选择“整理成博客”。"
                          />
                        )
                      )}
                    </>
                  )}
                  {page === "studio" && blog && (
                    <BlogEditor
                      key={blog.id}
                      blog={blog}
                      state={state}
                      busy={busy}
                      onSave={async (payload) => {
                        const saved = await api<Blog>(
                          `/blogs/${blog.id}/revisions`,
                          payload,
                        );
                        await reload();
                        return saved;
                      }}
                      onAccept={() =>
                        action(
                          () =>
                            api<Blog>(`/blogs/${blog.id}/accept`, {
                              revision: blog.revision,
                            }),
                          "文章已确认，可以整理到图书馆",
                        )
                      }
                      onPropose={() =>
                        action(
                          () =>
                            api<Proposal>("/library/proposals", {
                              blog_id: blog.id,
                            }),
                          "",
                          setProposalView,
                        )
                      }
                      onSource={setMaterialView}
                    />
                  )}
                  {page === "library" && !entry && (
                    <>
                      <PageHeading
                        eyebrow="LAYER 3 · PERSONAL LIBRARY"
                        title="让知识，长成自己的体系。"
                        subtitle={`${state.entries.length} 个知识条目 · ${due.length} 个可以复习的概念`}
                      />
                      {state.proposals.some((p) => p.status === "pending") && (
                        <section className="panel proposals-panel">
                          <div className="section-heading">
                            <h2>待确认的知识整理</h2>
                          </div>
                          {state.proposals
                            .filter((p) => p.status === "pending")
                            .map((p) => (
                              <div className="brief-row" key={p.id}>
                                <BookOpen size={23} />
                                <div>
                                  <h3>{p.title}</h3>
                                  <p>来自已确认博客 · {p.book}</p>
                                </div>
                                <Button onClick={() => setProposalView(p)}>
                                  查看并采纳
                                </Button>
                              </div>
                            ))}
                        </section>
                      )}
                      <div className="library-grid">
                        {state.entries.map((e) => (
                          <button
                            key={e.id}
                            className="library-card"
                            onClick={() => navigate(`library/${e.id}`)}
                          >
                            <div className="book-cover">
                              <BookOpen size={42} strokeWidth={1.2} />
                              <small>PERSONAL LIBRARY</small>
                              <strong>{e.book}</strong>
                              <span className="book-line" />
                            </div>
                            <div className="book-info">
                              <TopicBadge topic={e.topic} state={state} />
                              <h2>{e.title}</h2>
                              <p>
                                {e.material_ids.length} 份来源
                                {e.is_demo ? " · 体验条目" : ""}
                              </p>
                              <span
                                className={
                                  e.due_day <= state.today
                                    ? "review-due"
                                    : "muted"
                                }
                              >
                                <Clock3 size={14} />
                                {e.due_day <= state.today
                                  ? "可以复习了"
                                  : `${e.due_day} 复习`}
                              </span>
                            </div>
                          </button>
                        ))}
                      </div>
                      {!state.entries.length && (
                        <Empty
                          icon={BookOpen}
                          title="图书馆，从一个概念开始"
                          text="在写作台确认一篇文章，再把它整理成知识条目。"
                          action={
                            <Button onClick={() => navigate("studio")}>
                              去写作台
                            </Button>
                          }
                        />
                      )}
                    </>
                  )}
                  {page === "library" && entry && (
                    <>
                      <button
                        className="text-button back"
                        onClick={() => navigate("library")}
                      >
                        <ArrowLeft size={16} />
                        回到图书馆
                      </button>
                      <PageHeading
                        eyebrow={`LAYER 3 · ${entry.book}`}
                        title={entry.title}
                        subtitle={`v${entry.revision} · ${entry.material_ids.length} 份原始来源${entry.is_demo ? " · 体验条目" : ""}`}
                        action={
                          <a
                            className="button"
                            href={`/api/v1/export/${entry.id}`}
                          >
                            <ArrowDownToLine size={16} />
                            导出
                          </a>
                        }
                      />
                      <div className="reader-layout">
                        <section className="panel prose-panel">
                          {!entry.source_snapshots?.length && (
                            <p className="draft-warning">
                              旧条目没有冻结来源快照；侧栏只能显示当前素材，不代表当时版本。
                            </p>
                          )}
                          <Markdown sources={entry.source_snapshots}>
                            {entry.body}
                          </Markdown>
                        </section>
                        <aside>
                          <section className="panel">
                            <div className="section-heading">
                              <h2>用自己的话，再解释一次</h2>
                            </div>
                            <p className="reading-note">
                              读过，不等于理解。尝试闭上原文，回答这个概念解决了什么问题、何时失效。
                            </p>
                            <div className="review-buttons">
                              {[
                                ["clear", "能解释"],
                                ["fuzzy", "还模糊"],
                                ["forgot", "忘记了"],
                              ].map(([value, label]) => (
                                <Button
                                  disabled={busy}
                                  key={value}
                                  onClick={() =>
                                    action(
                                      () =>
                                        api(
                                          `/library/entries/${entry.id}/reviews`,
                                          { grade: value },
                                        ),
                                      "复习记录已保存，下一次日期已更新",
                                    )
                                  }
                                >
                                  {label}
                                </Button>
                              ))}
                            </div>
                            <small className="muted">
                              下次复习：{entry.due_day} · {entry.reviews.length}{" "}
                              次记录
                            </small>
                          </section>
                          <Evidence
                            materials={
                              entry.source_snapshots?.length
                                ? entry.source_snapshots
                                : state.materials.filter((m) =>
                                    entry.material_ids.includes(m.id),
                                  )
                            }
                            onOpen={setMaterialView}
                          />
                        </aside>
                      </div>
                    </>
                  )}
                  {page === "jobs" && (
                    <ProcessingView
                      state={state}
                      busy={busy}
                      onSubmit={submitDigest}
                      onSource={openEvidence}
                      onAction={(job, kind, consent) =>
                        action(
                          () =>
                            api(
                              `/jobs/${job.id}/${kind}`,
                              kind === "retry"
                                ? {
                                    cloud_consent: !!consent,
                                    provider_profile:
                                      state.processing.profiles.find(
                                        (p) =>
                                          p.provider === "openai_compatible",
                                      )?.profile_id,
                                  }
                                : {},
                            ),
                          kind === "cancel"
                            ? "任务已取消，旧 worker 无法交付"
                            : "任务已重新排队",
                        )
                      }
                    />
                  )}
                  {page === "sources" && (
                    <Sources
                      state={state}
                      busy={busy}
                      onAdd={(payload) =>
                        action(
                          () => api("/sources", payload),
                          "关注来源已保存；自动轮询尚未启用",
                        )
                      }
                    />
                  )}
                  {page === "settings" && (
                    <Settings
                      onRestore={(file) =>
                        action(
                          () => upload(file, "/workspace/restore"),
                          "备份已恢复，原件与全部版本保留",
                        )
                      }
                      state={state}
                      busy={busy}
                      onSave={(payload) =>
                        action(
                          () => api("/settings", payload, "PATCH"),
                          "偏好已保存",
                        )
                      }
                      onDemo={() =>
                        action(() => api("/demo", {}), "体验资料已添加")
                      }
                    />
                  )}
                </>
              )}
            </>
          )}
        </main>
        <footer className="workspace-footer">
          <span>盘铭 · 日日新，又日新。</span>
          <span>原文可追溯，理解由你完成。</span>
        </footer>
      </div>
      {captureOpen && (
        <CaptureModal
          initialMode={captureMode}
          busy={busy}
          onClose={() => {
            setCaptureOpen(false);
            setCaptureMode("note");
          }}
          state={state}
          onSubmit={(payload) =>
            action(
              () => api<Material>("/captures", payload),
              "素材已归档到 Layer0",
              () => {
                setCaptureOpen(false);
                setCaptureMode("note");
              },
            )
          }
          onUpload={(file) =>
            action(
              () => upload(file),
              "原文件已保存",
              () => {
                setCaptureOpen(false);
                setCaptureMode("note");
              },
            )
          }
        />
      )}
      {materialView && (
        <MaterialModal
          material={materialView}
          state={state}
          busy={busy}
          onClose={closeMaterial}
          onFeedback={(value) => feedback(materialView, value)}
          onDigest={(provider = "mock", consent = false) =>
            submitDigest([sourceRef(materialView)], {
              provider,
              cloud_consent: consent,
              provider_profile:
                provider === "openai_compatible"
                  ? state.processing.profiles.find(
                      (p) => p.provider === "openai_compatible",
                    )?.profile_id
                  : undefined,
            })
          }
          onPolicy={(policy) =>
            action(
              () =>
                api<Material>(
                  `/materials/${materialView.id}/policy`,
                  {
                    revision: materialView.revision,
                    processing_policy: policy,
                    provider_profile: state.processing.profiles.find(
                      (p) => p.provider === "openai_compatible",
                    )?.profile_id,
                  },
                  "PATCH",
                ),
              policy === "cloud_allowed"
                ? "当前正文已授权给所选服务，尚未外发"
                : "云端授权已撤回，未完成任务已取消",
              setMaterialView,
            )
          }
          onUpdate={(body) =>
            action(
              () =>
                api<Material>(`/materials/${materialView.id}/revisions`, {
                  title: materialView.title,
                  body,
                  revision: materialView.revision,
                }),
              "正文已保存为新版本，旧原件仍保留",
              setMaterialView,
            )
          }
          onWrite={() => {
            newBlog(
              [materialView.id],
              materialView.title,
              page === "reports" ? report?.id : undefined,
              page === "reports" ? report?.revision : undefined,
              [sourceRef(materialView)],
            );
            setMaterialView(null);
          }}
        />
      )}
      {history && (
        <Modal title="Report 版本" onClose={() => setHistory(null)}>
          <div className="version-list">
            {history.map((r) => (
              <button
                key={r.revision}
                onClick={() => {
                  setHistoricalReport(r);
                  setHistory(null);
                }}
              >
                <History size={18} />
                <span>
                  <strong>v{r.revision}</strong>
                  <small>
                    {new Date(r.cutoff_at).toLocaleString("zh-CN")} ·{" "}
                    {r.sources.length} 份输入
                  </small>
                </span>
                <ChevronRight size={18} />
              </button>
            ))}
          </div>
        </Modal>
      )}
      {proposalView && (
        <Modal
          title="确认图书馆整理"
          onClose={() => setProposalView(null)}
          wide
        >
          <div className="proposal-intro">
            <BookOpen size={25} />
            <div>
              <strong>{proposalView.title}</strong>
              <p>将保存到「{proposalView.book}」，并保留博客与原始素材来源。</p>
            </div>
          </div>
          <Markdown sources={proposalView.source_snapshots}>
            {proposalView.body}
          </Markdown>
          <div className="modal-actions">
            <Button onClick={() => setProposalView(null)}>暂不采纳</Button>
            <Button
              disabled={busy}
              className="primary"
              icon={Check}
              onClick={() =>
                action(
                  () =>
                    api<Entry>(
                      `/library/proposals/${proposalView.id}/accept`,
                      {},
                    ),
                  "知识条目已纳入图书馆",
                  (value) => {
                    setProposalView(null);
                    navigate(`library/${value.id}`);
                  },
                )
              }
            >
              采纳入馆
            </Button>
          </div>
        </Modal>
      )}
      {toast && (
        <div className="toast" role="status">
          <Check size={18} />
          <span>{toast}</span>
          <button
            className="icon-button"
            aria-label="关闭提示"
            onClick={() => setToast("")}
          >
            <X size={15} />
          </button>
        </div>
      )}
    </div>
  );
}

function shiftDay(value: string, shift: number) {
  const day = new Date(`${value}T12:00:00`);
  day.setDate(day.getDate() + shift);
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
}
function PageHeading({
  eyebrow,
  title,
  subtitle,
  action,
}: {
  eyebrow: string;
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {action && <div className="heading-actions">{action}</div>}
    </div>
  );
}
function TopicFilters({
  state,
  selected,
  onChange,
}: {
  state: State;
  selected: string;
  onChange: (s: string) => void;
}) {
  return (
    <div className="filters">
      <button
        className={selected === "all" ? "selected" : ""}
        onClick={() => onChange("all")}
      >
        全部素材
      </button>
      {state.topics.map((t) => (
        <button
          key={t.id}
          className={selected === t.id ? "selected" : ""}
          onClick={() => onChange(t.id)}
        >
          {t.name}
        </button>
      ))}
    </div>
  );
}
function MaterialList({
  materials,
  state,
  onOpen,
  onFeedback,
}: {
  materials: Material[];
  state: State;
  onOpen: (m: Material) => void;
  onFeedback: (m: Material, value: string) => void;
}) {
  return (
    <div className="material-list">
      {materials.map((material) => {
        const Icon = kindIcons[material.kind] || FileText;
        return (
          <div className="material-row" key={material.id}>
            <button className="material-main" onClick={() => onOpen(material)}>
              <span className={`material-icon ${topicColors[material.topic]}`}>
                <Icon size={21} />
              </span>
              <span className="material-info">
                <strong>{material.title}</strong>
                <span>
                  {kinds[material.kind]}
                  <i>·</i>
                  {timeLabel(material.created_at)}
                  {material.is_demo && (
                    <>
                      <i>·</i>
                      <span className="demo-label">体验素材</span>
                    </>
                  )}
                  <span className="material-topic">
                    <i>·</i>
                    {state.topics.find((t) => t.id === material.topic)?.name}
                  </span>
                </span>
              </span>
            </button>
            <div className="material-tail">
              {material.parse_state === "ready" ? (
                <select
                  aria-label={`${material.title} 的阅读状态`}
                  className={`status-select ${material.feedback === "useful" ? "useful" : ""}`}
                  value={material.feedback}
                  onChange={(e) => onFeedback(material, e.target.value)}
                >
                  {Object.entries(feedbackLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              ) : (
                <span className="badge gray">
                  {material.parse_state === "stored_only"
                    ? "仅存原件"
                    : "待补正文"}
                </span>
              )}
              <button
                className="icon-button"
                aria-label={`阅读 ${material.title}`}
                onClick={() => onOpen(material)}
              >
                <ChevronRight size={17} />
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
function Evidence({
  materials,
  onOpen,
}: {
  materials: Material[];
  onOpen: (m: Material) => void;
}) {
  return (
    <section className="panel evidence">
      <div className="section-heading">
        <h2>
          <Link2 size={17} />
          原始证据
        </h2>
        <span className="count-pill">{materials.length}</span>
      </div>
      {materials.map((m) => (
        <button key={m.id} onClick={() => onOpen(m)}>
          <FileText size={17} />
          <span>
            {m.title}
            <small>
              {kinds[m.kind]} · v{m.revision}
            </small>
          </span>
          <ArrowUpRight size={15} />
        </button>
      ))}
    </section>
  );
}
function ReportView({
  report,
  state,
  onOpen,
  onWrite,
}: {
  report: Report;
  state: State;
  onOpen: (m: Material) => void;
  onWrite: (
    ids: string[],
    title: string,
    reportId: string,
    reportRevision: number,
  ) => void;
}) {
  return (
    <div className="reader-layout">
      <div>
        <div className="report-coverage">
          <CheckCheck size={20} />
          <div>
            <strong>
              {report.coverage_state === "partial"
                ? "部分整理完成"
                : report.coverage_state === "no_updates"
                  ? "本期没有新素材"
                  : "本次输入已整理"}
            </strong>
            <span>
              {report.ready_count}/{report.sources.length} 份可用正文
              {report.pending_count > 0
                ? `，${report.pending_count} 份等待正文或解析`
                : " · 每条摘录都可以回到原文"}
            </span>
          </div>
        </div>
        <section className="panel report-prose">
          <div className="section-heading">
            <h2>今日重点与主题归纳</h2>
            <span className="tiny-tag">原文摘录</span>
          </div>
          {report.groups
            .filter((g) => g.materials.length)
            .map((g) => (
              <div className="report-topic" key={g.topic}>
                <div>
                  <TopicBadge topic={g.topic} state={state} />
                  <span className="muted">{g.materials.length} 份线索</span>
                </div>
                {report.sources
                  .filter((m) => g.materials.includes(m.id))
                  .map((m) => (
                    <article key={m.id}>
                      <h3>{m.title}</h3>
                      {m.digest.excerpts.map((q, i) => (
                        <blockquote key={i}>{q.text}</blockquote>
                      ))}
                      <button className="citation" onClick={() => onOpen(m)}>
                        <Link2 size={13} />
                        原文 · {m.digest.excerpts[0]?.line || 1} 行起 · v
                        {m.revision}
                      </button>
                    </article>
                  ))}
              </div>
            ))}
          {!report.ready_count && (
            <Empty
              title="还没有可引用的正文"
              text="为链接补充正文或上传一份 Markdown，然后更新报告。"
            />
          )}
        </section>
        <section className="panel report-briefs">
          <div className="section-heading">
            <h2>
              <NotebookPen size={18} />
              可以继续写的问题
            </h2>
          </div>
          {report.briefs.map((b, i) => (
            <div className="brief-row" key={`${b.topic}:${i}`}>
              <span className="brief-number">0{i + 1}</span>
              <div>
                <h3>{b.title}</h3>
                <p>{b.question}</p>
                <small>{b.material_ids.length} 份材料 · 待补充个人观点</small>
              </div>
              <Button
                icon={PencilLine}
                onClick={() =>
                  onWrite(b.material_ids, b.title, report.id, report.revision)
                }
              >
                开始写作
              </Button>
            </div>
          ))}
          {!report.briefs.length && (
            <p className="reading-note">本期证据不足，暂不生成写作选题。</p>
          )}
        </section>
        {(report.evidence_digests || []).map((d) => (
          <DigestCard
            key={d.id}
            digest={d}
            onSource={(ref) => {
              const material = report.sources.find(
                (m) =>
                  m.id === ref.material_id &&
                  m.revision === ref.material_revision,
              );
              if (material) onOpen(material);
            }}
          />
        ))}
      </div>
      <aside>
        <section className="panel">
          <div className="section-heading">
            <h2>本次输入</h2>
          </div>
          <div className="report-numbers">
            <span>
              原始素材<strong>{report.sources.length}</strong>
            </span>
            <span>
              有正文<strong>{report.ready_count}</strong>
            </span>
            <span>
              主题方向
              <strong>
                {report.groups.filter((g) => g.materials.length).length}
              </strong>
            </span>
          </div>
          <p className="reading-note">
            报告保留生成时的素材快照。更新会生成新版本，历史仍然可读。
          </p>
          {report.sources.some(
            (m) =>
              (m as Material & { inclusion_reason?: string })
                .inclusion_reason === "carryover",
          ) && (
            <p className="reading-note">包含前日补录素材，原采集日期仍保留。</p>
          )}
        </section>
        <Evidence materials={report.sources} onOpen={onOpen} />
        <div className="mode-note">
          <Sparkles size={16} />
          <div>
            {report.evidence_digests?.length
              ? report.evidence_digests.some((d) => d.mode === "cloud_llm")
                ? "包含真实模型证据消化"
                : "包含证据化 mock 消化"
              : "原文提取模式"}
            <span>
              提取与模型归纳都是待复核线索，不是自动事实核验；证据校验不代表结论成立。
            </span>
          </div>
        </div>
      </aside>
    </div>
  );
}

function BlogEditor({
  blog,
  state,
  busy,
  onSave,
  onAccept,
  onPropose,
  onSource,
}: {
  blog: Blog;
  state: State;
  busy: boolean;
  onSave: (p: {
    title: string;
    body: string;
    revision: number;
  }) => Promise<Blog>;
  onAccept: () => void;
  onPropose: () => void;
  onSource: (m: Material) => void;
}) {
  const [draftStore] = useState(() => {
    try {
      return new DraftStore(window.localStorage, blog.id, crypto.randomUUID());
    } catch {
      return null;
    }
  });
  const [base, setBase] = useState<DraftBase>({
    title: blog.title,
    body: blog.body,
    revision: blog.revision,
  });
  const [title, setTitle] = useState(blog.title);
  const [body, setBody] = useState(blog.body);
  const [recovery, setRecovery] = useState<Draft[]>(() => {
    try {
      return draftStore?.list() || [];
    } catch {
      return [];
    }
  });
  const [storageError, setStorageError] = useState(
    draftStore ? "" : "浏览器存储不可用，请下载本机稿或保存到服务器。",
  );
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState<Blog | null>(null);
  const [saving, setSaving] = useState(false);
  const locked = busy || saving;
  const [preview, setPreview] = useState(false);
  const dirty = title !== base.title || body !== base.body;
  const stale =
    blog.revision !== base.revision &&
    (title !== blog.title || body !== blog.body);
  const refreshDrafts = useCallback(() => {
    try {
      setRecovery(
        draftStore?.list().filter((d) => d.editor_id !== draftStore.editorId) ||
          [],
      );
    } catch {
      setStorageError("无法读取本机草稿，请保留页面并下载本机稿。");
    }
  }, [draftStore]);
  useEffect(() => {
    const changed = (e: StorageEvent) => {
      if (e.key?.startsWith("panming.draft.")) refreshDrafts();
    };
    window.addEventListener("storage", changed);
    return () => window.removeEventListener("storage", changed);
  }, [refreshDrafts]);
  useEffect(() => {
    if (dirty) {
      try {
        draftStore?.save(base, title, body);
        if (draftStore) setStorageError("");
      } catch {
        setStorageError(
          "本机草稿暂存失败（空间不足或存储被禁用）。内容仍在此页面，请下载或保存到服务器。",
        );
      }
    } else if (
      title === blog.title &&
      body === blog.body &&
      base.revision !== blog.revision
    ) {
      setBase({ title: blog.title, body: blog.body, revision: blog.revision });
    }
  }, [
    title,
    body,
    dirty,
    base,
    draftStore,
    blog.title,
    blog.body,
    blog.revision,
  ]);
  const save = useCallback(async () => {
    if (locked || !dirty || !title.trim()) return;
    setSaving(true);
    setError("");
    let savedDraft: Draft | undefined;
    try {
      if (draftStore) savedDraft = draftStore.save(base, title, body);
    } catch {
      setStorageError("本机暂存不可用，正在尝试服务器保存。");
    }
    try {
      const saved = await onSave({ title, body, revision: base.revision });
      setBase({
        title: saved.title,
        body: saved.body,
        revision: saved.revision,
      });
      setTitle(saved.title);
      setBody(saved.body);
      try {
        if (savedDraft) draftStore?.clearSaved(savedDraft);
      } catch {
        setStorageError("服务器已保存，本机备份暂未清理。");
      }
      refreshDrafts();
      setConflict(null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        try {
          setConflict(await api<Blog>(`/objects/${blog.id}`));
        } catch {
          setError("无法读取服务器版本。你的本机稿仍保留，可以下载后再试。");
        }
      } else
        setError(
          e instanceof Error ? e.message : "保存失败，请重试；本机稿保留。",
        );
    } finally {
      setSaving(false);
    }
  }, [
    locked,
    dirty,
    title,
    body,
    base,
    onSave,
    draftStore,
    blog.id,
    refreshDrafts,
  ]);
  async function recover(d: Draft) {
    try {
      const original = await api<Blog>(
        `/objects/${blog.id}?revision=${d.base.revision}`,
      );
      setBase({
        title: original.title,
        body: original.body,
        revision: original.revision,
      });
      setTitle(d.title);
      setBody(d.body);
      setError("");
    } catch {
      setError("这份草稿的基础版本不可读取。原稿不会删除，请先下载备份。");
    }
  }
  async function copyDraft() {
    if (locked) return;
    setSaving(true);
    setError("");
    try {
      const created = await api<Blog>("/blogs", {
        title: `${title.slice(0, 190)} · 副本`,
        material_ids: blog.material_ids,
        source_refs: blog.source_snapshots?.map(sourceRef),
      });
      await onSaveCopy(created);
    } catch (e) {
      setError(e instanceof Error ? e.message : "副本保存失败；原本机稿保留。");
    } finally {
      setSaving(false);
    }
  }
  async function onSaveCopy(created: Blog) {
    await api<Blog>(`/blogs/${created.id}/revisions`, {
      title: created.title,
      body,
      revision: created.revision,
    });
    window.location.href = `/#/studio/${created.id}`;
    window.location.reload();
  }
  useEffect(() => {
    const keys = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        void save();
      }
    };
    document.addEventListener("keydown", keys);
    return () => document.removeEventListener("keydown", keys);
  }, [save]);
  return (
    <>
      <button className="text-button back" onClick={() => navigate("studio")}>
        <ArrowLeft size={16} />
        回到写作台
      </button>
      <PageHeading
        eyebrow="LAYER 2 · WRITING STUDIO"
        title="你的素材，你的理解。"
        subtitle={`${blog.lifecycle === "accepted" ? "已确认" : "草稿"} · v${blog.revision} · ${dirty ? "修改暂存本机，请保存到服务器" : "已保存到工作空间"}`}
        action={
          <>
            <Button
              disabled={locked || !dirty || !title.trim()}
              className="primary"
              icon={Check}
              onClick={() => void save()}
            >
              保存修改
            </Button>
            <Button
              icon={ArrowDownToLine}
              onClick={() => downloadLocal(title, body)}
            >
              下载本机稿
            </Button>
            <a className="button" href={`/api/v1/export/${blog.id}`}>
              <ArrowDownToLine size={16} />
              导出已保存版
            </a>
          </>
        }
      />
      {(error || storageError || stale) && (
        <div className="draft-warning" role="alert">
          {error ||
            storageError ||
            (stale
              ? "服务器版本已变化。本机内容保留，请比较后继续。"
              : "")}{" "}
          {stale && (
            <Button
              onClick={async () => {
                try {
                  setConflict(await api<Blog>(`/objects/${blog.id}`));
                } catch (e) {
                  setError(e instanceof Error ? e.message : "无法读取服务器");
                }
              }}
            >
              比较服务器版本
            </Button>
          )}
        </div>
      )}
      {recovery.length > 0 && (
        <section className="panel draft-recovery">
          <h2>发现 {recovery.length} 份本机草稿备份</h2>
          <p className="reading-note">
            每个窗口独立保存。恢复会复制为当前窗口的新分支，不删除原稿。
          </p>
          {recovery.map((d) => (
            <div className="draft-branch" key={d.editor_id}>
              <span>
                {d.title}
                <small>
                  基础 v{d.base.revision} ·{" "}
                  {d.updated_at === "旧版草稿"
                    ? d.updated_at
                    : new Date(d.updated_at).toLocaleString("zh-CN")}
                </small>
              </span>
              <Button disabled={locked} onClick={() => void recover(d)}>
                恢复草稿 {d.editor_id.slice(0, 6)}
              </Button>
              <Button onClick={() => downloadLocal(d.title, d.body)}>
                下载
              </Button>
            </div>
          ))}
        </section>
      )}
      <div className="editor-layout">
        <section className="panel editor-panel">
          <input
            className="article-title-input"
            aria-label="博客标题"
            readOnly={locked}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <div className="editor-toolbar">
            <div className="segmented">
              <button
                className={!preview ? "active" : ""}
                onClick={() => setPreview(false)}
              >
                <PencilLine size={14} />
                编辑
              </button>
              <button
                className={preview ? "active" : ""}
                onClick={() => setPreview(true)}
              >
                <BookOpen size={14} />
                预览
              </button>
            </div>
            <span>Markdown · 草稿本机自动暂存</span>
          </div>
          {preview ? (
            <div className="editor-preview">
              <Markdown sources={blog.source_snapshots}>{body}</Markdown>
            </div>
          ) : (
            <textarea
              className="article-editor"
              aria-label="博客正文"
              readOnly={locked}
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          )}
        </section>
        <aside>
          <section className="panel">
            <div className="section-heading">
              <h2>让文章走向知识</h2>
            </div>
            <p className="reading-note">
              检查证据，写下自己的判断，再确认文章。图书馆整理会让你再次确认。
            </p>
            {blog.lifecycle === "accepted" ? (
              <Button
                disabled={locked || dirty || stale}
                className="full pink-button"
                icon={BookOpen}
                onClick={onPropose}
              >
                整理到图书馆
              </Button>
            ) : (
              <Button
                disabled={locked || dirty || stale}
                className="full"
                icon={CheckCheck}
                onClick={onAccept}
              >
                确认这篇文章
              </Button>
            )}
            {dirty && <small className="muted">请先保存当前修改</small>}
          </section>
          <Evidence
            materials={
              blog.source_snapshots?.length
                ? blog.source_snapshots
                : state.materials.filter((m) =>
                    blog.material_ids.includes(m.id),
                  )
            }
            onOpen={onSource}
          />
          {!blog.source_snapshots?.length && (
            <p className="draft-warning">
              旧文章没有冻结来源快照；当前素材不是当时证据版本。原文不会被自动回填。
            </p>
          )}
          <div className="mode-note">
            <PencilLine size={16} />
            <div>
              个人理解由你完成
              <span>原文摘录之外的观点和实验，需要你补充与验证。</span>
            </div>
          </div>
        </aside>
      </div>
      {conflict && (
        <Modal
          title="比较并解决版本冲突"
          onClose={() => setConflict(null)}
          wide
        >
          <p className="reading-note">
            服务器 v{conflict.revision}，本机稿基于 v{base.revision}
            。不会自动覆盖；请检查标题与正文，再选择处理方式。
          </p>
          <div className="conflict-columns">
            <label>
              基础版 · {base.title}
              <textarea aria-label="冲突基础版" readOnly value={base.body} />
            </label>
            <label>
              本机稿 · {title}
              <textarea aria-label="冲突本机稿" readOnly value={body} />
            </label>
            <label>
              服务器版 · {conflict.title}
              <textarea
                aria-label="冲突服务器版"
                readOnly
                value={conflict.body}
              />
            </label>
          </div>
          <p className="reading-note">
            “基于新版继续”保留本机文字并更新基础版本；你仍需手动合并、点击保存。若服务器再次变化会继续拦截。
          </p>
          <div className="modal-actions">
            <Button onClick={() => downloadLocal(title, body)}>
              下载本机稿
            </Button>
            <Button disabled={locked} onClick={() => void copyDraft()}>
              另存为副本
            </Button>
            <Button
              disabled={locked}
              onClick={() => {
                setBase({
                  title: conflict.title,
                  body: conflict.body,
                  revision: conflict.revision,
                });
                setTitle(conflict.title);
                setBody(conflict.body);
                setConflict(null);
              }}
            >
              使用服务器内容，保留本机备份
            </Button>
            <Button
              disabled={locked}
              className="primary"
              onClick={() => {
                setBase({
                  title: conflict.title,
                  body: conflict.body,
                  revision: conflict.revision,
                });
                setConflict(null);
              }}
            >
              保留本机稿，基于新版继续
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}

function Modal({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    return () => ref.current?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className={`modal ${wide ? "wide" : ""}`}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      <div className="modal-heading">
        <h2>{title}</h2>
        <button className="icon-button" aria-label="关闭面板" onClick={onClose}>
          <X size={20} />
        </button>
      </div>
      <div className="modal-content">{children}</div>
    </dialog>
  );
}
function CaptureModal({
  initialMode,
  state,
  busy,
  onClose,
  onSubmit,
  onUpload,
}: {
  initialMode: string;
  state: State;
  busy: boolean;
  onClose: () => void;
  onSubmit: (data: unknown) => void;
  onUpload: (file: File) => void;
}) {
  const [mode, setMode] = useState(initialMode);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [url, setUrl] = useState("");
  const [topic, setTopic] = useState("");
  const [reason, setReason] = useState("");
  const [file, setFile] = useState<File | null>(null);
  return (
    <Modal title="收集一份新的输入" onClose={onClose}>
      <div className="capture-tabs">
        {[
          ["note", "文字 / 笔记", PencilLine],
          ["url", "网页链接", Link2],
          ["file", "文件素材", Upload],
          ["chat", "AI 对话", MessageSquare],
        ].map(([value, label, Icon]) => {
          const I = Icon as LucideIcon;
          return (
            <button
              key={value as string}
              className={mode === value ? "active" : ""}
              onClick={() => setMode(value as string)}
            >
              <I size={16} />
              {label as string}
            </button>
          );
        })}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (mode === "file" && file) onUpload(file);
          else
            onSubmit({
              title,
              content,
              url: mode === "url" ? url : "",
              topic,
              reason,
              kind:
                mode === "chat"
                  ? "ai_conversation"
                  : mode === "url"
                    ? "web_page"
                    : "user_note",
            });
        }}
      >
        {mode === "file" ? (
          <label className="upload-area">
            <Upload size={30} />
            <strong>{file ? file.name : "选择一份文件"}</strong>
            <span>Markdown、TXT、对话导出 · 上限 8 MiB</span>
            <input
              aria-label="选择上传文件"
              type="file"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </label>
        ) : (
          <>
            <label>
              标题
              <input
                autoFocus
                required
                maxLength={200}
                placeholder="给这份输入一个名字"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </label>
            {mode === "url" && (
              <label>
                原文链接
                <input
                  required
                  type="url"
                  placeholder="https://…"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                />
              </label>
            )}
            <label>
              {mode === "url"
                ? "正文摘录（可选）"
                : mode === "chat"
                  ? "对话原文"
                  : "内容"}
              <textarea
                required={mode !== "url"}
                rows={6}
                placeholder={
                  mode === "chat"
                    ? "粘贴对话，保留用户与助手的角色…"
                    : "留下原文，或者记下刚刚想到的问题…"
                }
                value={content}
                onChange={(e) => setContent(e.target.value)}
              />
            </label>
            {mode === "url" && (
              <small className="muted">
                本版保存链接与提供的正文，不会自动读取受限网站。
              </small>
            )}
            <div className="form-row">
              <label>
                主题
                <select
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                >
                  <option value="">根据内容分类</option>
                  {state.topics.map((t) => (
                    <option value={t.id} key={t.id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                为什么保存
                <input
                  placeholder="可选，留下你的关注点"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              </label>
            </div>
          </>
        )}
        <div className="capture-policy">
          <Bookmark size={15} />
          <span>原件保留 · 本机私有 · 不向外部模型发送</span>
        </div>
        <div className="modal-actions">
          <Button type="button" onClick={onClose}>
            取消
          </Button>
          <Button
            type="submit"
            className="primary"
            icon={Plus}
            disabled={
              busy ||
              (mode === "file"
                ? !file
                : !title.trim() || (mode === "url" ? !url : !content.trim()))
            }
          >
            {busy ? "正在保存…" : "归档到素材库"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
function MaterialModal({
  material,
  state,
  busy,
  onClose,
  onFeedback,
  onUpdate,
  onWrite,
  onDigest,
  onPolicy,
}: {
  material: Material;
  state: State;
  busy: boolean;
  onClose: () => void;
  onFeedback: (value: string) => void;
  onUpdate: (body: string) => Promise<Material | undefined>;
  onWrite: () => void;
  onDigest: (
    provider?: "mock" | "openai_compatible",
    consent?: boolean,
  ) => void;
  onPolicy: (policy: "local_only" | "cloud_allowed") => void;
}) {
  const [tab, setTab] = useState("digest");
  const [editing, setEditing] = useState(false);
  const [body, setBody] = useState(material.content);
  const current = state.materials.find((m) => m.id === material.id);
  const pinned = !!current && current.revision !== material.revision;
  const cloud = state.processing.profiles.find(
    (p) => p.provider === "openai_compatible",
  );
  const allowed =
    material.processing_policy === "cloud_allowed" &&
    material.cloud_allowed_profile === cloud?.profile_id;
  const [cloudConsent, setCloudConsent] = useState(false);
  return (
    <Modal title={material.title} onClose={onClose} wide>
      <div className="material-detail-meta">
        <TopicBadge topic={material.topic} state={state} />
        <span>{kinds[material.kind]}</span>
        <span>{material.day}</span>
        <span>v{material.revision}</span>
        {material.is_demo && <span className="demo-label">体验素材</span>}
      </div>
      {pinned && (
        <p className="reading-note">
          正在阅读固定证据 v{material.revision}；当前素材为 v{current?.revision}
          。旧引用不会自动更新。
        </p>
      )}
      {material.reason && (
        <div className="capture-reason">
          <Bookmark size={16} />
          {material.reason}
        </div>
      )}
      {!pinned && cloud && (
        <section className="material-policy">
          <strong>
            云端处理策略 · {allowed ? "当前正文已授权" : "仅本地处理"}
          </strong>
          <p className="reading-note">
            服务：{cloud.endpoint_host} · 模型：{cloud.model}
            。发送范围是此素材的标题、正文及版本/片段引用，不包含保存理由或本机配置。授权不会自动处理；修改正文后回到仅本地。已发出的内容无法通过取消撤回。
          </p>
          <Button
            disabled={busy}
            onClick={() => {
              setCloudConsent(false);
              onPolicy(allowed ? "local_only" : "cloud_allowed");
            }}
          >
            {allowed ? "撤回云端授权" : "允许当前正文使用此服务"}
          </Button>
          {allowed && (
            <label className="cloud-consent">
              <input
                type="checkbox"
                checked={cloudConsent}
                onChange={(e) => setCloudConsent(e.target.checked)}
              />
              我确认将此版本的标题、正文及版本/片段引用发给上述服务，可能消耗
              API 额度。
            </label>
          )}
          {allowed && (
            <Button
              disabled={
                busy || !cloudConsent || material.parse_state !== "ready"
              }
              icon={Sparkles}
              onClick={() => onDigest("openai_compatible", true)}
            >
              使用真实模型消化
            </Button>
          )}
        </section>
      )}
      <div className="detail-tabs">
        <button
          className={tab === "digest" ? "active" : ""}
          onClick={() => setTab("digest")}
        >
          归纳与摘录
        </button>
        <button
          className={tab === "original" ? "active" : ""}
          onClick={() => setTab("original")}
        >
          原始正文
        </button>
      </div>
      {editing ? (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const saved = await onUpdate(body);
            if (saved) setEditing(false);
          }}
        >
          <label>
            补充正文，保存为新的素材版本
            <textarea
              aria-label="补充素材正文"
              rows={10}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              required
            />
          </label>
          <div className="modal-actions">
            <Button type="button" onClick={() => setEditing(false)}>
              取消
            </Button>
            <Button
              disabled={busy || !body.trim()}
              className="primary"
              type="submit"
            >
              保存新版本
            </Button>
          </div>
        </form>
      ) : tab === "original" ? (
        <Markdown>
          {material.content || "仅归档链接/文件，尚无可解析正文。"}
        </Markdown>
      ) : (
        <>
          <div className="reading-mode">
            <Sparkles size={16} />
            <span>基于原文的提取式整理，保留原始行号。</span>
          </div>
          {material.digest.excerpts.map((quote, i) => (
            <div className="excerpt" key={i}>
              <blockquote>{quote.text}</blockquote>
              <button className="citation" onClick={() => setTab("original")}>
                <Link2 size={13} />
                原文第 {quote.line} 行
              </button>
            </div>
          ))}
          {!material.digest.excerpts.length && (
            <p className="reading-note">
              正文不足以提取重点。你仍可以保留原件或在收集时粘贴正文。
            </p>
          )}
          <div className="question-box">
            <h3>
              <Lightbulb size={17} />
              可以继续追问
            </h3>
            {material.digest.questions.map((q) => (
              <p key={q}>{q}</p>
            ))}
          </div>
        </>
      )}
      {material.url && (
        <a
          className="source-link"
          href={material.url}
          target="_blank"
          rel="noreferrer"
        >
          <ExternalLink size={15} />
          打开原始链接
        </a>
      )}
      <div className="modal-actions">
        <Button
          disabled={busy || material.parse_state !== "ready"}
          icon={Sparkles}
          onClick={() => onDigest()}
        >
          证据化消化（本地 mock）
        </Button>
        {!pinned && (
          <Button
            disabled={busy}
            icon={PencilLine}
            onClick={() => {
              setBody(material.content);
              setEditing(true);
            }}
          >
            补充正文
          </Button>
        )}
        <Button
          disabled={busy}
          icon={Check}
          onClick={() => onFeedback("useful")}
        >
          有价值
        </Button>
        <Button
          disabled={busy}
          icon={Clock3}
          onClick={() => onFeedback("later")}
        >
          稍后读
        </Button>
        <a
          className="button"
          href={`/api/v1/materials/${material.id}/original?revision=${material.revision}`}
        >
          <ArrowDownToLine size={16} />
          导出
        </a>
        <Button
          className="primary"
          disabled={busy || material.parse_state !== "ready"}
          icon={NotebookPen}
          onClick={onWrite}
        >
          整理成博客
        </Button>
      </div>
    </Modal>
  );
}
function Sources({
  state,
  busy,
  onAdd,
}: {
  state: State;
  busy: boolean;
  onAdd: (data: unknown) => void;
}) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [kind, setKind] = useState("website");
  return (
    <>
      <PageHeading
        eyebrow="SOURCES · STAY CURIOUS"
        title="关注值得长期关注的东西。"
        subtitle="保存作者、博客与项目。当前版本以手动收集为主。"
        action={
          <Button className="primary" icon={Plus} onClick={() => setOpen(true)}>
            添加关注
          </Button>
        }
      />
      <div className="source-notice">
        <CircleHelp size={18} />
        <span>
          自动轮询与外部授权尚未接入。这里保存关注清单，不会在后台抓取内容。
        </span>
      </div>
      <div className="source-grid">
        {state.sources.map((source) => (
          <section className="panel source-card" key={source.id}>
            {source.kind === "github" ? (
              <Github size={26} />
            ) : (
              <Rss size={26} />
            )}
            <h2>{source.title}</h2>
            <p>
              {source.kind === "rss"
                ? "RSS / Atom"
                : source.kind === "github"
                  ? "GitHub 项目"
                  : "网站 / 作者"}
            </p>
            <span className="badge gray">手动关注</span>
            <a
              href={source.url}
              target="_blank"
              rel="noreferrer"
              className="text-button"
            >
              打开来源
              <ExternalLink size={15} />
            </a>
          </section>
        ))}
      </div>
      {!state.sources.length && (
        <Empty
          icon={Rss}
          title="建立你的关注清单"
          text="从一个博客、一位作者或一个开源项目开始。"
        />
      )}
      {open && (
        <Modal title="添加关注来源" onClose={() => setOpen(false)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              onAdd({ title, url, kind });
              setOpen(false);
            }}
          >
            <label>
              名称
              <input
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="作者、博客或项目名称"
              />
            </label>
            <label>
              链接
              <input
                type="url"
                required
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://…"
              />
            </label>
            <label>
              类型
              <select value={kind} onChange={(e) => setKind(e.target.value)}>
                <option value="website">网站 / 作者</option>
                <option value="rss">RSS / Atom</option>
                <option value="github">GitHub 项目</option>
              </select>
            </label>
            <div className="modal-actions">
              <Button disabled={busy} type="submit" className="primary">
                保存关注
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
function Settings({
  state,
  busy,
  onSave,
  onDemo,
  onRestore,
}: {
  state: State;
  busy: boolean;
  onSave: (data: unknown) => void;
  onDemo: () => void;
  onRestore: (file: File) => void;
}) {
  const [name, setName] = useState(state.settings.display_name);
  const [time, setTime] = useState(state.settings.report_time);
  const [restoreFile, setRestoreFile] = useState<File | null>(null);
  const [integrity, setIntegrity] = useState("");
  const empty =
    !state.settings.id &&
    ![
      state.materials,
      state.reports,
      state.blogs,
      state.entries,
      state.sources,
      state.proposals,
      state.jobs,
      state.digests,
    ].some((items) => items.length);
  return (
    <>
      <PageHeading
        eyebrow="SETTINGS · YOUR OWN RHYTHM"
        title="按自己的节奏，持续积累。"
        subtitle="你决定怎样收集、何时整理，以及什么值得留下。"
      />
      <div className="settings-layout">
        <form
          className="panel settings-panel"
          onSubmit={(e) => {
            e.preventDefault();
            onSave({ display_name: name, report_time: time });
          }}
        >
          <div className="section-heading">
            <h2>工作空间</h2>
          </div>
          <label>
            工作空间名称
            <input
              required
              maxLength={80}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label>
            习惯整理的时间
            <input
              type="time"
              required
              value={time}
              onChange={(e) => setTime(e.target.value)}
            />
          </label>
          <p className="muted">
            时间仅保存为偏好。本版需手动生成 Report，尚未启用定时任务。
          </p>
          <label>
            时区
            <input value="Asia/Shanghai" readOnly />
          </label>
          <Button className="primary" icon={Check} disabled={busy}>
            保存偏好
          </Button>
        </form>
        <div>
          <section className="panel settings-panel">
            <div className="section-heading">
              <h2>处理方式与数据</h2>
            </div>
            <div className="setting-info">
              <span>归纳方式</span>
              <strong>
                {state.processing.external_calls_enabled
                  ? "可选真实模型 / 本地 mock"
                  : "提取式 + 本地 mock 证据消化"}
              </strong>
            </div>
            <div className="setting-info">
              <span>模型外发</span>
              <strong>
                {state.processing.external_calls_enabled
                  ? "按素材授权，逐次确认"
                  : "未启用"}
              </strong>
            </div>
            <div className="setting-info">
              <span>数据保存</span>
              <strong>本机 PostgreSQL + 原件文件</strong>
            </div>
            {state.processing.profiles
              .filter((p) => p.provider === "openai_compatible")
              .map((p) => (
                <p className="reading-note" key={p.profile_id}>
                  已配置 {p.model} · {p.endpoint_host}；总超时 {p.timeout}
                  s，输出上限 {p.max_tokens} tokens。只读既有 LLM_
                  配置，密钥不显示、不进入备份。
                </p>
              ))}
            <div className="setting-info">
              <span>访问范围</span>
              <strong>本机浏览器 / CLI</strong>
            </div>
            <p className="reading-note">
              关闭页面后资料仍然保留，已提交任务继续由 Server 处理。可选本地
              mock 或已配置
              API；现有素材默认仅本地，必须授权并确认才会外发。自动订阅和团队登录尚未接入。
            </p>
          </section>
          <section className="panel settings-panel">
            <div className="section-heading">
              <h2>备份与恢复</h2>
            </div>
            <p className="reading-note">
              备份包含全部对象、修订、来源关系、原件和 SHA-256
              清单，不包含数据库密码或本机未保存草稿。请另行下载草稿。
            </p>
            <a className="button primary" href="/api/v1/workspace/backup">
              <ArrowDownToLine size={16} />
              下载完整备份
            </a>
            <Button
              onClick={async () => {
                try {
                  const result = await api<{
                    ok: boolean;
                    referenced_blobs: number;
                    missing: string[];
                    corrupt: string[];
                    orphan_count: number;
                  }>("/workspace/integrity");
                  setIntegrity(
                    `${result.ok ? "原件校验通过" : "原件存在异常"} · ${result.referenced_blobs} 份引用 · 缺失 ${result.missing.length} · 损坏 ${result.corrupt.length} · 未引用 ${result.orphan_count}（不会自动删除）`,
                  );
                } catch (e) {
                  setIntegrity(e instanceof Error ? e.message : "校验失败");
                }
              }}
            >
              检查原件完整性
            </Button>
            {integrity && (
              <p role="status" className="reading-note">
                {integrity}
              </p>
            )}
            <p className="reading-note">
              仅允许恢复到全新的空工作空间，不会覆盖当前数据。上传上限
              128MiB，展开上限 256MiB；过大的工作空间请使用数据库级备份。
            </p>
            <label>
              选择备份包
              <input
                aria-label="选择备份包"
                type="file"
                accept=".zip"
                disabled={!empty || busy}
                onChange={(e) => setRestoreFile(e.target.files?.[0] || null)}
              />
            </label>
            <Button
              disabled={!empty || busy || !restoreFile}
              onClick={() => {
                if (restoreFile) onRestore(restoreFile);
              }}
            >
              恢复到空工作空间
            </Button>
            {!empty && (
              <small className="muted">当前工作空间非空，已禁用恢复。</small>
            )}
          </section>
          <section className="panel settings-panel">
            <div className="section-heading">
              <h2>体验这条知识路径</h2>
            </div>
            <p className="reading-note">
              添加一组明确标记的示例，体验素材、Report、博客和图书馆。
            </p>
            <Button icon={Lightbulb} disabled={busy} onClick={onDemo}>
              添加体验资料
            </Button>
          </section>
        </div>
      </div>
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
