import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{ maxWidth: 600, margin: "60px auto", padding: "24px", fontFamily: "monospace" }}>
          <div style={{ color: "#ef4444", marginBottom: 12, fontWeight: 700 }}>
            Something went wrong
          </div>
          <pre style={{ color: "#8888a0", fontSize: "0.8rem", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
            {this.state.error.message}
          </pre>
          <button
            onClick={() => { this.setState({ error: null }); }}
            style={{ marginTop: 16, padding: "8px 18px", cursor: "pointer", background: "#12121a", border: "1px solid #1e1e2e", color: "#e4e4ef", borderRadius: 8 }}
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
);
