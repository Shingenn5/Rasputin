import React, { Suspense, lazy, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/rajdhani/500.css";
import "@fontsource/rajdhani/600.css";
import "@fontsource/rajdhani/700.css";
import "./styles/theme.css";
import "bootstrap/dist/css/bootstrap.min.css";
import "./styles/rasputin.css";
import "./styles/dashboard.css";
import "./styles/interface.css";
import { AppProviders } from "./app/AppProviders.jsx";
import { App } from "./app/App.jsx";

const PreviewApp = lazy(() => import("./preview/PreviewApp.jsx").then((module) => ({ default: module.PreviewApp })));

createRoot(document.getElementById("root")).render(
  <Root />,
);

function Root() {
  const previewPath = window.location.pathname.startsWith("/preview");
  const [previewAllowed, setPreviewAllowed] = useState(!previewPath ? false : null);

  useEffect(() => {
    if (!previewPath) return undefined;
    let alive = true;
    fetch("/api/ui/config")
      .then((response) => response.json())
      .then((payload) => {
        if (!alive) return;
        setPreviewAllowed(Boolean(payload?.data?.uiPreviewEnabled));
      })
      .catch(() => {
        if (alive) setPreviewAllowed(false);
      });
    return () => {
      alive = false;
    };
  }, [previewPath]);

  if (previewPath) {
    if (previewAllowed === null) {
      return <div className="preview-loading">Loading RasputinTest preview...</div>;
    }
    if (!previewAllowed) {
      document.body.dataset.ready = "true";
      return (
        <main className="preview-disabled">
          <h1>Preview UI Disabled</h1>
          <p>Start the isolated RasputinTest container with <code>RASPUTIN_UI_PREVIEW=1</code> to use preview routes.</p>
        </main>
      );
    }
    return (
      <Suspense fallback={<div className="preview-loading">Loading RasputinTest preview...</div>}>
        <PreviewApp />
      </Suspense>
    );
  }

  return (
    <AppProviders>
      <App />
    </AppProviders>
  );
}
