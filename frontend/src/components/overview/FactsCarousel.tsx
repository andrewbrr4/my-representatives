import { useEffect, useState } from "react";
import { useFactsQuery } from "@/hooks/useFactsQuery";

const ROTATE_MS = 6000;

/**
 * Rotating civics/America fun facts shown while research loads. Renders
 * nothing until facts have loaded, so the progress bar alone carries the
 * loading state if the facts endpoint is empty or slow.
 */
export function FactsCarousel() {
  const { data: facts } = useFactsQuery();
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    if (!facts || facts.length === 0) return;
    setIdx(Math.floor(Math.random() * facts.length));
    const timer = setInterval(() => {
      setIdx((i) => (i + 1) % facts.length);
    }, ROTATE_MS);
    return () => clearInterval(timer);
  }, [facts]);

  if (!facts || facts.length === 0) return null;

  return (
    <div className="mt-3 rounded-lg border bg-muted/40 p-3">
      <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
        Did you know?
      </p>
      <p key={idx} className="mt-1 text-sm leading-relaxed">
        {facts[idx]}
      </p>
    </div>
  );
}
