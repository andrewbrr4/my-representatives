import { useEffect, useState } from "react";
import { useFactsQuery } from "@/hooks/useFactsQuery";

const ROTATE_MS = 6000;

/** Fisher–Yates shuffle of [0..n). */
function shuffledIndices(n: number): number[] {
  const order = Array.from({ length: n }, (_, i) => i);
  for (let i = n - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }
  return order;
}

/**
 * Rotating civics/America fun facts shown while research loads. Renders
 * nothing until facts have loaded, so the progress bar alone carries the
 * loading state if the facts endpoint is empty or slow.
 *
 * Each instance shuffles the fact order independently, so multiple carousels
 * sharing the same (cached) fact list — e.g. one per rep on the compare page —
 * show different facts. The shuffle and rotation both run in an effect, never
 * during render, so Math.random/setState stay out of the render path.
 */
export function FactsCarousel({ issueId }: { issueId?: string } = {}) {
  const { data: facts } = useFactsQuery(issueId);
  const [order, setOrder] = useState<number[]>([]);
  const [pos, setPos] = useState(0);

  useEffect(() => {
    if (!facts || facts.length === 0) return;
    setOrder(shuffledIndices(facts.length));
    setPos(0);
    const timer = setInterval(() => {
      setPos((p) => (p + 1) % facts.length);
    }, ROTATE_MS);
    return () => clearInterval(timer);
  }, [facts]);

  if (!facts || facts.length === 0 || order.length === 0) return null;

  const factIdx = order[pos % order.length];

  return (
    <div className="mt-3 rounded-lg border bg-muted/40 p-3">
      <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
        Did you know?
      </p>
      <p key={pos} className="mt-1 text-sm leading-relaxed">
        {facts[factIdx]}
      </p>
    </div>
  );
}
