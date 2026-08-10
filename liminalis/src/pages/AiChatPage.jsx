import { ExternalLink, MessageSquareText, Server, ShieldCheck } from 'lucide-react';
import { Header } from '../components/Header';
import { SectionLabel } from '../components/SectionLabel';
import { SiteFooter } from '../components/SiteFooter';

const llmWikiUrl = import.meta.env.VITE_LLM_WIKI_URL || '/llm-wiki/';

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
            这里以 Liminalis 作为统一入口，嵌入当前项目内的 llm-wiki Context Social 控制台。记忆、人物、照片线索与聊天保持在本地 Go 服务中运行，前端把它纳入 Praxis 的工作流。
          </p>
        </div>

        <aside className="ai-chat-notes" aria-label="AI + Chat integration notes">
          <div>
            <Server size={18} />
            <span>Bundled runtime</span>
          </div>
          <p>llm-wiki 已迁入当前项目目录，并通过 Liminalis 的同源入口挂载，保留独立构建和排障能力。</p>
          <div>
            <ShieldCheck size={18} />
            <span>Local-first boundary</span>
          </div>
          <p>认证、Cookie 和 API 请求经由同一个 Liminalis origin 转发，减少浏览器侧端口和跨域边界。</p>
        </aside>
      </section>

      <section className="ai-chat-shell" aria-label="llm-wiki embedded console">
        <div className="ai-chat-frame-head">
          <div>
            <MessageSquareText size={20} />
            <div>
              <h2>llm-wiki · Context Social</h2>
              <p>
                如未加载，请使用 <code>npm run start:one-port</code> 启动统一入口。
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
