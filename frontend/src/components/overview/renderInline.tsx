/**
 * Shared inline text renderer — handles **bold**, *italic*, and [N] citations.
 * Used across all overview versions and IssueSearch.
 */

import type { Citation } from "@/types";

export function renderInline(
  text: string,
  citations: Citation[],
): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|\[\d+\])/g);
  return parts.map((part, i) => {
    const boldMatch = part.match(/^\*\*(.+)\*\*$/);
    if (boldMatch) {
      return <strong key={i}>{boldMatch[1]}</strong>;
    }
    const italicMatch = part.match(/^\*(.+)\*$/);
    if (italicMatch) {
      return <em key={i}>{italicMatch[1]}</em>;
    }
    const citeMatch = part.match(/^\[(\d+)\]$/);
    if (citeMatch) {
      const idx = parseInt(citeMatch[1], 10) - 1;
      const citation = citations[idx];
      if (citation) {
        return (
          <sup key={i}>
            <a
              href={citation.url}
              target="_blank"
              rel="noopener noreferrer"
              title={citation.title}
              className="text-primary hover:text-primary/80 ml-0.5"
            >
              [{citeMatch[1]}]
            </a>
          </sup>
        );
      }
    }
    return part;
  });
}
