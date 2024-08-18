import { ChevronRight, Menu, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { navItems } from '../lib/routes';
import { Logo } from './Logo';

export function Header() {
  const [open, setOpen] = useState(false);
  const [activeMenu, setActiveMenu] = useState(null);
  const headerRef = useRef(null);

  useEffect(() => {
    const closeMenu = (event) => {
      if (!headerRef.current?.contains(event.target)) {
        setActiveMenu(null);
      }
    };
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') {
        setActiveMenu(null);
      }
    };

    document.addEventListener('pointerdown', closeMenu);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeMenu);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, []);

  return (
    <header className="site-header" ref={headerRef}>
      <nav className="nav-shell">
        <Logo />
        <div className="nav-links">
          {navItems.map((item) => {
            if (item.children) {
              const expanded = activeMenu === item.label;
              return (
                <div key={item.label} className="nav-menu">
                  <button
                    type="button"
                    className="nav-link"
                    aria-expanded={expanded}
                    aria-haspopup="menu"
                    onClick={() => setActiveMenu((value) => (value === item.label ? null : item.label))}
                  >
                    <span className={`nav-dot ${item.tone}`} />
                    {item.label}
                    <ChevronRight size={13} className={expanded ? 'nav-arrow open' : 'nav-arrow'} />
                  </button>
                  {expanded && (
                    <div className="nav-dropdown" role="menu">
                      {item.children.map((child) => (
                        <a key={child.label} href={child.href} role="menuitem" onClick={() => setActiveMenu(null)}>
                          <strong>{child.label}</strong>
                          <span>{child.description}</span>
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              );
            }

            return (
              <a key={item.label} href={item.href} className={item.cta ? 'nav-cta' : 'nav-link'}>
                {!item.cta && <span className={`nav-dot ${item.tone}`} />}
                {item.label}
              </a>
            );
          })}
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
          {navItems.map((item) => {
            const expanded = activeMenu === item.label;
            if (item.children) {
              return (
                <div key={item.label} className="mobile-nav-group">
                  <button
                    type="button"
                    className="mobile-nav-parent"
                    aria-expanded={expanded}
                    onClick={() => setActiveMenu((value) => (value === item.label ? null : item.label))}
                  >
                    {item.label}
                    <ChevronRight size={14} className={expanded ? 'nav-arrow open' : 'nav-arrow'} />
                  </button>
                  {expanded &&
                    item.children.map((child) => (
                      <a
                        key={child.label}
                        href={child.href}
                        className="mobile-sub-link"
                        onClick={() => {
                          setOpen(false);
                          setActiveMenu(null);
                        }}
                      >
                        {child.label}
                      </a>
                    ))}
                </div>
              );
            }

            return (
              <div key={item.label} className="mobile-nav-group">
                <a
                  href={item.href}
                  onClick={() => {
                    setOpen(false);
                    setActiveMenu(null);
                  }}
                >
                  {item.label}
                </a>
              </div>
            );
          })}
        </div>
      )}
    </header>
  );
}
