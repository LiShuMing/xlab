import { LineChart, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { Header } from '../components/Header';
import { InvestWorkspacePanel } from '../components/invest/InvestWorkspacePanel';
import { MarkdownReader } from '../components/MarkdownReader';
import { SectionLabel } from '../components/SectionLabel';
import { SiteFooter } from '../components/SiteFooter';
import { fetchJson } from '../lib/api';

export function InvestPage() {
  const [stock, setStock] = useState('');
  const [query, setQuery] = useState('请从长期价值投资角度，分析商业模式、护城河、财务质量、估值安全边际、主要风险与合理买入区间。');
  const [analysisMode, setAnalysisMode] = useState('fast');
  const [report, setReport] = useState(null);
  const [workspace, setWorkspace] = useState(null);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [savingThesis, setSavingThesis] = useState(false);
  const [workspaceBusy, setWorkspaceBusy] = useState(false);

  const normalizeWorkspace = (data) => ({
    thesis: data.thesis ?? null,
    watch_items: data.watch_items ?? [],
    journal_entries: data.journal_entries ?? [],
    reviews: data.reviews ?? [],
  });

  const loadWorkspace = async (stockCode) => {
    if (!stockCode) return;
    const data = await fetchJson(`/api/invest/workspace/${encodeURIComponent(stockCode)}`);
    setWorkspace(normalizeWorkspace(data));
  };

  const submitAnalysis = async (event) => {
    event.preventDefault();
    if (!stock.trim()) return;

    setStatus('loading');
    setError('');
    setReport(null);
    setWorkspace(null);

    try {
      const data = await fetchJson('/api/invest/analyze-stock', {
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
      setWorkspace(normalizeWorkspace(data));
      setStatus('done');
    } catch (err) {
      setError(err.message);
      setStatus('error');
    }
  };

  const saveThesis = async (draft) => {
    if (!draft?.stock_code) return;
    setSavingThesis(true);
    setError('');
    try {
      const data = await fetchJson(`/api/invest/thesis/${encodeURIComponent(draft.stock_code)}`, {
        method: 'PUT',
        body: JSON.stringify(draft),
      });
      setWorkspace((current) => ({ ...(current ?? {}), thesis: data.thesis }));
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingThesis(false);
    }
  };

  const createWatchItem = async (payload) => {
    const stockCode = workspace?.thesis?.stock_code;
    if (!stockCode) return;
    setWorkspaceBusy(true);
    setError('');
    try {
      await fetchJson(`/api/invest/watch-items/${encodeURIComponent(stockCode)}`, {
        method: 'POST',
        body: JSON.stringify({ ...payload, thesis_id: workspace.thesis.id }),
      });
      await loadWorkspace(stockCode);
    } catch (err) {
      setError(err.message);
    } finally {
      setWorkspaceBusy(false);
    }
  };

  const updateWatchStatus = async (itemId, nextStatus) => {
    const stockCode = workspace?.thesis?.stock_code;
    if (!stockCode) return;
    setWorkspaceBusy(true);
    setError('');
    try {
      await fetchJson(`/api/invest/watch-items/${itemId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: nextStatus }),
      });
      await loadWorkspace(stockCode);
    } catch (err) {
      setError(err.message);
    } finally {
      setWorkspaceBusy(false);
    }
  };

  const createJournalEntry = async (payload) => {
    const stockCode = workspace?.thesis?.stock_code;
    if (!stockCode) return;
    setWorkspaceBusy(true);
    setError('');
    try {
      await fetchJson(`/api/invest/journal/${encodeURIComponent(stockCode)}`, {
        method: 'POST',
        body: JSON.stringify({ ...payload, thesis_id: workspace.thesis.id }),
      });
      await loadWorkspace(stockCode);
    } catch (err) {
      setError(err.message);
    } finally {
      setWorkspaceBusy(false);
    }
  };

  const createReview = async (payload) => {
    const stockCode = workspace?.thesis?.stock_code;
    if (!stockCode) return;
    setWorkspaceBusy(true);
    setError('');
    try {
      await fetchJson(`/api/invest/reviews/${encodeURIComponent(stockCode)}`, {
        method: 'POST',
        body: JSON.stringify({ ...payload, thesis_id: workspace.thesis.id }),
      });
      await loadWorkspace(stockCode);
    } catch (err) {
      setError(err.message);
    } finally {
      setWorkspaceBusy(false);
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
            使用 Liminalis 内置的数据采集与多 Agent 分析管线，围绕一家企业生成长期价值投资报告。它关注商业模式、财务质量、估值、安全边际与风险，而不是短期交易噪音。
          </p>
        </div>
        <aside className="invest-method">
          <span>Value Lens</span>
          <p>Data collection → specialist agents → synthesis report</p>
          <small>powered by Liminalis Invest</small>
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
              <p>LLM 分析通常需要几十秒，请保持统一后端运行。</p>
            </div>
          )}

          {report?.markdown && (
            <>
              <InvestWorkspacePanel
                stockCode={report.stock}
                workspace={workspace}
                onSaveThesis={saveThesis}
                saving={savingThesis}
                busy={workspaceBusy}
                onCreateWatchItem={createWatchItem}
                onUpdateWatchStatus={updateWatchStatus}
                onCreateJournalEntry={createJournalEntry}
                onCreateReview={createReview}
              />
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
            </>
          )}
        </div>
      </section>
      <SiteFooter />
    </main>
  );
}
