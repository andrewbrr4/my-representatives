import { NavLink } from "react-router-dom";

export function TabNav() {
  return (
    <div className="flex gap-1 border-b mb-6 max-w-4xl mx-auto">
      <NavLink
        to="/reps"
        className={({ isActive }) =>
          `px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            isActive
              ? "border-primary text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`
        }
      >
        My Representatives
      </NavLink>
      <NavLink
        to="/elections"
        className={({ isActive }) =>
          `px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            isActive
              ? "border-primary text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`
        }
      >
        Upcoming Elections
      </NavLink>
    </div>
  );
}
