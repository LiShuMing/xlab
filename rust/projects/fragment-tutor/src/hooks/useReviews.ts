import { useCallback, useState } from 'react';
import { useStore } from '../store';
import { databaseService } from '../services';
import type { ReviewItem } from '../types';

export function useReviews() {
  const { reviewQueue, setReviewQueue, currentReviewItem, setCurrentReviewItem } = useStore();
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({
    totalDue: 0,
    totalLearned: 0,
    todayCompleted: 0,
  });

  const loadReviewQueue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await databaseService.getReviewQueue();
      setReviewQueue(items);
      setStats({
        totalDue: items.filter(i => !i.lastScore).length,
        totalLearned: items.filter(i => i.lastScore !== null).length,
        todayCompleted: 0, // Would need additional tracking
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load review queue');
    } finally {
      setLoading(false);
    }
  }, [setReviewQueue]);

  const submitReview = useCallback(async (itemId: string, score: number) => {
    try {
      await databaseService.submitReview(itemId, score);
      
      // Update local queue
      setReviewQueue(reviewQueue.filter(item => item.id !== itemId));
      setCurrentReviewItem(null);
      
      // Reload queue to get updated schedule
      await loadReviewQueue();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to submit review');
      throw e;
    }
  }, [reviewQueue, setReviewQueue, setCurrentReviewItem, loadReviewQueue, setError]);

  const createVocabCard = useCallback(async (
    word: string, 
    definition: string, 
    context: string,
    documentId?: string
  ) => {
    try {
      const card = await databaseService.createVocabCard(word, definition, context, documentId);
      await loadReviewQueue();
      return card;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create card');
      throw e;
    }
  }, [loadReviewQueue, setError]);

  const createInsightCard = useCallback(async (
    insight: string,
    context: string,
    documentId?: string
  ) => {
    try {
      const card = await databaseService.createInsightCard(insight, context, documentId);
      await loadReviewQueue();
      return card;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create card');
      throw e;
    }
  }, [loadReviewQueue, setError]);

  const startReview = useCallback((item: ReviewItem) => {
    setCurrentReviewItem(item);
  }, [setCurrentReviewItem]);

  const skipReview = useCallback(() => {
    setCurrentReviewItem(null);
  }, [setCurrentReviewItem]);

  return {
    reviewQueue,
    currentReviewItem,
    loading,
    error,
    stats,
    loadReviewQueue,
    submitReview,
    createVocabCard,
    createInsightCard,
    startReview,
    skipReview,
  };
}
