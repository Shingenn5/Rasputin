import { Component, Suspense, useEffect, useState } from "react";

class ViewBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return this.props.active ? (
      <section role="alert" className="p-6">
        <p>This page could not load. Reload the application to try again.</p>
        <button type="button" className="w2-button" onClick={() => window.location.reload()}>Reload application</button>
      </section>
    ) : null;
  }
}

// Defer the first visit, then retain the view so drafts and filters survive navigation.
export function DeferredView({ active, children }) {
  const [visited, setVisited] = useState(active);
  useEffect(() => {
    if (active) setVisited(true);
  }, [active]);
  if (!active && !visited) return null;
  return (
    <ViewBoundary active={active}>
      <Suspense fallback={active ? <p role="status" className="p-6">Loading page…</p> : null}>
        {children}
      </Suspense>
    </ViewBoundary>
  );
}
