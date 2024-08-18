import {
  ArrowRight,
  BookOpenText,
  FlaskConical,
  HeartHandshake,
  LineChart,
  MessageSquareText,
} from 'lucide-react';
import { AboutContent } from '../components/AboutContent';
import { Header } from '../components/Header';
import { SectionLabel } from '../components/SectionLabel';
import { SiteFooter } from '../components/SiteFooter';

export function HomePage({ tags, pillars, stats }) {
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
        <div className="praxis-heading">
          <div>
            <SectionLabel>Praxis · 改变世界</SectionLabel>
            <h2>
              把洞察，
              <span className="gradient-text">变成行动工具</span>
            </h2>
          </div>
          <p>Praxis 承载那些从理解走向实践的产品：分析、判断、表达与创造。这里聚合价值投资、自我对话与 AI 上下文工具。</p>
        </div>
        <div className="praxis-products">
          <a href="/invest" className="praxis-product-card">
            <div>
              <LineChart size={24} />
              <span>价值投资</span>
            </div>
            <h3>基于 LLM 的企业长期价值分析报告</h3>
            <p>输入股票名称或代码，生成涵盖商业模式、护城河、估值、安全边际和风险的 Markdown 报告。</p>
            <small>
              进入分析页
              <ArrowRight size={14} />
            </small>
          </a>
          <a href="/ego" className="praxis-product-card">
            <div>
              <HeartHandshake size={24} />
              <span>自我对话</span>
            </div>
            <h3>基于记录、角色与长期记忆的自我实践空间</h3>
            <p>把每日片段沉淀下来，与不同 AI 角色对话，让理解自己成为一种可以持续练习的能力。</p>
            <small>
              进入 Ego
              <ArrowRight size={14} />
            </small>
          </a>
          <a href="/ai-chat" className="praxis-product-card">
            <div>
              <MessageSquareText size={24} />
              <span>AI + Chat</span>
            </div>
            <h3>集成 llm-wiki 的个人上下文与 AI 会话控制台</h3>
            <p>把记忆、人物关系、照片线索与聊天入口放到同一个工作台，作为长期个人 AI 系统的实验入口。</p>
            <small>
              进入 AI + Chat
              <ArrowRight size={14} />
            </small>
          </a>
        </div>
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
