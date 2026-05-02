import { ArrowRight, BookOpenText, Brain, Compass, FlaskConical, Menu, Sparkles, X, Zap } from 'lucide-react';
import { useState } from 'react';

const navItems = [
  { label: 'Codex · 知识图谱', href: '#codex', tone: 'blue' },
  { label: 'Inner Lab · 内在实验室', href: '#innerlab', tone: 'violet' },
  { label: '了解我们', href: '#manifesto', cta: true },
];

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

function Logo({ small = false }) {
  return (
    <a href="#home" className={small ? 'logo logo-small' : 'logo'}>
      <span className="logo-mark">L</span>
      <span>Luminal</span>
    </a>
  );
}

function Header() {
  const [open, setOpen] = useState(false);

  return (
    <header className="site-header">
      <nav className="nav-shell">
        <Logo />
        <div className="nav-links">
          {navItems.map((item) => (
            <a key={item.label} href={item.href} className={item.cta ? 'nav-cta' : 'nav-link'}>
              {!item.cta && <span className={`nav-dot ${item.tone}`} />}
              {item.label}
            </a>
          ))}
        </div>
        <button
          type="button"
          className="mobile-menu"
          onClick={() => setOpen((value) => !value)}
          aria-label="Toggle navigation"
        >
          {open ? <X size={18} /> : <Menu size={18} />}
        </button>
      </nav>
      {open && (
        <div className="mobile-panel">
          {navItems.map((item) => (
            <a key={item.label} href={item.href} onClick={() => setOpen(false)}>
              {item.label}
            </a>
          ))}
        </div>
      )}
    </header>
  );
}

function SectionLabel({ children }) {
  return <p className="section-label">{children}</p>;
}

function App() {
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
          Luminal 是一个为自驱者而建的平台：
          <br />
          技术的深度，与人性的温度，在这里并行生长。
        </p>
        <div className="hero-actions reveal delay-3">
          <a href="#codex" className="btn-primary">
            开始探索
          </a>
          <a href="#manifesto" className="btn-ghost">
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

      <section id="codex" className="section">
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

      <section id="manifesto" className="manifesto">
        <div className="manifesto-inner">
          <SectionLabel>我们的信念</SectionLabel>
          <h2 className="manifesto-quote">
            我们活在一个<span className="gradient-text">信息过剩</span>、
            <br />
            <span className="gradient-text">意义匮乏</span>的时代。
          </h2>
          <p className="manifesto-body">
            工程师需要的不只是文档，而是能够激发思考的视角；
            <br />
            每个人需要的不只是答案，而是理解问题的勇气。
            <br />
            <br />
            Luminal 不做流量的搬运工。
            <br />
            我们是一群相信「慢即是快」的建造者，
            <br />
            致力于打造一个让你愿意停下来、真正思考的空间。
          </p>
        </div>
      </section>

      <div className="divider" />

      <section id="innerlab" className="section section-compact">
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
            <a href="#codex" className="btn-primary">
              <BookOpenText size={16} />
              进入知识图谱
            </a>
            <a href="#innerlab" className="btn-ghost">
              <FlaskConical size={16} />
              探索内在实验室
            </a>
          </div>
        </div>
      </section>

      <footer>
        <Logo small />
        <div className="footer-links">
          <a href="#codex">Codex 知识图谱</a>
          <a href="#innerlab">Inner Lab 内在实验室</a>
          <a href="#manifesto">关于我们</a>
          <a href="mailto:ming.moriarty@gmail.com">联系</a>
        </div>
        <p>© 2026 Luminal. 为自驱者而建。</p>
      </footer>
    </main>
  );
}

export default App;
