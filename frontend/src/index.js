import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@/index.css";
import App from "@/App";

// Negeer runtime-fouten afkomstig van browser-extensies (bv. MetaMask inpage.js).
// Deze hebben niets met deze app te maken maar triggeren anders de dev-overlay.
const isExtensionError = (msg, source) => {
  const s = `${msg || ""} ${source || ""}`.toLowerCase();
  return (
    s.includes("chrome-extension://") ||
    s.includes("moz-extension://") ||
    s.includes("metamask") ||
    s.includes("failed to connect to metamask")
  );
};

window.addEventListener(
  "error",
  (event) => {
    if (isExtensionError(event.message, event.filename)) {
      event.stopImmediatePropagation();
      event.preventDefault();
    }
  },
  true,
);

window.addEventListener("unhandledrejection", (event) => {
  const reason = event.reason;
  const msg = typeof reason === "string" ? reason : reason?.message || reason?.stack || "";
  if (isExtensionError(msg, reason?.stack)) {
    event.stopImmediatePropagation();
    event.preventDefault();
  }
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
