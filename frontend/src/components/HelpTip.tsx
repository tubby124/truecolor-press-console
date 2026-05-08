// Tiny "(?)" affordance that opens a small plain-English popover. Used inline
// next to print-shop terms (Bleed, Imposition, DPI, Tray, Stock, etc).
//
// Click toggles. Click outside or press Escape to dismiss. Position is
// computed from the trigger button's getBoundingClientRect at open time so
// it survives layout shifts.

import { useEffect, useRef, useState } from "react";
import { GLOSSARY, lookup } from "./glossary";

interface HelpTipProps {
  /** Glossary key — see components/glossary.ts. */
  glossaryKey: keyof typeof GLOSSARY | string;
  /** Optional override label; defaults to "(?)". */
  label?: string;
}

export function HelpTip({ glossaryKey, label = "?" }: HelpTipProps) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const btnRef = useRef<HTMLButtonElement | null>(null);
  const entry = lookup(glossaryKey);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onClick = (e: MouseEvent) => {
      if (btnRef.current && !btnRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onClick);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  if (!entry) return null;

  const toggle = () => {
    if (!open && btnRef.current) {
      const r = btnRef.current.getBoundingClientRect();
      // Place to the right of the trigger if there's room, else below.
      const placeRight = r.right + 280 < window.innerWidth;
      setPos(
        placeRight
          ? { top: r.top - 4, left: r.right + 8 }
          : { top: r.bottom + 6, left: Math.max(8, r.left - 100) },
      );
    }
    setOpen((v) => !v);
  };

  return (
    <span style={{ display: "inline-flex", alignItems: "center", marginLeft: 4 }}>
      <button
        ref={btnRef}
        type="button"
        onClick={toggle}
        title={`What does "${entry.term}" mean?`}
        aria-label={`Help — ${entry.term}`}
        style={{
          width: 18,
          height: 18,
          borderRadius: "50%",
          border: "1px solid var(--border)",
          background: open ? "var(--accent)" : "transparent",
          color: open ? "white" : "var(--muted)",
          cursor: "pointer",
          fontSize: 11,
          lineHeight: 1,
          padding: 0,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {label}
      </button>
      {open && pos && (
        <div
          role="tooltip"
          style={{
            position: "fixed",
            top: pos.top,
            left: pos.left,
            width: 260,
            background: "#0f172a",
            color: "white",
            borderRadius: 8,
            padding: "10px 12px",
            boxShadow: "0 8px 24px rgba(0,0,0,0.3)",
            zIndex: 800,
            fontSize: 13,
            lineHeight: 1.5,
          }}
        >
          <strong style={{ display: "block", marginBottom: 4 }}>{entry.term}</strong>
          {entry.body}
        </div>
      )}
    </span>
  );
}
