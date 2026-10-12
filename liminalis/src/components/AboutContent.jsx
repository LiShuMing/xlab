import { ArrowRight } from 'lucide-react';
import { SectionLabel } from './SectionLabel';

const manifestoNotes = [
  {
    label: 'Culture',
    title: '慢下来，深下去',
    text: '我们珍视长期主义、开放笔记和可复用的知识结构。好的文化不是口号，而是一种允许人持续学习、诚实表达、互相启发的环境。',
  },
  {
    label: 'Value',
    title: '把知识变成行动',
    text: '价值不止来自答案，也来自提问、判断和创造。Logos 是理解世界，Praxis 是改变世界；Liminalis 鼓励把洞察转化为真实作品和长期行动。',
  },
  {
    label: 'Self',
    title: '看见更大的自己',
    text: '技术、认知、情绪和表达并不是彼此孤立的能力。我们相信自我成长发生在这些维度的交汇处，也发生在每一次认真面对内心的时候。',
  },
];

const growthDimensions = [
  {
    title: '技术',
    text: '理解系统如何工作，从源码、架构和工程经验中建立稳定的判断力。',
  },
  {
    title: '认知',
    text: '把信息整理成结构，把观点放回上下文，让复杂问题变得可以被反复思考。',
  },
  {
    title: '情绪',
    text: '承认人的脆弱、焦虑与迟疑，在长期成长中保留温度和自我照顾的能力。',
  },
  {
    title: '表达',
    text: '用写作、对话和创造把内在经验变成可分享、可连接、可沉淀的东西。',
  },
];

export function AboutContent({ compact = false }) {
  return (
    <section id="manifesto" className={compact ? 'manifesto manifesto-preview' : 'manifesto about-manifesto'}>
      <div className="manifesto-inner">
        <SectionLabel>了解我们 · About Liminalis</SectionLabel>
        <h2 className="manifesto-quote">
          Liminalis is a space for
          <br />
          <span className="gradient-text">knowledge, self-discovery,</span>
          <br />
          and meaningful growth.
        </h2>
        <p className="manifesto-body manifesto-lead">
          Liminalis 是一个面向知识、探索与自我成长的空间。
          <br />
          我们帮助个体在技术、认知、情绪和表达中持续成长，发现更大的自我价值。
          <br />
          Logos 是理解世界，Praxis 是改变世界。
        </p>

        {!compact && (
          <>
            <h3 className="manifesto-subquote">
              我们活在一个<span className="gradient-text">信息过剩</span>、
              <br />
              <span className="gradient-text">意义匮乏</span>的时代。
            </h3>
            <p className="manifesto-body">
              工程师需要的不只是文档，而是能够激发思考的视角；
              <br />
              每个人需要的不只是答案，而是理解问题的勇气。
              <br />
              <br />
              Liminalis 不做流量的搬运工。
              <br />
              我们是一群相信「慢即是快」的建造者，
              <br />
              致力于打造一个让你愿意停下来、真正思考的空间。
            </p>
            <div className="name-pair">
              <article>
                <p>Logos</p>
                <h4>理解世界</h4>
                <span>知识、语言、理性与结构。它帮助我们读懂技术系统，也帮助我们整理经验、建立判断。</span>
              </article>
              <article>
                <p>Praxis</p>
                <h4>改变世界</h4>
                <span>实践、行动、表达与创造。它让理解不止停留在脑中，而是先改变自己，再进入生活、关系和真实作品。</span>
              </article>
            </div>
          </>
        )}

        <div className="manifesto-grid">
          {manifestoNotes.map((note) => (
            <article key={note.label} className="manifesto-card">
              <p>{note.label}</p>
              <h4>{note.title}</h4>
              <span>{note.text}</span>
            </article>
          ))}
        </div>

        {!compact && (
          <div className="growth-panel">
            <div>
              <SectionLabel>成长维度</SectionLabel>
              <h3>技术、认知、情绪和表达，应该共同长大。</h3>
            </div>
            <div className="growth-grid">
              {growthDimensions.map((item) => (
                <article key={item.title}>
                  <h4>{item.title}</h4>
                  <p>{item.text}</p>
                </article>
              ))}
            </div>
          </div>
        )}

        {!compact && (
          <div className="growth-panel">
            <div>
              <SectionLabel>关于我们 · Company</SectionLabel>
              <h3>杭州普昇商贸有限公司</h3>
            </div>
            <div className="manifesto-body" style={{ marginTop: '1rem' }}>
              <p>
                Liminalis 是杭州普昇商贸有限公司旗下的知识品牌。
                <br />
                普昇商贸是一家综合贸易企业，业务涵盖多品类的商品贸易与供应链服务，
                致力于为客户提供高效、可靠的贸易解决方案。
              </p>
              <p>
                公司秉承「务实、开放、长期主义」的经营理念，
                在商业实践中追求品质与效率的平衡，
                同时通过 Liminalis 等品牌探索知识传播与个人成长的新可能。
              </p>
            </div>
            <div className="growth-grid">
              <article>
                <h4>主营业务</h4>
                <p>多品类综合贸易，覆盖商品采购、渠道拓展与供应链管理服务。</p>
              </article>
              <article>
                <h4>核心价值</h4>
                <p>务实诚信、品质优先、长期合作，与客户和伙伴共同成长。</p>
              </article>
              <article>
                <h4>品牌延伸</h4>
                <p>通过 Liminalis 等知识品牌，将商业经验转化为可分享的知识与洞察。</p>
              </article>
            </div>
          </div>
        )}

        {compact && (
          <a href="/about" className="manifesto-link">
            阅读完整介绍 <ArrowRight size={15} />
          </a>
        )}
      </div>
    </section>
  );
}
