import { BookOpen, CalendarDays, History, RotateCw, Settings } from 'lucide-react';
import { useStore } from '../store';

type ViewId = 'library' | 'today' | 'review' | 'reflection' | 'settings';

const navItems = [
  { id: 'library', label: '知识库', icon: BookOpen, shortcut: '⌘1' },
  { id: 'today', label: '今日任务', icon: CalendarDays, shortcut: '⌘2' },
  { id: 'review', label: '复习队列', icon: RotateCw, shortcut: '⌘3' },
  { id: 'reflection', label: '反省记录', icon: History, shortcut: '⌘4' },
  { id: 'settings', label: '设置', icon: Settings, shortcut: '⌘,' },
] satisfies Array<{ id: ViewId; label: string; icon: typeof BookOpen; shortcut: string }>;

export default function Sidebar() {
  const { currentView, setCurrentView } = useStore();

  return (
    <aside className="hidden w-60 flex-col border-r border-slate-200/80 bg-white/70 p-4 backdrop-blur sm:flex">
      <div className="mb-5 rounded-lg border border-slate-200 bg-white p-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Focus Index</div>
        <div className="mt-2 flex items-end justify-between">
          <span className="text-2xl font-semibold text-slate-950">FT</span>
          <span className="rounded-md bg-cyan-50 px-2 py-1 text-xs font-medium text-cyan-700">
            Live
          </span>
        </div>
      </div>

      <nav className="flex-1 space-y-1">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setCurrentView(item.id)}
            className={currentView === item.id ? 'sidebar-item-active' : 'sidebar-item'}
          >
            <item.icon className="h-4 w-4" />
            <span className="flex-1 text-left">{item.label}</span>
            <span className={currentView === item.id ? 'text-xs text-white/60' : 'text-xs text-slate-400'}>
              {item.shortcut}
            </span>
          </button>
        ))}
      </nav>

      <div className="border-t border-slate-200 pt-4">
        <div className="rounded-lg bg-slate-950 p-3 text-xs text-slate-300">
          <div className="mb-2 font-semibold uppercase tracking-wide text-white">Shortcuts</div>
          <div className="flex justify-between"><span>捕获</span><span>⌘⇧N</span></div>
          <div className="mt-1 flex justify-between"><span>反省</span><span>⌘⇧R</span></div>
        </div>
      </div>
    </aside>
  );
}
