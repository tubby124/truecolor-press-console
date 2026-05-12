import { useStore } from "../store";

// Inline styles override the CSS class so loud errors stay loud even if
// `.toast.error` isn't styled in App.css yet. The previous version rendered
// errors at the same visual weight as info toasts and operators missed them.
const LEVEL_STYLE: Record<string, React.CSSProperties> = {
  error: {
    background: "#c1272d",
    color: "#fff",
    border: "2px solid #ff5a5a",
    boxShadow: "0 4px 18px rgba(193,39,45,0.55)",
    fontSize: 15,
    fontWeight: 600,
    padding: "12px 16px",
    minWidth: 320,
    maxWidth: 560,
  },
  warn: {
    background: "#a86b00",
    color: "#fff",
    border: "1px solid #d99a2b",
    fontSize: 14,
    padding: "10px 14px",
  },
  success: {
    background: "#1f6b3a",
    color: "#fff",
    border: "1px solid #2f9e57",
    fontSize: 14,
    padding: "10px 14px",
  },
  info: {
    background: "var(--panel-2, #2a2a2e)",
    color: "var(--text, #f5f5f5)",
    border: "1px solid var(--border, #333)",
    fontSize: 13,
    padding: "8px 12px",
  },
};

const LEVEL_ICON: Record<string, string> = {
  error: "⛔",
  warn: "⚠️",
  success: "✓",
  info: "·",
};

export function Toasts() {
  const toasts = useStore((s) => s.toasts);
  const dismiss = useStore((s) => s.dismissToast);
  if (!toasts.length) return null;
  return (
    <div className="toasts" style={{ zIndex: 9999 }}>
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`toast ${t.level}`}
          onClick={() => dismiss(t.id)}
          role={t.level === "error" ? "alert" : "status"}
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 10,
            borderRadius: 8,
            cursor: "pointer",
            ...(LEVEL_STYLE[t.level] || LEVEL_STYLE.info),
          }}
          title="Click to dismiss"
        >
          <span style={{ fontSize: 18, lineHeight: 1.2 }} aria-hidden>
            {LEVEL_ICON[t.level] || "·"}
          </span>
          <span style={{ flex: 1, lineHeight: 1.45, whiteSpace: "pre-wrap" }}>{t.text}</span>
          <span
            aria-label="Dismiss"
            style={{
              opacity: 0.7,
              fontSize: 16,
              lineHeight: 1,
              marginLeft: 8,
            }}
          >
            ✕
          </span>
        </div>
      ))}
    </div>
  );
}
