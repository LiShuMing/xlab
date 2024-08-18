import { extractExcerpt, extractTitle, normalizeMarkdownForReader, readingMinutes } from './markdown';

export function basename(path) {
  return path.split('/').pop();
}

export function titleizeSlug(slug) {
  return slug
    .split('-')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export function bookIdFromPath(path) {
  const parts = path.split('/docs/books/')[1]?.split('/') ?? [];
  return parts.length > 1 ? parts[0] : null;
}

export function relativeBookPath(path) {
  const parts = path.split('/docs/books/')[1]?.split('/') ?? [];
  return parts.slice(1).join('/');
}

export function isBookMetadataPath(relativePath) {
  return ['README.md', 'SPEC.md', 'TASK_SPEC.md'].includes(relativePath);
}

export function chapterOrder(path) {
  const relativePath = relativeBookPath(path);
  if (relativePath === 'README.md') return 0;
  if (isBookMetadataPath(relativePath)) return -1;
  const match = relativePath.match(/(?:^|\/)(?:ch-?|chapter-)(\d+)/i);
  return match ? Number(match[1]) : 999;
}

export function compareChapters(a, b) {
  const appendixA = a.relativePath.toLowerCase().startsWith('appendix');
  const appendixB = b.relativePath.toLowerCase().startsWith('appendix');
  if (appendixA !== appendixB) return appendixA ? 1 : -1;
  return a.order - b.order || a.relativePath.localeCompare(b.relativePath);
}

export function chapterLabel(chapter, index) {
  const number = chapter.order === 999 ? index + 1 : chapter.order;
  return String(number).padStart(2, '0');
}

export function relativeDocsPath(path, collection) {
  return path.split(`/docs/${collection}/`)[1] ?? basename(path);
}

export function documentCategory(relativePath, fallback = 'Notes') {
  const parts = relativePath.split('/');
  if (parts.length <= 1) return fallback;
  return titleizeSlug(parts[0]);
}

export function documentDateSignal(relativePath) {
  return relativePath.match(/20\d{2}/)?.[0] ?? 'Evergreen';
}

export function buildDocumentCollection(modules, collection, fallbackCategory) {
  return Object.entries(modules)
    .map(([path, markdown]) => {
      const relativePath = relativeDocsPath(path, collection);
      const xlabPath = `docs/${collection}/${relativePath}`;
      const fallbackTitle = titleizeSlug(relativePath.replace(/\.md$/, '').replace(/\//g, '-'));
      const readerMarkdown = normalizeMarkdownForReader(markdown, fallbackTitle);
      return {
        id: path,
        title: extractTitle(readerMarkdown, fallbackTitle),
        excerpt: extractExcerpt(readerMarkdown),
        markdown: readerMarkdown,
        relativePath,
        xlabPath,
        category: documentCategory(relativePath, fallbackCategory),
        filename: basename(path),
        minutes: readingMinutes(readerMarkdown),
        dateSignal: documentDateSignal(relativePath),
      };
    })
    .sort((a, b) => a.category.localeCompare(b.category) || a.title.localeCompare(b.title));
}
