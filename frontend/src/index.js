import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

async function initializeMonitoring() {
  const [{ default: posthog }, Sentry] = await Promise.all([
    import('posthog-js'),
    import('@sentry/react'),
  ]);
  posthog.init("phc_w8UKLx4tra285j82owMe6AYVsScrDxnGApBZvW5ZC38J", {
    api_host: "https://us.i.posthog.com",
    capture_pageview: true,
    capture_pageleave: true,
  });
  Sentry.init({
    dsn: "https://e8ef0145205dcfe0fa6a6aee20153299@o4511416842715136.ingest.us.sentry.io/4511416944558080",
    environment: process.env.NODE_ENV,
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({ maskAllInputs: true, maskAllText: true }),
    ],
    tracesSampleRate: 1.0,
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
  });
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

initializeMonitoring().catch((error) => {
  console.warn('[monitoring] initialization failed', error);
});
