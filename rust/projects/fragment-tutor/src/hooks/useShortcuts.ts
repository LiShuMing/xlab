import { useEffect, useCallback } from 'react';
import { useStore } from '../store';
import { useReflection } from './useReflection';

export function useShortcuts() {
  const { setCurrentView, setIsCaptureModalOpen } = useStore();
  const { openReflection } = useReflection();

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
    const modifier = isMac ? e.metaKey : e.ctrlKey;

    // Cmd/Ctrl + Shift + R: Open reflection card
    if (modifier && e.shiftKey && e.key === 'r') {
      e.preventDefault();
      openReflection();
      return;
    }

    // Cmd/Ctrl + Shift + N: Open capture modal
    if (modifier && e.shiftKey && e.key === 'n') {
      e.preventDefault();
      setIsCaptureModalOpen(true);
      return;
    }

    // Escape: Close modals
    if (e.key === 'Escape') {
      setIsCaptureModalOpen(false);
      // Reflection card handles its own close
    }

    // Navigation shortcuts
    if (modifier && !e.shiftKey && !e.altKey) {
      switch (e.key) {
        case '1':
          e.preventDefault();
          setCurrentView('library');
          break;
        case '2':
          e.preventDefault();
          setCurrentView('today');
          break;
        case '3':
          e.preventDefault();
          setCurrentView('review');
          break;
        case '4':
          e.preventDefault();
          setCurrentView('reflection');
          break;
        case ',':
          e.preventDefault();
          setCurrentView('settings');
          break;
      }
    }
  }, [setCurrentView, setIsCaptureModalOpen, openReflection]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}
