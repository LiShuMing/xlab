export const navItems = [
  {
    label: 'Logos · 理解世界',
    href: '/logos',
    tone: 'blue',
    children: [
      { label: '代码实验室', href: '/logos', description: 'Markdown 开源书籍阅读仓库' },
      { label: '产品报告', href: '/reports', description: '数据库产品调研与深度报告' },
      { label: '博客', href: '/blogs', description: '技术随笔与阅读札记' },
      { label: '数据库动态', href: '/radar', description: '数据库领域动态' },
    ],
  },
  {
    label: 'Praxis · 改变世界',
    href: '/#praxis',
    tone: 'violet',
    children: [
      { label: '价值投资', href: '/invest', description: 'LLM 驱动的长期价值分析报告' },
      { label: '自我对话', href: '/ego', description: '记录、陪伴与长期记忆' },
      { label: 'AI + Chat', href: '/ai-chat', description: '个人上下文、AI 记忆与关系推荐' },
    ],
  },
  { label: '了解我们', href: '/about', cta: true },
];

export function isPlainLeftClick(event) {
  return event.button === 0 && !event.metaKey && !event.altKey && !event.ctrlKey && !event.shiftKey;
}

export function shouldHandleInternalLink(anchor, event) {
  if (!anchor || !isPlainLeftClick(event)) return false;
  if (anchor.target && anchor.target !== '_self') return false;
  if (anchor.hasAttribute('download')) return false;

  const url = new URL(anchor.href, window.location.href);
  if (url.origin !== window.location.origin) return false;
  return (
    url.pathname !== window.location.pathname ||
    url.search !== window.location.search ||
    url.hash !== window.location.hash
  );
}
