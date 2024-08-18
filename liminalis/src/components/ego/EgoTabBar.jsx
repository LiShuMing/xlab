import { NavLink, useLocation } from 'react-router-dom';

const tabs = [
  { label: 'Record', labelZh: '记录', path: '/ego/record', icon: '◈' },
  { label: 'Chat', labelZh: '对话', path: '/ego/chat', icon: '◇' },
  { label: 'Timeline', labelZh: '时间', path: '/ego/timeline', icon: '◉' },
  { label: 'Me', labelZh: '我', path: '/ego/me', icon: '○' },
];

export function EgoTabBar() {
  const location = useLocation();
  const isLoginPage = location.pathname === '/ego/login';

  if (isLoginPage) return null;

  return (
    <nav className="ego2-tab-bar">
      {tabs.map((tab) => (
        <NavLink
          key={tab.path}
          to={tab.path}
          end={tab.path === '/ego/record'}
          className={({ isActive }) =>
            `ego2-tab${isActive ? ' ego2-tab--active' : ''}`
          }
        >
          <span className="ego2-tab-icon">{tab.icon}</span>
          <span className="ego2-tab-label">{tab.labelZh}</span>
        </NavLink>
      ))}
    </nav>
  );
}
