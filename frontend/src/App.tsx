import { Routes, Route, Navigate } from "react-router-dom";
import { useAddress } from "@/contexts/AddressContext";
import { SearchPage } from "@/pages/SearchPage";
import { RepresentativesPage } from "@/pages/RepresentativesPage";
import { ElectionsPage } from "@/pages/ElectionsPage";
import { IssuesPage } from "@/pages/IssuesPage";
import { TabNav } from "@/components/TabNav";

function RequireAddress({ children }: { children: React.ReactNode }) {
  const { address } = useAddress();
  if (!address) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function ResultsLayout({ children }: { children: React.ReactNode }) {
  const { address, clearAddress } = useAddress();

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="text-center mb-8">
          <h1 className="text-5xl font-bold tracking-tight mb-2">KnowMyReps</h1>
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Your elected officials, at every level
          </p>
        </div>

        <div className="flex justify-center mb-6">
          <div className="flex items-center gap-3 text-sm">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Results for
            </span>
            <strong className="text-foreground font-semibold">{address}</strong>
            <button
              onClick={clearAddress}
              className="text-xs font-semibold uppercase tracking-wider text-primary underline underline-offset-2 hover:text-primary/80"
            >
              New search
            </button>
          </div>
        </div>

        <TabNav />
        {children}
      </div>
    </div>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<SearchPage />} />
      <Route
        path="/reps"
        element={
          <RequireAddress>
            <ResultsLayout>
              <RepresentativesPage />
            </ResultsLayout>
          </RequireAddress>
        }
      />
      <Route
        path="/elections"
        element={
          <RequireAddress>
            <ResultsLayout>
              <ElectionsPage />
            </ResultsLayout>
          </RequireAddress>
        }
      />
      <Route
        path="/issues"
        element={
          <RequireAddress>
            <ResultsLayout>
              <IssuesPage />
            </ResultsLayout>
          </RequireAddress>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
