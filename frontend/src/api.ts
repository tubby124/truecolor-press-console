// Thin fetch wrapper. Same-origin (Vite proxies /api in dev, FastAPI serves
// the built bundle from / in prod). 401 redirects to / so the login page renders.

import type {
  BatchItem,
  CancelSpoolResult,
  Finding,
  Health,
  InspectResult,
  Job,
  JobSummary,
  Preset,
  PressLiveState,
  PreviewResult,
  PrinterStatus,
  ScanImportResult,
  ScanInboxResponse,
  ScanSetupResponse,
  Stock,
  TestPattern,
  TraysResponse,
} from "./types";

class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: { Accept: "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (res.status === 401) {
    window.location.href = "/";
    throw new ApiError(401, "not authenticated");
  }
  const text = await res.text();
  let data: unknown = undefined;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : res.statusText;
    throw new ApiError(res.status, detail, data);
  }
  return data as T;
}

export interface UpdateCheck {
  current: string;
  latest: string | null;
  tag: string | null;
  name: string | null;
  notes: string | null;
  zip_url: string | null;
  zip_size: number;
  published_at: string | null;
  update_available: boolean;
  supports_apply: boolean;
  platform: string;
  frozen: boolean;
}

export interface UpdateApplyResult {
  ok: boolean;
  tag?: string;
  version?: string;
  message?: string;
  error?: string;
}

export const api = {
  health: () => request<Health>("/api/health"),
  me: () => request<{ user: string }>("/api/me"),
  presets: () => request<Preset[]>("/api/presets"),
  stocks: () => request<Stock[]>("/api/stocks"),
  rates: () => request<{ color: number; bw: number }>("/api/rates"),
  printer: () => request<PrinterStatus>("/api/printer"),

  // OTA updater (Windows .exe build only). Frontend polls /check on app
  // mount + every 30 min; calls /apply when the user clicks the banner.
  updateCheck: () => request<UpdateCheck>("/api/update/check"),
  updateApply: () => request<UpdateApplyResult>("/api/update/apply", { method: "POST" }),

  // Live press state — SNMP-derived tray + alert + pagecount snapshot.
  // Cached 15s server-side; UI polls every 30s. Use pressStateRefresh to
  // bypass the cache on explicit user action.
  pressState: () => request<PressLiveState>("/api/press/state"),
  pressStateRefresh: () => request<PressLiveState>("/api/press/state/refresh"),

  trays: () => request<TraysResponse>("/api/trays"),
  setTray: (
    tray: string,
    body: { stock_code: string | null; paper_size: string | null; level: string | null }
  ) =>
    request<TraysResponse>(`/api/trays/${tray}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  inspect: (file: File, quantityGuess = 100) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("quantity_guess", String(quantityGuess));
    return request<InspectResult>("/api/inspect", { method: "POST", body: fd });
  },

  bleedFix: (params: { inspect_filename: string; target_bleed_in?: number }) =>
    request<{
      page_count: number;
      page_sizes: [number, number][];
      findings: Finding[];
      can_send: boolean;
      bleed_added_in: number;
    }>("/api/bleed-fix", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        inspect_filename: params.inspect_filename,
        target_bleed_in: params.target_bleed_in ?? 0.125,
      }),
    }),

  preview: (params: {
    inspect_filename: string;
    preset_key: string;
    stock_code: string;
    quantity: number;
    sides: number;
  }) => {
    const fd = new FormData();
    fd.append("inspect_filename", params.inspect_filename);
    fd.append("preset_key", params.preset_key);
    fd.append("stock_code", params.stock_code);
    fd.append("quantity", String(params.quantity));
    fd.append("sides", String(params.sides));
    return request<PreviewResult>("/api/preview", { method: "POST", body: fd });
  },

  submitJob: (params: {
    file: File;
    workflow: string;
    preset_key: string;
    stock_code: string;
    quantity: number;
    sides: number;
  }) => {
    const fd = new FormData();
    fd.append("file", params.file);
    fd.append("workflow", params.workflow);
    fd.append("preset_key", params.preset_key);
    fd.append("stock_code", params.stock_code);
    fd.append("quantity", String(params.quantity));
    fd.append("sides", String(params.sides));
    return request<Job>("/api/job", { method: "POST", body: fd });
  },

  submitBatch: (params: {
    files: File[];
    workflow: string;
    preset_key: string;
    stock_code: string;
    quantity: number;
    sides: number;
  }) => {
    const fd = new FormData();
    for (const f of params.files) fd.append("files", f);
    fd.append("workflow", params.workflow);
    fd.append("preset_key", params.preset_key);
    fd.append("stock_code", params.stock_code);
    fd.append("quantity", String(params.quantity));
    fd.append("sides", String(params.sides));
    return request<BatchItem[]>("/api/batch", { method: "POST", body: fd });
  },

  jobs: (limit = 50) => request<JobSummary[]>(`/api/jobs?limit=${limit}`),
  job: (id: string) => request<Job>(`/api/job/${id}`),
  reprint: (id: string) => request<Job>(`/api/job/${id}/reprint`, { method: "POST" }),
  cancelSpool: (id: string) =>
    request<CancelSpoolResult>(`/api/job/${id}/cancel-spool`, { method: "POST" }),

  // ─── Test patterns (calibration PDFs for tech visit + first prints) ───
  testPatterns: () => request<TestPattern[]>("/api/test-patterns"),
  testPatternPdfUrl: (id: string) => `/api/test-patterns/${id}/file.pdf`,
  printTestPattern: (id: string) =>
    request<Job>(`/api/test-patterns/${id}/print-test`, { method: "POST" }),

  imposedPdfUrl: (id: string) => `/api/job/${id}/imposed.pdf`,
  thumbUrl: (id: string) => `/api/job/${id}/thumb.png`,

  auditCsvUrl: (start?: string, end?: string) => {
    const params = new URLSearchParams();
    if (start) params.set("start", start);
    if (end) params.set("end", end);
    const qs = params.toString();
    return `/api/jobs/audit.csv${qs ? `?${qs}` : ""}`;
  },

  // ─── Scanner inbox (C3070 Scan-to-SMB) ───
  scanInbox: () => request<ScanInboxResponse>("/api/scan/inbox"),
  scanImport: (filename: string) =>
    request<ScanImportResult>("/api/scan/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename }),
    }),
  scanDismiss: (filename: string) =>
    request<{ dismissed: string }>("/api/scan/dismiss", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename }),
    }),
  scanSetup: () => request<ScanSetupResponse>("/api/scan/setup-instructions"),
};

export { ApiError };
