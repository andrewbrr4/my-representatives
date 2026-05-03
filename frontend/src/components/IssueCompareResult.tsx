import { ChevronDown, ChevronRight } from "lucide-react";
import type { Representative } from "@/types";
import type { RepResult } from "@/hooks/useMultiIssueResearch";
import { FurtherReading } from "@/components/FurtherReading";
import { renderInline } from "@/components/overview/renderInline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

const levelColors: Record<string, string> = {
  federal: "bg-blue-600 text-white hover:bg-blue-700",
  state: "bg-amber-600 text-white hover:bg-amber-700",
  municipal: "bg-emerald-600 text-white hover:bg-emerald-700",
};

interface IssueCompareResultProps {
  rep: Representative;
  result: RepResult;
  onRetry: () => void;
}

export function IssueCompareResult({ rep, result, onRetry }: IssueCompareResultProps) {
  const { status, summary } = result;

  return (
    <Collapsible defaultOpen className="rounded-lg border bg-card text-card-foreground shadow-sm">
      <div className="p-4">
        <CollapsibleTrigger className="flex w-full items-center gap-2 cursor-pointer group">
          <ChevronRight className="h-4 w-4 group-data-[state=open]:hidden flex-shrink-0" />
          <ChevronDown className="h-4 w-4 group-data-[state=closed]:hidden flex-shrink-0" />
          <div className="flex items-center gap-2 flex-wrap min-w-0">
            <span className="font-semibold text-foreground">{rep.name}</span>
            <Badge className={levelColors[rep.level] || ""} variant="default">
              {rep.level}
            </Badge>
            <span className="text-sm text-muted-foreground">
              {rep.office}
              {rep.party && ` · ${rep.party}`}
            </span>
          </div>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="mt-3 pl-6">
            {status === "loading" && !summary?.stance_summary && (
              <div className="space-y-1.5">
                <Skeleton className="h-3.5 w-full" />
                <Skeleton className="h-3.5 w-5/6" />
                <Skeleton className="h-3.5 w-4/6" />
              </div>
            )}

            {(status === "loading" || status === "complete") && summary?.stance_summary && (
              <>
                <ul className="list-disc pl-5 space-y-1 text-sm leading-relaxed">
                  {summary.stance_summary.map((item, i) => (
                    <li key={i}>{renderInline(item, summary.citations ?? [])}</li>
                  ))}
                </ul>
                <FurtherReading sources={summary.further_reading} />
              </>
            )}

            {status === "failed" && (
              <div className="flex items-center gap-3">
                <p className="text-sm text-muted-foreground italic">
                  Research failed for this representative.
                </p>
                <Button onClick={onRetry} variant="outline" size="sm">
                  Retry
                </Button>
              </div>
            )}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
