import { useStore } from '../store';

export default function Header() {
  const { setIsCaptureModalOpen, setIsReflectionCardOpen } = useStore();

  return (
    <header className="bg-white border-b border-gray-200 px-6 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-semibold text-gray-900">
            FragmentTutor
          </h1>
          <span className="text-sm text-gray-500">
            碎片时间学习助手
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsCaptureModalOpen(true)}
            className="btn-primary"
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            捕获
          </button>
          
          <button
            onClick={() => setIsReflectionCardOpen(true)}
            className="btn-secondary"
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            60秒反省
          </button>
        </div>
      </div>
    </header>
  );
}
