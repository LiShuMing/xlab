export function extractTitle(markdown, fallback) {
  return markdown.match(/^#\s+(.+)$/m)?.[1] ?? fallback.replace(/\.md$/, '');
}

export function extractExcerpt(markdown) {
  const quote = markdown.match(/^>\s+(.+)$/m)?.[1];
  if (quote) return quote;

  const paragraph = markdown
    .split('\n')
    .map((line) => line.trim())
    .find((line) => line && !line.startsWith('#') && !line.startsWith('|') && !line.startsWith('-'));

  return paragraph ?? 'Markdown knowledge unit ready for structured reading.';
}

export function readingMinutes(markdown) {
  const words = markdown.replace(/```[\s\S]*?```/g, '').split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.ceil(words / 380));
}

export function normalizeMarkdownForReader(markdown, fallbackTitle) {
  const normalized = markdown.replace(/\r\n/g, '\n').replace(/ /g, ' ').trim();
  const lines = normalized.split('\n');
  const firstContentIndex = lines.findIndex((line) => line.trim());
  const firstHeadingIndex = lines.findIndex((line) => /^#\s+/.test(line.trim()));

  if (firstHeadingIndex > firstContentIndex) {
    return lines.slice(firstHeadingIndex).join('\n').trim();
  }

  if (firstHeadingIndex === -1 && fallbackTitle) {
    return `# ${fallbackTitle}\n\n${normalized}`;
  }

  return normalized;
}
