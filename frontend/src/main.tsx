import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/lib/queryClient";
import { AddressProvider } from "@/contexts/AddressContext";
import { IssuesProvider } from "@/contexts/IssuesContext";
import "./index.css";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/source-serif-4/600.css";
import "@fontsource/source-serif-4/700.css";
import App from "./App.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AddressProvider>
          <IssuesProvider>
            <App />
          </IssuesProvider>
        </AddressProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>
);
