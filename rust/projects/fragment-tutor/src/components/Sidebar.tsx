import { useStore } from '../store';

const navItems = [
  { id: 'library', label: '知识库', icon: '📚', shortcut: '⌘1' },
  { id: 'today', label: '今日任务', icon: '📅', shortcut: '⌘2' },
  { id: 'review', label: '复习队列', icon: '🧠', shortcut: '⌘3' },
  { id: 'reflection', label: '反省记录', icon: '🤔', shortcut: '⌘4' },
  { id: 'settings', label: '设置', icon: '⚙️', shortcut: '⌘,' },
];

export default function Sidebar() {
  const { currentView, setCurrentView } = useStore();

  return (
    <aside className="w-56 bg-white border-r border-gray-200 p-4 flex flex-col">
      <nav className="space-y-1 flex-1">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setCurrentView(item.id as any)}
            className={currentView === item.id ? 'sidebar-item-active' : 'sidebar-item'}
            style={{ width: '100%' }}
          >
            <span className="text-lg">{item.icon}</span>
            <span className="flex-1 text-left">{item.label}</span>
            <span className="text-xs text-gray-400">{item.shortcut}</span>
          </button>
        ))}
      </nav>

      <div className="pt-4 border-t border-gray-200">
        <div className="text-xs text-gray-500 text-center">
          <p>快捷键：</p>
          <p>⌘⇧N 捕获</p>
          <p>⌘⇧R 反省</p>
        </div>
      </div>
    </aside>
  );
}
