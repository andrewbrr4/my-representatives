import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AddressProvider } from "@/contexts/AddressContext";
import "./index.css";
import App from "./App.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AddressProvider>
        <App />
      </AddressProvider>
    </BrowserRouter>
  </StrictMode>
);
