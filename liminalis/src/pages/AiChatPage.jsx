import { ExternalLink, MessageSquareText, Server, ShieldCheck } from 'lucide-react';
import { Header } from '../components/Header';
import { SectionLabel } from '../components/SectionLabel';
import { SiteFooter } from '../components/SiteFooter';

const llmWikiUrl = import.meta.env.VITE_LLM_WIKI_URL || 'http://127.0.0.1:8787/';
const llmWikiRoot = '../projects/llm-wiki';

export function AiChatPage() {
  return (
    <main className="ai-chat-page">
      <Header />

      <section className="ai-chat-hero">
        <div className="ai-chat-copy">
          <SectionLabel>Praxis · AI + Chat</SectionLabel>
          <h1>
            把上下文，
            <span>
              变成可持续的
              <br />
              对话
            </span>
          </h1>
          <p>
            这里以 Liminalis 作为统一入口，嵌入 llm-wiki 的 Context Social 控制台。记忆、人物、照片线索与聊天保持在原服务中运行，前端只负责把它纳入 Praxis 的工作流。
          </p>
        </div>

        <aside className="ai-chat-notes" aria-label="AI + Chat integration notes">
          <div>
            <Server size={18} />
            <span>Independent runtime</span>
          </div>
          <p>llm-wiki 继续使用自己的 Go Web 服务和后端存储，避免把 Liminalis 重新变成多套业务逻辑的混合体。</p>
          <div>
            <ShieldCheck size={18} />
            <span>Local-first boundary</span>
          </div>
          <p>认证、Cookie 和 API 请求都留在 llm-wiki 域内，便于独立演进和排障。</p>
        </aside>
      </section>

      <section className="ai-chat-shell" aria-label="llm-wiki embedded console">
        <div className="ai-chat-frame-head">
          <div>
            <MessageSquareText size={20} />
            <div>
              <h2>llm-wiki · Context Social</h2>
              <p>
                如未加载，请先在 <code>{llmWikiRoot}</code> 执行 <code>make web</code>，或通过{' '}
                <code>VITE_LLM_WIKI_URL</code> 指向其他部署地址。
              </p>
            </div>
          </div>
          <a href={llmWikiUrl} target="_blank" rel="noreferrer">
            <ExternalLink size={16} />
            独立打开
          </a>
        </div>

        <div className="ai-chat-frame-wrap">
          <iframe title="llm-wiki Context Social" src={llmWikiUrl} loading="lazy" />
        </div>
      </section>

      <SiteFooter />
    </main>
  );
}
