import { createContext, useContext, useState, useCallback } from "react";
import { useMultiIssueResearch } from "@/hooks/useMultiIssueResearch";
import type { CompareStatus, RepResult } from "@/hooks/useMultiIssueResearch";
import type { Representative, IssueInfo } from "@/types";

function repId(rep: Representative): string {
  return `${rep.name}|${rep.office}`;
}

interface IssuesContextValue {
  // Form state
  query: string;
  setQuery: (q: string) => void;
  selected: Set<string>;
  toggleRep: (rep: Representative) => void;
  lastQuery: string;

  // Research state
  compareStatus: CompareStatus;
  matchedIssue: IssueInfo | null;
  errorMessage: string | null;
  compareIssue: (query: string, reps: Representative[]) => Promise<void>;
  getResult: (rep: Representative) => RepResult;
  retryRep: (rep: Representative, query: string) => Promise<void>;
  comparedReps: Representative[];

  // Submit handler
  handleSubmit: (selectedReps: Representative[]) => Promise<void>;
}

const IssuesContext = createContext<IssuesContextValue | null>(null);

export function IssuesProvider({ children }: { children: React.ReactNode }) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [lastQuery, setLastQuery] = useState("");

  const research = useMultiIssueResearch();

  const toggleRep = useCallback((rep: Representative) => {
    setSelected((prev) => {
      const next = new Set(prev);
      const id = repId(rep);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const handleSubmit = useCallback(
    async (selectedReps: Representative[]) => {
      const trimmed = query.trim();
      if (!trimmed || selectedReps.length === 0 || research.compareStatus === "matching") return;
      setLastQuery(trimmed);
      await research.compareIssue(trimmed, selectedReps);
    },
    [query, research],
  );

  return (
    <IssuesContext.Provider
      value={{
        query,
        setQuery,
        selected,
        toggleRep,
        lastQuery,
        compareStatus: research.compareStatus,
        matchedIssue: research.matchedIssue,
        errorMessage: research.errorMessage,
        compareIssue: research.compareIssue,
        getResult: research.getResult,
        retryRep: research.retryRep,
        comparedReps: research.comparedReps,
        handleSubmit,
      }}
    >
      {children}
    </IssuesContext.Provider>
  );
}

export function useIssues() {
  const ctx = useContext(IssuesContext);
  if (!ctx) throw new Error("useIssues must be used within IssuesProvider");
  return ctx;
}
