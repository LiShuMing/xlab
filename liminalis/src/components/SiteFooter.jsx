import { Logo } from './Logo';

export function SiteFooter() {
  return (
    <footer>
      <Logo small />
      <div className="footer-links">
        <a href="/logos">Logos 理解世界</a>
        <a href="/#praxis">Praxis 改变世界</a>
        <a href="/about">关于我们</a>
        <a href="mailto:ming.moriarty@gmail.com">联系</a>
      </div>
      <p>© 2026 Liminalis. 为自驱者而建。</p>
    </footer>
  );
}
