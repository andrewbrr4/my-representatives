import { useEffect, useState } from "react";
import { useFactsQuery } from "@/hooks/useFactsQuery";

const ROTATE_MS = 6000;

/**
 * Rotating civics/America fun facts shown while research loads. Renders
 * nothing until facts have loaded, so the progress bar alone carries the
 * loading state if the facts endpoint is empty or slow. Rotates sequentially
 * from the first fact; setState happens only in the async interval callback.
 */
export function FactsCarousel({ issueId }: { issueId?: string } = {}) {
  const { data: facts } = useFactsQuery(issueId);
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    if (!facts || facts.length === 0) return;
    const timer = setInterval(() => {
      setIdx((i) => (i + 1) % facts.length);
    }, ROTATE_MS);
    return () => clearInterval(timer);
  }, [facts]);

  if (!facts || facts.length === 0) return null;

  const safeIdx = idx % facts.length;

  return (
    <div className="mt-3 rounded-lg border bg-muted/40 p-3">
      <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
        Did you know?
      </p>
      <p key={safeIdx} className="mt-1 text-sm leading-relaxed">
        {facts[safeIdx]}
      </p>
    </div>
  );
}
