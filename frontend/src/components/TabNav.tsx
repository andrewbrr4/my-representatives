import { NavLink } from "react-router-dom";

function tabClass({ isActive }: { isActive: boolean }) {
  return `px-4 py-2.5 text-xs font-bold uppercase tracking-wider border-b-2 -mb-px transition-colors rounded-t-sm ${
    isActive
      ? "border-foreground text-foreground bg-card"
      : "border-transparent text-muted-foreground hover:text-foreground hover:bg-card/60"
  }`;
}

export function TabNav() {
  return (
    <div className="flex gap-1 border-b mb-6 max-w-4xl mx-auto">
      <NavLink to="/reps" className={tabClass}>
        Representative Overview
      </NavLink>
      <NavLink to="/issues" className={tabClass}>
        On the Issues
      </NavLink>
      <NavLink to="/elections" className={tabClass}>
        Upcoming Elections
      </NavLink>
    </div>
  );
}
