import { format, formatDistanceToNow, isToday, isYesterday, parseISO, addDays } from 'date-fns';
import { zhCN } from 'date-fns/locale';

export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  if (isToday(d)) {
    return `今天 ${format(d, 'HH:mm')}`;
  }
  if (isYesterday(d)) {
    return `昨天 ${format(d, 'HH:mm')}`;
  }
  return format(d, 'MM月dd日 HH:mm');
}

export function formatRelative(date: string | Date): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return formatDistanceToNow(d, { locale: zhCN, addSuffix: true });
}

export function formatDueDate(date: string | Date): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  const now = new Date();
  
  if (d <= now) {
    return '现在';
  }
  
  if (isToday(d)) {
    return `今天 ${format(d, 'HH:mm')}`;
  }
  
  const diffDays = Math.ceil((d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  
  if (diffDays === 1) {
    return '明天';
  }
  
  if (diffDays <= 7) {
    return `${diffDays}天后`;
  }
  
  return format(d, 'MM月dd日');
}

export function getNextReviewDate(intervalDays: number): Date {
  return addDays(new Date(), intervalDays);
}

export function formatDuration(minutes: number): string {
  if (minutes < 60) {
    return `${minutes}分钟`;
  }
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (mins === 0) {
    return `${hours}小时`;
  }
  return `${hours}小时${mins}分钟`;
}

export function getReadingTime(wordCount: number, wpm: number = 200): string {
  const minutes = Math.ceil(wordCount / wpm);
  if (minutes < 1) return '1分钟内';
  if (minutes < 60) return `约${minutes}分钟`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `约${hours}小时${mins}分钟`;
}
