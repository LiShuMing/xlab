function renderInline(text) {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\))/g);

  return parts.map((part, index) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={index}>{part.slice(1, -1)}</code>;
    }
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={index}>{part.slice(1, -1)}</em>;
    }
    const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (link) {
      return (
        <a key={index} href={link[2]} target="_blank" rel="noreferrer">
          {link[1]}
        </a>
      );
    }
    return part;
  });
}

const codeKeywords = new Set([
  'async',
  'await',
  'boolean',
  'break',
  'class',
  'const',
  'continue',
  'else',
  'export',
  'extends',
  'false',
  'for',
  'from',
  'function',
  'if',
  'import',
  'interface',
  'let',
  'new',
  'null',
  'number',
  'return',
  'string',
  'true',
  'type',
  'undefined',
  'while',
]);

function highlightCodeLine(line) {
  const parts = [];
  let cursor = 0;
  const tokenPattern = /(\/\/.*|(['"`])(?:\\.|(?!\2).)*\2|\b\d+(?:\.\d+)?\b|\b[A-Za-z_$][\w$]*\b)/g;

  line.replace(tokenPattern, (match, token, quote, offset) => {
    if (offset > cursor) {
      parts.push(line.slice(cursor, offset));
    }

    let className = 'syntax-plain';
    if (match.startsWith('//')) {
      className = 'syntax-comment';
    } else if (quote) {
      className = 'syntax-string';
    } else if (/^\d/.test(match)) {
      className = 'syntax-number';
    } else if (codeKeywords.has(match)) {
      className = 'syntax-keyword';
    } else if (/^[A-Z]/.test(match)) {
      className = 'syntax-type';
    }

    parts.push(
      <span key={`${offset}-${match}`} className={className}>
        {match}
      </span>,
    );
    cursor = offset + match.length;
    return match;
  });

  if (cursor < line.length) {
    parts.push(line.slice(cursor));
  }

  return parts;
}

function HighlightedCode({ code }) {
  const lines = code.split('\n');

  return lines.map((line, index) => (
    <span key={index} className="code-line">
      {highlightCodeLine(line)}
      {index < lines.length - 1 ? '\n' : ''}
    </span>
  ));
}

export function MarkdownReader({ markdown }) {
  const lines = markdown.split('\n');
  const blocks = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      blocks.push({ type: 'hr' });
      index += 1;
      continue;
    }

    if (trimmed.startsWith('```')) {
      const language = trimmed.replace('```', '').trim();
      const code = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith('```')) {
        code.push(lines[index]);
        index += 1;
      }
      blocks.push({ type: 'code', language, content: code.join('\n') });
      index += 1;
      continue;
    }

    if (trimmed.startsWith('|')) {
      const rows = [];
      while (index < lines.length && lines[index].trim().startsWith('|')) {
        rows.push(lines[index].trim());
        index += 1;
      }
      blocks.push({ type: 'table', rows });
      continue;
    }

    if (trimmed.startsWith('- ') || /^\d+\.\s+/.test(trimmed)) {
      const ordered = /^\d+\.\s+/.test(trimmed);
      const items = [];
      while (
        index < lines.length &&
        (ordered ? /^\d+\.\s+/.test(lines[index].trim()) : lines[index].trim().startsWith('- '))
      ) {
        items.push(lines[index].trim().replace(ordered ? /^\d+\.\s+/ : /^-\s+/, ''));
        index += 1;
      }
      blocks.push({ type: ordered ? 'ordered-list' : 'list', items });
      continue;
    }

    if (trimmed.startsWith('>')) {
      const quotes = [];
      while (index < lines.length && lines[index].trim().startsWith('>')) {
        quotes.push(lines[index].trim().replace(/^>\s?/, ''));
        index += 1;
      }
      blocks.push({ type: 'quote', content: quotes.join(' ') });
      continue;
    }

    if (/^\*\[[^\]]+\]:/.test(trimmed)) {
      const notes = [];
      while (index < lines.length && /^\*\[[^\]]+\]:/.test(lines[index].trim())) {
        notes.push(lines[index].trim().replace(/^\*/, ''));
        index += 1;
      }
      blocks.push({ type: 'footnotes', notes });
      continue;
    }

    if (trimmed.startsWith('#')) {
      const level = trimmed.match(/^#+/)?.[0].length ?? 1;
      blocks.push({ type: 'heading', level, content: trimmed.replace(/^#+\s*/, '') });
      index += 1;
      continue;
    }

    const paragraph = [trimmed];
    index += 1;
    while (
      index < lines.length &&
      lines[index].trim() &&
      !lines[index].trim().match(/^(#|>|\s*- |\s*\d+\.\s+|\||```|-{3,}|\*{3,}|_{3,})/)
    ) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    blocks.push({ type: 'paragraph', content: paragraph.join(' ') });
  }

  return (
    <article className="markdown-reader">
      {blocks.map((block, idx) => {
        if (block.type === 'heading') {
          const Tag = `h${Math.min(block.level, 3)}`;
          return <Tag key={idx}>{renderInline(block.content)}</Tag>;
        }
        if (block.type === 'quote') {
          return <blockquote key={idx}>{renderInline(block.content)}</blockquote>;
        }
        if (block.type === 'list' || block.type === 'ordered-list') {
          const Tag = block.type === 'ordered-list' ? 'ol' : 'ul';
          return (
            <Tag key={idx}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderInline(item)}</li>
              ))}
            </Tag>
          );
        }
        if (block.type === 'code') {
          return (
            <div key={idx} className="code-frame">
              {block.language && <span>{block.language}</span>}
              <pre>
                <code>
                  <HighlightedCode code={block.content} />
                </code>
              </pre>
            </div>
          );
        }
        if (block.type === 'footnotes') {
          return (
            <aside key={idx} className="footnote-block">
              {block.notes.map((note, noteIndex) => (
                <p key={noteIndex}>{renderInline(note)}</p>
              ))}
            </aside>
          );
        }
        if (block.type === 'hr') {
          return <hr key={idx} />;
        }
        if (block.type === 'table') {
          const rows = block.rows
            .filter((row) => !/^\|\s*:?-+/.test(row))
            .map((row) =>
              row
                .split('|')
                .slice(1, -1)
                .map((cell) => cell.trim()),
            );
          return (
            <div key={idx} className="table-frame">
              <table>
                {rows[0] && (
                  <thead>
                    <tr>
                      {rows[0].map((cell, cellIndex) => (
                        <th key={cellIndex}>{renderInline(cell)}</th>
                      ))}
                    </tr>
                  </thead>
                )}
                <tbody>
                  {rows.slice(1).map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {row.map((cell, cellIndex) => (
                        <td key={cellIndex}>{renderInline(cell)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        return <p key={idx}>{renderInline(block.content)}</p>;
      })}
    </article>
  );
}
