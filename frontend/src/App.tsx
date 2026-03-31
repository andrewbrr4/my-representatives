import { Routes, Route, Navigate } from "react-router-dom";
import { useAddress } from "@/contexts/AddressContext";
import { SearchPage } from "@/pages/SearchPage";
import { RepresentativesPage } from "@/pages/RepresentativesPage";
import { ElectionsPage } from "@/pages/ElectionsPage";
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
          <h1 className="text-4xl font-bold tracking-tight mb-2">KnowMyReps</h1>
          <p className="text-muted-foreground">
            Find your elected representatives at every level of government.
          </p>
        </div>

        <div className="flex justify-center mb-6">
          <div className="flex items-center gap-3 text-sm">
            <span className="text-muted-foreground">
              Results for: <strong className="text-foreground">{address}</strong>
            </span>
            <button
              onClick={clearAddress}
              className="text-primary underline underline-offset-2 hover:text-primary/80"
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
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
