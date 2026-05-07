import { Component, type ErrorInfo, type ReactNode } from "react";

interface State {
  err: Error | null;
}

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { err: null };

  static getDerivedStateFromError(err: Error): State {
    return { err };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("UI error:", error, info);
  }

  render() {
    if (!this.state.err) return this.props.children;
    return (
      <div style={{ padding: 40, maxWidth: 640, margin: "60px auto", color: "var(--text)" }}>
        <h1 style={{ color: "var(--danger)" }}>Something broke</h1>
        <pre
          style={{
            background: "var(--panel)",
            padding: 14,
            borderRadius: 8,
            overflow: "auto",
            whiteSpace: "pre-wrap",
          }}
        >
          {this.state.err.message}
          {"\n\n"}
          {this.state.err.stack}
        </pre>
        <button
          className="cta"
          type="button"
          onClick={() => {
            this.setState({ err: null });
            window.location.reload();
          }}
        >
          Reload
        </button>
      </div>
    );
  }
}
