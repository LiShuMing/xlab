import { BrainCircuit, CheckCircle2, Plus, ScanLine } from 'lucide-react';
import { useStore } from '../store';

export default function Header() {
  const { setIsCaptureModalOpen, setIsReflectionCardOpen } = useStore();

  return (
    <header className="border-b border-slate-200/80 bg-white/90 px-6 py-3 backdrop-blur">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-slate-950 text-white">
            <BrainCircuit className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-sm font-semibold uppercase tracking-wide text-slate-950">
              FragmentTutor
            </h1>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <ScanLine className="h-3.5 w-3.5 text-cyan-600" />
              <span>碎片学习控制台</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsCaptureModalOpen(true)}
            className="btn-primary"
          >
            <Plus className="h-4 w-4" />
            捕获
          </button>

          <button
            onClick={() => setIsReflectionCardOpen(true)}
            className="btn-secondary"
          >
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            60秒反省
          </button>
        </div>
      </div>
    </header>
  );
}
