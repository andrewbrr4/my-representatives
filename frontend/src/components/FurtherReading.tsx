/**
 * Reusable "Further reading" expandable list — the deduped Tavily pool
 * that informed an AI overview/issue summary. Distinct from inline
 * citations: citations enforce trust on bullets via [N] markers; this
 * list is the broader exploration pool, encouraging the user to do their
 * own independent research as a jumping-off point from the AI summary.
 */

import { ChevronDown, ChevronRight } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

export interface SourceLink {
  title: string;
  url: string;
}

interface FurtherReadingProps {
  sources: SourceLink[] | undefined;
}

export function FurtherReading({ sources }: FurtherReadingProps) {
  if (!sources || sources.length === 0) return null;

  return (
    <Collapsible className="not-prose mt-4">
      <CollapsibleTrigger className="flex w-full items-center gap-1 text-xs font-bold uppercase tracking-wider text-foreground hover:text-foreground/80 cursor-pointer group">
        <ChevronRight className="h-4 w-4 group-data-[state=open]:hidden" />
        <ChevronDown className="h-4 w-4 group-data-[state=closed]:hidden" />
        Further reading
        <span className="ml-1 font-bold text-muted-foreground">({sources.length})</span>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <ul className="list-disc pl-5 mt-2 space-y-1.5 text-sm">
          {sources.map((s, i) => (
            <li key={i}>
              <a
                href={s.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline underline-offset-2 hover:text-primary/80 break-all"
              >
                {s.title}
              </a>
            </li>
          ))}
        </ul>
      </CollapsibleContent>
    </Collapsible>
  );
}
