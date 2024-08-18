import pyRadarFeed from '../data/pyRadarFeed';

export const radarTypeLabels = {
  release: '发布',
  benchmark: '基准',
  blog: '博客',
  news: '新闻',
  tutorial: '教程',
  engine: '引擎',
  paper: '论文',
  other: '文章',
};

export function formatRadarDate(value) {
  if (!value) return 'Unknown';
  const dateValue = new Date(`${value}T00:00:00`);
  if (Number.isNaN(dateValue.getTime())) return value;
  return dateValue.toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
  });
}

export function radarTypeLabel(type) {
  return radarTypeLabels[type] ?? type ?? '文章';
}

export function radarReadingSignal(item) {
  const text = `${item.title} ${item.summary} ${item.tags?.join(' ') ?? ''}`.toLowerCase();
  if (text.includes('postgres') || text.includes('mysql') || text.includes('query')) return 'Query & Engine';
  if (text.includes('spark') || text.includes('lakehouse') || text.includes('warehouse')) return 'Analytics';
  if (text.includes('release') || text.includes('version') || text.includes('launch')) return 'Release Watch';
  if (text.includes('benchmark') || text.includes('performance')) return 'Performance';
  return 'DB Systems';
}

export function fallbackRadarPayload() {
  return {
    items: pyRadarFeed.items ?? [],
    total_items: pyRadarFeed.totalItems ?? pyRadarFeed.items?.length ?? 0,
    products: pyRadarFeed.products ?? [],
    contentTypes: pyRadarFeed.contentTypes ?? [],
    latestSyncBatch: pyRadarFeed.latestSyncBatch,
  };
}
