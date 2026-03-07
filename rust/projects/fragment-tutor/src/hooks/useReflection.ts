import { useCallback, useEffect, useState } from 'react';
import { useStore } from '../store';
import { databaseService } from '../services';
import type { Reflection, ReflectionStats } from '../types';
import { format } from 'date-fns';

export function useReflection() {
  const { isReflectionCardOpen, setIsReflectionCardOpen } = useStore();
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentReflection, setCurrentReflection] = useState<Reflection | null>(null);
  const [stats, setStats] = useState<ReflectionStats | null>(null);

  const loadTodayReflection = useCallback(async () => {
    const today = format(new Date(), 'yyyy-MM-dd');
    try {
      const reflection = await databaseService.getReflection(today);
      setCurrentReflection(reflection);
    } catch (e) {
      console.error('Failed to load reflection:', e);
    }
  }, []);

  const loadStats = useCallback(async () => {
    try {
      const stats = await databaseService.getReflectionStats();
      setStats(stats);
    } catch (e) {
      console.error('Failed to load stats:', e);
    }
  }, []);

  useEffect(() => {
    if (isReflectionCardOpen) {
      loadTodayReflection();
      loadStats();
    }
  }, [isReflectionCardOpen, loadTodayReflection, loadStats]);

  const saveReflection = useCallback(async (data: {
    keyWin: string;
    avoidance: string;
    nextFix: string;
    deepWorkMin: number;
    familyMin: number;
    sleepH: number;
    notes?: string;
  }) => {
    setLoading(true);
    setError(null);
    try {
      const reflection = await databaseService.saveReflection(data);
      setCurrentReflection(reflection);
      await loadStats();
      return reflection;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save reflection');
      throw e;
    } finally {
      setLoading(false);
    }
  }, [loadStats, setError]);

  const openReflection = useCallback(() => {
    setIsReflectionCardOpen(true);
  }, [setIsReflectionCardOpen]);

  const closeReflection = useCallback(() => {
    setIsReflectionCardOpen(false);
  }, [setIsReflectionCardOpen]);

  const loadReflectionLog = useCallback(async (days: number = 30) => {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - days);
    
    try {
      const logs = await databaseService.getReflectionLog(
        format(startDate, 'yyyy-MM-dd'),
        format(endDate, 'yyyy-MM-dd')
      );
      return logs;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load reflection log');
      return [];
    }
  }, [setError]);

  return {
    isOpen: isReflectionCardOpen,
    currentReflection,
    stats,
    loading,
    error,
    saveReflection,
    openReflection,
    closeReflection,
    loadTodayReflection,
    loadStats,
    loadReflectionLog,
  };
}
