import { useEffect } from 'react';
import { useStore } from './store';
import { useShortcuts } from './hooks/useShortcuts';
import Layout from './components/Layout';
import LibraryPage from './pages/LibraryPage';
import TodayPage from './pages/TodayPage';
import ReviewPage from './pages/ReviewPage';
import ReflectionPage from './pages/ReflectionPage';
import SettingsPage from './pages/SettingsPage';
import CaptureModal from './components/CaptureModal';
import ReflectionCard from './components/ReflectionCard';
import { getVersion } from '@tauri-apps/api/app';

function App() {
  const { currentView, isCaptureModalOpen, isReflectionCardOpen } = useStore();
  useShortcuts();

  useEffect(() => {
    // Initialize app
    const init = async () => {
      try {
        const version = await getVersion();
        console.log(`FragmentTutor v${version}`);
      } catch {
        // Not running in Tauri
      }
    };
    init();
  }, []);

  const renderPage = () => {
    switch (currentView) {
      case 'library':
        return <LibraryPage />;
      case 'today':
        return <TodayPage />;
      case 'review':
        return <ReviewPage />;
      case 'reflection':
        return <ReflectionPage />;
      case 'settings':
        return <SettingsPage />;
      default:
        return <LibraryPage />;
    }
  };

  return (
    <Layout>
      {renderPage()}
      
      {/* Modals */}
      {isCaptureModalOpen && <CaptureModal />}
      {isReflectionCardOpen && <ReflectionCard />}
    </Layout>
  );
}

export default App;
