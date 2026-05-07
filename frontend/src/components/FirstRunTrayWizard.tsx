import { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { Stock, TrayKey } from "../types";

const TRAY_KEYS: TrayKey[] = ["T1", "T2", "T3", "T4", "T5"];

export function FirstRunTrayWizard({ onDone }: { onDone: () => void }) {
  const setTrays = useStore((s) => s.setTrays);
  const pushToast = useStore((s) => s.pushToast);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [step, setStep] = useState(0);
  const [picks, setPicks] = useState<Record<TrayKey, string | null>>({
    T1: null, T2: null, T3: null, T4: null, T5: null,
  });

  useEffect(() => {
    api.stocks().then(setStocks);
  }, []);

  async function finish() {
    try {
      let last;
      for (const k of TRAY_KEYS) {
        const code = picks[k];
        const stock = stocks.find((s) => s.code === code);
        last = await api.setTray(k, {
          stock_code: code,
          paper_size: stock?.parent_sheet ?? null,
          level: code ? "full" : "unknown",
        });
      }
      if (last) setTrays(last);
      pushToast("success", "Tray setup saved. You can edit any tray any time.");
      onDone();
    } catch (e) {
      pushToast("error", `Setup failed: ${e instanceof Error ? e.message : e}`);
    }
  }

  const tray = TRAY_KEYS[step];

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <h2>First-time setup — what's loaded in each tray?</h2>
        <p>Step {step + 1} of {TRAY_KEYS.length}: {tray}</p>

        <div className="tray-editor-row">
          <label>{tray}</label>
          <select
            value={picks[tray] ?? ""}
            onChange={(e) =>
              setPicks((p) => ({ ...p, [tray]: e.target.value || null }))
            }
          >
            <option value="">— empty / not set —</option>
            {stocks.map((s) => (
              <option key={s.code} value={s.code} title={`${s.name} · ${s.weight}`}>
                {s.friendly_name || s.name} ({s.weight})
              </option>
            ))}
          </select>
        </div>

        <div className="modal-actions">
          {step > 0 && (
            <button className="cta secondary" type="button" onClick={() => setStep(step - 1)}>
              Back
            </button>
          )}
          <button className="cta secondary" type="button" onClick={onDone}>
            Skip — I'll set later
          </button>
          {step < TRAY_KEYS.length - 1 ? (
            <button className="cta" type="button" onClick={() => setStep(step + 1)}>
              Next
            </button>
          ) : (
            <button className="cta" type="button" onClick={finish}>
              Save all
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
